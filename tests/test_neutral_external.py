import copy
import numpy as np
import pytest
import torch
from hawa.plugin import Session,check_case
from hawa.neutral_external import compile_links,METHOD
from hawa.boundary_contracts import FACES
from test_neutral import case


def external():
    s=case();s['neutral_precursor']['mode']='external'
    cs=[dict(type='velocity',velocity=[5.,0.,0.],profile='neutral'),dict(type='open',velocity=[-5.,0.,0.],profile='neutral'),dict(type='periodic'),dict(type='periodic'),dict(type='wall'),dict(type='slip')]
    s.update(boundary_method=METHOD,boundary_set=dict(schema=1,patches=[dict(id=f,face=f,condition=c) for f,c in zip(FACES,cs)]))
    return s


def building(s,cropped=False):
    n=s['shape'];coords=np.indices(tuple(np.array(n)+2))-1
    solid=(coords[0]<(3 if cropped else 7))&(coords[0]>=(-2 if cropped else 4))&(coords[1]>=4)&(coords[1]<=6)&(coords[2]<4)
    s['solid_halo']=np.flatnonzero(solid).tolist();s['solid']=np.flatnonzero(solid[1:-1,1:-1,1:-1]).tolist()
    return s


def test_link_ownership_and_halo():
    s=building(external(),True);p=compile_links(s);seen=set()
    for q,row in enumerate(p['links']):
        for i in row['body']:
            assert (q,int(i)) not in seen;seen.add((q,int(i)))
        for i in row['external']:
            assert (q,int(i)) not in seen;seen.add((q,int(i)))
        for side,z in enumerate((0,s['shape'][2]-1)):
            for x,y in np.argwhere(p['wall_masks'][side][q]):
                i=np.ravel_multi_index((x,y,z),s['shape']);assert(q,int(i)) not in seen;seen.add((q,int(i)))
    assert p['report']['body_links']>0
    s.pop('solid_halo')
    with pytest.raises(ValueError,match='halo'):check_case(s)


@pytest.mark.parametrize('cropped',[False,True])
def test_body_coupling(cropped):
    s=Session(building(external(),cropped),'cpu');s.advance(100)
    assert s.quality['finite'] and s.quality['max_lattice_mach']<.1
    assert torch.count_nonzero(s.flow.f[:,s.flow.solid])==0


def test_uniform_unknown_link_reconstruction():
    spec=external()
    for patch in spec['boundary_set']['patches'][:2]:patch['condition']['profile']='uniform'
    s=Session(spec,'cpu');f=s.flow;s.solver.rough_floor.factor=0
    u=torch.zeros_like(f.u());u[0]=f.units.convert_velocity_to_lu(5.)
    f.f=f.equilibrium(f,torch.ones_like(f.rho()),u)
    s.advance(100)
    np.testing.assert_allclose(s.fields()['velocity'][0],5.,atol=3e-5)
    np.testing.assert_allclose(s.fields()['velocity'][1:],0.,atol=3e-5)


def test_external_cpu_mps():
    if not torch.backends.mps.is_available():pytest.skip('MPS unavailable')
    spec=building(external(),True);a=Session(spec,'cpu');b=Session(spec,'mps');a.advance(40);b.advance(40)
    np.testing.assert_allclose(a.fields()['velocity'],b.fields()['velocity'],atol=5e-5,rtol=5e-4)


def test_external_physical_mass_budget():
    import lettuce as lt
    from hawa.neutral import make
    for cropped in (False,True):
        spec=building(external(),cropped);f,sim=make(spec,lt.Context('cpu',torch.float64,use_native=False))
        for _ in range(8):
            sim(1)
            r=sim.external_links.report
            assert abs(r['mass_budget_residual_lu'])<1e-10,r


def test_adjacent_inflow_and_reverse_axis():
    spec=external();spec['neutral_precursor']['direction']=[.6,.8,0.]
    for face in (0,2):spec['boundary_set']['patches'][face]['condition']=dict(type='velocity',velocity=[3.,4.,0.],profile='neutral')
    for face in (1,3):spec['boundary_set']['patches'][face]['condition']=dict(type='open',velocity=[-3.,-4.,0.],profile='neutral')
    s=Session(spec,'cpu');s.advance(60)
    assert s.quality['finite'] and s.quality['max_lattice_mach']<.1
    spec=external();spec['neutral_precursor']['direction']=[-1.,0.,0.]
    spec['boundary_set']['patches'][0]['condition']=dict(type='open',velocity=[5.,0.,0.],profile='neutral')
    spec['boundary_set']['patches'][1]['condition']=dict(type='velocity',velocity=[-5.,0.,0.],profile='neutral')
    s=Session(spec,'cpu');s.advance(60)
    assert s.fields()['velocity'][0].mean()<0


def test_top_input_and_pressure_reference():
    spec=external();spec['boundary_set']['patches'][5]['condition']=dict(type='open',velocity=[0.,0.,-.2])
    s=Session(spec,'cpu');s.advance(20);assert s.quality['finite']
    spec['boundary_set']['patches'][0]['condition']['velocity']=[100.,0,0]
    with pytest.raises(ValueError,match='Mach'):check_case(spec)


def test_unsupported_inputs_fail_explicitly():
    for field,value,match in [('profile','parabolic','profiles'),('velocity',[1.,0.,0.],'stationary')]:
        spec=external();face=0 if field=='profile' else 4
        spec['boundary_set']['patches'][face]['condition'][field]=value
        if field=='profile':spec['boundary_set']['patches'][face]['condition']['profile_axis']=2
        with pytest.raises(ValueError,match=match):check_case(spec)
    spec=external();spec['boundary_set']['patches'][1]['condition']['pressure_pa']=10000.
    with pytest.raises(ValueError,match='density budget'):check_case(spec)


def test_open_pressure_and_incoming_top():
    import lettuce as lt
    from hawa.neutral import make
    spec=external();spec['boundary_set']['patches'][1]['condition']['pressure_pa']=.5
    f,sim=make(spec,lt.Context('cpu',torch.float64,use_native=False))
    assert sim.external_links.faces[1]['density_delta']>0
    sim(1);positive=f.f.clone()
    spec['boundary_set']['patches'][1]['condition']['pressure_pa']=0.
    f0,sim0=make(spec,lt.Context('cpu',torch.float64,use_native=False));sim0(1)
    assert not torch.equal(positive,f0.f)
    spec['boundary_set']['patches'][5]['condition']=dict(type='open',velocity=[0.,0.,-.2])
    f,sim=make(spec,lt.Context('cpu',torch.float64,use_native=False))
    u=f.u();u[2]=f.units.convert_velocity_to_lu(-.2);f.f=f.equilibrium(f,u=u)
    sim(1);assert sim.external_links.report['incoming_open_links']>0


def test_shifted_mass_diagnostic_does_not_cancel_absolute_masses():
    s=Session(building(external(),True),'cpu');s.advance(30)
    assert abs(s.solver.external_links.report['mass_budget_residual_lu'])<1e-5


def test_fd_regularization_preserves_wall_and_body_link_ownership():
    import lettuce as lt
    from hawa.neutral import make
    f,sim=make(building(external(),True),lt.Context('cpu',torch.float64,use_native=False))
    for _ in range(4):
        sim._collide();sim.rough_floor.capture();sim.external_links.capture();sim._stream();sim.rough_floor.apply()
        bc=sim.external_links;out=f.f.reshape(19,-1)
        # Body reflection occurs inside ExternalLinks.apply, before regularization.
        out[bc.body_q,bc.body_ix]=bc.saved[bc.body_opposite,bc.body_ix]
        before=out[:,bc.fd_nodes].clone()
        bc.apply()
        torch.testing.assert_close(out[:,bc.fd_nodes][bc.protected],before[bc.protected],rtol=0,atol=0)
        assert abs(bc.report['mass_budget_residual_lu'])<1e-10


def test_small_shifted_exterior_pressure_survives_fp32():
    spec=external();spec['boundary_set']['patches'][1]['condition']['pressure_pa']=.0001
    s=Session(spec,'cpu');s.advance(1)
    # Away from wall/body corners the prescribed gauge pressure is reconstructed
    # directly from density deviation, without adding/subtracting rho_ref in FP32.
    np.testing.assert_allclose(s.fields()['pressure'][-1,2:-2,2:-2],.0001,atol=1e-5,rtol=0)


def test_pressure_backflow_uses_interior_normal_speed_and_gauge_pressure():
    import lettuce as lt
    from hawa.neutral import make
    spec=external();condition=spec['boundary_set']['patches'][1]['condition']
    condition.update(backflow_mode='pressure',velocity=[0.,.1,0.],pressure_pa=.01,profile='uniform')
    f,sim=make(spec,lt.Context('cpu',torch.float64,use_native=False));u=f.u();u[0]=-f.units.convert_velocity_to_lu(.2);f.f=f.equilibrium(f,u=u)
    sim(1)
    assert sim.external_links.report['incoming_open_links']>0
    np.testing.assert_allclose(f.u_pu[0,-1,2:-2,2:-2].numpy(),-.2,rtol=0,atol=1e-8)
    np.testing.assert_allclose(f.u_pu[1,-1,2:-2,2:-2].numpy(),.1,rtol=0,atol=1e-8)
    np.testing.assert_allclose(f.p_pu[0,-1,2:-2,2:-2].numpy(),.01,rtol=0,atol=1e-9)
    condition['velocity'][0]=-.2
    with pytest.raises(ValueError,match='derives normal'):check_case(spec)
