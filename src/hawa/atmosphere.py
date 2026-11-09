"""SI neutral surface-layer relations and numerical feasibility diagnostics.

These relations are preparation/verification utilities, not an atmospheric solver.
The shifted log law uses height above the aerodynamic ground, no displacement,
and the same roughness convention for inflow and stress. It does not model waves,
stratification, or separated-wall non-equilibrium effects.
"""
import math
import numpy as np


def _positive(value, name):
    if isinstance(value, (bool, str)):
        raise ValueError(name + ' must be a finite positive number')
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(name + ' must be a finite positive number') from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name + ' must be a finite positive number')
    return value


def _log_height_ratio(height, roughness):
    # log(1+h/z0) without overflowing h/z0; h=0 has the exact limit zero.
    with np.errstate(divide='ignore'):
        return np.logaddexp(0., np.log(height)-math.log(roughness))


def neutral_profile(height_m, reference_velocity, reference_height_m,
                    roughness_length_m, normal=(0., 0., 1.)):
    """Return vectors (..., 3) from the shifted neutral logarithmic mean law.

    U(h)=Uref log(1+h/z0)/log(1+href/z0). Heights are distances, not world Z.
    The reference vector must be tangential to a unit surface normal. Ground is
    exactly zero. Negative heights are errors; clipping could hide a bad map.
    """
    z0 = _positive(roughness_length_m, 'roughness length')
    href = _positive(reference_height_m, 'reference height')
    if href <= z0:
        raise ValueError('Reference height must be above the roughness length')
    h = np.asarray(height_m, dtype=float)
    velocity = np.asarray(reference_velocity, dtype=float)
    n = _normal(normal)
    if not np.isfinite(h).all() or np.any(h < 0):
        raise ValueError('Profile heights must be finite and nonnegative')
    if velocity.shape != (3,) or not np.isfinite(velocity).all():
        raise ValueError('Reference velocity must contain three finite components')
    if abs(velocity @ n) > 1e-10 * max(1., np.linalg.norm(velocity)):
        raise ValueError('Reference velocity must be tangential to the surface')
    with np.errstate(over='ignore', invalid='ignore'):
        result = _log_height_ratio(h, z0)[..., None] / _log_height_ratio(href, z0) * velocity
    if not np.isfinite(result).all():
        raise ValueError('Profile parameters exceed numerical range')
    return result


def _normal(value):
    n = np.asarray(value, dtype=float)
    if n.shape != (3,) or not np.isfinite(n).all() or not np.isclose(np.linalg.norm(n), 1., rtol=0, atol=1e-10):
        raise ValueError('Surface normal must be a finite unit vector')
    return n


def neutral_wall_traction(velocity_m_s, sample_height_m, roughness_length_m,
                          density_kg_m3=1.225, normal=(0., 0., 1.), kappa=.41):
    """Equilibrium rough-wall traction ON THE FLUID, in Pa, and u* in m/s.

    A constitutive relation only: a solver must impose the returned stress through
    a verified momentum-conserving wall operator. The normal velocity is projected
    out, not made impermeable here. Samples must lie above z0. This is a basic
    input constraint, not proof that a sample is inside an equilibrium log layer.
    """
    z0 = _positive(roughness_length_m, 'roughness length')
    h = _positive(sample_height_m, 'sample height')
    rho = _positive(density_kg_m3, 'density')
    k = _positive(kappa, 'von Karman constant')
    if h <= z0:
        raise ValueError('Wall sample must be above the roughness length')
    u = np.asarray(velocity_m_s, dtype=float)
    n = _normal(normal)
    if u.ndim < 1 or u.shape[-1] != 3 or not np.isfinite(u).all():
        raise ValueError('Wall velocity must have finite trailing vector components')
    tangent = u - np.sum(u*n, axis=-1)[..., None]*n
    speed = np.linalg.norm(tangent, axis=-1)
    factor = k / _log_height_ratio(h, z0)
    # This form is continuous at rest and does not divide by speed.
    with np.errstate(over='ignore', invalid='ignore'):
        traction = -rho*factor**2*speed[..., None]*tangent
    if not np.isfinite(traction).all() or not np.isfinite(factor*speed).all():
        raise ValueError('Wall parameters exceed numerical range')
    return {'traction_on_fluid_pa': traction, 'friction_velocity_m_s': factor*speed}


def scaling_report(dx, speed, viscosity, mach=.05):
    """Inspect physical relaxation and its FP32 representation without allocating.

    The existing production limit remains unchanged. SGS can vanish at rest or
    in weak strain, so it cannot be used to waive the molecular relaxation check.
    """
    dx, speed, viscosity, mach = [_positive(v, n) for v, n in zip(
        (dx, speed, viscosity, mach), ('cell width', 'speed', 'viscosity', 'Mach'))]
    try:
        dt = mach*dx/(math.sqrt(3)*speed)
        margin = 3*viscosity*dt/dx**2
    except (OverflowError, ZeroDivisionError):
        raise ValueError('Scaling parameters exceed numerical range') from None
    if not math.isfinite(dt) or not math.isfinite(margin) or dt <= 0 or margin <= 0:
        raise ValueError('Scaling parameters exceed numerical range')
    tau = .5 + margin
    if tau > np.finfo(np.float32).max:
        raise ValueError('Relaxation exceeds FP32 numerical range')
    tau32 = float(np.float32(tau))
    represented = tau32-.5
    return {'time_step_seconds': dt, 'tau': tau, 'tau_minus_half': margin,
            'tau_fp32': tau32, 'tau_minus_half_fp32': represented,
            'relative_margin_rounding_error': abs(represented-margin)/margin,
            'fp32_rounds_to_half': tau32 == .5,
            'production_supported': tau > .500001 and mach <= .15,
            'policy': 'hawa-fp32-relaxation-v1',
            'qualification': 'scaling only; no turbulence or wall-model validation'}
