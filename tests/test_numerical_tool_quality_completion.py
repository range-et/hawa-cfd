"""Numerical-tool reporting contracts; CPU substitutes do not prove GPU parity."""
import builtins
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from hawa import plugin
from test_walls import link_spec

ROOT = Path(__file__).resolve().parents[1]


def execute_script(name, fixture_root):
    source = ROOT/'scripts'/name
    # Keep the real file identity for measurement. Redirect only this script's
    # pathlib import to resolve its output root inside the fixture checkout.
    def fixture_path(value):
        return fixture_root/'scripts'/name if str(value) == str(source) else Path(value)
    real_import = builtins.__import__
    def script_import(module, *args, **kwargs):
        if module == 'pathlib': return SimpleNamespace(Path=fixture_path)
        return real_import(module, *args, **kwargs)
    namespace = {'__name__': '__main__', '__file__': str(source),
                 '__builtins__': dict(vars(builtins), __import__=script_import)}
    exec(compile(source.read_text(), str(source), 'exec'), namespace)
    return namespace


def curved_inputs(tmp_path, completed=True):
    directory = tmp_path/'results/v05/boundaries'; directory.mkdir(parents=True)
    (directory/'geometry.json').write_text(json.dumps({'state': 'completed' if completed else 'failed'}))
    case = link_spec()
    for n in (13,25,49): (directory/('sphere-%d.json'%n)).write_text(json.dumps(case))
    return directory, case


@pytest.mark.parametrize('fault', ['none', 'mismatch', 'nonfinite'])
def test_curved_parity_records_cpu_fixture_comparison_and_failed_rows(tmp_path, monkeypatch, fault):
    directory, case = curved_inputs(tmp_path)
    real_session = plugin.Session; devices = []
    def session(spec, device):
        devices.append(device)
        actual = real_session(spec, 'cpu')
        if device == 'mps' and fault != 'none':
            advance = actual.advance
            def corrupt_after_advance(steps):
                advance(steps)
                if fault == 'mismatch': actual.flow.f.add_(.01)
                else: actual.flow.f[0,0,0,0] = float('nan')
            actual.advance = corrupt_after_advance
        return actual
    monkeypatch.setattr(plugin, 'Session', session)
    monkeypatch.setattr(torch.backends.mps, 'is_available', lambda: True)
    if fault == 'none': execute_script('verify_curved_parity.py', tmp_path)
    else:
        with pytest.raises(AssertionError): execute_script('verify_curved_parity.py', tmp_path)
    report = json.loads((directory/'sphere-parity.json').read_text())
    assert report['steps'] == 40
    if fault == 'none':
        assert report['state'] == 'completed' and len(report['rows']) == 3
        assert devices == ['cpu','mps']*3
        for row in report['rows']:
            assert row == {'shape': case['shape'], 'links': len(case['wall_links']), 'max_population_difference': 0.}
    else:
        assert report['state'] == 'failed' and 'error' in report and report['rows'] == []
        assert devices == ['cpu','mps']


@pytest.mark.parametrize('fault', ['geometry', 'hardware', 'session'])
def test_curved_parity_always_persists_failure_evidence(tmp_path, monkeypatch, fault):
    directory, _ = curved_inputs(tmp_path, completed=fault != 'geometry')
    monkeypatch.setattr(torch.backends.mps, 'is_available', lambda: fault != 'hardware')
    calls = []
    def unavailable(spec, device):
        calls.append(device)
        raise RuntimeError('injected device construction failure')
    monkeypatch.setattr(plugin, 'Session', unavailable)
    with pytest.raises((AssertionError, RuntimeError)): execute_script('verify_curved_parity.py', tmp_path)
    report = json.loads((directory/'sphere-parity.json').read_text())
    assert report['state'] == 'failed' and report['rows'] == [] and 'error' in report
    if fault == 'hardware': assert 'MPS hardware unavailable' in report['error']
    if fault == 'session': assert 'device construction failure' in report['error'] and calls == ['cpu']
    else: assert calls == []


@pytest.mark.parametrize('reject_after', [None, 2])
def test_neutral_adjustment_computes_variance_and_stops_on_rejection(tmp_path, monkeypatch, reject_after, capsys):
    # Deterministic external-device observations isolate the actual report
    # arithmetic and stop policy; this does not run or qualify the MPS solver.
    requested = []; counts = []
    velocity = np.array([[[[1.,3.],[3.,5.]],[[5.,7.],[7.,9.]]],
                         [[[0.,2.],[2.,4.]],[[4.,6.],[6.,8.]]],
                         [[[0.,0.],[0.,0.]],[[0.,0.],[0.,0.]]]])
    mean = velocity.mean((1,2)); variance = ((velocity-mean[:,None,None,:])**2).mean((1,2))
    class ObservedSession:
        def __init__(self, spec, device):
            requested.append((spec,device)); self.flow = SimpleNamespace(i=0, units=SimpleNamespace(convert_time_to_pu=lambda steps: steps*.02))
            self.solver = SimpleNamespace(rough_floor=SimpleNamespace(report={'mean_traction_on_fluid_pa': [-.1,0.,0.]}))
            self.relative_mass_change = 1e-7; self.quality = {'status': 'within-tested-envelope'}
        def advance(self, steps):
            counts.append(steps); self.flow.i += steps
            if reject_after is not None and len(counts) >= reject_after: self.quality = {'status': 'rejected'}
        def fields(self): return {'velocity': velocity}
    monkeypatch.setattr(plugin, 'Session', ObservedSession)
    monkeypatch.chdir(tmp_path); directory = tmp_path/'results/neutral-precursor'; directory.mkdir(parents=True)
    execute_script('verify_neutral_adjustment.py', tmp_path)
    report = json.loads((directory/'adjustment-mps.json').read_text())
    length = 40 if reject_after is None else reject_after
    assert counts == [500]*length and report['steps'] == length*500
    assert len(report['samples']) == length and len(capsys.readouterr().out.splitlines()) == length
    assert report['device'] == requested[0][1] == 'mps'
    assert report['spec'] == requested[0][0] and report['atmospheric_validation'] is False
    assert 'no experimental reference' in report['scope'] and report['wall_seconds'] >= 0
    for i, row in enumerate(report['samples']):
        np.testing.assert_array_equal(row['profile'], mean)
        np.testing.assert_array_equal(row['resolved_variance'], variance)
        assert row['time_seconds'] == (i+1)*10.
        assert row['wall']['mean_traction_on_fluid_pa'] == [-.1,0.,0.] and row['mass_change'] == 1e-7
    assert report['samples'][-1]['quality']['status'] == ('rejected' if reject_after else 'within-tested-envelope')
