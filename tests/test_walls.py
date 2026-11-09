import numpy as np
import pytest
import torch
import lettuce as lt
from hawa.plugin import Session
from hawa.optimization import evaluate
from test_optimization import spec


def link_spec(fraction=.5):
    case=spec();shape=case['shape'];solid=set(case['solid']);links=[]
    for site in solid:
        c=np.array(np.unravel_index(site,shape))
        for i,e in enumerate(lt.D3Q19().e[1:],1):
            f=c-e;idx=int(np.ravel_multi_index(f,shape))
            if idx not in solid:links.append([i,idx,fraction])
    case['wall_links']=links
    return case


@pytest.mark.parametrize("fraction", [.25, .5, .75])
def test_fractional_reflection_and_force_parity(fraction):
    values=[]
    for device in ['cpu']+(['mps'] if torch.backends.mps.is_available() else []):
        s=Session(link_spec(fraction),device)
        r=evaluate(s,40,10,6);assert r['fitness']>0;values.append(r['fitness'])
    np.testing.assert_allclose(values,values[0],rtol=3e-4)


def test_interpolated_wall_equilibrium():
    s=Session(link_spec(),'cpu');u=torch.zeros_like(s.flow.u());s.flow.f=s.flow.equilibrium(s.flow,s.flow.rho(),u)
    # Exercise bounce-back in isolation from the imposed inlet.
    s.solver._collide=lambda:None
    before=s.flow.f.clone();s.solver._collide_and_stream()
    np.testing.assert_allclose(s.flow.f.numpy(),before.numpy(),atol=1e-7)
    np.testing.assert_allclose(s.solver.wall_history[-1].numpy(),0,atol=1e-6)


def test_invalid_fraction_rejected():
    case=link_spec();case['wall_links'][0][2]=1.1
    with pytest.raises(ValueError):Session(case,'cpu')
