"""Independent cases and display overlap are not coupled refinement contracts."""
import numpy as np
import pytest
from hawa.fields import store, dispatch_field
from hawa.plugin import Session


@pytest.mark.parametrize('origin, spacing, point, expected', [
    ((2, 2, 2), .5, (3, 3, 3), 2.),  # contained finer domain owns
    ((8, 0, 0), .5, (7, 1, 1), None),  # disjoint gap has no data
    ((6, 0, 0), .5, (6, 1, 1), 2.),  # shared face: finest owns
    ((0, 0, 0), 1., (3, 3, 3), 1.),  # duplicate extent: first input owns
    ((4, 0, 0), .5, (5, 1, 1), 2.),  # partial overlap: finest owns
])
@pytest.mark.parametrize('translation', [0., 1_000_000.])
def test_view_relationships_keep_declared_sample_ownership(origin, spacing, point, expected, translation):
    keys = []
    for start, dx, speed in [((0, 0, 0), 1., 1.), (origin, spacing, 2.)]:
        shape = (7, 7, 7)
        arrays = dict(velocity=np.zeros((3,)+shape), pressure=np.zeros(shape), density=np.ones(shape), solid=np.zeros(shape, bool))
        arrays['velocity'][0] = speed
        spec = dict(shape=list(shape), dx=dx, spacing=dx, origin=(np.array(start)+translation).tolist(), basis=np.eye(3).tolist())
        keys.append(store(arrays, dict(case=spec, time=0., mean=False))['frame'])
    # Field API points use the first frame's local displayed coordinates.
    result = dispatch_field(dict(action='sample', frames=keys, field='speed', points=[point]))
    assert result['valid'] == [expected is not None]
    assert result['values'] == [0. if expected is None else expected]
    assert result['domain_index'] == [-1 if expected is None else (0 if expected == 1. else 1)]
    if spacing == 1.:
        reverse = dispatch_field(dict(action='sample', frames=keys[::-1], field='speed', points=[point]))
        assert reverse['values'] == [2.] and reverse['domain_index'] == [0]


@pytest.mark.parametrize('origin, dx', [((2, 2, 2), .5), ((8, 0, 0), .5), ((6, 0, 0), .5), ((0, 0, 0), 1.), ((4, 0, 0), .5)])
def test_independent_sessions_do_not_reject_spatial_relationships(origin, dx):
    spec = dict(shape=[7]*3, dx=1., spacing=1., origin=[0]*3, speed=1., viscosity=1., density=1.225,
                mach=.05, collision='bgk', solid=[], boundaries=['inlet','outlet','periodic','periodic','periodic','periodic'])
    first = Session(spec, 'cpu')
    second = Session(dict(spec, origin=list(origin), dx=dx, spacing=dx), 'cpu')
    assert first.flow.f.data_ptr() != second.flow.f.data_ptr()
    before = first.flow.f.clone()
    second.flow.f.zero_()
    assert first.flow.f.equal(before)
    assert first.flow.i == second.flow.i == 0
