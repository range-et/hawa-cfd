import json
import time

import numpy as np
import pytest

from hawa.plugin import check_case, dispatch, dispatch_json, SESSIONS


@pytest.fixture
def session(solver_device):
    result = dispatch({"op": "create", "case": {"example": "tgv3d-bgk", "size": 12}, "device": solver_device})
    yield result["session"]
    dispatch({"op": "close", "session": result["session"]})


def test_background_lifecycle_and_resume(session):
    dispatch({"op": "start", "session": session, "steps": 500})
    dispatch({"op": "pause", "session": session})
    status = dispatch({"op": "status", "session": session})
    paused = status["steps"]
    assert status["state"] in ("paused", "completed")
    time.sleep(.02)
    assert dispatch({"op": "status", "session": session})["steps"] == paused
    target = paused + 10
    dispatch({"op": "start", "session": session, "steps": target})
    SESSIONS[session].thread.join(timeout=10)
    assert dispatch({"op": "status", "session": session})["steps"] == target
    dispatch({"op": "reset", "session": session})
    assert dispatch({"op": "status", "session": session})["steps"] == 0


def test_interpolation_slice_streamlines_and_checkpoint(session, tmp_path):
    dispatch({"op": "step", "session": session, "steps": 5})
    before = SESSIONS[session].flow.f.clone()
    saved = tmp_path / "restart.npz"
    dispatch({"op": "save", "session": session, "path": str(saved)})
    dispatch({"op": "step", "session": session, "steps": 5})
    dispatch({"op": "load", "session": session, "path": str(saved)})
    np.testing.assert_array_equal(SESSIONS[session].flow.f.cpu().numpy(), before.cpu().numpy())
    assert dispatch({"op": "status", "session": session})["steps"] == 5
    sampled = dispatch({"op": "sample", "session": session, "points": [[1.5, 2, 3], [-1, 0, 0]]})
    assert sampled["values"][0] is not None and sampled["values"][1] is None
    field = dispatch({"op": "slice", "session": session, "axis": 2, "index": 5})
    assert field["shape"] == [12, 12] and len(field["values"]) == 144
    lines = dispatch({"op": "streamlines", "session": session, "seeds": [[2, 2, 2]], "steps": 10})
    assert len(lines["paths"][0]) > 2
    assert len(lines["paths"][0]) <= 11


def test_physical_wind_boundaries_and_solid_device_parity():
    import torch
    devices = ["cpu"] + (["mps"] if torch.backends.mps.is_available() else [])
    states = []
    spec = {"shape": [12, 10, 8], "dx": .1, "speed": 1., "viscosity": .01,
            "solid": [(5 * 10 + 5) * 8 + 3], "collision": "regularized"}
    for device in devices:
        result = dispatch({"op": "create", "case": spec, "device": device})
        ident = result["session"]
        try:
            dispatch({"op": "step", "session": ident, "steps": 20})
            states.append(SESSIONS[ident].flow.f.detach().cpu().numpy().copy())
            assert dispatch({"op": "status", "session": ident})["steps"] == 20
        finally:
            dispatch({"op": "close", "session": ident})
    for state in states[1:]:
        np.testing.assert_allclose(state, states[0], rtol=3e-4, atol=2e-6)


@pytest.mark.parametrize("change", [{"dx": -1}, {"speed": float("nan")},
                                    {"boundaries": ["inlet", "outlet", "periodic", "wall", "wall", "slip"]},
                                    {"solid": [0]}, {"shape": [1000, 1000, 1000]}])
def test_preflight_rejects_invalid_cases(change):
    spec = {"shape": [12, 10, 8], "dx": .1, "speed": 1., "viscosity": .01}
    spec.update(change)
    with pytest.raises(ValueError):
        check_case(spec)


def test_json_boundary_reports_errors_without_invalid_json():
    result = json.loads(dispatch_json('{"op":"status","session":"missing"}'))
    assert not result["ok"] and result["type"] == "KeyError"


@pytest.mark.parametrize('iteration,density', [(-1,1), (1.5,1), (2,-1)])
def test_checkpoint_rejects_invalid_state_atomically(session,tmp_path,iteration,density):
    from hawa.plugin import canonical
    s=SESSIONS[session]
    before=s.flow.f.cpu().numpy().copy()
    path=tmp_path/'bad.npz'
    np.savez_compressed(path,populations=before*density,iteration=np.array(iteration),spec=np.array(canonical(s.spec)))
    with pytest.raises(ValueError,match='Checkpoint'):
        dispatch({'op':'load','session':session,'path':str(path)})
    np.testing.assert_array_equal(before,s.flow.f.cpu().numpy())
    assert s.flow.i==0


@pytest.mark.parametrize('size',[0,-1,True,16.5,10000])
def test_example_preflight_checks_size(size):
    with pytest.raises(ValueError,match='size'):check_case({'example':'tgv3d-bgk','size':size})


def test_example_preflight_checks_memory():
    with pytest.raises(ValueError,match='memory'):check_case({'example':'tgv3d-bgk','size':128})


def test_slice_provenance_tracks_captured_fields_not_later_solver_state(session, monkeypatch):
    solver = SESSIONS[session]
    dispatch({'op': 'step', 'session': session, 'steps': 5})
    capture = solver.fields

    def fields_then_advance(mean=False, with_provenance=False):
        fields = capture(mean, with_provenance=with_provenance)
        solver.advance(3)
        return fields

    monkeypatch.setattr(solver, 'fields', fields_then_advance)
    result = dispatch({'op': 'slice', 'session': session, 'field': 'pressure'})
    assert solver.flow.i == 8
    assert result['steps'] == 5
    assert result['session'] == session
    assert result['physical_time'] == pytest.approx(solver.flow.units.convert_time_to_pu(5))
    assert result['field'] == 'pressure'


def test_default_fields_remain_array_only_for_recording_and_exports(session):
    assert all(isinstance(value, np.ndarray) for value in SESSIONS[session].fields().values())


def test_async_close_of_missing_session_is_idempotent():
    assert dispatch({'op': 'close_async', 'session': 'already-closed'}) == {'closed': True}


def test_wall_and_slip_face_nodes_are_exported_as_not_simulated():
    # Default faces: z=0 wall (full-way bounce-back), z=-1 slip; neither holds flow data.
    spec = {"shape": [12, 10, 8], "dx": .1, "speed": 1., "viscosity": .01, "solid": [(5 * 10 + 5) * 8 + 3]}
    ident = dispatch({"op": "create", "case": spec, "device": "cpu"})["session"]
    try:
        dispatch({"op": "step", "session": ident, "steps": 20})
        fields = SESSIONS[ident].fields()
        nodes = fields["boundary_nodes"]
        assert nodes[:, :, 0].all() and nodes[:, :, -1].all() and nodes.sum() == 2 * 12 * 10
        assert not fields["solid"][:, :, 0].any() and fields["solid"].sum() == 1  # obstacle mask unchanged
        floor = dispatch({"op": "slice", "session": ident, "axis": 2, "index": 0})
        assert not any(floor["valid"])
        rows = dispatch({"op": "sample", "session": ident, "points": [[6, 4, .4], [6, 4, .6], [6, 4, 1]]})["values"]
        assert rows[0] is None and rows[1]["velocity"] == pytest.approx(rows[2]["velocity"])
    finally:
        dispatch({"op": "close", "session": ident})


def test_examples_export_their_bounce_back_walls():
    from hawa.plugin import Session
    nodes = Session({"example": "poiseuille2d-guo", "size": 16}, "cpu").fields()["boundary_nodes"]
    assert nodes[:, [0, -1]].all() and not nodes[:, 1:-1].any()
    assert Session({"example": "tgv2d-bgk", "size": 8}, "cpu").fields().get("boundary_nodes") is None


def mps_labelled(monkeypatch):
    # Real CPU solvers whose backend reports MPS, so the lock rule can run off a Mac.
    import torch
    from hawa import plugin
    from hawa.backends import Backend
    build = plugin.make_solver
    def make(spec, device):
        backend, flow, solver = build(spec, 'cpu')
        if device != 'mps':
            return backend, flow, solver
        labelled = Backend(torch.device('mps'), 'mps')
        monkeypatch.setattr(labelled, 'synchronize', lambda: None)
        return labelled, flow, solver
    monkeypatch.setattr(plugin, 'make_solver', make)
    return plugin


def test_metal_sessions_share_one_device_lock_and_serialise_device_work(monkeypatch):
    import threading
    plugin = mps_labelled(monkeypatch)
    case = {"example": "tgv3d-bgk", "size": 8}
    a, b = plugin.Session(case, 'mps'), plugin.Session(case, 'mps')
    c, d = plugin.Session(case, 'cpu'), plugin.Session(case, 'cpu')
    assert a.lock is b.lock is plugin.MPS_LOCK
    assert c.lock is not d.lock and plugin.MPS_LOCK not in (c.lock, d.lock)
    held, release = threading.Event(), threading.Event()
    def hold():
        with plugin.MPS_LOCK:
            held.set(); release.wait(10)
    holder = threading.Thread(target=hold); holder.start(); held.wait(10)
    built = []
    workers = [threading.Thread(target=lambda: b.advance(5)), threading.Thread(target=lambda: built.append(plugin.Session(case, 'mps')))]
    for w in workers: w.start()
    # Another thread's MPS work blocks both stepping and construction; a CPU session does not wait.
    c.advance(5)
    time.sleep(.3)
    assert b.flow.i == 0 and not built and c.flow.i == 5
    release.set(); holder.join(10)
    for w in workers: w.join(30)
    assert b.flow.i == 5 and len(built) == 1 and built[0].lock is plugin.MPS_LOCK
    # Field reads of another MPS session wait for the lock as well.
    with plugin.MPS_LOCK:
        reader = threading.Thread(target=lambda: built.append(a.fields())); reader.start(); time.sleep(.2)
        assert len(built) == 1
    reader.join(10)
    assert len(built) == 2 and built[1]['velocity'].shape[0] == 3


def test_advance_releases_the_device_lock_between_chunks(monkeypatch):
    import threading
    plugin = mps_labelled(monkeypatch)
    a = plugin.Session({"example": "tgv3d-bgk", "size": 8}, 'mps')
    first, got = threading.Event(), []
    def synchronize():
        # Hold the first chunk until the other thread has queued for the lock.
        if not first.is_set():
            first.set(); end = time.monotonic()+5
            while not plugin.MPS_LOCK.queue and time.monotonic() < end: time.sleep(.005)
    monkeypatch.setattr(a.backend, 'synchronize', synchronize)
    def other():
        first.wait(5)
        if plugin.MPS_LOCK.acquire(timeout=5):
            got.append(a.flow.i); plugin.MPS_LOCK.release()
    waiter = threading.Thread(target=other, daemon=True); waiter.start()
    a.advance(15); waiter.join(5)
    # The queued thread gets the lock at the first chunk boundary, not after all 15 steps.
    assert a.flow.i == 15 and got == [5]


def test_pause_from_a_thread_holding_the_device_lock_lets_the_worker_stop(monkeypatch):
    import threading
    plugin = mps_labelled(monkeypatch)
    a = plugin.Session({"example": "tgv3d-bgk", "size": 8}, 'mps')
    a.start(10**6)
    end = time.monotonic()+5
    while a.flow.i == 0 and time.monotonic() < end: time.sleep(.005)
    out = []
    def job():
        # A query job holds the lock while it pauses the session (save/load).
        plugin.MPS_LOCK.acquire(timeout=5)
        try:
            a.pause(); out.append((a.state, plugin.MPS_LOCK.owner == threading.get_ident(), plugin.MPS_LOCK.depth))
        except RuntimeError as exc:
            out.append(str(exc))
        finally:
            plugin.MPS_LOCK.release()
    worker = threading.Thread(target=job, daemon=True); worker.start(); worker.join(5)
    assert out == [('paused', True, 1)] and a.thread is None


def test_refined_run_waits_on_pause_outside_the_device_lock(monkeypatch):
    import threading
    from hawa import refinement
    plugin = mps_labelled(monkeypatch)
    sessions = []
    class Recorded(plugin.Session):
        def __init__(self, spec, device):
            super().__init__(spec, device); sessions.append(self)
    monkeypatch.setattr(plugin, 'Session', Recorded)
    coarse = dict(shape=[17]*3, dx=1., spacing=1., origin=[0,0,0], speed=1., viscosity=1., density=1.225, mach=.05, collision='bgk', solid=[], boundaries=['inlet','outlet','periodic','periodic','periodic','periodic'])
    fine = {**coarse, 'shape': [13]*3, 'dx': .5, 'spacing': .5, 'origin': [5,5,5], 'refinement_lower': [5]*3, 'refinement_upper': [11]*3}
    free, seen = [], []
    def checkpoint(n):
        seen.append(n)
        # A paused job waits here: the lock must be free for other MPS work.
        probe = threading.Thread(target=lambda: free.append(plugin.MPS_LOCK.acquire(timeout=0) and (plugin.MPS_LOCK.release() or True)))
        probe.start(); probe.join(5)
    r = refinement.run_refined(dict(case=coarse, fine_case=fine, steps=7, device='mps'), checkpoint)
    assert sessions[0].lock is plugin.MPS_LOCK and r['steps'] == 7 and sessions[0].flow.i == 7
    # Before construction, then before each 5-step chunk, then once complete.
    assert free == [True, True, True, True] and seen == [0, 0, 5, 7]
    assert r['backend'] == sessions[0].backend.info() and abs(r['relative_mass_change']) < 1e-3


def test_device_lock_is_reentrant_fair_and_owned():
    import threading
    from hawa.plugin import DeviceLock
    lock = DeviceLock()
    # Every wait here is bounded, so a broken lock fails the test instead of hanging it.
    def run(target):
        thread = threading.Thread(target=target, daemon=True); thread.start(); return thread
    def settle(done):
        end = time.monotonic()+2
        while not done():
            assert time.monotonic() < end, 'lock did not reach the expected state'
            time.sleep(.005)
    assert lock.acquire(timeout=1) is True and lock.acquire(timeout=1) is True and lock.depth == 2
    # Another thread neither takes nor releases a lock it does not hold.
    out = []
    def other():
        out.append(lock.acquire(timeout=0))
        try:
            lock.release()
        except RuntimeError as exc:
            out.append(str(exc))
    run(other).join(2)
    assert out == [False, 'Device lock released by a thread that does not hold it'] and lock.queue == []
    lock.release(); lock.release()
    assert lock.owner is None and lock.depth == 0
    freed = []
    run(lambda: freed.append(lock.acquire(timeout=1) and lock.release() is None)).join(2)
    assert freed == [True]
    with lock:
        with lock:
            assert lock.depth == 2
    order = []
    assert lock.acquire(timeout=1)
    def wait(name):
        if lock.acquire(timeout=2):
            order.append(name); lock.release()
    first = run(lambda: wait('first')); settle(lambda: len(lock.queue) == 1)
    second = run(lambda: wait('second')); settle(lambda: len(lock.queue) == 2)
    lock.release()
    # The releasing thread queues behind earlier waiters instead of retaking the lock.
    if lock.acquire(timeout=2):
        order.append('main'); lock.release()
    first.join(2); second.join(2)
    assert order == ['first', 'second', 'main'] and lock.owner is None and lock.depth == 0
    # A thread can give up every hold while it waits, then get them back.
    assert lock.acquire(timeout=1) and lock.acquire(timeout=1)
    taken = []
    assert lock.suspend() == 2 and lock.owner is None and lock.depth == 0
    run(lambda: taken.append(lock.acquire(timeout=1) and lock.release() is None)).join(2)
    lock.restore(2)
    assert taken == [True] and lock.owner == threading.get_ident() and lock.depth == 2
    lock.release(); lock.release(); lock.restore(0)
    suspended = []
    run(lambda: suspended.append(lock.suspend())).join(2)
    assert suspended == [0] and lock.owner is None and lock.depth == 0
    # An interrupted wait leaves the queue, so later callers are not blocked behind it.
    assert lock.acquire(timeout=1)
    def interrupted(*args):
        raise KeyboardInterrupt
    raised = []
    def interrupt():
        lock.condition.wait_for = interrupted
        try:
            lock.acquire(timeout=1)
        except KeyboardInterrupt:
            raised.append(list(lock.queue))
    run(interrupt).join(2)
    del lock.condition.wait_for
    lock.release()
    late = []
    run(lambda: late.append(lock.acquire(timeout=1) and lock.release() is None)).join(2)
    assert raised == [[]] and late == [True]


def test_device_lock_waiter_with_a_stop_check_keeps_its_place():
    # Kept apart from the fast lock test so a broken lock fails that one first.
    import threading
    from hawa.plugin import DeviceLock
    lock = DeviceLock()
    def run(target):
        thread = threading.Thread(target=target, daemon=True); thread.start(); return thread
    def settle(done):
        end = time.monotonic()+2
        while not done():
            assert time.monotonic() < end, 'lock did not reach the expected state'
            time.sleep(.005)
    def wait(name):
        if lock.acquire(timeout=2):
            order.append(name); lock.release()
    # A waiter that polls a stop request keeps its place ahead of later waiters, and gives it
    # up once stop() is true, even without a notify.
    assert lock.acquire(timeout=1)
    order, flag = [], []
    def polled(name, stop):
        if lock.acquire(stop=stop):
            order.append(name); lock.release()
        else:
            order.append(name+' stopped')
    first = run(lambda: polled('polled', lambda: False)); settle(lambda: len(lock.queue) == 1)
    second = run(lambda: wait('later')); settle(lambda: len(lock.queue) == 2)
    lock.release(); first.join(2); second.join(2)
    assert order == ['polled', 'later'] and lock.queue == []
    assert lock.acquire(timeout=1)
    stopper = run(lambda: polled('cancelled', lambda: bool(flag))); settle(lambda: len(lock.queue) == 1)
    flag.append(True); stopper.join(2)
    assert order[-1] == 'cancelled stopped' and lock.queue == [] and lock.owner == threading.get_ident()
    lock.release()


def test_async_close_reply_survives_immediate_cleanup(monkeypatch):
    from hawa import plugin

    session = plugin.Session(dict(example="tgv3d-bgk", size=8), "cpu")
    plugin.SESSIONS[session.id] = session

    class ImmediateThread:
        def __init__(self, target, **kwargs):
            self.target = target
        def start(self):
            self.target()

    monkeypatch.setattr(plugin.threading, "Thread", ImmediateThread)
    reply = plugin.dispatch({"op": "close_async", "session": session.id})
    assert reply["session"] == session.id and reply["steps"] == 0
    assert reply["state"] == "paused"
    assert session.flow is None and session.id not in plugin.SESSIONS


def test_overlapping_close_requests_share_one_cleanup_and_survive_release_failure(monkeypatch):
    from hawa import plugin
    session = plugin.Session(dict(example='tgv3d-bgk', size=8), 'cpu')
    plugin.SESSIONS[session.id] = session
    pending = []
    class QueuedThread:
        def __init__(self, target, **kwargs): self.target = target
        def start(self): pending.append(self.target)
    monkeypatch.setattr(plugin.threading, 'Thread', QueuedThread)
    first = plugin.dispatch(dict(op='close_async', session=session.id))
    assert plugin.dispatch(dict(op='close_async', session=session.id)) == first
    assert plugin.dispatch(dict(op='pause_async', session=session.id)) == first
    assert len(pending) == 1
    with pytest.raises(ValueError, match='closing or closed'):
        session.start(10)
    original_gc = plugin.gc.collect
    def fail_release(): raise RuntimeError('cache cleanup failed')
    monkeypatch.setattr(plugin.gc, 'collect', fail_release)
    pending.pop()()
    assert plugin.SESSIONS[session.id] is session
    assert session.flow is None and not session.close_pending
    with pytest.raises(ValueError, match='closing or closed'):
        session.start(10)
    status = session.status()
    assert status['state'] == 'failed' and status['error'] == 'cache cleanup failed'
    assert status['steps'] == first['steps'] and status['case_hash'] == first['case_hash']
    monkeypatch.setattr(plugin.gc, 'collect', original_gc)
    plugin.dispatch(dict(op='close_async', session=session.id))
    assert len(pending) == 1
    pending.pop()()
    assert session.id not in plugin.SESSIONS
    assert plugin.dispatch(dict(op='close', session=session.id)) == {'closed': True}


def test_failed_cleanup_thread_start_allows_retry(monkeypatch):
    from hawa import plugin
    session = plugin.Session(dict(example='tgv3d-bgk', size=8), 'cpu')
    plugin.SESSIONS[session.id] = session
    class FailingThread:
        def __init__(self, target, **kwargs): pass
        def start(self): raise RuntimeError('thread creation failed')
    monkeypatch.setattr(plugin.threading, 'Thread', FailingThread)
    with pytest.raises(RuntimeError, match='thread creation failed'):
        plugin.dispatch(dict(op='close_async', session=session.id))
    assert not session.close_pending and plugin.SESSIONS[session.id] is session
    plugin.dispatch(dict(op='close', session=session.id))


def test_duplicate_close_and_status_do_not_wait_for_memory_cleanup(monkeypatch):
    import threading
    from hawa import plugin
    session = plugin.Session(dict(example='tgv3d-bgk', size=8), 'cpu')
    plugin.SESSIONS[session.id] = session
    entered, resume, replied = threading.Event(), threading.Event(), threading.Event()
    workers, replies = [], []
    real_thread = threading.Thread
    def thread_factory(*args, **kwargs):
        worker = real_thread(*args, **kwargs)
        workers.append(worker)
        return worker
    def collect():
        entered.set()
        assert resume.wait(5), 'test did not release cleanup'
    monkeypatch.setattr(plugin.threading, 'Thread', thread_factory)
    monkeypatch.setattr(plugin.gc, 'collect', collect)
    plugin.dispatch(dict(op='close_async', session=session.id))
    def duplicate():
        replies.append(plugin.dispatch(dict(op='close_async', session=session.id)))
        replied.set()
    caller = real_thread(target=duplicate)
    try:
        assert entered.wait(5)
        caller.start()
        assert replied.wait(2), 'duplicate close waited for memory cleanup'
        assert replies[0]['steps'] == 0 and session.status()['steps'] == 0
        assert len(workers) == 1 and session.flow is None
    finally:
        resume.set()
        if caller.ident is not None: caller.join(5)
        for worker in workers: worker.join(5)
    assert not any(worker.is_alive() for worker in workers)
    assert session.id not in plugin.SESSIONS


@pytest.mark.parametrize('failure', [None, 'sync', 'empty'])
def test_release_clears_tensor_roots_and_retries_device_cache_failure(monkeypatch, failure):
    import torch
    from hawa import plugin
    session = plugin.Session(dict(example='tgv3d-bgk', size=8), 'cpu')
    session.advance(5)
    session.initial_wall_velocity = torch.ones(3)
    plugin.SESSIONS[session.id] = session
    calls = []
    failed = False
    original_gc = plugin.gc.collect
    class FakeDevice:
        type = 'mps'
    def collect():
        calls.append('gc')
        return original_gc()
    def cache_call(name):
        nonlocal failed
        calls.append(name)
        if failure == name and not failed:
            failed = True
            raise RuntimeError('device cleanup failed at '+name)
    monkeypatch.setattr(session.backend, 'device', FakeDevice())
    monkeypatch.setattr(torch.backends.mps, 'is_available', lambda: True)
    monkeypatch.setattr(plugin.gc, 'collect', collect)
    monkeypatch.setattr(torch.mps, 'synchronize', lambda: cache_call('sync'))
    monkeypatch.setattr(torch.mps, 'empty_cache', lambda: cache_call('empty'))
    if failure is not None:
        with pytest.raises(RuntimeError, match='device cleanup failed at '+failure):
            plugin.dispatch(dict(op='close', session=session.id))
        assert plugin.SESSIONS[session.id] is session
        assert not session.close_pending and session.release_requested
        assert calls == (['gc', 'sync'] if failure == 'sync' else ['gc', 'sync', 'empty'])
        calls.clear()
    assert plugin.dispatch(dict(op='close', session=session.id)) == {'closed': True}
    assert session.id not in plugin.SESSIONS and calls == ['gc', 'sync', 'empty']
    for name in ('flow', 'solver', 'initial_f', 'initial_wall_velocity', 'mean_u', 'mean_p', 'mean_rho'):
        assert getattr(session, name) is None
    assert session.status()['steps'] == 5
    assert session.status()['resolution'] == [8, 8, 8]


@pytest.mark.parametrize('device,available', [('cpu', True), ('mps', False)], ids=['host-backend', 'unavailable-backend'])
def test_release_flush_requires_both_cache_session_and_available_backend(monkeypatch, device, available):
    import torch
    from hawa import plugin
    session = plugin.Session(dict(example='tgv3d-bgk', size=8), 'cpu')
    monkeypatch.setattr(session.backend, 'device', torch.device(device))
    monkeypatch.setattr(torch.backends.mps, 'is_available', lambda: available)
    def forbidden():
        pytest.fail('MPS cache operation without an available MPS session')
    monkeypatch.setattr(torch.mps, 'synchronize', forbidden)
    monkeypatch.setattr(torch.mps, 'empty_cache', forbidden)
    session.release()
    assert session.flow is None
    assert session.status()['resolution'] == [8, 8, 8]


def test_start_checks_boundary_time_before_worker_creation_at_tolerance(monkeypatch):
    from hawa import plugin
    session = plugin.Session(dict(example='tgv3d-bgk', size=8), 'cpu')
    session.spec['boundary_field'] = {'end_time': 10. - 1e-10}
    monkeypatch.setattr(session.flow.units, 'convert_time_to_pu', lambda target: float(target))
    queued = []
    class QueuedThread:
        def __init__(self, target, **kwargs): self.target = target
        def start(self): queued.append(self.target)
        def is_alive(self): return False
    monkeypatch.setattr(plugin.threading, 'Thread', QueuedThread)
    with pytest.raises(ValueError, match='Target exceeds boundary time coverage'):
        session.start(11)
    assert queued == [] and session.state == 'ready' and session.target == 0
    session.start(10)
    assert len(queued) == 1 and session.state == 'running' and session.target == 10
    session.release()



def test_async_pause_and_reset_preserve_transition_and_worker_contract(monkeypatch):
    from hawa import plugin
    session = plugin.Session(dict(example='tgv3d-bgk', size=8), 'cpu')
    session.advance(2)
    plugin.SESSIONS[session.id] = session
    queued = []
    class QueuedThread:
        def __init__(self, target, **kwargs):
            assert kwargs.get('daemon') is True
            self.target = target
        def start(self): queued.append(self.target)
    class ActiveWorker:
        def is_alive(self): return True
    monkeypatch.setattr(plugin.threading, 'Thread', QueuedThread)
    session.thread = ActiveWorker()
    paused = plugin.dispatch(dict(op='pause_async', session=session.id))
    assert paused['state'] == 'pausing' and session.stop.is_set() and queued == []
    session.thread = None
    resetting = plugin.dispatch(dict(op='reset_async', session=session.id))
    assert resetting['state'] == 'resetting' and len(queued) == 1
    with pytest.raises(ValueError, match='Wait for reset'):
        session.start(5)
    queued.pop()()
    assert session.state == 'ready' and session.flow.i == 0 and session.error is None
    plugin.dispatch(dict(op='close', session=session.id))


def test_overlapping_synchronous_closes_remove_registry_idempotently(monkeypatch):
    from hawa import plugin
    session = plugin.Session(dict(example='tgv3d-bgk', size=8), 'cpu')
    plugin.SESSIONS[session.id] = session
    original_pause = session.pause
    nested = []
    def pause():
        if not nested:
            nested.append(True)
            assert plugin.dispatch(dict(op='close', session=session.id)) == {'closed': True}
        original_pause()
    monkeypatch.setattr(session, 'pause', pause)
    assert plugin.dispatch(dict(op='close', session=session.id)) == {'closed': True}
    assert nested == [True] and session.id not in plugin.SESSIONS
    assert session.status()['resolution'] == [8, 8, 8]


def test_query_close_and_async_cleanup_use_consistent_device_lock_order(monkeypatch):
    import threading
    import torch
    from hawa import jobs, plugin

    session = plugin.Session(dict(example='tgv3d-bgk', size=8), 'cpu')
    plugin.SESSIONS[session.id] = session
    query_holds_device, cleanup_waits_device = threading.Event(), threading.Event()
    workers = []
    real_thread = threading.Thread

    class ObservedDeviceLock(plugin.DeviceLock):
        def acquire(self, *args, **kwargs):
            if threading.current_thread() is not query.thread:
                cleanup_waits_device.set()
            return super().acquire(*args, **kwargs)

    class BoundedReleaseLock:
        # A broken lock order fails the query instead of stranding test threads.
        def __init__(self): self.lock = threading.Lock()
        def __enter__(self):
            assert self.lock.acquire(timeout=2), 'cleanup/device lock inversion'
        def __exit__(self, *args): self.lock.release()

    def thread_factory(*args, **kwargs):
        worker = real_thread(*args, **kwargs)
        workers.append(worker)
        return worker

    device_lock = ObservedDeviceLock()
    monkeypatch.setattr(plugin, 'MPS_LOCK', device_lock)
    monkeypatch.setattr(jobs, 'MPS_LOCK', device_lock)
    monkeypatch.setattr(jobs, 'SHARE_DEVICE_LOCK', True)
    monkeypatch.setattr(session, 'release_lock', BoundedReleaseLock())
    monkeypatch.setattr(session.backend, 'device', torch.device('mps'))
    monkeypatch.setattr(torch.backends.mps, 'is_available', lambda: True)
    monkeypatch.setattr(torch.mps, 'synchronize', lambda: None)
    monkeypatch.setattr(torch.mps, 'empty_cache', lambda: None)
    monkeypatch.setattr(plugin.threading, 'Thread', thread_factory)
    query = jobs.Job(dict(kind='query', request=dict(op='close', session=session.id)))
    take_device = query.take_device
    def take_then_wait(*args, **kwargs):
        take_device(*args, **kwargs)
        query_holds_device.set()
        assert cleanup_waits_device.wait(5), 'async cleanup did not attempt device lock'
    monkeypatch.setattr(query, 'take_device', take_then_wait)
    try:
        query.thread.start()
        assert query_holds_device.wait(5)
        reply = plugin.dispatch(dict(op='close_async', session=session.id))
        assert reply['session'] == session.id
        assert cleanup_waits_device.wait(5)
        query.thread.join(7)
    finally:
        cleanup_waits_device.set()
        for worker in workers:
            if worker.ident is not None: worker.join(7)
        plugin.SESSIONS.pop(session.id, None)
    assert not any(worker.is_alive() for worker in workers)
    assert query.state == 'completed', query.error
    assert query.result == {'closed': True}
    assert session.flow is None and device_lock.owner is None


@pytest.mark.parametrize("shared", [False, True], ids=["separate-session-lock", "shared-device-lock"])
def test_async_release_waits_for_complete_cpu_capture(monkeypatch, shared):
    import threading
    from hawa import fields, plugin

    session = plugin.Session(dict(example='tgv3d-bgk', size=8), 'cpu')
    session.advance(5)
    plugin.SESSIONS[session.id] = session
    flow = session.flow
    captured, finish_capture, cleanup_checkpoint = (threading.Event() for _ in range(3))
    frames, failures, cleanup_workers = [], [], []
    original_fields, collect = session.fields, plugin.gc.collect
    real_thread = threading.Thread

    class CaptureLock:
        def __init__(self): self.lock = plugin.DeviceLock() if shared else threading.RLock()
        def __enter__(self):
            if threading.current_thread() is not capture_worker:
                # Signal before blocking: cleanup must wait for the entire frame.
                cleanup_checkpoint.set()
            assert self.lock.acquire(timeout=5), 'capture lock did not drain'
        def __exit__(self, *args): self.lock.release()

    def blocked_fields(*args, **kwargs):
        arrays = original_fields(*args, **kwargs)
        captured.set()
        assert finish_capture.wait(5), 'capture was not resumed'
        return arrays

    def capture():
        try: frames.append(fields.capture(session))
        except Exception as exc: failures.append(exc)

    def collecting():
        # Pre-fix cleanup bypasses the capture lock and reaches collection early.
        cleanup_checkpoint.set()
        return collect()

    def thread_factory(*args, **kwargs):
        worker = real_thread(*args, **kwargs)
        cleanup_workers.append(worker)
        return worker

    capture_worker = real_thread(target=capture, daemon=True)
    capture_lock = CaptureLock()
    monkeypatch.setattr(session, 'lock', capture_lock)
    if shared: monkeypatch.setattr(plugin, 'MPS_LOCK', capture_lock)
    monkeypatch.setattr(session, 'fields', blocked_fields)
    monkeypatch.setattr(plugin.gc, 'collect', collecting)
    monkeypatch.setattr(plugin.threading, 'Thread', thread_factory)
    intact = False
    try:
        capture_worker.start()
        assert captured.wait(5)
        reply = plugin.dispatch(dict(op='close_async', session=session.id))
        assert reply['session'] == session.id and reply['steps'] == 5
        assert cleanup_checkpoint.wait(5)
        intact = session.flow is flow and session.solver is not None
        # Polling stays independent of a close waiting for capture ownership.
        assert plugin.dispatch(dict(op='status', session=session.id))['steps'] == 5
    finally:
        finish_capture.set()
        capture_worker.join(7)
        for worker in cleanup_workers: worker.join(7)
        plugin.SESSIONS.pop(session.id, None)
        for frame in frames: fields.FRAMES.pop(frame['frame'], None)
    assert not capture_worker.is_alive() and not any(t.is_alive() for t in cleanup_workers)
    assert intact, 'cleanup cleared tensors while the capture lock was held'
    assert not failures and len(frames) == 1
    assert frames[0]['iteration'] == 5 and frames[0]['time'] == flow.units.convert_time_to_pu(5)
    assert session.flow is session.solver is None
