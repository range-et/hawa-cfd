"""Real CPU workflow controls, not wing accuracy or convergence benchmarks."""
from copy import deepcopy
import math
import threading
import time

import numpy as np
import pytest

from hawa.plugin import Session, SESSIONS, case_key, sample_arrays
from hawa.stationary_loads import StationaryLoads
from hawa.sweeps import SweepController, plot_segments


GENERATION = 29


def prepared_cube(candidate_id='rest-0', speed=.5, warning=False, transformed=False):
    """Interior equilibrium before the inlet disturbance reaches a distant cube.

    Four source steps test accepted completion at a fixed 0.01 stationarity
    criterion. This is deliberately a rest/control experiment, not a polar.
    """
    shape = [16, 12, 10]
    solid = [int(np.ravel_multi_index((i, j, k), shape))
             for i in (7, 8) for j in (5, 6) for k in (4, 5)]
    origin = [10., 20., 30.] if transformed else [0., 0., 0.]
    basis = [[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]] if transformed else np.eye(3).tolist()
    spec = dict(shape=shape, dx=.5, speed=speed, viscosity=.1, density=2.,
                collision='bgk', mach=.12 if warning else .01,
                boundaries=['inlet', 'outlet', 'slip', 'slip', 'slip', 'slip'],
                solid=solid, origin=origin, basis=basis, spacing=.5)
    if not warning:
        spec['initial_velocity'] = [0., 0., 0.]
    vertices = [[3.25,2.25,1.75], [4.25,2.25,1.75], [4.25,3.25,1.75], [3.25,3.25,1.75],
                [3.25,2.25,2.75], [4.25,2.25,2.75], [4.25,3.25,2.75], [3.25,3.25,2.75]]
    triangles = [[0,2,1], [0,3,2], [4,5,6], [4,6,7], [0,1,5], [0,5,4],
                 [1,2,6], [1,6,5], [2,3,7], [2,7,6], [3,0,4], [3,4,7]]
    geometry = dict(vertices_m=(np.asarray(origin) + np.asarray(vertices) @ np.asarray(basis)).tolist(),
                    triangles=triangles)
    candidate = dict(candidate_id=candidate_id, angle_deg=0., speed_m_s=speed,
                     geometry_hash=case_key(geometry), case_hash=case_key(spec))
    identity = dict(case_id='independent-cpu-control', revision=0, generation=GENERATION,
                    candidate_id=candidate_id, geometry_hash=candidate['geometry_hash'],
                    case_hash=candidate['case_hash'])
    dt = spec['mach'] * spec['dx'] / (math.sqrt(3.) * speed)
    request = dict(schema='hawa-measurement-1', identity=identity,
                   references=dict(density_kg_m3=2., speed_m_s=speed, area_m2=1., chord_m=1.,
                                   pressure_pa=0., drag_axis_world=basis[0], lift_axis_world=basis[2]),
                   bodies=[dict(body_id='cube', moment_origin_world_m=(np.asarray(origin) +
                               np.asarray([3.75,2.75,2.25]) @ np.asarray(basis)).tolist())],
                   window=dict(start_s=0., end_s=3*dt, minimum_samples=4,
                               stationarity_absolute_coefficient_tolerance=.01))
    lattice_points = [[1., 5., 4.], [7., 5., 4.], [3., 0., 4.]]
    probes = [dict(probe_id=ident, position_world_m=(np.asarray(origin) +
                   np.asarray(point)*spec['dx'] @ np.asarray(basis)).tolist())
              for ident, point in zip(('near-inlet', 'solid', 'boundary'), lattice_points)]
    return dict(candidate=candidate, spec=spec, body_indices=dict(cube=solid), request=request,
                probes=probes, origin_world_m=origin, basis=basis, steps=4,
                selected_body_id='cube', dtype='float32', geometry=geometry)


def drive(controller, predicate=None, timeout=15.):
    """Bounded test-driver polling on the test thread, never a host callback."""
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        controller.tick()
        if predicate is not None and predicate():
            return
        if predicate is None and controller.state in ('completed', 'cancelled', 'disposed'):
            return
        time.sleep(.001)
    pytest.fail('Real CPU sweep did not reach the expected state before test deadline')


def dispose(controller):
    controller.dispose()
    drive(controller)


def independent_pressure_replay(prepared):
    """Capture exact post-collision/pre-reflection state using a fresh CPU session."""
    session = Session(deepcopy(prepared['spec']), 'cpu')
    pressure = []
    origin = np.asarray(prepared['origin_world_m'])
    basis = np.asarray(prepared['basis'])
    points = [((np.asarray(p['position_world_m'])-origin) @ basis.T / prepared['spec']['dx']).tolist()
              for p in prepared['probes']]

    # Wrap __call__ via an actual BounceBack subclass so boundary_nodes retains
    # its ordinary type-based mask behavior (including invalid slip nodes).
    class CapturingBoundary(StationaryLoads):
        def __call__(self, flow):
            values = sample_arrays(session.fields(with_provenance=True), points)
            pressure.append((int(flow.i), float(flow.units.convert_time_to_pu(flow.i)), values))
            return super().__call__(flow)

    boundary = CapturingBoundary(session.flow, prepared['spec'], prepared['body_indices'],
                                  prepared['request']['bodies'], prepared['origin_world_m'], prepared['basis'])
    session.solver.post_boundaries[-1] = boundary
    session.advance(prepared['steps'])
    return pressure, boundary.history, session.flow.i


def test_real_cpu_candidates_use_fresh_sessions_and_repeatable_actual_identity():
    from hawa.sweep_executor import CpuSweepExecutor
    prepared = {e['candidate']['candidate_id']: e for e in
                (prepared_cube('speed-half', .5), prepared_cube('speed-one', 1.))}
    before = set(SESSIONS)
    executor = CpuSweepExecutor(prepared)
    controller = SweepController([e['candidate'] for e in prepared.values()], executor, GENERATION)
    try:
        controller.run()
        drive(controller)
        assert [r['state'] for r in controller.records] == ['completed', 'completed']
        details = [executor.results(key, GENERATION) for key in prepared]
        assert len({d['session'] for d in details}) == 2
        assert [d['identity']['case_hash'] for d in details] == [case_key(e['spec']) for e in prepared.values()]
        assert details[0]['identity']['case_hash'] != details[1]['identity']['case_hash']
        assert details[0]['identity']['geometry_hash'] == details[1]['identity']['geometry_hash']
        for detail, entry in zip(details, prepared.values()):
            assert detail['device'] == 'cpu' and detail['dtype'] == 'float32'
            assert detail['identity'] == entry['request']['identity']
            assert [row['step'] for row in detail['load_samples']] == [0, 1, 2, 3]
            assert all(row['quality'] == 'accepted' for row in detail['load_samples'])
            assert detail['summary']['bodies'][0]['stationarity']['passed']
            assert detail['last_field']['snapshot']['steps'] == 3
            assert detail['final_quality']['iteration'] == 4
        assert executor.audit() == dict(handles=0, live_workers=0, session_ids=[])
        assert set(SESSIONS) == before
        assert len(plot_segments(controller.records)[0]) == 2
        # Retained snapshots are detached, not shared with later callers.
        details[0]['probe_samples'][0]['pressure_pa'] = 999.
        assert executor.results('speed-half', GENERATION)['probe_samples'][0]['pressure_pa'] != 999.
        again = CpuSweepExecutor(prepared)
        repeat = SweepController([e['candidate'] for e in prepared.values()], again, GENERATION)
        try:
            repeat.run(); drive(repeat)
            for key in prepared:
                a = executor.results(key, GENERATION)
                b = again.results(key, GENERATION)
                assert a['session'] != b['session']
                assert a['load_samples'] == b['load_samples']
                assert [p['pressure_pa'] for p in a['probe_samples']] == [p['pressure_pa'] for p in b['probe_samples']]
        finally:
            dispose(repeat)
    finally:
        dispose(controller)


def test_real_warning_is_retained_and_splits_plot_without_fabricated_coefficients():
    from hawa.sweep_executor import CpuSweepExecutor
    entries = [prepared_cube('before'), prepared_cube('warning', warning=True), prepared_cube('after')]
    executor = CpuSweepExecutor({e['candidate']['candidate_id']: e for e in entries})
    controller = SweepController([e['candidate'] for e in entries], executor, GENERATION)
    try:
        controller.run(); drive(controller)
        assert [r['state'] for r in controller.records] == ['completed', 'rejected', 'completed']
        warning = executor.results('warning', GENERATION)
        assert warning['final_quality']['status'] in ('warning', 'rejected')
        assert warning['final_quality']['trigger'] is not None
        assert any(s['quality'] in ('warning', 'rejected') for s in warning['load_samples'])
        assert [len(segment) for segment in plot_segments(controller.records)] == [1, 1]
        assert 'warning' not in [p['candidate']['candidate_id'] for segment in plot_segments(controller.records) for p in segment]
        assert executor.audit()['handles'] == executor.audit()['live_workers'] == 0
    finally:
        dispose(controller)


def test_pressure_and_loads_share_actual_collision_phase_and_world_probe_mapping():
    from hawa.sweep_executor import CpuSweepExecutor, PHASE
    entry = prepared_cube(transformed=True)
    key = entry['candidate']['candidate_id']
    executor = CpuSweepExecutor({key: entry})
    controller = SweepController([entry['candidate']], executor, GENERATION)
    try:
        controller.run(); drive(controller)
        assert controller.records[0]['state'] == 'completed'
        detail = executor.results(key, GENERATION)
        reference, loads, final_step = independent_pressure_replay(entry)
        assert final_step == 4
        assert detail['phase'] == PHASE == 'after-collision-before-obstacle-reflection-and-stream'
        assert detail['last_field']['snapshot']['phase'] == PHASE
        for step, time_s, values in reference:
            actual = [p for p in detail['probe_samples'] if p['step'] == step]
            assert [p['probe_id'] for p in actual] == ['near-inlet', 'solid', 'boundary']
            for row, expected, descriptor in zip(actual, values, entry['probes']):
                assert row['time_s'] == pytest.approx(time_s, rel=1e-12, abs=1e-14)
                assert row['phase'] == PHASE and row['session'] == detail['session']
                assert row['position_world_m'] == descriptor['position_world_m']
                if expected is None:
                    assert row['valid'] is False and row['pressure_pa'] is None and row['Cp'] is None
                    assert row['reason']
                else:
                    assert row['valid'] is True and not row['reason']
                    assert row['pressure_pa'] == expected['pressure']
                    q = .5 * entry['spec']['density'] * entry['spec']['speed']**2
                    assert row['Cp'] == expected['pressure']/q
            actual_load = detail['load_samples'][step]
            assert actual_load['time_s'] == pytest.approx(time_s, rel=1e-12, abs=1e-14)
            np.testing.assert_array_equal(actual_load['force_world_n'], loads[step]['loads'][0]['force_world_n'])
        # Near-inlet pressure changes: this catches a fixed/final-field replay
        # incorrectly reused under every source timestamp.
        pressures = [p['pressure_pa'] for p in detail['probe_samples'] if p['probe_id'] == 'near-inlet']
        assert len(set(pressures)) > 1
    finally:
        dispose(controller)


@pytest.mark.parametrize('finish', ['resume', 'cancel', 'dispose'])
def test_real_worker_pause_and_cleanup_are_cooperative(monkeypatch, finish):
    from hawa.sweep_executor import CpuSweepExecutor
    entered, release = threading.Event(), threading.Event()
    observed = []
    original = Session.advance

    def gated_advance(session, steps):
        if not observed:
            observed.append(session)
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test failed to release real numerical step')
        return original(session, steps)

    def forbidden_pause(session):
        raise AssertionError('Executor must not call Session.pause and join a live worker')

    monkeypatch.setattr(Session, 'advance', gated_advance)
    monkeypatch.setattr(Session, 'pause', forbidden_pause)
    entry = prepared_cube()
    key = entry['candidate']['candidate_id']
    executor = CpuSweepExecutor({key: entry})
    handles = []
    original_start = executor.start
    def tracked_start(candidate, generation):
        handle = original_start(candidate, generation)
        handles.append(handle)
        return handle
    monkeypatch.setattr(executor, 'start', tracked_start)
    controller = SweepController([entry['candidate']], executor, GENERATION)
    try:
        controller.run(); controller.tick()
        assert entered.wait(5)
        controller.pause()
        release.set()
        drive(controller, lambda: controller.records[0]['state'] == 'paused')
        assert observed[0].flow.i == 1
        assert executor.audit()['handles'] == executor.audit()['live_workers'] == 1
        assert executor.audit()['session_ids'] == [observed[0].id]
        for _ in range(4):
            controller.tick()
        assert observed[0].flow.i == 1
        if finish == 'resume':
            controller.resume()
        elif finish == 'cancel':
            controller.cancel()
        else:
            controller.dispose()
        drive(controller, timeout=1.)
        assert executor.audit() == dict(handles=0, live_workers=0, session_ids=[])
        detail = executor.results(key, GENERATION)
        expected = 'completed' if finish == 'resume' else 'cancelled'
        assert controller.records[0]['state'] == expected
        assert detail['state'] == expected
        assert len(detail['load_samples']) == (4 if finish == 'resume' else 1)
    finally:
        release.set()
        # A broken close may undo cancellation while paused. Release the worker
        # through independent public controls before retrying controller disposal;
        # repeatedly calling the same broken close would hide failure in a timeout.
        if handles and executor.audit()['handles']:
            executor.resume(handles[0])
            executor.cancel(handles[0])
            deadline = time.monotonic() + 2.
            while executor.audit()['live_workers'] and time.monotonic() < deadline:
                time.sleep(.001)
            assert not executor.audit()['live_workers'], 'worker cleanup did not drain'
        dispose(controller)


def test_invalid_final_case_hash_rejects_before_creating_session(monkeypatch):
    from hawa.sweep_executor import CpuSweepExecutor
    entry = prepared_cube()
    entry['spec']['speed'] = 3.
    constructed = []

    def must_not_construct(*args, **kwargs):
        constructed.append(True)
        raise AssertionError('Invalid prepared identity allocated a solver')

    monkeypatch.setattr(Session, '__init__', must_not_construct)
    with pytest.raises(ValueError, match='identity'):
        CpuSweepExecutor({entry['candidate']['candidate_id']: entry})
    assert constructed == []


def test_blended_wing_recipe_runs_real_short_cases_without_claiming_settling():
    from hawa.sweep_executor import CpuSweepExecutor
    from scripts.wing_solver_recipe import prepare_sweep
    study = prepare_sweep(
        dict(root='2418', tip='0018', span_m=.3, root_chord_m=.2, tip_chord_m=.15,
             section_points=21, span_stations=3),
        [dict(angle_deg=-3., speed_m_s=1.), dict(angle_deg=3., speed_m_s=1.)],
        dict(shape=[25, 25, 17], dx=.025, origin_world_m=[-.2, -.3, -.2]),
        dict(density=1., viscosity=.01, mach=.03, pressure_pa=0.))
    entries = {}
    for key, raw in study['prepared'].items():
        spec = raw['case']
        dt = spec['mach']*spec['dx']/(math.sqrt(3.)*spec['speed'])
        candidate = raw['candidate']
        request = dict(schema='hawa-measurement-1',
                       identity=dict(case_id='short-blended-wing', revision=0, generation=GENERATION,
                                     candidate_id=key, case_hash=candidate['case_hash'],
                                     geometry_hash=candidate['geometry_hash']),
                       references=raw['references'], bodies=raw['bodies'],
                       window=dict(start_s=0., end_s=3*dt, minimum_samples=4,
                                   stationarity_absolute_coefficient_tolerance=.01))
        entries[key] = dict(candidate=candidate, spec=spec, body_indices=raw['body_indices'],
                            request=request, probes=[], origin_world_m=raw['origin_world_m'],
                            basis=raw['basis'], steps=4, selected_body_id='wing', dtype='float32',
                            geometry=raw['geometry'])
    assert len({e['candidate']['geometry_hash'] for e in entries.values()}) == 2
    assert len({e['candidate']['case_hash'] for e in entries.values()}) == 2
    executor = CpuSweepExecutor(entries)
    controller = SweepController(study['candidates'], executor, GENERATION)
    try:
        controller.run(); drive(controller)
        assert all(r['state'] == 'rejected' for r in controller.records)
        assert plot_segments(controller.records) == []
        for candidate in study['candidates']:
            detail = executor.results(candidate['candidate_id'], GENERATION)
            assert len(detail['load_samples']) == 4
            assert detail['summary']['bodies'][0]['stationarity']['passed'] is False
            assert detail['summary']['bodies'][0]['stationarity']['absolute_coefficient_change'] > .01
            assert detail['identity']['case_hash'] == candidate['case_hash']
            assert detail['last_field']['pressure'].shape == (25, 25, 17)
        assert executor.audit() == dict(handles=0, live_workers=0, session_ids=[])
    finally:
        dispose(controller)
