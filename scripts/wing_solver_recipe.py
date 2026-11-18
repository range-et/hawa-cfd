"""Example-only CPU voxel preparation for a real, bounded wing measurement sweep.

No solver is constructed here. This explicitly synthetic coarse workflow is not
an aerodynamic validation case. Final case hashes include each rotated solid set.
"""

import numpy as np

from hawa.plugin import case_key, check_case
from hawa.stationary_loads import validate_case
from scripts.wing_measurement_recipe import _hash, _number, wing_mesh


from hawa.mesh_voxel import _domain, voxelize_mesh


def prepare_sweep(wing_parameters, operating_points, domain, fluid):
    """Produce exact solver cases and references, without allocating sessions.

    The parent runner supplies case identity/generation, measurement windows,
    probes and step budget. Voxelization is recomputed from each rotated mesh.
    """
    allowed = {'root', 'tip', 'span_m', 'root_chord_m', 'tip_chord_m',
               'section_points', 'span_stations', 'pivot_m'}
    if not isinstance(wing_parameters, dict) or set(wing_parameters) - allowed:
        raise ValueError('unsupported wing recipe parameters')
    if not isinstance(operating_points, list) or not 1 <= len(operating_points) <= 64:
        raise ValueError('provide 1..64 ordered angle/speed points')
    shape, dx, origin = _domain(domain)
    if not isinstance(fluid, dict) or set(fluid) != {'density', 'viscosity', 'mach', 'pressure_pa'}:
        raise ValueError('fluid requires density, viscosity, mach and pressure_pa')
    density = _number(fluid['density'], 'density', True)
    viscosity = _number(fluid['viscosity'], 'viscosity', True)
    mach = _number(fluid['mach'], 'mach', True)
    pressure = _number(fluid['pressure_pa'], 'pressure_pa')
    candidates, prepared = [], {}
    for index, point in enumerate(operating_points):
        if not isinstance(point, dict) or set(point) != {'angle_deg', 'speed_m_s'}:
            raise ValueError('each operating point requires angle_deg and speed_m_s')
        alpha = _number(point['angle_deg'], 'angle_deg')
        speed = _number(point['speed_m_s'], 'speed_m_s', True)
        mesh = wing_mesh(**wing_parameters, angle_deg=alpha)
        geometry = dict(vertices_m=mesh['vertices_m'], triangles=mesh['triangles'])
        solid = voxelize_mesh(geometry, domain)
        basis = np.eye(3).tolist()
        spec = dict(shape=list(shape), dx=dx, spacing=dx, speed=speed,
                    viscosity=viscosity, density=density, mach=mach, collision='bgk',
                    boundaries=['inlet', 'outlet', 'slip', 'slip', 'slip', 'slip'],
                    solid=solid, origin=origin.tolist(), basis=basis)
        ownership = {'wing': solid.copy()}
        validate_case(spec, ownership, device='cpu')
        check_case(spec)
        candidate = dict(candidate_id='wing-{:03d}'.format(index), angle_deg=alpha,
                         speed_m_s=speed, geometry_hash=_hash(geometry), case_hash=case_key(spec))
        references = dict(density_kg_m3=density, speed_m_s=speed,
                          area_m2=mesh['reference_area_m2'], chord_m=mesh['reference_chord_m'],
                          pressure_pa=pressure, drag_axis_world=[1., 0., 0.], lift_axis_world=[0., 0., 1.])
        prepared[candidate['candidate_id']] = dict(candidate=candidate.copy(), case=spec,
                body_indices=ownership, bodies=[dict(body_id='wing', moment_origin_world_m=mesh['pivot_m'])],
                references=references, origin_world_m=origin.tolist(), basis=basis,
                geometry=geometry, geometry_hash=candidate['geometry_hash'])
        candidates.append(candidate)
    return dict(candidates=candidates, prepared=prepared, identity_scope='final solver case',
                claim='Coarse synthetic workflow only; no aerodynamic qualification')


def demo_sweep(refined=False):
    """Two CPU cases at fixed physical bounds; optional 10 mm rather than 25 mm grid."""
    if type(refined) is not bool:
        raise ValueError('refined must be a boolean')
    return prepare_sweep(
        dict(root='2418', tip='0018', span_m=.6, root_chord_m=.3, tip_chord_m=.2,
             section_points=41, span_stations=5),
        [dict(angle_deg=-3., speed_m_s=1.), dict(angle_deg=3., speed_m_s=1.)],
        dict(shape=[81, 101, 61] if refined else [33, 41, 25],
             dx=.01 if refined else .025, origin_world_m=[-.2, -.5, -.2]),
        dict(density=1., viscosity=.01, mach=.03, pressure_pa=0.))
