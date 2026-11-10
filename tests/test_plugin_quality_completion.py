"""Public session step validation must leave solver and statistics unchanged."""
import pytest
import torch
from hawa.plugin import Session


@pytest.mark.parametrize('steps', [True, False, -1, 1.5, '1', None])
def test_session_rejects_invalid_steps_without_mutating_state(steps):
    session = Session({'example': 'tgv3d-bgk', 'size': 8}, 'cpu')
    populations = session.flow.f.clone()
    initial_quality = dict(session.quality)
    with pytest.raises(ValueError, match='Steps must be a nonnegative integer'):
        session.advance(steps)
    torch.testing.assert_close(session.flow.f, populations, rtol=0, atol=0)
    assert session.flow.i == 0 and session.samples == 0 and session.mean_u is None
    assert session.quality == initial_quality and session.state == 'ready'
    # Zero is an admitted no-op, unlike boolean False despite equal numeric value.
    session.advance(0)
    torch.testing.assert_close(session.flow.f, populations, rtol=0, atol=0)
    assert session.flow.i == 0 and session.samples == 0
