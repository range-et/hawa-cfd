import numpy as np
import pytest
import torch
import lettuce

from hawa.engine import LettuceSimulation


@pytest.mark.parametrize("device", ["cpu", "mps", "cuda:0"])
def test_actual_lettuce_engine_runs_3d_in_chunks(device):
    if device == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    if device == "cuda:0" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    sim = LettuceSimulation("tgv3d-bgk", device=device, size=12)
    before = sim.snapshot()
    sim.advance(7).advance(13)
    assert sim.flow.i == 20
    assert sim.diagnostics()["passed"]
    assert not np.array_equal(before["populations"], sim.snapshot()["populations"])
    assert not np.shares_memory(before["populations"], sim.snapshot()["populations"])


def test_context_preserves_cpu_double_default_on_non_cuda_machine():
    if torch.cuda.is_available():
        pytest.skip("Upstream defaults to CUDA when present")
    context = lettuce.Context(dtype=torch.float64)
    assert context.device.type == "cpu"
    assert context.dtype == torch.float64


def test_mps_rejects_double_precision():
    if not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    with pytest.raises(ValueError, match="float64"):
        lettuce.Context(device="mps", dtype=torch.float64, use_native=False)
