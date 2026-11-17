"""Independent manufactured contracts for SI measurement analysis."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from hawa.measurements import (Body, Probe, References, Request, Sample, Window,
                               coefficients, finite_vectors, sample_probes, summarize, unit_vector,
                               translate_moment, validate_request)

FIXTURE = Path(__file__).parent / 'fixtures/measurements/measurement-v1.json'


def fixture():
    return json.loads(FIXTURE.read_text())


def test_frozen_algebra_and_origin_translation():
    data = fixture()
    before = copy.deepcopy(data)
    out = summarize(data['request'], data['samples'])
    body = out['bodies'][0]
    for key in ('q_pa', 'CD', 'CY', 'CL', 'Cm'):
        assert body['mean'][key] == data['expected'][key]
    assert body['force_std_world_n'] == [0, 0, 0]
    assert body['coefficient_std'] == dict(CD=0, CY=0, CL=0, Cm=0)
    assert out['usable'] and body['stationarity']['passed']
    assert body['duration_s'] == 3 and body['count'] == 4
    assert translate_moment([36, 0, 72], [0, 18, 0], [0, 0, 0], [1, 0, 0]) == [0, 90, 0]
    assert data == before


def test_axis_rotation_sign_and_load_cell():
    request = fixture()['request']
    request['references'].update(drag_axis_world=[0, 1, 0], lift_axis_world=[0, 0, 1])
    request['load_axis_world'] = [0, -1, 0]
    out = coefficients(request, [0, -36, 72], [-18, 0, 0])
    assert out['CD'] == -1 and out['CL'] == 2 and out['Cm'] == .25
    assert out['load_cell_n'] == 36


@pytest.mark.parametrize('path,value', [
    (('schema',), 'wrong'), (('extra',), 0), (('identity', 'revision'), True),
    (('identity', 'generation'), -1), (('identity','case_id'), ''),
    (('references','density_kg_m3'), '2'), (('references','speed_m_s'), False),
    (('references','area_m2'), 0), (('references','chord_m'), -1),
    (('references','pressure_pa'), float('nan')),
    (('references','drag_axis_world'), [2,0,0]),
    (('references','lift_axis_world'), [1,0,0]),
    (('references','speed_m_s'), 1e300),
    (('references','speed_m_s'), 1e-300),
    (('window','end_s'), 1), (('window','minimum_samples'), 3),
    (('load_axis_world',), [0,0,0]), (('bodies',), []),
])
def test_request_rejections(path, value):
    request = fixture()['request']
    target = request
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        validate_request(request)


def test_duplicate_body_and_mutated_model_rejected():
    request = fixture()['request']
    request['bodies'] *= 2
    with pytest.raises(ValueError, match='unique'):
        validate_request(request)
    model = validate_request(fixture()['request'])
    model.references.speed_m_s = -3
    with pytest.raises(ValueError):
        coefficients(model, [0,0,0], [0,0,0])


@pytest.mark.parametrize('vectors,count', [([[True,0,0]],1), ([['1',0,0]],1), ([[0,0]],1), ([[float('inf'),0,0]],1)])
def test_helper_coercion_rejected(vectors,count):
    with pytest.raises(ValueError):
        finite_vectors(vectors,count)


def test_arithmetic_overflow_rejects_results():
    request = fixture()['request']
    request['references']['area_m2'] = 1e-300
    with pytest.warns(RuntimeWarning), pytest.raises(ValueError):
        coefficients(request, [1e300,0,0], [0,0,0])
    with pytest.warns(RuntimeWarning), pytest.raises(ValueError):
        translate_moment([1e300,0,0],[0,0,0],[0,1e300,0],[0,0,0])
    data = fixture()
    for sample in data['samples']:
        sample['force_world_n'] = [1e308,0,0]
    with pytest.warns(RuntimeWarning), pytest.raises(ValueError):
        summarize(data['request'],data['samples'])


@pytest.mark.parametrize('patch', [dict(force_world_n=None), dict(reason='bad'),
    dict(valid=False), dict(valid=False,force_world_n=None,torque_world_nm=None,reason=''),
    dict(step=True), dict(time_s=-1), dict(quality='unknown')])
def test_invalid_sample_schema(patch):
    data = fixture()
    data['samples'][0].update(patch)
    with pytest.raises(ValueError):
        summarize(data['request'],data['samples'])


def test_invalid_rejected_and_unknown_samples_not_dropped():
    data = fixture()
    data['samples'][0].update(valid=False,force_world_n=None,torque_world_nm=None,reason='solid')
    with pytest.raises(ValueError,match='Invalid or rejected'):
        summarize(data['request'],data['samples'])
    data = fixture()
    data['samples'][0]['quality'] = 'rejected'
    with pytest.raises(ValueError,match='Invalid or rejected'):
        summarize(data['request'],data['samples'])
    data = fixture()
    data['samples'][0]['identity']['generation'] = 7
    with pytest.raises(ValueError,match='identity'):
        summarize(data['request'],data['samples'])
    data = fixture()
    data['samples'][0]['body_id'] = 'other'
    with pytest.raises(ValueError,match='identity'):
        summarize(data['request'],data['samples'])


@pytest.mark.parametrize('mode', ['empty','missing','order','step','end','spacing'])
def test_bad_windows(mode):
    data = fixture()
    if mode == 'empty': data['samples'] = []
    if mode == 'missing': data['samples'] = data['samples'][:-1]
    if mode == 'order': data['samples'].reverse()
    if mode == 'step': data['samples'][1]['step'] = 1
    if mode == 'end': data['request']['window']['end_s'] = 5
    if mode == 'spacing': data['samples'][1]['time_s'] = 2.1
    with pytest.raises(ValueError):
        summarize(data['request'],data['samples'])


def test_warning_and_drift_unusable_and_population_statistics():
    data = fixture()
    data['samples'][0]['quality'] = 'warning'
    out = summarize(data['request'],data['samples'])
    assert not out['usable'] and out['bodies'][0]['quality'] == 'warning'
    data = fixture()
    for sample in data['samples'][2:]: sample['force_world_n'][0] = 72
    out = summarize(data['request'],data['samples'])
    body = out['bodies'][0]
    assert not out['usable'] and body['stationarity']['absolute_coefficient_change'] == 1
    assert body['coefficient_std']['CD'] == .5
    assert body['mean']['CD'] == 1.5


def test_window_filters_outside_samples_and_multiple_bodies():
    data = fixture()
    before = copy.deepcopy(data['samples'][0]); before.update(step=0,time_s=0.)
    after = copy.deepcopy(data['samples'][-1]); after.update(step=5,time_s=5.)
    data['samples'] = [before] + data['samples'] + [after]
    data['request']['bodies'].append(dict(body_id='tail',moment_origin_world_m=[0,0,0]))
    for sample in copy.deepcopy(data['samples']):
        sample['body_id'] = 'tail'; data['samples'].append(sample)
    out = summarize(data['request'],data['samples'])
    assert [body['count'] for body in out['bodies']] == [4,4]
    data['samples'] = data['samples'][:6]
    with pytest.raises(ValueError,match='Insufficient'):
        summarize(data['request'],data['samples'])


def test_sample_bounds():
    data = fixture()
    with pytest.raises(ValueError):
        summarize(data['request'],[data['samples'][0]] * 100001)
    data['request']['bodies'].append(dict(body_id='tail',moment_origin_world_m=[0,0,0]))
    with pytest.raises(ValueError,match='Body history'):
        summarize(data['request'],[data['samples'][0]] * 100001)


def test_pressure_probe_and_explicit_surface_offset():
    request = fixture()['request']
    seen = []
    probes = [dict(probe_id='fluid',position_world_m=[1,2,3]),
              dict(probe_id='tap',position_world_m=[0,0,.1],body_id='wing',
                   surface_point_world_m=[0,0,0],outward_normal_world=[0,0,1],offset_m=.1)]
    def sampler(point):
        seen.append(point)
        return 118. if len(seen) == 1 else None
    result = sample_probes(request,probes,2.,sampler)
    assert result[0]['Cp'] == 2 and result[0]['valid']
    assert result[1]['Cp'] is None and result[1]['pressure_pa'] is None and result[1]['reason']
    assert result[1]['approximate_surface'] and seen == [[1,2,3],[0,0,.1]]


@pytest.mark.parametrize('probe', [dict(probe_id='p',position_world_m=[0,0,0],body_id='wing'),
    dict(probe_id='p',position_world_m=[0,0,0],body_id='wing',surface_point_world_m=[0,0,0],outward_normal_world=[0,0,1],offset_m=.1),
    dict(probe_id='p',position_world_m=[0,0,.1],body_id='other',surface_point_world_m=[0,0,0],outward_normal_world=[0,0,1],offset_m=.1)])
def test_bad_probe_attachment(probe):
    with pytest.raises(ValueError):
        sample_probes(fixture()['request'],[probe],1.,lambda point:0.)


def test_probe_misc_rejections():
    req = fixture()['request']; probes=[dict(probe_id='p',position_world_m=[0,0,0])]
    for value in (True,-1,float('nan')):
        with pytest.raises(ValueError): sample_probes(req,probes,value,lambda point:0.)
    for values in ([],probes*257,probes*2):
        with pytest.raises(ValueError): sample_probes(req,values,0.,lambda point:0.)
    for value in (float('nan'),True,'118'):
        with pytest.raises(ValueError): sample_probes(req,probes,0.,lambda point:value)


def test_schema_snapshots():
    root = Path(__file__).parents[1] / 'docs/schemas'
    for name, model in [('measurement-request',Request),('measurement-sample',Sample),('measurement-probe',Probe)]:
        assert json.loads((root/(name+'.schema.json')).read_text()) == model.model_json_schema()


def test_mutated_sample_probe_and_unit_vector_cannot_bypass_validation():
    data = fixture()
    sample = Sample.model_validate(data['samples'][0]); sample.valid = 'yes'
    with pytest.raises(ValueError): summarize(data['request'],[sample]+data['samples'][1:])
    probe = Probe.model_validate(dict(probe_id='p',position_world_m=[1,2,3]))
    probe.position_world_m[0] = True
    with pytest.raises(ValueError): sample_probes(data['request'],[probe],0.,lambda point:118.)
    with pytest.raises(ValueError): unit_vector([1,False,0])
