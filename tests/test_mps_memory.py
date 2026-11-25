"""Regressions for MPS memory release on session/job teardown (#76)."""
import pytest
import torch

from hawa.plugin import dispatch


def _small_case(shape=(12, 10, 8)):
    return {
        "shape": list(shape),
        "dx": 0.25,
        "speed": 2.0,
        "viscosity": 0.02,
        "density": 1.225,
        "mach": 0.05,
        "collision": "regularized",
        "boundaries": ["inlet", "outlet", "periodic", "periodic", "wall", "slip"],
    }


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS unavailable")
def test_mps_teardown_returns_current_and_driver_memory():
    """On Apple Silicon MPS, closing a session returns current and driver allocations."""
    torch.mps.synchronize()
    torch.mps.empty_cache()
    before_cur = torch.mps.current_allocated_memory()

    sid = dispatch({"op": "create", "case": _small_case((64, 48, 32)), "device": "mps"})["session"]
    dispatch({"op": "step", "session": sid, "steps": 10})
    peak_drv = torch.mps.driver_allocated_memory()
    assert peak_drv > 100 * 1024 * 1024

    dispatch({"op": "close", "session": sid})
    after_cur = torch.mps.current_allocated_memory()
    after_drv = torch.mps.driver_allocated_memory()
    assert after_cur <= before_cur + 1024 * 1024
    assert after_drv < peak_drv * 0.25


