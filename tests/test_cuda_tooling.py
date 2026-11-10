"""Measured CPU/isolated orchestration coverage of the CUDA PR tooling changes."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch
import lettuce as lt

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def test_windows_memory_adapter_uses_peak_working_set(monkeypatch):
    import example_worker
    import psutil
    # Restore the real module after exercising the Windows-only diagnostic on macOS.
    monkeypatch.setitem(sys.modules, 'resource', sys.modules.get('resource'))
    monkeypatch.setattr(psutil, 'Process', lambda: SimpleNamespace(memory_info=lambda: SimpleNamespace(peak_wset=4096)))
    example_worker.windows_resource_adapter()
    resource = sys.modules['resource']
    assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss == 4
    with pytest.raises(ValueError): resource.getrusage(99)


def test_portable_adapter_changes_only_omitted_native_default(monkeypatch):
    import pytest_portable
    calls = []
    def context(self, **kwargs): calls.append(kwargs)
    monkeypatch.setattr(lt.Context, '__init__', context)
    pytest_portable.pytest_configure(None)
    try:
        lt.Context('cpu', torch.float64)
        lt.Context('cpu', torch.float32, use_native=True)
        assert calls == [dict(device='cpu', dtype=torch.float64, use_native=False),
                         dict(device='cpu', dtype=torch.float32, use_native=True)]
    finally:
        pytest_portable.pytest_unconfigure(None)
    assert lt.Context.__init__ is context


def test_rotating_sphere_cpu_reports_finite_opposing_torque():
    from benchmark_rotating_sphere import benchmark
    report = benchmark(1., device='cpu')
    assert report['steps'] > 0
    assert report['torque'] < 0 and np.isfinite(report['relative_error'])
    assert report['analytic_unbounded'] == pytest.approx(-8*np.pi*.2*.1)


def test_parity_worker_captures_all_checkpoints_from_real_cpu_solver(tmp_path, monkeypatch):
    import parity_worker
    import hawa.cases
    monkeypatch.setattr(hawa.cases, 'CASES', {'tgv2d-bgk': hawa.cases.CASES['tgv2d-bgk']})
    report = parity_worker.run('backport', 'cpu', tmp_path)
    assert report['passed'] and report['cases']['tgv2d-bgk']['steps'] == 50
    with np.load(tmp_path / 'tgv2d-bgk.npz') as data:
        assert len(data.files) == 16
        assert all(np.isfinite(data[key]).all() for key in data.files)
        assert not np.array_equal(data['0_f'], data['50_f'])


def test_parity_orchestrator_uses_separate_interpreters_and_real_comparison(tmp_path, monkeypatch):
    import compare_engines
    commands = []
    import subprocess
    real_run = subprocess.run
    monkeypatch.setattr(compare_engines, 'ROOT', tmp_path)
    monkeypatch.setattr(torch.backends.mps, 'is_available', lambda: False)
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: False)
    monkeypatch.setattr(sys, 'argv', ['compare', '--output', str(tmp_path / 'out'), '--reference-python', 'oracle-python'])
    def worker(command, **kwargs):
        if not isinstance(command, list) or '--output' not in command:
            return real_run(command, **kwargs)
        commands.append(command)
        output = Path(command[command.index('--output')+1]); output.mkdir(parents=True, exist_ok=True)
        device = command[command.index('--device')+1]
        (output / 'metadata.json').write_text(json.dumps(dict(upstream_commit='fixed', dtype=device, cases={'tiny': {}})))
        np.savez(output / 'tiny.npz', f=np.array([1.]))
    monkeypatch.setattr(compare_engines.subprocess, 'run', worker)
    compare_engines.main()
    assert [c[0] for c in commands] == ['oracle-python', sys.executable, 'oracle-python', sys.executable]
    report = json.loads((tmp_path / 'out/report.json').read_text())
    assert report['passed'] and set(report['results']) == {'cpu', 'cpu64'}
    assert all(r['comparisons'][0]['max_abs_error'] == 0 for r in report['results'].values())


@pytest.mark.parametrize('exit_code, expected', [(0, 0), (1, 1)])
def test_example_orchestrator_requires_successful_worker_exit(tmp_path, monkeypatch, exit_code, expected):
    import run_examples
    examples = tmp_path / 'vendor/lettuce/examples'; examples.mkdir(parents=True)
    path = examples / 'nested/example.py'; path.parent.mkdir(); path.write_text('pass')
    monkeypatch.setattr(run_examples, 'ROOT', tmp_path)
    monkeypatch.setattr(run_examples, 'entrypoints', lambda root: [path])
    monkeypatch.setattr(sys, 'argv', ['run_examples', '--output-root', str(tmp_path / 'out')])
    def worker(command, **kwargs):
        assert command[2] == 'nested/example.py'
        output = Path(command[command.index('--output')+1]); output.mkdir(parents=True)
        (output / 'report.json').write_text(json.dumps(dict(source=command[2], status='passed')))
        return SimpleNamespace(returncode=exit_code, stderr='')
    monkeypatch.setattr(run_examples.subprocess, 'run', worker)
    assert run_examples.main() == expected
    report = json.loads((tmp_path / 'out/backport-cpu/report.json').read_text())
    assert report['examples'][0]['status'] == ('passed' if expected == 0 else 'failed')


def test_example_worker_executes_original_source_and_records_cpu_fields(tmp_path, monkeypatch):
    import example_worker
    from matplotlib import pyplot as plt
    source = tmp_path / 'source'; source.mkdir()
    (source / 'tiny.py').write_text('''import lettuce as lt
import torch
flow = lt.TaylorGreenVortex(lt.Context(), resolution=[8,8], reynolds_number=100, mach_number=.05)
simulation = lt.Simulation(flow, lt.BGKCollision(flow.units.relaxation_parameter_lu), [])
simulation(2)
''')
    output = tmp_path / 'out'
    # main is designed for a disposable worker process; restore its adaptations here.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'path', list(sys.path))
    monkeypatch.setattr(sys, 'argv', ['worker', 'tiny.py', '--source-root', str(source), '--output', str(output)])
    for obj, attr in [(np.random, 'seed'), (lt.Context, '__init__'), (lt.Simulation, '__init__'),
                      (lt.Simulation, '__call__'), (lt.BreakableSimulation, '__call__'), (plt, 'show'), (plt, 'savefig')]:
        monkeypatch.setattr(obj, attr, getattr(obj, attr))
    assert example_worker.main() == 0
    report = json.loads((output / 'report.json').read_text())
    assert report['status'] == 'passed' and report['simulations'][0]['iterations'] == 2
    assert report['simulations'][0]['finite']
    with np.load(output / 'fields_0.npz') as data:
        assert set(data.files) == {'f', 'rho', 'u', 'p'}
