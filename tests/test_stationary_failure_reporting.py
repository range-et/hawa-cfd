"""Advancement failures must replace stale success without saving invalid state."""
import json
from types import SimpleNamespace
import sys

import numpy as np
import pytest

from test_tooling_entrypoints import execute_fixture


@pytest.mark.parametrize('close_failure',[False,True])
@pytest.mark.parametrize('stage',['first','after-pass'])
@pytest.mark.parametrize('exception',[RuntimeError,ValueError])
def test_advance_exception_invalidates_success_and_closes_session(tmp_path,monkeypatch,stage,exception,close_failure):
    import hawa.plugin
    from hawa.atmosphere import neutral_profile
    out=tmp_path/'stationary.json';out.write_text(json.dumps(dict(passed=True,stale=True)))
    profile=neutral_profile(np.arange(12)+.5,[5.,0,0],6.,.01).T
    target=1.225*(.41*5/np.log1p(6/.01))**2
    failing_step=500 if stage=='first' else 20500
    calls=[];field_steps=[]
    class Session:
        flow=SimpleNamespace(i=0,units=SimpleNamespace(convert_time_to_pu=lambda n:n*.01))
        quality=dict(status='within-tested-envelope')
        solver=SimpleNamespace(rough_floor=SimpleNamespace(report=dict(mean_traction_on_fluid_pa=[-target,0,0])))
        def advance(self,n):
            self.flow.i+=n
            if self.flow.i==failing_step:
                assert json.loads(out.read_text())['passed'] is True
                self.quality['status']='rejected'
                raise exception('Nonfinite populations or nonpositive density')
        def fields(self):
            assert self.quality['status']!='rejected'
            field_steps.append(self.flow.i)
            return dict(velocity=np.broadcast_to(profile[:,None,None,:],(3,2,2,12)))
    session=Session()
    def dispatch(request):
        calls.append((request['op'],session.flow.i))
        if request['op']=='create':return dict(session='fixture')
        if request['op']=='save':assert session.quality['status']!='rejected'
        if request['op']=='close' and close_failure:raise RuntimeError('cleanup also failed')
    monkeypatch.setattr(hawa.plugin,'dispatch',dispatch)
    monkeypatch.setattr(hawa.plugin,'SESSIONS',{'fixture':session})
    monkeypatch.setattr(sys,'argv',['stationary','--steps',str(failing_step),'--device','cpu','--output',str(out)])
    with pytest.raises(SystemExit) as stop:execute_fixture('verify_neutral_stationary',tmp_path)
    assert stop.value.code==1
    report=json.loads(out.read_text())
    assert report['passed'] is False and 'stale' not in report
    assert report['error']==exception.__name__+': Nonfinite populations or nonpositive density'
    assert report['quality_status']=='rejected' and report['steps']==failing_step
    if close_failure:assert report['cleanup_error']=='RuntimeError: cleanup also failed'
    else:assert 'cleanup_error' not in report
    assert report['checkpoint_omitted']=='No additional checkpoint attempted after failure'
    assert len(report['samples'])==len(field_steps)==(0 if stage=='first' else 40)
    assert calls[-1]==('close',failing_step)
    assert [step for op,step in calls if op=='save']==([] if stage=='first' else [5000,10000,15000,20000])
    assert report['targets']==dict(stationarity=.02,drag=.05,profile=.05)
    assert report['physical_validation'] is False


@pytest.mark.parametrize('scenario',['zero','resumed-complete','load-error','save-error','close-error'])
def test_no_progress_or_lifecycle_failure_never_reuses_previous_pass(tmp_path,monkeypatch,scenario):
    import hawa.plugin
    out=tmp_path/'stationary.json'
    out.write_text(json.dumps(dict(passed=True,samples=[])))
    calls=[]
    class Session:
        flow=SimpleNamespace(i=0,units=SimpleNamespace(convert_time_to_pu=lambda n:n*.01))
        quality=dict(status='within-tested-envelope')
        solver=SimpleNamespace(rough_floor=SimpleNamespace(report=dict(mean_traction_on_fluid_pa=[0,0,0])))
        def advance(self,n):self.flow.i+=n
        def fields(self):return dict(velocity=np.ones((3,2,2,12)))
    session=Session()
    def dispatch(request):
        op=request['op'];calls.append(op)
        if op=='create':return dict(session='fixture')
        if op=='load':
            if scenario=='load-error':raise ValueError('checkpoint unreadable')
            session.flow.i=500
        if op=='save' and scenario=='save-error':raise OSError('checkpoint write failed')
        if op=='close' and scenario=='close-error':raise RuntimeError('close failed')
    monkeypatch.setattr(hawa.plugin,'dispatch',dispatch)
    monkeypatch.setattr(hawa.plugin,'SESSIONS',{'fixture':session})
    args=['stationary','--steps','500' if scenario in ('resumed-complete','save-error') else '0','--output',str(out)]
    if scenario in ('resumed-complete','load-error'):args.append('--resume')
    monkeypatch.setattr(sys,'argv',args)
    with pytest.raises(SystemExit) as stop:execute_fixture('verify_neutral_stationary',tmp_path)
    assert stop.value.code==1 and calls[-1]=='close'
    report=json.loads(out.read_text());assert report['passed'] is False
    if scenario in ('zero','resumed-complete'):assert report['reason']=='No samples advanced in this invocation'
    if scenario=='load-error':assert report['error']=='ValueError: checkpoint unreadable'
    if scenario=='save-error':assert report['error']=='OSError: checkpoint write failed'
    if scenario=='close-error':assert report['cleanup_error']=='RuntimeError: close failed'


@pytest.mark.parametrize('failure',['create','session-lookup'])
def test_session_startup_failure_replaces_stale_success_without_closing_unknown_session(tmp_path,monkeypatch,failure):
    import hawa.plugin
    out=tmp_path/'stationary.json';out.write_text(json.dumps(dict(passed=True,stale=True)))
    calls=[]
    def dispatch(request):
        calls.append(request)
        if request['op']=='create':
            if failure=='create':raise ValueError('invalid wall sample or device')
            return dict(session='created-but-unavailable')
    monkeypatch.setattr(hawa.plugin,'dispatch',dispatch)
    monkeypatch.setattr(hawa.plugin,'SESSIONS',{})
    monkeypatch.setattr(sys,'argv',['stationary','--steps','500','--output',str(out)])
    with pytest.raises(SystemExit) as stop:execute_fixture('verify_neutral_stationary',tmp_path)
    assert stop.value.code==1
    report=json.loads(out.read_text())
    assert report['passed'] is False and 'stale' not in report
    assert report['steps']==0 and report['samples']==[] and report['quality_status']=='unknown'
    assert report['physical_validation'] is False
    if failure=='create':
        assert report['error']=='ValueError: invalid wall sample or device'
        assert [r['op'] for r in calls]==['create']
    else:
        assert report['error']=="KeyError: 'created-but-unavailable'"
        assert calls[-1]==dict(op='close',session='created-but-unavailable')


@pytest.mark.parametrize('filename',['stationary.json','x'*245+'.json'])
@pytest.mark.parametrize('failure',['create','load','malformed','none'])
def test_resume_preserves_complete_history_before_startup_or_load(tmp_path,monkeypatch,failure,filename):
    import hawa.plugin
    from pathlib import Path
    out=tmp_path/filename
    samples=[dict(step=500,profile=[1,2,3],drag=4),dict(step=1000,profile=[5,6,7],drag=8)]
    original=(json.dumps(dict(passed=True,samples=samples,provenance='original'))+'\n').encode()
    if failure=='malformed':original=b'{invalid but irreplaceable study text'
    out.write_bytes(original)
    calls=[]
    session=SimpleNamespace(flow=SimpleNamespace(i=0),quality=dict(status='within-tested-envelope'))
    def dispatch(request):
        calls.append(request['op'])
        if request['op']=='create':
            if failure=='create':raise RuntimeError('device unavailable')
            return dict(session='fixture')
        if request['op']=='load':
            if failure=='load':raise ValueError('checkpoint mismatch')
            session.flow.i=500
    monkeypatch.setattr(hawa.plugin,'dispatch',dispatch)
    monkeypatch.setattr(hawa.plugin,'SESSIONS',{'fixture':session})
    monkeypatch.setattr(sys,'argv',['stationary','--resume','--steps','500','--output',str(out)])
    # A second attempt must never replace the first preserved report.
    backups=[]
    for _ in range(2):
        out.write_bytes(original)
        with pytest.raises(SystemExit) as stop:execute_fixture('verify_neutral_stationary',tmp_path)
        assert stop.value.code==1
        result=json.loads(out.read_text())
        assert result['passed'] is False
        backup=Path(result['resume_backup'])
        assert len(backup.name.encode())<64
        assert result['resume_source_report']==str(out.resolve())
        assert backup.read_bytes()==original and backup not in backups
        backups.append(backup)
        if failure in ('create','load'):assert result['samples']==samples
        elif failure=='none':assert result['samples']==samples[:1]
        else:assert result['samples']==[] and 'JSONDecodeError' in result['error']
        assert all(p.read_bytes()==original for p in backups)
    if failure in ('create','malformed'):assert 'close' not in calls
    else:assert calls[-1]=='close'
