"""Opt-in CPU sweep execution with explicit worker and result ownership.

No dispatcher, exports, Rhino adapters, global sessions, or accelerator selection.
Only float32 is supported because the unchanged Session constructor uses it.
"""
from copy import deepcopy
import hashlib
import json
import math
import threading
import uuid

import numpy as np
import lettuce as lt

from .boundary_data import geometry as domain_geometry
from .measurements import Probe, SCHEMA, sample_probes, summarize, validate_request
from .plugin import Session, case_key, check_case, sample_arrays
from .quality import assess
from .stationary_loads import StationaryLoads, validate_case, world_basis
from .sweeps import validate_candidates

PHASE = 'after-collision-before-obstacle-reflection-and-stream'
_KEYS = {'candidate', 'spec', 'body_indices', 'request', 'probes', 'origin_world_m',
         'basis', 'steps', 'selected_body_id', 'dtype', 'geometry'}


def _geometry_hash(geometry):
    if not isinstance(geometry, dict) or set(geometry) != {'vertices_m', 'triangles'}:
        raise ValueError('Geometry requires vertices_m and triangles')
    vertices, faces = geometry['vertices_m'], geometry['triangles']
    if (not isinstance(vertices, list) or not 4 <= len(vertices) <= 200000 or
            not isinstance(faces, list) or not 4 <= len(faces) <= 400000):
        raise ValueError('Geometry must contain a bounded nonempty triangle mesh')
    if any(not isinstance(v, list) or len(v) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) for x in v) for v in vertices):
        raise ValueError('Geometry vertices must be finite numeric triples')
    if any(not isinstance(f, list) or len(f) != 3 or any(type(i) is not int or not 0 <= i < len(vertices) for i in f) or len(set(f)) != 3 for f in faces):
        raise ValueError('Geometry triangles require three distinct valid integer indices')
    payload = json.dumps(geometry, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _prepare(entry):
    """Validate/detach all expensive inputs before any worker is started."""
    if not isinstance(entry, dict) or set(entry) != _KEYS:
        raise ValueError('Prepared candidate fields do not match the executor contract')
    value = deepcopy(entry)
    candidate = validate_candidates([value['candidate']])[0]
    spec = value['spec']
    if value['dtype'] != 'float32':
        raise ValueError('CPU Session sweeps currently support dtype=float32 only')
    validate_case(spec, value['body_indices'], 'cpu')
    check_case(spec)
    req = validate_request(value['request'])
    origin, basis = world_basis(value['origin_world_m'], value['basis'])
    case_origin, case_basis, _ = domain_geometry(spec)
    if not np.allclose(origin, case_origin, rtol=0., atol=1e-10) or not np.allclose(basis, case_basis, rtol=0., atol=1e-10):
        raise ValueError('Measurement frame must match the case physical origin and basis')
    if (case_key(spec) != candidate['case_hash'] or _geometry_hash(value['geometry']) != candidate['geometry_hash'] or
            any(getattr(req.identity, key) != candidate[key] for key in ('candidate_id', 'case_hash', 'geometry_hash'))):
        raise ValueError('Prepared geometry/case/measurement identity mismatch')
    if candidate['speed_m_s'] != spec['speed'] or req.references.speed_m_s != spec['speed'] or req.references.density_kg_m3 != spec['density']:
        raise ValueError('Coefficient reference speed/density must match the physical case')
    if not np.allclose(req.references.drag_axis_world, basis[0], rtol=0., atol=1e-10):
        raise ValueError('Drag axis must follow the actual +X inlet direction')
    if [body.body_id for body in req.bodies] != list(value['body_indices']) or value['selected_body_id'] not in value['body_indices']:
        raise ValueError('Measurement body ownership/selection mismatch')
    steps = value['steps']
    if type(steps) is not int or not 4 <= steps <= 100000:
        raise ValueError('Sweep steps must be an integer from 4 to 100000')
    probes = value['probes']
    if not isinstance(probes, list) or len(probes) > 256 or steps * len(probes) > 100000:
        raise ValueError('Probe capture exceeds the bounded 100000-row budget')
    for probe in probes:
        Probe.model_validate(probe)
    if probes:
        # Validate uniqueness and body attachment without evaluating source fields.
        sample_probes(req, probes, 0., lambda point: None)
    dt = spec.get('mach', .05) * spec['dx'] / (math.sqrt(3) * spec['speed'])
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError('Candidate physical timestep must be finite and positive')
    endpoints = [req.window.start_s / dt, req.window.end_s / dt]
    if (not np.isfinite(endpoints).all() or any(not math.isclose(x, round(x), rel_tol=1e-9, abs_tol=1e-12) for x in endpoints) or
            endpoints[1] > steps-1+1e-9 or round(endpoints[1])-round(endpoints[0])+1 < req.window.minimum_samples):
        raise ValueError('Measurement window must cover enough exact source steps within the run')
    value['origin_world_m'], value['basis'] = origin.tolist(), basis.tolist()
    return value


def _budget(prepared):
    """Bound all retained data before duplicating any mesh or case payload."""
    rows = cells = vertices = faces = 0
    for entry in prepared.values():
        if not isinstance(entry, dict) or set(entry) != _KEYS:
            raise ValueError('Prepared candidate fields do not match the executor contract')
        spec, geometry = entry['spec'], entry['geometry']
        if not isinstance(spec, dict) or not isinstance(geometry, dict):
            raise ValueError('Case and geometry must be dictionaries')
        shape = spec.get('shape')
        if not isinstance(shape, list) or len(shape) != 3 or any(type(n) is not int or n < 4 for n in shape):
            raise ValueError('Case shape must contain three integer dimensions')
        if (type(entry['steps']) is not int or not 4 <= entry['steps'] <= 100000 or
                not isinstance(entry['body_indices'], dict) or not isinstance(entry['probes'], list) or
                not isinstance(geometry.get('vertices_m'), list) or not isinstance(geometry.get('triangles'), list)):
            raise ValueError('Prepared candidate counts must be bounded collections')
        rows += entry['steps'] * (len(entry['body_indices']) + len(entry['probes']))
        cells += math.prod(shape)
        vertices += len(geometry['vertices_m'])
        faces += len(geometry['triangles'])
        if rows > 100000 or cells > 1500000 or vertices > 200000 or faces > 400000:
            raise ValueError('Sweep exceeds aggregate retained-row/grid/mesh budget')


class _Run:
    def __init__(self, entry, generation):
        self.entry = entry
        self.generation = generation
        self.condition = threading.Condition()
        self.paused = False
        self.cancelled = False
        self.state = 'queued'
        self.reason = ''
        self.result = None
        self.session = None
        self.thread = None
        self.details = None

    def checkpoint(self):
        """Only the background worker waits; control methods merely signal."""
        with self.condition:
            while self.paused and not self.cancelled:
                self.state = 'paused'
                self.condition.wait()
            if self.cancelled:
                return False
            self.state = 'running'
            return True


class _Capture(StationaryLoads):
    def __init__(self, session, entry):
        super().__init__(session.flow, entry['spec'], entry['body_indices'], entry['request']['bodies'],
                         entry['origin_world_m'], entry['basis'], capacity=entry['steps'])
        self.session = session
        self.entry = entry
        self.load_samples = []
        self.probe_samples = []
        self.last_field = None
        self.last_quality = None

    def __call__(self, flow):
        # These observations share exactly the population phase used by loads.
        self.session.quality = assess(self.session)
        quality = deepcopy(self.session.quality)
        fields = self.session.fields(with_provenance=True)
        field_stamp = fields['snapshot']
        field_stamp['phase'] = PHASE
        result = super().__call__(flow)
        capture = self.history[-1]
        if field_stamp['steps'] != capture['source_step'] or not math.isclose(field_stamp['physical_time'], capture['source_time_s'], rel_tol=1e-12, abs_tol=1e-12):
            raise RuntimeError('Pressure/load capture phase identity mismatch')
        status = {'within-tested-envelope': 'accepted', 'warning': 'warning', 'rejected': 'rejected'}[quality['status']]
        for load in capture['loads']:
            self.load_samples.append(dict(schema=SCHEMA, identity=deepcopy(self.entry['request']['identity']),
                                          **load, step=capture['source_step'], time_s=capture['source_time_s'],
                                          valid=True, reason='', quality=status))
        origin = np.asarray(self.entry['origin_world_m'])
        basis = np.asarray(self.entry['basis'])
        def pressure(point):
            lattice = ((np.asarray(point)-origin) @ basis.T / self.dx).tolist()
            value = sample_arrays(fields, [lattice])[0]
            return None if value is None else float(value['pressure'])
        if self.entry['probes']:
            probes = sample_probes(self.entry['request'], self.entry['probes'], capture['source_time_s'], pressure)
            for probe in probes:
                probe.update(step=capture['source_step'], session=self.session.id, phase=PHASE,
                             quality=status, source_quality=deepcopy(quality))
            self.probe_samples.extend(probes)
        self.last_field = fields
        self.last_quality = quality
        return result


class CpuSweepExecutor:
    """One fresh private Session per candidate; methods never join a live worker.

    Construct outside a UI callback: prepared-data admission is synchronous.
    start/poll/control/close return promptly; all allocation/solving is on workers.
    Detailed detached results survive close through results(candidate_id,generation).
    """
    def __init__(self, prepared):
        if not isinstance(prepared, dict) or not 1 <= len(prepared) <= 64:
            raise ValueError('Executor requires 1..64 prepared candidates')
        _budget(prepared)
        self._prepared = {key: _prepare(value) for key, value in prepared.items()}
        if any(key != value['candidate']['candidate_id'] for key, value in self._prepared.items()):
            raise ValueError('Prepared mapping keys must match candidate IDs')
        self._lock = threading.RLock()
        self._handles = {}
        self._closed = set()
        self._seen = set()
        self._results = {}

    def _run(self, handle):
        with self._lock:
            if handle not in self._handles:
                raise ValueError('Unknown or closed executor handle')
            return self._handles[handle]

    def start(self, candidate, generation):
        validate_candidates([candidate])
        if type(generation) is not int or generation < 0:
            raise ValueError('Generation must be a nonnegative integer')
        with self._lock:
            entry = self._prepared.get(candidate['candidate_id'])
            if entry is None or entry['candidate'] != candidate or entry['request']['identity']['generation'] != generation:
                raise ValueError('Candidate/generation does not match prepared inputs')
            key = (candidate['candidate_id'], generation)
            if key in self._seen or self._handles:
                raise ValueError('Close the current handle; each prepared generation runs only once')
            handle = uuid.uuid4().hex
            run = _Run(entry, generation)
            run.thread = threading.Thread(target=self._work, args=(run,), name='Hawa CPU sweep '+handle[:8], daemon=True)
            self._handles[handle] = run
            try:
                run.thread.start()
            except Exception:
                del self._handles[handle]
                raise
            self._seen.add(key)
            return handle

    def _work(self, run):
        session = capture = None
        entry = run.entry
        detail = dict(candidate=deepcopy(entry['candidate']), identity=deepcopy(entry['request']['identity']),
                      dtype='float32', device='cpu', phase=PHASE, load_samples=[], probe_samples=[],
                      summary=None, last_field=None, quality=None, session=None)
        try:
            if not run.checkpoint():
                return
            session = Session(entry['spec'], 'cpu')
            with run.condition:
                run.session = session
            detail['session'] = session.id
            capture = _Capture(session, entry)
            # The preflight admits only full-way stationary obstacles; match the
            # actual mask instead of assuming a fragile boundary-list position.
            matches = [i for i, boundary in enumerate(session.solver.post_boundaries)
                       if isinstance(boundary, lt.BounceBackBoundary) and
                       np.array_equal(boundary.make_no_collision_mask(session.flow.resolution, session.flow.context).cpu().numpy(),
                                      session.flow.solid.cpu().numpy())]
            if len(matches) != 1:
                raise ValueError('Expected exactly one matching full-way obstacle boundary')
            session.solver.post_boundaries[matches[0]] = capture
            for _ in range(entry['steps']):
                if not run.checkpoint():
                    break
                session.advance(1)
            with run.condition:
                cancelled = run.cancelled
            if not cancelled:
                try:
                    summary = summarize(entry['request'], capture.load_samples)
                except ValueError as exc:
                    with run.condition:
                        run.state, run.reason = 'rejected', str(exc)
                else:
                    detail['summary'] = summary
                    selected = next(body for body in summary['bodies'] if body['body_id'] == entry['selected_body_id'])
                    quality = selected['quality']
                    if session.quality['status'] in ('warning', 'rejected'):
                        quality = session.quality['status']
                    with run.condition:
                        run.result = dict(identity=deepcopy(entry['request']['identity']), quality=quality,
                                          window_valid=True, stationarity_passed=selected['stationarity']['passed'],
                                          coefficients={key:selected['mean'][key] for key in ('CL','CD')})
                        run.state = 'completed'
        except Exception as exc:
            with run.condition:
                run.state, run.reason = 'failed', str(exc)
        finally:
            if capture is not None:
                detail.update(load_samples=capture.load_samples, probe_samples=capture.probe_samples,
                              last_field=capture.last_field, quality=capture.last_quality)
                capture.session = None  # Break session -> boundary -> session ownership.
            with run.condition:
                if run.cancelled:
                    run.state, run.reason, run.result = 'cancelled', 'Sweep cancelled', None
                detail.update(provenance=dict(session=detail['session'], phase=PHASE, identity=deepcopy(entry['request']['identity'])),
                              state=run.state, reason=run.reason,
                              final_quality=None if session is None else deepcopy(session.quality))
                run.details = detail
                run.session = None
            with self._lock:
                self._results[(entry['candidate']['candidate_id'], run.generation)] = detail

    def poll(self, handle):
        run = self._run(handle)
        with run.condition:
            return dict(state=run.state, candidate_id=run.entry['candidate']['candidate_id'],
                        generation=run.generation, reason=run.reason, result=deepcopy(run.result))

    def pause(self, handle):
        run = self._run(handle)
        with run.condition:
            run.paused = True

    def resume(self, handle):
        run = self._run(handle)
        with run.condition:
            run.paused = False
            run.condition.notify_all()

    def cancel(self, handle):
        run = self._run(handle)
        with run.condition:
            run.cancelled = True
            run.condition.notify_all()

    def close(self, handle):
        with self._lock:
            if handle in self._closed:
                return True
            run = self._run(handle)
            if run.thread.is_alive():
                with run.condition:
                    # A completed worker may still be publishing retained results.
                    if run.state not in ('completed','failed','rejected','cancelled'):
                        run.cancelled = True
                        run.condition.notify_all()
                return False
            del self._handles[handle]
            self._closed.add(handle)
            return True

    def results(self, candidate_id, generation):
        with self._lock:
            key = (candidate_id, generation)
            return deepcopy(self._results.get(key))

    def audit(self):
        with self._lock:
            sessions = []
            for run in self._handles.values():
                with run.condition:
                    if run.session is not None:
                        sessions.append(run.session.id)
            return dict(handles=len(self._handles), live_workers=sum(run.thread.is_alive() for run in self._handles.values()),
                        session_ids=sessions)
