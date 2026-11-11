"""Previously unmeasured portable contracts, callbacks and control transitions."""
import copy
import numpy as np
import pytest

from hawa import plugin
from hawa.boundary_data import FieldInlet
from hawa.collision import SmagorinskyV1
from hawa.neutral import ShiftedEquilibrium, ShiftedRegularizedSGS
from hawa.plugin import SlipBoundary, ExtrapolationOutlet


@pytest.mark.parametrize('kind', [FieldInlet, SmagorinskyV1, ShiftedEquilibrium,
                                  ShiftedRegularizedSGS, SlipBoundary, ExtrapolationOutlet])
def test_portable_models_do_not_advertise_native_kernels(kind):
    # Capability declarations are deliberately independent of initialized flow state.
    obj = object.__new__(kind)
    assert obj.native_available() is False
    if kind is not FieldInlet:
        with pytest.raises(NotImplementedError):
            obj.native_generator(0)


def test_external_reset_discards_runtime_report_without_aliasing_plan():
    from test_neutral_external import external
    session = plugin.Session(external(), 'cpu')
    links = session.solver.external_links
    expected = copy.deepcopy(links.plan['report'])
    session.advance(2)
    assert 'mass_budget_residual_lu' in links.report
    links.reset()
    assert links.report == expected
    links.report['sentinel'] = 123
    assert 'sentinel' not in links.plan['report']
    links.reset()
    assert links.report == expected


def test_optional_field_collection_callbacks_preserve_sample_results():
    from test_field_collection import frame
    from hawa.field_collection import FieldCollection, dispatch_collection
    from hawa.fields import FRAMES
    key = frame(speed=2.)
    try:
        view = FieldCollection([key], 'speed')
        values, valid, velocity, owner = view.sample([[1., 1., 1.]])
        np.testing.assert_array_equal(values, [2.])
        assert valid.tolist() == [True] and owner.tolist() == [0]
        np.testing.assert_array_equal(velocity, [[2., 0., 0.]])
        result = dispatch_collection(dict(action='sample', frames=[key], points=[[1., 1., 1.]]))
        assert result['values'] == [2.] and result['valid'] == [True]
    finally:
        FRAMES.pop(key, None)


def test_trace_without_callback_follows_uniform_field():
    from hawa.fields import trace
    velocity = np.zeros((3, 6, 6, 6)); velocity[0] = 1.
    result = trace(dict(velocity=velocity, pressure=np.zeros((6, 6, 6)),
                        density=np.ones((6, 6, 6))), [[1., 2., 2.]], steps=4, step=.5)
    np.testing.assert_allclose(result['paths'], [[[1., 2., 2.], [1.5, 2., 2.], [2., 2., 2.], [2.5, 2., 2.], [3., 2., 2.]]])
    np.testing.assert_array_equal(result['values'], [[1., 1., 1., 1., 1.]])
    assert result['reasons'] == ['completed'] and result['valid'] == [[True] * 5]


def test_boundary_series_default_callbacks_roundtrip_and_wall_history(tmp_path):
    from test_boundary_series import case, recording
    from hawa.boundary_series import capture, sample_parent, sample_wall_history, read
    spec = case()
    manifest = recording(tmp_path/'parent', spec, vary=False)
    mapped = capture(manifest, spec, tmp_path/'boundary.npz')
    arrays, meta = read(mapped['case']['boundary_field']['path'])
    assert meta['schema'] == 'hawa-boundary-series-2'
    shape = spec['shape']
    source = dict(velocity=np.broadcast_to(np.array([1., 2., 3.])[:, None, None, None], (3, *shape)),
                  pressure=np.ones(shape)*4., wall_velocity=np.broadcast_to(np.array([5., 6., 0.])[:, None, None], (3, *shape[:2])))
    u, p, _ = sample_parent(source, spec, np.array([[2., 2., 2.5]]), np.array([False]))
    np.testing.assert_allclose(u, [[1., 2., 3.]])
    np.testing.assert_allclose(p, [4.])
    history = sample_wall_history(source, spec, spec)
    np.testing.assert_allclose(history, source['wall_velocity'])
    assert arrays['velocity'].shape[0] == 3


@pytest.mark.parametrize('operation,fails', [('reset_async', False), ('close_async', False), ('reset_async', True)])
def test_async_control_dispatches_completion_and_records_failure(monkeypatch, operation, fails):
    pending = []
    class QueuedThread:
        def __init__(self, target, **kwargs):
            self.target = target
        def start(self):
            pending.append(self.target)
    monkeypatch.setattr(plugin.threading, 'Thread', QueuedThread)
    result = plugin.dispatch(dict(op='create', case=dict(example='tgv3d-bgk', size=8), device='cpu'))
    key = result['session']; session = plugin.SESSIONS[key]
    try:
        session.advance(2)
        if fails:
            def broken_reset():
                raise RuntimeError('injected reset failure')
            monkeypatch.setattr(session, 'pause', broken_reset)
        plugin.dispatch(dict(op=operation, session=key))
        assert session.stop.is_set() and len(pending) == 1
        assert session.state == ('resetting' if operation == 'reset_async' else 'paused')
        pending.pop()()
        if fails:
            assert session.state == 'failed' and session.error == 'injected reset failure'
        elif operation == 'close_async':
            assert key not in plugin.SESSIONS
        else:
            assert session.status()['steps'] == 0
    finally:
        plugin.SESSIONS.pop(key, None)
