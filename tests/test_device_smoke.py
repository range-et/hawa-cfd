"""Device smoke gate contracts (#57); real builders run on CPU only.

CPU runs here exercise the gate's comparison, guard and manifest logic and its
CPU FP32 proxy. They are not CUDA or MPS evidence.
"""
import copy
import importlib.util
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import time

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
try:
    import device_smoke as smoke
    IMPORT_ERROR = None
except (Exception, SystemExit) as error:  # mutmut 2.4.5 counts a collection error (exit 2) as a survivor.
    IMPORT_ERROR = error


@pytest.fixture(autouse=True)
def importable():
    if IMPORT_ERROR is not None:
        pytest.fail('scripts/device_smoke.py failed to import: {!r}'.format(IMPORT_ERROR))


def fixture_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tests' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bounded(name='values', pattern='.', rtol=0., atol=0., **extra):
    return dict(name=name, **{'class': 'bounded'}, pattern=pattern, rtol=rtol, atol=atol, **extra)


def bitwise(name='bits', pattern='.'):
    return dict(name=name, **{'class': 'bitwise'}, pattern=pattern)


def test_committed_policy_declares_existing_inputs_and_unwidened_tolerances():
    policy = smoke.load_policy(smoke.POLICY)
    cases = policy['cases']
    declared = {(name, c['name']): (c['class'], c.get('rtol'), c.get('atol'), c.get('atol_scale'))
                for name, case in cases.items() for c in case['checks']}
    assert declared == {
        ('engine-2d', 'populations-density-velocity'): ('bounded', 3e-4, 2e-6, None),
        ('engine-2d', 'pressure'): ('bounded', 3e-4, 2e-6, 'pressure_conversion_scale'),
        ('kbc-near-equilibrium', 'post-collision-populations'): ('bitwise', None, None, None),
        ('neutral-shifted-regularized', 'velocity'): ('bounded', 3e-4, 3e-5, None),
        ('neutral-shifted-regularized', 'relative-mass-change'): ('bounded', 0., 1e-6, None),
        ('moving-sphere', 'solid-mask'): ('bitwise', None, None, None),
        ('moving-sphere', 'populations'): ('bounded', 3e-4, 3e-6, None),
        ('curved-wall-channel', 'max-speed'): ('bounded', 3e-4, 2e-6, None)}
    # The inputs are the existing criteria's own fixtures, not new cases.
    assert cases['neutral-shifted-regularized']['params'] == dict(steps=100, spec=fixture_module('test_neutral').case(10.))
    assert cases['moving-sphere']['params'] == dict(steps=12, spec=fixture_module('test_motion').moving_case())
    assert cases['kbc-near-equilibrium']['params'] == dict(sizes=[1, 8], populations=fixture_module('test_kbc_precision').POPULATIONS)
    from hawa.cases import CASES
    assert set(cases['engine-2d']['params']['cases']) < set(CASES)
    assert cases['curved-wall-channel']['params'] == dict(n=8, q=[.25, .75])
    assert all(case['unsupported'] == {} for case in cases.values())


def test_bitwise_compares_rounded_reference_bits():
    reference = np.array([1/3, 2., 0.], np.float64)
    exact = reference.astype(np.float32)
    assert smoke.compare(bitwise(), {'a': reference}, {'a': exact}, {})['passed']
    one_ulp = exact.copy()
    one_ulp[0] = np.nextafter(one_ulp[0], np.float32(1))
    signed = exact.copy()
    signed[2] = -0.
    for candidate in (one_ulp, signed):
        row = smoke.compare(bitwise(), {'a': reference}, {'a': candidate}, {})['arrays'][0]
        assert row['mismatches'] == 1 and row['passed'] is False
        assert (row['reference_dtype'], row['candidate_dtype'], row['shape']) == ('float64', 'float32', [3])
    mask = np.array([[True, False], [False, True]])
    flipped = mask.copy()
    flipped[1, 0] = True
    result = smoke.compare(bitwise('mask'), {'m': mask}, {'m': flipped}, {})
    assert result['arrays'][0]['mismatches'] == 1 and result['passed'] is False
    assert result['name'] == 'mask' and result['comparison_class'] == 'bitwise'
    shape = smoke.compare(bitwise(), {'a': reference}, {'a': exact[:2]}, {})['arrays'][0]
    assert shape['passed'] is False and shape['error'] == 'Shape differs from reference [3]'


def test_bounded_uses_reference_magnitude_inclusive_limit_and_named_scale():
    check = bounded(rtol=.1, atol=.5)
    reference = np.array([10., 0.])
    # Limits are 0.5 + 0.1 * |reference|: exactly at the limit passes.
    assert smoke.compare(check, {'a': reference}, {'a': reference + [1.5, .5]}, {})['passed']
    # A candidate-relative limit would accept 12 (0.5 + 1.2 >= 2); the reference limit does not.
    row = smoke.compare(check, {'a': reference}, {'a': reference + [2., 0.]}, {})['arrays'][0]
    assert row == dict(array='a', reference_dtype='float64', candidate_dtype='float64', shape=[2],
                       rtol=.1, atol=.5, violations=1, max_abs_error=2., passed=False)
    scaled = bounded(rtol=0., atol=2e-6, atol_scale='pressure_conversion_scale')
    config = {'p': dict(pressure_conversion_scale=400.)}
    within = smoke.compare(scaled, {'p': np.zeros(1)}, {'p': np.full(1, 7.9e-4)}, config)
    assert within['passed'] and within['arrays'][0]['atol'] == pytest.approx(8e-4)
    assert not smoke.compare(scaled, {'p': np.zeros(1)}, {'p': np.full(1, 8.1e-4)}, config)['passed']
    nonfinite = smoke.compare(check, {'a': reference}, {'a': np.array([np.nan, 0.])}, {})['arrays'][0]
    assert nonfinite['max_abs_error'] == 'nonfinite' and nonfinite['violations'] == 1


def test_evaluate_requires_matching_inventory_and_one_owner_per_array():
    arrays = {'x/0_rho': np.ones(2), 'x/0_p': np.zeros(2)}
    checks = [bounded('density', '_rho$'), bounded('pressure', '_p$')]
    results = smoke.evaluate(checks, arrays, copy.deepcopy(arrays), {}, {})
    assert [(r['name'], [a['array'] for a in r['arrays']]) for r in results] == [
        ('density', ['x/0_rho']), ('pressure', ['x/0_p'])]
    with pytest.raises(ValueError, match=r"^Reference and candidate arrays differ: \['x/0_p'\]$"):
        smoke.evaluate(checks, arrays, {'x/0_rho': np.ones(2)}, {}, {})
    with pytest.raises(ValueError, match='^Reference and candidate case configurations differ$'):
        smoke.evaluate(checks, arrays, arrays, {'x/0_p': {'tau': 1}}, {'x/0_p': {'tau': 2}})
    with pytest.raises(ValueError, match='^Arrays need exactly one declared check: x/0_p, x/0_rho$'):
        smoke.evaluate([bounded('all', '.'), bounded('again', 'x')], arrays, arrays, {}, {})
    with pytest.raises(ValueError, match='^Arrays need exactly one declared check: x/0_p$'):
        smoke.evaluate([bounded('density', 'rho$')], arrays, arrays, {}, {})
    with pytest.raises(ValueError, match='^Check selects no arrays: unused$'):
        smoke.evaluate(checks + [bounded('unused', 'never')], arrays, arrays, {}, {})


def policy_with(**cases):
    return dict(schema=1, cases=cases)


def case(builder='fake', checks=None, **extra):
    return dict(builder=builder, criterion_source='fixture', params={}, checks=checks or [bounded()], **extra)


@pytest.mark.parametrize('change,message', [
    (lambda p: p.update(schema=2), '^Policy requires schema 1 and at least one case$'),
    (lambda p: p.update(cases={}), '^Policy requires schema 1 and at least one case$'),
    (lambda p: p['cases']['c'].update(builder='unknown'), '^c: requires a known builder, checks and a criterion source$'),
    (lambda p: p['cases']['c'].update(checks=[]), '^c: requires a known builder, checks and a criterion source$'),
    (lambda p: p['cases']['c'].pop('criterion_source'), '^c: requires a known builder, checks and a criterion source$'),
    (lambda p: p['cases']['c']['checks'][0].update({'class': 'statistical'}), '^c: comparison class must be one of bitwise, bounded$'),
    (lambda p: p['cases']['c']['checks'][0].pop('atol'), '^c: bounded checks require finite nonnegative rtol and atol$'),
    (lambda p: p['cases']['c']['checks'][0].update(rtol=-1e-9), '^c: bounded checks require finite nonnegative rtol and atol$'),
    (lambda p: p['cases']['c']['checks'][0].update(atol=float('inf')), '^c: bounded checks require finite nonnegative rtol and atol$'),
    (lambda p: p['cases']['c']['checks'][0].update(atol='0.1'), '^c: bounded checks require finite nonnegative rtol and atol$'),
    (lambda p: p['cases']['c'].update(checks=[dict(bitwise(), rtol=0.)]), '^c: bitwise checks take no tolerance$'),
    (lambda p: p['cases']['c'].update(unsupported={'xpu': dict(exception='E', match='m')}), '^c: an unsupported device needs its guard exception and message$'),
    (lambda p: p['cases']['c'].update(unsupported={'mps': dict(exception='E')}), '^c: an unsupported device needs its guard exception and message$'),
    (lambda p: p['cases']['c'].update(unsupported={'mps': dict(match='m')}), '^c: an unsupported device needs its guard exception and message$'),
])
def test_policy_rejects_undeclared_classes_tolerances_and_guards(tmp_path, monkeypatch, change, message):
    monkeypatch.setitem(smoke.BUILDERS, 'fake', None)
    policy = policy_with(c=case())
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps(policy))
    assert smoke.load_policy(path) == policy
    change(policy)
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError, match=message):
        smoke.load_policy(path)


def test_policy_accepts_declared_guard_and_bitwise_check(tmp_path, monkeypatch):
    monkeypatch.setitem(smoke.BUILDERS, 'fake', None)
    policy = policy_with(c=case(checks=[bitwise()], unsupported={'mps': dict(exception='E', match='m')}))
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps(policy))
    assert smoke.load_policy(path) == policy


class Builder:
    """Records calls and seeds; returns exact or perturbed arrays."""

    def __init__(self, offset=0., fail=None, fail_reference=False):
        self.calls, self.seeds = [], []
        self.offset, self.fail, self.fail_reference = offset, fail, fail_reference

    def __call__(self, device, reference, params, directory):
        self.calls.append((device, reference, params, directory.name))
        self.seeds.append((torch.initial_seed(), np.random.get_state()[1][0]))
        torch.manual_seed(99)
        np.random.seed(99)
        if reference and self.fail_reference:
            raise RuntimeError('reference fixture failure')
        if not reference and self.fail is not None:
            raise self.fail
        return {'x/values': np.array([1., 2.]) + (0 if reference else self.offset)}, {'x/values': dict(scale=1)}


def run(monkeypatch, tmp_path, builder, device='cpu', **extra):
    monkeypatch.setitem(smoke.BUILDERS, 'fake', builder)
    return smoke.run_case('c', case(checks=[bounded(atol=.1)], **extra), device, tmp_path / 'case')


def test_case_runs_cpu_fp64_reference_then_seeded_candidate(monkeypatch, tmp_path):
    builder = Builder(offset=.05)
    before = time.perf_counter()
    record = run(monkeypatch, tmp_path, builder, 'cuda:0')
    elapsed = time.perf_counter() - before
    assert record['status'] == 'pass' and record['id'] == 'c' and record['builder'] == 'fake'
    assert record['criterion_source'] == 'fixture'
    assert builder.calls == [('cpu', True, {}, 'reference'), ('cuda:0', False, {}, 'candidate')]
    assert builder.seeds == [(0, 0), (0, 0)]
    assert 0 <= record['reference_seconds'] <= elapsed and 0 <= record['candidate_seconds'] <= elapsed
    assert record['checks'][0]['arrays'][0]['violations'] == 0
    for name, offset in (('reference', 0), ('candidate', .05)):
        with np.load(tmp_path / 'case' / (name + '.npz')) as saved:
            np.testing.assert_array_equal(saved['x/values'], np.array([1., 2.]) + offset)


def test_case_fails_outside_tolerance_or_when_any_run_fails(monkeypatch, tmp_path):
    record = run(monkeypatch, tmp_path / 'a', Builder(offset=.2))
    assert record['status'] == 'fail' and record['checks'][0]['arrays'][0]['violations'] == 2
    record = run(monkeypatch, tmp_path / 'b', Builder(fail_reference=True))
    assert record['status'] == 'fail' and record['error'] == 'RuntimeError: reference fixture failure'
    record = run(monkeypatch, tmp_path / 'c', Builder(fail=RuntimeError('device fixture failure')))
    assert record['status'] == 'fail' and record['error'] == 'RuntimeError: device fixture failure'
    assert 'candidate_seconds' in record and record['checks'] == []


def test_only_the_declared_runtime_guard_is_unsupported_guarded(monkeypatch, tmp_path):
    guard = {'mps': dict(exception='ValueError', match='MPS does not support')}
    refused = Builder(fail=ValueError('MPS does not support float64; select float32'))
    before = time.perf_counter()
    record = run(monkeypatch, tmp_path / 'a', refused, 'mps', unsupported=guard)
    assert 0 <= record['candidate_seconds'] <= time.perf_counter() - before
    assert record['status'] == 'unsupported-guarded' and record['checks'] == []
    assert record['guard'] == 'ValueError: MPS does not support float64; select float32'
    for name, failure in (('b', RuntimeError('MPS does not support float64')), ('c', ValueError('other message'))):
        record = run(monkeypatch, tmp_path / name, Builder(fail=failure), 'mps', unsupported=guard)
        assert record['status'] == 'fail' and record['error'].endswith(str(failure))
    record = run(monkeypatch, tmp_path / 'd', Builder(), 'mps', unsupported=guard)
    assert record['status'] == 'fail'
    assert record['error'] == 'RuntimeError: Declared unsupported on this device, but no runtime guard refused it'
    # A guard declared for MPS never excuses another device.
    record = run(monkeypatch, tmp_path / 'e', Builder(fail=ValueError('MPS does not support')), 'cuda:0',
                 unsupported=guard)
    assert record['status'] == 'fail'
    assert run(monkeypatch, tmp_path / 'f', Builder(), 'cpu', unsupported=guard)['status'] == 'pass'


def test_command_returns_output_or_none():
    assert smoke.command([sys.executable, '-c', 'print(" value ")']) == 'value'
    assert smoke.command([sys.executable, '-c', 'raise SystemExit(3)']) is None
    assert smoke.command([str(ROOT / 'no-such-tool')]) is None


def test_environment_describes_the_requested_device(monkeypatch):
    calls = []
    monkeypatch.setattr(smoke, 'command', lambda arguments: calls.append(arguments) or 'answer')
    monkeypatch.setenv('OMP_NUM_THREADS', '1')
    common = {'os', 'machine', 'processor', 'python', 'executable', 'torch', 'numpy', 'torch_threads', 'variables'}
    cpu = smoke.environment('cpu')
    assert set(cpu) == common and calls == []
    assert set(cpu['variables']) == {'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'PYTORCH_ENABLE_MPS_FALLBACK',
                                     'CUDA_VISIBLE_DEVICES'}
    assert cpu['variables']['OMP_NUM_THREADS'] == '1' and cpu['torch'] == torch.__version__
    monkeypatch.setattr(smoke.torch.cuda, 'get_device_name', lambda index: 'GPU {}'.format(index))
    monkeypatch.setattr(smoke.torch.cuda, 'get_device_capability', lambda index: (12, index))
    monkeypatch.setattr(smoke.torch.version, 'cuda', '12.8')
    cuda = smoke.environment('cuda:0')
    assert {k: cuda[k] for k in set(cuda) - common} == dict(cuda_runtime='12.8', gpu='GPU 0', capability=[12, 0],
                                                         driver='answer')
    assert calls == [['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader']]
    monkeypatch.setattr(smoke.platform, 'mac_ver', lambda: ('27.0.1', ('', '', ''), 'arm64'))
    mps = smoke.environment('mps')
    assert {k: mps[k] for k in set(mps) - common} == dict(macos='27.0.1', mac_model='answer', chip='answer')
    assert calls[1:] == [['sysctl', '-n', 'hw.model'], ['sysctl', '-n', 'machdep.cpu.brand_string']]


def test_provenance_records_commit_dirty_state_and_source_digest(tmp_path):
    def git(*arguments):
        return subprocess.check_output(['git', *arguments], cwd=tmp_path, text=True).strip()
    git('init', '-q')
    (tmp_path / 'a.py').write_text('x = 1\n')
    git('add', 'a.py')
    git('-c', 'user.name=t', '-c', 'user.email=t@example.com', 'commit', '-qm', 'fixture')
    clean = smoke.provenance(tmp_path)
    assert clean['commit'] == git('rev-parse', 'HEAD') and clean['dirty'] is False
    assert clean['status'] == [] and clean['files'] == 1 and len(clean['source_sha256']) == 64
    (tmp_path / 'a.py').write_text('x = 2\n')
    dirty = smoke.provenance(tmp_path)
    assert dirty['dirty'] is True and dirty['status'] == [' M a.py']
    assert dirty['source_sha256'] != clean['source_sha256'] and dirty['index_sha256'] == clean['index_sha256']


@pytest.fixture
def fake_run(monkeypatch, tmp_path):
    """A two-case policy with fake builders and fixed provenance."""
    monkeypatch.setitem(smoke.BUILDERS, 'fake', Builder())
    monkeypatch.setitem(smoke.BUILDERS, 'guarded', Builder(fail=ValueError('declared guard')))
    policy = policy_with(first=case(checks=[bounded(atol=.1)]),
                         second=case('guarded', unsupported={'cpu': dict(exception='ValueError', match='declared')}))
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps(policy))
    states = [dict(commit='c', dirty=False), dict(commit='c', dirty=False)]
    monkeypatch.setattr(smoke, 'provenance', lambda: states.pop(0))
    monkeypatch.setattr(smoke, 'environment', lambda device: dict(device=device))
    threads = torch.get_num_threads()
    yield path, states
    torch.set_num_threads(threads)  # main() pins one thread for the rest of its process.


def test_main_writes_manifest_without_counting_guarded_cases_as_passes(fake_run, tmp_path, capsys, monkeypatch):
    path, _ = fake_run
    output = tmp_path / 'new' / 'run'
    arguments = ['--device', 'cpu', '--output', str(output), '--overlapping-jobs', 'none', '--policy', str(path)]
    monkeypatch.setenv('PYTORCH_ENABLE_MPS_FALLBACK', '1')  # Refused only for MPS runs.
    before = time.perf_counter()
    assert smoke.main(arguments) == 0
    elapsed = time.perf_counter() - before
    text = (output / 'manifest.json').read_text()
    manifest = json.loads(text)
    assert text == json.dumps(manifest, indent=2) + '\n'
    assert manifest['result'] == 'pass' and manifest['source_unchanged'] is True
    assert manifest['counts'] == {'pass': 1, 'fail': 0, 'unsupported-guarded': 1}
    assert [(c['id'], c['status']) for c in manifest['cases']] == [('first', 'pass'), ('second', 'unsupported-guarded')]
    assert manifest['device'] == 'cpu' and manifest['torch_device'] == 'cpu' and manifest['environment'] == {'device': 'cpu'}
    assert manifest['backend']['selected'] == 'cpu' and manifest['seeds'] == {'torch': 0, 'numpy': 0}
    assert manifest['reference'] == {'device': 'cpu', 'dtype': 'float64'} and manifest['candidate_dtype'] == 'float32'
    assert manifest['overlapping_jobs'] == 'none' and manifest['source_before'] == {'commit': 'c', 'dirty': False}
    assert manifest['policy'] == dict(path=str(path), sha256=smoke.hashlib.sha256(path.read_bytes()).hexdigest())
    assert manifest['schema'] == 1 and manifest['tool'] == 'scripts/device_smoke.py'
    assert 0 <= manifest['seconds'] <= elapsed
    assert manifest['started_utc'] <= manifest['finished_utc'] and torch.get_num_threads() == 1
    with np.load(output / 'cases/first/candidate.npz') as saved:
        np.testing.assert_array_equal(saved['x/values'], [1., 2.])
    lines = capsys.readouterr().out.splitlines()
    assert lines[:4] == ['first: running', 'first: pass ', 'second: running', 'second: unsupported-guarded ']
    assert lines[4] == 'Device smoke cpu: pass ({})'.format(output.resolve() / 'manifest.json')
    with pytest.raises(FileExistsError):
        smoke.main(arguments)


def test_main_fails_on_source_drift_or_failed_case(fake_run, tmp_path, monkeypatch, capsys):
    path, states = fake_run
    states[1] = dict(commit='c', dirty=True)
    arguments = ['--device', 'cpu', '--overlapping-jobs', 'none', '--policy', str(path)]
    assert smoke.main(arguments + ['--output', str(tmp_path / 'drift')]) == 1
    manifest = json.loads((tmp_path / 'drift/manifest.json').read_text())
    assert manifest['result'] == 'fail' and manifest['source_unchanged'] is False
    assert manifest['counts']['fail'] == 0
    states.extend([dict(commit='c'), dict(commit='c')])
    monkeypatch.setitem(smoke.BUILDERS, 'fake', Builder(fail=RuntimeError('device fixture failure')))
    capsys.readouterr()
    assert smoke.main(arguments + ['--output', str(tmp_path / 'failed')]) == 1
    manifest = json.loads((tmp_path / 'failed/manifest.json').read_text())
    assert manifest['result'] == 'fail' and manifest['counts']['fail'] == 1 and manifest['source_unchanged']
    assert 'first: fail RuntimeError: device fixture failure' in capsys.readouterr().out.splitlines()


def test_interrupted_run_leaves_an_incomplete_manifest(fake_run, tmp_path, monkeypatch):
    path, _ = fake_run
    def interrupt(*arguments):
        raise KeyboardInterrupt
    monkeypatch.setattr(smoke, 'run_case', interrupt)
    with pytest.raises(KeyboardInterrupt):
        smoke.main(['--device', 'cpu', '--output', str(tmp_path / 'run'), '--overlapping-jobs', 'none',
                    '--policy', str(path)])
    manifest = json.loads((tmp_path / 'run/manifest.json').read_text())
    assert manifest['result'] == 'incomplete' and manifest['cases'] == [] and 'counts' not in manifest


@pytest.mark.parametrize('omitted', ['--device', '--output', '--overlapping-jobs'])
def test_main_requires_device_output_and_overlapping_jobs_statement(tmp_path, capsys, omitted):
    values = {'--device': 'cpu', '--output': str(tmp_path / 'never'), '--overlapping-jobs': 'none'}
    arguments = [part for name, value in values.items() if name != omitted for part in (name, value)]
    with pytest.raises(SystemExit) as exit_info:
        smoke.main(arguments)
    assert exit_info.value.code == 2 and omitted in capsys.readouterr().err
    assert not (tmp_path / 'never').exists()


@pytest.mark.parametrize('arguments,environment,message', [
    (['--device', 'cpu', '--overlapping-jobs', '  '], {}, 'State the overlapping jobs, or "none"$'),
    (['--device', 'mps', '--overlapping-jobs', 'none'], {'PYTORCH_ENABLE_MPS_FALLBACK': '1'},
     'Unset PYTORCH_ENABLE_MPS_FALLBACK; CPU fallback would hide MPS results$'),
    (['--device', 'cpu', '--overlapping-jobs', 'none', '--policy', 'missing.json'], {},
     r'Invalid policy: \[Errno 2\] '),
])
def test_main_rejects_unstated_jobs_mps_fallback_and_invalid_policy(tmp_path, monkeypatch, capsys,
                                                                    arguments, environment, message):
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exit_info:
        smoke.main(arguments + ['--output', str(tmp_path / 'never')])
    assert exit_info.value.code == 2 and re.search(': error: ' + message, capsys.readouterr().err.splitlines()[-1])
    assert not (tmp_path / 'never').exists()


def test_script_help_runs_without_creating_outputs(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['device_smoke.py', '--help'])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(ROOT / 'scripts/device_smoke.py'), run_name='__main__')
    text = ' '.join(capsys.readouterr().out.split())
    assert exit_info.value.code == 0 and text.endswith(
        '--output OUTPUT New evidence directory --overlapping-jobs OVERLAPPING_JOBS '
        'Other work running on this machine during the run, or "none" --policy POLICY')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('name,device', [('cpu', 'cpu'), ('cuda', 'cuda:0'), ('mps', 'mps')])
def test_main_probes_the_requested_torch_device_before_writing(tmp_path, monkeypatch, name, device):
    import hawa.backends
    def refuse(requested):
        raise RuntimeError('probe ' + requested)
    monkeypatch.setattr(hawa.backends, 'select_backend', refuse)
    monkeypatch.delenv('PYTORCH_ENABLE_MPS_FALLBACK', raising=False)
    with pytest.raises(RuntimeError, match='^probe {}$'.format(device)):
        smoke.main(['--device', name, '--output', str(tmp_path / 'never'), '--overlapping-jobs', 'none'])
    assert not (tmp_path / 'never').exists()


def test_kbc_builder_reproduces_the_existing_precision_fixture():
    import lettuce as lt
    params = smoke.load_policy(smoke.POLICY)['cases']['kbc-near-equilibrium']['params']
    for reference, dtype in ((True, torch.float64), (False, torch.float32)):
        arrays, config = smoke.kbc('cpu', reference, params, None)
        assert config == {}
        for size in (1, 8):
            # Construction copied from tests/test_kbc_precision.py.
            flow = lt.TaylorGreenVortex(lt.Context('cpu', dtype, use_native=False), [8, 8], 10, .05)
            flow.units = lt.UnitConversion(reynolds_number=lt.D2Q9.cs*.05*512/(1/6),
                                           mach_number=.05, characteristic_length_lu=1)
            flow.f = torch.tensor(params['populations'], dtype=torch.float32).to(dtype)[:, None, None].expand(
                -1, size, size).clone()
            expected = lt.KBCCollision()(flow).numpy()
            assert arrays['size-{}/populations'.format(size)].dtype == expected.dtype
            np.testing.assert_array_equal(arrays['size-{}/populations'.format(size)], expected)


def test_neutral_reference_reports_relative_mass_change(monkeypatch):
    import hawa.neutral
    class Flow:
        def __init__(self):
            self.mass = 2.
            self.u_pu = torch.zeros(1)
        def rho(self):
            return torch.tensor([self.mass])
    flow = Flow()
    def make(spec, context):
        assert context.dtype == torch.float64 and context.device.type == 'cpu'
        return flow, lambda steps: setattr(flow, 'mass', 2. + steps)
    monkeypatch.setattr(hawa.neutral, 'make', make)
    arrays, config = smoke.neutral('cpu', True, dict(spec={}, steps=1), None)
    assert arrays['relative_mass_change'] == .5 and config == {}


def test_real_builders_pass_their_criteria_on_the_cpu_proxy(tmp_path):
    """Reduced real runs: FP64 reference arrays and FP32 candidate arrays differ only within policy."""
    policy = smoke.load_policy(smoke.POLICY)['cases']
    reduced = dict(engine=dict(cases=['poiseuille2d-guo']),
                   kbc=policy['kbc-near-equilibrium']['params'],
                   neutral=dict(policy['neutral-shifted-regularized']['params'], steps=5),
                   moving=dict(policy['moving-sphere']['params'], steps=2),
                   wall=dict(n=4, q=[.25]))
    names = {case['builder']: name for name, case in policy.items()}
    expected_arrays = dict(engine={'poiseuille2d-guo/{}_{}'.format(step, field) for step in (0, 1, 10, 50)
                                   for field in ('f', 'rho', 'u', 'p')},
                           kbc={'size-1/populations', 'size-8/populations'},
                           neutral={'velocity', 'relative_mass_change'},
                           moving={'populations', 'solid'}, wall={'q-0.25/max_speed'})
    configs = {}
    for builder, params in reduced.items():
        reference, reference_config = smoke.BUILDERS[builder]('cpu', True, params, tmp_path / builder / 'r')
        candidate, candidate_config = smoke.BUILDERS[builder]('cpu', False, params, tmp_path / builder / 'c')
        assert set(reference) == set(candidate) == expected_arrays[builder]
        for name, array in reference.items():
            assert array.dtype in (np.float64, np.bool_), name
            assert candidate[name].dtype in ((np.float32, np.bool_) if np.ndim(array) else (np.float64,)), name
        results = smoke.evaluate(policy[names[builder]]['checks'], reference, candidate,
                                 reference_config, candidate_config)
        assert all(result['passed'] for result in results), builder
        configs[builder] = reference_config
    # Only the stored-precision path differs: FP64 and FP32 channel speeds are not identical.
    wall_reference, _ = smoke.wall('cpu', True, reduced['wall'], tmp_path)
    wall_candidate, _ = smoke.wall('cpu', False, reduced['wall'], tmp_path)
    assert wall_reference['q-0.25/max_speed'] != wall_candidate['q-0.25/max_speed']
    assert configs['engine']['poiseuille2d-guo/50_p']['pressure_conversion_scale'] > 0
    # Undeclared (excluded) compatibility cases are never run.
    for side in ('r', 'c'):
        assert sorted(p.name for p in (tmp_path / 'engine' / side).iterdir()) == ['metadata.json', 'poiseuille2d-guo.npz']
        metadata = json.loads((tmp_path / 'engine' / side / 'metadata.json').read_text())
        assert list(metadata['cases']) == ['poiseuille2d-guo']
    # Existing benchmark callers keep the CPU FP32 defaults.
    from benchmark_curved_walls import run as channel
    assert channel(4, .25) == channel(4, .25, 'cpu', torch.float32)
