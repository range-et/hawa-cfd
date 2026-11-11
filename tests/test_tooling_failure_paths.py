"""Failure paths and CLI wiring; device doubles are not CUDA qualifications."""
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch

from test_tooling_execution import load
from test_tooling_entrypoints import execute_fixture
from test_cuda_verification import repository, write_evidence


@pytest.mark.parametrize('header',['bytes=-','nonsense','bytes=0-1,4-5'])
def test_preview_rejects_malformed_ranges(tmp_path,header):
    m=load('preview_site');(tmp_path/'clip.mp4').write_bytes(b'0123')
    raw=('GET /clip.mp4 HTTP/1.0\r\nHost: localhost\r\nRange: '+header+'\r\n\r\n').encode()
    class Socket:
        output=io.BytesIO()
        def makefile(self,*args,**kw):return io.BytesIO(raw)
        def sendall(self,value):self.output.write(value)
    socket=Socket();m.PreviewHandler(socket,('127.0.0.1',0),object(),directory=str(tmp_path))
    head,body=socket.output.getvalue().split(b'\r\n\r\n',1)
    assert b'416 Unsupported byte range' in head and b'Unsupported byte range' in body


def test_preview_stops_at_early_eof_and_cli_binds_loopback(tmp_path,monkeypatch):
    import http.server
    m=load('preview_site');handler=object.__new__(m.PreviewHandler);handler.remaining=4
    target=io.BytesIO();handler.copyfile(io.BytesIO(b'ab'),target)
    assert target.getvalue()==b'ab' and handler.remaining==2
    calls=[]
    class Server:
        def __init__(self,address,factory):
            assert address==('127.0.0.1',9876)
            assert factory.keywords['directory']==str(tmp_path)
        def serve_forever(self):calls.append('served')
    monkeypatch.setattr(http.server,'ThreadingHTTPServer',Server)
    monkeypatch.setattr(sys,'argv',['preview','--port','9876','--directory',str(tmp_path)])
    execute_fixture('preview_site',tmp_path)
    assert calls==['served']


def test_evidence_rejects_missing_call_phase_and_inconsistent_skip_counts(tmp_path):
    m=load('pytest_evidence');out=tmp_path/'phase.json'
    config=SimpleNamespace(_verification_reports={'test_a':[('setup','passed'),('teardown','passed')]},_verification_collected=['test_a'],getoption=lambda name:str(out))
    m.pytest_sessionfinish(SimpleNamespace(config=config),0)
    assert json.loads(out.read_text())['outcomes']==[dict(nodeid='test_a',outcome='failed')]
    m=load('verification_evidence');ids=['test_a[cpu]']
    write_evidence(tmp_path,'expected',ids);write_evidence(tmp_path,'actual',ids)
    data=json.loads((tmp_path/'actual.json').read_text());data['outcomes'][0]['outcome']='skipped';(tmp_path/'actual.json').write_text(json.dumps(data))
    with pytest.raises(ValueError,match='skip mismatch'):m.validate_pytest(tmp_path/'expected.json',tmp_path/'actual.json',tmp_path/'actual.xml')


@pytest.mark.parametrize('fault',['repeats','python','pins'])
def test_cuda_runner_rejects_invalid_environment_before_evidence(tmp_path,monkeypatch,fault):
    import hawa.backends
    m=load('verify_cuda')
    monkeypatch.setattr(hawa.backends,'select_backend',lambda device:SimpleNamespace(info=lambda:{}))
    monkeypatch.setattr(sys,'argv',['cuda','--output',str(tmp_path/'out'),'--repeats','0' if fault=='repeats' else '1'])
    if fault=='python':monkeypatch.setattr(m,'sys',SimpleNamespace(version_info=(3,10)))
    if fault=='pins':monkeypatch.setattr(torch,'__version__','0.0')
    with pytest.raises(SystemExit) as stop:m.main()
    assert stop.value.code==2 and not (tmp_path/'out').exists()


@pytest.mark.production_python
def test_cuda_runner_full_scope_keeps_all_stage_commands_and_evidence(repository,monkeypatch):
    import subprocess
    import hawa.backends
    import audit_backport
    m=load('verify_cuda');monkeypatch.setattr(m,'ROOT',repository)
    monkeypatch.setattr(hawa.backends,'select_backend',lambda device:SimpleNamespace(info=lambda:dict(fixture=True)))
    monkeypatch.setattr(torch.cuda,'get_device_name',lambda index:'fixture')
    monkeypatch.setattr(torch.cuda,'get_device_capability',lambda index:(0,0))
    monkeypatch.setattr(audit_backport,'audit',lambda:dict(fixture=True))
    out=repository/'results/all';monkeypatch.setattr(sys,'argv',['cuda','--output',str(out),'--repeats','1'])
    original=subprocess.run;commands=[]
    def run(command,**kwargs):
        if command[0]!=sys.executable:return original(command,**kwargs)
        commands.append(command)
        if command[1:3]==['-m','pytest']:
            target=Path(next(a.split('=',1)[1] for a in command if a.startswith('--verification-evidence=')))
            write_evidence(target.parent,target.stem,['test_a[cuda:0]'])
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(m.subprocess,'run',run)
    assert m.main()==0
    report=json.loads((out/'report.json').read_text())
    assert report['full_scope'] and report['full_passed'] and report['passed']
    assert [r['name'] for r in report['stages']]==['hawa-1-collection','hawa-1','upstream-portable-collection','upstream-portable','core-parity','examples-cpu','examples-cuda-0','example-parity']
    assert len(commands)==8 and all(r['source_unchanged'] for r in report['stages'])


@pytest.mark.parametrize('name',['benchmark_motion','benchmark_curved_walls','benchmark_refinement','benchmark_rotating_sphere'])
def test_benchmark_entrypoint_routes_declared_grids_and_persists_rows(tmp_path,monkeypatch,name):
    import ast
    m=load(name);calls=[]
    monkeypatch.setattr(torch.backends.mps,'is_available',lambda:True)
    if hasattr(m,'ROOT'):monkeypatch.setattr(m,'ROOT',tmp_path)
    original_resolve=Path.resolve;source=Path(m.__file__)
    monkeypatch.setattr(Path,'resolve',lambda p,*a,**kw:tmp_path/'scripts'/source.name if p==source else original_resolve(p,*a,**kw))
    if name=='benchmark_motion':
        def runner(device):calls.append(device);return dict(device=device,fixture=True,max_fluid_population_error=0.,max_force_newtons=0.)
        monkeypatch.setattr(m,'comoving',runner);output=tmp_path/'results/motion/comoving.json'
    elif name=='benchmark_curved_walls':
        def runner(n,q):calls.append((n,q));return dict(n=n,q=q,fixture=True)
        monkeypatch.setattr(m,'run',runner);output=tmp_path/'results/v04/wall-benchmark.json'
    elif name=='benchmark_refinement':
        def runner(n,steps,device='cpu'):calls.append((n,steps,device));return dict(n=n,steps=steps,device=device,fixture=True)
        monkeypatch.setattr(m,'benchmark',runner);output=tmp_path/'results/v04/refinement-benchmark.json'
    else:
        def runner(dx,device):calls.append((dx,device));return dict(dx=dx,device=device,fixture=True)
        monkeypatch.setattr(m,'benchmark',runner);output=tmp_path/'rotation.json'
        monkeypatch.setattr(sys,'argv',['rotation','--device','cpu','--output',str(output)])
    output.parent.mkdir(parents=True,exist_ok=True)
    # Execute the exact module guard against the loaded module. Benchmark runners
    # are explicit orchestration doubles; separate tests exercise real CPU math.
    tree=ast.parse(source.read_text());guard=tree.body[-1]
    assert isinstance(guard,ast.If) and ast.unparse(guard.test)=="__name__ == '__main__'"
    exec(compile(ast.Module(body=[guard],type_ignores=[]),str(source),'exec'),dict(vars(m),__name__='__main__'))
    rows=json.loads(output.read_text());assert len(rows)==len(calls) and all(r['fixture'] for r in rows)
    if name=='benchmark_motion':assert calls==['cpu','mps']
    elif name=='benchmark_curved_walls':assert calls==[(n,q) for q in (.25,.75) for n in (8,12,16)]
    elif name=='benchmark_refinement':assert calls==[(16,40,'cpu'),(24,40,'cpu'),(32,40,'cpu'),(16,40,'mps')]
    else:assert calls==[(.5,'cpu'),(1/3,'cpu'),(.25,'cpu')]


@pytest.mark.parametrize('fault',['prepare-source','oversize','load-clock','load-descriptor','child-clock','run-descriptor','run-source'])
def test_nesting_rejects_mid_operation_provenance_and_clock_changes(tmp_path,monkeypatch,fault):
    from test_neutral_nesting_verification import study,descriptor
    path,manifest,bundle=descriptor(tmp_path,monkeypatch)
    if fault=='oversize':
        path.write_bytes(b' '*(4*1024**2+1))
        with pytest.raises(ValueError,match='exceeds 4 MiB'):study.load_reference(path)
        return
    if fault=='prepare-source':
        snapshots=iter([{'fixture':'before'},{'fixture':'after'}])
        monkeypatch.setattr(study,'sources',lambda:next(snapshots))
        monkeypatch.setattr(study,'create_recording',lambda *a,**kw:dict(manifest=str(manifest),backend={'fixture':True}))
        with pytest.raises(ValueError,match='Source changed during reference preparation'):study.prepare_reference(tmp_path,bundle['config'],'cpu')
        assert not (tmp_path/'reference.json').exists()
        return
    if fault=='load-clock':
        original=study.series;calls=[]
        def series(*a,**kw):
            result=original(*a,**kw);calls.append(True)
            return (result[0]+1,*result[1:]) if len(calls)==2 else result
        monkeypatch.setattr(study,'series',series)
        with pytest.raises(ValueError,match='Frozen reference clocks differ'):study.load_reference(path)
        return
    if fault=='load-descriptor':
        original=study.digest;calls=[]
        def digest(target):
            if Path(target)==path:
                calls.append(True)
                if len(calls)==2:path.write_text(path.read_text()+' ')
            return original(target)
        monkeypatch.setattr(study,'digest',digest)
        with pytest.raises(ValueError,match='descriptor changed while loading'):study.load_reference(path)
        return
    args=['--output',str(tmp_path/'result'),'--reuse-reference',str(path)]
    if fault=='child-clock':
        monkeypatch.setattr(study,'capture',lambda *a,**kw:dict(case={}))
        child=tmp_path/'child/manifest.json'
        monkeypatch.setattr(study,'create_recording',lambda *a,**kw:dict(manifest=str(child),backend={'fixture':True}))
        original=study.series
        def series(target,*a,**kw):
            result=original(manifest if Path(target)==child else target,*a,**kw)
            return (result[0]+1,*result[1:]) if Path(target)==child else result
        monkeypatch.setattr(study,'series',series)
        error='Child and parent absolute clocks differ'
    else:
        args.append('--reference-only')
        if fault=='run-descriptor':
            original=study.metrics
            def metrics(*a,**kw):
                result=original(*a,**kw);path.write_text(path.read_text()+' ');return result
            monkeypatch.setattr(study,'metrics',metrics);error='descriptor changed during execution'
        else:
            original=study.sources;calls=[]
            def sources():
                calls.append(True);result=original()
                return dict(result,fixture_changed='yes') if len(calls)==4 else result
            monkeypatch.setattr(study,'sources',sources);error='Source changed during study'
    assert study.main(args)==1
    report=json.loads((tmp_path/'result/result.json').read_text())
    assert not report['passed'] and not report['full_nesting_passed'] and error in report['error']


def test_audit_entrypoint_reports_exact_sources_and_rejects_missing_modules(tmp_path,capsys):
    import hashlib
    vendor=tmp_path/'vendor/lettuce';(vendor/'lettuce').mkdir(parents=True)
    source=vendor/'lettuce/__init__.py';source.write_bytes(b'# fixture\n')
    (vendor/'upstream.json').write_text(json.dumps(dict(commit='fixture',source_sha256={'lettuce/__init__.py':hashlib.sha256(source.read_bytes()).hexdigest()})))
    execute_fixture('audit_backport',tmp_path)
    report=json.loads(capsys.readouterr().out)
    assert report['commit']=='fixture' and report['unchanged_modules']==1 and report['changed_modules']==[]
    source.unlink()
    with pytest.raises(RuntimeError,match='Missing upstream module'):execute_fixture('audit_backport',tmp_path)


def test_motion_summary_entrypoint_keeps_package_checks_without_copying_archive_identity(tmp_path):
    motion=tmp_path/'results/motion';motion.mkdir(parents=True)
    (tmp_path/'results/v04').mkdir();(tmp_path/'docs').mkdir()
    files={'native-examples.json':dict(state='completed',results=[dict(passed=True,fixture=True)]),'native-controls.json':dict(state='completed'),'native-cleanup.json':dict(jobs=0,sessions=0,workers=[]),'rotating-sphere.json':dict(fixture=True),'comoving.json':dict(fixture=True),'timing.json':dict(fixture=True),'annotation-report.json':dict(fixture=True),'package.json':dict(checked=True,zip_sha256='fixture',bytes=17)}
    for name,value in files.items():(motion/name).write_text(json.dumps(value))
    (tmp_path/'results/v04/native-examples.json').write_text(json.dumps(files['native-examples.json']))
    (motion/'tests-final.txt').write_text('140 passed, 29 skipped')
    (motion/'engine-parity.txt').write_text('fixture only, not device verification')
    execute_fixture('summarize_motion_verification',tmp_path)
    report=json.loads((tmp_path/'docs/verification-motion-v0.4.json').read_text())
    assert report['package_checks']==dict(checked=True)
    assert report['native_motion']['results'][0]['fixture']
    assert report['engine_parity']['log']=='fixture only, not device verification'
