"""Asynchronous, CPU-only stationary mesh studies using the measured sweep contract.

Geometry is supplied by the host in world metres. No wing construction lives here.
Only the worker voxelizes, constructs sessions and captures immutable field frames.
"""
from copy import deepcopy
import math
import time

import numpy as np

from .jobs import Job, Cancelled
from .mesh_voxel import _domain, _number, voxelize_mesh
from .measurements import Probe, validate_request
from .plugin import case_key, check_case
from .sweep_executor import CpuSweepExecutor, _geometry_hash
from .sweeps import SweepController, plot_segments

_KEYS = {'kind', 'device', 'case', 'geometry', 'operating_points', 'references',
         'pivot_world_m', 'probes', 'settling_steps', 'sample_steps',
         'stationarity_tolerance', 'case_id', 'generation'}


def validate_submission(request):
    """Bound input collections before admission; no voxelization or solver allocation."""
    if not isinstance(request, dict) or set(request) != _KEYS:
        raise ValueError('Stationary study fields do not match the contract')
    if request['kind'] != 'stationary_study' or request['device'] != 'cpu':
        raise ValueError('Stationary studies require explicit CPU')
    case = request['case']
    if not isinstance(case, dict) or case.get('solid', []) != []:
        raise ValueError('Stationary study requires an empty-solid base case')
    allowed = {'shape', 'dx', 'spacing', 'speed', 'viscosity', 'density', 'mach',
               'collision', 'boundaries', 'solid', 'origin', 'basis', 'initial_velocity',
               'memory_limit_mb', 'reference_pressure'}
    if set(case) - allowed or case.get('collision', 'bgk') != 'bgk':
        raise ValueError('Stationary study supports physical uniform BGK cases only')
    for key in ('dx', 'speed', 'viscosity', 'density'):
        _number(case.get(key), key, True)
    _domain(dict(shape=case.get('shape'), dx=case.get('dx'), origin_world_m=case.get('origin', [0., 0., 0.])))
    if case.get('basis', np.eye(3).tolist()) != np.eye(3).tolist():
        raise ValueError('Stationary study requires a world-axis-aligned domain')
    if _number(case.get('spacing', case['dx']), 'spacing', True) != case['dx']:
        raise ValueError('Stationary study case spacing must equal dx in world metres')
    geometry = request['geometry']
    _geometry_hash(geometry)
    if len(geometry['vertices_m']) > 26000 or len(geometry['triangles']) > 52000:
        raise ValueError('Stationary voxelization mesh budget exceeded')
    points = request['operating_points']
    if not isinstance(points, list) or not 1 <= len(points) <= 64:
        raise ValueError('Provide 1..64 ordered angle/speed points')
    for point in points:
        if not isinstance(point, dict) or set(point) != {'angle_deg', 'speed_m_s'}:
            raise ValueError('Operating point requires angle_deg and speed_m_s')
        _number(point['angle_deg'], 'angle_deg')
        _number(point['speed_m_s'], 'speed_m_s', True)
    refs = request['references']
    if not isinstance(refs, dict) or set(refs) != {'area_m2', 'chord_m', 'pressure_pa'}:
        raise ValueError('References require area_m2, chord_m and pressure_pa')
    for key in refs:
        _number(refs[key], key, key != 'pressure_pa')
    pivot = request['pivot_world_m']
    if not isinstance(pivot, list) or len(pivot) != 3:
        raise ValueError('Pivot requires three world metre coordinates')
    for value in pivot:
        _number(value, 'pivot_world_m')
    settling, samples = request['settling_steps'], request['sample_steps']
    if (type(settling) is not int or settling < 0 or type(samples) is not int or
            samples < 4 or settling + samples > 100000):
        raise ValueError('Require nonnegative settling, >=4 samples and <=100000 steps')
    tolerance = _number(request['stationarity_tolerance'], 'stationarity_tolerance')
    if tolerance < 0:
        raise ValueError('Stationarity tolerance must be nonnegative')
    if not isinstance(request['case_id'], str) or not request['case_id'].strip():
        raise ValueError('Case identity must be nonempty')
    if type(request['generation']) is not int or request['generation'] < 0:
        raise ValueError('Generation must be a nonnegative integer')
    probes = request['probes']
    if not isinstance(probes, list) or len(probes) > 256:
        raise ValueError('Provide at most 256 fluid probes')
    for probe in probes:
        model = Probe.model_validate(probe)
        if model.body_id is not None:
            raise ValueError('Stationary studies currently accept world-fixed fluid probes only')
    if len({p['probe_id'] for p in probes}) != len(probes):
        raise ValueError('Probe IDs must be unique')
    count = len(points)
    if (count * math.prod(case['shape']) > 1500000 or
            count * (settling + samples) * (1 + len(probes)) > 100000 or
            count * len(geometry['vertices_m']) > 200000 or count * len(geometry['triangles']) > 400000):
        raise ValueError('Stationary study exceeds aggregate retained-row/grid/mesh budget')
    check_case(case)


def prepare(request, checkpoint):
    """Prepare exact rotated, voxelized and hashed candidates on the job worker."""
    entries = {}
    base = request['case']
    domain = dict(shape=base['shape'], dx=base['dx'], origin_world_m=base.get('origin', [0., 0., 0.]))
    pivot = np.asarray(request['pivot_world_m'])
    vertices = np.asarray(request['geometry']['vertices_m'])
    for index, point in enumerate(request['operating_points']):
        checkpoint(0)
        a = math.radians(point['angle_deg'])
        c, s = math.cos(a), math.sin(a)
        rotation = np.array([[c, 0., s], [0., 1., 0.], [-s, 0., c]])
        geometry = dict(vertices_m=((vertices-pivot) @ rotation.T+pivot).tolist(),
                        triangles=deepcopy(request['geometry']['triangles']))
        solid = voxelize_mesh(geometry, domain, checkpoint)
        spec = deepcopy(base)
        spec.update(solid=solid, speed=float(point['speed_m_s']), collision='bgk')
        candidate = dict(candidate_id='study-{:03d}'.format(index), angle_deg=float(point['angle_deg']),
                         speed_m_s=float(point['speed_m_s']), geometry_hash=_geometry_hash(geometry), case_hash=case_key(spec))
        identity = dict(case_id=request['case_id'], candidate_id=candidate['candidate_id'],
                        revision=0, generation=request['generation'],
                        case_hash=candidate['case_hash'], geometry_hash=candidate['geometry_hash'])
        refs = dict(request['references'], density_kg_m3=spec['density'], speed_m_s=spec['speed'],
                    drag_axis_world=[1., 0., 0.], lift_axis_world=[0., 0., 1.])
        dt = spec.get('mach', .05)*spec['dx']/(math.sqrt(3)*spec['speed'])
        measurement = dict(schema='hawa-measurement-1', identity=identity, references=refs,
                           bodies=[dict(body_id='body', moment_origin_world_m=request['pivot_world_m'])],
                           window=dict(start_s=request['settling_steps']*dt,
                                       end_s=(request['settling_steps']+request['sample_steps']-1)*dt,
                                       minimum_samples=request['sample_steps'],
                                       stationarity_absolute_coefficient_tolerance=request['stationarity_tolerance']))
        validate_request(measurement)
        entries[candidate['candidate_id']] = dict(candidate=candidate, spec=spec,
            body_indices={'body': solid}, request=measurement, probes=deepcopy(request['probes']),
            origin_world_m=domain['origin_world_m'], basis=np.eye(3).tolist(),
            steps=request['settling_steps']+request['sample_steps'], selected_body_id='body',
            dtype='float32', geometry=geometry)
    return entries


def retain_frame(detail, entry):
    """Register an immutable existing-format frame with the actual capture identity."""
    from .fields import store
    fields = detail.pop('last_field')
    if fields is None:
        return None
    stamp = fields.pop('snapshot')
    meta = dict(iteration=stamp['steps'], time=stamp['physical_time'],
                case=dict(entry['spec'], physical_dx=entry['spec']['dx'],
                          reference_pressure=entry['request']['references']['pressure_pa']),
                mean=False, samples=0, quality=detail['quality'], phase=detail['phase'],
                identity=detail['identity'], session=detail['session'], snapshot=stamp)
    return store(fields, meta)


class StationaryStudyJob(Job):
    """Own sweep workers and view frames until close; snapshots never run physics."""
    def __init__(self, request):
        super().__init__(request)
        self.target = len(request['operating_points'])
        self.details = {}
        self.frames = set()
        self.progress = None
        self.cleanup = None

    def _release_frames(self):
        from .fields import FRAMES, LOCK
        with LOCK:
            for key in self.frames:
                FRAMES.pop(key, None)
        self.frames.clear()
        self.details.clear()

    def work(self):
        controller = executor = None
        try:
            self.checkpoint(0, 'preparing')
            entries = prepare(self.request, self.checkpoint)
            self.checkpoint(0)
            executor = CpuSweepExecutor(entries)
            controller = SweepController([entry['candidate'] for entry in entries.values()], executor,
                                         generation=self.request['generation'])
            controller.run()
            while controller.state not in ('completed', 'cancelled', 'disposed'):
                with self.condition:
                    if self.cancelled:
                        controller.cancel()
                    elif self.paused:
                        controller.pause()
                    else:
                        controller.resume()
                    controller.tick()
                    records = controller.records
                    for record in records:
                        record['CM'] = None
                    self.steps = sum(r['state'] in ('completed', 'failed', 'rejected', 'cancelled') for r in records)
                    paused = self.paused and all(r['state'] != 'running' for r in records)
                    self.state = 'cancelling' if self.cancelled else ('paused' if paused else 'pausing' if self.paused else 'running')
                    self.progress = dict(records=records, plots={name: plot_segments(records, name)
                                         for name in ('cl_alpha', 'cd_alpha', 'cl_cd')})
                time.sleep(.01)  # This is a dedicated worker, never the GH solution thread.
            self.checkpoint(self.steps)
            for key, entry in entries.items():
                self.checkpoint(self.steps)
                detail = executor.results(key, self.request['generation'])
                if detail is not None:
                    frame = retain_frame(detail, entry)
                    with self.condition:
                        if frame is not None:
                            self.frames.add(frame['frame'])
                        detail.update(frame=frame, geometry=entry['geometry'])
                        self.details[key] = detail
                        record = next(r for r in self.progress['records'] if r['candidate']['candidate_id'] == key)
                        if record['state'] == 'completed':
                            record['CM'] = detail['summary']['bodies'][0]['mean']['Cm']
            with self.condition:
                if self.cancelled:
                    raise Cancelled('Stationary study cancelled')
                self.result = self.progress
                self.state = 'completed'
        except Cancelled:
            with self.condition:
                self.state = 'cancelled'
        except Exception as exc:
            with self.condition:
                self.error, self.state = str(exc), 'failed'
        finally:
            if controller is not None:
                controller.dispose()
                while controller.state == 'draining':
                    controller.tick()
                    time.sleep(.01)
            with self.condition:
                self.cleanup = None if executor is None else executor.audit()
                if self.state != 'completed' or self.disposed:
                    self._release_frames()
                    self.result = None

    def snapshot(self, selected_candidate=None):
        with self.condition:
            value = super().snapshot()
            value['progress'] = deepcopy(self.progress)
            value['cleanup'] = deepcopy(self.cleanup)
            if selected_candidate is not None:
                if type(selected_candidate) is not int or not 0 <= selected_candidate < self.target:
                    raise ValueError('Selected candidate index outside study')
                if self.state == 'completed' and self.result is not None:
                    value['result']['selected'] = deepcopy(self.details.get('study-{:03d}'.format(selected_candidate)))
            return value

    def control(self, action):
        with self.condition:
            super().control(action)
            if action == 'close':
                self._release_frames()
