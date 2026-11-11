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


@pytest.mark.parametrize('route', ['field', 'statistics', 'boundary', 'recording', 'info'])
def test_query_routes_arguments_and_copies_result(isolated_jobs, monkeypatch, route):
    from hawa import fields, flow_statistics, boundary_data, recording
    calls = []
    def called(*args):
        calls.append(args); return {'route': route}
    monkeypatch.setattr(fields, 'dispatch_field', called)
    monkeypatch.setattr(flow_statistics, 'analyze', called)
    monkeypatch.setattr(boundary_data, 'capture', called)
    monkeypatch.setattr(recording, 'pathlines', called)
    monkeypatch.setattr(plugin, 'dispatch', called)
    req = dict(op=route, action={'boundary':'capture', 'recording':'particles'}.get(route, 'sample'),
               manifest='parent.json', points=[[1, 2, 3]], seeds=[[4, 5, 6]], case={'shape':[8, 8, 8]},
               path='mapped.npz', start_time=2., end_time=4., last=6)
    job = jobs.Job(dict(kind='query', request=req)); job.work()
    assert job.state == 'completed' and job.result == {'route': route} and job.session is None
    args = calls[0]
    if route == 'field': assert args[0] == req and args[1] is None and args[2] == job.checkpoint
    elif route == 'statistics': assert args == ('parent.json', [[1, 2, 3]], 2., 4., job.checkpoint)
    elif route == 'boundary': assert args == ('parent.json', {'shape':[8, 8, 8]}, 'mapped.npz', job.checkpoint, 2., 4.)
    elif route == 'recording': assert args == ('parent.json', [[4, 5, 6]], 6, job.checkpoint)
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
