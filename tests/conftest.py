"""Explicit backend coverage; CUDA verification must never pass by skipping it."""
import sys

import pytest
import torch


def pytest_addoption(parser):
    parser.addoption("--require-cuda", action="store_true",
                     help="Fail before collection if a real CUDA operation cannot run")


def pytest_configure(config):
    config.addinivalue_line("markers", "production_python: runs a production entry point "
                            "that refuses any interpreter other than Python 3.9")


def pytest_collection_modifyitems(config, items):
    """The Python 3.12 dev suite skips these; the authoritative 3.9 suite runs them."""
    if sys.version_info[:2] == (3, 9):
        return
    skip = pytest.mark.skip(reason="production entry point requires Python 3.9")
    for item in items:
        if item.get_closest_marker("production_python"):
            item.add_marker(skip)


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
