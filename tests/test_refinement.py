import numpy as np
import pytest
import torch
import lettuce as lt
from hawa.refinement import RefinedStepper,run_refined
from hawa.fields import get


def test_constant_flow_and_composite_mass(solver_device):
    ctx=lt.Context(torch.device(solver_device),torch.float32,use_native=False)
    c=lt.TaylorGreenVortex(ctx,[16,16],10,.05);f=lt.TaylorGreenVortex(ctx,[15,15],10,.05)
    for flow in (c,f):
        u=torch.zeros_like(flow.u());u[0]=.02;flow.f=flow.equilibrium(flow,torch.ones_like(flow.rho()),u)
    step=RefinedStepper(lt.Simulation(c,lt.BGKCollision(.8),[]),lt.Simulation(f,lt.BGKCollision(1.1),[]),[4,4],[11,11])
    mass=float(step.composite_mass())
    step(20)
    assert float(step.composite_mass())==pytest.approx(mass,rel=3e-6)
    np.testing.assert_allclose(f.u()[0].cpu().numpy(),.02,atol=2e-7)
    np.testing.assert_allclose(f.u()[1].cpu().numpy(),0,atol=2e-7)


def test_physical_patch_matches_time_and_units(solver_device):
    coarse=dict(shape=[17]*3,dx=1.,spacing=1.,origin=[0,0,0],speed=1.,viscosity=1.,density=1.225,mach=.05,collision='bgk',solid=[],boundaries=['inlet','outlet','periodic','periodic','periodic','periodic'])
    fine={**coarse,'shape':[13]*3,'dx':.5,'spacing':.5,'origin':[5,5,5],'refinement_lower':[5]*3,'refinement_upper':[11]*3}
    r=run_refined(dict(case=coarse,fine_case=fine,steps=10,device=solver_device),lambda n:None)
    a,ma=get(r['coarse_frame']['frame']);b,mb=get(r['fine_frame']['frame'])
    assert ma['time']==pytest.approx(mb['time'])
    assert mb['iteration']==2*ma['iteration']==20
    np.testing.assert_allclose(b['velocity'][0],1,atol=2e-5)
    assert mb['case']['physical_dx']==.5
    assert a['solid'][6:11,6:11,6:11].all()


def test_refined_frames_mask_wall_faces_like_session_fields(solver_device):
    from hawa.plugin import sample_arrays
    coarse=dict(shape=[17]*3,dx=1.,spacing=1.,origin=[0,0,0],speed=1.,viscosity=1.,density=1.225,mach=.05,collision='bgk',solid=[],boundaries=['inlet','outlet','periodic','periodic','wall','slip'])
    fine={**coarse,'shape':[13]*3,'dx':.5,'spacing':.5,'origin':[5,5,5],'refinement_lower':[5]*3,'refinement_upper':[11]*3}
    r=run_refined(dict(case=coarse,fine_case=fine,steps=2,device=solver_device),lambda n:None)
    a,_=get(r['coarse_frame']['frame']);b,_=get(r['fine_frame']['frame'])
    nodes=a['boundary_nodes']
    assert nodes[:,:,0].all() and nodes[:,:,16].all() and not nodes[:,:,1:16].any() and not a['solid'][:,:,0].any()
    assert 'boundary_nodes' not in b and not b['solid'].any()
    assert [row is not None for row in sample_arrays(a,[[8,8,.4],[8,8,.6],[8,8,15.4],[8,8,15.6]])]==[False,True,True,False]


def test_three_dimensional_equilibrium_and_cancel(solver_device):
    from hawa.jobs import Cancelled
    ctx=lt.Context(torch.device(solver_device),torch.float32,use_native=False)
    c=lt.TaylorGreenVortex(ctx,[12]*3,10,.05);f=lt.TaylorGreenVortex(ctx,[11]*3,10,.05)
    for flow in (c,f):
        u=torch.zeros_like(flow.u());u[0]=.02;u[1]=.01
        flow.f=flow.equilibrium(flow,torch.ones_like(flow.rho()),u)
    step=RefinedStepper(lt.Simulation(c,lt.BGKCollision(.8),[]),lt.Simulation(f,lt.BGKCollision(1.1),[]),[3]*3,[8]*3)
    mass=float(step.composite_mass());step(10)
    assert float(step.composite_mass())==pytest.approx(mass,rel=3e-6)
    np.testing.assert_allclose(f.u()[0].cpu().numpy(),.02,atol=2e-7)
    def cancel(n):raise Cancelled()
    with pytest.raises(Cancelled):step(100,cancel)
    assert c.i==10 and f.i==20


COARSE=dict(shape=[17]*3,dx=1.,spacing=1.,origin=[0,0,0],speed=1.,viscosity=1.,density=1.225,mach=.05,collision='bgk',solid=[],boundaries=['inlet','outlet','periodic','periodic','periodic','periodic'])
FINE={**COARSE,'shape':[13]*3,'dx':.5,'spacing':.5,'origin':[5,5,5],'refinement_lower':[5]*3,'refinement_upper':[11]*3}


# The interface stencil spans coarse x = 4..12 for the patch 5..11; only x = 7..9 is inside it.
@pytest.mark.parametrize('x,rejected',[(3,False),(4,True),(6,True),(7,False),(9,False),(10,True),(12,True),(13,False)])
def test_refinement_rejects_solids_in_the_interface_stencil(x,rejected):
    request=dict(case={**COARSE,'solid':[x*289+8*17+8]},fine_case=FINE,steps=1,device='cpu')
    if rejected:
        with pytest.raises(ValueError,match='^Move the refinement interface at least two coarse cells away from solids$'):run_refined(request,lambda n:None)
    else:
        assert run_refined(request,lambda n:None)['steps']==1


@pytest.mark.parametrize('fill',[0.,-1.,float('nan')])
def test_refined_run_stops_when_a_grid_loses_positive_density(monkeypatch,fill):
    from hawa import refinement
    step=refinement.RefinedStepper.__call__
    def broken(self,steps,checkpoint=lambda n:None):
        step(self,steps,checkpoint);self.fine.flow.f.fill_(fill)
    monkeypatch.setattr(refinement.RefinedStepper,'__call__',broken)
    with pytest.raises(RuntimeError,match='^Refined simulation became unstable$'):
        run_refined(dict(case=COARSE,fine_case=FINE,steps=3,device='cpu'),lambda n:None)
