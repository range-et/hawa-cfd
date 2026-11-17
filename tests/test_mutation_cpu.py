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


def test_refinement_omitted_steps_runs_default_200_coarse_400_fine():
    """A small real CPU grid protects the public default after preflight extraction."""
    from hawa.refinement import run_refined
    from hawa.fields import get
    coarse = dict(shape=[11]*3, dx=1., spacing=1., origin=[0., 0., 0.],
                  speed=1., viscosity=1., density=1.225, mach=.05,
                  collision='bgk', solid=[],
                  boundaries=['inlet', 'outlet', 'periodic', 'periodic', 'periodic', 'periodic'])
    fine = dict(coarse, shape=[9]*3, dx=.5, spacing=.5, origin=[2., 2., 2.],
                refinement_lower=[2]*3, refinement_upper=[6]*3)
    result = run_refined(dict(case=coarse, fine_case=fine, device='cpu'), lambda n: None)
    _, parent = get(result['coarse_frame']['frame'])
    _, child = get(result['fine_frame']['frame'])
    assert result['steps'] == parent['iteration'] == 200
    assert child['iteration'] == 400
    assert parent['time'] == pytest.approx(child['time'])
