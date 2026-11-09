"""Refinement placement tolerances must not grow with world translation."""
import numpy as np
import pytest

from hawa.fields import get
from hawa.refinement import run_refined


def cases(translation, basis=None):
    axes = np.eye(3) if basis is None else np.asarray(basis, dtype=float)
    coarse = dict(shape=[17]*3, dx=1., spacing=1., origin=[translation]*3,
                  basis=axes.tolist(), speed=1., viscosity=1., density=1.225,
                  mach=.05, collision='bgk', solid=[],
                  boundaries=['inlet', 'outlet', 'periodic', 'periodic', 'periodic', 'periodic'])
    origin = np.asarray(coarse['origin']) + np.array([5, 5, 5]) @ axes
    fine = dict(coarse, shape=[13]*3, dx=.5, spacing=.5, origin=origin.tolist(),
                refinement_lower=[5]*3, refinement_upper=[11]*3)
    return coarse, fine


@pytest.mark.parametrize('translation', [0., 1_000_000., -1_000_000.])
@pytest.mark.parametrize('axis', [0, 1, 2])
@pytest.mark.parametrize('offset', [-1., 1.])
def test_misaligned_patch_rejected_before_solver_construction(monkeypatch, translation, axis, offset):
    import hawa.plugin
    coarse, fine = cases(translation)
    fine['origin'][axis] += offset

    def unexpected_session(*args, **kwargs):
        pytest.fail('Misaligned patch reached solver construction')

    monkeypatch.setattr(hawa.plugin, 'Session', unexpected_session)
    with pytest.raises(ValueError, match='Fine grid origin does not match its parent patch'):
        run_refined(dict(case=coarse, fine_case=fine, steps=1, device='cpu'), lambda n: None)


@pytest.mark.parametrize('translation', [0., 1_000_000., -1_000_000.])
@pytest.mark.parametrize('offset, accepted', [(5e-8, True), (2e-7, False)])
def test_existing_absolute_alignment_bound_is_preserved(monkeypatch, translation, offset, accepted):
    import hawa.plugin
    coarse, fine = cases(translation)
    fine['origin'][0] += offset

    class ReachedSolver(Exception):
        pass

    def stop_at_session(*args, **kwargs):
        raise ReachedSolver()

    monkeypatch.setattr(hawa.plugin, 'Session', stop_at_session)
    error = ReachedSolver if accepted else ValueError
    with pytest.raises(error):
        run_refined(dict(case=coarse, fine_case=fine, steps=1, device='cpu'), lambda n: None)


@pytest.mark.parametrize('translation', [0., 1_000_000., -1_000_000.])
@pytest.mark.parametrize('basis', [None, [[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]]])
def test_aligned_translated_and_rotated_patch_retains_frame_placement(translation, basis):
    coarse, fine = cases(translation, basis)
    result = run_refined(dict(case=coarse, fine_case=fine, steps=1, device='cpu'), lambda n: None)
    arrays, meta = get(result['fine_frame']['frame'])
    _, parent = get(result['coarse_frame']['frame'])
    assert meta['case']['origin'] == fine['origin']
    assert meta['case']['basis'] == coarse['basis']
    assert meta['iteration'] == 2 * parent['iteration'] == 2
    assert meta['time'] == pytest.approx(parent['time'])
    assert np.isfinite(arrays['velocity']).all()


@pytest.mark.parametrize('lower, upper, shape, reason', [
    ([18, 5, 5], [24, 11, 11], [13]*3, 'clearance'),  # disjoint
    ([16, 5, 5], [22, 11, 11], [13]*3, 'clearance'),  # touching
    ([12, 5, 5], [18, 11, 11], [13]*3, 'clearance'),  # partial overlap
    ([0]*3, [16]*3, [33]*3, 'clearance'),  # coincident extent
    ([0, 5, 5], [6, 11, 11], [13]*3, 'clearance'),  # contained, no halo
    ([5]*3, [8]*3, [7]*3, 'four coarse intervals'),
    ([5]*3, [11]*3, [12, 13, 13], 'resolution'),
    ([5., 5, 5], [11]*3, [13]*3, 'integer'),
    ([5, 5], [11, 11], [13]*3, 'dimension'),
])
@pytest.mark.parametrize('translation', [0., 1_000_000.])
def test_unsupported_patch_topology_rejects_before_allocation(monkeypatch, lower, upper, shape, reason, translation):
    import hawa.plugin
    coarse, fine = cases(translation)
    fine.update(refinement_lower=lower, refinement_upper=upper, shape=shape)
    fine['origin'] = (np.asarray(coarse['origin']) + np.asarray((lower + [5]*3)[:3])).tolist()
    def unexpected_session(*args, **kwargs):
        pytest.fail('Unsupported fine_case topology reached parent Session allocation')
    monkeypatch.setattr(hawa.plugin, 'Session', unexpected_session)
    import lettuce as lt
    monkeypatch.setattr(lt, 'Simulation', unexpected_session)
    checkpoints = []
    with pytest.raises(ValueError, match=reason) as error:
        run_refined(dict(case=coarse, fine_case=fine, steps=1, device='cpu'), checkpoints.append)
    assert 'fine_case' in str(error.value) and 'parent' in str(error.value)
    assert checkpoints == []


@pytest.mark.parametrize('lower, upper', [([2]*3, [6]*3), ([10]*3, [14]*3)])
def test_minimum_patch_and_clearance_limits_remain_supported(lower, upper):
    coarse, fine = cases(0.)
    fine.update(refinement_lower=lower, refinement_upper=upper, shape=[9]*3, origin=lower)
    result = run_refined(dict(case=coarse, fine_case=fine, steps=1, device='cpu'), lambda n: None)
    arrays, meta = get(result['fine_frame']['frame'])
    assert arrays['pressure'].shape == (9, 9, 9)
    assert meta['iteration'] == 2 and meta['case']['origin'] == lower
    assert np.isfinite(arrays['velocity']).all()


def test_relative_rotation_rejected_before_construction(monkeypatch):
    import hawa.plugin
    coarse, fine = cases(0.)
    fine['basis'] = [[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]]
    def unexpected_session(*args, **kwargs):
        pytest.fail('Relative rotation reached solver construction')
    monkeypatch.setattr(hawa.plugin, 'Session', unexpected_session)
    with pytest.raises(ValueError, match='Grid axes must match'):
        run_refined(dict(case=coarse, fine_case=fine, steps=1, device='cpu'), lambda n: None)


@pytest.mark.parametrize('lower, upper, shape, reason', [
    ([16, 5, 5], [22, 11, 11], [13]*3, 'clearance'),
    ([5]*3, [11]*3, [12, 13, 13], 'resolution'),
    ([5., 5, 5], [11]*3, [13]*3, 'integer'),
    ([5, 5], [11, 11], [13]*3, 'dimension'),
])
def test_direct_stepper_keeps_topology_defenses(lower, upper, shape, reason):
    from types import SimpleNamespace
    from hawa.refinement import RefinedStepper
    # Topology failure must precede any access to collision or tensor state.
    coarse = SimpleNamespace(flow=SimpleNamespace(resolution=[17]*3, stencil=SimpleNamespace(d=3)))
    fine = SimpleNamespace(flow=SimpleNamespace(resolution=shape))
    with pytest.raises(ValueError, match=reason):
        RefinedStepper(coarse, fine, lower, upper)


@pytest.mark.parametrize('invalid', [None, 5])
def test_missing_or_scalar_patch_corner_has_domain_diagnostic(monkeypatch, invalid):
    import hawa.plugin
    coarse, fine = cases(0.)
    fine['refinement_lower'] = invalid
    def unexpected_session(*args, **kwargs):
        pytest.fail('Malformed corner reached solver construction')
    monkeypatch.setattr(hawa.plugin, 'Session', unexpected_session)
    with pytest.raises(ValueError, match='fine_case.*parent.*dimension'):
        run_refined(dict(case=coarse, fine_case=fine, steps=1, device='cpu'), lambda n: None)
