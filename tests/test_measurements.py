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


@pytest.mark.parametrize('density,speed,expected_q', [
    (1e-200, 1e200, 5e199),
    (1e200, 1e-200, 5e-201),
])
def test_reference_products_keep_valid_scaled_extremes(density, speed, expected_q):
    """Validation and consumers use the same order; squaring U first is unsafe."""
    data = fixture()
    request = data['request']
    request['references'].update(density_kg_m3=density, speed_m_s=speed,
                                 area_m2=1., chord_m=1., pressure_pa=0.)
    validated = validate_request(request)
    force = [expected_q, 0., 2 * expected_q]
    moment = [0., expected_q / 4, 0.]
    result = coefficients(validated, force, moment)
    assert np.isfinite(result['q_pa']) and result['q_pa'] > 0
    assert result['q_pa'] / expected_q == pytest.approx(1., rel=1e-15, abs=0.)
    assert result['CD'] == pytest.approx(1., rel=1e-15, abs=0.)
    assert result['CL'] == pytest.approx(2., rel=1e-15, abs=0.)
    assert result['Cm'] == pytest.approx(.25, rel=1e-15, abs=0.)
    probe = sample_probes(validated, [dict(probe_id='p', position_world_m=[0., 0., 0.])],
                          1., lambda point: 2 * expected_q)[0]
    assert probe['Cp'] == pytest.approx(2., rel=1e-15, abs=0.)
    assert probe['valid'] and probe['pressure_pa'] != 0
    for sample in data['samples']:
        sample.update(force_world_n=force, torque_world_nm=moment)
    summary = summarize(validated, data['samples'])
    assert summary['usable']
    assert summary['bodies'][0]['mean']['CD'] == pytest.approx(1., rel=1e-15, abs=0.)


def test_complete_measurement_contract_with_nonzero_side_load_and_fluctuations():
    data = fixture()
    data['request']['window']['stationarity_absolute_coefficient_tolerance'] = 0.
    for sample, factor in zip(data['samples'], [1., 3., 1., 3.]):
        sample['force_world_n'] = [36*factor, 18*factor, 72*factor]
        sample['torque_world_nm'] = [0., 18*factor, 0.]
    output = summarize(data['request'], data['samples'])
    for key in ('schema', 'identity', 'references', 'window'):
        assert output[key] == data['request'][key]
    assert output['statistic'] == 'equal-weight population standard deviation; not confidence bounds'
    body = output['bodies'][0]
    assert body['body_id'] == 'wing' and body['quality'] == 'accepted'
    assert output['usable'] and body['usable']
    assert body['force_mean_world_n'] == [72.,36.,144.]
    assert body['torque_mean_world_nm'] == [0.,36.,0.]
    assert body['force_std_world_n'] == [36.,18.,72.]
    assert body['torque_std_world_nm'] == [0.,18.,0.]
    assert body['mean'] == dict(q_pa=9., D=72., Y=36., L=144., CD=2., CY=1., CL=4., Cm=.5, load_cell_n=72.)
    assert body['coefficient_std'] == dict(CD=1., CY=.5, CL=2., Cm=.25)
    assert body['stationarity'] == dict(passed=True, absolute_coefficient_change=0., tolerance=0.)


def test_probe_output_retains_identity_coordinates_pressure_and_zero_source_time():
    req = fixture()['request']
    probes = [dict(probe_id='p'+str(i),position_world_m=[float(i),2.,3.]) for i in range(256)]
    rows = sample_probes(req, probes, 0., lambda point:118.)
    assert len(rows) == 256
    for index,row in enumerate(rows):
        assert row == dict(schema='hawa-measurement-1', identity=req['identity'], time_s=0.,
                           probe_id='p'+str(index),position_world_m=[float(index),2.,3.],
                           body_id=None,surface_point_world_m=None,outward_normal_world=None,offset_m=None,
                           valid=True,reason='',pressure_pa=118.,Cp=2.,approximate_surface=False)
    with pytest.raises(ValueError):
        sample_probes(req,probes+[dict(probe_id='extra',position_world_m=[0.,0.,0.])],0.,lambda point:118.)


def test_summary_requires_a_list_and_checks_history_outside_window():
    data=fixture()
    with pytest.raises(ValueError):summarize(data['request'],tuple(data['samples']))
    outside=[dict(data['samples'][0],step=i,time_s=0.) for i in (0,1)]
    for index,sample in enumerate(data['samples'],2):sample['step']=index
    with pytest.raises(ValueError,match='strictly increase'):
        summarize(data['request'],outside+data['samples'])


@pytest.mark.parametrize('delta',[2e-10,1e-7])
def test_unit_axes_do_not_inherit_numpy_default_tolerances(delta):
    with pytest.raises(ValueError):unit_vector([1.+delta,0.,0.])


@pytest.mark.parametrize('duration,perturbation',[(1.,1e-7),(1e-5,1e-10)])
def test_sample_spacing_does_not_inherit_numpy_default_tolerances(duration,perturbation):
    data=fixture()
    data['request']['window'].update(start_s=0.,end_s=3*duration)
    for i,sample in enumerate(data['samples']):sample['time_s']=i*duration
    data['samples'][1]['time_s']+=perturbation
    with pytest.raises(ValueError,match='uniform'):summarize(data['request'],data['samples'])


def test_declared_maximum_history_is_accepted_without_truncation():
    data=fixture()
    samples=[dict(data['samples'][0],step=i,time_s=float(i)) for i in range(100000)]
    output=summarize(data['request'],samples)
    assert output['usable'] and output['bodies'][0]['count']==4
    with pytest.raises(ValueError,match='bounded'):
        summarize(data['request'],samples+[dict(samples[-1],step=100000,time_s=100000.)])


@pytest.mark.parametrize('scale,delta',[(1.,1e-7),(1e-5,1e-10)])
def test_endpoints_cannot_use_numpy_looser_default_tolerances(scale,delta):
    data=fixture();data['request']['window'].update(start_s=scale,end_s=4*scale)
    for sample,value in zip(data['samples'],np.linspace(scale+delta,4*scale-delta,4)):
        sample['time_s']=float(value)
    with pytest.raises(ValueError,match='endpoints'):summarize(data['request'],data['samples'])


@pytest.mark.parametrize('scale,delta',[(1.,1e-7),(1e-5,1e-10)])
def test_nearby_outside_samples_are_not_silently_admitted(scale,delta):
    data=fixture();data['request']['window'].update(start_s=scale,end_s=4*scale)
    for i,sample in enumerate(data['samples'],1):sample.update(step=i,time_s=i*scale)
    outside=[dict(data['samples'][0],step=0,time_s=scale-delta),
             dict(data['samples'][-1],step=5,time_s=4*scale+delta)]
    result=summarize(data['request'],[outside[0]]+data['samples']+[outside[1]])
    assert result['usable'] and result['bodies'][0]['count']==4


@pytest.mark.parametrize('kind',['axis','vector-shape','vector-finite','time','probe-count','probe-duplicate','probe-body','sampler'])
def test_rejections_keep_an_actionable_diagnostic(kind):
    req=fixture()['request'];probe=dict(probe_id='p',position_world_m=[0.,0.,0.])
    with pytest.raises(ValueError) as caught:
        if kind=='axis':unit_vector([2.,0.,0.])
        elif kind=='vector-shape':finite_vectors([[1.,2.]],1)
        elif kind=='vector-finite':finite_vectors([[float('nan'),0.,0.]],1)
        elif kind=='time':sample_probes(req,[probe],-1.,lambda point:0.)
        elif kind=='probe-count':sample_probes(req,[],0.,lambda point:0.)
        elif kind=='probe-duplicate':sample_probes(req,[probe,probe],0.,lambda point:0.)
        elif kind=='probe-body':
            probe.update(body_id='unknown',surface_point_world_m=[0.,0.,-1.],outward_normal_world=[0.,0.,1.],offset_m=1.)
            sample_probes(req,[probe],0.,lambda point:0.)
        else:sample_probes(req,[probe],0.,lambda point:float('inf'))
    assert str(caught.value) and str(caught.value)!='None'


def test_fixed_interval_roundoff_within_declared_tolerance_is_accepted():
    data=fixture();data['request']['window'].update(start_s=0.,end_s=3.)
    # Nominal dt=1 s; subsequent intervals deviate by only 0.75e-9 s.
    for sample,t in zip(data['samples'],[0.,1.,2.+.75e-9,3.]):sample['time_s']=t
    result=summarize(data['request'],data['samples'])
    assert result['usable'] and result['bodies'][0]['duration_s']==3.
