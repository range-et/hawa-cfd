"""Cancellable in-process evaluation jobs. UI calls never join a worker."""
import copy
import threading
import uuid
import torch
from .plugin import Session, SESSIONS, REGISTRY_LOCK, MPS_LOCK, case_key
from .optimization import evaluate


class Cancelled(RuntimeError):
    pass


class Job:
    def __init__(self, request):
        self.request = copy.deepcopy(request)
        self.id = str(uuid.uuid4())
        self.condition = threading.Condition()
        self.cancelled = False
        self.paused = False
        self.disposed = False
        self.session = None
        self.result = None
        self.error = None
        self.state = 'queued'
        self.steps = 0
        self.target = request.get('steps', 200)
        self.key = case_key(request)
        self.holds_device = False
        self.thread = threading.Thread(target=self.work, name='Hawa evaluation '+self.id[:8], daemon=True)

    def checkpoint(self, steps, state='running'):
        # Other device work can run while this job waits or reports a cancel.
        held = self.drop_device()
        with self.condition:
            self.steps = steps
            while self.paused and not self.cancelled:
                self.state = 'paused'
                self.condition.wait()
            if self.cancelled:
                raise Cancelled('Evaluation cancelled')
            self.state = state
        if held:
            self.take_device(state)

    def take_device(self, state='running'):
        """Hold the shared MPS lock for this worker's device work (#99).

        PyTorch's MPS backend aborts when two threads submit work at once, so on
        a Mac a job's device work runs under the lock that MPS sessions step
        under; checkpoint releases it. The job keeps its place in the queue
        while it waits, and gives it up only to pause or cancel.
        """
        if not SHARE_DEVICE_LOCK:
            return
        while not MPS_LOCK.acquire(stop=lambda: self.paused or self.cancelled):
            self.checkpoint(self.steps, state)
        self.holds_device = True

    def drop_device(self):
        held, self.holds_device = self.holds_device, False
        if held:
            MPS_LOCK.release()
        return held

    def work(self):
        try:
            if self.request.get('kind') == 'query':
                from .plugin import dispatch
                self.checkpoint(0)
                # Field, statistics and boundary queries read stored frames on the
                # CPU, and session reads take the session lock. Holding the device
                # lock for them would make views wait behind Solve and Record (#99).
                request = self.request['request']
                if request['op'] == 'field':
                    from .fields import dispatch_field
                    value = dispatch_field(request, SESSIONS.get(request.get('session')), self.checkpoint)
                elif request['op'] == 'statistics':
                    from .flow_statistics import analyze
                    value=analyze(request['manifest'],request['points'],request.get('start_time',0.),request.get('end_time'),self.checkpoint)
                elif request['op'] == 'boundary' and request['action'] == 'capture':
                    from .boundary_data import capture
                    value = capture(request['manifest'], request['case'], request['path'], self.checkpoint,request.get('start_time',0.),request.get('end_time'))
                else:
                    # Other operations can run solver work, such as evaluate.
                    self.take_device()
                    value = dispatch(request)
                with self.condition:
                    if self.cancelled:
                        raise Cancelled('Query cancelled')
                    self.result = value
                    self.state = 'completed'
                return
            # One candidate at a time bounds GPU allocation. Waiting is cancellable
            # and reports 'queued', not 'running', until the device slot is free.
            while not DEVICE_SLOT.acquire(timeout=.05):
                self.checkpoint(self.steps, 'queued')
            try:
                self.checkpoint(0)
                self.take_device()
                if self.request.get('kind') == 'refine':
                    from .refinement import run_refined
                    value=run_refined(self.request,self.checkpoint)
                    with self.condition:
                        if self.cancelled:raise Cancelled('Refinement cancelled')
                        self.result=value;self.steps=self.target;self.state='completed'
                    return
                s = Session(self.request['case'], self.request.get('device', 'auto'))
                self.session = s
                self.checkpoint(0)
                if self.request.get('kind') == 'create':
                    value = {}
                elif self.request.get('kind') == 'motion_evaluate':
                    from .motion import evaluate_motion
                    value=evaluate_motion(s,self.request,self.checkpoint)
                    self.target=value['steps'];s.target=self.target;s.state='completed'
                elif self.request.get('kind') == 'record':
                    from .recording import record
                    value = record(s, self.target, self.request.get('interval', 10), self.request['directory'], self.checkpoint)
                else:
                    value = evaluate(s, self.target, self.request.get('window', 20),
                                     float(self.request['reference_volume']), checkpoint=self.checkpoint)
                with self.condition:
                    if self.cancelled:
                        raise Cancelled('Evaluation cancelled')
                    with REGISTRY_LOCK:
                        SESSIONS[s.id] = s
                    value['status'] = s.status()
                    self.result = value
                    self.steps = self.target
                    self.state = 'completed'
            finally:
                self.drop_device()
                DEVICE_SLOT.release()
        except Cancelled:
            with self.condition:
                self.state = 'cancelled'
        except Exception as exc:
            with self.condition:
                self.error = str(exc)
                self.state = 'failed'
        finally:
            self.drop_device()
            with self.condition:
                if self.state != 'completed' or self.disposed:
                    if self.session is not None:
                        with REGISTRY_LOCK:
                            SESSIONS.pop(self.session.id, None)
                    self.session = None
                    self.result = None

    def snapshot(self):
        with self.condition:
            return {'job': self.id, 'key': self.key, 'state': self.state,
                    'steps': self.steps, 'target': self.target, 'error': self.error,
                    'result': copy.deepcopy(self.result)}

    def control(self, action):
        with self.condition:
            if action == 'close':
                self.disposed = True
                self.cancelled = True
                if self.session is not None and self.state == 'completed':
                    # A completed creation job can own a running Solve session.
                    # Request cancellation before dropping its registry entry.
                    self.session.stop.set()
                    with REGISTRY_LOCK:
                        SESSIONS.pop(self.session.id, None)
                    self.session = None
                self.result = None
                self.condition.notify_all()
            elif self.state in ('completed', 'cancelled', 'failed'):
                return
            elif action == 'pause':
                self.paused = True
                if self.state != 'paused':
                    self.state = 'pausing'
            elif action == 'resume':
                self.paused = False
                self.condition.notify_all()
            elif action == 'cancel':
                self.cancelled = True
                self.state = 'cancelling'
                self.condition.notify_all()
            else:
                raise ValueError('Job control: pause, resume, cancel or close')


DEVICE_SLOT = threading.Semaphore(1)
# Only Apple's MPS backend needs one thread at a time across jobs and sessions.
SHARE_DEVICE_LOCK = torch.backends.mps.is_available()
JOBS = {}
LOCK = threading.Lock()


def dispatch_job(request):
    if request['op'] == 'evaluate_submit':
        job = Job({k:v for k,v in request.items() if k != 'op'})
        with LOCK:
            if len(JOBS) >= 32:
                raise ValueError('Close unused evaluation jobs before submitting more')
            JOBS[job.id] = job
        job.thread.start()
        return job.snapshot()
    with LOCK:
        if request['op'] == 'evaluate_control' and request.get('action') == 'close' and request['job'] not in JOBS:
            return {'closed': True}
        job = JOBS[request['job']]
    if request['op'] == 'evaluate_control':
        action = request['action']
        job.control(action)
        if action == 'close':
            with LOCK:
                JOBS.pop(job.id, None)
    elif request['op'] != 'evaluate_poll':
        raise ValueError('Unknown evaluation operation')
    return job.snapshot()
