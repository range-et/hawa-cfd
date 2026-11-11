import copy
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


def test_moving_device_parity_and_nonzero_loads():
    states=[]
    for device in ['cpu']+(['mps'] if torch.backends.mps.is_available() else []) + (['cuda:0'] if torch.cuda.is_available() else []):
        s=Session(moving_case(),device);s.advance(12)
        assert s.flow.i==12 and len(s.solver.moving.history)==12
        assert np.isfinite(s.solver.moving.history[-1]['loads'][0]['force']).all()
        states.append(s.flow.f.cpu().numpy().copy())
    for state in states[1:]:np.testing.assert_allclose(state,states[0],rtol=3e-4,atol=3e-6)


def test_moving_restart_matches_continuous(tmp_path, solver_device):
    s=Session(moving_case(),solver_device);SESSIONS[s.id]=s
    try:
        s.advance(5);dispatch(dict(op='save',session=s.id,path=str(tmp_path/'state.npz')))
        s.advance(5);expected=s.flow.f.clone();load=s.solver.moving.history[-1]
        dispatch(dict(op='load',session=s.id,path=str(tmp_path/'state.npz')));s.advance(5)
        np.testing.assert_array_equal(s.flow.f.cpu().numpy(),expected.cpu().numpy())
        assert s.solver.moving.history[-1]==load
        dispatch(dict(op='reset',session=s.id));assert s.flow.i==0 and not s.solver.moving.history
    finally:dispatch(dict(op='close',session=s.id))


def test_moving_speed_and_overlap_rejected(solver_device):
    c=moving_case();c['moving_bodies'][0]['motion']['frequency']=100
    with pytest.raises(ValueError,match='Mach'):Session(c,solver_device)
    c=moving_case();b={**c['moving_bodies'][0],'id':'other'};c['moving_bodies'].append(b)
    with pytest.raises(ValueError,match='overlap'):Session(c,solver_device)


def test_uniform_flow_translates_with_body_without_force_spikes(solver_device):
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    from benchmark_motion import comoving
    result=comoving(solver_device,100)
    assert result['max_fluid_population_error']<3e-6
    assert result['max_force_newtons']<.002


def test_couette_moving_reflection_matches_analytic_profile(solver_device):
    import lettuce as lt
    from hawa.moving_boundaries import moving_reflection
    if solver_device == 'mps':pytest.skip('MPS does not support float64')
    stencil=lt.D2Q9();e=torch.tensor(stencil.e,dtype=torch.float64,device=solver_device);w=torch.tensor(stencil.w,dtype=torch.float64,device=solver_device)
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
            populations[stencil.opposite[i],:,y]=moving_reflection(post[i,:,y],post[stencil.opposite[i],:,y],post[i,:,y],torch.tensor(.5,device=solver_device),rho[:,y],wall*v[0],w[i])
    u=torch.einsum('qd,qxy->dxy',e,populations)/populations.sum(0)
    expected=speed*(np.arange(n)+.5)/n
    np.testing.assert_allclose(u[0].cpu().numpy(),np.broadcast_to(expected,(4,n)),rtol=2e-5,atol=1e-8)


def test_sdf_sampling_matches_sphere(solver_device):
    from hawa.moving_boundaries import MovingBoundaries
    c=moving_case();b=c['moving_bodies'][0];h=.125;lo=np.array([1.25,1.25,.75]);shape=[13]*3
    xyz=np.stack(np.meshgrid(*[lo[i]+np.arange(shape[i])*h for i in range(3)],indexing='ij'),-1)
    b['geometry']=dict(type='sdf',origin=lo.tolist(),shape=shape,spacing=h,values=(np.linalg.norm(xyz-np.array([2,2,1.5]),axis=-1)-.55).reshape(-1).tolist())
    s=Session(c,solver_device);s.advance(5)
    assert s.flow.solid.any()
    assert np.isfinite(s.solver.moving.history[-1]['loads'][0]['force']).all()


def test_recorded_pose_is_synchronized(tmp_path, solver_device):
    from hawa.recording import record,load_frame
    s=Session(moving_case(),solver_device);r=record(s,4,2,tmp_path/'motion',lambda n:None)
    frame=load_frame(r['manifest'],2)
    assert frame['motion']['poses'][0]['time']==frame['time']
    assert frame['motion']['poses']==s.solver.moving.poses


def test_cycle_objective_rejects_partial_cycles(solver_device):
    from hawa.motion import evaluate_motion
    s=Session(moving_case(),solver_device)
    with pytest.raises(ValueError,match='whole cycles'):evaluate_motion(s,dict(period=.3),lambda n:None)


def test_cycle_evaluation_returns_complete_window(solver_device):
    from hawa.motion import evaluate_motion
    c=moving_case();m=c['moving_bodies'][0]['motion'];m.update(amplitude=.01,frequency=5)
    # The full Motion Evaluate job request, as Grasshopper sends it (minus op).
    request=dict(kind='motion_evaluate',case=copy.deepcopy(c),device=solver_device,period=.2,settle_cycles=1,cycles=1,
                 metric='input_power',body_id='body',axis=0);sent=copy.deepcopy(request)
    s=Session(c,solver_device);result=evaluate_motion(s,request,lambda n:None)
    assert request==sent and result['body_id']=='body' and result['period']==.2
    assert result['samples']>=10 and np.isfinite(result['fitness'])
    assert s.flow.i==result['steps']
    samples=[h['loads'][0]['power'] for h in s.solver.moving.history if .2<h['time']<=.4]
    np.testing.assert_allclose(result['fitness'],-np.mean(samples))
    again=evaluate_motion(s,dict(period=.2),lambda n:None)  # body_id defaults to the first body
    assert again['body_id']=='body' and again['fitness']==result['fitness'] and s.flow.i==result['steps']
    force=evaluate_motion(s,dict(period=.2,metric='force',axis=1),lambda n:None)  # the window is already complete
    forces=[h['loads'][0]['force'][1] for h in s.solver.moving.history if .2<h['time']<=.4]
    np.testing.assert_allclose(force['fitness'],np.mean(forces))


def test_moving_recording_pathlines_and_pause_cancel(tmp_path, solver_device):
    import time
    from hawa.jobs import JOBS
    c=moving_case()
    job=dispatch(dict(op='evaluate_submit',kind='record',case=c,device=solver_device,steps=1000,interval=100,directory=str(tmp_path/'run')))['job']
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


def test_two_body_load_ids_and_domain_exit(solver_device):
    c=moving_case();first=c['moving_bodies'][0];first['geometry']['radius']=.3;first['pivot']=[1.5,2,1.5];first['geometry']['center']=[1.5,2,1.5]
    import copy
    second=copy.deepcopy(first);second['id']='second';second['pivot']=[3.5,2,1.5];second['geometry']['center']=[3.5,2,1.5];c['moving_bodies'].append(second)
    s=Session(c,solver_device);s.advance(3)
    assert [v['id'] for v in s.solver.moving.history[-1]['loads']]==['body','second']
    c=moving_case();c['moving_bodies'][0]['pivot']=[.5,2,1.5];c['moving_bodies'][0]['geometry']['center']=[.5,2,1.5]
    with pytest.raises(ValueError,match='clearance'):Session(c,solver_device)


def test_rotating_sphere_occupancy_is_constant(solver_device):
    c=moving_case();c['moving_bodies'][0]['motion']=dict(type='rotation',axis=[0,0,1],rpm=5)
    s=Session(c,solver_device);before=s.flow.solid.clone();s.advance(30)
    assert torch.equal(before,s.flow.solid)


@pytest.mark.parametrize('device', ['cuda:0'])
def test_rotating_sphere_surface_mask_matches_cpu(device):
    """Regression: FP32 SDF rounding must not change geometry across devices.

    Four cells straddled sdf == 0 at dx=1/3 on the RTX 5070 Ti before the
    ordered, rationalized distance calculation.
    """
    if not torch.cuda.is_available():pytest.skip('CUDA hardware unavailable')
    case=moving_case()
    case.update(shape=[25]*3,dx=1/3,viscosity=.2,mach=.1)
    case['moving_bodies']=[dict(id='sphere',pivot=[4,4,4],
        geometry=dict(type='sphere',center=[4,4,4],radius=1.),
        motion=dict(type='rotation',axis=[0,0,1],rpm=.1*60/(2*np.pi),ramp=1.))]
    cpu=Session(case,'cpu');gpu=Session(case,device)
    np.testing.assert_array_equal(gpu.flow.solid.cpu().numpy(),cpu.flow.solid.numpy(),
                                  err_msg='CPU/CUDA must classify the same sphere surface cells')


@pytest.mark.parametrize('dimension', [2, 3])
def test_radial_distance_preserves_surface_sign_and_accuracy(solver_device, dimension):
    from hawa.moving_boundaries import _radial_distance
    # Include the immediate representable neighbours of an on-surface point.
    x=np.array([0., np.nextafter(np.float32(1),np.float32(0)), 1.,
                np.nextafter(np.float32(1),np.float32(2)), 2.],np.float32)
    points=np.zeros((len(x),dimension),np.float32);points[:,0]=x
    actual=_radial_distance(torch.tensor(points,device=solver_device),1.).cpu().numpy()
    np.testing.assert_array_equal(np.sign(actual),np.sign(x.astype(float)-1))
    np.testing.assert_allclose(actual,x.astype(float)-1,rtol=2e-7,atol=1e-14)


@pytest.mark.parametrize('kind', ['sphere', 'cylinder'])
def test_rotated_off_pivot_body_geometry_device_parity(kind, solver_device):
    case=moving_case();case.update(shape=[25]*3,dx=1/3,viscosity=.2,mach=.1)
    geometry=dict(type=kind,center=[4,4,4],radius=1.)
    if kind=='cylinder':geometry['length']=2.
    case['moving_bodies']=[dict(id='body',pivot=[4.2,4,4],geometry=geometry,
        motion=dict(type='rotation',axis=[1,2,3],rpm=.5))]
    cpu=Session(case,'cpu');candidate=Session(case,solver_device)
    for time in (0.,.23,1.):
        cpu.solver.moving.update(time,False);candidate.solver.moving.update(time,False)
        np.testing.assert_array_equal(candidate.flow.solid.cpu().numpy(),cpu.flow.solid.numpy())
        np.testing.assert_allclose(candidate.solver.moving.distances[0].cpu().numpy(),
                                   cpu.solver.moving.distances[0].numpy(),rtol=2e-6,atol=2e-7)


# Payload validation (#68): every declared constraint is exercised through the
# public entry points (validate_bodies, check_case/Session, evaluate_motion).
DELETE=object()
# A minimal valid SDF with exact literal samples, so hashes are platform-stable.
SMALL_SDF=dict(type='sdf',origin=[1.5,1.5,1.],spacing=.5,shape=[3,3,3],values=[1.]*13+[-.5]+[1.]*13)


def grasshopper_case(**motion):
    """The shape Motion, Moving Body and Motion Case send: kind tags, label, sdf geometry."""
    case=moving_case();case['label']='Hawa prescribed-motion case'
    case['moving_bodies']=[dict(kind='Body',id='body',pivot=[2,2,1.5],geometry=copy.deepcopy(SMALL_SDF),
                                motion=dict(kind='Motion',**motion))]
    return case


def python_case(geometry=None, motion=None):
    case=moving_case();body=case['moving_bodies'][0]
    if geometry is not None:body['geometry']=geometry
    if motion is None:del body['motion']
    else:body['motion']=motion
    return case


# Shapes of examples 17-20 and 32 (Grasshopper) and of the Python scripts. C# sends
# whole-number doubles such as 0d as JSON integers. Hashes were recorded on main
# at 3bfb1d3, before pydantic validation existed.
LEGACY_PAYLOADS={
    'example-17-oscillating-cylinder':(lambda:grasshopper_case(type='oscillation',axis=[0,1,0],ramp=.5,amplitude=.15,frequency=.5,phase=0,mode='translation'),
        '75c7e61ea2db65f316e613cec7011ac476df1e28fc7139dcbb87ff59ca4fc489'),
    'example-18-pitching-airfoil':(lambda:grasshopper_case(type='oscillation',axis=[0,0,1],ramp=0,amplitude=.2,frequency=.5,phase=0,mode='rotation'),
        '9cb5e48344320389634f3ba4ca47dae8e264de0b4bb68ba875613d8ea805b954'),
    'example-19-rotating-paddle':(lambda:grasshopper_case(type='rotation',axis=[0,0,1],ramp=1,rpm=20),
        '9fb861e1df2c499229538e9e8d57a3de3210e8a2e8db77d341a724495b0c2574'),
    'example-20-motion-cycle-search':(lambda:grasshopper_case(type='oscillation',axis=[0,1,0],ramp=0,amplitude=.1,frequency=1,phase=0,mode='translation'),
        '1daaa5cf17faa6a1bd078db1ccb4300a45149c5df2cb07759619b0eed92870e1'),
    'example-32-translation':(lambda:grasshopper_case(type='translation',axis=[1,0,0],ramp=.5,speed=.2),
        '227b8227a1b130bccea3fd2272acd4c45177593454dc53bd8a7c317c53d07eb9'),
    'python-oscillating-sphere':(moving_case,
        '43d58a1c9c8efb901e08e37248eda265132330c61c631bbddbd7a06ca32ad95d'),
    'python-cylinder':(lambda:python_case(dict(type='cylinder',center=[2,2,1.5],radius=.5,length=2.),
                                          dict(type='oscillation',axis=[0,1,0],amplitude=.25,frequency=.5,ramp=.5)),
        'f8c9d0431dafc0a682d3e2a9fb47f670dc909f017954e9cee4b98dfba63b4197'),
    'python-fixed-without-motion':(python_case,
        'bddbe78cef5dd865b1cfcc1c1293f98c3b99b7ed657b805ba2a4ca6772537bb1'),
}


def edit(case, path, value):
    target=case
    for key in path[:-1]:target=target[key]
    if value is DELETE:del target[path[-1]]
    else:target[path[-1]]=value
    return case


@pytest.mark.parametrize('name', sorted(LEGACY_PAYLOADS))
def test_legacy_motion_payloads_validate_without_changing_case_hash(name):
    from hawa.plugin import check_case
    factory,expected_hash=LEGACY_PAYLOADS[name];spec=factory();before=copy.deepcopy(spec)
    validate_bodies(spec)
    assert check_case(spec)['case_hash']==expected_hash
    assert spec==before  # validation never writes defaults back into the spec


def test_grasshopper_shaped_sdf_case_runs(solver_device):
    c=moving_case();b=c['moving_bodies'][0];h=.125;lo=np.array([1.25,1.25,.75]);shape=[13]*3
    xyz=np.stack(np.meshgrid(*[lo[i]+np.arange(shape[i])*h for i in range(3)],indexing='ij'),-1)
    c['label']='Hawa prescribed-motion case';b['kind']='Body'
    b['motion']=dict(kind='Motion',type='oscillation',axis=[0,1,0],ramp=0,amplitude=.15,frequency=.5,phase=0,mode='translation')
    b['geometry']=dict(type='sdf',origin=lo.tolist(),shape=shape,spacing=h,values=(np.linalg.norm(xyz-np.array([2,2,1.5]),axis=-1)-.55).reshape(-1).tolist())
    s=Session(c,solver_device);s.advance(2)
    assert s.flow.i==2 and np.isfinite(s.solver.moving.history[-1]['loads'][0]['force']).all()


BODY=('moving_bodies',0)
MOTION=BODY+('motion',)
GEOMETRY=BODY+('geometry',)
CYLINDER=dict(type='cylinder',center=[2,2,1.5],radius=.5,length=2.)
BODY_REJECTIONS=[
    # motion: enum, kind, unknown key, finiteness, type, range, axis
    (moving_case,MOTION+('type',),'spin',"motion.type: Input should be 'fixed', 'translation', 'rotation' or 'oscillation'"),
    (moving_case,MOTION+('mode',),'pitch',"motion.mode: Input should be 'translation' or 'rotation'"),
    (moving_case,MOTION+('kind',),'Body',"motion.kind: Input should be 'Motion'"),
    (moving_case,MOTION+('velocity',),1.,'motion.velocity: Extra inputs are not permitted'),
    *[(moving_case,MOTION+(key,),bad,'motion.'+key+': Input should be a finite number')
      for key,bad in (('speed',float('nan')),('rpm',float('inf')),('amplitude',float('nan')),
                      ('frequency',float('inf')),('phase',float('-inf')),('ramp',float('nan')))],
    (moving_case,MOTION+('speed',),'fast','motion.speed: Input should be a valid number'),
    (moving_case,MOTION+('speed',),'0.5','motion.speed: Input should be a valid number'),  # numeric string
    (moving_case,MOTION+('amplitude',),True,'motion.amplitude: Input should be a valid number'),  # bool
    (moving_case,GEOMETRY+('radius',),'0.55','geometry.sphere.radius: Input should be a valid number'),
    (moving_case,GEOMETRY+('center',),[2,True,1.5],'geometry.sphere.center.1: Input should be a valid number'),
    (moving_case,MOTION+('rpm',),None,'motion.rpm: Input should be a valid number'),
    (moving_case,MOTION+('ramp',),-.1,'motion.ramp: Input should be greater than or equal to 0'),
    (moving_case,MOTION+('frequency',),-1,'motion.frequency: Input should be greater than or equal to 0'),
    (moving_case,MOTION+('axis',),[0,1],'motion.axis: List should have at least 3 items after validation, not 2'),
    (moving_case,MOTION+('axis',),[0,1,0,0],'motion.axis: List should have at most 3 items after validation, not 4'),
    (moving_case,MOTION+('axis',),[0,float('nan'),0],'motion.axis.1: Input should be a finite number'),
    (moving_case,MOTION+('axis',),[0,0,0],'motion: Motion axis cannot be zero'),
    (moving_case,MOTION+('axis',),[1e-13,0,0],'motion: Motion axis cannot be zero'),
    (moving_case,MOTION,'oscillation','motion: Input should be a valid dictionary or instance of Motion'),
    # body: kind, unknown key, id, pivot, geometry tag
    (moving_case,BODY,'body','Moving body 1: Input should be a valid dictionary or instance of Body'),
    (moving_case,BODY+('kind',),'Motion',"kind: Input should be 'Body'"),
    (moving_case,BODY+('domain_key',),'{}','domain_key: Extra inputs are not permitted'),
    (moving_case,BODY+('id',),DELETE,'id: Field required'),
    (moving_case,BODY+('id',),'','id: String should have at least 1 character'),
    (moving_case,BODY+('id',),7,'id: Input should be a valid string'),
    (moving_case,BODY+('pivot',),DELETE,'pivot: Field required'),
    (moving_case,BODY+('pivot',),[2,2],'pivot: List should have at least 3 items after validation, not 2'),
    (moving_case,BODY+('pivot',),[2,float('inf'),1.5],'pivot.1: Input should be a finite number'),
    (moving_case,GEOMETRY,DELETE,'geometry: Field required'),
    (moving_case,GEOMETRY+('type',),'cone','geometry: use type sphere, cylinder or sdf'),
    (moving_case,GEOMETRY+('type',),DELETE,'geometry: use type sphere, cylinder or sdf'),
    # sphere and cylinder
    (moving_case,GEOMETRY+('radius',),0,'geometry.sphere.radius: Input should be greater than 0'),
    (moving_case,GEOMETRY+('radius',),float('nan'),'geometry.sphere.radius: Input should be a finite number'),
    (moving_case,GEOMETRY+('center',),DELETE,'geometry.sphere.center: Field required'),
    (moving_case,GEOMETRY+('length',),2.,'geometry.sphere.length: Extra inputs are not permitted'),
    (lambda:python_case(dict(CYLINDER),{}),GEOMETRY+('length',),0.,'geometry.cylinder.length: Input should be greater than 0'),
    (lambda:python_case(dict(CYLINDER),{}),GEOMETRY+('length',),DELETE,'geometry.cylinder.length: Field required'),
    # sdf: StrictInt shape, sample budget, values, spacing, origin, unknown key
    (grasshopper_case,GEOMETRY+('shape',),[3,3],'geometry.sdf.shape: List should have at least 3 items after validation, not 2'),
    (grasshopper_case,GEOMETRY+('shape',),[3,3,3.],'geometry.sdf.shape.2: Input should be a valid integer'),
    (grasshopper_case,GEOMETRY+('shape',),[3,True,3],'geometry.sdf.shape.1: Input should be a valid integer'),
    (grasshopper_case,GEOMETRY+('shape',),[3,3,2],'geometry.sdf.shape.2: Input should be greater than or equal to 3'),
    (grasshopper_case,GEOMETRY+('shape',),[100,100,21],'geometry.sdf: SDF shape exceeds 200000 samples'),
    (grasshopper_case,GEOMETRY+('values',),[1.]*26,'geometry.sdf: SDF values must match its shape'),
    (grasshopper_case,GEOMETRY+('values',),[1.]*200001,'geometry.sdf.values: List should have at most 200000 items after validation, not 200001'),
    (grasshopper_case,GEOMETRY+('values',),[float('nan')]+[1.]*12+[-.5]+[1.]*13,'geometry.sdf.values.0: Input should be a finite number'),
    (grasshopper_case,GEOMETRY+('spacing',),0,'geometry.sdf.spacing: Input should be greater than 0'),
    (grasshopper_case,GEOMETRY+('origin',),[1.5,1.5],'geometry.sdf.origin: List should have at least 3 items after validation, not 2'),
    (grasshopper_case,GEOMETRY+('center',),[2,2,1.5],'geometry.sdf.center: Extra inputs are not permitted'),
]


@pytest.mark.parametrize('case,path,value,message', BODY_REJECTIONS)
def test_moving_body_constraints_rejected(case, path, value, message):
    spec=edit(case(),path,value)
    expected=message if message.startswith('Moving body') else 'Moving body 1 '+message
    with pytest.raises(ValueError) as error:validate_bodies(spec)
    assert str(error.value)==expected


@pytest.mark.parametrize('path,value,message', [
    (GEOMETRY+('values',),[1.]*27,'^SDF requires a resolved interior$'),
    (GEOMETRY+('values',),[1.]*13+[0.]+[1.]*13,'^SDF requires a resolved interior$'),  # zero is the surface, not inside
    (GEOMETRY+('values',),[0.]+[1.]*12+[-.5]+[1.]*13,'^SDF needs a positive exterior padding layer$'),
    (('moving_bodies',),[],'Use one to four moving bodies'),
    (('moving_bodies',),{'id':'body'},'Use one to four moving bodies'),
    (('wall_links',),[[0,1]],'uniform BGK'),
    (('refinement_lower',),[0,0,0],'uniform BGK'),
    (('shape',),[60,50,51],'limited to 150000 cells'),
    (MOTION+('speed',),3.,'lattice Mach 0.15'),
])
def test_case_level_and_sample_checks_rejected(path, value, message):
    spec=edit(grasshopper_case(type='translation',axis=[1,0,0],ramp=0,speed=.2),path,value)
    with pytest.raises(ValueError,match=message):validate_bodies(spec)


def test_body_errors_name_the_body_and_ids_stay_unique():
    from hawa.plugin import check_case
    spec=moving_case();spec['moving_bodies'].append(copy.deepcopy(spec['moving_bodies'][0]))
    with pytest.raises(ValueError,match='^Body IDs must be unique$'):validate_bodies(spec)
    spec['moving_bodies'][1].update(id='second',pivot=[2,2])
    with pytest.raises(ValueError,match='^Moving body 2 pivot: List should have at least 3 items'):check_case(spec)
    spec['moving_bodies']*=3
    with pytest.raises(ValueError,match='^Use one to four moving bodies$'):Session(spec,'cpu')


@pytest.mark.parametrize('path,value', [
    (MOTION+('ramp',),0),(MOTION+('frequency',),0),(MOTION+('phase',),0),  # C# 0d arrives as int
    (MOTION+('axis',),[0,1,0]),(MOTION+('axis',),[1e-11,0,0]),            # just above the zero-axis limit
    (GEOMETRY+('spacing',),1),(BODY+('pivot',),[2,2,1]),
])
def test_integer_and_boundary_values_accepted(path, value):
    validate_bodies(edit(grasshopper_case(type='oscillation',axis=[0,1,0],ramp=.5,amplitude=.1,frequency=.5,phase=.1,mode='translation'),path,value))


def test_sdf_at_the_sample_budget_is_accepted():
    shape=[100,100,20];values=np.ones(shape);values[50,50,10]=-1.
    spec=grasshopper_case(type='fixed')
    spec['moving_bodies'][0]['geometry'].update(origin=[1.95,1.95,1.49],spacing=.001,shape=shape,values=values.reshape(-1).tolist())
    validate_bodies(spec)
