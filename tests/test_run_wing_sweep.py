"""CLI composition preserves explicit windows and drains on interruption."""
from copy import deepcopy
import json

import pytest

from scripts import run_wing_sweep as driver


def recipe():
    candidate = dict(candidate_id='a', angle_deg=0., speed_m_s=1., case_hash='case', geometry_hash='mesh')
    raw = dict(case=dict(dx=.1, speed=1., viscosity=.01, mach=.03),
               references=dict(density_kg_m3=1., speed_m_s=1., area_m2=2., chord_m=1.,
                               pressure_pa=0., drag_axis_world=[1.,0.,0.], lift_axis_world=[0.,0.,1.]),
               bodies=[dict(body_id='wing', moment_origin_world_m=[0.,0.,0.])],
               body_indices={'wing':[1]}, origin_world_m=[0.,0.,0.],
               basis=[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]], geometry={'vertices_m':[], 'triangles':[]})
    return dict(candidates=[candidate], prepared={'a':raw})


def test_preparation_exact_source_window_and_detachment():
    source=recipe()
    probes=[dict(probe_id='p',position_world_m=[1.,1.,1.])]
    entries=driver.prepare_entries(source,3,5,.02,'case-id',9,probes)
    entry=entries['a'];req=entry['request']
    dt=.03*.1/(3**.5)
    assert req['window']==dict(start_s=3*dt,end_s=7*dt,minimum_samples=5,
                              stationarity_absolute_coefficient_tolerance=.02)
    assert req['identity']['case_id']=='case-id' and req['identity']['generation']==9
    assert entry['steps']==8 and entry['dtype']=='float32' and entry['selected_body_id']=='wing'
    source['prepared']['a']['case']['speed']=20
    probes[0]['position_world_m'][0]=50
    assert entry['spec']['speed']==1. and entry['probes'][0]['position_world_m'][0]==1.
    assert driver.prepare_entries(recipe(),0,4,.1)['a']['probes']==[]


@pytest.mark.parametrize('settling,samples',[(True,4),(-1,4),(0,True),(0,3),(99999,4)])
def test_preparation_rejects_bad_step_budget(settling,samples):
    with pytest.raises(ValueError):driver.prepare_entries(recipe(),settling,samples,.1)


class Executor:
    def __init__(self,prepared):
        self.prepared=prepared;self.open=[];self.polls=0;self.cancelled=False;self.closes=0
        self.interrupt=False

    def start(self,candidate,generation):
        handle=dict(candidate=candidate,generation=generation)
        self.open.append(handle)
        return handle

    def poll(self,handle):
        self.polls+=1
        if self.interrupt:raise KeyboardInterrupt()
        entry=self.prepared[handle['candidate']['candidate_id']]
        return dict(state='completed',candidate_id=handle['candidate']['candidate_id'],
            generation=handle['generation'],result=dict(identity=deepcopy(entry['request']['identity']),
            quality='accepted',window_valid=True,stationarity_passed=True,coefficients=dict(CL=.2,CD=.1)))

    def pause(self,handle):pass
    def resume(self,handle):pass
    def cancel(self,handle):self.cancelled=True
    def close(self,handle):
        self.closes+=1
        if self.closes==1:return False
        self.open.remove(handle)
        return True
    def results(self,candidate_id,generation):return {'candidate_id':candidate_id,'generation':generation}
    def audit(self):return {'handles':len(self.open),'live_workers':0,'session_ids':[]}


def install(monkeypatch,entries):
    from hawa import sweep_executor
    executor=Executor(entries)
    monkeypatch.setattr(sweep_executor,'CpuSweepExecutor',lambda prepared:executor)
    monkeypatch.setattr(driver.time,'sleep',lambda seconds:None)
    return executor


def test_runner_returns_plots_and_waits_for_confirmed_cleanup(monkeypatch):
    entries=driver.prepare_entries(recipe(),0,4,.1)
    executor=install(monkeypatch,entries)
    result=driver.run_prepared(entries)
    assert result['records'][0]['state']=='completed'
    assert result['plots']['cl_cd'][0][0]['x']==.1
    assert result['plots']['cl_alpha'][0][0]['y']==.2
    assert result['cleanup']['handles']==0 and executor.closes==2
    assert result['details']['a']['generation']==0 and not result['timed_out']


def test_runner_timeout_and_interrupt_drain(monkeypatch):
    entries=driver.prepare_entries(recipe(),0,4,.1)
    executor=install(monkeypatch,entries)
    clock=iter([0.,0.,2.,2.])
    monkeypatch.setattr(driver.time,'monotonic',lambda:next(clock))
    result=driver.run_prepared(entries,1.)
    assert result['timed_out'] and result['records'][0]['state']=='cancelled'
    assert executor.cancelled and executor.closes==2 and not executor.open
    executor=install(monkeypatch,entries);executor.interrupt=True
    monkeypatch.setattr(driver.time,'monotonic',lambda:0.)
    with pytest.raises(KeyboardInterrupt):driver.run_prepared(entries)
    assert executor.cancelled and not executor.open and executor.closes==2


@pytest.mark.parametrize('timeout',[0.,-1.,True,float('inf')])
def test_bad_timeout(monkeypatch,timeout):
    entries=driver.prepare_entries(recipe(),0,4,.1)
    install(monkeypatch,entries)
    with pytest.raises(ValueError,match='timeout_s'):driver.run_prepared(entries,timeout)


def test_mixed_generations_reject_before_worker(monkeypatch):
    entries=driver.prepare_entries(recipe(),0,4,.1)
    entries['b']=deepcopy(entries['a']);entries['b']['request']['identity']['generation']=1
    executor=install(monkeypatch,entries)
    with pytest.raises(ValueError,match='generation'):driver.run_prepared(entries)
    assert not executor.open


@pytest.mark.parametrize('state,timed_out,expected',[('completed',False,0),('rejected',False,1),('cancelled',True,1)])
def test_cli_reports_actual_acceptance(monkeypatch,capsys,state,timed_out,expected):
    from scripts import wing_solver_recipe
    monkeypatch.setattr(wing_solver_recipe,'demo_sweep',recipe)
    observed=[]
    def run(entries,timeout):
        observed.append((entries,timeout))
        return dict(timed_out=timed_out,records=[dict(state=state)])
    monkeypatch.setattr(driver,'run_prepared',run)
    assert driver.main(['--settling-steps','2','--sample-steps','6','--stationarity-tolerance','.03',
                        '--timeout','5'])==expected
    assert json.loads(capsys.readouterr().out)['records'][0]['state']==state
    assert observed[0][0]['a']['steps']==8 and observed[0][1]==5.


def test_module_entrypoint_prints_compact_report_and_exits(monkeypatch,capsys):
    import runpy
    import sys
    from scripts import wing_solver_recipe
    monkeypatch.setattr(wing_solver_recipe,'demo_sweep',recipe)
    entries=driver.prepare_entries(recipe(),1000,64,.05)
    executor=install(monkeypatch,entries)
    monkeypatch.setattr(sys,'argv',['run_wing_sweep'])
    monkeypatch.delitem(sys.modules,'scripts.run_wing_sweep',raising=False)
    with pytest.raises(SystemExit) as result:
        runpy.run_module('scripts.run_wing_sweep',run_name='__main__')
    assert result.value.code==0
    report=json.loads(capsys.readouterr().out)
    assert 'details' not in report and report['records'][0]['state']=='completed'
    assert not executor.open
