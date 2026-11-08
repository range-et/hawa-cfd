import pytest
import torch

from hawa.backends import select_backend
from hawa.lbm import VortexConfig, VortexSimulation


def test_vortex_conservation_and_analytic_decay():
    sim = VortexSimulation(select_backend("cpu"))
    initial_energy = sim.diagnostics()["mean_kinetic_energy"]
    sim.advance(200)
    report = sim.diagnostics()
    assert report["passed"], report
    assert report["mean_kinetic_energy"] < initial_energy
    assert report["velocity_relative_l2_error"] < 0.02


def test_chunked_stepping_matches_single_run():
    a = VortexSimulation(select_backend("cpu"), VortexConfig(size=32))
    b = VortexSimulation(select_backend("cpu"), VortexConfig(size=32))
    a.advance(20)
    b.advance(7).advance(13)
    torch.testing.assert_close(a.f, b.f, rtol=0, atol=0)


@pytest.mark.parametrize("device", ["mps", "cuda:0"])
def test_accelerator_agrees_with_cpu(device):
    available = torch.backends.mps.is_available() if device == "mps" else torch.cuda.is_available()
    if not available:
        pytest.skip(device + " hardware unavailable")
    cpu = VortexSimulation(select_backend("cpu"), VortexConfig(size=32)).advance(50)
    gpu = VortexSimulation(select_backend(device), VortexConfig(size=32)).advance(50)
    torch.testing.assert_close(gpu.f.cpu(), cpu.f, rtol=2e-5, atol=2e-6)
    assert gpu.diagnostics()["passed"]


def test_explicit_device_never_falls_back(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="Cannot use cuda:0"):
        select_backend("cuda")


def test_auto_falls_back_visibly(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    backend = select_backend("auto")
    assert backend.device.type == "cpu"
    assert len(backend.notes) == 2


@pytest.mark.parametrize("kwargs", [{"tau": 0.5}, {"speed": 1}, {"size": 8}, {"tau": float("nan")}])
def test_invalid_physical_configuration(kwargs):
    with pytest.raises(ValueError):
        VortexConfig(**kwargs)
