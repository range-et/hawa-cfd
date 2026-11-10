"""Malformed persisted/view inputs fail before publishing a result."""
import json
import numpy as np
import pytest
from hawa import fields
from hawa.field_collection import FieldCollection
from hawa.recording import read_manifest
from test_field_collection import frame


def arrays():
    return {'velocity': np.zeros((3, 4, 4, 4)), 'pressure': np.zeros((4, 4, 4)),
            'density': np.ones((4, 4, 4))}


@pytest.mark.parametrize('extra,message', [({'solid': np.zeros((4,4,4))}, 'boolean'),
    ({'solid': np.zeros((3,4,4), bool)}, 'boolean'),
    ({'strain_rate': np.zeros((3,4,4,4))}, 'strain rate'),
    ({'strain_rate': np.full((3,3,4,4,4), np.nan)}, 'strain rate'),
    ({'wall_velocity': np.zeros((2,4,4))}, 'wall velocity'),
    ({'wall_velocity': np.full((3,4,4), np.inf)}, 'wall velocity')])
def test_optional_frame_arrays_are_validated(extra, message):
    data = arrays(); assert fields.validate(data, {'case': {}}) > 0
    data.update(extra)
    with pytest.raises(ValueError, match=message): fields.validate(data, {'case': {}})


@pytest.mark.parametrize('metadata', [None, [], {}, {'case': None}])
def test_frame_requires_case_metadata(metadata):
    with pytest.raises(ValueError, match='case metadata'): fields.validate(arrays(), metadata)


def test_field_unknown_scalar_action_and_trace_limits():
    data = arrays()
    with pytest.raises(ValueError, match='Field:'): fields.scalar(data, 'temperature', {})
    key = fields.store(data, {'case': {}})['frame']
    with pytest.raises(ValueError, match='Unknown'): fields.dispatch_field({'action': 'unknown', 'frame': key})
    for args in ({'steps': 0}, {'step': .001}, {'direction': 0}):
        with pytest.raises(ValueError, match='Trace limits'): fields.trace(data, [[1,1,1]], **args)


@pytest.mark.parametrize('keys', [None, (), [], ['x']*17, [1]])
def test_collection_requires_bounded_frame_identifiers(keys):
    with pytest.raises(ValueError, match='1..16'): FieldCollection(keys, 'speed')


def test_collection_rejects_reference_mismatch_bad_points_and_actions():
    a, b = frame(), frame()
    fields.get(b)[1]['case']['reference_pressure'] = 1.
    with pytest.raises(ValueError, match='Pressure references'): FieldCollection([a,b], 'pressure')
    collection = FieldCollection([a,b], 'speed')
    for points in ([1,2,3], [[1,2]], [[np.nan,0,0]], [[0,0,0]]*10001):
        with pytest.raises(ValueError, match='three-coordinate'): collection.sample(points)
    for args in ({'steps': True}, {'steps': 0}, {'step': 2.}, {'direction': 0}):
        with pytest.raises(ValueError, match='Trace limits'): collection.trace([[1,1,1]], **args)
    with pytest.raises(ValueError, match='Multi-domain'): fields.dispatch_field({'action': 'unknown', 'frames': [a,b]})


@pytest.mark.parametrize('data,message', [({}, 'case metadata'),
    ({'case': {}, 'frames': []}, '1..1000'),
    ({'case': {}, 'frames': [{}]}, 'filename'),
    ({'case': {}, 'frames': [{'file': 3}]}, 'filename'),
    ({'case': {}, 'frames': [{'file': 'a.npz', 'time': float('nan')}]}, 'finite and increase'),
    ({'case': {}, 'frames': [{'file': 'a.npz', 'time': 1.}, {'file': 'b.npz', 'time': 1.}]}, 'finite and increase')])
def test_recording_manifest_rejects_malformed_entries(tmp_path, data, message):
    path = tmp_path/'manifest.json'; path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=message): read_manifest(path)


def test_polar_parser_skips_non_numeric_header_rows(tmp_path):
    from hawa.airfoils import read_polar
    path = tmp_path/'polar.csv'
    path.write_text('alpha,cl,cd\nunits,none,none\n0,0,.01\n1,.1,.02\n')
    parsed = read_polar(path)
    assert parsed['rows'] == [[0., 0., .01, None], [1., .1, .02, None]]
