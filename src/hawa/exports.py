"""Versioned, atomic numerical field tables; raw NPZ remains a separate contract."""
import csv
import json
import os
from pathlib import Path
import tempfile

import numpy as np

from . import __version__
from .boundary_data import geometry
from .fields import validate

MAX_ROWS = 250000
HEADER = ['i', 'j', 'k', 'x', 'y', 'z', 'solid', 'boundary_node', 'valid',
          'u_domain', 'v_domain', 'w_domain', 'pressure', 'density']
MARKER = 'hawa-field-csv-1'


def export_csv(session, request, checkpoint=None):
    """Write one instantaneous table, checking cancellation before atomic publication.

    Coordinates use physical units and the case basis; velocity remains in domain
    axes, without reconstruction. Invalid flow cells have empty quantity columns.
    The JSON preamble declares the expected row count for truncated-file detection.
    """
    allowed = {'op', 'session', 'path', 'format', 'request_id', 'revision'}
    if (set(request) - allowed or request.get('format') != 'csv' or
            not isinstance(request.get('path'), str) or not request['path'].strip()):
        raise ValueError('CSV export requires format=csv and a nonempty path; unsupported options')
    if checkpoint is not None:
        checkpoint(0)
    # Freeze JSON while holding the same lock as the fields: nested quality/case
    # records can otherwise change during file IO. No registry frame is retained.
    with session.lock:
        arrays = session.fields()
        spec = session.spec
        dx = float(session.flow.units.convert_length_to_pu(1))
        origin, basis, dx = geometry({**spec, 'dx': dx,
                                     'spacing': spec.get('spacing', spec.get('dx', 1.))})
        shape = arrays['pressure'].shape
        rows = int(np.prod(shape))
        if rows > MAX_ROWS:
            raise ValueError('CSV export exceeds 250000 cells; use NPZ or a smaller case')
        validate(arrays, {'case': spec})
        normalized = 'example' in spec
        units = {'position': 'normalized length' if normalized else 'm',
                 'velocity': 'normalized velocity' if normalized else 'm/s',
                 'pressure': 'normalized pressure' if normalized else 'Pa',
                 'density': 'normalized density' if normalized else 'kg/m^3',
                 'time': 'normalized time' if normalized else 's'}
        local_time = float(session.flow.units.convert_time_to_pu(session.flow.i))
        time_origin = float(spec.get('time_origin_seconds', 0.))
        metadata = json.dumps({
            'schema': MARKER, 'rows': rows, 'shape': list(shape), 'columns': HEADER,
            'units': units, 'unit_system': 'benchmark-normalized' if normalized else 'SI',
            'session': session.id, 'case_hash': session.key, 'case': spec,
            'hawa_version': __version__, 'backend': session.backend.info(),
            'iteration': session.flow.i,
            'local_time': local_time, 'time_origin': time_origin,
            'absolute_time': time_origin + local_time,
            'quality': session.quality, 'sampling': 'instantaneous lattice nodes',
            'origin': origin.tolist(), 'basis': basis.tolist(), 'dx': dx,
            'velocity_axes': 'domain; world vector = domain vector @ basis',
            'pressure_reference': 'solver gauge pressure relative to rest density; no coefficient conversion',
            'validity': 'valid = not (solid or boundary_node); invalid quantities are empty',
            'precision': 'Python float round-trip decimal; float32 values promoted exactly',
        }, allow_nan=False)
    path = Path(request['path'])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         dir=path.parent, prefix='.hawa-export.',
                                         suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            writer = csv.writer(out)
            writer.writerow([MARKER, metadata])
            writer.writerow(HEADER)
            solid = arrays.get('solid', np.zeros(shape, dtype=bool))
            boundary = arrays.get('boundary_nodes', np.zeros(shape, dtype=bool))
            for number, index in enumerate(np.ndindex(shape)):
                if checkpoint is not None and number % 1024 == 0:
                    checkpoint(number)
                ijk = list(index) + [0] * (3 - len(index))
                position = origin + np.asarray(ijk) @ basis * dx
                valid = not (solid[index] or boundary[index])
                quantities = [''] * 5
                if valid:
                    quantities = [float(arrays['velocity'][(axis,) + index])
                                  for axis in range(len(shape))]
                    quantities += [0.] * (3 - len(shape))
                    quantities += [float(arrays['pressure'][index]), float(arrays['density'][index])]
                writer.writerow(ijk + position.tolist() +
                                [int(solid[index]), int(boundary[index]), int(valid)] + quantities)
            out.flush()
            os.fsync(out.fileno())
        if checkpoint is not None:
            checkpoint(rows)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {'path': str(path), 'format': 'csv', 'rows': rows}
