"""Probe/load interchange and captured-source publication contracts."""
import csv
import json
import threading
import uuid
from types import SimpleNamespace

import numpy as np
import pytest

from hawa import exports
from hawa.jobs import Cancelled
from hawa.plugin import sample_arrays
from test_csv_export import request, snapshot as snapshot


def read(path):
    with path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.reader(stream))
    meta = json.loads(rows[0][1])
    assert rows[0][0] == meta['schema'] and rows[1] == meta['columns']
    assert len(rows) - 2 == meta['rows']
    assert all(len(row) == len(rows[1]) for row in rows[2:])
    return meta, rows[2:]


def moving(snapshot):
    session, arrays = snapshot
    session.spec.update(speed=2., density=1.2, reference_pressure=12., time_origin_seconds=10.,
                        moving_bodies=[{'id': '=sum("x")\ncomma,', 'pivot': [1., 2., 3.],
                                        'motion': {'type': 'translation', 'axis': [1., 0., 0.], 'speed': 1.}},
                                       {'id': 'fixed', 'pivot': [-1., 0., 2.]}])
    history = [{'time': t, 'loads': [{'id': body['id'], 'force': [t, -2., 3.],
                                     'torque': [4., 5., -6.], 'power': -7.}
                                    for body in session.spec['moving_bodies']]}
               for t in (.125, .25)]
    session.solver = SimpleNamespace(moving=SimpleNamespace(dt=.125, history=history))
    return session, history


def test_probe_order_duplicates_masks_positions_and_exact_sampler_values(snapshot, tmp_path):
    session, arrays = snapshot
    points = [[1.2, 1.5, 1.1], [0., 0., 0.], [-1., 0., 0.], [1.2, 1.5, 1.1], [1., 0., 0.]]
    path = tmp_path / 'probes.csv'
    result = exports.export_csv(session, request(path, table='probes', points=points))
    meta, rows = read(path)
    assert meta['schema'] == 'hawa-probe-csv-1' and result['rows'] == 5
    assert meta['columns'] == ['probe_index', 'i', 'j', 'k', 'x', 'y', 'z', 'valid',
                               'u_domain', 'v_domain', 'w_domain', 'pressure', 'density', 'speed']
    expected = sample_arrays(arrays, points)
    for index, (point, row, sample) in enumerate(zip(points, rows, expected)):
        assert int(row[0]) == index and list(map(float, row[1:4])) == point
        assert list(map(float, row[4:7])) == [2 - point[1] * .5, 3 + point[0] * .5, 4 + point[2] * .5]
        assert row[7] == str(int(sample is not None))
        if sample is None:
            assert row[8:] == [''] * 6
        else:
            assert list(map(float, row[8:])) == sample['velocity'] + [sample['pressure'], sample['density'], sample['speed']]
    assert rows[0][1:] == rows[3][1:]
    assert meta['reference_quantities'] == dict(density=1.225, speed=None, reference_pressure=0., area=None, length=None, coefficients='not computed')


def test_two_dimensional_probe_projection_and_chunking(snapshot, tmp_path):
    session, _ = snapshot
    arrays = dict(velocity=np.ones((2, 3, 3)), pressure=np.ones((3, 3)), density=np.ones((3, 3)))
    session.fields = lambda: arrays
    points = [[1., 1., 7.]] * 1025
    path = tmp_path / '2d.csv'
    checkpoints = []
    exports.export_csv(session, request(path, table='probes', points=points), checkpoints.append)
    meta, rows = read(path)
    assert checkpoints == [0, 0, 1024, 1025]
    assert 'projected to zero' in meta['two_dimensional']
    assert rows[0][1:4] == ['1.0', '1.0', '7.0']
    assert list(map(float, rows[0][4:7])) == [1.5, 3.5, 4.]
    assert list(map(float, rows[-1][8:11])) == [1., 1., 0.]


def test_load_history_raw_values_historical_pivots_ids_and_capture_scope(snapshot, tmp_path):
    session, history = moving(snapshot)
    path = tmp_path / 'loads.csv'
    result = exports.export_csv(session, request(path, table='loads'))
    meta, rows = read(path)
    assert result['table'] == 'loads' and result['rows'] == 4
    assert meta['schema'] == 'hawa-load-csv-1' and meta['columns'] == exports.LOAD_HEADER
    assert meta['units'] == dict(position='m', velocity='m/s', pressure='Pa', density='kg/m^3', time='s', force='N', torque='N*m', power='W')
    assert meta['history'] == dict(samples=2, capacity=10000, dt=.125, local_start=.125, local_end=.25,
                                  absolute_start=10.125, absolute_end=10.25, starts_after_initial_step=False,
                                  truncated=False, truncation_basis='retained start is later than first step; earlier samples not supplied',
                                  coverage='retained history only; may be truncated, reset or restored')
    assert meta['reference_quantities'] == dict(density=1.2, speed=2., reference_pressure=12., area=None, length=None, coefficients='not computed')
    assert meta['quality_scope'] == 'capture only; not historical load samples'
    assert meta['torque_reference'] == 'instantaneous moving pivot' and meta['power_sign'] == 'signed fluid work on body'
    assert meta['body_id_encoding'] == 'JSON string; decode each body_id cell with json.loads'
    for index, row in enumerate(rows):
        sample, body = divmod(index, 2)
        t = history[sample]['time']
        assert int(row[0]) == sample and json.loads(row[1]) == session.spec['moving_bodies'][body]['id']
        assert list(map(float, row[2:4])) == [t, 10 + t]
        assert list(map(float, row[4:7])) == ([0., 4 + t, 7.] if body == 0 else [2., 2., 6.])
        assert row[7] == '1' and list(map(float, row[8:])) == [t, -2., 3., 4., 5., -6., -7.]


def test_load_retention_boundary_and_snapshot_detachment(snapshot, tmp_path):
    session, history = moving(snapshot)
    history.pop(0)
    attribution = dict(case_id='case', revision=2, generation=3, version=4)
    req = request(tmp_path / 'loads.csv', table='loads', attribution=attribution)
    def checkpoint(n):
        if n == 2:
            history[0]['loads'][0]['force'][0] = 99
            session.spec['moving_bodies'][0]['id'] = 'changed'
            session.quality['warnings'].append('new')
            attribution['revision'] = 999
            session.state = 'running'
    result = exports.export_csv(session, req, checkpoint)
    meta, rows = read(tmp_path / 'loads.csv')
    assert meta['history']['truncated'] and meta['history']['starts_after_initial_step']
    assert float(rows[0][8]) == .25 and json.loads(rows[0][1]) != 'changed'
    assert meta['quality'] == {'warnings': ['x,\ny']}
    assert result['attribution']['revision'] == 2 and result['source_state'] == 'paused'
    assert meta['attribution'] == result['attribution']


@pytest.mark.parametrize('table', ['fields', 'probes', 'loads'])
def test_expected_guard_and_identity_echo(snapshot, tmp_path, table):
    session, _ = moving(snapshot)
    path = tmp_path / 'guard.csv'
    path.write_text('old')
    options = dict(table=table)
    if table == 'probes': options['points'] = [[1., 1., 1.]]
    expected = dict(case_hash='hash', iteration=7, state='paused')
    for key, bad in [('case_hash', 'other'), ('iteration', 6), ('state', 'completed')]:
        with pytest.raises(ValueError, match='source changed'):
            exports.export_csv(session, request(path, expected={**expected, key: bad}, **options))
        assert path.read_text() == 'old' and not exports.DESTINATIONS
    result = exports.export_csv(session, request(path, expected=expected, attribution={'case_id': 'same'}, **options))
    meta, _ = read(path)
    assert set(result) == {'path', 'format', 'table', 'rows', 'artifact_id', 'session', 'case_hash', 'iteration', 'local_time', 'time_origin', 'absolute_time', 'source_state', 'attribution'}
    assert str(uuid.UUID(result['artifact_id'])) == result['artifact_id']
    for key in set(result) - {'path', 'format'}: assert result[key] == meta[key]
    assert result['case_hash'] == 'hash' and result['session'] == 's' and result['iteration'] == 7
    assert result['source_state'] == 'paused' and result['local_time'] == .875 and result['absolute_time'] == 10.875
    assert meta['attribution_authority'] == 'caller-declared; not solver identity'


@pytest.mark.parametrize('options', [
    {'op': 'sample'}, {'session': ''}, {'session': 1}, {'table': []}, {'table': 'bad'},
    {'request_id': 1}, {'request_id': ''}, {'revision': -1}, {'revision': True},
    {'points': []}, {'expected': None}, {'expected': {}},
    {'expected': dict(case_hash='h', iteration=True, state='paused')},
    {'expected': dict(case_hash='', iteration=1, state='paused')},
    {'expected': dict(case_hash='h', iteration=-1, state='paused')},
    {'expected': dict(case_hash='h', iteration=1, state='')},
    {'attribution': None}, {'attribution': {'foreign': 1}}, {'attribution': {'case_id': 1}},
    {'attribution': {'case_id': ''}}, {'attribution': {'revision': True}},
    {'attribution': {'generation': -1}}, {'attribution': {'version': 1.5}},
    {'table': 'probes'}, {'table': 'probes', 'points': []},
    {'table': 'probes', 'points': [[1., 2.]]}, {'table': 'probes', 'points': [[1., True, 3.]]},
    {'table': 'probes', 'points': [[1., '2', 3.]]}, {'table': 'probes', 'points': [[1., float('inf'), 3.]]},
    {'table': 'probes', 'points': [[0, 0, 0]] * 10001},
])
def test_strict_request_errors_preserve_destination(snapshot, tmp_path, options):
    path = tmp_path / 'strict.csv'
    path.write_text('old')
    with pytest.raises(ValueError) as error: exports.export_csv(snapshot[0], request(path, **options))
    assert str(error.value) not in ('', 'None')
    assert path.read_text() == 'old' and list(tmp_path.iterdir()) == [path] and not exports.DESTINATIONS


@pytest.mark.parametrize('failure', ['stationary', 'empty', 'capacity', 'bodycount', 'dt', 'endpoint', 'time_order', 'future', 'ids', 'duplicate_ids', 'force', 'torque', 'power', 'pivot', 'record', 'missing_time', 'missing_force', 'loads_type'])
def test_invalid_load_sources_fail_without_publication(snapshot, tmp_path, failure):
    session, history = moving(snapshot)
    if failure == 'stationary': session.solver = SimpleNamespace()
    elif failure == 'empty': history.clear()
    elif failure == 'capacity': history[:] = history * 5001
    elif failure == 'bodycount': session.spec['moving_bodies'] = []
    elif failure == 'dt': session.solver.moving.dt = 0
    elif failure == 'endpoint': history[0]['time'] = 0
    elif failure == 'time_order': history[1]['time'] = .125
    elif failure == 'future': history[1]['time'] = 1.
    elif failure == 'ids': history[0]['loads'].pop()
    elif failure == 'duplicate_ids': session.spec['moving_bodies'][1]['id'] = session.spec['moving_bodies'][0]['id']
    elif failure == 'force': history[0]['loads'][0]['force'] = [1.]
    elif failure == 'torque': history[0]['loads'][0]['torque'] = None
    elif failure == 'power': history[0]['loads'][0]['power'] = True
    elif failure == 'record': history[0] = None
    elif failure == 'missing_time': del history[0]['time']
    elif failure == 'missing_force': del history[0]['loads'][0]['force']
    elif failure == 'loads_type': history[0]['loads'] = None
    else: session.spec['moving_bodies'][0]['pivot'] = [float('inf'), 0., 0.]
    path = tmp_path / 'bad.csv'
    path.write_text('old')
    with pytest.raises(ValueError) as error: exports.export_csv(session, request(path, table='loads'))
    assert str(error.value) not in ('', 'None')
    assert path.read_text() == 'old' and list(tmp_path.iterdir()) == [path] and not exports.DESTINATIONS


@pytest.mark.parametrize('table', ['fields', 'probes', 'loads'])
@pytest.mark.parametrize('failure', ['cancel', 'replace', 'partial_rows'])
def test_publication_failures_release_reservation(snapshot, tmp_path, monkeypatch, table, failure):
    session, _ = moving(snapshot)
    path = tmp_path / 'atomic.csv'
    path.write_text('old')
    options = {'table': table}
    if table == 'probes': options['points'] = [[1., 1., 1.]]
    calls = []
    def checkpoint(n):
        calls.append(n)
        if failure == 'cancel' and len(calls) == 3: raise Cancelled('before publish')
    def fail(*args): raise OSError('replace failed')
    with monkeypatch.context() as patch:
        if failure == 'replace': patch.setattr(exports.os, 'replace', fail)
        if failure == 'partial_rows': patch.setattr(exports, {'fields': 'field_rows', 'probes': 'probe_rows', 'loads': 'load_rows'}[table], lambda *args: iter([]))
        with pytest.raises((Cancelled, OSError, ValueError)) as error:
            exports.export_csv(session, request(path, **options), checkpoint)
        assert str(error.value) not in ('', 'None')
    assert path.read_text() == 'old' and list(tmp_path.iterdir()) == [path] and not exports.DESTINATIONS
    exports.export_csv(session, request(path, **options))
    read(path)


def test_canonical_destination_contention_and_independent_paths(snapshot, tmp_path):
    session, _ = snapshot
    path = tmp_path / 'same.csv'
    entered, release = threading.Event(), threading.Event()
    outcome = []
    def checkpoint(n):
        if not entered.is_set():
            entered.set()
            assert release.wait(5)
    def worker():
        try: outcome.append(exports.export_csv(session, request(path), checkpoint))
        except Exception as error: outcome.append(error)
    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert entered.wait(5)
        for alias in (tmp_path / 'child' / '..' / 'same.csv', tmp_path / 'SAME.CSV'):
            with pytest.raises(ValueError, match='already being exported'):
                exports.export_csv(session, request(alias, table='probes', points=[[1, 1, 1]]))
        exports.export_csv(session, request(tmp_path / 'other.csv'))
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and len(outcome) == 1 and isinstance(outcome[0], dict)
    assert not exports.DESTINATIONS
    read(path)


def test_identity_and_invalid_capture_time_reject_before_arrays(snapshot, tmp_path):
    session, _ = snapshot
    path = tmp_path / 'capture.csv'
    def forbidden(): raise AssertionError('read arrays before guard')
    session.fields = forbidden
    with pytest.raises(ValueError, match='identity mismatch'):
        exports.export_csv(session, request(path, session='other'))
    with pytest.raises(ValueError, match='source changed'):
        exports.export_csv(session, request(path, expected=dict(case_hash='other', iteration=7, state='paused')))
    session.spec['time_origin_seconds'] = -1
    with pytest.raises(ValueError, match='times'):
        exports.export_csv(session, request(path))
    assert not path.exists() and not exports.DESTINATIONS


@pytest.mark.parametrize('table', ['fields', 'probes', 'loads'])
def test_finite_source_coordinates_that_overflow_world_mapping_reject(snapshot, tmp_path, table):
    session, history = moving(snapshot)
    session.spec['basis'] = np.eye(3).tolist()
    options = {'table': table}
    if table == 'loads':
        session.spec['origin'] = [1.7e308, 0., 0.]
        session.spec['spacing'] = .5
        session.spec['moving_bodies'][0]['pivot'] = [1.7e308, 0., 0.]
        session.spec['moving_bodies'][0]['motion'] = {'type': 'fixed'}
    else:
        session.flow.units.convert_length_to_pu = lambda n: 1.7e308
        session.spec['origin'] = [0., 0., 0.]
        session.spec['spacing'] = 1.7e308
        if table == 'probes': options['points'] = [[2., 0., 0.]]
    path = tmp_path / 'overflow.csv'
    path.write_text('old')
    with np.errstate(over='ignore', invalid='ignore'), pytest.raises(ValueError, match='positions must be finite'):
        exports.export_csv(session, request(path, **options))
    assert path.read_text() == 'old' and list(tmp_path.iterdir()) == [path] and not exports.DESTINATIONS


def test_reconstructed_pivot_overflow_rejects(snapshot, tmp_path):
    session, _ = moving(snapshot)
    body = session.spec['moving_bodies'][0]
    body['pivot'] = [1.7e308, 0., 0.]
    body['motion']['speed'] = 1.7e308
    with np.errstate(over='ignore', invalid='ignore'), pytest.raises(ValueError, match='Historical pivot'):
        exports.export_csv(session, request(tmp_path / 'pivot.csv', table='loads'))
    assert not list(tmp_path.iterdir()) and not exports.DESTINATIONS


def test_full_retained_capacity_and_probe_upper_bound(snapshot, tmp_path):
    session, history = moving(snapshot)
    body = session.spec['moving_bodies'][1]
    session.spec['moving_bodies'] = [body]
    history[:] = [{'time': (i + 1) * .125, 'loads': [dict(id=body['id'], force=[1., 2., 3.], torque=[4., 5., 6.], power=7.)]}
                  for i in range(10000)]
    session.flow.i = 10000
    path = tmp_path / 'capacity.csv'
    result = exports.export_csv(session, request(path, table='loads'))
    meta, rows = read(path)
    assert result['rows'] == 10000 and len(rows) == 10000 and rows[-1][0] == '9999'
    assert meta['history']['samples'] == 10000 and not meta['history']['truncated']
    assert meta['history']['local_end'] == 1250.
    result = exports.export_csv(session, request(path, table='probes', points=[[1, 1, 1]] * 10000))
    assert result['rows'] == 10000 and len(read(path)[1]) == 10000


def test_destination_released_even_when_temporary_cleanup_fails(snapshot, tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path / 'cleanup.csv'
    path.write_text('old')
    original = Path.unlink
    def fail_sync(*args): raise OSError('disk failure')
    def fail_unlink(*args, **kwargs): raise PermissionError('temporary cleanup denied')
    with monkeypatch.context() as patch:
        patch.setattr(exports.os, 'fsync', fail_sync)
        patch.setattr(Path, 'unlink', fail_unlink)
        with pytest.raises(PermissionError, match='cleanup denied'):
            exports.export_csv(snapshot[0], request(path))
    assert not exports.DESTINATIONS and path.read_text() == 'old'
    for temporary in tmp_path.glob('.hawa-export.*'): original(temporary)
    exports.export_csv(snapshot[0], request(path))
    read(path)


def test_caller_request_detached_before_checkpoint(snapshot, tmp_path):
    session, _ = snapshot
    path = tmp_path / 'detached.csv'
    points = [[1., 1., 1.]]
    req = request(path, table='probes', points=points, expected=dict(case_hash='hash', iteration=7, state='paused'),
                  attribution=dict(case_id='case', revision=1, generation=2, version=3))
    def checkpoint(n):
        points[0][0] = 99.
        req['expected']['iteration'] = 999
        req['attribution']['version'] = 999
        req['path'] = str(tmp_path / 'wrong.csv')
    result = exports.export_csv(session, req, checkpoint)
    meta, rows = read(path)
    assert result['path'] == str(path) and result['attribution']['version'] == 3
    assert list(map(float, rows[0][1:4])) == [1., 1., 1.] and not (tmp_path / 'wrong.csv').exists()


def test_nonmapping_request_rejects():
    with pytest.raises(ValueError, match='CSV export requires'):
        exports.validate_request([])


def test_real_cpu_moving_session_round_trips_loads_and_probes(tmp_path):
    from hawa.plugin import dispatch, SESSIONS
    case = dict(shape=[20, 16, 12], dx=.25, spacing=.5, origin=[2., 4., 6.],
                basis=[[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]],
                speed=1., viscosity=.05, density=1., mach=.04, collision='bgk', time_origin_seconds=2.,
                moving_bodies=[dict(id='=quoted,"\nbody', pivot=[2., 2., 1.5],
                                    geometry=dict(type='sphere', center=[2., 2., 1.5], radius=.55),
                                    motion=dict(type='oscillation', axis=[0., 1., 0.], amplitude=.15, frequency=.5))])
    ident = dispatch(dict(op='create', case=case, device='cpu'))['session']
    path = tmp_path / 'actual.csv'
    try:
        with pytest.raises(ValueError, match='No load samples'):
            dispatch(dict(op='export', session=ident, path=str(path), format='csv', table='loads'))
        dispatch(dict(op='step', session=ident, steps=3))
        expected = dispatch(dict(op='body_loads', session=ident))
        result = dispatch(dict(op='export', session=ident, path=str(path), format='csv', table='loads'))
        meta, rows = read(path)
        assert result['iteration'] == 3 and len(rows) == 3 and meta['case'] == case
        for row, record in zip(rows, expected['history']):
            load = record['loads'][0]
            assert json.loads(row[1]) == load['id']
            assert list(map(float, row[2:4])) == [record['time'], 2 + record['time']]
            assert list(map(float, row[8:])) == load['force'] + load['torque'] + [load['power']]
            # Independent sinusoidal displacement and rotated/translated pivot.
            displacement = .15 * np.sin(2 * np.pi * .5 * record['time'])
            np.testing.assert_allclose(list(map(float, row[4:7])), [-1. - displacement, 4., 4.5], rtol=0, atol=1e-14)
        points = [[1., 1., 1.], [8., 8., 6.], [-1., 0., 0.]]
        expected = dispatch(dict(op='sample', session=ident, points=points))['values']
        dispatch(dict(op='export', session=ident, path=str(path), format='csv', table='probes', points=points))
        meta, rows = read(path)
        for row, sample in zip(rows, expected):
            assert row[7] == str(int(sample is not None))
            if sample is not None:
                assert list(map(float, row[8:])) == sample['velocity'] + [sample['pressure'], sample['density'], sample['speed']]
            else:
                assert row[8:] == [''] * 6
        assert meta['quality'] == SESSIONS[ident].quality
    finally:
        dispatch(dict(op='close', session=ident))
    assert ident not in SESSIONS and not exports.DESTINATIONS


@pytest.mark.parametrize('options', [
    {'session': 1},
    {'expected': dict(case_hash=1, iteration=0, state='paused')},
    {'expected': dict(case_hash='', iteration=0, state='paused')},
    {'expected': dict(case_hash='hash', iteration=True, state='paused')},
    {'expected': dict(case_hash='hash', iteration=-1, state='paused')},
    {'expected': dict(case_hash='hash', iteration=0, state=1)},
    {'expected': dict(case_hash='hash', iteration=0, state='')},
    {'table': 'probes', 'points': [(1, 2, 3)]},
])
def test_request_validation_rejects_before_capture(tmp_path, options):
    with pytest.raises(ValueError):
        exports.validate_request(request(tmp_path / 'table.csv', **options))


def test_initial_revision_and_iteration_are_valid(tmp_path):
    req = request(tmp_path / 'table.csv', revision=0,
                  expected=dict(case_hash='hash', iteration=0, state='paused'),
                  attribution=dict(revision=0, generation=0, version=0))
    assert exports.validate_request(req) == {**req, 'table': 'fields'}


def test_table_semantics_and_captured_history_are_detached(snapshot, tmp_path):
    session, history = moving(snapshot)
    req = exports.validate_request(request(tmp_path / 'loads.csv', table='loads'))
    data, meta = exports.capture(session, req)
    history[0]['loads'][0]['force'][0] = 999
    assert data[0]['loads'][0]['force'][0] == .125
    assert meta['sampling'] == 'retained step-end load history'
    assert meta['validity'] == 'complete finite load sample; not physical qualification'
    assert meta['force_axes'] == 'domain; force on body by fluid'
    assert meta['pivot_source'] == 'prescribed motion at row local_time'
    req = exports.validate_request(request(tmp_path / 'probes.csv', table='probes', points=[[1, 1, 1]]))
    _, meta = exports.capture(session, req)
    assert meta['sampling'] == 'fluid-only trilinear interpolation at requested lattice points'
    assert meta['validity'] == 'existing halfway-fluid sampling rule; invalid quantities are empty'
    assert meta['two_dimensional'] == 'third lattice coordinate is projected to zero for sampling, as in sample_arrays'


@pytest.mark.parametrize('count', [4, 5])
def test_load_body_count_boundary(snapshot, tmp_path, count):
    import copy
    session, history = moving(snapshot)
    bodies = [dict(copy.deepcopy(session.spec['moving_bodies'][0]), id=str(i)) for i in range(count)]
    session.spec['moving_bodies'] = bodies
    for record in history:
        record['loads'] = [dict(copy.deepcopy(record['loads'][0]), id=b['id']) for b in bodies]
    req = request(tmp_path / 'bodies.csv', table='loads')
    if count == 4:
        assert exports.export_csv(session, req)['rows'] == 8
    else:
        with pytest.raises(ValueError): exports.export_csv(session, req)


@pytest.mark.parametrize('failure', ['capacity', 'zero', 'boolean', 'nan', 'local_negative', 'bad_id', 'empty_id', 'nonfinite_metadata'])
def test_capture_and_load_validation_boundaries(snapshot, tmp_path, failure):
    import copy
    session, history = moving(snapshot)
    req = exports.validate_request(request(tmp_path / 'bad.csv', table='loads'))
    if failure == 'capacity': history[:] = [copy.deepcopy(history[0])] * 10001
    elif failure == 'zero': history[0]['time'] = 0
    elif failure == 'boolean': history[0]['time'] = True
    elif failure == 'nan': history[0]['time'] = float('nan')
    elif failure == 'local_negative': session.flow.units.convert_time_to_pu = lambda _: -1.
    elif failure == 'nonfinite_metadata': session.quality['residual'] = float('nan')
    elif failure in ('bad_id', 'empty_id'):
        ident = 12 if failure == 'bad_id' else ''
        session.spec['moving_bodies'][0]['id'] = ident
        for record in history: record['loads'][0]['id'] = ident
        with pytest.raises(ValueError): exports.export_csv(session, req)
        return
    with pytest.raises(ValueError): exports.capture(session, req)


def test_retention_tolerance_boundary_and_last_time_inclusive(snapshot, tmp_path):
    session, history = moving(snapshot)
    history[0]['time'] = session.solver.moving.dt * (1 + 1e-9)
    history[1]['time'] = .875 + session.solver.moving.dt * 1e-9
    exports.export_csv(session, request(tmp_path / 'boundary.csv', table='loads'))
    meta, rows = read(tmp_path / 'boundary.csv')
    assert meta['history']['truncated'] is False
    assert meta['history']['starts_after_initial_step'] is False
    assert float(rows[-1][2]) == history[1]['time']


def test_internal_history_boolean_time_rejected(snapshot, tmp_path):
    import copy
    session, history = moving(snapshot)
    session.flow.units.convert_time_to_pu = lambda _: 3.
    history.append(copy.deepcopy(history[-1]))
    history[-1]['time'] = 2.
    history[1]['time'] = True
    with pytest.raises(ValueError): exports.export_csv(session, request(tmp_path / 'bool.csv', table='loads'))
