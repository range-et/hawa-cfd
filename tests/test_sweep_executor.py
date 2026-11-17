"""Actual CPU sessions plus deterministic worker lifecycle fault injection."""
from copy import deepcopy
import hashlib
import json
import math
import threading
import time

import numpy as np
import pytest

import hawa.sweep_executor as module
from hawa.plugin import case_key, SESSIONS
from hawa.sweep_executor import CpuSweepExecutor, PHASE


def prepared():
    shape = [12,9,9]
    indices = [int(np.ravel_multi_index((x,y,z),shape)) for x in (5,6) for y in (3,4) for z in (3,4)]
    spec = dict(shape=shape,dx=.5,speed=1.,viscosity=.1,density=2.,collision='bgk',mach=.01,
                initial_velocity=[0.,0.,0.],boundaries=['inlet','outlet','slip','slip','slip','slip'],solid=indices)
    geometry=dict(vertices_m=[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]],triangles=[[0,1,2],[0,1,3],[0,2,3],[1,2,3]])
    gh=hashlib.sha256(json.dumps(geometry,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    ch=case_key(spec)
    candidate=dict(candidate_id='a',angle_deg=0.,speed_m_s=1.,geometry_hash=gh,case_hash=ch)
    request=dict(schema='hawa-measurement-1',identity=dict(case_id='fixture',candidate_id='a',case_hash=ch,geometry_hash=gh,revision=0,generation=7),
                 references=dict(density_kg_m3=2.,speed_m_s=1.,area_m2=1.,chord_m=1.,pressure_pa=0.,drag_axis_world=[1.,0.,0.],lift_axis_world=[0.,0.,1.]),
                 bodies=[dict(body_id='wing',moment_origin_world_m=[0.,0.,0.])],
                 window=dict(start_s=0.,end_s=3*.01*.5/math.sqrt(3),minimum_samples=4,stationarity_absolute_coefficient_tolerance=.01))
    entry=dict(candidate=candidate,spec=spec,body_indices=dict(wing=indices),request=request,
               probes=[dict(probe_id='fluid',position_world_m=[1.,2.,2.]),dict(probe_id='invalid',position_world_m=[-10.,0.,0.])],
               origin_world_m=[0.,0.,0.],basis=np.eye(3).tolist(),steps=4,selected_body_id='wing',dtype='float32',geometry=geometry)
    return {'a':entry}


def wait_for(predicate):
    deadline=time.monotonic()+10
    while not predicate():
        if time.monotonic()>deadline:pytest.fail('worker did not reach expected state')
        time.sleep(.001)


def finish(executor,handle):
    wait_for(lambda:not executor.audit()['live_workers'])
    reply=executor.poll(handle)
    assert executor.close(handle)
    return reply


def test_real_cpu_result_keeps_aligned_observations_after_close():
    data=prepared();executor=CpuSweepExecutor(data)
    before=set(SESSIONS)
    handle=executor.start(data['a']['candidate'],7)
    reply=finish(executor,handle)
    assert reply['state']=='completed'
    result=executor.results('a',7)
    assert result['session'] and result['device']=='cpu' and result['dtype']=='float32'
    assert result['summary']['usable']
    assert [s['step'] for s in result['load_samples']]==[0,1,2,3]
    assert result['last_field']['snapshot']['steps']==3
    assert result['last_field']['snapshot']['session']==result['session']
    assert result['provenance']['phase']==PHASE
    assert all(p['phase']==PHASE and p['session']==result['session'] for p in result['probe_samples'])
    assert [p['valid'] for p in result['probe_samples']]==[True,False]*4
    assert result['probe_samples'][-1]['Cp'] is None
    result['load_samples'].clear()
    assert len(executor.results('a',7)['load_samples'])==4
    assert executor.results('never-started',7) is None
    assert executor.audit()==dict(handles=0,live_workers=0,session_ids=[])
    assert set(SESSIONS)==before
    assert executor.close(handle)
    with pytest.raises(ValueError):executor.poll(handle)
    with pytest.raises(ValueError):executor.start(data['a']['candidate'],7)


def test_empty_probes_and_detached_preparation():
    data=prepared();data['a']['probes']=[]
    executor=CpuSweepExecutor(data)
    candidate=deepcopy(data['a']['candidate'])
    data['a']['spec']['solid'].clear()
    handle=executor.start(candidate,7)
    assert finish(executor,handle)['state']=='completed'
    assert executor.results('a',7)['probe_samples']==[]


def test_pause_ack_resume_cancel_and_retained_worker_ownership(monkeypatch):
    entered,release=threading.Event(),threading.Event()
    original=module.Session.advance
    def gated(session,steps):
        entered.set()
        assert release.wait(10)
        return original(session,steps)
    monkeypatch.setattr(module.Session,'advance',gated)
    data=prepared();executor=CpuSweepExecutor(data)
    handle=executor.start(data['a']['candidate'],7)
    assert entered.wait(10)
    executor.pause(handle)
    assert executor.audit()['session_ids']
    assert executor.poll(handle)['state']=='running'
    release.set()
    wait_for(lambda:executor.poll(handle)['state']=='paused')
    with pytest.raises(ValueError,match='Close'):executor.start(data['a']['candidate'],7)
    executor.resume(handle)
    executor.cancel(handle)
    reply=finish(executor,handle)
    assert reply['state']=='cancelled' and reply['result'] is None
    assert executor.results('a',7)['state']=='cancelled'


def test_close_requests_cancel_without_joining_running_worker(monkeypatch):
    entered,release=threading.Event(),threading.Event()
    original=module.Session.advance
    def gated(session,steps):
        entered.set();assert release.wait(10);return original(session,steps)
    monkeypatch.setattr(module.Session,'advance',gated)
    data=prepared();executor=CpuSweepExecutor(data);handle=executor.start(data['a']['candidate'],7)
    assert entered.wait(10)
    assert executor.close(handle) is False
    assert executor.audit()['handles']==1 and executor.audit()['live_workers']==1
    release.set()
    assert finish(executor,handle)['state']=='cancelled'


def test_cancel_before_session_creation(monkeypatch):
    entered,release=threading.Event(),threading.Event()
    original=module._Run.checkpoint
    def checkpoint(run):
        entered.set();assert release.wait(10);return original(run)
    monkeypatch.setattr(module._Run,'checkpoint',checkpoint)
    data=prepared();executor=CpuSweepExecutor(data);handle=executor.start(data['a']['candidate'],7)
    assert entered.wait(10)
    executor.cancel(handle);release.set()
    assert finish(executor,handle)['state']=='cancelled'
    assert executor.results('a',7)['session'] is None


def test_thread_start_failure_retains_no_resources(monkeypatch):
    data=prepared();executor=CpuSweepExecutor(data)
    def fail(thread):raise RuntimeError('start fault')
    monkeypatch.setattr(threading.Thread,'start',fail)
    with pytest.raises(RuntimeError,match='start fault'):executor.start(data['a']['candidate'],7)
    assert executor.audit()==dict(handles=0,live_workers=0,session_ids=[])


@pytest.mark.parametrize('generation',[True,-1,8])
def test_generation_mismatch(generation):
    data=prepared();executor=CpuSweepExecutor(data)
    with pytest.raises(ValueError):executor.start(data['a']['candidate'],generation)


def test_changed_candidate_refused_before_thread():
    data=prepared();executor=CpuSweepExecutor(data)
    candidate=deepcopy(data['a']['candidate']);candidate['angle_deg']=1.
    with pytest.raises(ValueError):executor.start(candidate,7)
    with pytest.raises(ValueError):executor.close('unknown')
    assert executor.audit()['handles']==0


@pytest.mark.parametrize('change', ['map','keys','dtype','geometry_keys','geometry_empty','vertices','faces',
    'hash','request_hash','speed','reference_speed','density','drag','selected','body','steps',
    'probes','probe_budget','duplicate_probe','window','few_samples','dt'])
def test_preparation_rejects_before_allocation(change,monkeypatch):
    data=prepared();entry=data['a']
    if change=='map':data={'wrong':entry}
    if change=='keys':entry['unknown']=True
    if change=='dtype':entry['dtype']='float64'
    if change=='geometry_keys':entry['geometry']['foo']=1
    if change=='geometry_empty':entry['geometry']['vertices_m']=[]
    if change=='vertices':entry['geometry']['vertices_m'][0][0]=True
    if change=='faces':entry['geometry']['triangles'][0]=[0,0,1]
    if change=='hash':entry['candidate']['case_hash']='bad'
    if change=='request_hash':entry['request']['identity']['geometry_hash']='bad'
    if change=='speed':entry['candidate']['speed_m_s']=2.
    if change=='reference_speed':entry['request']['references']['speed_m_s']=2.
    if change=='density':entry['request']['references']['density_kg_m3']=3.
    if change=='drag':entry['request']['references'].update(drag_axis_world=[0.,1.,0.])
    if change=='selected':entry['selected_body_id']='missing'
    if change=='body':entry['request']['bodies'][0]['body_id']='missing'
    if change=='steps':entry['steps']=True
    if change=='probes':entry['probes']={}
    if change=='probe_budget':entry['steps']=100000
    if change=='duplicate_probe':entry['probes']*=2
    if change=='window':entry['request']['window']['end_s']*=1.1
    if change=='few_samples':entry['request']['window']['minimum_samples']=5
    if change=='dt':
        monkeypatch.setattr(module,'check_case',lambda spec:None)
        entry['spec']['mach']=0.
        entry['candidate']['case_hash']=case_key(entry['spec'])
        entry['request']['identity']['case_hash']=entry['candidate']['case_hash']
    def no_session(*args):pytest.fail('invalid preflight allocated Session')
    monkeypatch.setattr(module,'Session',no_session)
    with pytest.raises(ValueError):CpuSweepExecutor(data)


def test_empty_map_refused():
    with pytest.raises(ValueError):CpuSweepExecutor({})


def test_real_warning_is_retained(monkeypatch):
    original=module.assess
    def warning(session):
        result=original(session);result['status']='warning';return result
    monkeypatch.setattr(module,'assess',warning)
    data=prepared();executor=CpuSweepExecutor(data);handle=executor.start(data['a']['candidate'],7)
    result=finish(executor,handle)
    assert result['state']=='completed' and result['result']['quality']=='warning'
    assert not executor.results('a',7)['summary']['usable']


def test_rejected_window_keeps_raw_data(monkeypatch):
    def reject(request,samples):raise ValueError('insufficient accepted window')
    monkeypatch.setattr(module,'summarize',reject)
    data=prepared();executor=CpuSweepExecutor(data);handle=executor.start(data['a']['candidate'],7)
    assert finish(executor,handle)['state']=='rejected'
    detail=executor.results('a',7)
    assert detail['summary'] is None and len(detail['load_samples'])==4


def test_solver_failure_stays_failed_with_partial_history(monkeypatch):
    original=module.Session.advance
    def fail(session,steps):
        original(session,steps)
        raise RuntimeError('worker fault')
    monkeypatch.setattr(module.Session,'advance',fail)
    data=prepared();executor=CpuSweepExecutor(data);handle=executor.start(data['a']['candidate'],7)
    reply=finish(executor,handle)
    assert reply['state']=='failed' and reply['reason']=='worker fault'
    assert len(executor.results('a',7)['load_samples'])==1


def test_missing_obstacle_boundary_fails_owned_worker(monkeypatch):
    original=module.Session
    def missing(*args):
        session=original(*args);session.solver.post_boundaries=[];return session
    monkeypatch.setattr(module,'Session',missing)
    data=prepared();executor=CpuSweepExecutor(data);handle=executor.start(data['a']['candidate'],7)
    assert 'exactly one' in finish(executor,handle)['reason']


def test_capture_time_mismatch_fails_before_publishing(monkeypatch):
    original=module.Session.fields
    def fields(session,*args,**kwargs):
        result=original(session,*args,**kwargs);result['snapshot']['steps']+=1;return result
    monkeypatch.setattr(module.Session,'fields',fields)
    data=prepared();executor=CpuSweepExecutor(data);handle=executor.start(data['a']['candidate'],7)
    assert 'phase identity mismatch' in finish(executor,handle)['reason']


@pytest.mark.parametrize('change',['shape','case','geometry','frame','total_rows','total_cells','total_vertices','total_faces'])
def test_aggregate_budget_and_frame_precede_worker_allocation(change):
    data=prepared();entry=data['a']
    if change=='shape':entry['spec']['shape']=[4]
    if change=='case':entry['spec']=[]
    if change=='geometry':entry['geometry']=[]
    if change=='frame':entry['origin_world_m']=[1.,0.,0.]
    if change=='total_rows':entry['steps']=100000
    if change=='total_cells':entry['spec']['shape']=[200,200,200]
    if change=='total_vertices':entry['geometry']['vertices_m']=[[0.,0.,0.]]*200001
    if change=='total_faces':entry['geometry']['triangles']=[[0,1,2]]*400001
    with pytest.raises(ValueError):CpuSweepExecutor(data)


def test_probe_per_candidate_limit_is_enforced():
    data=prepared();data['a']['probes']=[dict(probe_id=str(i),position_world_m=[0.,0.,0.]) for i in range(257)]
    with pytest.raises(ValueError,match='Probe capture'):CpuSweepExecutor(data)
