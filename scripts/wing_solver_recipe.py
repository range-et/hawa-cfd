"""Example-only CPU voxel preparation for a real, bounded wing measurement sweep.

No solver is constructed here. This explicitly synthetic coarse workflow is not
an aerodynamic validation case. Final case hashes include each rotated solid set.
"""
import math
from collections import Counter

import numpy as np

from hawa.plugin import case_key, check_case
from hawa.measurements import finite_vectors
from hawa.stationary_loads import validate_case
from scripts.wing_measurement_recipe import _hash, _number, wing_mesh


def _domain(domain):
    if not isinstance(domain, dict) or set(domain) != {'shape', 'dx', 'origin_world_m'}:
        raise ValueError('domain requires shape, dx and origin_world_m only')
    shape = domain['shape']
    if (not isinstance(shape, list) or len(shape) != 3 or
            any(type(n) is not int or n < 4 for n in shape) or math.prod(shape) > 150000):
        raise ValueError('domain requires three dimensions with 4..150000 total cells')
    dx = _number(domain['dx'], 'dx', True)
    origin = domain['origin_world_m']
    if not isinstance(origin, list) or len(origin) != 3:
        raise ValueError('origin_world_m requires three coordinates')
    origin = np.array([_number(v, 'origin_world_m') for v in origin])
    upper = origin + (np.array(shape) - 1) * dx
    if not np.isfinite(upper).all() or np.any(upper <= origin):
        raise ValueError('domain extents overflow or collapse')
    return shape, dx, origin


def voxelize_mesh(geometry, domain):
    """Classify nodes against the closed triangular recipe using signed X rays.

    Surface ties are inside. Shared-edge ray crossings are deduplicated; opposing
    tangent crossings cancel. This bounded example classifier is not a CAD API.
    """
    shape, dx, origin = _domain(domain)
    if not isinstance(geometry, dict) or set(geometry) != {'vertices_m', 'triangles'}:
        raise ValueError('geometry requires vertices_m and triangles')
    vertices = finite_vectors(geometry['vertices_m'], len(geometry['vertices_m']))
    faces = np.asarray(geometry['triangles'])
    if (vertices.ndim != 2 or vertices.shape[1] != 3 or not 4 <= len(vertices) <= 26000 or
            not np.isfinite(vertices).all() or faces.ndim != 2 or faces.shape[1] != 3 or
            not 4 <= len(faces) <= 52000 or faces.dtype.kind not in 'iu' or
            np.any(faces < 0) or np.any(faces >= len(vertices))):
        raise ValueError('finite bounded vertices and integer triangle indices required')
    edges = Counter((int(face[i]), int(face[(i + 1) % 3])) for face in faces for i in range(3))
    if any(count != 1 or edges[(b, a)] != 1 for (a, b), count in edges.items()):
        raise ValueError('mesh must be a closed consistently oriented manifold')
    triangles = vertices[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    shifted = triangles - vertices[0]
    volume = np.einsum('ij,ij->i', shifted[:, 0], np.cross(shifted[:, 1], shifted[:, 2])).sum() / 6
    if (not np.isfinite(normals).all() or np.any(np.linalg.norm(normals, axis=1) == 0) or
            not math.isfinite(float(volume)) or volume <= 0):
        raise ValueError('mesh requires nondegenerate triangles and positive volume')
    upper = origin + (np.array(shape) - 1) * dx
    if np.any(vertices.min(0) < origin + 2 * dx) or np.any(vertices.max(0) > upper - 2 * dx):
        raise ValueError('wing requires two clear lattice spacings at every domain face')
    # Work only on rays intersecting the mesh's YZ bounds; no tensor/GPU path.
    ys = origin[1] + np.arange(shape[1]) * dx
    zs = origin[2] + np.arange(shape[2]) * dx
    eps = dx * 1e-8
    pairs = [(j, k) for j in range(shape[1]) for k in range(shape[2])
             if vertices[:, 1].min() - eps <= ys[j] <= vertices[:, 1].max() + eps
             and vertices[:, 2].min() - eps <= zs[k] <= vertices[:, 2].max() + eps]
    if not pairs:
        raise ValueError('wing is unresolved on this grid')
    rays = np.array([[ys[j], zs[k]] for j, k in pairs])
    intersections = [[] for _ in pairs]
    for face in faces:
        triangle = vertices[face]
        a, b, c = triangle[:, 1:]
        v, w = b - a, c - a
        determinant = v[0] * w[1] - v[1] * w[0]
        if abs(determinant) <= dx * dx * 1e-14:
            continue  # A face parallel to the X ray contributes no crossing.
        offset = rays - a
        u = (offset[:, 0] * w[1] - offset[:, 1] * w[0]) / determinant
        t = (v[0] * offset[:, 1] - v[1] * offset[:, 0]) / determinant
        selected = np.flatnonzero((u >= -1e-10) & (t >= -1e-10) & (u + t <= 1 + 1e-10))
        for ray in selected:
            x = triangle[0, 0] + u[ray] * (triangle[1, 0] - triangle[0, 0]) + t[ray] * (triangle[2, 0] - triangle[0, 0])
            intersections[ray].append((float(x), 1 if determinant > 0 else -1))
    mask = np.zeros(shape, dtype=bool)
    xs = origin[0] + np.arange(shape[0]) * dx
    for (j, k), crossings in zip(pairs, intersections):
        groups = []
        for x, sign in sorted(crossings):
            if groups and abs(x - groups[-1][0]) <= eps:
                groups[-1][1] += sign
            else:
                groups.append([x, sign])
        winding = 0
        last = None
        for x, sign in groups:
            if winding:
                mask[:, j, k] |= (xs >= last - eps) & (xs <= x + eps)
            mask[:, j, k] |= np.abs(xs - x) <= eps
            winding -= int(np.sign(sign))
            last = x
        if winding:
            raise ValueError('mesh ray did not close; repair geometry before voxelization')
    solid = np.flatnonzero(mask).tolist()
    if not solid:
        raise ValueError('wing is unresolved on this grid')
    return solid


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


def demo_sweep():
    """Two modest CPU cases at explicit synthetic viscosity; no execution here."""
    return prepare_sweep(
        dict(root='2418', tip='0018', span_m=.6, root_chord_m=.3, tip_chord_m=.2,
             section_points=41, span_stations=5),
        [dict(angle_deg=-3., speed_m_s=1.), dict(angle_deg=3., speed_m_s=1.)],
        dict(shape=[33, 41, 25], dx=.025, origin_world_m=[-.2, -.5, -.2]),
        dict(density=1., viscosity=.01, mach=.03, pressure_pa=0.))
