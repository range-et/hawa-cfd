"""Assertion-driven control-plane tests; Rhino adapter behavior needs live evidence."""
import importlib.util
import json
from pathlib import Path
import threading
import types
import sys

import pytest

SPEC = importlib.util.spec_from_file_location("host_acceptance", Path(__file__).parents[1] / "scripts/host_acceptance.py")
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)


@pytest.fixture
def run(tmp_path):
    root = tmp_path / 'repo'
    source = root / 'examples/grasshopper'
    source.mkdir(parents=True)
    for n in (31, 32):
        (source / ('%s-example.gh' % n)).write_bytes(b'archive')
    return host.create(root, tmp_path / 'run', timeout=10, now=100, document=8)


def ack(state, **values):
    return dict(run_id=state['run_id'], sequence=state['sequence'], phase=state['phase'], **values)


def step(state, **values):
    return host.advance(state, ack(state, **values), now=101)


def started(run):
    s = step(run, safe=True, rhino_serial=8, original_gh='user-doc')
    s = step(s, owned='owned')
    s = step(s, ready=True)
    return step(s)


def test_complete_two_examples_with_polling_and_cleanup(run):
    s = started(run)
    for i in (0, 1):
        assert s['phase'] == 'observe' and s['index'] == i
        assert step(s, passed=False)['phase'] == 'observe'
        s = step(s, passed=True, outputs={'valid': True})
        assert s['phase'] == 'close'
        s = step(s)
        assert step(s, clean=False)['phase'] == 'cleanup'
        s = step(s, clean=True)
        assert s['owned'] is None
        if i == 0:
            s = step(s, owned='next')
            assert step(s, ready=False)['phase'] == 'prepare'
            s = step(step(s, ready=True))
    assert s['status'] == 'passed' and len(s['results']) == 2
    assert s['original_gh'] == 'user-doc'
    with pytest.raises(ValueError, match='terminal'):
        step(s)


def test_preflight_refuses_user_work_and_old_ack(run):
    assert step(run, safe=False)['status'] == 'blocked'
    with pytest.raises(ValueError, match='stale'):
        host.advance(run, ack(run) | {'sequence': -1}, now=101)
    assert step(run, error='host not loaded')['status'] == 'failed'


def test_deadlines_do_not_reset_on_waits_and_cleanup_has_own_deadline(run):
    s = started(run)
    waiting = host.advance(s, ack(s, passed=False), now=108)
    assert waiting['deadline'] == s['deadline']
    timeout = host.advance(waiting, None, now=111)
    assert timeout['phase'] == 'close' and timeout['failure'] == 'Timeout in observe'
    assert timeout['deadline'] == 121
    assert host.advance(timeout, None, now=121)['status'] == 'blocked'
    closed = host.advance(timeout, ack(timeout), now=112)
    assert host.advance(closed, None, now=122)['status'] == 'blocked'
    assert host.advance(closed, ack(closed, clean=True), now=113)['status'] == 'failed'


def test_cancel_missing_response_recovers_owned_and_does_not_claim_pass(run):
    opening = step(run, safe=True, rhino_serial=8, original_gh=None)
    with pytest.raises(ValueError, match='pending'):
        host.advance(opening, None, now=101)
    lost = host.advance(opening, None, now=101, cancel=True, recovered_owned='durable-id')
    assert lost['owned'] == 'durable-id' and lost['phase'] == 'close'
    assert step(step(lost), clean=True)['status'] == 'failed'
    partial = step(opening, owned='created-before-error', error='open failed')
    assert partial['phase'] == 'close' and partial['owned'] == 'created-before-error'
    assert host.advance(run, None, now=101, cancel=True)['status'] == 'failed'


def test_failure_and_bad_state_are_explicit(run):
    s = started(run)
    assert step(s, error='bad mesh')['phase'] == 'close'
    assert step(step(s, passed=True), error='close failed')['status'] == 'blocked'
    s['phase'] = 'invalid'
    with pytest.raises(ValueError, match='Unknown phase'):
        step(s)


def test_create_unique_copies_hashes_and_publish_terminal(run):
    output = Path(run['output'])
    assert (output / 'request.cs').exists() and '__REQUEST_BASE64__' not in (output / 'request.cs').read_text()
    assert (output / 'audit.py').exists()
    assert all(len(v) == 64 for v in run['source_hashes'].values())
    with pytest.raises(FileExistsError):
        host.create(run['root'], output, document=8)
    for timeout in (0, -1, 3601, float('nan')):
        with pytest.raises(ValueError):
            host.create(run['root'], output / 'invalid', timeout, document=8)
    run['status'] = 'passed'
    host.publish(run)
    assert not (output / 'request.cs').exists() and not (output / 'audit.py').exists()
    assert json.loads((output / 'state.json').read_text())['status'] == 'passed'


def test_cli_poll_missing_cancel_and_wrong_owner(run, monkeypatch, capsys):
    output = Path(run['output'])
    monkeypatch.setattr(host.time, 'time', lambda: 101)
    with pytest.raises(ValueError, match='pending'):
        host.main(['poll', '--output', str(output)])
    (output / 'ownership.json').write_text(json.dumps(dict(run_id='wrong', owned='x')))
    with pytest.raises(ValueError, match='ownership'):
        host.main(['poll', '--output', str(output), '--cancel'])
    (output / 'ownership.json').unlink()
    assert host.main(['poll', '--output', str(output), '--cancel']) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'failed'


def test_cli_start_reply_and_durable_owner(run, monkeypatch, capsys):
    monkeypatch.setattr(host.time, 'time', lambda: 100)
    output = Path(run['output']).with_name('second')
    assert host.main(['start', '--root', run['root'], '--output', str(output), '--document', '8']) == 0
    state = json.loads((output / 'state.json').read_text())
    (output / 'reply-0000.json').write_text(json.dumps(ack(state, safe=True, rhino_serial=8, original_gh=None)))
    assert host.main(['poll', '--output', str(output)]) == 0
    (output / 'ownership.json').write_text(json.dumps(dict(run_id=state['run_id'], owned='durable')))
    assert host.main(['poll', '--output', str(output), '--cancel']) == 0
    assert json.loads((output / 'state.json').read_text())['phase'] == 'close'


def test_audit_reads_loaded_modules_and_does_not_import_solver(run, monkeypatch, tmp_path):
    # Execute generated embedded Python against controlled module registries.
    module = tmp_path / 'fake.py'; module.write_text('module data')
    plugin = types.SimpleNamespace(REGISTRY_LOCK=threading.Lock(), SESSIONS={'s': 1}, __file__=str(module))
    jobs = types.SimpleNamespace(LOCK=threading.Lock(), JOBS={'j': 1}, __file__=str(module))
    script = (Path(run['output']) / 'audit.py').read_text()
    for loaded in (False, True):
        monkeypatch.setitem(sys.modules, 'hawa.plugin', plugin if loaded else None)
        monkeypatch.setitem(sys.modules, 'hawa.jobs', jobs if loaded else None)
        exec(compile(script, str(Path(host.__file__).with_name('host_acceptance_audit.py')), 'exec'), {})
        report = json.loads((Path(run['output']) / 'audit-0000.json').read_text())
        assert report['sessions'] == report['jobs'] == int(loaded)
        assert len(report['sources']) == 2 * int(loaded)
        assert report['run_id'] == run['run_id'] and report['sequence'] == 0


def test_cli_module_entrypoint(run, monkeypatch):
    import runpy
    output = str(Path(run["output"]).with_name("entrypoint"))
    monkeypatch.setattr(sys, "argv", [host.__file__, "start", "--root", run["root"], "--output", output, "--document", "8"])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(host.__file__, run_name="__main__")
    assert caught.value.code == 0
    assert (Path(output) / "state.json").exists()


def test_identity_evidence_and_request_sequence_are_preserved(run):
    s = step(run, safe=True, rhino_serial=8, original_gh='previous')
    assert s['rhino_serial'] == 8 and s['sequence'] == 1
    s = step(s, owned='child')
    assert s['owned'] == 'child' and s['sequence'] == 2
    s = step(step(s, ready=True))
    evidence = ack(s, passed=True, outputs={'velocity': [1.25, 0, 0]}, steps=60)
    done = host.advance(s, evidence, now=101)
    assert done['results'] == [evidence] and done['sequence'] == s['sequence'] + 1
    assert step(run, safe=False)['failure'] == 'Unsafe host preflight'
    assert host.advance(run, None, now=101, cancel=True)['failure'] == 'Cancelled by operator'
    for bad in ('true', 1, [], None):
        assert step(run, safe=bad)['status'] == 'blocked'
        assert step(s, passed=bad)['phase'] == 'observe'
    # The engine does not mutate the caller's persisted snapshot.
    assert run['sequence'] == 0 and run['results'] == []


def test_creation_inventory_defaults_and_nested_output(run):
    import uuid
    root = Path(run['root'])
    output = Path(run['output']).with_name('nested') / 'new' / 'run'
    s = host.create(root, output, now=10, document=8)
    assert s['timeout'] == 180 and s['deadline'] == 190
    assert uuid.UUID(hex=s['run_id']).hex == s['run_id']
    assert s['run_id'] != run['run_id']
    assert s['original_gh'] is None and s['rhino_serial'] == 8
    assert s['examples'] == [str(output / ('%s-example.gh' % n)) for n in (31, 32)]
    assert set(s['source_hashes']) == {str(root / 'examples/grasshopper' / ('%s-example.gh' % n)) for n in (31, 32)}
    assert all(Path(path).read_bytes() == b'archive' for path in s['examples'])
    for timeout in (0.1, 1, 3600):
        t = host.create(root, output.with_name('boundary-' + str(timeout)), timeout, now=10, document=8)
        assert t['deadline'] == 10 + timeout
    s['status'] = 'failed'
    host.publish(s)
    host.publish(s)  # Terminal writes remain idempotent after scripts are removed.


@pytest.mark.parametrize('argv', [[], ['start'], ['start', '--root', '/tmp'], ['start', '--output', '/tmp'], ['poll']])
def test_cli_requires_complete_arguments(argv):
    with pytest.raises(SystemExit) as result:
        host.main(argv)
    assert result.value.code == 2


def test_cli_timeout_and_success_status(run, monkeypatch, capsys):
    output = Path(run['output']).with_name('cli')
    monkeypatch.setattr(host.time, 'time', lambda: 100)
    assert host.main(['start', '--root', run['root'], '--output', str(output), '--timeout', '1.5', '--document', '8']) == 0
    s = json.loads((output / 'state.json').read_text())
    assert s['timeout'] == 1.5 and s['deadline'] == 101.5
    s.update(phase='cleanup', index=1, owned='owned')
    host.publish(s)
    (output / 'reply-0000.json').write_text(json.dumps(ack(s, clean=True)))
    assert host.main(['poll', '--output', str(output)]) == 0
    assert json.loads((output / 'state.json').read_text())['status'] == 'passed'


def test_operator_cancel_ignores_corrupt_reply_and_retains_owned_id(run, monkeypatch):
    monkeypatch.setattr(host.time, 'time', lambda: 101)
    output = Path(run['output'])
    (output / 'reply-0000.json').write_text('corrupt response')
    (output / 'ownership.json').write_text(json.dumps(dict(run_id=run['run_id'], owned='owned')))
    assert host.main(['poll', '--output', str(output), '--cancel']) == 0
    state = json.loads((output / 'state.json').read_text())
    assert state['phase'] == 'close' and state['owned'] == 'owned'


def test_explicit_scratch_serial_required(run):
    for value in (None, 0, -1, True, "8"):
        with pytest.raises(ValueError, match="scratch"):
            host.create(run['root'], Path(run['output']).with_name('invalid'), document=value)


def test_document_identity_and_minimum_serial(run):
    assert step(run, safe=True, rhino_serial=9, original_gh=None)['status'] == 'blocked'
    state = host.create(run['root'], Path(run['output']).with_name('serial-one'), document=1)
    assert state['rhino_serial'] == 1


@pytest.mark.parametrize('missing', ['--root', '--output', '--document'])
def test_each_cli_required_argument(run, missing):
    args = {'--root': run['root'], '--output': str(Path(run['output']).with_name('missing')), '--document': '8'}
    del args[missing]
    argv = ['start']
    for key, value in args.items():
        argv.extend([key, value])
    with pytest.raises(SystemExit) as result:
        host.main(argv)
    assert result.value.code == 2


def test_cli_default_timeout(run):
    output = Path(run['output']).with_name('default-timeout')
    assert host.main(['start', '--root', run['root'], '--output', str(output), '--document', '8']) == 0
    assert json.loads((output / 'state.json').read_text())['timeout'] == 180
