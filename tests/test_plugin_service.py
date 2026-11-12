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
