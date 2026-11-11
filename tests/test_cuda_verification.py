"""Adversarial orchestration tests; mocked devices are NOT numerical CUDA evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest
import torch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import verification_evidence as evidence
import verify_cuda
import verify_cuda_benchmarks as benchmarks


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root)


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    git(tmp_path, 'config', 'user.name', 'Test')
    (tmp_path / '.gitignore').write_text('results/\n')
    (tmp_path / 'engine.py').write_text('value = 1\n')
    (tmp_path / 'uv.lock').write_text('version = 1\n')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'fixture')
    return tmp_path


@pytest.mark.parametrize('change', ['edit', 'add', 'delete', 'stage', 'lock'])
def test_snapshot_detects_source_inventory_lock_and_index_changes(repository, change):
    before = evidence.snapshot(repository)
    if change == 'edit':
        (repository / 'engine.py').write_text('value = 2\n')
    elif change == 'add':
        (repository / 'test_new.py').write_text('assert True\n')
    elif change == 'delete':
        (repository / 'engine.py').unlink()
    elif change == 'lock':
        (repository / 'uv.lock').write_text('version = 2\n')
    else:
        (repository / 'engine.py').write_text('value = 2\n')
        git(repository, 'add', '.')
        (repository / 'engine.py').write_text('value = 1\n')
    assert before != evidence.snapshot(repository)


def write_evidence(root, name, ids, outcomes=None):
    data = dict(collected=ids, exit_code=0, outcomes=outcomes or [dict(nodeid=i, outcome='passed') for i in ids])
    (root / (name + '.json')).write_text(json.dumps(data))
    suite = ET.Element('testsuite')
    for row in data['outcomes']:
        case = ET.SubElement(suite, 'testcase', classname='tests.test_stub', name=row['nodeid'])
        if row['outcome'] != 'passed':
            ET.SubElement(case, 'skipped' if row['outcome'] == 'skipped' else 'failure')
    ET.ElementTree(suite).write(root / (name + '.xml'))


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'failure', 'skip_cuda', 'collection', 'xml_missing', 'xml_duplicate', 'xml_failure', 'bad_xml'])
def test_complete_inventory_rejects_bad_evidence(tmp_path, fault):
    ids = ['test_a[cpu]', 'test_a[cuda:0]']
    write_evidence(tmp_path, 'expected', ids)
    write_evidence(tmp_path, 'actual', ids)
    p = tmp_path / 'actual.json'
    d = json.loads(p.read_text())
    xml = tmp_path / 'actual.xml'
    if fault == 'missing': d['outcomes'].pop()
    elif fault == 'duplicate': d['outcomes'].append(d['outcomes'][0])
    elif fault == 'failure': d['outcomes'][0]['outcome'] = 'failed'
    elif fault == 'skip_cuda':
        d['outcomes'][1]['outcome'] = 'skipped'
        tree = ET.parse(xml); ET.SubElement(list(tree.getroot())[1], 'skipped'); tree.write(xml)
    elif fault == 'collection': d['collected'].pop()
    elif fault == 'xml_missing': xml.unlink()
    elif fault == 'xml_duplicate':
        tree = ET.parse(xml); tree.getroot().append(list(tree.getroot())[0]); tree.write(xml)
    elif fault == 'xml_failure':
        tree = ET.parse(xml); ET.SubElement(list(tree.getroot())[0], 'failure'); tree.write(xml)
    else: xml.write_text('invalid xml')
    p.write_text(json.dumps(d))
    with pytest.raises((ValueError, OSError, ET.ParseError)):
        evidence.validate_pytest(tmp_path / 'expected.json', p, xml, require_cuda=True)


@pytest.mark.production_python
@pytest.mark.parametrize('fault', [None, 'partial', 'drift', 'bad_xml', 'collection_exit'])
def test_cuda_runner_scrubs_selection_and_fails_closed(repository, monkeypatch, fault):
    import hawa.backends
    monkeypatch.setattr(verify_cuda, 'ROOT', repository)
    monkeypatch.setattr(hawa.backends, 'select_backend', lambda device: SimpleNamespace(info=lambda: {'mock': True}))
    monkeypatch.setattr(torch.cuda, 'get_device_name', lambda index: 'mock orchestration only')
    monkeypatch.setattr(torch.cuda, 'get_device_capability', lambda index: (0, 0))
    monkeypatch.setenv('PYTEST_ADDOPTS', '-k one')
    monkeypatch.setenv('PYTEST_PLUGINS', 'untrusted_selector')
    output = repository / 'results/run'
    monkeypatch.setattr(sys, 'argv', ['verify_cuda', '--output', str(output), '--stages', 'suite', '--repeats', '1'])

    real_run = subprocess.run
    def fake_run(command, **kwargs):
        if command[:3] != [sys.executable, '-m', 'pytest']: return real_run(command, **kwargs)
        assert 'PYTEST_ADDOPTS' not in kwargs['env']
        assert 'PYTEST_PLUGINS' not in kwargs['env']
        assert kwargs['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'
        assert 'addopts=' in command
        target = Path(next(a.split('=', 1)[1] for a in command if a.startswith('--verification-evidence=')))
        ids = ['test_a[cpu]', 'test_a[cuda:0]']
        collecting = '--collect-only' in command
        if fault == 'partial' and not collecting: ids = ids[1:]
        write_evidence(target.parent, target.stem, ids)
        if fault == 'drift': (repository / 'engine.py').write_text('changed')
        if fault == 'bad_xml' and not collecting: target.with_suffix('.xml').write_text('bad')
        return SimpleNamespace(returncode=1 if fault == 'collection_exit' else 0)

    monkeypatch.setattr(verify_cuda.subprocess, 'run', fake_run)
    assert verify_cuda.main() == (0 if fault is None else 1)
    report = json.loads((output / 'report.json').read_text())
    assert report['passed'] == (fault is None)
    assert not report['full_passed'] and not report['full_scope']
    assert (output / 'index.diff').exists()
    with pytest.raises(FileExistsError): verify_cuda.main()


@pytest.mark.parametrize('fault', [None, 'drift', 'numeric'])
def test_benchmark_orchestrator_retains_thresholds_and_hashes_engine(repository, monkeypatch, fault):
    monkeypatch.setattr(benchmarks, '__file__', str(repository / 'scripts/verify_cuda_benchmarks.py'))
    monkeypatch.setattr(benchmarks, 'select_backend', lambda device: None)
    monkeypatch.setattr(torch.cuda, 'get_device_name', lambda index: 'mock orchestration only')
    def benchmark(device, **options):
        if fault == 'drift': (repository / 'engine.py').write_text('changed')
        return dict(max_fluid_population_error=.1 if fault == 'numeric' else 0., max_force_newtons=0.,
                    refined_relative_l2=.1, coarse_relative_l2=.2, relative_mass_drift=0., max_speed=1., torque=1.)
    for name in ('comoving', 'refinement', 'wall', 'rotation'):
        monkeypatch.setattr(benchmarks, name, benchmark)
    path = repository / 'results/benchmarks.json'
    monkeypatch.setattr(sys, 'argv', ['benchmarks', '--output', str(path)])
    assert benchmarks.main() == (0 if fault is None else 1)
    report = json.loads(path.read_text())
    assert len(report['results']) == 13
    assert 'engine.py' in report['source_before']['files']
    assert report['passed'] == (fault is None)
    with pytest.raises(SystemExit): benchmarks.main()


def test_pytest_evidence_hooks_track_teardown_failures_and_duplicate_phases(tmp_path):
    import pytest_evidence as plugin
    parser = SimpleNamespace(addoption=lambda *args, **kwargs: None)
    plugin.pytest_addoption(parser)
    config = SimpleNamespace(getoption=lambda name: str(tmp_path / 'evidence.json'))
    plugin.pytest_configure(config)
    session = SimpleNamespace(config=config, items=[SimpleNamespace(nodeid=i) for i in ['pass', 'skip', 'fail', 'duplicate']])
    plugin.pytest_sessionstart(session); plugin.pytest_collection_finish(session)
    for nodeid in ['pass', 'skip', 'fail', 'duplicate']:
        phases = [('setup', 'skipped' if nodeid == 'skip' else 'passed')]
        if nodeid != 'skip': phases.append(('call', 'passed'))
        phases.append(('teardown', 'failed' if nodeid == 'fail' else 'passed'))
        if nodeid == 'duplicate': phases.append(('call', 'passed'))
        for when, outcome in phases:
            plugin.pytest_runtest_logreport(SimpleNamespace(nodeid=nodeid, when=when, outcome=outcome))
    plugin.pytest_sessionfinish(session, 1)
    report = json.loads((tmp_path / 'evidence.json').read_text())
    assert [row['outcome'] for row in report['outcomes']] == ['passed', 'skipped', 'failed', 'failed']
    assert report['exit_code'] == 1


def test_real_pytest_collection_execution_ignores_config_selectors(tmp_path):
    (tmp_path / 'pytest.ini').write_text('[pytest]\naddopts = -k missing\n')
    (tmp_path / 'test_cases.py').write_text('def test_one(): assert True\ndef test_two(): assert True\n')
    env = evidence.clean_environment()
    env['PYTHONPATH'] = str(SCRIPTS.parent)
    common = [sys.executable, '-m', 'pytest', str(tmp_path), '-o', 'addopts=', '-p', 'scripts.pytest_evidence']
    expected, actual, xml = [tmp_path / name for name in ('expected.json', 'actual.json', 'actual.xml')]
    subprocess.run([*common, '--collect-only', '--verification-evidence=' + str(expected)], env=env, check=True, capture_output=True)
    subprocess.run([*common, '--verification-evidence=' + str(actual), '--junitxml=' + str(xml)], env=env, check=True, capture_output=True)
    assert evidence.validate_pytest(expected, actual, xml)['total'] == 2
