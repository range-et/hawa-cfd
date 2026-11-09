import copy
import numpy as np
import pytest
import torch
from hawa.plugin import Session, check_case
from hawa.boundaries import FACES, METHOD, compile_plan
from hawa.collision import SmagorinskyV1
from test_boundary_data import case, series
from hawa.boundary_data import attach
from test_walls import link_spec


def channel(axis=0, wall=True):
    s=case(); s['shape']=[9,9,9]; s['initial_velocity']=[0.,0.,0.]
    cs=[dict(type='periodic') for _ in FACES]
    v=[0.,0.,0.];v[axis]=1.
    cs[2*axis]=dict(type='velocity',velocity=v)
    cs[2*axis+1]=dict(type='open',velocity=[0.,0.,0.],pressure_pa=0.)
    if wall:
        a=(axis+1)%3
        cs[2*a]=dict(type='wall');cs[2*a+1]=dict(type='wall')
        cs[2*axis].update(profile='parabolic',profile_axis=a)
    s.update(boundary_method=METHOD,boundary_set=dict(schema=1,patches=[dict(id=f,face=f,condition=c) for f,c in zip(FACES,cs)]))
    return s


def test_composition_mapped_curved_walls(tmp_path):
    s=link_spec();s['boundaries']=['inlet','outlet']+['periodic']*4
    v=np.zeros((2,3,*s['shape'][1:]));v[0,0]=1;v[1,0]=1.2
    session=Session(attach(series(tmp_path/'bc.npz',s,v),s)['case'],'cpu');session.advance(10)
    t=float(session.flow.units.convert_time_to_pu(10))
    np.testing.assert_allclose(session.fields()['velocity'][0,0],1+.2*t,atol=5e-6)
    assert len(session.solver.wall_history)==10
    assert session.solver.boundary_step.names=={'interpolated-walls','legacy-mapped-inlet'}


@pytest.mark.parametrize('axis',[0,1,2])
def test_channel_prescribed_moments(axis):
    s=Session(channel(axis),'cpu');s.advance(25)
    u=s.fields()['velocity'];plane=np.take(u,0,axis=axis+1)
    a=(axis+1)%3;tangents=[a for a in range(3) if a!=axis]
    expected=4*np.linspace(0,1,9)*(1-np.linspace(0,1,9))
    sizes=[1,1];sizes[tangents.index(a)]=9
    np.testing.assert_allclose(plane[axis],np.broadcast_to(expected.reshape(sizes),(9,9)),atol=5e-6)
    np.testing.assert_allclose(np.take(u,0,axis=a+1),0,atol=5e-6)


def test_rotation_and_order():
    a=Session(channel(0),'cpu');b=Session(channel(1),'cpu');a.advance(30);b.advance(30)
    ua=a.fields()['velocity'];ub=b.fields()['velocity']
    np.testing.assert_allclose(ua,ub[[1,2,0]].transpose(0,2,3,1),atol=2e-5,rtol=3e-4)
    spec=channel();spec['boundary_set']['patches'].reverse()
    c=Session(spec,'cpu');c.advance(30)
    np.testing.assert_array_equal(a.flow.f.numpy(),c.flow.f.numpy())


def test_conflicts_and_cropped_solids():
    s=channel();s['boundary_set']['patches'][0]['condition'].pop('profile')
    with pytest.raises(ValueError,match='shared edge'):check_case(s)
    s=channel()
    s['boundary_set']['patches'][4]['condition']=dict(type='open')
    s['boundary_set']['patches'][5]['condition']=dict(type='slip')
    with pytest.raises(ValueError,match='Adjacent'):check_case(s)
    s=channel(wall=False);mask=np.zeros(s['shape'],bool);mask[:3,3:6,3:6]=True;s['solid']=np.flatnonzero(mask).tolist()
    session=Session(s,'cpu');session.advance(10);assert session.quality['finite']
    s['solid']=[int(np.ravel_multi_index((1,1,1),s['shape']))]
    with pytest.raises(ValueError,match='donor'):check_case(s)


def test_open_reversal_and_pressure():
    s=channel(wall=False);v=[-1.,.1,0.]
    s['boundary_set']['patches'][1]['condition']['velocity']=v
    session=Session(s,'cpu');flow=session.flow
    u=torch.zeros_like(flow.u());u[0]=flow.units.convert_velocity_to_lu(-.5)
    flow.f=flow.equilibrium(flow,flow.rho(),u)
    session.solver.general_boundary.reconstruct()
    np.testing.assert_allclose(flow.u_pu[:,-1].numpy(),np.broadcast_to(np.array(v)[:,None,None],(3,9,9)),atol=5e-6)
    assert session.solver.general_boundary.report['open_incoming_nodes']==81


@pytest.mark.parametrize('device',['cpu','mps','cuda:0'])
def test_general_backend(device):
    if device=='mps' and not torch.backends.mps.is_available():pytest.skip('MPS unavailable')
    if device.startswith('cuda') and not torch.cuda.is_available():pytest.skip('CUDA unavailable')
    spec=channel();a=Session(spec,'cpu');b=Session(spec,device);a.advance(40);b.advance(40)
    np.testing.assert_allclose(a.fields()['velocity'],b.fields()['velocity'],atol=2e-5,rtol=3e-4)


def test_smagorinsky_manufactured_stress():
    session=Session(case(),'cpu');flow=session.flow
    base=flow.equilibrium(flow,flow.rho(),torch.zeros_like(flow.u()))
    e=flow.torch_stencil.e;w=flow.torch_stencil.w
    perturb=(w*e[:,0]*e[:,1])[:,None,None,None]
    values=[]
    for amplitude in (1e-3,2e-3,-1e-3):
        flow.f=base+amplitude*perturb
        model=SmagorinskyV1(.8);model(flow)
        pi=flow.shear_tensor(flow.f-flow.equilibrium(flow,flow.rho(),flow.u()))
        magnitude=torch.sqrt(2*(pi*pi).sum((0,1)))/(2*flow.rho()[0]*flow.stencil.cs**2)
        expected=(.8+torch.sqrt(.8**2+12*.17**2*magnitude))/2
        torch.testing.assert_close(model.tau_eff,expected)
        values.append(float((model.tau_eff-.8).mean()))
    assert values[1]/values[0]==pytest.approx(2,rel=.01)
    assert values[2]==pytest.approx(values[0],rel=.001)
    model=SmagorinskyV1(.8,0);actual=model(flow)
    import lettuce as lt
    torch.testing.assert_close(actual,lt.BGKCollision(.8)(flow))


def test_mapped_with_walls_and_open(tmp_path):
    spec=channel();spec['boundary_set']['patches'][0]['condition']['profile']='mapped'
    y=np.linspace(0,1,9);v=np.zeros((2,3,9,9));v[0,0]=(4*y*(1-y))[:,None];v[1,0]=1.1*v[0,0]
    spec=attach(series(tmp_path/'walls.npz',spec,v),spec)['case']
    s=Session(spec,'cpu');s.advance(15);t=float(s.flow.units.convert_time_to_pu(15))
    np.testing.assert_allclose(s.fields()['velocity'][0,0],v[0,0]*(1+.1*t),atol=5e-6)
    np.testing.assert_allclose(s.fields()['velocity'][:,:,0],0,atol=5e-6)


def test_sgs_zero_and_device():
    spec=channel();spec['collision']='smagorinsky-v1'
    cpu=Session(spec,'cpu');model=cpu.solver.collision;model(cpu.flow)
    torch.testing.assert_close(model.tau_eff,torch.full_like(model.tau_eff,model.tau))
    cpu.advance(30)
    if torch.backends.mps.is_available():
        mps=Session(spec,'mps');mps.advance(30)
        np.testing.assert_allclose(cpu.fields()['velocity'],mps.fields()['velocity'],atol=2e-5,rtol=3e-4)


def test_boundary_neq_preserved_and_pressure_moment():
    s=Session(channel(wall=False),'cpu');f=s.flow
    e=f.torch_stencil.e;w=f.torch_stencil.w
    f.f += (1e-3*w*e[:,1]*e[:,2])[:,None,None,None]
    bc=s.solver.general_boundary
    source=f.f.reshape(19,-1)[:,bc.donor].clone()
    rho=source.sum(0,keepdim=True);u=torch.einsum('qd,qn->dn',e,source)/rho
    expected=source-f.equilibrium(f,rho,u)
    bc.reconstruct()
    actual=f.f.reshape(19,-1)[:,bc.ix];rho=actual.sum(0,keepdim=True);u=torch.einsum('qd,qn->dn',e,actual)/rho
    torch.testing.assert_close(actual-f.equilibrium(f,rho,u),expected,atol=2e-7,rtol=1e-4)
    np.testing.assert_allclose(f.rho()[0,-1].numpy(),1.,atol=3e-7)


def test_slip_edges_and_shear_projection():
    spec=channel(wall=False)
    for p in spec['boundary_set']['patches'][2:]:p['condition']={'type':'slip'}
    spec['initial_velocity']=[0.,.2,.3]
    s=Session(spec,'cpu');f=s.flow;e=f.torch_stencil.e;w=f.torch_stencil.w
    f.f+=(1e-3*w*e[:,0]*e[:,1])[:,None,None,None]
    s.solver.general_boundary.reconstruct()
    u=f.u_pu.numpy()
    np.testing.assert_allclose(u[1,:,0,:],0,atol=5e-6)
    np.testing.assert_allclose(u[2,:,:,0],0,atol=5e-6)
    stress=f.shear_tensor(f.f-f.equilibrium(f)).numpy()
    np.testing.assert_allclose(stress[0,1,:,0,:],0,atol=2e-7)
    np.testing.assert_allclose(stress[0,2,:,:,0],0,atol=2e-7)


def test_open_exterior_wall_conflict():
    spec=channel();spec['boundary_set']['patches'][1]['condition']['velocity']=[-1,.2,0]
    with pytest.raises(ValueError,match='shared edge'):check_case(spec)


def test_multistep_reversal_and_cropped_window():
    # Both signs are maintained by the same mixed boundary algorithm.
    for sign in (-1,1):
        spec=channel(1,wall=False);spec['initial_velocity']=[0.,sign*.2,0.]
        spec['boundary_set']['patches'][2]['condition']=dict(type='open',velocity=[0.,.2,0.])
        spec['boundary_set']['patches'][3]['condition']=dict(type='open',velocity=[0.,-.2,0.])
        s=Session(spec,'cpu');s.advance(80)
        np.testing.assert_allclose(s.fields()['velocity'][1],sign*.2,atol=2e-5)
        # Reverse the fluid state in the same solver to exercise the other branch.
        u=torch.zeros_like(s.flow.u());u[1]=s.flow.units.convert_velocity_to_lu(-sign*.2)
        s.flow.f=s.flow.equilibrium(s.flow,torch.ones_like(s.flow.rho()),u)
        s.advance(80)
        np.testing.assert_allclose(s.fields()['velocity'][1],-sign*.2,atol=2e-5)
    # Same closed prism through two windows: compare a causally interior section.
    # This verifies classification/streaming consistency, not cut-face accuracy.
    profiles=[]
    for nx in (41,61):
        spec=channel(wall=False);spec['shape']=[nx,9,9];spec['initial_velocity']=[.1,0.,0.]
        mask=np.zeros(spec['shape'],bool);mask[:,0:3,:]=True;spec['solid']=np.flatnonzero(mask).tolist()
        spec['boundary_set']['patches'][0]['condition']['velocity']=[.1,0.,0.]
        s=Session(spec,'cpu');s.advance(10);profiles.append(s.fields()['velocity'][:,nx//2,3:,:])
        assert np.isfinite(profiles[-1]).all()
    np.testing.assert_allclose(*profiles,atol=2e-6,rtol=1e-5)


def test_channel_record_capture_with_walls(tmp_path):
    from hawa.recording import record
    from hawa.boundary_data import capture
    spec=channel();spec['viscosity']=.1
    parent=Session(spec,'cpu');record(parent,20,5,str(tmp_path/'parent'),lambda n:None)
    # Put the child inlet inside the parent's channel, retaining its wall edges.
    child=copy.deepcopy(spec);child['shape'][0]=4;child['origin']=[.2,0,0]
    result=capture(tmp_path/'parent/manifest.json',child,tmp_path/'child.npz')
    assert result['case']['boundary_set']['patches'][0]['condition']['profile']=='mapped'
    s=Session(result['case'],'cpu');s.advance(20)
    assert s.quality['finite']
    np.testing.assert_allclose(s.fields()['velocity'][:,:,0],0,atol=5e-6)


def test_refinement_and_reset_guards():
    from hawa.refinement import run_refined
    with pytest.raises(ValueError,match='General boundary'):
        run_refined({'case':channel(),'fine_case':case()},lambda n:None)
    s=Session(channel(),'cpu');s.advance(5)
    assert 'fluid_mass_lu' in s.solver.general_boundary.report
    s.solver.general_boundary.reset()
    assert 'fluid_mass_lu' not in s.solver.general_boundary.report
