"""Finite export contracts with raw-session readback oracles, not exporter helpers."""
import csv
import itertools
import json
import uuid

import numpy as np

TABLES = ('fields', 'probes', 'loads')
SOURCES = ('normalized2D', 'physical3D', 'moving3D')
MODES = ('valid', 'expected-mismatch', 'cancel')
HEADERS = {
    'fields': ['i', 'j', 'k', 'x', 'y', 'z', 'solid', 'boundary_node', 'valid',
               'u_domain', 'v_domain', 'w_domain', 'pressure', 'density'],
    'probes': ['probe_index', 'i', 'j', 'k', 'x', 'y', 'z', 'valid',
               'u_domain', 'v_domain', 'w_domain', 'pressure', 'density', 'speed'],
    'loads': ['sample_index', 'body_id', 'local_time', 'absolute_time',
              'pivot_x', 'pivot_y', 'pivot_z', 'valid', 'force_x_domain',
              'force_y_domain', 'force_z_domain', 'torque_x_domain',
              'torque_y_domain', 'torque_z_domain', 'power'],
}
SCHEMAS = {'fields': 'hawa-field-csv-1', 'probes': 'hawa-probe-csv-1', 'loads': 'hawa-load-csv-1'}


def export_cases():
    for table, source, mode in itertools.product(TABLES, SOURCES, MODES):
        yield dict(id='exports/'+'/'.join((table, source, mode)), table=table,
                   source=source, mode=mode,
                   expected=mode == 'valid' and (table != 'loads' or source == 'moving3D'))


def source_case(source):
    if source == 'normalized2D':
        return dict(example='tgv2d-bgk', size=8)
    spec = dict(shape=[12, 12, 12], dx=.5, spacing=2., origin=[8., 12., 16.],
                basis=[[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]],
                speed=1., viscosity=.1, density=1.225, mach=.05, collision='bgk',
                solid=[], boundaries=['inlet','outlet']+['periodic']*4, time_origin_seconds=2.)
    if source == 'moving3D':
        spec['moving_bodies'] = [dict(id='body, "A"', pivot=[2.75]*3,
            geometry=dict(type='sphere', center=[2.75]*3, radius=.65),
            motion=dict(type='translation', axis=[1., 0., 0.], speed=.1, ramp=0.))]
    else:
        spec['solid'] = [int(np.ravel_multi_index((5, 5, 5), spec['shape']))]
    return spec


def readback(path, table):
    with path.open(encoding='utf-8', newline='') as stream:
        records = list(csv.reader(stream))
    assert len(records[0]) == 2 and records[0][0] == SCHEMAS[table]
    meta = json.loads(records[0][1])
    assert meta['schema'] == SCHEMAS[table] and records[1] == HEADERS[table] == meta['columns']
    rows = records[2:]
    assert len(rows) == meta['rows'] and all(len(row) == len(HEADERS[table]) for row in rows)
    return meta, rows


def verify_values(table, meta, rows, arrays, history, points, origin, basis, dx):
    """Independent exact-node/field/history oracle; interpolation is not reimplemented."""
    shape = arrays['pressure'].shape
    solid = arrays.get('solid', np.zeros(shape, bool))
    boundary = arrays.get('boundary_nodes', np.zeros(shape, bool))
    if table == 'loads':
        assert len(rows) == len(history) == 4
        for number, (row, sample) in enumerate(zip(rows, history)):
            load = sample['loads'][0]
            assert int(row[0]) == number and json.loads(row[1]) == 'body, "A"'
            assert list(map(float, row[2:4])) == [sample['time'], sample['time'] + 2.]
            # This fixture is translation at 0.1 m/s along domain X, without ramp.
            pivot = np.array([2.75 + .1*sample['time'], 2.75, 2.75])
            np.testing.assert_array_equal(list(map(float, row[4:7])), origin + pivot @ basis)
            assert row[7] == '1'
            assert list(map(float, row[8:])) == load['force'] + load['torque'] + [load['power']]
        assert meta['history']['samples'] == 4 and meta['history']['capacity'] == 10000
        assert meta['history']['truncated'] is False
        assert meta['torque_reference'] == 'instantaneous moving pivot'
        assert meta['power_sign'] == 'signed fluid work on body'
        return
    indices = list(np.ndindex(shape)) if table == 'fields' else points
    assert len(rows) == len(indices)
    for number, (row, index) in enumerate(zip(rows, indices)):
        lattice = list(index) + [0.]*(3-len(index))
        sampled = lattice if len(shape) == 3 else lattice[:2] + [0.]
        position = origin + np.asarray(sampled) @ basis * dx
        if table == 'fields':
            assert list(map(int, row[:3])) == lattice
            np.testing.assert_array_equal(list(map(float, row[3:6])), position)
            flags = [int(solid[index]), int(boundary[index])]
            valid = not any(flags)
            assert list(map(int, row[6:9])) == flags + [int(valid)]
            quantities = row[9:]
        else:
            assert int(row[0]) == number and list(map(float, row[1:4])) == lattice
            np.testing.assert_array_equal(list(map(float, row[4:7])), position)
            valid = number != 1  # The second declared probe is outside all dimensions.
            assert row[7] == str(int(valid))
            quantities = row[8:]
            index = tuple(int(v) for v in sampled[:len(shape)])
        if not valid:
            assert quantities == ['']*(5 if table == 'fields' else 6)
            continue
        velocity = [float(arrays['velocity'][(a,)+tuple(index)]) for a in range(len(shape))]
        velocity += [0.]*(3-len(shape))
        expected = velocity + [float(arrays['pressure'][tuple(index)]), float(arrays['density'][tuple(index)])]
        if table == 'probes':
            expected += [float(np.linalg.norm(velocity))]
        np.testing.assert_array_equal(list(map(float, quantities)), expected)


def exercise_export(row, directory, device):
    """Return observed acceptance, asserting precise rejection and byte preservation."""
    from hawa.plugin import Session
    from hawa.exports import export_csv
    from hawa.jobs import Cancelled
    session = Session(source_case(row['source']), device)
    try:
        session.advance(4)
        arrays = session.fields()
        history = json.loads(json.dumps(list(session.solver.moving.history))) if row['source'] == 'moving3D' else []
        spec = session.spec
        dx = float(session.flow.units.convert_length_to_pu(1))
        basis = np.asarray(spec.get('basis', np.eye(3)), float)
        origin = np.asarray(spec.get('origin', [0., 0., 0.])) * dx/spec.get('spacing', spec.get('dx', 1.))
        local_time = float(session.flow.units.convert_time_to_pu(4))
        time_origin = spec.get('time_origin_seconds', 0.)
        identity = dict(case_hash=session.key, iteration=4, state=session.state)
        path = directory/row['id']/device.replace(':', '-')/'table.csv'
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = b'previous complete destination\n'
        path.write_bytes(previous)
        points = [[2., 2., 9. if row['source'] == 'normalized2D' else 2.], [-10., -10., -10.],
                  [2., 2., 9. if row['source'] == 'normalized2D' else 2.]]
        request = dict(op='export', session=session.id, path=str(path), format='csv', table=row['table'],
                       expected=dict(identity), attribution=dict(case_id='matrix-case', revision=7, generation=3, version=2))
        if row['table'] == 'probes':request['points'] = points
        if row['mode'] == 'expected-mismatch':request['expected']['iteration'] += 1
        supported = row['table'] != 'loads' or row['source'] == 'moving3D'
        count = int(np.prod(arrays['pressure'].shape)) if row['table'] == 'fields' else (len(points) if row['table'] == 'probes' else len(history))
        cancelled = []
        def checkpoint(number):
            if row['mode'] == 'cancel' and supported and number == count:
                cancelled.append(number)
                raise Cancelled('matrix cancellation before publication')
        try:
            result = export_csv(session, request, checkpoint)
        except (ValueError, Cancelled) as exc:
            if row['mode'] == 'expected-mismatch':assert isinstance(exc, ValueError) and 'source changed' in str(exc)
            elif not supported:assert isinstance(exc, ValueError) and 'moving-body session' in str(exc)
            else:assert row['mode'] == 'cancel' and isinstance(exc, Cancelled) and cancelled == [count]
            assert path.read_bytes() == previous and list(path.parent.iterdir()) == [path]
            return False
        assert row['mode'] == 'valid' and supported
        meta, rows = readback(path, row['table'])
        assert uuid.UUID(meta['artifact_id']).version == 4
        for key, value in dict(session=session.id, case_hash=session.key, iteration=4,
                               local_time=local_time, time_origin=time_origin, absolute_time=local_time+time_origin,
                               source_state=identity['state'], attribution=request['attribution'], table=row['table']).items():
            assert meta[key] == result[key] == value
        assert result['artifact_id'] == meta['artifact_id'] and result['rows'] == len(rows)
        assert meta['backend']['selected'] == device and meta['case'] == spec
        normalized = row['source'] == 'normalized2D'
        units = dict(position='normalized length', velocity='normalized velocity', pressure='normalized pressure',
                     density='normalized density', time='normalized time') if normalized else dict(position='m', velocity='m/s', pressure='Pa', density='kg/m^3', time='s')
        if row['table'] == 'loads':units.update(force='N', torque='N*m', power='W')
        assert meta['units'] == units and meta['unit_system'] == ('benchmark-normalized' if normalized else 'SI')
        assert meta['reference_quantities'] == dict(density=spec.get('density'), speed=spec.get('speed'), reference_pressure=0., area=None, length=None, coefficients='not computed')
        verify_values(row['table'], meta, rows, arrays, history, points, origin, basis, dx)
        assert list(path.parent.iterdir()) == [path]
        return True
    finally:
        session.pause()
