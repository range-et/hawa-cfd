"""Strict SI measurement analysis, independent of solver/export/host ownership."""
import json
import numbers
from typing import Annotated, List, Literal, Optional

import numpy as np
from pydantic import ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from .motion import Payload, Vector, Positive, NonNegative, check

SCHEMA = 'hawa-measurement-1'
Identifier = Annotated[StrictStr, Field(min_length=1)]
Count = Annotated[StrictInt, Field(ge=0)]


def unit_vector(value):
    """Reject scaling mistakes instead of normalising user axes silently."""
    value = finite_vectors([value], 1)[0]
    if not np.isclose(np.linalg.norm(value), 1., rtol=0., atol=1e-10):
        raise ValueError('Axis must be a unit vector')
    return np.asarray(value, dtype=float)


class MeasurementPayload(Payload):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, revalidate_instances='always')


class Identity(MeasurementPayload):
    case_id: Identifier
    candidate_id: Identifier
    case_hash: Identifier
    geometry_hash: Identifier
    revision: Count
    generation: Count


class References(MeasurementPayload):
    density_kg_m3: Positive
    speed_m_s: Positive
    area_m2: Positive
    chord_m: Positive
    pressure_pa: StrictFloat
    drag_axis_world: Vector
    lift_axis_world: Vector

    @model_validator(mode='after')
    def axes(self):
        drag = unit_vector(self.drag_axis_world)
        lift = unit_vector(self.lift_axis_world)
        if abs(float(drag @ lift)) > 1e-10:
            raise ValueError('Drag and lift axes must be perpendicular')
        q = .5 * self.density_kg_m3 * self.speed_m_s * self.speed_m_s
        products = np.asarray([q, q * self.area_m2, q * self.area_m2 * self.chord_m])
        if not np.isfinite(products).all() or np.any(products <= 0):
            raise ValueError('Reference products must be finite and nonzero')
        return self


class Body(MeasurementPayload):
    body_id: Identifier
    moment_origin_world_m: Vector


class Window(MeasurementPayload):
    start_s: NonNegative
    end_s: Positive
    minimum_samples: Annotated[StrictInt, Field(ge=4, le=100000)]
    stationarity_absolute_coefficient_tolerance: NonNegative

    @model_validator(mode='after')
    def ordered(self):
        if self.end_s <= self.start_s:
            raise ValueError('Window end must be after start')
        return self


class Request(MeasurementPayload):
    schema_: Literal['hawa-measurement-1'] = Field(alias='schema')
    identity: Identity
    references: References
    bodies: Annotated[List[Body], Field(min_length=1, max_length=4)]
    window: Window
    load_axis_world: Optional[Vector] = None

    @model_validator(mode='after')
    def unique_bodies(self):
        ids = [body.body_id for body in self.bodies]
        if len(set(ids)) != len(ids):
            raise ValueError('Body IDs must be unique')
        if self.load_axis_world is not None:
            unit_vector(self.load_axis_world)
        return self


class Sample(MeasurementPayload):
    schema_: Literal['hawa-measurement-1'] = Field(alias='schema')
    identity: Identity
    body_id: Identifier
    step: Count
    time_s: NonNegative
    force_world_n: Optional[Vector]
    torque_world_nm: Optional[Vector]
    valid: StrictBool
    reason: StrictStr
    quality: Literal['accepted', 'warning', 'rejected']

    @model_validator(mode='after')
    def validity(self):
        if self.valid:
            if self.force_world_n is None or self.torque_world_nm is None or self.reason:
                raise ValueError('Valid samples require vectors and an empty reason')
        elif self.force_world_n is not None or self.torque_world_nm is not None or not self.reason:
            raise ValueError('Invalid samples require null vectors and a reason')
        return self


class Probe(MeasurementPayload):
    probe_id: Identifier
    position_world_m: Vector
    body_id: Optional[Identifier] = None
    surface_point_world_m: Optional[Vector] = None
    outward_normal_world: Optional[Vector] = None
    offset_m: Optional[Positive] = None

    @model_validator(mode='after')
    def attachment(self):
        attached = [self.body_id, self.surface_point_world_m, self.outward_normal_world, self.offset_m]
        if any(value is not None for value in attached):
            if any(value is None for value in attached):
                raise ValueError('A surface tap requires body, surface point, normal and offset')
            normal = unit_vector(self.outward_normal_world)
            expected = np.asarray(self.surface_point_world_m) + self.offset_m * normal
            if not np.allclose(self.position_world_m, expected, rtol=0., atol=1e-10):
                raise ValueError('Tap position must match its explicit offset')
        return self


def validate_request(request):
    """Validate without mutating an existing case or caller payload."""
    if isinstance(request, Request):
        request = request.model_dump(by_alias=True)
    return check(Request, request, 'Measurement')


def finite_vectors(values, count):
    """Strict numeric vectors for direct helpers as well as schema entry points."""
    raw = np.asarray(values, dtype=object)
    if raw.shape != (count, 3) or any(isinstance(v, (bool, np.bool_)) or not isinstance(v, numbers.Real) for v in raw.flat):
        raise ValueError('Require finite numeric vectors without coercion')
    array = np.asarray(raw, dtype=float)
    if not np.isfinite(array).all():
        raise ValueError('Require finite numeric vectors')
    return array


def finite_result(value):
    """Reject arithmetic overflow before returning any result to consumers."""
    return json.loads(json.dumps(value, allow_nan=False))


def translate_moment(force, moment, old_origin, new_origin):
    """Translate a fluid-on-body moment between SI world reference points."""
    values = finite_vectors([force, moment, old_origin, new_origin], 4)
    return finite_result((values[1] + np.cross(values[2] - values[3], values[0])).tolist())


def coefficients(request, force, moment):
    """Return signed wind-axis loads and coefficients; no absolute-value repair."""
    request = validate_request(request)
    values = finite_vectors([force, moment], 2)
    ref = request.references
    drag, lift = np.asarray(ref.drag_axis_world), np.asarray(ref.lift_axis_world)
    side = np.cross(lift, drag)
    q = .5 * ref.density_kg_m3 * ref.speed_m_s ** 2
    d, y, l = np.asarray([drag, side, lift]) @ values[0]
    load_axis = drag if request.load_axis_world is None else np.asarray(request.load_axis_world)
    return finite_result(dict(q_pa=q, D=float(d), Y=float(y), L=float(l), CD=float(d/(q*ref.area_m2)),
                CY=float(y/(q*ref.area_m2)), CL=float(l/(q*ref.area_m2)),
                Cm=float(values[1] @ side/(q*ref.area_m2*ref.chord_m)),
                load_cell_n=float(values[0] @ load_axis)))


def summarize(request, samples):
    """Reduce complete, uniformly timed windows without dropping invalid data."""
    req = validate_request(request)
    if not isinstance(samples, list) or not samples or len(samples) > 100000 * len(req.bodies):
        raise ValueError('A bounded nonempty sample list is required')
    parsed = [check(Sample, sample, 'Sample') for sample in samples]
    ids = [body.body_id for body in req.bodies]
    if any(sample.identity != req.identity or sample.body_id not in ids for sample in parsed):
        raise ValueError('Sample identity/body does not match the request')
    results = []
    for body in req.bodies:
        history = [sample for sample in parsed if sample.body_id == body.body_id]
        if len(history) > 100000:
            raise ValueError('Body history exceeds 100000 samples')
        times = np.asarray([sample.time_s for sample in history])
        steps = np.asarray([sample.step for sample in history])
        if np.any(np.diff(times) <= 0) or np.any(np.diff(steps) <= 0):
            raise ValueError('Body samples must strictly increase in step and time')
        window = req.window
        selected = [sample for sample in history if
                    (sample.time_s >= window.start_s or np.isclose(sample.time_s, window.start_s, rtol=1e-9, atol=1e-12)) and
                    (sample.time_s <= window.end_s or np.isclose(sample.time_s, window.end_s, rtol=1e-9, atol=1e-12))]
        if len(selected) < window.minimum_samples:
            raise ValueError('Insufficient measurement samples')
        times = np.asarray([sample.time_s for sample in selected])
        if not np.allclose(times[[0, -1]], [window.start_s, window.end_s], rtol=1e-9, atol=1e-12):
            raise ValueError('Measurement window endpoints are not covered')
        if not np.allclose(np.diff(times), np.diff(times)[0], rtol=1e-9, atol=1e-12):
            raise ValueError('Measurement samples require uniform time spacing')
        if any(not sample.valid or sample.quality == 'rejected' for sample in selected):
            raise ValueError('Invalid or rejected samples cannot produce usable coefficients')
        forces = np.asarray([sample.force_world_n for sample in selected])
        moments = np.asarray([sample.torque_world_nm for sample in selected])
        rows = [coefficients(req, f, m) for f, m in zip(forces, moments)]
        coeffs = np.asarray([[row['CD'], row['CY'], row['CL']] for row in rows])
        split = len(selected) // 2
        drift = float(np.max(np.abs(coeffs[:split].mean(0) - coeffs[split:].mean(0))))
        stable = drift <= window.stationarity_absolute_coefficient_tolerance
        result = dict(body_id=body.body_id, count=len(selected), duration_s=float(times[-1]-times[0]),
                      mean=coefficients(req, forces.mean(0), moments.mean(0)),
                      force_mean_world_n=forces.mean(0).tolist(), force_std_world_n=forces.std(0).tolist(),
                      torque_mean_world_nm=moments.mean(0).tolist(), torque_std_world_nm=moments.std(0).tolist(),
                      coefficient_std={key:float(np.std([row[key] for row in rows])) for key in ('CD','CY','CL','Cm')},
                      stationarity=dict(passed=stable, absolute_coefficient_change=drift,
                                        tolerance=window.stationarity_absolute_coefficient_tolerance),
                      usable=stable and all(sample.quality == 'accepted' for sample in selected), quality='warning' if any(sample.quality == 'warning' for sample in selected) else 'accepted')
        results.append(result)
    return finite_result(dict(schema=SCHEMA, identity=req.identity.model_dump(), references=req.references.model_dump(),
                window=req.window.model_dump(), bodies=results,
                usable=all(result['usable'] for result in results), statistic='equal-weight population standard deviation; not confidence bounds'))


def sample_probes(request, probes, time_s, sampler):
    """Call a point sampler returning pressure Pa or None; preserve invalid points."""
    req = validate_request(request)
    if type(time_s) not in (int, float) or not np.isfinite(time_s) or time_s < 0:
        raise ValueError('Probe time must be finite nonnegative seconds')
    if not isinstance(probes, list) or not 1 <= len(probes) <= 256:
        raise ValueError('Provide 1..256 probes')
    parsed = [check(Probe, probe, 'Probe') for probe in probes]
    if len(set(probe.probe_id for probe in parsed)) != len(parsed):
        raise ValueError('Probe IDs must be unique')
    ids = {body.body_id for body in req.bodies}
    if any(probe.body_id is not None and probe.body_id not in ids for probe in parsed):
        raise ValueError('Unknown probe body')
    q = .5 * req.references.density_kg_m3 * req.references.speed_m_s ** 2
    results = []
    for probe in parsed:
        pressure = sampler(list(probe.position_world_m))
        if pressure is not None and (type(pressure) not in (int, float) or not np.isfinite(pressure)):
            raise ValueError('Sampler must return finite pressure Pa or None')
        results.append(dict(schema=SCHEMA, identity=req.identity.model_dump(), time_s=float(time_s),
                            **probe.model_dump(), valid=pressure is not None,
                            reason='' if pressure is not None else 'sample invalid or outside fluid',
                            pressure_pa=pressure, Cp=None if pressure is None else (pressure-req.references.pressure_pa)/q,
                            approximate_surface=probe.body_id is not None))
    return finite_result(results)
