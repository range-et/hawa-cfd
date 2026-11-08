import numpy as np
import pytest
import torch
from hawa.motion import pose,validate_bodies
from hawa.plugin import Session,dispatch,SESSIONS


def moving_case():
    return dict(shape=[20,16,12],dx=.25,speed=1.,viscosity=.05,density=1.,mach=.04,collision='bgk',
                moving_bodies=[dict(id='body',pivot=[2,2,1.5],geometry=dict(type='sphere',center=[2,2,1.5],radius=.55),
                                    motion=dict(type='oscillation',axis=[0,1,0],amplitude=.15,frequency=.5))])


def test_motion_derivative_and_rotation():
    b=moving_case()['moving_bodies'][0]
    for motion in (dict(type='translation',axis=[1,2,3],speed=.4,ramp=.5),
                   dict(type='oscillation',axis=[0,1,0],amplitude=.2,frequency=2,phase=.3,ramp=.5),
                   dict(type='rotation',axis=[0,0,1],rpm=60,ramp=.5)):
        b['motion']=motion;t=.23;h=1e-6;a=pose(b,t-h);c=pose(b,t+h);m=pose(b,t)
        np.testing.assert_allclose((np.array(c['pivot'])-a['pivot'])/(2*h),m['velocity'],atol=1e-8)
        r=np.array(m['rotation']);np.testing.assert_allclose(r.T@r,np.eye(3),atol=1e-12)
        velocity=(np.array(c['rotation'])[:,0]-np.array(a['rotation'])[:,0])/(2*h)
        np.testing.assert_allclose(velocity,np.cross(m['omega'],r[:,0]),atol=1e-8)


def test_moving_cpu_mps_and_nonzero_loads():
    states=[]
    for device in ['cpu']+(['mps'] if torch.backends.mps.is_available() else []):
        s=Session(moving_case(),device);s.advance(12)
        assert s.flow.i==12 and len(s.solver.moving.history)==12
        assert np.isfinite(s.solver.moving.history[-1]['loads'][0]['force']).all()
        states.append(s.flow.f.cpu().numpy().copy())
    for state in states[1:]:np.testing.assert_allclose(state,states[0],rtol=3e-4,atol=3e-6)


def test_moving_restart_matches_continuous(tmp_path):
    s=Session(moving_case(),'cpu');SESSIONS[s.id]=s
    try:
        s.advance(5);dispatch(dict(op='save',session=s.id,path=str(tmp_path/'state.npz')))
        s.advance(5);expected=s.flow.f.clone();load=s.solver.moving.history[-1]
        dispatch(dict(op='load',session=s.id,path=str(tmp_path/'state.npz')));s.advance(5)
        np.testing.assert_array_equal(s.flow.f.numpy(),expected.numpy())
        assert s.solver.moving.history[-1]==load
        dispatch(dict(op='reset',session=s.id));assert s.flow.i==0 and not s.solver.moving.history
    finally:dispatch(dict(op='close',session=s.id))


def test_moving_speed_and_overlap_rejected():
    c=moving_case();c['moving_bodies'][0]['motion']['frequency']=100
    with pytest.raises(ValueError,match='Mach'):Session(c,'cpu')
    c=moving_case();b={**c['moving_bodies'][0],'id':'other'};c['moving_bodies'].append(b)
    with pytest.raises(ValueError,match='overlap'):Session(c,'cpu')


def test_uniform_flow_translates_with_body_without_force_spikes():
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    from benchmark_motion import comoving
    result=comoving('cpu',100)
    assert result['max_fluid_population_error']<3e-6
    assert result['max_force_newtons']<.002


def test_couette_moving_reflection_matches_analytic_profile():
    import lettuce as lt
    from hawa.moving_boundaries import moving_reflection
    stencil=lt.D2Q9();e=torch.tensor(stencil.e,dtype=torch.float64);w=torch.tensor(stencil.w,dtype=torch.float64)
    n=10;speed=.02;tau=.8
    populations=w[:,None,None].expand(-1,4,n).clone()
    for _ in range(1500):
        rho=populations.sum(0);u=torch.einsum('qd,qxy->dxy',e,populations)/rho
        eu=torch.einsum('qd,dxy->qxy',e,u)
        equilibrium=w[:,None,None]*rho*(1+3*eu+4.5*eu**2-1.5*(u*u).sum(0))
        post=populations-(populations-equilibrium)/tau
        populations=torch.stack([torch.roll(post[i],tuple(map(int,v)),(0,1)) for i,v in enumerate(stencil.e)])
        for i,v in enumerate(stencil.e):
            if v[1]==0:continue
            y=n-1 if v[1]>0 else 0;wall=speed if v[1]>0 else 0
            populations[stencil.opposite[i],:,y]=moving_reflection(post[i,:,y],post[stencil.opposite[i],:,y],post[i,:,y],torch.tensor(.5),rho[:,y],wall*v[0],w[i])
    u=torch.einsum('qd,qxy->dxy',e,populations)/populations.sum(0)
    expected=speed*(np.arange(n)+.5)/n
    np.testing.assert_allclose(u[0].numpy(),np.broadcast_to(expected,(4,n)),rtol=2e-5,atol=1e-8)


def test_sdf_sampling_matches_sphere():
    from hawa.moving_boundaries import MovingBoundaries
    c=moving_case();b=c['moving_bodies'][0];h=.125;lo=np.array([1.25,1.25,.75]);shape=[13]*3
    xyz=np.stack(np.meshgrid(*[lo[i]+np.arange(shape[i])*h for i in range(3)],indexing='ij'),-1)
    b['geometry']=dict(type='sdf',origin=lo.tolist(),shape=shape,spacing=h,values=(np.linalg.norm(xyz-np.array([2,2,1.5]),axis=-1)-.55).reshape(-1).tolist())
    s=Session(c,'cpu');s.advance(5)
    assert s.flow.solid.any()
    assert np.isfinite(s.solver.moving.history[-1]['loads'][0]['force']).all()


def test_recorded_pose_is_synchronized(tmp_path):
    from hawa.recording import record,load_frame
    s=Session(moving_case(),'cpu');r=record(s,4,2,tmp_path/'motion',lambda n:None)
    frame=load_frame(r['manifest'],2)
    assert frame['motion']['poses'][0]['time']==frame['time']
    assert frame['motion']['poses']==s.solver.moving.poses


def test_cycle_objective_rejects_partial_cycles():
    from hawa.motion import evaluate_motion
    s=Session(moving_case(),'cpu')
    with pytest.raises(ValueError,match='whole cycles'):evaluate_motion(s,dict(period=.3),lambda n:None)


def test_cycle_evaluation_returns_complete_window():
    from hawa.motion import evaluate_motion
    c=moving_case();m=c['moving_bodies'][0]['motion'];m.update(amplitude=.01,frequency=5)
    s=Session(c,'cpu');result=evaluate_motion(s,dict(period=.2,settle_cycles=1,cycles=1,metric='input_power'),lambda n:None)
    assert result['samples']>=10 and np.isfinite(result['fitness'])
    assert s.flow.i==result['steps']
    samples=[h['loads'][0]['power'] for h in s.solver.moving.history if .2<h['time']<=.4]
    np.testing.assert_allclose(result['fitness'],-np.mean(samples))


def test_moving_recording_pathlines_and_pause_cancel(tmp_path):
    import time
    from hawa.jobs import JOBS
    c=moving_case()
    job=dispatch(dict(op='evaluate_submit',kind='record',case=c,device='cpu',steps=1000,interval=100,directory=str(tmp_path/'run')))['job']
    worker=JOBS[job]
    dispatch(dict(op='evaluate_control',job=job,action='pause'))
    end=time.monotonic()+5
    while worker.state!='paused' and time.monotonic()<end:time.sleep(.01)
    assert worker.state=='paused'
    steps=worker.steps;time.sleep(.03);assert worker.steps==steps
    dispatch(dict(op='evaluate_control',job=job,action='resume'))
    dispatch(dict(op='evaluate_control',job=job,action='close'))
    worker.thread.join(timeout=5)
    assert not worker.thread.is_alive() and worker.result is None and worker.session is None


def test_two_body_load_ids_and_domain_exit():
    c=moving_case();first=c['moving_bodies'][0];first['geometry']['radius']=.3;first['pivot']=[1.5,2,1.5];first['geometry']['center']=[1.5,2,1.5]
    import copy
    second=copy.deepcopy(first);second['id']='second';second['pivot']=[3.5,2,1.5];second['geometry']['center']=[3.5,2,1.5];c['moving_bodies'].append(second)
    s=Session(c,'cpu');s.advance(3)
    assert [v['id'] for v in s.solver.moving.history[-1]['loads']]==['body','second']
    c=moving_case();c['moving_bodies'][0]['pivot']=[.5,2,1.5];c['moving_bodies'][0]['geometry']['center']=[.5,2,1.5]
    with pytest.raises(ValueError,match='clearance'):Session(c,'cpu')


def test_rotating_sphere_occupancy_is_constant():
    c=moving_case();c['moving_bodies'][0]['motion']=dict(type='rotation',axis=[0,0,1],rpm=5)
    s=Session(c,'cpu');before=s.flow.solid.clone();s.advance(30)
    assert torch.equal(before,s.flow.solid)
