import json
import time

import numpy as np
import pytest

from hawa.plugin import check_case, dispatch, dispatch_json, SESSIONS


@pytest.fixture
def session():
    result = dispatch({"op": "create", "case": {"example": "tgv3d-bgk", "size": 12}, "device": "cpu"})
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
    np.testing.assert_array_equal(SESSIONS[session].flow.f.numpy(), before.numpy())
    assert dispatch({"op": "status", "session": session})["steps"] == 5
    sampled = dispatch({"op": "sample", "session": session, "points": [[1.5, 2, 3], [-1, 0, 0]]})
    assert sampled["values"][0] is not None and sampled["values"][1] is None
    field = dispatch({"op": "slice", "session": session, "axis": 2, "index": 5})
    assert field["shape"] == [12, 12] and len(field["values"]) == 144
    lines = dispatch({"op": "streamlines", "session": session, "seeds": [[2, 2, 2]], "steps": 10})
    assert len(lines["paths"][0]) > 2
    assert len(lines["paths"][0]) <= 11


def test_physical_wind_boundaries_and_solid_on_cpu_and_mps():
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
    before=s.flow.f.numpy().copy()
    path=tmp_path/'bad.npz'
    np.savez_compressed(path,populations=before*density,iteration=np.array(iteration),spec=np.array(canonical(s.spec)))
    with pytest.raises(ValueError,match='Checkpoint'):
        dispatch({'op':'load','session':session,'path':str(path)})
    np.testing.assert_array_equal(before,s.flow.f.numpy())
    assert s.flow.i==0


@pytest.mark.parametrize('size',[0,-1,True,16.5,10000])
def test_example_preflight_checks_size(size):
    with pytest.raises(ValueError,match='size'):check_case({'example':'tgv3d-bgk','size':size})


def test_example_preflight_checks_memory():
    with pytest.raises(ValueError,match='memory'):check_case({'example':'tgv3d-bgk','size':128})
