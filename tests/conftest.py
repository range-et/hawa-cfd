"""Explicit backend coverage; CUDA verification must never pass by skipping it."""
import pytest
import torch


def pytest_addoption(parser):
    parser.addoption("--require-cuda", action="store_true",
                     help="Fail before collection if a real CUDA operation cannot run")


def pytest_sessionstart(session):
    if session.config.getoption("--require-cuda"):
        from hawa.backends import select_backend
        try:
            backend = select_backend("cuda:0")
            assert backend.device.type == "cuda"
        except Exception as exc:
            raise pytest.UsageError("CUDA verification requires working hardware: {}".format(exc))


@pytest.fixture(params=["cpu", "cuda:0", "mps"])
def solver_device(request):
    device = request.param
    if device.startswith("cuda") and not torch.cuda.is_available():
        pytest.skip("CUDA hardware unavailable")
    if device == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS hardware unavailable")
    return device
