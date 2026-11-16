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
    return host.create(root, tmp_path / 'run', timeout=10, now=100)


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
        host.create(run['root'], output)
    for timeout in (0, -1, 3601, float('nan')):
        with pytest.raises(ValueError):
            host.create(run['root'], output / 'invalid', timeout)
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
    assert host.main(['start', '--root', run['root'], '--output', str(output)]) == 0
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
    monkeypatch.setattr(sys, "argv", [host.__file__, "start", "--root", run["root"], "--output", output])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(host.__file__, run_name="__main__")
    assert caught.value.code == 0
    assert (Path(output) / "state.json").exists()
