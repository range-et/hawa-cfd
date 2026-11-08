import numpy as np
import pytest
import torch
import lettuce as lt
from hawa.refinement import RefinedStepper,run_refined
from hawa.fields import get


def test_constant_flow_and_composite_mass():
    ctx=lt.Context(torch.device('cpu'),torch.float32,use_native=False)
    c=lt.TaylorGreenVortex(ctx,[16,16],10,.05);f=lt.TaylorGreenVortex(ctx,[15,15],10,.05)
    for flow in (c,f):
        u=torch.zeros_like(flow.u());u[0]=.02;flow.f=flow.equilibrium(flow,torch.ones_like(flow.rho()),u)
    step=RefinedStepper(lt.Simulation(c,lt.BGKCollision(.8),[]),lt.Simulation(f,lt.BGKCollision(1.1),[]),[4,4],[11,11])
    mass=float(step.composite_mass())
    step(20)
    assert float(step.composite_mass())==pytest.approx(mass,rel=3e-6)
    np.testing.assert_allclose(f.u()[0].numpy(),.02,atol=2e-7)
    np.testing.assert_allclose(f.u()[1].numpy(),0,atol=2e-7)


def test_physical_patch_matches_time_and_units():
    coarse=dict(shape=[17]*3,dx=1.,spacing=1.,origin=[0,0,0],speed=1.,viscosity=1.,density=1.225,mach=.05,collision='bgk',solid=[],boundaries=['inlet','outlet','periodic','periodic','periodic','periodic'])
    fine={**coarse,'shape':[13]*3,'dx':.5,'spacing':.5,'origin':[5,5,5],'refinement_lower':[5]*3,'refinement_upper':[11]*3}
    r=run_refined(dict(case=coarse,fine_case=fine,steps=10,device='cpu'),lambda n:None)
    a,ma=get(r['coarse_frame']['frame']);b,mb=get(r['fine_frame']['frame'])
    assert ma['time']==pytest.approx(mb['time'])
    assert mb['iteration']==2*ma['iteration']==20
    np.testing.assert_allclose(b['velocity'][0],1,atol=2e-5)
    assert mb['case']['physical_dx']==.5
    assert a['solid'][6:11,6:11,6:11].all()


def test_three_dimensional_equilibrium_and_cancel():
    from hawa.jobs import Cancelled
    ctx=lt.Context(torch.device('cpu'),torch.float32,use_native=False)
    c=lt.TaylorGreenVortex(ctx,[12]*3,10,.05);f=lt.TaylorGreenVortex(ctx,[11]*3,10,.05)
    for flow in (c,f):
        u=torch.zeros_like(flow.u());u[0]=.02;u[1]=.01
        flow.f=flow.equilibrium(flow,torch.ones_like(flow.rho()),u)
    step=RefinedStepper(lt.Simulation(c,lt.BGKCollision(.8),[]),lt.Simulation(f,lt.BGKCollision(1.1),[]),[3]*3,[8]*3)
    mass=float(step.composite_mass());step(10)
    assert float(step.composite_mass())==pytest.approx(mass,rel=3e-6)
    np.testing.assert_allclose(f.u()[0].numpy(),.02,atol=2e-7)
    def cancel(n):raise Cancelled()
    with pytest.raises(Cancelled):step(100,cancel)
    assert c.i==10 and f.i==20
