"""Orchestration and saved-array contracts; synthetic workers do not qualify hardware."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def script_imports(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def saved_case(directory, metadata=None, fields=None):
    directory.mkdir(parents=True, exist_ok=True)
    if metadata is None:
        metadata = dict(upstream_commit='pinned', dtype='torch.float32',
                        cases={'flow': {'steps': 50, 'pressure_conversion_scale': 100}})
    (directory / 'metadata.json').write_text(json.dumps(metadata))
    np.savez(directory / 'flow.npz', **(fields if fields is not None else {'50_p': np.array([1., 2.])}))


@pytest.mark.parametrize('mismatch,message', [
    ('upstream_commit', 'upstream commit'), ('dtype', 'Precision'), ('cases', 'Case lists'),
    ('configuration', 'configurations'), ('fields', 'Missing comparison fields')])
def test_parity_comparison_rejects_incompatible_evidence(tmp_path, mismatch, message):
    m = load_script('compare_engines')
    reference, candidate = tmp_path / 'reference', tmp_path / 'candidate'
    saved_case(reference)
    meta = json.loads((reference / 'metadata.json').read_text())
    fields = None
    if mismatch == 'configuration':
        meta['cases']['flow']['steps'] = 49
    elif mismatch == 'fields':
        fields = {'50_rho': np.array([1., 2.])}
    else:
        meta[mismatch] = {} if mismatch == 'cases' else 'different'
    saved_case(candidate, meta, fields)
    with pytest.raises(RuntimeError, match=message):
        m.compare(reference, candidate, 'cpu')


def test_parity_tracks_known_oracle_failures_and_repairs(tmp_path):
    m = load_script('compare_engines')
    reference, candidate = tmp_path / 'reference', tmp_path / 'candidate'
    meta = dict(upstream_commit='pinned', dtype='torch.float32', cases={
        'repaired': {'status': 'known-upstream-error'}, 'unchanged': {'status': 'known-upstream-error'}})
    saved_case(reference, meta)
    meta['cases']['repaired'] = {'steps': 50}
    saved_case(candidate, meta)
    report = m.compare(reference, candidate, 'cpu')
    assert report['repaired_upstream_cases'] == ['repaired']
    assert set(report['known_upstream_errors']) == {'repaired', 'unchanged'}
    assert report['comparisons'] == []


@pytest.mark.parametrize('device,rtol,atol', [('cpu64', 1e-11, 1e-12), ('cpu', 3e-6, 2e-7), ('mps', 3e-4, 2e-4)])
def test_parity_pressure_tolerances_are_explicit_and_enforced(tmp_path, device, rtol, atol):
    m = load_script('compare_engines')
    reference, candidate = tmp_path / 'reference', tmp_path / 'candidate'
    saved_case(reference)
    saved_case(candidate)
    result = m.compare(reference, candidate, device)['comparisons'][0]
    assert result['rtol'] == rtol and result['atol'] == pytest.approx(atol)
    assert result['max_abs_error'] == 0
    np.savez(candidate / 'flow.npz', **{'50_p': np.array([9., 2.])})
    with pytest.raises(AssertionError, match='flow / 50_p'):
        m.compare(reference, candidate, device)


def test_parity_orchestrator_reuses_cpu_oracle_for_accelerators(tmp_path, monkeypatch):
    m = load_script('compare_engines')
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    monkeypatch.setattr(m, 'audit', lambda: {'fixture': 'source-audit-boundary'})
    monkeypatch.setattr(m.torch.backends.mps, 'is_available', lambda: True)
    monkeypatch.setattr(m.torch.cuda, 'is_available', lambda: True)
    monkeypatch.setattr(sys, 'version_info', (3, 9))
    output = tmp_path / 'parity'
    monkeypatch.setattr(sys, 'argv', ['compare', '--output', str(output), '--reference-python', '/fixture/oracle-python'])
    calls = []
    def worker(command, **kwargs):
        calls.append(command)
        assert kwargs['check'] and kwargs['env']['MPLBACKEND'] == 'Agg'
        saved_case(Path(command[command.index('--output') + 1]))
    monkeypatch.setattr(m.subprocess, 'run', worker)
    m.main()
    report = json.loads((output / 'report.json').read_text())
    assert report['passed'] and report['cuda_tested']
    assert set(report['results']) == {'cpu', 'cpu64', 'mps', 'cuda:0'}
    assert len(calls) == 6
    assert [c[c.index('--device') + 1] for c in calls if c[c.index('--role') + 1] == 'upstream'] == ['cpu', 'cpu64']
    assert all(c[0] == '/fixture/oracle-python' for c in calls if c[c.index('--role') + 1] == 'upstream')


def test_parity_orchestrator_rejects_wrong_python_before_audit(tmp_path, monkeypatch):
    m = load_script('compare_engines')
    monkeypatch.setattr(sys, 'version_info', (3, 10))
    monkeypatch.setattr(sys, 'argv', ['compare', '--output', str(tmp_path / 'parity')])
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 2 and not (tmp_path / 'parity').exists()


@pytest.mark.parametrize('outcome,exit_code,status', [('success', 0, 'passed'), ('false-pass', 1, 'failed'), ('no-report', 1, 'failed'), ('timeout', 1, 'timeout')])
def test_reference_example_checkout_full_run_and_failure_reporting(tmp_path, monkeypatch, outcome, exit_code, status):
    m = load_script('run_examples')
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    manifest = tmp_path / 'vendor/lettuce/upstream.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({'commit': 'exact-pinned-commit'}))
    output = tmp_path / 'results'
    monkeypatch.setattr(sys, 'argv', ['run', '--reference', '--full', '--match', 'tiny', '--output-root', str(output)])
    commands = []
    def external(command, **kwargs):
        commands.append(command)
        if command[:2] == ['git', 'clone']:
            checkout = Path(command[-1])
            (checkout / '.git').mkdir(parents=True)
            (checkout / 'examples').mkdir()
            (checkout / 'examples/tiny.py').write_text('print("worker fixture")')
        elif command[0] == 'git':
            assert command[-3:] == ['checkout', '--detach', 'exact-pinned-commit']
        else:
            assert '--full' in command and kwargs['timeout'] is None
            assert kwargs['env']['MPLBACKEND'] == 'Agg'
            destination = Path(command[command.index('--output') + 1])
            if outcome == 'timeout':
                raise subprocess.TimeoutExpired(command, 180)
            if outcome != 'no-report':
                destination.mkdir(parents=True, exist_ok=True)
                (destination / 'report.json').write_text(json.dumps({'source': 'tiny.py', 'status': 'passed'}))
            return SimpleNamespace(returncode=int(outcome != 'success'), stderr='worker stderr')
    monkeypatch.setattr(m.subprocess, 'run', external)
    assert m.main() == exit_code
    record = json.loads((output / 'reference-cpu/report-tiny.json').read_text())
    assert record['profile'] == 'full' and record['examples'][0]['status'] == status
    assert len(commands) == 3
    if outcome == 'false-pass':
        assert record['examples'][0]['error'] == 'Worker exited with code 1'
    if outcome == 'no-report':
        assert record['examples'][0]['error'] == 'worker stderr'
    assert 'venv-reference' in commands[-1][0]


def test_empty_example_selection_does_not_claim_success(tmp_path, monkeypatch):
    m = load_script('run_examples')
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['run', '--match', 'absent', '--output-root', str(tmp_path / 'results')])
    with pytest.raises(SystemExit) as error:
        m.main()
    assert error.value.code == 2
    assert not (tmp_path / 'results').exists()


@pytest.mark.parametrize('script', ['compare_engines', 'run_examples'])
def test_orchestrator_cli_help_has_no_execution_side_effects(script, monkeypatch, capsys):
    import runpy
    monkeypatch.setattr(sys, 'argv', [script, '--help'])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(ROOT / 'scripts' / (script + '.py')), run_name='__main__')
    assert error.value.code == 0
    assert '--output' in capsys.readouterr().out


def test_parity_cli_runs_real_small_cpu_case_and_publishes_metadata(tmp_path, monkeypatch, capsys):
    import runpy
    import hawa.cases as cases
    import torch
    monkeypatch.setattr(cases, 'CASES', {'tgv2d-bgk': cases.CASES['tgv2d-bgk']})
    monkeypatch.setattr(sys, 'path', list(sys.path))
    output = tmp_path / 'parity-cpu'
    monkeypatch.setattr(sys, 'argv', ['parity_worker', '--role', 'backport', '--device', 'cpu', '--output', str(output)])
    prior_threads = torch.get_num_threads()
    try:
        runpy.run_path(str(ROOT / 'scripts/parity_worker.py'), run_name='__main__')
    finally:
        torch.set_num_threads(prior_threads)
    metadata = json.loads((output / 'metadata.json').read_text())
    assert metadata['passed'] and metadata['device'] == 'cpu'
    assert metadata['engine_distribution'] == 'hawa-lettuce'
    assert metadata['cases']['tgv2d-bgk']['steps'] == 50
    assert json.loads(capsys.readouterr().out)['cases'] == metadata['cases']
    with np.load(output / 'tgv2d-bgk.npz') as arrays:
        assert len(arrays.files) == 16
        assert all(np.isfinite(arrays[name]).all() for name in arrays.files)
        assert (arrays['50_rho'] > 0).all()
        assert np.linalg.norm(arrays['50_u']) < np.linalg.norm(arrays['0_u'])
