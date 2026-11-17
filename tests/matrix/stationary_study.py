"""Bounded study products with explicit independent supported-operation oracle."""
import itertools
import math

import numpy as np


def stationary_study_cases():
    for angle, speed, selection, device in itertools.product((-10.,10.),(.5,1.),(0,1),('cpu','mps','cuda:0')):
        yield dict(id='stationary-study/angle-{}/speed-{}/selection-{}/{}'.format(angle,speed,selection,device),
                   angle=angle,speed=speed,selection=selection,device=device,mode='run',
                   expected=device=='cpu' and selection==0)
    for mode,device in itertools.product(('open-mesh','rotated-domain','cancel'),('cpu','mps','cuda:0')):
        yield dict(id='stationary-study/'+mode+'/'+device,angle=0.,speed=1.,selection=0,
                   device=device,mode=mode,expected=False)


def study_request(row):
    vertices=[[0.,-.25,-.25],[.5,-.25,-.25],[.5,.25,-.25],[0.,.25,-.25],
              [0.,-.25,.25],[.5,-.25,.25],[.5,.25,.25],[0.,.25,.25]]
    faces=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
           [3,7,6],[3,6,2],[0,4,7],[0,7,3],[1,2,6],[1,6,5]]
    return dict(kind='stationary_study', device=row['device'],
        case=dict(shape=[13,11,11],dx=.25,speed=1.,viscosity=.1,density=1.,mach=.01,
                  collision='bgk',solid=[],origin=[-1.,-1.,-1.],basis=np.eye(3).tolist(),
                  boundaries=['inlet','outlet','slip','slip','slip','slip']),
        geometry=dict(vertices_m=vertices,triangles=faces),
        operating_points=[dict(angle_deg=row['angle'],speed_m_s=row['speed'])],
        references=dict(area_m2=.25,chord_m=.5,pressure_pa=0.),pivot_world_m=[.25,0.,0.],
        probes=[dict(probe_id='fluid',position_world_m=[-.5,0.,0.])],
        settling_steps=0,sample_steps=4,stationarity_tolerance=.05,
        case_id='g6-stationary',generation=7)


def exercise_stationary_study(row):
    from hawa.stationary_study import StationaryStudyJob, validate_submission
    from hawa.jobs import JOBS, dispatch_job
    from hawa.plugin import SESSIONS
    from hawa.fields import FRAMES, get
    request=study_request(row)
    before_jobs,before_sessions=set(JOBS),set(SESSIONS)
    if row['mode']=='open-mesh':request['geometry']['triangles'].pop()
    if row['mode']=='rotated-domain':request['case']['basis']=[[0.,1.,0.],[-1.,0.,0.],[0.,0.,1.]]
    try:
        validate_submission(request)
    except ValueError as exc:
        # A different input error must not masquerade as the expected rejection.
        if row['device']!='cpu':assert 'explicit CPU' in str(exc)
        else:assert row['mode']=='rotated-domain' and 'axis-aligned' in str(exc)
        return False
    job=None;frame_id=None
    try:
        if row['mode']=='cancel':
            job=StationaryStudyJob(request)
            job.control('cancel')
            JOBS[job.id]=job
            job.thread.start()
        else:
            submitted=dispatch_job(dict(op='evaluate_submit',**request))
            job=JOBS[submitted['job']]
        job.thread.join(20)
        assert not job.thread.is_alive(), 'Study must drain within bounded fixture timeout'
        snapshot=job.snapshot()
        if row['mode']=='cancel':
            assert snapshot['state']=='cancelled' and snapshot['result'] is None
            assert not job.frames and not job.details
            return False
        if row['mode']=='open-mesh':
            assert snapshot['state']=='failed' and 'closed' in snapshot['error']
            assert snapshot['result'] is None
            return False
        assert snapshot['state']=='completed',snapshot
        try:
            selected=dispatch_job(dict(op='evaluate_poll',job=job.id,selected_candidate=row['selection']))['result']['selected']
        except ValueError as exc:
            assert row['selection']==1 and 'index outside study' in str(exc)
            return False
        assert row['selection']==0
        assert selected['identity']['generation']==7 and selected['identity']['case_id']=='g6-stationary'
        assert selected['candidate']['angle_deg']==row['angle'] and selected['candidate']['speed_m_s']==row['speed']
        frame=selected['frame'];frame_id=frame['frame'];arrays,meta=get(frame_id)
        assert arrays['pressure'].shape==(13,11,11) and np.isfinite(arrays['pressure']).all()
        assert meta['identity']==selected['identity'] and meta['session']==selected['session']
        assert meta['iteration']==3 and meta['time']==selected['load_samples'][-1]['time_s']
        assert math.isclose(meta['time'],3*.01*.25/(math.sqrt(3)*row['speed']),rel_tol=1e-12,abs_tol=1e-12)
        assert [r['step'] for r in selected['load_samples']]==[0,1,2,3]
        assert all(p['session']==selected['session'] and p['phase']==selected['phase'] for p in selected['probe_samples'])
        # Analytic +Y rotation of the first supplied corner around (.25,0,0).
        angle=math.radians(row['angle'])
        expected=[.25-.25*math.cos(angle)-.25*math.sin(angle),-.25,
                  .25*math.sin(angle)-.25*math.cos(angle)]
        np.testing.assert_allclose(selected['geometry']['vertices_m'][0],expected,rtol=0,atol=1e-15)
        assert snapshot['cleanup']==dict(handles=0,live_workers=0,session_ids=[])
        return True
    finally:
        if job is not None:
            dispatch_job(dict(op='evaluate_control',job=job.id,action='close'))
            job.thread.join(20)
            assert not job.thread.is_alive() and not job.frames and not job.details
        if frame_id is not None:assert frame_id not in FRAMES
        assert set(JOBS)==before_jobs and set(SESSIONS)==before_sessions
