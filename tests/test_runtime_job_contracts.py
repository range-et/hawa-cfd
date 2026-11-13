"""Deterministic job state/cleanup tests; no host scheduling claim."""
import copy
import threading
from types import SimpleNamespace

import pytest

from hawa import jobs, plugin


@pytest.fixture
def isolated_jobs(monkeypatch):
    monkeypatch.setattr(jobs, 'JOBS', {})
    monkeypatch.setattr(jobs, 'SESSIONS', {})
    monkeypatch.setattr(jobs, 'DEVICE_SLOT', threading.Semaphore(1))
    return jobs


def request(**values):
    return dict(case={'example': 'tgv3d-bgk', 'size': 8}, device='cpu', steps=4,
                window=2, reference_volume=3., **values)


def test_request_and_snapshot_own_nested_data(isolated_jobs):
    original = request(); job = jobs.Job(original)
    original['case']['size'] = 99
    assert job.request['case']['size'] == 8 and job.target == 4
    job.result = {'nested': {'value': [1, 2]}}
    snapshot = job.snapshot(); snapshot['result']['nested']['value'][0] = 99
    assert job.result['nested']['value'] == [1, 2]
    assert snapshot['job'] == job.id and snapshot['key'] == job.key


def test_checkpoint_pauses_resumes_and_reports_cancellation(isolated_jobs, monkeypatch):
    job = jobs.Job(request()); job.control('pause')
    assert job.state == 'pausing' and job.paused
    waited = []
    def resume():
        waited.append(job.state)
        job.control('resume')
    monkeypatch.setattr(job.condition, 'wait', resume)
    job.checkpoint(3)
    assert waited == ['paused'] and job.state == 'running' and job.steps == 3 and not job.paused
    job.control('cancel')
    assert job.state == 'cancelling' and job.cancelled
    with pytest.raises(jobs.Cancelled): job.checkpoint(4)
    with pytest.raises(ValueError, match='Job control'): jobs.Job(request()).control('unsupported')


def test_job_waiting_for_the_device_reports_queued_until_cancelled(isolated_jobs):
    jobs.DEVICE_SLOT.acquire()
    job = jobs.Job(request(kind='create'))
    # Record the state each slot-wait checkpoint leaves, so the check cannot pass on the constructor's 'queued'.
    seen, waited, original = [], threading.Event(), job.checkpoint
    def checkpoint(steps, *state):
        original(steps, *state)
        seen.append((job.state, job.steps, job.session))
        if len(seen) == 2: waited.set()
    job.checkpoint = checkpoint
    try:
        job.thread.start()
        assert waited.wait(5) and seen[:2] == [('queued', 0, None)] * 2
    finally:
        job.control('cancel'); job.thread.join(5)
        jobs.DEVICE_SLOT.release()
    assert job.state == 'cancelled' and not job.thread.is_alive()
    job = jobs.Job(request()); job.checkpoint(2, 'queued')
    assert job.state == 'queued' and job.steps == 2


@pytest.mark.parametrize('state', ['completed', 'cancelled', 'failed'])
def test_terminal_jobs_ignore_control_but_close_disposes_result(isolated_jobs, state):
    job = jobs.Job(request()); job.state = state; job.result = {'value': 3}
    for operation in ('pause', 'resume', 'cancel'):
        job.control(operation)
        assert job.state == state and job.result == {'value': 3}
    job.control('close')
    assert job.disposed and job.cancelled and job.result is None


@pytest.mark.parametrize('kind', ['create', 'record', 'motion_evaluate', 'evaluate'])
def test_successful_job_routes_options_and_registers_own_session(isolated_jobs, monkeypatch, kind):
    class Session:
        def __init__(self, case, device):
            self.id = 'owned'; self.stop = threading.Event(); self.state = 'ready'; self.target = 0
            assert case == {'example': 'tgv3d-bgk', 'size': 8} and device == 'cpu'
        def status(self): return {'session': self.id, 'state': self.state, 'target': self.target}
    monkeypatch.setattr(jobs, 'Session', Session)
    calls = []
    def evaluate(session, target, window, volume, checkpoint):
        calls.append(('evaluate', target, window, volume)); checkpoint(target)
        return {'fitness': 5.}
    monkeypatch.setattr(jobs, 'evaluate', evaluate)
    from hawa import recording, motion
    def record(session, target, interval, directory, checkpoint):
        calls.append(('record', target, interval, directory)); checkpoint(target)
        return {'manifest': 'fixture.json'}
    def moving(session, req, checkpoint):
        calls.append(('motion', req['kind'])); checkpoint(6)
        return {'steps': 6, 'objective': 3.}
    monkeypatch.setattr(recording, 'record', record)
    monkeypatch.setattr(motion, 'evaluate_motion', moving)
    req = request(kind=kind, interval=2, directory='recorded')
    job = jobs.Job(req); job.work()
    assert job.state == 'completed' and job.session.id == 'owned'
    assert jobs.SESSIONS['owned'] is job.session
    assert job.result['status']['session'] == 'owned'
    if kind == 'create': assert calls == [] and set(job.result) == {'status'}
    if kind == 'record': assert calls == [('record', 4, 2, 'recorded')] and job.result['manifest'] == 'fixture.json'
    if kind == 'motion_evaluate': assert calls == [('motion', 'motion_evaluate')] and job.steps == job.target == 6
    if kind == 'evaluate': assert calls == [('evaluate', 4, 2, 3.)] and job.result['fitness'] == 5.
    session = job.session; job.control('close')
    assert session.stop.is_set() and 'owned' not in jobs.SESSIONS and job.session is None and job.result is None
    assert jobs.DEVICE_SLOT.acquire(blocking=False)
    jobs.DEVICE_SLOT.release()


@pytest.mark.parametrize('cancel', [False, True])
def test_worker_failure_or_late_cancel_never_publishes_session(isolated_jobs, monkeypatch, cancel):
    class Session:
        def __init__(self, *args): self.id = 'unpublished'
        def status(self): return {'session': self.id}
    monkeypatch.setattr(jobs, 'Session', Session)
    job = jobs.Job(request())
    def fail(*args, **kwargs):
        if cancel:
            job.cancelled = True
            return {'fitness': 4}
        raise RuntimeError('solver exploded')
    monkeypatch.setattr(jobs, 'evaluate', fail)
    job.work()
    assert job.state == ('cancelled' if cancel else 'failed')
    assert job.error == (None if cancel else 'solver exploded')
    assert job.result is None and job.session is None and not jobs.SESSIONS
    assert jobs.DEVICE_SLOT.acquire(blocking=False)
    jobs.DEVICE_SLOT.release()


@pytest.mark.parametrize('route', ['field', 'statistics', 'boundary', 'info'])
def test_query_routes_arguments_and_copies_result(isolated_jobs, monkeypatch, route):
    from hawa import fields, flow_statistics, boundary_data
    calls = []
    def called(*args):
        calls.append(args); return {'route': route}
    monkeypatch.setattr(fields, 'dispatch_field', called)
    monkeypatch.setattr(flow_statistics, 'analyze', called)
    monkeypatch.setattr(boundary_data, 'capture', called)
    monkeypatch.setattr(plugin, 'dispatch', called)
    req = dict(op=route, action={'boundary':'capture'}.get(route, 'sample'),
               manifest='parent.json', points=[[1, 2, 3]], case={'shape':[8, 8, 8]},
               path='mapped.npz', start_time=2., end_time=4.)
    job = jobs.Job(dict(kind='query', request=req)); job.work()
    assert job.state == 'completed' and job.result == {'route': route} and job.session is None
    args = calls[0]
    if route == 'field': assert args[0] == req and args[1] is None and args[2] == job.checkpoint
    elif route == 'statistics': assert args == ('parent.json', [[1, 2, 3]], 2., 4., job.checkpoint)
    elif route == 'boundary': assert args == ('parent.json', {'shape':[8, 8, 8]}, 'mapped.npz', job.checkpoint, 2., 4.)
    else: assert args == (req,)


def test_late_query_cancellation_discards_result(isolated_jobs, monkeypatch):
    job = jobs.Job({'kind':'query', 'request':{'op':'info'}})
    def cancelled(req):
        job.cancelled = True
        return {'unpublishable': True}
    monkeypatch.setattr(plugin, 'dispatch', cancelled)
    job.work()
    assert job.state == 'cancelled' and job.result is None


def test_dispatch_enforces_capacity_unknown_operations_and_idempotent_close(isolated_jobs, monkeypatch):
    started = []
    class Thread:
        def __init__(self, target, **kwargs): self.target = target
        def start(self): started.append(self.target)
    monkeypatch.setattr(jobs.threading, 'Thread', Thread)
    created = jobs.dispatch_job(dict(request(), op='evaluate_submit'))
    key = created['job']
    assert len(started) == 1 and jobs.dispatch_job(dict(op='evaluate_poll', job=key))['state'] == 'queued'
    with pytest.raises(ValueError, match='Unknown evaluation'): jobs.dispatch_job(dict(op='unknown', job=key))
    for i in range(31): jobs.JOBS[str(i)] = object()
    with pytest.raises(ValueError, match='Close unused'): jobs.dispatch_job(dict(request(), op='evaluate_submit'))
    assert len(started) == 1
    jobs.dispatch_job(dict(op='evaluate_control', job=key, action='close'))
    assert key not in jobs.JOBS
    assert jobs.dispatch_job(dict(op='evaluate_control', job=key, action='close')) == {'closed': True}


def test_jobs_hold_the_shared_device_lock_outside_checkpoints(isolated_jobs, monkeypatch):
    import time
    lock = plugin.DeviceLock()
    monkeypatch.setattr(jobs, 'MPS_LOCK', lock); monkeypatch.setattr(jobs, 'SHARE_DEVICE_LOCK', True)
    # Every wait is bounded, so a broken loop fails the test instead of hanging it.
    def run(target):
        thread = threading.Thread(target=target, daemon=True); thread.start(); thread.join(2)
        return thread
    def probe():
        free = []
        run(lambda: free.append(lock.acquire(timeout=0) and lock.release() is None))
        return free
    def worker(job, *steps):
        out = []
        def body():
            for step in steps: step()
            out.append((job.holds_device, job.state, job.steps)); job.drop_device()
        assert not run(body).is_alive()
        return out
    job = jobs.Job(request())
    assert worker(job, job.take_device) == [(True, 'queued', 0)] and lock.owner is None and not job.holds_device
    # A busy lock: the first try fails, as if another thread held it for one poll.
    attempts, take = [], lock.acquire
    def busy(timeout=None, stop=None):
        attempts.append(stop)
        return len(attempts) % 2 == 0 and take(timeout)
    monkeypatch.setattr(lock, 'acquire', busy)
    # A wait that gives up reports the caller's state and keeps the step count; it gives up
    # only to pause or cancel.
    for args, state in (((), 'running'), (('starting',), 'starting')):
        job = jobs.Job(request()); job.steps = 3
        assert worker(job, lambda: job.take_device(*args)) == [(True, state, 3)]
        stop = attempts[-2]; assert stop() is False
        job.control('pause'); assert stop() is True
        job.control('resume'); job.control('cancel'); assert stop() is True
    # A checkpoint takes the lock back in the state it reports.
    job = jobs.Job(request())
    assert worker(job, job.take_device, lambda: job.checkpoint(3, 'queued')) == [(True, 'queued', 3)] and len(attempts) == 8
    monkeypatch.setattr(lock, 'acquire', take)
    # A query does not wait for the device lock: views keep updating while another thread
    # holds it for a solve chunk or a recording.
    calls, took, stop = [], threading.Event(), threading.Event()
    def solving():
        lock.acquire(timeout=1); took.set(); stop.wait(5); lock.release()
    threading.Thread(target=solving, daemon=True).start(); took.wait(2)
    from hawa import fields
    monkeypatch.setattr(fields, 'dispatch_field', lambda *args: calls.append(lock.owner == threading.get_ident()) or {'ok': True})
    job = jobs.Job({'kind': 'query', 'request': {'op': 'field', 'action': 'plane'}})
    assert not run(job.work).is_alive()
    assert calls == [False] and job.state == 'completed' and job.result == {'ok': True} and not job.holds_device
    stop.set()
    end = time.monotonic()+2
    while lock.owner is not None and time.monotonic() < end: time.sleep(.005)
    assert lock.owner is None
    # Other operations can run solver work, such as evaluate, so they hold the lock.
    monkeypatch.setattr(plugin, 'dispatch', lambda req: calls.append((lock.owner == threading.get_ident(), probe())) or {'ok': True})
    job = jobs.Job({'kind': 'query', 'request': {'op': 'evaluate'}}); run(job.work)
    assert calls[1:] == [(True, [False])] and job.state == 'completed' and lock.owner is None and not job.holds_device
    job = jobs.Job(request()); job.take_device(); job.control('pause')
    paused = []
    def resume_free():
        paused.append((job.holds_device, probe())); job.control('resume')
    monkeypatch.setattr(job.condition, 'wait', resume_free)
    job.checkpoint(3)
    assert paused == [(False, [True])] and job.holds_device and lock.owner == threading.get_ident()
    job.control('cancel')
    with pytest.raises(jobs.Cancelled): job.checkpoint(4)
    assert not job.holds_device and lock.owner is None
    # Waiting for the lock stays cancellable, and a failed evaluation releases it.
    # The holder stays alive: a finished thread's identifier can be reused by the next one.
    took, stop = threading.Event(), threading.Event()
    def holder():
        lock.acquire(timeout=1); took.set(); stop.wait(5); lock.release()
    threading.Thread(target=holder, daemon=True).start(); took.wait(2)
    waiting = jobs.Job(request()); waiting.control('cancel'); raised = []
    def wait():
        try:
            waiting.take_device()
        except jobs.Cancelled:
            raised.append(waiting.holds_device)
    assert not run(wait).is_alive() and raised == [False]
    stop.set()
    end = time.monotonic()+2
    while lock.owner is not None and time.monotonic() < end: time.sleep(.005)
    def failed(*args, **kwargs):
        assert lock.owner == threading.get_ident()
        raise RuntimeError('diverged')
    monkeypatch.setattr(jobs, 'evaluate', failed)
    job = jobs.Job(request()); run(job.work)
    assert job.state == 'failed' and job.error == 'diverged' and lock.owner is None and not job.holds_device
    # Off a Mac, jobs take no lock.
    monkeypatch.setattr(jobs, 'SHARE_DEVICE_LOCK', False)
    job = jobs.Job(request()); job.take_device()
    assert not job.holds_device and lock.owner is None
