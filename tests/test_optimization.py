import numpy as np
import pytest
import torch
import lettuce as lt
from hawa.plugin import Session, dispatch, SESSIONS
from hawa.optimization import MeasuredBounceBack, evaluate


def spec():
    shape = (18, 12, 10)
    solid = [np.ravel_multi_index((x,y,z), shape).item()
             for x in range(6,10) for y in range(5,8) for z in range(4,7)]
    return dict(shape=list(shape), dx=.5, speed=1., viscosity=.1, density=1000.,
                boundaries=['inlet','outlet','slip','slip','slip','slip'], solid=solid)


def test_equilibrium_closed_body_has_zero_momentum_force(solver_device):
    s=Session(spec(), solver_device)
    boundary=MeasuredBounceBack(s.flow,s.flow.solid,2)
    s.flow.f=s.flow.equilibrium(s.flow,s.flow.rho(),torch.zeros_like(s.flow.u()))
    boundary(s.flow)
    np.testing.assert_allclose(boundary.history[0].cpu().numpy(),0,atol=1e-6)
    # Reverse a uniform stream: the startup momentum transfer changes sign.
    u=torch.zeros_like(s.flow.u());u[0]=.02
    s.flow.f=s.flow.equilibrium(s.flow,s.flow.rho(),u);boundary(s.flow)
    forward=boundary.history[-1].cpu().numpy().copy()
    s.flow.f=s.flow.equilibrium(s.flow,s.flow.rho(),-u);boundary(s.flow)
    np.testing.assert_allclose(boundary.history[-1].cpu().numpy(),-forward,atol=2e-6)
    assert forward[0]>0


def test_completed_evaluation_repeatability_and_device_parity():
    devices=['cpu','cpu']+(['mps'] if torch.backends.mps.is_available() else []) + (['cuda:0'] if torch.cuda.is_available() else [])
    values=[]
    for device in devices:
        result=dispatch(dict(op='evaluate',case=spec(),device=device,steps=40,window=10,reference_volume=6))
        try:
            assert result['status']['steps']==40 and result['status']['state']=='completed'
            assert result['samples']==10 and result['fitness']>0
            values.append(result['fitness'])
        finally:
            dispatch(dict(op='close',session=result['status']['session']))
    assert values[0]==values[1]
    np.testing.assert_allclose(values,values[0],rtol=3e-4)


@pytest.mark.parametrize('changes',[dict(steps=1),dict(window=40),dict(reference_volume=-1)])
def test_invalid_evaluation_does_not_register_a_session(changes, solver_device):
    before=set(SESSIONS)
    request=dict(op='evaluate',case=spec(),device=solver_device,steps=40,window=10,reference_volume=6)
    request.update(changes)
    with pytest.raises(ValueError):dispatch(request)
    assert set(SESSIONS)==before


def test_force_units_scale_with_density_but_fitness_does_not(solver_device):
    a=Session(spec(),solver_device)
    denser=spec();denser['density']=2000.
    b=Session(denser,solver_device)
    ra=evaluate(a,40,10,6);rb=evaluate(b,40,10,6)
    np.testing.assert_allclose(rb['force_newtons'],2*np.asarray(ra['force_newtons']),rtol=2e-6,atol=1e-6)
    assert rb['fitness']==pytest.approx(ra['fitness'],rel=2e-6)
