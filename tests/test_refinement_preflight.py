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
