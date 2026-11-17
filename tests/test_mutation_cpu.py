"""The mutation-only guard cannot let a mutated default auto path probe MPS."""
import importlib.util
from pathlib import Path
import pytest
import torch
from hawa import backends


def test_mutation_cpu_guard_blocks_auto_and_explicit_accelerator_probes(monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'tools/mutation/cpu_only.py'
    spec = importlib.util.spec_from_file_location('cpu_only', path)
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(torch.backends.mps, 'is_available', lambda: True)
    plugin.pytest_configure(None)
    seen = []
    def probe(device):
        assert device.type == 'cpu', 'Mutation worker tried to probe an accelerator'
        seen.append(str(device))
    monkeypatch.setattr(backends, '_probe', probe)
    assert not torch.cuda.is_available() and not torch.backends.mps.is_available()
    assert str(backends.select_backend().device) == 'cpu'
    assert str(backends.select_backend('auto').device) == 'cpu'
    for device in ['mps', 'cuda:0']:
        with pytest.raises(RuntimeError, match='unavailable'):
            backends.select_backend(device)
    assert seen == ['cpu', 'cpu']
