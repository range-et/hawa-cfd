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


@pytest.mark.parametrize('dx,dt,rho_lu', [(.25, .125, 2.), (.5, 2., 3.), (2., .25, .5)])
def test_manufactured_impulse_has_independent_physical_force_and_moment_scale(monkeypatch, dx, dt, rho_lu):
    # The oracle deliberately does not read boundary.scale. One population gives
    # a known impulse, so changing a conversion exponent cannot bless itself.
    spec, sets, bodies = case()
    spec['dx'] = dx
    session = Session(spec, 'cpu')
    monkeypatch.setattr(session.flow.units, 'convert_time_to_pu', lambda step: step * dt)
    monkeypatch.setattr(session.flow.units, 'characteristic_density_lu', rho_lu)
    flow = session.flow
    flow.f.zero_()
    direction = next(i for i, e in enumerate(flow.stencil.e) if list(e) == [1, 0, 1])
    flow.f[direction, 3, 3, 3] = .25
    bodies[0]['moment_origin_world_m'] = [1., -2., .5]
    collector = StationaryLoads(flow, spec, sets, bodies)
    collector(flow)
    physical_impulse = 2. * .25 * (2. / rho_lu) * dx**4 / dt**2
    force = np.array([physical_impulse, 0., physical_impulse])
    # The transfer is parallel to the link; moving along that link cannot alter
    # its torque. The perpendicular y arm makes both x/z moments observable.
    arm = np.array([2.5 * dx, 3 * dx, 2.5 * dx]) - np.array([1., -2., .5])
    expected_torque = np.array([arm[1] * physical_impulse,
                                (arm[2] - arm[0]) * physical_impulse,
                                -arm[1] * physical_impulse])
    row = collector.history[-1]
    np.testing.assert_allclose(row['loads'][0]['force_world_n'], force, rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(row['loads'][0]['torque_world_nm'], expected_torque, rtol=1e-13, atol=1e-13)
    assert row['reduction_dtype'] == 'float64'
    assert row['method'] == 'full-way momentum exchange; pre-stream source state'


def test_isolated_impulses_attribute_each_body_and_exclude_internal_links():
    spec, sets, bodies = case(True)
    session = Session(spec, 'cpu')
    session.flow.f.zero_()
    direction = next(i for i, e in enumerate(session.flow.stencil.e) if list(e) == [1, 0, 0])
    session.flow.f[direction, 3, 3, 3] = .25
    session.flow.f[direction, 8, 3, 3] = .75
    # The previous node (3,3,3) is solid, so this population is internal and
    # must have no contribution even though its magnitude dominates the others.
    session.flow.f[direction, 4, 3, 3] = 1000.
    boundary = StationaryLoads(session.flow, spec, sets, bodies)
    boundary(session.flow)
    dt = float(session.flow.units.convert_time_to_pu(1))
    rho_lu = float(session.flow.units.characteristic_density_lu)
    scale = 2. / rho_lu * .5**4 / dt**2
    records = boundary.history[-1]['loads']
    assert [r['body_id'] for r in records] == ['wing', 'tail']
    np.testing.assert_allclose(records[0]['force_world_n'], [.5 * scale, 0., 0.], rtol=1e-13)
    np.testing.assert_allclose(records[1]['force_world_n'], [1.5 * scale, 0., 0.], rtol=1e-13)


@pytest.mark.parametrize('face', [2, 3, 4, 5])
@pytest.mark.parametrize('kind', ['wall', 'slip'])
def test_each_transverse_wall_face_requires_actual_fluid_padding(face, kind):
    spec, _, _ = case()
    spec['boundaries'] = ['inlet', 'outlet', 'periodic', 'periodic', 'periodic', 'periodic']
    pair = 2 * (face // 2)
    spec['boundaries'][pair:pair+2] = [kind, kind]
    coords = [4, 4, 4]
    coords[face // 2] = 1 if face % 2 == 0 else spec['shape'][face // 2] - 2
    index = int(np.ravel_multi_index(coords, spec['shape']))
    spec['solid'] = [index]
    with pytest.raises(ValueError, match='fluid padding'):
        validate_case(spec, {'wing': [index]})
    coords[face // 2] += 1 if face % 2 == 0 else -1
    spec['solid'] = [int(np.ravel_multi_index(coords, spec['shape']))]
    owner = validate_case(spec, {'wing': spec['solid']})
    assert np.count_nonzero(owner) == 1


@pytest.mark.parametrize('offset', [list(e) for e in lt.D3Q19().e if any(e)])
def test_every_d3q19_contact_direction_rejects_separate_body_attribution(offset):
    spec, _, _ = case()
    a = np.array([5, 4, 4]); b = a + offset
    indices = [int(np.ravel_multi_index(v, spec['shape'])) for v in (a, b)]
    spec['solid'] = indices
    with pytest.raises(ValueError, match='touch'):
        validate_case(spec, dict(a=[indices[0]], b=[indices[1]]))


def test_corner_only_contact_is_not_a_d3q19_link():
    spec, _, _ = case()
    indices = [int(np.ravel_multi_index(v, spec['shape'])) for v in ([4, 4, 4], [5, 5, 5])]
    spec['solid'] = indices
    owner = validate_case(spec, dict(a=[indices[0]], b=[indices[1]]))
    assert sorted(owner[owner > 0].tolist()) == [1, 2]


@pytest.mark.parametrize('shape', [[4, 4, 4], [60, 50, 50]])
def test_exact_grid_admission_limits(shape):
    spec, _, _ = case()
    spec['shape'] = shape
    spec['boundaries'] = ['inlet', 'outlet', 'periodic', 'periodic', 'periodic', 'periodic']
    coords = [n // 2 for n in shape]
    spec['solid'] = [int(np.ravel_multi_index(coords, shape))]
    owner = validate_case(spec, {'wing': spec['solid']})
    assert owner.shape == tuple(shape)
    assert owner.dtype == np.int8  # bounded ownership storage is one byte/cell
    assert np.count_nonzero(owner) == 1


def test_four_body_limit_accepts_four_and_rejects_five():
    spec, _, _ = case()
    spec['shape'] = [20, 9, 9]
    indices = [int(np.ravel_multi_index((x, 4, 4), spec['shape'])) for x in (3, 6, 9, 12, 15)]
    sets = {str(i): [v] for i, v in enumerate(indices[:4])}
    spec['solid'] = indices[:4]
    owner = validate_case(spec, sets)
    assert set(owner.flat) == {0, 1, 2, 3, 4}
    session = Session(spec, 'cpu')
    bodies = [dict(body_id=key, moment_origin_world_m=[0., 0., 0.]) for key in sets]
    boundary = StationaryLoads(session.flow, spec, sets, bodies)
    boundary(session.flow)
    assert [load['body_id'] for load in boundary.history[-1]['loads']] == list(sets)
    spec['solid'] = indices
    sets['4'] = [indices[-1]]
    with pytest.raises(ValueError, match='1..4'):
        validate_case(spec, sets)


@pytest.mark.parametrize('key,value', [('shape', [3, 9, 9]), ('shape', (12, 9, 9)),
    ('shape', [12., 9, 9]), ('shape', [True, 9, 9]), ('dx', 0), ('speed', 0),
    ('viscosity', 0), ('density', 0), ('refinement_patch', {}), ('patch', {}),
    ('boundaries', ['inlet', 'outlet', 'periodic', 'periodic', 'wall']),
    ('boundaries', ('inlet', 'outlet', 'slip', 'slip', 'slip', 'slip')),
    ('boundaries', ['inlet', 'outlet', 'slip', 'slip', 'periodic', 'wall'])])
def test_admission_rejects_unsupported_exact_boundary_inputs(key, value):
    spec, sets, _ = case()
    spec[key] = value
    with pytest.raises(ValueError):
        validate_case(spec, sets)


def test_solid_collection_contract_rejects_duplicates_and_coercion():
    spec, sets, _ = case()
    for values in (tuple(spec['solid']), spec['solid'] * 2, [float(v) for v in spec['solid']],
                   [np.prod(spec['shape']).item()], [-1]):
        invalid = copy.deepcopy(spec); invalid['solid'] = values
        with pytest.raises(ValueError, match='Case solid indices'):
            validate_case(invalid, sets)
    for values in ([-1], [np.prod(spec['shape']).item()], [float(sets['wing'][0])]):
        with pytest.raises(ValueError, match='Body IDs'):
            validate_case(spec, {'wing': values})


@pytest.mark.parametrize('face', range(6))
def test_domain_face_solids_are_refused_on_all_sides(face):
    spec, _, _ = case()
    coords = [4, 4, 4]
    coords[face // 2] = 0 if face % 2 == 0 else spec['shape'][face // 2] - 1
    spec['solid'] = [int(np.ravel_multi_index(coords, spec['shape']))]
    with pytest.raises(ValueError, match='clear node layer'):
        validate_case(spec, {'wing': spec['solid']})


@pytest.mark.parametrize('basis', [np.diag([1 + 1e-9, 1 / (1 + 1e-9), 1.]),
                                  np.diag([1 + 4e-11] * 3)])
def test_nearly_valid_frames_cannot_relax_absolute_orthonormal_or_determinant_bounds(basis):
    with pytest.raises(ValueError, match='orthonormal'):
        world_basis([0., 0., 0.], basis)


def test_arbitrary_rotation_and_valid_roundoff_are_accepted():
    c, s = np.cos(.37), np.sin(.37)
    basis = [[c, s, 0.], [-s, c, 0.], [0., 0., 1.]]
    origin, result = world_basis([1., 2., 3.], basis)
    np.testing.assert_array_equal(origin, [1., 2., 3.])
    np.testing.assert_allclose(result, basis, rtol=0., atol=0.)
    world_basis([0., 0., 0.], np.diag([1 + 2e-11] * 3))


def test_units_near_mismatch_are_not_accepted_with_default_relative_tolerance(monkeypatch):
    spec, sets, bodies = case(); session = Session(spec, 'cpu')
    monkeypatch.setattr(session.flow.units, 'convert_length_to_pu', lambda value: .5 * (1 + 5e-10))
    with pytest.raises(ValueError, match='units differ'):
        StationaryLoads(session.flow, spec, sets, bodies)
    monkeypatch.setattr(session.flow.units, 'convert_length_to_pu', lambda value: .5)
    monkeypatch.setattr(session.flow.units, 'characteristic_density_pu', 2. * (1 + 5e-10))
    with pytest.raises(ValueError, match='units differ'):
        StationaryLoads(session.flow, spec, sets, bodies)


def test_missing_spec_incompatible_dimension_and_resolution_are_not_collected(monkeypatch):
    spec, sets, bodies = case(); session = Session(spec, 'cpu')
    monkeypatch.delattr(session.flow, 'spec')
    with pytest.raises(ValueError, match='specification'):
        StationaryLoads(session.flow, spec, sets, bodies)
    monkeypatch.setattr(session.flow, 'spec', spec, raising=False)
    monkeypatch.setattr(session.flow, 'stencil', SimpleNamespace(q=19, d=2))
    with pytest.raises(ValueError, match='D3Q19'):
        StationaryLoads(session.flow, spec, sets, bodies)
    monkeypatch.setattr(session.flow, 'stencil', SimpleNamespace(q=19, d=3))
    monkeypatch.setattr(session.flow, 'resolution', [12, 9, 8])
    with pytest.raises(ValueError, match='D3Q19'):
        StationaryLoads(session.flow, spec, sets, bodies)


def test_collector_checks_actual_device_metadata_before_allocating():
    spec, sets, bodies = case(); session = Session(spec, 'cpu')
    # All real tensors stay on CPU; the deliberately inconsistent metadata
    # represents an unsupported caller and must fail before link construction.
    flow = SimpleNamespace(context=SimpleNamespace(device='unsupported-device'),
                           spec=spec, stencil=session.flow.stencil,
                           resolution=session.flow.resolution, f=session.flow.f,
                           solid=session.flow.solid, units=session.flow.units)
    with pytest.raises(ValueError, match='explicit cpu'):
        StationaryLoads(flow, spec, sets, bodies)


def test_body_references_require_list_even_when_tuple_has_valid_members():
    spec, sets, bodies = case(); session = Session(spec, 'cpu')
    with pytest.raises(ValueError, match='body moment references'):
        StationaryLoads(session.flow, spec, sets, tuple(bodies))


def test_zero_force_conversion_from_underflow_is_rejected(monkeypatch):
    spec, sets, bodies = case(); session = Session(spec, 'cpu')
    monkeypatch.setattr(session.flow.units, 'characteristic_density_lu', 1e308)
    monkeypatch.setattr(session.flow.units, 'convert_time_to_pu', lambda step: step * 1e10)
    # Every input scale remains finite/positive; their combined force scale
    # underflows to exactly zero and must not silently erase measured loads.
    with pytest.raises(ValueError, match='positive finite'):
        StationaryLoads(session.flow, spec, sets, bodies)


def test_finite_force_with_overflowing_moment_is_rejected_without_history():
    spec, sets, bodies = case(); session = Session(spec, 'cpu')
    bodies[0]['moment_origin_world_m'] = [0., 1e308, 0.]
    session.flow.f.zero_()
    direction = next(i for i, e in enumerate(session.flow.stencil.e) if list(e) == [1, 0, 0])
    session.flow.f[direction, 3, 3, 3] = 2.
    # The impulse is finite, while its moment about this finite but remote
    # reference cannot be represented. Neither partial nor nonfinite rows pass.
    boundary = StationaryLoads(session.flow, spec, sets, bodies)
    with pytest.raises(ValueError, match='Nonfinite'):
        boundary(session.flow)
    assert not boundary.history


@pytest.mark.parametrize('construct_under_trap', [False, True])
def test_explicit_cpu_collection_ignores_ambient_allocation_device(construct_under_trap):
    """Meta is an allocation trap only; no accelerator hardware is touched."""
    spec, sets, bodies = case(); session = Session(spec, 'cpu')
    session.flow.f.zero_()
    direction = next(i for i, e in enumerate(session.flow.stencil.e) if list(e) == [1, 0, 0])
    session.flow.f[direction, 3, 3, 3] = .25
    with torch.device('meta' if construct_under_trap else 'cpu'):
        boundary = StationaryLoads(session.flow, spec, sets, bodies)
    assert boundary.make_no_collision_mask(session.flow.resolution, session.flow.context).device.type == 'cpu'
    for _, links in boundary.links:
        for _, mask, arm, vector in links:
            assert mask.device.type == arm.device.type == vector.device.type == 'cpu'
    # Also covers a caller changing allocation context after construction.
    with torch.device('meta'):
        reflected = boundary(session.flow)
    assert reflected.device.type == 'cpu'
    load = boundary.history[-1]['loads'][0]
    scale = (spec['density'] / session.flow.units.characteristic_density_lu
             * spec['dx']**4 / session.flow.units.convert_time_to_pu(1)**2)
    np.testing.assert_allclose(load['force_world_n'], [.5 * scale, 0., 0.], atol=1e-12)
    assert np.isfinite(load['torque_world_nm']).all()
