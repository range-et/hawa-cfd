"""Regression for outlet-local instability in long open-domain runs."""
import numpy as np
import pytest
from hawa.plugin import Session


def test_open_cylinder_outflow_stays_bounded():
    shape=[61,31,4];x,y,z=np.indices(shape)
    s=Session(dict(shape=shape,dx=.4,spacing=.4,speed=1.,viscosity=.1,density=1.225,mach=.1,collision='bgk',boundaries=['inlet','outlet','periodic','periodic','periodic','periodic'],solid=np.flatnonzero((x-15)**2+(y-15.3)**2<=9).tolist()),'cpu')
    # The previous anti-bounce-back outlet developed negative density by step 750.
    s.advance(1000)
    rho=s.flow.rho().numpy()
    assert rho.min()>.9 and rho.max()<1.1
    assert np.linalg.norm(s.flow.u().numpy(),axis=0).max()<.15


def test_uniform_open_flow_remains_uniform():
    s=Session(dict(shape=[12,8,4],dx=1.,speed=1.,viscosity=.1,density=1.225,mach=.05,collision='bgk',boundaries=['inlet','outlet','periodic','periodic','periodic','periodic'],solid=[]),'cpu')
    s.advance(100)
    np.testing.assert_allclose(s.flow.u_pu[0].numpy(),1,atol=5e-5)
