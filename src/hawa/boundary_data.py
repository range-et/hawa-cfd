"""Bounded offline parent-to-child inlet transfer, in physical coordinates/time."""
import hashlib
import json
import math
from pathlib import Path
import zipfile
import numpy as np
import torch
import lettuce as lt

MAX_BYTES = 64 * 1024**2
SCHEMA = 'hawa-boundary-series-1'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''): h.update(block)
    return h.hexdigest()


def geometry(spec):
    spacing = float(spec.get('spacing', spec['dx']))
    dx = float(spec['dx'])
    basis = np.asarray(spec.get('basis', np.eye(3)), float)
    origin = np.asarray(spec.get('origin', [0, 0, 0]), float) * dx / spacing
    if (not np.isfinite([spacing, dx]).all() or min(spacing, dx) <= 0 or
        basis.shape != (3, 3) or not np.isfinite(basis).all() or
        origin.shape != (3,) or not np.isfinite(origin).all() or
        not np.allclose(basis @ basis.T, np.eye(3), atol=1e-7) or np.linalg.det(basis) < .999999):
        raise ValueError('Boundary mapping requires a finite right-handed orthonormal basis and positive spacing')
    return origin, basis, dx


def grid_key(spec):
    o, b, dx = geometry(spec)
    return {'shape': list(spec['shape']), 'origin_m': o.tolist(), 'basis': b.tolist(), 'dx_m': dx}


def read(path, expected_hash=None, allow_wall_zero=False):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES: raise ValueError('Boundary file exceeds 64 MiB budget')
    if expected_hash and digest(path) != expected_hash: raise ValueError('Boundary file changed; import again')
    with zipfile.ZipFile(path) as z:
        if sum(v.file_size for v in z.infolist()) > MAX_BYTES: raise ValueError('Expanded boundary file exceeds 64 MiB')
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z['metadata']))
        times, velocity = z['times'], z['velocity']
    if meta.get('schema') != SCHEMA: raise ValueError('Unsupported boundary schema')
    if times.ndim != 1 or not 2 <= len(times) <= 1000 or not np.isfinite(times).all() or times[0] != 0 or np.any(np.diff(times) <= 0):
        raise ValueError('Boundary times must start at zero and strictly increase; 2..1000 frames')
    shape = meta['grid']['shape']
    if velocity.shape != (len(times), 3, shape[1], shape[2]) or not np.isfinite(velocity).all():
        raise ValueError('Invalid boundary velocity shape or values')
    if not allow_wall_zero and np.any(velocity[:, 0] <= 0):
        raise ValueError('Mapped inlet requires positive normal velocity; backflow is unsupported')
    quality = meta.get('quality', {})
    if quality.get('transfer_scope')=='experimental-neutral-nesting':raise ValueError('Neutral parent data requires v2 and an explicitly enabled neutral child')
    if quality.get('policy') != 'hawa-low-mach-v1' or not quality.get('transfer_eligible') or quality.get('status') != 'within-tested-envelope':
        raise ValueError('Source quality is unchecked or outside the transfer envelope')
    return times.astype(float), velocity.astype(np.float32), meta


def file_schema(path):
    from .boundary_series import SERIES_MAX_BYTES
    path=Path(path)
    if path.stat().st_size>SERIES_MAX_BYTES:raise ValueError('Boundary series exceeds 256 MiB budget')
    with zipfile.ZipFile(path) as z:
        if sum(v.file_size for v in z.infolist())>SERIES_MAX_BYTES:raise ValueError('Expanded boundary series exceeds 256 MiB')
        if z.getinfo('metadata.npy').file_size>16*1024**2:raise ValueError('Boundary metadata exceeds 16 MiB')
    with np.load(path,allow_pickle=False) as z:return json.loads(str(z['metadata'])).get('schema')


def attach(path, spec):
    from . import boundary_series
    if file_schema(path)==boundary_series.SCHEMA:return boundary_series.attach(path,spec)
    from .plugin import check_case
    sha = digest(path)
    times, velocity, meta = read(path, sha, allow_wall_zero=bool(spec.get("boundary_set")))
    if grid_key(spec) != meta['grid']: raise ValueError('Boundary dataset belongs to a different child grid')
    maximum = float(np.linalg.norm(velocity, axis=1).max()) * spec.get('mach', .05) / spec['speed']
    if maximum > .15: raise ValueError('Imported velocity exceeds child lattice Mach 0.15; revise physical scaling')
    import copy
    result = copy.deepcopy(spec)
    if result.get('boundary_set'):
        patches = result['boundary_set'].get('patches', [])
        inlet = next((p for p in patches if p.get('face')=='x-'), None)
        if inlet is None or inlet.get('condition', {}).get('type')!='velocity':
            raise ValueError('BoundarySeries v1 attaches only to a velocity X- patch')
        inlet['condition']['profile']='mapped'
    result['boundary_field'] = {'path': str(Path(path).resolve()), 'sha256': sha,
                                'end_time': float(times[-1]), 'grid': meta['grid']}
    check_case(result)
    return {'case': result, 'report': {'frames': len(times), 'duration_seconds': float(times[-1]),
            'max_imported_lattice_mach': maximum, 'source': meta['source'], 'quality': meta['quality']}}


def capture(manifest, spec, path, checkpoint=lambda n: None, start_time=0., end_time=None):
    if spec.get('neutral_precursor',{}).get('mode')=='external':
        from .boundary_series import capture as capture_v2
        return capture_v2(manifest,spec,path,checkpoint,start_time,end_time)
    if start_time!=0 or end_time is not None:raise ValueError('Time-window selection requires BoundarySeries v2 neutral external mode')
    from .recording import read_manifest
    from .fields import read_frame
    from .plugin import sample_arrays, check_case
    check_case(spec)
    root, source, _ = read_manifest(manifest)
    if not source.get('complete'): raise ValueError('Parent recording must be complete')
    entries = source['frames']
    n = spec['shape']
    if len(entries) < 2 or len(entries) * 3 * n[1] * n[2] * 4 > MAX_BYTES // 2:
        raise ValueError('Boundary capture requires 2..1000 frames within 32 MiB velocity budget')
    origin, basis, dx = geometry(spec)
    indices = np.array([(0, y, z) for y in range(n[1]) for z in range(n[2])])
    world = origin + indices @ basis * dx
    velocities, times = [], []
    source_hash = digest(root)
    hashes = []
    for i, entry in enumerate(entries):
        checkpoint(i)
        frame_path = root.parent / entry['file']
        arrays, meta = read_frame(frame_path)
        q = meta.get('quality', {})
        if q.get('transfer_scope')=='experimental-neutral-nesting':raise ValueError('Neutral parent requires an explicitly enabled neutral child and BoundarySeries v2')
        if not q.get('transfer_eligible') or q.get('policy') != 'hawa-low-mach-v1':
            raise ValueError('Parent recording quality does not permit transfer; re-record with diagnostics')
        parent = meta['case']
        if parent != source['case'] or not np.isclose(meta['time'], entry['time']):
            raise ValueError('Recording frame provenance does not match manifest')
        po, pb, pdx = geometry(parent)
        points = (world - po) @ pb.T / pdx
        points[np.abs(points) < 1e-10] = 0
        values = []
        for start in range(0, len(points), 1024):
            checkpoint(i)
            values.extend(sample_arrays(arrays, points[start:start+1024]))
        if any(v is None for v in values): raise ValueError('Child inlet has missing or solid parent coverage')
        velocity = np.array([v['velocity'] for v in values]) @ pb @ basis.T
        velocities.append(velocity.T.reshape(3, n[1], n[2]))
        times.append(float(meta['time']))
        hashes.append(digest(frame_path))
    if digest(root) != source_hash: raise ValueError('Parent recording changed during capture')
    times = np.asarray(times); offset = float(times[0]); times -= offset
    meta = {'schema': SCHEMA, 'grid': grid_key(spec), 'units': 'm/s; seconds; metres',
            'interpolation': 'trilinear space, linear time; no extrapolation',
            'boundary': 'X- equilibrium velocity, legacy Hawa formulation',
            'source': {'manifest_sha256': source_hash, 'frame_sha256': hashes, 'case': source['case'], 'time_offset_seconds': offset},
            'quality': q}
    checkpoint(len(entries))
    # Exclusive creation prevents overwriting another study. Remove partial writes on failure.
    path = Path(path)
    with path.open('xb') as f:
        try: np.savez_compressed(f, times=times, velocity=np.asarray(velocities, np.float32), metadata=np.array(json.dumps(meta)))
        except BaseException:
            f.close(); path.unlink(); raise
    try: return attach(path, spec)
    except BaseException:
        path.unlink(); raise


class FieldInlet(lt.EquilibriumBoundaryPU):
    """Existing equilibrium inlet generalized to a time-dependent vector plane."""
    def __init__(self, flow, mask):
        ref = flow.spec['boundary_field']
        times, velocity, meta = read(ref['path'], ref['sha256'], allow_wall_zero=bool(flow.spec.get('boundary_set')))
        if grid_key(flow.spec) != meta['grid']: raise ValueError('Boundary grid mismatch')
        maximum = np.linalg.norm(velocity, axis=1).max() * flow.spec.get('mach', .05) / flow.spec['speed']
        if maximum > .15: raise ValueError('Imported velocity exceeds child lattice Mach 0.15')
        self.times = times
        self.values = velocity
        self.cached = None
        super().__init__(flow.context, flow, mask, velocity[0][:, None])

    def __call__(self, flow):
        # Lettuce applies post boundaries before incrementing the completed step.
        t = float(flow.units.convert_time_to_pu(flow.i + 1))
        if t > self.times[-1] + 1e-10: raise ValueError('Boundary time coverage exhausted; capture a longer parent recording')
        i = min(int(np.searchsorted(self.times, t, side='right')) - 1, len(self.times)-2)
        i = max(0, i)
        if self.cached != i:
            self.a = flow.context.convert_to_tensor(self.values[i][:, None])
            self.b = flow.context.convert_to_tensor(self.values[i+1][:, None])
            self.cached = i
        w = (t-self.times[i])/(self.times[i+1]-self.times[i])
        self.velocity = self.a*(1-w)+self.b*w
        return super().__call__(flow)

    def native_available(self): return False
