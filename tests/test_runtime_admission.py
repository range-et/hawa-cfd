"""Runtime admission rules: independent invalid-input and fallback contracts."""
import copy

import numpy as np
import pytest
import torch

from hawa import backends, cases
from hawa.boundary_contracts import FACES, conditions


def boundary_spec(kind='wall'):
    return {'boundary_set': {'schema': 1, 'patches': [
        {'id': 'patch-'+face, 'face': face, 'condition': {'type': kind}}
        for face in FACES]}}


def test_boundary_order_defaults_and_input_are_independent():
    spec = boundary_spec()
    spec['boundary_set']['patches'].reverse()
    spec['boundary_set']['patches'][0]['condition']['velocity'] = [1., 2., 0.]
    before = copy.deepcopy(spec)
    result = conditions(spec)
    assert len(result) == 6 and result[-1]['velocity'] == [1., 2., 0.]
    assert result[0]['velocity'] == [0., 0., 0.]
    result[-1]['velocity'][0] = 99
    assert spec == before


@pytest.mark.parametrize('data,message', [
    (None, 'schema'), ([], 'schema'), ({'schema': 2}, 'schema'),
    ({'schema': 1, 'patches': {}}, 'six faces'),
    ({'schema': 1, 'patches': []}, 'six faces'),
])
def test_boundary_container_rejection(data, message):
    with pytest.raises(ValueError, match=message):
        conditions({'boundary_set': data})


@pytest.mark.parametrize('patch,message', [
    (None, 'name and an oriented face'),
    ({'id': '', 'face': 'x-', 'condition': {'type': 'wall'}}, 'name and an oriented face'),
    ({'id': 1, 'face': 'x-', 'condition': {'type': 'wall'}}, 'name and an oriented face'),
    ({'id': 'a', 'face': 'bad', 'condition': {'type': 'wall'}}, 'name and an oriented face'),
    ({'id': 'a', 'face': 'x-', 'condition': []}, 'must be an object'),
    ({'id': 'a', 'face': 'x-', 'condition': {'type': 'not-supported'}}, 'Unsupported'),
])
def test_boundary_patch_rejection(patch, message):
    spec = boundary_spec(); spec['boundary_set']['patches'][0] = patch
    with pytest.raises(ValueError, match=message): conditions(spec)


@pytest.mark.parametrize('field,value', [('id', 'patch-x+'), ('face', 'x+')])
def test_duplicate_names_and_faces_rejected_independently(field, value):
    spec = boundary_spec(); spec['boundary_set']['patches'][0][field] = value
    with pytest.raises(ValueError, match='Duplicate'): conditions(spec)


@pytest.mark.parametrize('condition,message', [
    ({'type': 'wall', 'velocity': [1., 0., 0.]}, 'normal velocity'),
    ({'type': 'open', 'velocity': [-1., 0., 0.]}, 'incoming or tangential'),
    ({'type': 'open', 'velocity': [1., 0., 0.], 'backflow_mode': 'pressure'}, 'only tangential'),
    ({'type': 'wall', 'backflow_mode': 'pressure'}, 'Backflow mode'),
    ({'type': 'open', 'backflow_mode': 'invalid'}, 'Backflow mode'),
    ({'type': 'velocity', 'velocity': [1., 2.]}, 'three finite'),
    ({'type': 'velocity', 'velocity': [1., np.nan, 0.]}, 'three finite'),
    ({'type': 'pressure', 'pressure_pa': float('inf')}, 'finite gauge'),
    ({'type': 'pressure', 'pressure_pa': '12'}, 'finite gauge'),
    ({'type': 'wall', 'profile': 'parabolic', 'profile_axis': 1}, 'Only velocity'),
    ({'type': 'velocity', 'profile': 'unknown'}, 'Only velocity'),
    ({'type': 'velocity', 'profile': 'neutral'}, 'requires the neutral'),
    ({'type': 'velocity', 'profile': 'parabolic', 'profile_axis': 0}, 'tangential'),
    ({'type': 'velocity', 'profile': 'parabolic', 'profile_axis': True}, 'tangential'),
    ({'type': 'velocity', 'profile': 'parabolic', 'profile_axis': 3}, 'tangential'),
    ({'type': 'velocity', 'profile': 'mapped'}, 'attached X-'),
])
def test_boundary_condition_rejections(condition, message):
    spec = boundary_spec(); spec['boundary_set']['patches'][0]['condition'] = condition
    with pytest.raises(ValueError, match=message): conditions(spec)


@pytest.mark.parametrize('face', range(6))
def test_open_faces_accept_inward_normal_and_reject_outward(face):
    spec = boundary_spec(); c = {'type': 'open', 'velocity': [0., 0., 0.], 'pressure_pa': -12}
    c['velocity'][face//2] = 1 if face % 2 == 0 else -1
    spec['boundary_set']['patches'][face]['condition'] = c
    actual = conditions(spec)[face]
    assert actual['velocity'] == c['velocity'] and actual['pressure_pa'] == -12.
    c['velocity'][face//2] *= -1
    with pytest.raises(ValueError, match='incoming or tangential'): conditions(spec)


def test_profile_and_pressure_backflow_contracts():
    spec = boundary_spec()
    spec['boundary_set']['patches'][0]['condition'] = {'type': 'velocity', 'profile': 'parabolic', 'profile_axis': 2}
    assert conditions(spec)[0]['profile_axis'] == 2
    spec['boundary_set']['patches'][0]['condition'] = {'type': 'open', 'backflow_mode': 'pressure', 'velocity': [0., 3., 4.]}
    result = conditions(spec)[0]
    assert result['pressure_pa'] == 0. and result['velocity'] == [0., 3., 4.]
    spec['neutral_precursor'] = {'schema': 1}
    for profile in ('neutral', 'mapped'):
        spec['boundary_set']['patches'][0]['condition'] = {'type': 'open', 'profile': profile}
        spec['boundary_field'] = {'schema': 'hawa-boundary-series-2', 'faces': ['x-']}
        assert conditions(spec)[0]['profile'] == profile
    spec['boundary_field']['faces'] = ['x+']
    with pytest.raises(ValueError, match='not present'): conditions(spec)
    spec['boundary_field'] = {'schema': 1}
    spec['boundary_set']['patches'][0]['condition'] = {'type': 'velocity', 'profile': 'mapped'}
    assert conditions(spec)[0]['profile'] == 'mapped'
    spec['boundary_set']['patches'][1]['condition'] = {'type': 'velocity', 'profile': 'mapped'}
    with pytest.raises(ValueError, match='attached X-'): conditions(spec)


@pytest.mark.parametrize('name,expected', [('tgv2d-bgk',32),('tgv3d-bgk',12),('cavity2d-bgk',32)])
def test_example_size_defaults_and_endpoints(name, expected):
    assert cases.example_size(name) == expected
    assert cases.example_size(name, 8) == 8
    assert cases.example_size(name, 128) == 128


@pytest.mark.parametrize('size', [7,129,8.,True,False,'16'])
def test_example_size_rejects_invalid_values(size):
    with pytest.raises(ValueError, match='integer from 8 to 128'): cases.example_size('tgv2d-bgk',size)
    with pytest.raises(ValueError, match='Unknown example'): cases.example_size('missing',size)


@pytest.mark.parametrize('name,dimension,kind', [
    ('tgv2d-bgk',2,'BGKCollision'),('tgv2d-trt',2,'TRTCollision'),
    ('tgv2d-smagorinsky',2,'SmagorinskyCollision'),('tgv3d-bgk',3,'BGKCollision'),
    ('tgv3d-smagorinsky',3,'SmagorinskyCollision'),('cavity2d-bgk',2,'BGKCollision'),
    ('poiseuille2d-guo',2,'BGKCollision'),
])
def test_case_construction_uses_declared_shape_collision_and_force(name, dimension, kind):
    import lettuce as lt
    flow, sim = cases.make_case(name,lt.Context('cpu',torch.float32,use_native=False),8)
    assert tuple(flow.resolution) == (8,)*dimension
    assert type(sim.collision).__name__ == kind
    assert flow.i == 0 and torch.isfinite(flow.f).all()
    assert flow.units.reynolds_number == (1 if name == 'poiseuille2d-guo' else 10)
    assert flow.units.mach_number == .05
    if name == 'poiseuille2d-guo':
        assert sim.collision.force is not None and type(sim.collision.force).__name__ == 'Guo'
        assert torch.count_nonzero(flow.u()) == 0
    elif kind == 'BGKCollision': assert sim.collision.force is None
    sim(1)
    assert flow.i == 1 and torch.isfinite(flow.f).all()


def test_case_catalog_rejects_unknown_flow_type(monkeypatch):
    monkeypatch.setitem(cases.CASES,'broken',('unsupported','bgk'))
    with pytest.raises(ValueError,match='Unknown flow: unsupported'):
        cases.make_case('broken',None,8)


@pytest.mark.parametrize('requested', ['invalid', 'cpu:0', 'mps:0', 'meta'])
def test_backend_invalid_names_fail_before_probe(monkeypatch, requested):
    def probe(device): pytest.fail('invalid device reached probe')
    monkeypatch.setattr(backends,'_probe',probe)
    with pytest.raises(ValueError,match='Use auto'): backends.select_backend(requested)


def test_backend_cpu_probe_and_wrong_result_rejection(monkeypatch):
    backends._probe(torch.device('cpu'))
    monkeypatch.setattr(torch,'where',lambda *args:torch.zeros((4,4)))
    with pytest.raises(RuntimeError,match='incorrect results'): backends._probe(torch.device('cpu'))


def test_backend_auto_fallback_order_and_failure_reasons(monkeypatch):
    seen=[]; synced=[]
    monkeypatch.setattr(torch.cuda,'is_available',lambda:True)
    monkeypatch.setattr(torch.backends.mps,'is_available',lambda:True)
    def probe(device):
        seen.append(str(device))
        if device.type!='cpu': raise NotImplementedError('unsupported operation')
    monkeypatch.setattr(backends,'_probe',probe)
    monkeypatch.setattr(backends.Backend,'synchronize',lambda self:synced.append(str(self.device)))
    selected=backends.select_backend('AUTO')
    assert seen==['cuda:0','mps','cpu'] and synced==['cpu']
    info=selected.info()
    assert info['requested']=='auto' and info['selected']=='cpu'
    assert info['torch']==torch.__version__ and info['cuda_available'] and info['mps_available']
    assert len(info['notes'])==2 and 'cuda:0' in info['notes'][0] and 'mps' in info['notes'][1]
    seen.clear()
    with pytest.raises(RuntimeError,match='Cannot use cuda:0'): backends.select_backend('CUDA')
    assert seen==['cuda:0']
    monkeypatch.setattr(backends,'_probe',lambda device:(_ for _ in ()).throw(RuntimeError('failed all')))
    with pytest.raises(RuntimeError,match='No usable backend'): backends.select_backend()


def test_backend_synchronization_routes_exact_device(monkeypatch):
    calls=[]
    monkeypatch.setattr(torch.cuda,'synchronize',lambda device:calls.append(('cuda',str(device))))
    monkeypatch.setattr(torch.mps,'synchronize',lambda:calls.append(('mps',None)))
    backends.Backend(torch.device('cpu'),'cpu').synchronize()
    backends.Backend(torch.device('cuda:2'),'cuda:2').synchronize()
    backends.Backend(torch.device('mps'),'mps').synchronize()
    assert calls==[('cuda','cuda:2'),('mps',None)]


def test_public_face_identity_is_fixed_and_all_condition_kinds_are_accepted():
    assert FACES == ('x-', 'x+', 'y-', 'y+', 'z-', 'z+')
    for kind in ('velocity', 'pressure', 'open', 'wall', 'slip', 'periodic'):
        actual = conditions(boundary_spec(kind))
        assert [c['type'] for c in actual] == [kind]*6


def test_boundary_condition_metadata_is_deeply_detached():
    spec=boundary_spec()
    spec['boundary_set']['patches'][0]['condition']['annotation']={'values':[1,2]}
    actual=conditions(spec)
    assert actual[0]['annotation']=={'values':[1,2]}
    actual[0]['annotation']['values'][0]=99
    assert spec['boundary_set']['patches'][0]['condition']['annotation']=={'values':[1,2]}


@pytest.mark.parametrize('face',range(6))
def test_wall_normal_tolerance_and_tangential_profile_axes(face):
    spec=boundary_spec();c=spec['boundary_set']['patches'][face]['condition'];axis=face//2
    c['velocity']=[0.,0.,0.];c['velocity'][axis]=1e-12
    assert conditions(spec)[face]['velocity'][axis]==1e-12
    c['velocity'][axis]=1.01e-12
    with pytest.raises(ValueError,match='normal velocity'):conditions(spec)
    for profile_axis in set(range(3))-{axis}:
        c.update(type='velocity',profile='parabolic',profile_axis=profile_axis)
        assert conditions(spec)[face]['profile_axis']==profile_axis


@pytest.mark.parametrize('device',['cpu','mps','cuda:3'])
def test_explicit_valid_devices_probe_and_sync_once(monkeypatch,device):
    calls=[]
    monkeypatch.setattr(torch.cuda,'is_available',lambda:True)
    monkeypatch.setattr(torch.backends.mps,'is_available',lambda:True)
    monkeypatch.setattr(backends,'_probe',lambda d:calls.append(('probe',str(d))))
    monkeypatch.setattr(backends.Backend,'synchronize',lambda self:calls.append(('sync',str(self.device))))
    result=backends.select_backend(device)
    assert str(result.device)==device and result.requested==device and result.notes==[]
    assert calls==[('probe',device),('sync',device)]


@pytest.mark.parametrize('device,reason',[('cuda:0','CUDA is unavailable'),('mps','MPS is unavailable')])
def test_unavailable_devices_are_rejected_before_probe(monkeypatch,device,reason):
    monkeypatch.setattr(torch.cuda,'is_available',lambda:False)
    monkeypatch.setattr(torch.backends.mps,'is_available',lambda:False)
    def unexpected(device):pytest.fail('unavailable device reached probe')
    monkeypatch.setattr(backends,'_probe',unexpected)
    with pytest.raises(RuntimeError,match=reason):backends.select_backend(device)


def test_backend_default_notes_are_independent():
    a=backends.Backend(torch.device('cpu'),'cpu');b=backends.Backend(torch.device('cpu'),'cpu')
    assert a.notes==b.notes==[]
    a.notes.append('a failure')
    assert b.notes==[] and a.info()['notes']==['a failure']


def test_probe_does_not_accept_twice_the_declared_error(monkeypatch):
    monkeypatch.setattr(torch,'where',lambda *args:torch.tensor(60.+1.5e-5,dtype=torch.float32))
    with pytest.raises(RuntimeError,match='incorrect results'):backends._probe(torch.device('cpu'))
    monkeypatch.setattr(torch,'where',lambda *args:torch.tensor(60.+5e-6,dtype=torch.float32))
    backends._probe(torch.device('cpu'))


@pytest.mark.parametrize('face', range(6))
def test_open_normal_tolerance_and_parabolic_normal_rejection(face):
    spec = boundary_spec(); c = spec['boundary_set']['patches'][face]['condition']
    axis = face//2; outward = 1 if face%2 else -1
    c.update(type='open', velocity=[0., 0., 0.])
    c['velocity'][axis] = outward*1e-12
    assert conditions(spec)[face]['velocity'][axis] == outward*1e-12
    c['velocity'][axis] = outward*1.01e-12
    with pytest.raises(ValueError, match='incoming or tangential'): conditions(spec)
    c.update(backflow_mode='pressure'); c['velocity'][axis] = -outward*1e-12
    assert conditions(spec)[face]['velocity'][axis] == -outward*1e-12
    c['velocity'][axis] = -outward*1.01e-12
    with pytest.raises(ValueError, match='derives normal'): conditions(spec)
    c.update(type='velocity', backflow_mode='velocity', profile='parabolic', profile_axis=axis)
    with pytest.raises(ValueError, match='tangential profile_axis'): conditions(spec)


@pytest.mark.parametrize('kind', ['wall', 'slip', 'periodic', 'pressure'])
@pytest.mark.parametrize('profile', ['mapped', 'neutral'])
def test_neutral_contract_does_not_allow_profiles_on_closed_conditions(kind, profile):
    spec = boundary_spec(); spec['neutral_precursor'] = {'schema': 1}
    spec['boundary_field'] = {'schema': 'hawa-boundary-series-2', 'faces': list(FACES)}
    spec['boundary_set']['patches'][0]['condition'].update(type=kind, profile=profile)
    with pytest.raises(ValueError, match='Only velocity'): conditions(spec)


def test_public_case_catalog_collision_names_are_stable():
    assert {name: description[1] for name, description in cases.CASES.items()} == {
        'tgv2d-bgk': 'bgk', 'tgv2d-trt': 'trt', 'tgv3d-smagorinsky': 'smagorinsky',
        'tgv2d-smagorinsky': 'smagorinsky', 'tgv3d-bgk': 'bgk',
        'cavity2d-bgk': 'bgk', 'poiseuille2d-guo': 'bgk'}
