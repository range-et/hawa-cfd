"""Small explicit-CPU force/link controls; no engineering validation claim."""
import copy
from types import SimpleNamespace

import lettuce as lt
import numpy as np
import pytest
import torch

from hawa.plugin import Session
from hawa.optimization import MeasuredBounceBack
from hawa.stationary_loads import StationaryLoads, validate_case, world_basis


def case(two=False):
    shape = [12,9,9]
    a = [int(np.ravel_multi_index((x,y,z),shape)) for x in (3,4) for y in (3,4) for z in (3,4)]
    b = [int(np.ravel_multi_index((x,y,z),shape)) for x in (8,9) for y in (3,4) for z in (3,4)]
    sets = dict(wing=a,tail=b) if two else dict(wing=a)
    spec = dict(shape=shape,dx=.5,speed=1.,viscosity=.1,density=2.,collision='bgk',
                boundaries=['inlet','outlet','slip','slip','slip','slip'],solid=a+b if two else a)
    bodies = [dict(body_id=key,moment_origin_world_m=[0,0,0]) for key in sets]
    return spec,sets,bodies


def collector(two=False, **kwargs):
    spec, sets, bodies = case(two)
    validate_case(spec,sets)
    session = Session(spec,'cpu')
    return session, StationaryLoads(session.flow,spec,sets,bodies,**kwargs)


def test_stationary_reflection_and_aggregate_force_parity():
    session, measured = collector(True)
    baseline = MeasuredBounceBack(session.flow,session.flow.solid,2)
    reflected = measured(session.flow)
    np.testing.assert_array_equal(reflected.numpy(),baseline(session.flow).numpy())
    actual = np.sum([x['force_world_n'] for x in measured.history[-1]['loads']],axis=0)
    expected = baseline.history[-1].numpy()*measured.scale
    np.testing.assert_allclose(actual,expected,atol=1e-5,rtol=1e-6)
    assert [x['body_id'] for x in measured.history[-1]['loads']] == ['wing','tail']
    assert measured.history[-1]['source_step'] == 0 and measured.history[-1]['source_time_s'] == 0
    assert measured.history[-1]['solver_dtype'] == 'torch.float32'


def test_actual_solver_populations_unchanged_by_measurement():
    spec,sets,bodies=case()
    original=Session(spec,'cpu'); measured=Session(spec,'cpu')
    boundary=StationaryLoads(measured.flow,spec,sets,bodies)
    measured.solver.post_boundaries[-1]=boundary
    original.advance(5); measured.advance(5)
    assert torch.equal(original.flow.f,measured.flow.f)
    assert len(boundary.history)==5
    assert [x['source_step'] for x in boundary.history]==list(range(5))
    assert boundary.history[-1]['source_time_s']==4*boundary.dt


def test_equilibrium_reversal_and_density_scaling():
    session,boundary=collector()
    flow=session.flow
    flow.f=flow.equilibrium(flow,flow.rho(),torch.zeros_like(flow.u()))
    boundary(flow)
    np.testing.assert_allclose(boundary.history[-1]['loads'][0]['force_world_n'],0,atol=1e-10)
    np.testing.assert_allclose(boundary.history[-1]['loads'][0]['torque_world_nm'],0,atol=1e-10)
    u=torch.zeros_like(flow.u());u[0]=.02
    rho=flow.rho().clone()
    flow.f=flow.equilibrium(flow,rho,u);boundary(flow)
    forward=np.asarray(boundary.history[-1]['loads'][0]['force_world_n'])
    flow.f=flow.equilibrium(flow,rho,-u);boundary(flow)
    np.testing.assert_allclose(boundary.history[-1]['loads'][0]['force_world_n'],-forward,atol=1e-8)
    assert forward[0]>0
    spec,sets,bodies=case();spec['density']*=2
    dense=Session(spec,'cpu');other=StationaryLoads(dense.flow,spec,sets,bodies)
    dense.flow.f=flow.f.clone();other(dense.flow)
    np.testing.assert_allclose(other.history[-1]['loads'][0]['force_world_n'],-2*forward,atol=1e-8)


def test_single_link_torque_halfway_position_and_world_transform():
    spec,sets,bodies=case();session=Session(spec,'cpu')
    session.flow.f.zero_()
    index=next(i for i,e in enumerate(session.flow.stencil.e) if list(e)==[1,0,0])
    session.flow.f[index,3,3,3]=.25
    basis=[[0,1,0],[-1,0,0],[0,0,1]]
    boundary=StationaryLoads(session.flow,spec,sets,bodies,origin_world_m=[10,20,30],basis=basis)
    boundary(session.flow)
    record=boundary.history[-1]['loads'][0]
    force=np.asarray([0,.5*boundary.scale,0])
    wall=np.array([10,20,30])+np.array([1.25,1.5,1.5])@basis
    np.testing.assert_allclose(record['force_world_n'],force,atol=1e-12)
    np.testing.assert_allclose(record['torque_world_nm'],np.cross(wall,force),atol=1e-12)
    bodies[0]['moment_origin_world_m']=[1,0,0]
    moved=StationaryLoads(session.flow,spec,sets,bodies,origin_world_m=[10,20,30],basis=basis)
    moved(session.flow)
    np.testing.assert_allclose(moved.history[-1]['loads'][0]['torque_world_nm'],np.cross(wall-[1,0,0],force),atol=1e-12)


@pytest.mark.parametrize('patch',[{'collision':'regularized'},{'wall_links':[]},{'moving_bodies':[]},
    {'boundary_set':{}},{'neutral_precursor':{}},{'boundary_field':{}},{'refinement':{}},
    {'example':'tgv3d'},{'shape':[4,4]},{'shape':[100,100,100]},{'dx':True},{'density':float('inf')},
    {'boundaries':['inlet']},{'boundaries':['inlet','outlet','periodic','wall','slip','slip']},
    {'boundaries':['inlet','outlet','foo','foo','slip','slip']},{'solid':[]},{'solid':[999999]}, {'solid':[True]}])
def test_preflight_rejections(patch):
    spec,sets,_=case();spec.update(patch)
    with pytest.raises(ValueError): validate_case(spec,sets)


def test_preflight_ownership_rejections():
    spec,sets,_=case()
    for device in ('auto','mps','cuda:0'):
        with pytest.raises(ValueError): validate_case(spec,sets,device)
    for bad in ({},{'':sets['wing']},{'wing':[]},{'wing':[True]}, {'wing':sets['wing']*2}):
        with pytest.raises(ValueError): validate_case(spec,bad)
    with pytest.raises(ValueError,match='overlap'): validate_case(spec,dict(a=sets['wing'],b=sets['wing']))
    with pytest.raises(ValueError,match='union'): validate_case(spec,dict(a=sets['wing'][:-1]))
    first=sets['wing'][0]
    with pytest.raises(ValueError,match='touch'): validate_case(spec,dict(a=[first],b=sets['wing'][1:]))
    spec['solid']=[0]
    with pytest.raises(ValueError,match='clear'): validate_case(spec,dict(a=[0]))


@pytest.mark.parametrize('origin,basis', [([0,0],np.eye(3)),([True,0,0],np.eye(3)),([0,0,0],np.diag([1,1,-1])),([0,0,0],np.ones((3,3))),([0,0,0],[['1',0,0],[0,1,0],[0,0,1]])])
def test_world_basis_rejections(origin,basis):
    with pytest.raises(ValueError):world_basis(origin,basis)


def test_collector_identity_dtype_references_and_capacity_guards():
    spec,sets,bodies=case();session=Session(spec,'cpu')
    for bad in ([],[dict(body_id='wrong',moment_origin_world_m=[0,0,0])]):
        with pytest.raises(ValueError):StationaryLoads(session.flow,spec,sets,bad)
    for cap in (True,0,100001):
        with pytest.raises(ValueError):StationaryLoads(session.flow,spec,sets,bodies,capacity=cap)
    mismatch=copy.deepcopy(spec);mismatch['dx']*=2
    with pytest.raises(ValueError,match='specification'):StationaryLoads(session.flow,mismatch,sets,bodies)
    session.flow.solid[5,5,5]=True
    with pytest.raises(ValueError,match='mask'):StationaryLoads(session.flow,spec,sets,bodies)
    session.flow.solid[5,5,5]=False
    original=session.flow.f
    session.flow.f=original.to(torch.float16)
    with pytest.raises(ValueError,match='float32'):StationaryLoads(session.flow,spec,sets,bodies)
    session.flow.f=original
    boundary=StationaryLoads(session.flow,spec,sets,bodies,capacity=1)
    with pytest.raises(ValueError,match='different flow'):boundary(SimpleNamespace())
    boundary(session.flow)
    with pytest.raises(ValueError,match='capacity'):boundary(session.flow)
    assert len(boundary.history)==1


def test_collector_nonfinite_populations_rejected_without_partial_append():
    session,boundary=collector()
    session.flow.f.fill_(float('nan'))
    with pytest.raises(ValueError,match='Nonfinite'):boundary(session.flow)
    assert not boundary.history


def test_conversion_guards(monkeypatch):
    spec,sets,bodies=case();s=Session(spec,'cpu')
    monkeypatch.setattr(s.flow.units,'convert_time_to_pu',lambda time:0.)
    with pytest.raises(ValueError,match='positive finite'):StationaryLoads(s.flow,spec,sets,bodies)
    monkeypatch.setattr(s.flow.units,'convert_time_to_pu',lambda time:1e-300)
    with pytest.raises(ValueError,match='overflow or underflow'):StationaryLoads(s.flow,spec,sets,bodies)
    monkeypatch.setattr(s.flow.units,'convert_time_to_pu',lambda time:1e-150)
    monkeypatch.setattr(s.flow.units,'characteristic_density_lu',1e-300)
    with pytest.raises(ValueError,match='positive finite'):StationaryLoads(s.flow,spec,sets,bodies)
    monkeypatch.setattr(s.flow.units,'convert_length_to_pu',lambda length:.6)
    with pytest.raises(ValueError,match='units differ'):StationaryLoads(s.flow,spec,sets,bodies)


def test_float64_collector_and_wrong_stencil(monkeypatch):
    session,boundary=collector()
    session.flow.f=session.flow.f.double()
    spec,sets,bodies=case()
    boundary=StationaryLoads(session.flow,spec,sets,bodies)
    boundary(session.flow)
    assert boundary.history[-1]['solver_dtype']=='torch.float64'
    monkeypatch.setattr(session.flow,'stencil',SimpleNamespace(q=27,d=3))
    with pytest.raises(ValueError,match='D3Q19'):StationaryLoads(session.flow,spec,sets,bodies)


def test_boundary_node_is_not_fluid_padding():
    spec,sets,_=case()
    spec['solid']=[int(np.ravel_multi_index((3,1,3),spec['shape']))]
    with pytest.raises(ValueError,match='fluid padding'):
        validate_case(spec,dict(wing=spec['solid']))
    spec['boundaries'][2:4]=['periodic','periodic']
    assert validate_case(spec,dict(wing=spec['solid'])).sum()==1


def test_native_codegen_cannot_silently_bypass_collection():
    _, boundary = collector()
    assert not boundary.native_available()
    with pytest.raises(NotImplementedError, match='portable CPU'):
        boundary.native_generator(0)
