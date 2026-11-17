"""Self-contained native checkpoints; validation precedes new-session publication."""
import json
import math
import os
from pathlib import Path
import tempfile
import time
import uuid
import zipfile

import numpy as np

from . import __version__
from .exports import DESTINATIONS, DESTINATION_LOCK

SCHEMA = 'hawa-native-data-1'
MAX_BYTES = 256 * 1024**2
MAX_METADATA = 16 * 1024**2


def frozen(value):
    """Reject non-JSON/nonfinite caller state and detach every nested value."""
    return json.loads(json.dumps(value, allow_nan=False))


def context(value):
    if (not isinstance(value, dict) or set(value) - {'case_id', 'revision', 'generation', 'version'} or
            any((not isinstance(v, str) or not v) if k == 'case_id' else (type(v) is not int or v < 0)
                for k, v in value.items())):
        raise ValueError('Native data context requires a case ID and nonnegative integer stamps')
    return frozen(value)


def validate_case(spec):
    from .plugin import check_case
    allowed = {'kind', 'label', 'hawa_block_width', 'shape', 'origin', 'origin_m', 'spacing',
               'dx', 'speed', 'viscosity', 'density', 'mach', 'collision', 'boundaries',
               'solid', 'wall_links', 'basis', 'time_origin_seconds', 'memory_limit_mb'}
    if (not isinstance(spec, dict) or set(spec) - allowed or
            not {'shape', 'dx', 'speed', 'viscosity'}.issubset(spec)):
        raise ValueError('Native data supports only self-contained stationary native 3D cases')
    if spec.get('basis', np.eye(3).tolist()) != np.eye(3).tolist():
        raise ValueError('Native data requires an axis-aligned case')
    check_case(spec)
    from .boundary_data import geometry
    origin, _, _ = geometry(spec)
    if 'origin_m' in spec and not np.allclose(np.asarray(spec['origin_m'], float), origin, rtol=1e-12, atol=1e-12):
        raise ValueError('Native case physical and model origins disagree')
    if 'wall_links' in spec and spec['wall_links']:
        links = np.asarray(spec['wall_links'], float)
        if (links.ndim != 2 or links.shape[1] != 3 or not np.isfinite(links).all() or
                np.any(links[:, :2] != np.floor(links[:, :2])) or
                np.any(links[:, 0] < 1) or np.any(links[:, 0] >= 19) or
                np.any(links[:, 1] < 0) or np.any(links[:, 1] >= math.prod(spec['shape'])) or
                np.any(links[:, 2] <= 0) or np.any(links[:, 2] > 1)):
            raise ValueError('Invalid native wall links')


def validate_payload(populations, meta, means):
    from .plugin import case_key
    from .quality import validate_provenance
    keys = {'schema', 'artifact_id', 'case', 'case_hash', 'iteration', 'local_time', 'time_origin',
            'absolute_time', 'source_state', 'source_session', 'quality', 'native_settings',
            'attribution', 'population_storage', 'hawa_version', 'samples', 'initial_mass'}
    if not isinstance(meta, dict) or set(meta) != keys or meta['schema'] != SCHEMA or meta['population_storage'] != 'f':
        raise ValueError('Unsupported native data metadata schema')
    validate_case(meta['case'])
    if (meta['case_hash'] != case_key(meta['case']) or type(meta['iteration']) is not int or meta['iteration'] < 0 or
            any(not isinstance(meta[k], str) or not meta[k] for k in ('artifact_id', 'source_session', 'hawa_version')) or
            meta['source_state'] not in ('ready', 'paused', 'completed')):
        raise ValueError('Invalid native data capture identity')
    if any(type(meta[k]) not in (int, float) or not math.isfinite(meta[k]) or meta[k] < 0
           for k in ('local_time', 'time_origin', 'absolute_time')):
        raise ValueError('Invalid native data time')
    spec = meta['case']
    expected_time = meta['iteration'] * spec['dx'] * spec.get('mach', .05) / (math.sqrt(3) * spec.get('speed', 1))
    if (not math.isclose(meta['local_time'], expected_time, rel_tol=1e-12, abs_tol=1e-12) or
            meta['time_origin'] != spec.get('time_origin_seconds', 0.) or
            meta['absolute_time'] != meta['local_time'] + meta['time_origin']):
        raise ValueError('Native data time does not match the case and iteration')
    if (populations.dtype != np.dtype('float32') or populations.shape != (19, *spec['shape']) or
            not np.isfinite(populations).all() or not np.isfinite(populations.sum(axis=0)).all() or
            np.any(populations.sum(axis=0) <= 0)):
        raise ValueError('Native populations require finite float32 D3Q19 data and positive density')
    if (type(meta['initial_mass']) not in (int, float) or not math.isfinite(meta['initial_mass']) or meta['initial_mass'] <= 0 or
            type(meta['samples']) is not int or not 0 <= meta['samples'] <= meta['iteration'] // 5 or
            set(means) != ({'mean_u', 'mean_p', 'mean_rho'} if meta['samples'] else set())):
        raise ValueError('Invalid native mass baseline or averaging state')
    for name, array in means.items():
        if (array.dtype != np.dtype('float32') or array.shape != ((3 if name == 'mean_u' else 1), *spec['shape']) or
                not np.isfinite(array).all() or (name == 'mean_rho' and np.any(array <= 0))):
            raise ValueError('Invalid native mean field')
    quality = meta['quality']
    if (not isinstance(quality, dict) or quality.get('policy') != 'hawa-low-mach-v1' or
            quality.get('status') not in ('within-tested-envelope', 'warning', 'rejected') or
            type(quality.get('iteration')) is not int or quality['iteration'] != meta['iteration'] or
            type(quality.get('time_seconds')) not in (int, float) or
            not math.isclose(quality.get('time_seconds', -1), meta['local_time'], rel_tol=1e-12, abs_tol=1e-12)):
        raise ValueError('Invalid native data quality history')
    validate_provenance(quality, meta['iteration'])
    if not isinstance(meta['native_settings'], dict):
        raise ValueError('native_settings must be a caller-declared object')
    context(meta['attribution'])
    frozen(meta)


def read_archive(path, checkpoint=lambda n: None):
    """Bound both ZIP expansion and NPY-declared allocation before loading arrays."""
    checkpoint(0)
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = {e.filename for e in entries}
        base = {'metadata.npy', 'populations.npy'}
        if len(entries) != len(names) or names not in (base, base | {'mean_u.npy', 'mean_p.npy', 'mean_rho.npy'}):
            raise ValueError('Native data requires metadata, populations and complete optional means')
        if sum(e.file_size for e in entries) > MAX_BYTES:
            raise ValueError('Native data exceeds 256 MiB expanded budget')
        for entry in entries:
            with archive.open(entry) as stream:
                version = np.lib.format.read_magic(stream)
                if version == (1, 0): shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
                elif version == (2, 0): shape, _, dtype = np.lib.format.read_array_header_2_0(stream)
                else: raise ValueError('Unsupported native NPY version')
                size = math.prod(shape) * dtype.itemsize
                if (dtype.hasobject or dtype.fields is not None or size + stream.tell() != entry.file_size or
                        (entry.filename == 'metadata.npy' and (shape != () or dtype.kind != 'U' or size > MAX_METADATA)) or
                        (entry.filename != 'metadata.npy' and (len(shape) != 4 or dtype != np.dtype('float32')))):
                    raise ValueError('Invalid or oversized native NPY header')
        checkpoint(0)
        with archive.open('metadata.npy') as stream:
            meta = json.loads(str(np.load(stream, allow_pickle=False)))
        with archive.open('populations.npy') as stream:
            populations = np.load(stream, allow_pickle=False)
        means = {}
        for name in ('mean_u', 'mean_p', 'mean_rho'):
            if name + '.npy' in names:
                with archive.open(name + '.npy') as stream:
                    means[name] = np.load(stream, allow_pickle=False)
    validate_payload(populations, meta, means)
    checkpoint(0)
    return populations, meta, means


def save(session, request, checkpoint=lambda n: None):
    from .plugin import case_key
    allowed = {'op', 'action', 'session', 'path', 'expected', 'native_settings', 'attribution'}
    if (set(request) - allowed or request.get('op') != 'data' or request.get('action') != 'save' or
            not isinstance(request.get('path'), str) or not request['path'].strip()):
        raise ValueError('Native data save requires a path and supported options')
    request = frozen(request)
    expected = request.get('expected')
    if (not isinstance(expected, dict) or set(expected) != {'case_hash', 'iteration', 'state'} or
            not isinstance(expected['case_hash'], str) or not expected['case_hash'] or
            type(expected['iteration']) is not int or expected['iteration'] < 0 or
            expected['state'] not in ('ready', 'paused', 'completed')):
        raise ValueError('Native save requires an exact stopped source stamp')
    attribution = context(request.get('attribution', {}))
    path = Path(request['path']).resolve()
    key = str(path).casefold()
    with DESTINATION_LOCK:
        if key in DESTINATIONS:
            raise ValueError('Destination is already being exported')
        DESTINATIONS.add(key)
    temporary = None
    try:
        checkpoint(0)
        with session.lock:
            expected = {'case_hash': session.key, 'iteration': session.flow.i, 'state': session.state}
            if (request.get('session') != session.id or request.get('expected') != expected or
                    session.state not in ('ready', 'paused', 'completed') or
                    (session.thread is not None and session.thread.is_alive())):
                raise ValueError('Native save requires the exact stopped source; refresh and retry')
            populations = session.flow.f.detach().cpu().numpy().copy()
            means = {name: getattr(session, name).detach().cpu().numpy().copy()
                     for name in ('mean_u', 'mean_p', 'mean_rho')} if session.samples else {}
            local = float(session.flow.units.convert_time_to_pu(session.flow.i))
            origin = session.spec.get('time_origin_seconds', 0.)
            meta = frozen(dict(schema=SCHEMA, artifact_id=str(uuid.uuid4()), case=session.spec,
                               case_hash=case_key(session.spec), iteration=session.flow.i,
                               local_time=local, time_origin=origin, absolute_time=origin + local,
                               source_state=session.state, source_session=session.id, quality=session.quality,
                               native_settings=request.get('native_settings', {}), attribution=attribution,
                               population_storage='f', hawa_version=__version__,
                               samples=session.samples, initial_mass=session.initial_mass))
        validate_payload(populations, meta, means)
        metadata = np.array(json.dumps(meta, allow_nan=False))
        if metadata.nbytes > MAX_METADATA or metadata.nbytes + populations.nbytes + sum(a.nbytes for a in means.values()) + 4096 > MAX_BYTES:
            raise ValueError('Native data exceeds the archive budget')
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.hawa-data.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            np.savez_compressed(stream, populations=populations, metadata=metadata, **means)
            stream.flush()
            os.fsync(stream.fileno())
        checkpoint(1)
        os.replace(temporary, path)
        return {'path': str(path), 'format': 'npz', 'schema': SCHEMA, 'metadata': meta}
    finally:
        try:
            if temporary is not None: temporary.unlink(missing_ok=True)
        finally:
            with DESTINATION_LOCK: DESTINATIONS.remove(key)


def restore(session, populations, meta, means):
    """Restore only a newly allocated, unpublished job-owned session; never advance."""
    from .quality import assess
    if session.key != meta['case_hash'] or tuple(session.flow.f.shape) != populations.shape:
        raise ValueError('Restored session does not match archived case')
    with session.lock:
        session.flow.f.copy_(session.flow.context.convert_to_tensor(populations))
        session.flow.i = meta['iteration']
        session.target = meta['iteration']
        session.initial_mass = meta['initial_mass']
        session.samples = meta['samples']
        for name in ('mean_u', 'mean_p', 'mean_rho'):
            setattr(session, name, session.flow.context.convert_to_tensor(means[name]) if name in means else None)
        session.relative_mass_change = (float(session.flow.rho().sum().cpu()) - session.initial_mass) / session.initial_mass
        session.quality = frozen(meta['quality'])
        session.quality = assess(session)
        session.state = 'paused'
        session.updated = time.time()
