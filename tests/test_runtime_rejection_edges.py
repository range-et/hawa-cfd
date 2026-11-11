"""Runtime admission failures paired with valid controls; all checks use CPU."""
import copy
import threading

import numpy as np
import pytest

from hawa import atmosphere, boundaries, jobs, neutral
from hawa.collision import SmagorinskyV1
from hawa.engine import LettuceSimulation
from test_general_boundaries import channel
from test_neutral import case as neutral_case


@pytest.mark.parametrize('key,value,message', [
    ('collision', 'bgk', 'requires shifted'),
    ('boundaries', ['periodic']*6, 'topology'),
    ('roughness_length_m', .5, 'Require z0'),
    ('reference_height_m', 12., 'Require z0'),
    ('direction', [1., 0., .01], 'horizontal unit'),
    ('direction', [2., 0., 0.], 'horizontal unit'),
    ('smagorinsky_constant', .301, 'Cs'),
    ('perturbation_fraction', .101, 'perturbation'),
    ('wall_sample_index', True, 'interior Z'),
    ('wall_sample_index', 11, 'interior Z'),
    ('wall_filter_seconds', -1., 'nonnegative'),
    ('wall_filter_seconds', float('nan'), 'nonnegative'),
    ('mach', .15, 'Mach 0.10'),
])
def test_neutral_rejects_invalid_physical_contract(key, value, message):
    spec = neutral_case()
    assert neutral.validate(spec)['storage'] == 'g=f-w'
    target = spec if key in ('collision', 'boundaries', 'mach') else spec['neutral_precursor']
    target[key] = value
    with pytest.raises(ValueError, match=message): neutral.validate(spec)


@pytest.mark.parametrize('velocity', [[1., 0.], [1., float('nan'), 0.]])
def test_profile_and_wall_reject_invalid_vectors(velocity):
    with pytest.raises(ValueError, match='three finite'):
        atmosphere.neutral_profile(1., velocity, 2., .01)
    with pytest.raises(ValueError, match='trailing vector'):
        atmosphere.neutral_wall_traction(velocity, 1., .01)


def test_profile_rejects_reference_and_result_overflow():
    with pytest.raises(ValueError, match='above the roughness'):
        atmosphere.neutral_profile(1., [1., 0., 0.], .01, .01)
    with pytest.raises(ValueError, match='numerical range'):
        atmosphere.neutral_profile(1e300, [1e308, 0., 0.], .02, .01)
    with pytest.raises(ValueError, match='Scaling parameters'):
        atmosphere.scaling_report(1., 1e-308, 1., mach=10.)
    with pytest.raises(ValueError, match='FP32'):
        atmosphere.scaling_report(1., 1., 1e50)


@pytest.mark.parametrize('tau,constant,message', [(.5, .17, 'tau'), (float('inf'), .17, 'tau'),
    (.8, -.01, 'constant'), (.8, float('nan'), 'constant')])
def test_collision_rejects_unphysical_relaxation(tau, constant, message):
    assert SmagorinskyV1(.8, 0.).constant == 0.
    with pytest.raises(ValueError, match=message): SmagorinskyV1(tau, constant)


@pytest.mark.parametrize('steps', [True, -1, 1.5, '1'])
def test_engine_rejects_steps_without_advancing(steps):
    simulation = LettuceSimulation('tgv2d-bgk', 'cpu', 8)
    before = simulation.snapshot()
    with pytest.raises(ValueError, match='nonnegative integer'): simulation.advance(steps)
    after = simulation.snapshot()
    np.testing.assert_array_equal(after['populations'], before['populations'])
    assert after['iteration'] == before['iteration'] == 0


@pytest.mark.parametrize('change,message', [
    ({'boundary_method': 'unknown'}, 'explicit boundary_method'),
    ({'moving_bodies': [{'body': 1}]}, 'stationary uniform'),
    ({'boundary_field': {'path': 'unused'}}, 'exactly one mapped'),
    ({'mach': .2}, 'Mach 0.15'),
    ({'wall_links': [[1, 0, .5]]}, 'overlap NEE'),
])
def test_boundary_plan_rejects_unsupported_compositions(change, message):
    spec = channel(wall=False)
    assert len(boundaries.compile_plan(spec)['indices']) > 0
    spec.update(change)
    with pytest.raises(ValueError, match=message): boundaries.compile_plan(spec)


def test_boundary_plan_requires_pairs_reference_and_slip_tangency():
    spec = channel(wall=False)
    patches = spec['boundary_set']['patches']
    patches[2]['condition'] = {'type': 'slip'}
    with pytest.raises(ValueError, match='opposite-face pairs'): boundaries.compile_plan(spec)
    patches[3]['condition'] = {'type': 'slip'}
    patches[0]['condition']['velocity'] = [1., .1, 0.]
    with pytest.raises(ValueError, match='zero normal component'): boundaries.compile_plan(spec)
    patches[0]['condition']['velocity'] = [1., 0., 0.]
    patches[1]['condition'] = {'type': 'wall'}
    with pytest.raises(ValueError, match='reference face'): boundaries.compile_plan(spec)


@pytest.mark.parametrize('cancel', [False, True])
def test_refinement_job_publishes_only_when_not_cancelled(monkeypatch, cancel):
    from hawa import refinement
    monkeypatch.setattr(jobs, 'DEVICE_SLOT', threading.Semaphore(1))
    job = jobs.Job({'kind': 'refine', 'case': {'example': 'tgv3d-bgk', 'size': 8}, 'steps': 7})
    result = {'field': 'result', 'nested': [1, 2]}
    def run(request, checkpoint):
        assert request == job.request
        checkpoint(3)
        if cancel: job.control('cancel')
        return result
    monkeypatch.setattr(refinement, 'run_refined', run)
    job.work()
    assert job.state == ('cancelled' if cancel else 'completed')
    assert job.result == (None if cancel else result)
    assert job.session is None
    assert jobs.DEVICE_SLOT.acquire(blocking=False)
    jobs.DEVICE_SLOT.release()
    if not cancel: assert job.steps == job.target == 7


def test_fixed_motion_and_unsupported_geometry():
    from hawa.motion import speed_bound, validate_bodies
    from test_motion import moving_case
    spec = moving_case(); body = spec['moving_bodies'][0]
    body['motion'] = {'type': 'fixed'}
    assert speed_bound(body) == 0.
    validate_bodies(spec)
    spec['collision'] = 'regularized'
    with pytest.raises(ValueError, match='uniform BGK'): validate_bodies(spec)
    spec['collision'] = 'bgk'; body['geometry']['type'] = 'cone'
    with pytest.raises(ValueError, match='sphere, cylinder or sdf'): validate_bodies(spec)


@pytest.mark.parametrize('options,message', [
    ({'period': 0.}, 'period: Input should be greater than 0'),
    ({'period': float('nan')}, 'period: Input should be a finite number'),
    ({'period': '0.2'}, 'period: Input should be a valid number'),
    ({'period': True}, 'period: Input should be a valid number'),
    ({'settle_cycles': True}, 'settle_cycles: Input should be a valid integer'),
    ({'settle_cycles': 1.}, 'settle_cycles: Input should be a valid integer'),
    ({'settle_cycles': -1}, 'settle_cycles: Input should be greater than or equal to 0'),
    ({'settle_cycles': 21}, 'settle_cycles: Input should be less than or equal to 20'),
    ({'cycles': 0}, 'cycles: Input should be greater than or equal to 1'),
    ({'cycles': 21}, 'cycles: Input should be less than or equal to 20'),
    ({'metric': 'drag'}, "metric: Input should be 'force', 'torque', 'power' or 'input_power'"),
    ({'axis': 3}, 'axis: Input should be less than or equal to 2'),
    ({'axis': -1}, 'axis: Input should be greater than or equal to 0'),
    ({'axis': 1.}, 'axis: Input should be a valid integer'),
    ({'body_id': ''}, 'body_id: String should have at least 1 character'),
    ({'body_id': 3}, 'body_id: Input should be a valid string'),
    ({'kind': 'record'}, "kind: Input should be 'motion_evaluate'"),
    ({'device': 0}, 'device: Input should be a valid string'),
    ({'case': []}, 'case: Input should be a valid dictionary'),
    ({'steps': 10}, 'steps: Extra inputs are not permitted'),
    ([], ': Input should be a valid dictionary or instance of MotionEvaluation')])
def test_motion_evaluation_rejects_invalid_requests_before_advancing(options, message):
    from hawa.motion import evaluate_motion
    from hawa.plugin import Session
    from test_motion import moving_case
    session = Session(moving_case(), 'cpu')
    with pytest.raises(ValueError) as error: evaluate_motion(session, options, lambda _: None)
    assert str(error.value) == 'Motion evaluation' + ('' if message.startswith(':') else ' ') + message
    assert session.flow.i == 0 and not session.solver.moving.history


@pytest.mark.parametrize('mode,message', [('advanced', 'fresh physical'), ('empty', 'no solid'),
    ('face', 'touches a domain face')])
def test_optimization_rejects_invalid_obstacle_before_advancing(mode, message):
    from hawa.optimization import evaluate
    from hawa.plugin import Session
    from test_optimization import spec
    case = spec()
    if mode == 'empty': case['solid'] = []
    if mode == 'face': case['solid'].append(int(np.ravel_multi_index((5, 0, 5), case['shape'])))
    session = Session(case, 'cpu')
    if mode == 'advanced': session.advance(1)
    before = session.flow.i
    with pytest.raises(ValueError, match=message): evaluate(session, 5, 2, 1.)
    assert session.flow.i == before


@pytest.mark.parametrize('late', [False, True])
def test_optimization_cancellation_cannot_publish_objective(late):
    from hawa.optimization import evaluate
    from hawa.plugin import Session
    from test_optimization import spec
    session = Session(spec(), 'cpu')
    if not late: session.stop.set()
    def checkpoint(step):
        if late: session.stop.set()
    with pytest.raises(RuntimeError, match='cancelled'): evaluate(session, 2, 1, 1., checkpoint)
    assert session.state != 'completed'


def test_nonfinite_or_empty_fluid_is_rejected():
    from hawa.plugin import Session
    from hawa.quality import assess
    from test_neutral import case
    session = Session(case(), 'cpu')
    session.flow.f.fill_(float('nan'))
    report = assess(session)
    assert report['status'] == 'rejected'
    assert report['max_lattice_mach'] is None
    assert report['transfer_eligible'] is False
