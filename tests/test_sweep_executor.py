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


def wait_for(predicate, executor=None):
    deadline=time.monotonic()+10
    while not predicate():
        if executor is not None and not executor.audit()['live_workers']:
            pytest.fail('worker terminated before the expected observation')
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
    assert reply['reason'] == result['reason'] == ''
    assert result['schema']=='hawa-cpu-sweep-result-1'
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
    try:
        wait_for(entered.is_set, executor)
        executor.pause(handle)
        assert executor.audit()['session_ids']
        assert executor.poll(handle)['state']=='running'
        release.set()
        wait_for(lambda:executor.poll(handle)['state']=='paused', executor)
        with pytest.raises(ValueError,match='Close'):executor.start(data['a']['candidate'],7)
        executor.resume(handle)
        executor.cancel(handle)
        reply=finish(executor,handle)
        assert reply['state']=='cancelled' and reply['result'] is None
        assert executor.results('a',7)['state']=='cancelled'
    finally:
        release.set()
        executor.close(handle)



def test_close_requests_cancel_without_joining_running_worker(monkeypatch):
    entered,release=threading.Event(),threading.Event()
    original=module.Session.advance
    def gated(session,steps):
        entered.set();assert release.wait(10);return original(session,steps)
    monkeypatch.setattr(module.Session,'advance',gated)
    data=prepared();executor=CpuSweepExecutor(data);handle=executor.start(data['a']['candidate'],7)
    try:
        wait_for(entered.is_set, executor)
        assert executor.close(handle) is False
        assert executor.audit()['handles']==1 and executor.audit()['live_workers']==1
        release.set()
        assert finish(executor,handle)['state']=='cancelled'
    finally:
        release.set()
        executor.close(handle)



def test_cancel_before_session_creation(monkeypatch):
    entered,release=threading.Event(),threading.Event()
    original=module._Run.checkpoint
    def checkpoint(run):
        entered.set();assert release.wait(10);return original(run)
    monkeypatch.setattr(module._Run,'checkpoint',checkpoint)
    data=prepared();executor=CpuSweepExecutor(data);handle=executor.start(data['a']['candidate'],7)
    try:
        wait_for(entered.is_set, executor)
        executor.cancel(handle);release.set()
        assert finish(executor,handle)['state']=='cancelled'
        detail = executor.results('a', 7)
        assert_retained_envelope(detail, data['a'], 'cancelled', 'Sweep cancelled')
        assert detail['session'] is None
        assert detail['load_samples'] == detail['probe_samples'] == []
        assert all(detail[key] is None for key in ('summary', 'last_field', 'quality', 'final_quality'))
    finally:
        release.set()
        executor.close(handle)



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
    assert 'insufficient accepted window' in detail['reason']


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


def test_standalone_preparation_checks_its_own_envelope_and_steps():
    with pytest.raises(ValueError,match='fields'):
        module._prepare({})
    entry=prepared()['a'];entry['steps']=0
    with pytest.raises(ValueError,match='steps'):
        module._prepare(entry)


def test_translated_rotated_case_frame_matches_real_sampling():
    baseline=prepared();executor=CpuSweepExecutor(baseline)
    handle=executor.start(baseline['a']['candidate'],7);finish(executor,handle)
    original=executor.results('a',7)
    data=prepared();entry=data['a']
    basis=np.array([[0.,1.,0.],[-1.,0.,0.],[0.,0.,1.]])
    entry['spec'].update(origin=[2.,3.,4.],spacing=1.,basis=basis.tolist())
    origin=np.array([1.,1.5,2.]) # display origin * physical dx / display spacing
    entry['origin_world_m']=origin.tolist();entry['basis']=basis.tolist()
    entry['request']['references']['drag_axis_world']=basis[0].tolist()
    for probe in entry['probes']:
        probe['position_world_m']=(origin+np.asarray(probe['position_world_m'])@basis).tolist()
    entry['geometry']['vertices_m']=(origin+np.asarray(entry['geometry']['vertices_m'])@basis).tolist()
    gh=hashlib.sha256(json.dumps(entry['geometry'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    ch=case_key(entry['spec'])
    entry['candidate'].update(case_hash=ch,geometry_hash=gh)
    entry['request']['identity'].update(case_hash=ch,geometry_hash=gh)
    transformed=CpuSweepExecutor(data);handle=transformed.start(entry['candidate'],7)
    assert finish(transformed,handle)['state']=='completed'
    result=transformed.results('a',7)
    for before,after in zip(original['probe_samples'],result['probe_samples']):
        assert before['pressure_pa']==after['pressure_pa'] and before['valid']==after['valid']
    for before,after in zip(original['load_samples'],result['load_samples']):
        np.testing.assert_allclose(after['force_world_n'],np.asarray(before['force_world_n'])@basis,atol=1e-12,rtol=1e-12)


def test_terminal_result_does_not_release_a_still_live_worker(monkeypatch):
    """Publication is not worker exit; close must preserve completed data."""
    published, release = threading.Event(), threading.Event()
    original = module.CpuSweepExecutor._work
    def delayed_exit(executor, run):
        original(executor, run)
        published.set()
        assert release.wait(10)
    monkeypatch.setattr(module.CpuSweepExecutor, '_work', delayed_exit)
    data = prepared()
    executor = CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    try:
        wait_for(published.is_set, executor)
        assert executor.poll(handle)['state'] == 'completed'
        assert executor.close(handle) is False
        assert executor.audit() == dict(handles=1, live_workers=1, session_ids=[])
        with pytest.raises(ValueError, match='Close'):
            executor.start(data['a']['candidate'], 7)
        assert executor.results('a', 7)['summary']['usable']
    finally:
        release.set()
        wait_for(lambda: not executor.audit()['live_workers'])
        assert executor.close(handle)
    assert executor.results('a', 7)['state'] == 'completed'
    assert executor.audit() == dict(handles=0, live_workers=0, session_ids=[])


def assert_retained_envelope(detail, entry, state, reason):
    """A failed/cancelled run remains inspectable by the same consumer as success."""
    assert set(detail) == {'schema', 'candidate', 'identity', 'dtype', 'device', 'phase',
                           'load_samples', 'probe_samples', 'summary', 'last_field',
                           'quality', 'session', 'provenance', 'state', 'reason', 'final_quality'}
    assert detail['schema'] == 'hawa-cpu-sweep-result-1'
    assert detail['candidate'] == entry['candidate']
    assert detail['identity'] == entry['request']['identity']
    assert detail['provenance'] == dict(session=detail['session'], phase=PHASE,
                                      identity=entry['request']['identity'])
    assert (detail['device'], detail['dtype'], detail['phase']) == ('cpu', 'float32', PHASE)
    assert (detail['state'], detail['reason']) == (state, reason)


def test_failure_before_session_has_complete_detached_result(monkeypatch):
    def unavailable(*args):
        raise RuntimeError('CPU allocation unavailable')
    monkeypatch.setattr(module, 'Session', unavailable)
    data = prepared(); executor = CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    reply = finish(executor, handle)
    detail = executor.results('a', 7)
    assert_retained_envelope(detail, data['a'], 'failed', 'CPU allocation unavailable')
    assert reply['result'] is None
    assert detail['load_samples'] == detail['probe_samples'] == []
    for key in ('session', 'summary', 'last_field', 'quality', 'final_quality'):
        assert detail[key] is None
    detail['candidate']['angle_deg'] = 90
    detail['provenance']['identity']['case_id'] = 'changed'
    assert_retained_envelope(executor.results('a', 7), data['a'], 'failed', reply['reason'])


@pytest.mark.parametrize('generation', [0, 1])
def test_generation_boundary_runs_but_numeric_lookalikes_do_not(generation):
    data = prepared(); data['a']['request']['identity']['generation'] = generation
    executor = CpuSweepExecutor(data)
    for invalid in (float(generation), bool(generation), str(generation), None):
        unexpected_handle = None
        try:
            with pytest.raises(ValueError):
                unexpected_handle = executor.start(data['a']['candidate'], invalid)
        finally:
            if unexpected_handle is not None:
                executor.cancel(unexpected_handle)
                finish(executor, unexpected_handle)
        assert executor.audit()['handles'] == 0
    handle = executor.start(data['a']['candidate'], generation)
    assert finish(executor, handle)['state'] == 'completed'
    assert executor.results('a', generation)['identity']['generation'] == generation


@pytest.mark.parametrize('status', ['within-tested-envelope', 'warning', 'rejected'])
def test_capture_quality_and_provenance_are_retained_for_every_observation(monkeypatch, status):
    original = module.assess
    def quality(session):
        result = original(session)
        result['status'] = status
        result['independent_marker'] = {'source_step': session.flow.i}
        return result
    monkeypatch.setattr(module, 'assess', quality)
    data = prepared(); executor = CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    reply = finish(executor, handle)
    detail = executor.results('a', 7)
    assert_retained_envelope(detail, data['a'], reply['state'], reply['reason'])
    expected = 'accepted' if status == 'within-tested-envelope' else status
    assert len(detail['load_samples']) == 4
    assert len(detail['probe_samples']) == 8
    for sample in detail['load_samples'] + detail['probe_samples']:
        assert sample['identity'] == data['a']['request']['identity']
        assert sample['quality'] == expected
        assert sample['time_s'] == pytest.approx(sample['step'] * .01 * .5 / math.sqrt(3), abs=1e-14)
    for sample in detail['probe_samples']:
        assert sample['source_quality']['status'] == status
        assert sample['source_quality']['independent_marker'] == {'source_step': sample['step']}
    assert detail['quality']['status'] == status
    assert detail['quality']['independent_marker'] == {'source_step': 3}
    assert detail['last_field']['snapshot']['phase'] == PHASE


@pytest.mark.parametrize('status', ['warning', 'rejected'])
def test_final_advance_quality_can_veto_accepted_capture(monkeypatch, status):
    original = module.Session.advance
    def advance(session, steps):
        result = original(session, steps)
        if session.flow.i == 4:
            session.quality['status'] = status
        return result
    monkeypatch.setattr(module.Session, 'advance', advance)
    data = prepared(); executor = CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    reply = finish(executor, handle)
    detail = executor.results('a', 7)
    assert detail['summary']['usable']
    assert detail['quality']['status'] == 'within-tested-envelope'
    assert detail['final_quality']['status'] == status
    assert reply['result']['quality'] == status


@pytest.mark.parametrize('offset', [1e-7, .1])
def test_pressure_time_mismatch_with_matching_step_fails(monkeypatch, offset):
    original = module.Session.fields
    def fields(session, *args, **kwargs):
        result = original(session, *args, **kwargs)
        if result['snapshot']['steps'] == 1:
            result['snapshot']['physical_time'] += offset
        return result
    monkeypatch.setattr(module.Session, 'fields', fields)
    data = prepared(); executor = CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    reply = finish(executor, handle)
    assert reply['state'] == 'failed'
    assert 'phase identity mismatch' in reply['reason']
    detail = executor.results('a', 7)
    assert [s['step'] for s in detail['load_samples']] == [0]
    assert [s['step'] for s in detail['probe_samples']] == [0, 0]


@pytest.mark.parametrize('field,value', [
    ('vertices_m', [[0., 0., 0.]] * 3),
    ('triangles', [[0, 1, 2]] * 3),
    ('vertex', [0., 0.]), ('vertex', (0., 0., 0.)),
    ('vertex', [True, 0., 0.]), ('vertex', ['0', 0., 0.]),
    ('vertex', [float('inf'), 0., 0.]), ('vertex', [float('nan'), 0., 0.]),
    ('triangle', [0, 1, 4]), ('triangle', [-1, 1, 2]),
    ('triangle', [False, 1, 2]), ('triangle', [0., 1, 2]),
    ('triangle', [0, 1, 2, 0]), ('triangle', (0, 1, 2)),
])
def test_geometry_admission_rejects_invalid_content_even_with_matching_hash(field, value):
    data = prepared(); entry = data['a']; geometry = entry['geometry']
    if field == 'vertex':
        geometry['vertices_m'][0] = value
    elif field == 'triangle':
        geometry['triangles'][0] = value
    else:
        geometry[field] = value
    # Match the caller's hash deliberately: validation must reject the content itself.
    digest = hashlib.sha256(json.dumps(geometry, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    entry['candidate']['geometry_hash'] = digest
    entry['request']['identity']['geometry_hash'] = digest
    with pytest.raises(ValueError):
        CpuSweepExecutor(data)


@pytest.mark.parametrize('resource', ['rows', 'cells', 'vertices', 'faces'])
def test_aggregate_budget_includes_every_candidate_at_exact_limit(resource):
    data = prepared(); first = data['a']; second = deepcopy(first)
    data['b'] = second
    for entry in data.values():
        entry['probes'] = []
    if resource == 'rows':
        first['steps'] = second['steps'] = 50000
    elif resource == 'cells':
        first['spec']['shape'] = second['spec']['shape'] = [100, 100, 75]
    elif resource == 'vertices':
        first['geometry']['vertices_m'] = second['geometry']['vertices_m'] = [[0., 0., 0.]] * 100000
    else:
        first['geometry']['triangles'] = second['geometry']['triangles'] = [[0, 1, 2]] * 200000
    # This pre-copy guard deliberately does not inspect mesh or solver validity.
    module._budget(data)
    if resource == 'rows':
        second['steps'] += 1
    elif resource == 'cells':
        second['spec']['shape'] = [100, 100, 76]
    elif resource == 'vertices':
        second['geometry']['vertices_m'] = second['geometry']['vertices_m'] + [[0., 0., 0.]]
    else:
        second['geometry']['triangles'] = second['geometry']['triangles'] + [[0, 1, 2]]
    with pytest.raises(ValueError, match='aggregate'):
        module._budget(data)


def test_aggregate_row_budget_counts_bodies_and_probes():
    data = prepared(); entry = data['a']
    entry['steps'] = 25000
    entry['body_indices']['second'] = []
    module._budget(data)  # 25000 * (2 bodies + 2 probes) == 100000.
    entry['steps'] += 1
    with pytest.raises(ValueError, match='aggregate'):
        module._budget(data)


def test_nonzero_settling_window_and_default_mach_admission():
    data = prepared(); entry = data['a']
    del entry['spec']['mach']
    ch = case_key(entry['spec'])
    entry['candidate']['case_hash'] = entry['request']['identity']['case_hash'] = ch
    dt = .05 * .5 / math.sqrt(3)
    entry['steps'] = 6
    entry['request']['window'].update(start_s=2*dt, end_s=5*dt)
    executor = CpuSweepExecutor(data)
    handle = executor.start(entry['candidate'], 7)
    assert finish(executor, handle)['state'] == 'completed'
    detail = executor.results('a', 7)
    assert len(detail['load_samples']) == 6
    assert detail['load_samples'][-1]['time_s'] == pytest.approx(5*dt)
    for start, end in ((2, 6), (2, 4), (2.1, 5), (2, 5.1)):
        invalid = deepcopy(data)
        invalid['a']['request']['window'].update(start_s=start*dt, end_s=end*dt)
        with pytest.raises(ValueError):
            CpuSweepExecutor(invalid)


def test_maximum_probe_count_is_admitted_without_starting_worker():
    data = prepared()
    data['a']['probes'] = [dict(probe_id=str(i), position_world_m=[1., 2., 2.]) for i in range(256)]
    executor = CpuSweepExecutor(data)
    assert executor.audit() == dict(handles=0, live_workers=0, session_ids=[])


@pytest.mark.parametrize('field', ['origin', 'basis', 'drag'])
@pytest.mark.parametrize('offset,accepted', [(5e-11, True), (2e-10, False), (1e-7, False)])
def test_frame_and_drag_use_absolute_tolerance_at_nonzero_coordinates(field, offset, accepted):
    data = prepared(); entry = data['a']
    def rotation(angle):
        c, s = math.cos(angle), math.sin(angle)
        return [[c, s, 0.], [-s, c, 0.], [0., 0., 1.]]
    basis = rotation(.4)
    entry['spec'].update(origin=[4., 6., 8.], spacing=1., basis=basis)
    entry['origin_world_m'] = [2., 3., 4.]
    entry['basis'] = deepcopy(basis)
    entry['request']['references']['drag_axis_world'] = basis[0]
    digest = case_key(entry['spec'])
    entry['candidate']['case_hash'] = entry['request']['identity']['case_hash'] = digest
    if field == 'origin':
        entry['origin_world_m'][0] += offset
    elif field == 'basis':
        entry['basis'] = rotation(.4 + offset)
        entry['request']['references']['drag_axis_world'] = entry['basis'][0]
    else:
        entry['request']['references']['drag_axis_world'] = rotation(.4 + offset)[0]
    if accepted:
        executor = CpuSweepExecutor(data)
        assert executor.audit() == dict(handles=0, live_workers=0, session_ids=[])
    else:
        with pytest.raises(ValueError, match='Drag axis' if field == 'drag' else 'Measurement frame'):
            CpuSweepExecutor(data)


@pytest.mark.parametrize('field,value', [
    ('shape', (12, 9, 9)), ('shape', [12, 9]), ('shape', [12., 9, 9]),
    ('shape', [True, 9, 9]), ('shape', [3, 9, 9]),
    ('spec', []), ('geometry', []), ('body_indices', []), ('probes', ()),
    ('vertices_m', ()), ('triangles', ()),
    ('steps', 4.), ('steps', True), ('steps', 3), ('steps', 100001),
])
def test_malformed_resource_collections_rejected_before_deepcopy(monkeypatch, field, value):
    data = prepared(); entry = data['a']
    if field == 'shape':
        entry['spec'][field] = value
    elif field in ('vertices_m', 'triangles'):
        entry['geometry'][field] = value
    else:
        entry[field] = value
    def forbidden_copy(*args, **kwargs):
        pytest.fail('resource envelope must be rejected before copying payloads')
    monkeypatch.setattr(module, 'deepcopy', forbidden_copy)
    with pytest.raises(ValueError):
        CpuSweepExecutor(data)


def test_budget_admits_minimum_shape_without_copying_or_running_solver(monkeypatch):
    data = prepared(); data['a']['spec']['shape'] = [4, 4, 4]
    def forbidden_copy(*args, **kwargs):
        pytest.fail('budget inspection must not copy payloads')
    monkeypatch.setattr(module, 'deepcopy', forbidden_copy)
    module._budget(data)


def test_unknown_entry_field_rejected_before_copy(monkeypatch):
    data = prepared(); data['a']['unexpected'] = 'untrusted payload'
    def forbidden(*args):
        pytest.fail('unknown envelope reached deepcopy')
    monkeypatch.setattr(module, 'deepcopy', forbidden)
    with pytest.raises(ValueError) as exc:
        CpuSweepExecutor(data)
    assert str(exc.value) and str(exc.value) != 'None'


def test_exact_step_limit_without_worker_allocation():
    data = prepared(); data['a'].update(steps=100000, probes=[])
    executor = CpuSweepExecutor(data)
    assert executor.audit()['handles'] == 0
    data['a']['steps'] = 100001
    with pytest.raises(ValueError):
        CpuSweepExecutor(data)


def test_aggregate_cell_budget_rejects_single_cell_over_limit():
    data = prepared(); data['b'] = deepcopy(data['a'])
    data['a']['spec']['shape'] = [4, 7, 53567]
    data['b']['spec']['shape'] = [5, 5, 5]
    assert 4*7*53567 + 5*5*5 == 1500001
    with pytest.raises(ValueError):
        module._budget(data)


def test_unknown_geometry_field_rejected_even_with_matching_digest():
    data = prepared(); entry = data['a']; entry['geometry']['extra'] = 'untrusted'
    digest = hashlib.sha256(json.dumps(entry['geometry'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    entry['candidate']['geometry_hash'] = entry['request']['identity']['geometry_hash'] = digest
    with pytest.raises(ValueError) as exc:
        CpuSweepExecutor(data)
    assert str(exc.value) and str(exc.value) != 'None'


@pytest.mark.parametrize('field,count', [('vertices_m', 200000), ('triangles', 400000)])
def test_geometry_hash_accepts_exact_upper_count_without_solver(field, count):
    geometry = prepared()['a']['geometry']
    geometry[field] = (geometry[field] * (count // len(geometry[field])))
    expected = hashlib.sha256(json.dumps(geometry, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert module._geometry_hash(geometry) == expected
    geometry[field].append(geometry[field][0])
    with pytest.raises(ValueError):
        module._geometry_hash(geometry)


def test_geometry_vertex_lower_bound_is_independent_of_triangle_count():
    geometry = dict(vertices_m=[[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]],
                    triangles=[[0, 1, 2]] * 4)
    with pytest.raises(ValueError):
        module._geometry_hash(geometry)


def test_candidate_count_limit_with_real_budget_and_preparation():
    data = {}
    for i in range(64):
        entry = prepared()['a']; key = str(i)
        entry['candidate']['candidate_id'] = entry['request']['identity']['candidate_id'] = key
        data[key] = entry
    executor = CpuSweepExecutor(data)
    assert executor.audit()['handles'] == 0
    data['64'] = deepcopy(data['0'])
    data['64']['candidate']['candidate_id'] = data['64']['request']['identity']['candidate_id'] = '64'
    with pytest.raises(ValueError):
        CpuSweepExecutor(data)


def test_worker_thread_is_daemon_and_owns_target(monkeypatch):
    captured = []
    class ThreadSpy:
        def __init__(self, **kwargs):
            captured.append(kwargs)
        def start(self):
            pass
        def is_alive(self):
            return False
    monkeypatch.setattr(module.threading, 'Thread', ThreadSpy)
    data = prepared(); executor = CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    try:
        assert len(captured) == 1
        assert captured[0]['daemon'] is True
        assert captured[0]['target'] == executor._work
        assert len(captured[0]['args']) == 1
    finally:
        assert executor.close(handle)


@pytest.mark.parametrize('source_step,offset,accepted', [(0, 5e-13, True), (1, 2e-12, False)])
def test_capture_timestamp_tolerance_is_strict_and_has_absolute_floor(monkeypatch, source_step, offset, accepted):
    original = module.Session.fields
    def fields(session, *args, **kwargs):
        result = original(session, *args, **kwargs)
        if result['snapshot']['steps'] == source_step:
            result['snapshot']['physical_time'] += offset
        return result
    monkeypatch.setattr(module.Session, 'fields', fields)
    data = prepared(); executor = CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    reply = finish(executor, handle)
    assert reply['state'] == ('completed' if accepted else 'failed')
    if not accepted:
        assert 'phase identity mismatch' in reply['reason']


def test_near_zero_window_endpoint_uses_absolute_alignment_tolerance():
    data = prepared(); dt = .01 * .5 / math.sqrt(3)
    data['a']['request']['window']['start_s'] = 5e-13 * dt
    assert CpuSweepExecutor(data).audit()['handles'] == 0
    data['a']['request']['window']['start_s'] = 2e-12 * dt
    with pytest.raises(ValueError):
        CpuSweepExecutor(data)


def test_worker_selects_obstacle_among_nonmatching_domain_bounceback_masks():
    data = prepared(); entry = data['a']
    entry['spec']['boundaries'] = ['inlet', 'outlet', 'wall', 'wall', 'wall', 'wall']
    digest = case_key(entry['spec'])
    entry['candidate']['case_hash'] = entry['request']['identity']['case_hash'] = digest
    executor = CpuSweepExecutor(data)
    handle = executor.start(entry['candidate'], 7)
    reply = finish(executor, handle)
    assert reply['state'] == 'completed', reply['reason']
    assert len(executor.results('a', 7)['load_samples']) == 4


def test_last_source_step_admission_includes_exact_roundoff_allowance():
    data = prepared()
    dt = .01 * .5 / math.sqrt(3)
    limit = 3 + 1e-9
    end = limit * dt
    assert end / dt == limit
    data['a']['request']['window']['end_s'] = end
    executor = CpuSweepExecutor(data)
    assert executor.audit() == dict(handles=0, live_workers=0, session_ids=[])
    data['a']['request']['window']['end_s'] = math.nextafter(end, math.inf)
    assert data['a']['request']['window']['end_s'] / dt > limit
    with pytest.raises(ValueError, match='window'):
        CpuSweepExecutor(data)


def test_queued_observation_is_valid_before_worker_allocates(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = CpuSweepExecutor._work

    def gated(executor, run):
        entered.set()
        assert release.wait(5)
        return original(executor, run)

    monkeypatch.setattr(CpuSweepExecutor, '_work', gated)
    data = prepared(); executor = CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    try:
        wait_for(entered.is_set, executor)
        assert executor.poll(handle) == dict(state='queued', candidate_id='a',
                                             generation=7, reason='', result=None)
        assert executor.audit() == dict(handles=1, live_workers=1, session_ids=[])
        assert executor.results('a', 7) is None
    finally:
        executor.cancel(handle)
        release.set()
        finish(executor, handle)


def test_failure_before_first_capture_preserves_nullable_observations(monkeypatch):
    def fail_before_capture(session, steps):
        raise RuntimeError('first numerical step failed')

    monkeypatch.setattr(module.Session, 'advance', fail_before_capture)
    data = prepared(); executor = CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    reply = finish(executor, handle)
    assert reply['state'] == 'failed'
    result = executor.results('a', 7)
    assert_retained_envelope(result, data['a'], 'failed', 'first numerical step failed')
    assert result['session']
    assert result['last_field'] is None and result['quality'] is None
    assert result['summary'] is None
    assert result['load_samples'] == result['probe_samples'] == []


def test_cancel_after_last_capture_does_not_publish_a_success_summary(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = module.Session.advance

    def gate_last_step(session, steps):
        result = original(session, steps)
        if session.flow.i == 4:
            entered.set()
            assert release.wait(5)
        return result

    monkeypatch.setattr(module.Session, 'advance', gate_last_step)
    data = prepared(); executor = CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    try:
        wait_for(entered.is_set, executor)
        executor.cancel(handle)
        release.set()
        reply = finish(executor, handle)
        assert reply['state'] == 'cancelled' and reply['result'] is None
        result = executor.results('a', 7)
        assert result['summary'] is None
        assert len(result['load_samples']) == 4
        assert len(result['probe_samples']) == 8
    finally:
        release.set()
        if executor.audit()['handles']:
            executor.cancel(handle)
            finish(executor, handle)
