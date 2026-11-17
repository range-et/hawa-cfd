"""Stationary mesh bridge admission, physical identity and cooperative ownership."""
from copy import deepcopy
import threading
import time

import numpy as np
import pytest

from hawa import stationary_study as module
from hawa.jobs import JOBS, dispatch_job
from hawa.fields import FRAMES, get
from hawa.plugin import SESSIONS, case_key


def box_mesh(low=(0., 0., 0.), high=(1., 1., 1.)):
    vertices = [[low[0], low[1], low[2]], [high[0], low[1], low[2]],
                [high[0], high[1], low[2]], [low[0], high[1], low[2]],
                [low[0], low[1], high[2]], [high[0], low[1], high[2]],
                [high[0], high[1], high[2]], [low[0], high[1], high[2]]]
    faces = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
             [0, 1, 5], [0, 5, 4], [3, 7, 6], [3, 6, 2],
             [0, 4, 7], [0, 7, 3], [1, 2, 6], [1, 6, 5]]
    return dict(vertices_m=vertices, triangles=faces)


def request():
    return dict(kind='stationary_study', device='cpu',
        case=dict(shape=[13, 11, 11], dx=.25, speed=1., viscosity=.1, density=1., mach=.01,
                  collision='bgk', boundaries=['inlet','outlet','slip','slip','slip','slip'],
                  solid=[], initial_velocity=[0.,0.,0.], origin=[-1., -1., -1.], basis=np.eye(3).tolist()),
        geometry=box_mesh((0.,-.25,-.25),(.5,.25,.25)),
        operating_points=[dict(angle_deg=0., speed_m_s=1.)],
        references=dict(area_m2=.25, chord_m=.5, pressure_pa=0.), pivot_world_m=[.25,0.,0.],
        probes=[dict(probe_id='upstream', position_world_m=[-.5,0.,0.])],
        settling_steps=0, sample_steps=4, stationarity_tolerance=.05, case_id='test',generation=3)


def finish(job):
    job.thread.join(20)
    assert not job.thread.is_alive()
    return job.snapshot(0)


def submit(data=None):
    response = dispatch_job(dict(op='evaluate_submit', **(request() if data is None else data)))
    return JOBS[response['job']]


def test_real_study_frame_load_probe_source_and_cleanup():
    before=set(SESSIONS)
    job=submit()
    try:
        result=finish(job)
        assert result['state']=='completed', result
        selected=result['result']['selected']
        assert 'last_field' not in selected
        assert selected['identity']['case_id']=='test'
        assert selected['identity']['generation']==3
        assert selected['candidate']['case_hash']==selected['identity']['case_hash']
        assert selected['geometry']==request()['geometry']
        record=result['result']['records'][0]
        assert record['state']=='completed'
        assert record['CM']==selected['summary']['bodies'][0]['mean']['Cm']
        assert len(selected['load_samples'])==len(selected['probe_samples'])==4
        frame=selected['frame'];arrays,meta=get(frame['frame'])
        assert meta['identity']==selected['identity']
        assert meta['iteration']==selected['load_samples'][-1]['step']==3
        assert meta['time']==selected['load_samples'][-1]['time_s']
        assert meta['phase']==selected['phase']==selected['probe_samples'][-1]['phase']
        assert meta['session']==selected['session']==meta['snapshot']['session']
        assert arrays['pressure'].shape==(13,11,11)
        assert not arrays['pressure'].flags.writeable
        assert result['cleanup']==dict(handles=0,live_workers=0,session_ids=[])
        assert set(SESSIONS)==before
        assert 'selected' not in dispatch_job(dict(op='evaluate_poll',job=job.id))['result']
        with pytest.raises(ValueError,match='index'):job.snapshot(True)
        selected['geometry']['vertices_m'].clear()
        assert job.snapshot(0)['result']['selected']['geometry']['vertices_m']
        # Surface-field queries consume the standard frame directly, without a live session.
        from hawa.fields import dispatch_field
        sample=dispatch_field(dict(op='field',action='sample',frame=frame['frame'],field='pressure',points=[[2.,4.,4.]]))
        assert sample['valid']==[True]
    finally:
        dispatch_job(dict(op='evaluate_control',job=job.id,action='close'))
    assert not job.frames and not job.details and frame['frame'] not in FRAMES
    assert dispatch_job(dict(op='evaluate_control',job=job.id,action='close'))=={'closed':True}


def test_rotation_hashes_and_matched_windows():
    data=request();data['operating_points'].append(dict(angle_deg=90.,speed_m_s=2.))
    data['settling_steps']=8
    module.validate_submission(data)
    entries=module.prepare(data,lambda _:None)
    a,b=entries.values()
    assert a['candidate']['geometry_hash']!=b['candidate']['geometry_hash']
    assert np.array(b['geometry']['vertices_m'])[0]==pytest.approx([0.,-.25,.25])
    assert b['candidate']['case_hash']==case_key(b['spec'])
    assert a['request']['references']['area_m2']==b['request']['references']['area_m2']==.25
    assert a['request']['window']['start_s']==2*b['request']['window']['start_s']


@pytest.mark.parametrize('change,match',[
    ({'extra':1},'fields'),({'device':'cuda'},'CPU'),({'kind':'query'},'CPU'),
    ({'case':{'solid':[1]}},'empty-solid'),({'case':{'collision':'kbc'}},'BGK'),
    ({'operating_points':[]},'1..64'),({'operating_points':[{}]},'Operating'),
    ({'references':{}},'References'),({'pivot_world_m':[0.]},'Pivot'),
    ({'settling_steps':-1},'settling'),({'sample_steps':True},'settling'),
    ({'stationarity_tolerance':-1},'nonnegative'),({'case_id':' '},'identity'),
    ({'generation':True},'Generation'),({'probes':None},'256'),
    ({'sample_steps':100000},'aggregate'),
])
def test_reject_submission(change,match):
    data=request();data.update(change)
    with pytest.raises(ValueError,match=match):module.validate_submission(data)


def test_reject_domain_geometry_and_probe_contracts():
    data=request();data['case']['basis'][0][0]=-1
    with pytest.raises(ValueError,match='axis-aligned'):module.validate_submission(data)
    data=request();data['case']['spacing']=100.
    with pytest.raises(ValueError,match='world metres'):module.validate_submission(data)
    data=request();data['geometry']['vertices_m']*=4000
    with pytest.raises(ValueError,match='mesh budget'):module.validate_submission(data)
    data=request();data['probes']*=2
    with pytest.raises(ValueError,match='unique'):module.validate_submission(data)
    data=request();data['probes']=[dict(probe_id='tap',position_world_m=[0.,0.,1.],body_id='body',surface_point_world_m=[0.,0.,0.],outward_normal_world=[0.,0.,1.],offset_m=1.)]
    with pytest.raises(ValueError,match='world-fixed'):module.validate_submission(data)


def test_pause_cancel_preparation_and_close(monkeypatch):
    entered=threading.Event();release=threading.Event()
    original=module.prepare
    def gated(data,checkpoint):
        entered.set();release.wait(5);return original(data,checkpoint)
    monkeypatch.setattr(module,'prepare',gated)
    job=submit();assert entered.wait(5)
    dispatch_job(dict(op='evaluate_control',job=job.id,action='pause'))
    release.set()
    deadline=time.monotonic()+5
    while job.snapshot()['state']!='paused' and time.monotonic()<deadline:time.sleep(.001)
    assert job.snapshot()['state']=='paused'
    dispatch_job(dict(op='evaluate_control',job=job.id,action='cancel'))
    assert finish(job)['state']=='cancelled'
    assert not job.details and not job.frames
    dispatch_job(dict(op='evaluate_control',job=job.id,action='close'))


def test_prepare_failure_is_retained_not_silent():
    data=request();data['geometry']['triangles'].pop()
    job=submit(data)
    try:
        result=finish(job)
        assert result['state']=='failed' and 'closed' in result['error']
        assert result['result'] is None and result['cleanup'] is None
    finally:dispatch_job(dict(op='evaluate_control',job=job.id,action='close'))


def test_missing_field_never_fabricates_snapshot():
    assert module.retain_frame({'last_field':None},{}) is None


def test_active_pause_resume_cancel_drains_worker(monkeypatch):
    import hawa.sweep_executor as execution
    entered=threading.Event();release=threading.Event()
    original=execution._Capture.__call__
    def gated(capture,flow):
        entered.set();release.wait(5)
        return original(capture,flow)
    monkeypatch.setattr(execution._Capture,'__call__',gated)
    data=request();data['sample_steps']=1000
    job=submit(data)
    try:
        assert entered.wait(5)
        job.control('pause')
        time.sleep(.03)
        assert job.snapshot()['state']=='pausing'
        release.set()
        deadline=time.monotonic()+5
        while job.snapshot()['state']!='paused' and time.monotonic()<deadline:time.sleep(.001)
        assert job.snapshot()['state']=='paused'
        job.control('resume')
        time.sleep(.03)
        job.control('cancel')
        result=finish(job)
        assert result['state']=='cancelled'
        assert result['result'] is None
        assert result['cleanup']==dict(handles=0,live_workers=0,session_ids=[])
        assert not job.frames and not job.details
    finally:
        release.set();job.control('close')
        JOBS.pop(job.id,None)


def test_control_race_during_capture_withholds_and_releases(monkeypatch):
    original=module.retain_frame
    def cancel_during_capture(detail,entry):
        frame=original(detail,entry)
        job.control('cancel')
        return frame
    monkeypatch.setattr(module,'retain_frame',cancel_during_capture)
    # Instantiate before starting to keep closure assignment deterministic.
    job=module.StationaryStudyJob(request());job.thread.start()
    result=finish(job)
    assert result['state']=='cancelled' and result['result'] is None
    assert not job.frames and not job.details


def test_controller_fault_drains_still_active_worker(monkeypatch):
    def failed_plot(records,name):
        raise RuntimeError('plot failure')
    monkeypatch.setattr(module,'plot_segments',failed_plot)
    job=submit()
    try:
        result=finish(job)
        assert result['state']=='failed' and result['error']=='plot failure'
        assert result['cleanup']==dict(handles=0,live_workers=0,session_ids=[])
    finally:dispatch_job(dict(op='evaluate_control',job=job.id,action='close'))
