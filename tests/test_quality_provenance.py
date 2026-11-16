"""Sampled quality history explains sticky status without changing the policy."""
import json
from types import SimpleNamespace

import pytest
import torch

from hawa.quality import assess


def session():
    flow = SimpleNamespace(i=0, f=torch.ones((1, 2, 2, 2)),
                           units=SimpleNamespace(convert_time_to_pu=lambda i: i * .25))
    flow.rho = lambda: flow.f
    flow.u = lambda: torch.full((3, 2, 2, 2), flow.mach / 3)
    flow.mach = .04
    return SimpleNamespace(flow=flow, spec={}, solver=SimpleNamespace(collision=None))


def sample(s, step, density=1., mach=.04):
    s.flow.i = step
    s.flow.f.fill_(density)
    s.flow.mach = mach
    s.quality = assess(s)
    return s.quality


def test_density_transient_keeps_trigger_and_sampled_peak_after_recovery():
    s = session()
    first = sample(s, 5, 1.08)
    trigger = first['trigger']
    v = trigger['violations'][0]
    assert trigger['status'] == 'warning'
    assert trigger['iteration'] == 5 and trigger['time_seconds'] == 1.25
    assert v == dict(quantity='max_density_deviation', value=pytest.approx(.08), limit=.05)
    assert first['reasons'] == ['Sampled density deviation 8% > 5% at step 5 (t=1.25 s)']
    # A second warning raises the sampled peak, but not the original trigger.
    sample(s, 10, 1.09)
    q = sample(s, 15)
    assert q['status'] == 'warning' and q['current_status'] == 'within-tested-envelope'
    assert q['trigger'] == trigger and q['reasons'] == first['reasons']
    assert q['max_density_deviation'] == 0
    assert q['peak_sampled_density_deviation'] == pytest.approx(.09)
    assert q['peak_sampled_density_deviation_iteration'] == 10
    assert q['peak_sampled_lattice_mach'] == pytest.approx(.04)
    assert q['peak_sampled_lattice_mach_iteration'] == 5
    assert q['iteration'] == 15 and q['time_seconds'] == 3.75
    assert not q['transfer_eligible'] and q['cadence_steps'] == 5
    json.dumps(q, allow_nan=False)


def test_rejection_escalates_warning_and_preserves_both_exceedances():
    s = session()
    sample(s, 5, 1.08)
    rejected = sample(s, 10, 1.12, .2)
    assert rejected['status'] == 'rejected'
    assert rejected['trigger']['violations'] == [
        dict(quantity='max_lattice_mach', value=pytest.approx(.2), limit=.15),
        dict(quantity='max_density_deviation', value=pytest.approx(.12), limit=.1)]
    assert rejected['reasons'] == [
        'Sampled lattice Mach 0.2 > 0.15 at step 10 (t=2.5 s)',
        'Sampled density deviation 12% > 10% at step 10 (t=2.5 s)']
    q = sample(s, 15)
    assert q['trigger'] == rejected['trigger']
    assert q['peak_sampled_lattice_mach'] == pytest.approx(.2)
    assert q['peak_sampled_lattice_mach_iteration'] == 10


@pytest.mark.parametrize('density', [float('nan'), float('inf'), 0., -1.])
def test_invalid_state_trigger_is_json_safe_and_retained(density):
    s = session()
    q = sample(s, 7, density)
    assert q['status'] == 'rejected'
    assert q['trigger'] == dict(status='rejected', iteration=7, time_seconds=1.75,
                              violations=[dict(quantity='finite_positive_fluid', value=False, limit=True)])
    assert q['max_lattice_mach'] is None and q['max_density_deviation'] is None
    assert q['peak_sampled_density_deviation'] == 0
    assert q['peak_sampled_density_deviation_iteration'] is None
    assert q['reasons'] == ['Nonfinite populations, nonpositive density or no fluid cells at step 7 (t=1.75 s)']
    json.dumps(q, allow_nan=False)
    recovered = sample(s, 10)
    assert recovered['trigger'] == q['trigger'] and recovered['reasons'] == q['reasons']


def test_legacy_history_remains_honest_when_trigger_and_peak_step_are_unknown():
    s = session()
    s.quality = dict(status='rejected', reasons=['Earlier exceedance'], peak_sampled_lattice_mach=.46)
    q = sample(s, 100)
    assert q['status'] == 'rejected' and q['trigger'] is None
    assert q['reasons'] == ['Earlier exceedance']
    assert q['peak_sampled_lattice_mach'] == .46
    assert q['peak_sampled_lattice_mach_iteration'] is None
    assert q['peak_sampled_density_deviation'] == 0


def test_unchecked_and_healthy_history_and_mach_only_warning():
    s = session()
    s.quality = dict(status='unchecked')
    q = sample(s, 0)
    assert q['status'] == 'within-tested-envelope' and q['trigger'] is None
    assert q['reasons'] == [] and q['transfer_eligible']
    q = sample(s, 5, mach=.12)
    assert q['status'] == 'warning'
    assert q['trigger']['violations'] == [dict(quantity='max_lattice_mach', value=pytest.approx(.12), limit=.1)]
    assert q['reasons'] == ['Sampled lattice Mach 0.12 > 0.1 at step 5 (t=1.25 s)']


def test_real_checkpoint_round_trip_and_legacy_history(tmp_path):
    import numpy as np
    from hawa.plugin import Session, SESSIONS, dispatch
    s = Session(dict(shape=[6, 6, 6], dx=.1, spacing=.1, speed=1., viscosity=.01), 'cpu')
    SESSIONS[s.id] = s
    path = tmp_path / 'history.npz'
    try:
        s.flow.i = 5
        s.flow.f *= 1.08
        s.quality = assess(s)
        trigger = s.quality['trigger']
        s.flow.f.copy_(s.initial_f)
        s.flow.i = 10
        s.quality = assess(s)
        dispatch(dict(op='save', session=s.id, path=str(path)))
        dispatch(dict(op='reset', session=s.id))
        assert s.quality['trigger'] is None
        dispatch(dict(op='load', session=s.id, path=str(path)))
        assert s.quality['trigger'] == trigger
        assert s.quality['peak_sampled_density_deviation_iteration'] == 5
        assert s.quality['max_density_deviation'] < .001
        with np.load(path, allow_pickle=False) as data:
            arrays = dict(data)
        history = json.loads(str(arrays['quality']))
        history.pop('trigger')
        history.pop('peak_sampled_density_deviation')
        history.pop('peak_sampled_density_deviation_iteration')
        history.pop('peak_sampled_lattice_mach_iteration')
        arrays['quality'] = np.array(json.dumps(history))
        np.savez(path, **arrays)
        dispatch(dict(op='load', session=s.id, path=str(path)))
        assert s.quality['trigger'] is None and s.quality['status'] == 'warning'
        assert s.quality['reasons'] == history['reasons']
    finally:
        dispatch(dict(op='close', session=s.id))


@pytest.mark.parametrize('key,value', [
    ('peak_sampled_density_deviation', 'bad'), ('peak_sampled_density_deviation', float('nan')),
    ('peak_sampled_density_deviation', -1), ('peak_sampled_density_deviation', True),
    ('peak_sampled_density_deviation_iteration', -1), ('peak_sampled_density_deviation_iteration', 11),
    ('peak_sampled_lattice_mach_iteration', True), ('trigger', 'bad'),
    ('trigger', {}),
])
def test_checkpoint_rejects_invalid_provenance_before_mutating(tmp_path, key, value):
    import numpy as np
    from hawa.plugin import Session, SESSIONS, dispatch
    s = Session(dict(shape=[6, 6, 6], dx=.1, spacing=.1, speed=1., viscosity=.01), 'cpu')
    SESSIONS[s.id] = s
    path = tmp_path / 'bad.npz'
    try:
        dispatch(dict(op='save', session=s.id, path=str(path)))
        with np.load(path, allow_pickle=False) as data:
            arrays = dict(data)
        history = json.loads(str(arrays['quality']))
        history[key] = value
        arrays['quality'] = np.array(json.dumps(history))
        np.savez(path, **arrays)
        before = s.flow.f.clone()
        expected = 'trigger' if key == 'trigger' else 'provenance'
        with pytest.raises(ValueError, match='^Checkpoint quality ' + expected + ' is invalid$'):
            dispatch(dict(op='load', session=s.id, path=str(path)))
        assert torch.equal(s.flow.f, before) and s.flow.i == 0
    finally:
        dispatch(dict(op='close', session=s.id))


@pytest.mark.parametrize('change', [
    dict(status='warning'), dict(iteration=-1), dict(iteration=11), dict(iteration=True),
    dict(time_seconds=-1), dict(time_seconds=float('inf')), dict(time_seconds='bad'),
    dict(violations=[]), dict(violations={}), dict(violations=['bad']),
    dict(violations=[dict(quantity=[], value=.2, limit=.15)]),
    dict(violations=[dict(quantity='unknown', value=.2, limit=.15)]),
    dict(violations=[dict(quantity='max_lattice_mach', value=float('nan'), limit=.15)]),
    dict(violations=[dict(quantity='max_lattice_mach', value='bad', limit=.15)]),
    dict(violations=[dict(quantity='max_lattice_mach', value=.2, limit=.1)]),
    dict(violations=[dict(quantity='max_lattice_mach', value=.1, limit=.15)]),
    dict(violations=[dict(quantity='finite_positive_fluid', value=True, limit=True)]),
    dict(violations=[dict(quantity='finite_positive_fluid', value=False, limit=False)]),
])
def test_trigger_validation_rejects_malformed_history(change):
    from hawa.quality import validate_provenance
    trigger = dict(status='rejected', iteration=5, time_seconds=1.25,
                   violations=[dict(quantity='max_lattice_mach', value=.2, limit=.15)])
    trigger.update(change)
    expected = 'violation' if change.get('violations') and isinstance(change['violations'], list) else 'trigger'
    with pytest.raises(ValueError, match='^Checkpoint quality ' + expected + ' is invalid$'):
        validate_provenance(dict(status='rejected', trigger=trigger), 10)


def test_valid_warning_rejection_and_invalid_fluid_provenance():
    from hawa.quality import validate_provenance
    s = session()
    validate_provenance(sample(s, 5, mach=.12), 5)
    validate_provenance(sample(s, 10, mach=.2), 10)
    s = session()
    validate_provenance(sample(s, 5, float('nan')), 5)


def test_legacy_absent_reasons_and_healthy_history_do_not_invent_triggers():
    s = session()
    s.quality = dict(status='warning')
    q = sample(s, 5)
    assert q['reasons'] == [] and q['trigger'] is None
    s.quality = dict(status='within-tested-envelope', reasons=['stale'], trigger={'stale': True})
    q = sample(s, 10)
    assert q['reasons'] == [] and q['trigger'] is None


def test_trigger_only_lists_quantities_strictly_above_the_limit():
    import math
    s = session()
    velocity = torch.zeros((3, 2, 2, 2), dtype=torch.float64)
    velocity[0] = .15 / math.sqrt(3)
    s.flow.u = lambda: velocity
    q = sample(s, 5, 1.12)
    assert q['max_lattice_mach'] == .15
    assert [v['quantity'] for v in q['trigger']['violations']] == ['max_density_deviation']


@pytest.mark.parametrize('density,mach', [(1.08, .04), (1.12, .04), (1., .2)])
def test_checkpoint_accepts_initial_exceedance_at_step_zero(density, mach):
    from hawa.quality import validate_provenance
    s = session()
    validate_provenance(sample(s, 0, density, mach), 0)


@pytest.mark.parametrize('quantity,value,limit', [
    ('max_lattice_mach', .15, .15), ('max_density_deviation', .1, .1)])
def test_checkpoint_rejects_threshold_equality(quantity, value, limit):
    from hawa.quality import validate_provenance
    with pytest.raises(ValueError, match='^Checkpoint quality violation is invalid$'):
        validate_provenance(dict(status='rejected', trigger=dict(status='rejected', iteration=0,
            time_seconds=0, violations=[dict(quantity=quantity, value=value, limit=limit)])), 0)


def test_checkpoint_rejects_mismatched_severity_with_otherwise_valid_limits():
    from hawa.quality import validate_provenance
    with pytest.raises(ValueError, match='^Checkpoint quality trigger is invalid$'):
        validate_provenance(dict(status='rejected', trigger=dict(status='warning', iteration=0,
            time_seconds=0, violations=[dict(quantity='max_lattice_mach', value=.12, limit=.1)])), 0)


@pytest.mark.parametrize('quantity,limit', [('mach', .1), ('mach', .15), ('density', .05), ('density', .1)])
def test_near_threshold_reason_keeps_strict_exceedance_visible(quantity, limit):
    import math
    s = session()
    s.flow.f = s.flow.f.double()
    velocity = torch.zeros((3, 2, 2, 2), dtype=torch.float64)
    s.flow.u = lambda: velocity
    if quantity == 'mach':
        velocity[0] = math.nextafter(limit, math.inf) / math.sqrt(3)
    else:
        s.flow.f.fill_(math.nextafter(1 + limit, math.inf))
    q = assess(s)
    v = q['trigger']['violations'][0]
    assert v['value'] > limit
    amount = v['value'] * (100 if quantity == 'density' else 1)
    label = 'density deviation' if quantity == 'density' else 'lattice Mach'
    unit = '%' if quantity == 'density' else ''
    bound = limit * (100 if quantity == 'density' else 1)
    assert q['reasons'] == [f'Sampled {label} {amount!r}{unit} > {bound:.6g}{unit} at step 0 (t=0 s)']
