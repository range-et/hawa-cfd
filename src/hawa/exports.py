"""Atomic numerical tables with frozen solver identity and explicit coordinate units."""
import csv
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import uuid

import numpy as np

from . import __version__
from .boundary_data import geometry
from .fields import validate

MAX_ROWS = 250000
HEADER = ['i', 'j', 'k', 'x', 'y', 'z', 'solid', 'boundary_node', 'valid',
          'u_domain', 'v_domain', 'w_domain', 'pressure', 'density']
MARKER = 'hawa-field-csv-1'
PROBE_HEADER = ['probe_index', 'i', 'j', 'k', 'x', 'y', 'z', 'valid',
                'u_domain', 'v_domain', 'w_domain', 'pressure', 'density', 'speed']
LOAD_HEADER = ['sample_index', 'body_id', 'local_time', 'absolute_time',
               'pivot_x', 'pivot_y', 'pivot_z', 'valid', 'force_x_domain',
               'force_y_domain', 'force_z_domain', 'torque_x_domain',
               'torque_y_domain', 'torque_z_domain', 'power']
DESTINATIONS = set()
DESTINATION_LOCK = threading.Lock()


def validate_request(request):
    """Freeze the small caller payload; unknown options and coercive types reject."""
    allowed = {'op', 'session', 'path', 'format', 'request_id', 'revision',
               'table', 'points', 'expected', 'attribution'}
    if (not isinstance(request, dict) or set(request) - allowed or
            request.get('format') != 'csv' or not isinstance(request.get('path'), str) or
            not request['path'].strip()):
        raise ValueError('CSV export requires format=csv and a nonempty path; unsupported options')
    if request.get('op') != 'export' or not isinstance(request.get('session'), str) or not request['session']:
        raise ValueError('CSV export requires op=export and a session ID')
    table = request.get('table', 'fields')
    if table not in ('fields', 'probes', 'loads'):
        raise ValueError('CSV table must be fields, probes or loads')
    if 'request_id' in request and (not isinstance(request['request_id'], str) or not request['request_id']):
        raise ValueError('request_id must be a nonempty string')
    if request.get('revision') is not None and (type(request['revision']) is not int or request['revision'] < 0):
        raise ValueError('revision must be a nonnegative integer or null')
    expected = request.get('expected')
    if 'expected' in request and (not isinstance(expected, dict) or set(expected) != {'case_hash', 'iteration', 'state'} or
            not isinstance(expected['case_hash'], str) or not expected['case_hash'] or
            type(expected['iteration']) is not int or expected['iteration'] < 0 or
            not isinstance(expected['state'], str) or not expected['state']):
        raise ValueError('expected requires case_hash, nonnegative integer iteration and state')
    attribution = request.get('attribution', {})
    if not isinstance(attribution, dict) or set(attribution) - {'case_id', 'revision', 'generation', 'version'}:
        raise ValueError('attribution accepts only case_id, revision, generation and version')
    for key, value in attribution.items():
        if (key == 'case_id' and (not isinstance(value, str) or not value)) or (
                key != 'case_id' and (type(value) is not int or value < 0)):
            raise ValueError('Invalid attribution ' + key)
    points = request.get('points')
    if table == 'probes':
        if (not isinstance(points, list) or not 1 <= len(points) <= 10000 or
                any(not isinstance(p, list) or len(p) != 3 or
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in points)):
            raise ValueError('Probes require 1..10000 finite three-coordinate lattice points')
    elif 'points' in request:
        raise ValueError('points is supported only for probe CSV')
    return json.loads(json.dumps({**request, 'table': table, 'attribution': attribution}, allow_nan=False))


def capture(session, request):
    """Capture under the solver lock; expected is checked before reading arrays/history."""
    with session.lock:
        if request['session'] != session.id:
            raise ValueError('Export session identity mismatch')
        identity = dict(case_hash=session.key, iteration=session.flow.i, state=session.state)
        if request.get('expected') is not None and request['expected'] != identity:
            raise ValueError('Export source changed; refresh the completed result before exporting')
        spec = session.spec
        dx = float(session.flow.units.convert_length_to_pu(1))
        origin, basis, dx = geometry({**spec, 'dx': dx,
                                     'spacing': spec.get('spacing', spec.get('dx', 1.))})
        local_time = float(session.flow.units.convert_time_to_pu(session.flow.i))
        time_origin = float(spec.get('time_origin_seconds', 0.))
        if not math.isfinite(local_time) or local_time < 0 or not math.isfinite(time_origin) or time_origin < 0:
            raise ValueError('Capture times must be finite and nonnegative')
        normalized = 'example' in spec
        units = {'position': 'normalized length' if normalized else 'm',
                 'velocity': 'normalized velocity' if normalized else 'm/s',
                 'pressure': 'normalized pressure' if normalized else 'Pa',
                 'density': 'normalized density' if normalized else 'kg/m^3',
                 'time': 'normalized time' if normalized else 's'}
        table = request['table']
        meta = dict(schema=MARKER, table=table, columns=HEADER, units=units,
                    unit_system='benchmark-normalized' if normalized else 'SI',
                    session=session.id, case_hash=session.key, case=spec,
                    hawa_version=__version__, backend=session.backend.info(),
                    iteration=session.flow.i, local_time=local_time, time_origin=time_origin,
                    absolute_time=time_origin + local_time, source_state=session.state,
                    artifact_id=str(uuid.uuid4()), attribution=request['attribution'],
                    attribution_authority='caller-declared; not solver identity',
                    quality=session.quality, quality_scope='capture only; not historical load samples',
                    sampling='instantaneous lattice nodes', origin=origin.tolist(), basis=basis.tolist(), dx=dx,
                    velocity_axes='domain; world vector = domain vector @ basis',
                    pressure_reference='solver gauge pressure relative to rest density; no coefficient conversion',
                    reference_quantities={'density': spec.get('density', None if normalized else 1.225),
                                          'speed': spec.get('speed'), 'reference_pressure': spec.get('reference_pressure', 0.),
                                          'area': None, 'length': None, 'coefficients': 'not computed'},
                    validity='valid = not (solid or boundary_node); invalid quantities are empty',
                    precision='Python float round-trip decimal; float32 values promoted exactly')
        if table == 'loads':
            moving = getattr(session.solver, 'moving', None)
            if moving is None:
                raise ValueError('Load CSV requires a moving-body session')
            history = list(moving.history)
            if not history:
                raise ValueError('No load samples; advance the moving-body session at least one step')
            if not 1 <= len(history) <= 10000 or not 1 <= len(spec.get('moving_bodies', [])) <= 4:
                raise ValueError('Load history exceeds 10000 samples or has invalid body count')
            if any(not isinstance(record, dict) or not {'time', 'loads'}.issubset(record) for record in history):
                raise ValueError('Load history records require time and loads')
            first, last = history[0]['time'], history[-1]['time']
            if any(type(t) not in (int, float) or not math.isfinite(t) or t <= 0 for t in (first, last)):
                raise ValueError('Load history endpoints must be finite positive times')
            dt = float(moving.dt)
            if not math.isfinite(dt) or dt <= 0:
                raise ValueError('Load history requires a positive finite time step')
            meta.update(schema='hawa-load-csv-1', columns=LOAD_HEADER,
                        rows=len(history) * len(spec['moving_bodies']),
                        units={**units, 'force': 'N', 'torque': 'N*m', 'power': 'W'},
                        sampling='retained step-end load history', validity='complete finite load sample; not physical qualification',
                        body_id_encoding='JSON string; decode each body_id cell with json.loads',
                        force_axes='domain; force on body by fluid', torque_reference='instantaneous moving pivot',
                        power_sign='signed fluid work on body', pivot_source='prescribed motion at row local_time',
                        history={'samples': len(history), 'capacity': 10000, 'dt': dt,
                                 'local_start': first, 'local_end': last,
                                 'absolute_start': time_origin + first, 'absolute_end': time_origin + last,
                                 'starts_after_initial_step': first > dt * (1 + 1e-9),
                                 'truncated': first > dt * (1 + 1e-9),
                                 'truncation_basis': 'retained start is later than first step; earlier samples not supplied',
                                 'coverage': 'retained history only; may be truncated, reset or restored'})
            data = history
        else:
            data = session.fields()
            validate(data, {'case': spec})
            shape = data['pressure'].shape
            rows = int(np.prod(shape)) if table == 'fields' else len(request['points'])
            if table == 'fields' and rows > MAX_ROWS:
                raise ValueError('CSV export exceeds 250000 cells; use NPZ or a smaller case')
            meta.update(shape=list(shape), rows=rows)
            if table == 'probes':
                meta.update(schema='hawa-probe-csv-1', columns=PROBE_HEADER,
                            sampling='fluid-only trilinear interpolation at requested lattice points',
                            validity='existing halfway-fluid sampling rule; invalid quantities are empty',
                            two_dimensional='third lattice coordinate is projected to zero for sampling, as in sample_arrays')
        # Detach nested case/quality/history/attribution while their owner is locked.
        frozen = json.loads(json.dumps({'metadata': meta, 'history': data if table == 'loads' else None}, allow_nan=False))
        return frozen['history'] if table == 'loads' else data, frozen['metadata']


def field_rows(arrays, meta):
    """Preserve the version-1 field table exactly, including domain-axis quantities."""
    shape = arrays['pressure'].shape
    solid = arrays.get('solid', np.zeros(shape, dtype=bool))
    boundary = arrays.get('boundary_nodes', np.zeros(shape, dtype=bool))
    for index in np.ndindex(shape):
        ijk = list(index) + [0] * (3 - len(index))
        position = np.asarray(meta['origin']) + np.asarray(ijk) @ np.asarray(meta['basis']) * meta['dx']
        if not np.isfinite(position).all():
            raise ValueError('Export positions must be finite')
        valid = not (solid[index] or boundary[index])
        quantities = [''] * 5
        if valid:
            quantities = [float(arrays['velocity'][(axis,) + index]) for axis in range(len(shape))]
            quantities += [0.] * (3 - len(shape))
            quantities += [float(arrays['pressure'][index]), float(arrays['density'][index])]
        yield ijk + position.tolist() + [int(solid[index]), int(boundary[index]), int(valid)] + quantities


def probe_rows(arrays, meta, points):
    """Retain requested order/duplicates, using the existing sampler in bounded chunks."""
    from .plugin import sample_arrays
    for start in range(0, len(points), 1024):
        for offset, value in enumerate(sample_arrays(arrays, points[start:start + 1024])):
            point = points[start + offset]
            # The existing 2D sampler projects the third coordinate. Position is
            # the actual sampled plane, while i/j/k preserve the caller request.
            sampled = point if arrays['pressure'].ndim == 3 else point[:2] + [0.]
            position = np.asarray(meta['origin']) + np.asarray(sampled) @ np.asarray(meta['basis']) * meta['dx']
            if not np.isfinite(position).all():
                raise ValueError('Export positions must be finite')
            quantities = [''] * 6 if value is None else value['velocity'] + [value['pressure'], value['density'], value['speed']]
            yield [start + offset] + point + position.tolist() + [int(value is not None)] + quantities


def load_rows(history, meta):
    """Raw signed loads with historical physical pivots; never infer coefficients."""
    from .motion import pose
    bodies = meta['case']['moving_bodies']
    ids = [body['id'] for body in bodies]
    if any(not isinstance(ident, str) or not ident for ident in ids) or len(set(ids)) != len(ids):
        raise ValueError('Load history requires unique nonempty body IDs')
    previous = 0.
    for number, record in enumerate(history):
        time = record['time']
        if type(time) not in (int, float) or not math.isfinite(time) or time <= previous or time > meta['local_time'] + meta['history']['dt'] * 1e-9:
            raise ValueError('Load history times must increase and not exceed capture time')
        previous = time
        loads = record['loads']
        if (not isinstance(loads, list) or len(loads) != len(ids) or
                any(not isinstance(load, dict) or not {'id', 'force', 'torque', 'power'}.issubset(load) for load in loads) or
                [load['id'] for load in loads] != ids):
            raise ValueError('Load history body IDs must match case order without gaps')
        for body, load in zip(bodies, loads):
            force, torque, power = load['force'], load['torque'], load['power']
            if (not isinstance(force, list) or len(force) != 3 or not isinstance(torque, list) or len(torque) != 3 or
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in force + torque + [power])):
                raise ValueError('Load history requires finite force, torque and power')
            pivot = np.asarray(pose(body, time)['pivot'])
            if not np.isfinite(pivot).all():
                raise ValueError('Historical pivot must be finite')
            world = np.asarray(meta['origin']) + pivot @ np.asarray(meta['basis'])
            if not np.isfinite(world).all():
                raise ValueError('Export positions must be finite')
            yield [number, json.dumps(body['id'], ensure_ascii=False), time, meta['time_origin'] + time] + world.tolist() + [1] + force + torque + [power]


def export_csv(session, request, checkpoint=None):
    """Reserve destination, freeze source, then atomically publish one complete table."""
    request = validate_request(request)
    path = Path(request['path'])
    destination = str(path.resolve()).casefold()
    with DESTINATION_LOCK:
        if destination in DESTINATIONS:
            raise ValueError('CSV destination is already being exported; wait or choose another path')
        DESTINATIONS.add(destination)
    temporary = None
    try:
        if checkpoint is not None:
            checkpoint(0)
        data, meta = capture(session, request)
        table = request['table']
        if table == 'fields':
            rows = field_rows(data, meta)
        elif table == 'probes':
            rows = probe_rows(data, meta, request['points'])
        else:
            rows = load_rows(data, meta)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         dir=path.parent, prefix='.hawa-export.',
                                         suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            writer = csv.writer(out)
            writer.writerow([meta['schema'], json.dumps(meta, allow_nan=False)])
            writer.writerow(meta['columns'])
            written = 0
            for number, row in enumerate(rows):
                if checkpoint is not None and number % 1024 == 0:
                    checkpoint(number)
                writer.writerow(row)
                written += 1
            if written != meta['rows']:
                raise ValueError('CSV row count changed during export')
            out.flush()
            os.fsync(out.fileno())
        if checkpoint is not None:
            checkpoint(meta['rows'])
        os.replace(temporary, path)
    finally:
        try:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        finally:
            with DESTINATION_LOCK:
                DESTINATIONS.remove(destination)
    keys = ('table', 'rows', 'artifact_id', 'session', 'case_hash', 'iteration', 'local_time',
            'time_origin', 'absolute_time', 'source_state', 'attribution')
    return {'path': str(path), 'format': 'csv', **{key: meta[key] for key in keys}}
