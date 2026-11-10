"""Small real fixtures for verification and developer-tool boundaries."""
import functools
import http.client
import importlib.util
import io
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_refinement_benchmark_reports_measured_error_and_mass():
    result = load('benchmark_refinement').benchmark(n=16, steps=2, device='cpu')
    assert result['n'] == 16 and result['steps'] == 2 and result['device'] == 'cpu'
    assert 0 <= result['refined_relative_l2'] < .1
    assert 0 <= result['coarse_relative_l2'] < .1
    assert abs(result['relative_mass_drift']) < 1e-4


def test_curved_wall_benchmark_reports_small_channel_error():
    result = load('benchmark_curved_walls').run(4, .5)
    assert result['n'] == 4 and result['q'] == .5
    assert result['expected_max'] == pytest.approx(7.5e-6)
    assert result['max_speed'] > 0
    # On this symmetric two-fluid-row fixture, both measured speeds coincide.
    # Verify error reporting; this underresolved case is not an accuracy pass.
    assert result['relative_l2'] == pytest.approx(abs(result['max_speed']/result['expected_max'] - 1))


@pytest.mark.parametrize('header,status,payload', [(None, 200, b'0123456789'), ('bytes=2-5', 206, b'2345'),
    ('bytes=-3', 206, b'789'), ('bytes=8-', 206, b'89'), ('bytes=7-99', 206, b'789'),
    ('bytes=20-', 416, b''), ('bytes=4-2', 416, b'')])
def test_preview_byte_ranges_use_actual_file_content(tmp_path, header, status, payload):
    # Handle a real HTTP request synchronously through in-memory socket streams.
    module = load('preview_site')
    (tmp_path/'clip.mp4').write_bytes(b'0123456789')
    raw = b'GET /clip.mp4 HTTP/1.0\r\nHost: localhost\r\n'
    if header: raw += ('Range: '+header+'\r\n').encode()
    raw += b'\r\n'
    class Socket:
        def __init__(self): self.output = io.BytesIO()
        def makefile(self, *args, **kwargs): return io.BytesIO(raw)
        def sendall(self, value): self.output.write(value)
    socket = Socket()
    module.PreviewHandler(socket, ('127.0.0.1', 0), object(), directory=str(tmp_path))
    response = socket.output.getvalue()
    head, body = response.split(b'\r\n\r\n', 1)
    assert b' '+str(status).encode()+b' ' in head
    assert b'Accept-Ranges: bytes' in head
    assert body == payload
    if status == 206:
        assert ('Content-Length: '+str(len(payload))).encode() in head
        assert b'Content-Range: bytes ' in head


def test_motion_summary_refuses_missing_or_failed_evidence(tmp_path, monkeypatch):
    module = load('summarize_motion_verification')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    with pytest.raises(FileNotFoundError): module.main()
    directory = tmp_path/'results/motion'; directory.mkdir(parents=True)
    (tmp_path/'results/v04').mkdir(); (tmp_path/'docs').mkdir()
    files = {'native-examples.json':dict(state='completed',results=[dict(passed=True)]),
             'native-controls.json':dict(state='completed'), 'native-cleanup.json':dict(jobs=0,sessions=0,workers=[]),
             'rotating-sphere.json':dict(passed=True), 'comoving.json':dict(passed=True),
             'timing.json':dict(seconds=1), 'annotation-report.json':dict(passed=True)}
    for name,value in files.items(): (directory/name).write_text(json.dumps(value))
    (tmp_path/'results/v04/native-examples.json').write_text(json.dumps(files['native-examples.json']))
    (directory/'tests-final.txt').write_text('140 passed, 29 skipped')
    (directory/'engine-parity.txt').write_text('fixture evidence, not a device qualification')
    module.main()
    result=json.loads((tmp_path/'docs/verification-motion-v0.4.json').read_text())
    assert result['native_cleanup']==files['native-cleanup.json']
    assert result['hawa_tests']['passed']==140
    assert 'CUDA hardware and Windows installation unverified' in result['limitations']
    (directory/'native-cleanup.json').write_text(json.dumps(dict(jobs=1,sessions=0,workers=[])))
    with pytest.raises(AssertionError): module.main()


@pytest.mark.parametrize('count,release,expected', [(67,False,0),(67,True,1),(66,False,None)])
def test_combined_checker_requires_current_contract_inventory(tmp_path, monkeypatch, count, release, expected):
    from types import SimpleNamespace
    module=load('check_compatibility_evidence')
    monkeypatch.setattr(module,'verify_evidence',lambda path:dict(counts=dict(passed=1,blocked=1),release_pass=False))
    monkeypatch.setattr(module,'verify_examples',lambda path:dict(nodes=54))
    monkeypatch.setattr(module.subprocess,'run',lambda *a,**kw:SimpleNamespace(stdout='tests/test_fixture.py::test_one\n'))
    junit=tmp_path/'suite.xml';junit.write_text('<testsuite><testcase classname="test_fixture" name="test_one"/></testsuite>')
    state=tmp_path/'state.log';state.write_text(json.dumps(dict(passed=count)))
    monkeypatch.setattr(sys,'argv',['check','--matrix',str(tmp_path),'--junit',str(junit),'--state-log',str(state)]+(['--release'] if release else []))
    if expected is None:
        with pytest.raises(ValueError,match='State contract'):module.main()
    else: assert module.main()==expected


@pytest.mark.parametrize('reference',[False,True])
def test_upstream_runner_isolates_reference_and_preserves_exit_status(tmp_path,monkeypatch,reference):
    module=load('run_upstream_tests');monkeypatch.setattr(module,'ROOT',tmp_path)
    vendor=tmp_path/'vendor/lettuce';(vendor/'tests').mkdir(parents=True);(vendor/'docs').mkdir()
    (vendor/'tests/test_original.py').write_text('assert True\n');(vendor/'docs/modules.rst').write_text('original documentation')
    observed=[]
    def call(command,**kwargs):observed.append((command,kwargs));return 7
    monkeypatch.setattr(module.subprocess,'call',call)
    monkeypatch.setattr(sys,'argv',['run']+(['--reference'] if reference else []))
    assert module.main()==7
    command,options=observed[0]
    assert command[1:3]==['-m','pytest'] and options['cwd']==tmp_path and options['env']['MPLBACKEND']=='Agg'
    if reference:
        assert '.venv-reference' in command[0] and command[3]==str(tmp_path/'.reference/upstream-tests/tests')
        assert (tmp_path/'.reference/upstream-tests/tests/test_original.py').read_text()=='assert True\n'
        assert (tmp_path/'.reference/upstream-tests/docs/modules.rst').read_text()=='original documentation'
    else:assert command[0]==sys.executable and command[3]==str(vendor/'tests')


def test_scaling_harness_keeps_failed_feasibility_explicit(tmp_path,monkeypatch):
    module=load('verify_atmospheric_scaling')
    monkeypatch.setattr(module.torch.backends.mps,'is_available',lambda:False)
    monkeypatch.setattr(module.torch.cuda,'is_available',lambda:False)
    output=tmp_path/'scaling.json';monkeypatch.setattr(sys,'argv',['scaling','--output',str(output)])
    assert module.main()==2
    report=json.loads(output.read_text())
    assert not report['passed'] and len(report['cases'])==3
    assert [r['preflight'] for r in report['cases']]==['accepted','rejected','rejected']
    assert report['cases'][-1]['devices']['cpu']['rounds_to_half'] is True
    assert all(set(r['devices'])=={'cpu'} for r in report['cases'])
    assert 'CUDA' in report['omitted']


def test_precursor_harness_zero_step_control_preserves_limits(tmp_path,monkeypatch):
    module=load('verify_neutral_precursor');output=tmp_path/'precursor.json'
    monkeypatch.setattr(sys,'argv',['precursor','--output',str(output),'--steps','0','--device','cpu'])
    assert module.main()==0
    report=json.loads(output.read_text())
    assert report['atmospheric_validation'] is False
    assert [r['shape'][0] for r in report['cases']]==[12,16,24]
    assert all(r['steps']==0 and r['surface_layer_relative_l2_drift']==0 and r['profile_target']==.05 for r in report['cases'])
