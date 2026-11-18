"""Example-only blended-wing geometry and sweep descriptors; never runs a solver.

Coordinates are metres, wind +X, span +Y, up +Z. This is a reproducible
headless counterpart of an ordinary Grasshopper loft/mesh recipe, not a Hawa node.
"""
import hashlib
import json
import math

import numpy as np

from hawa.airfoils import naca


def _number(value, name, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + ' must be a finite number')
    if positive and value <= 0:
        raise ValueError(name + ' must be positive')
    return float(value)


def _hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode('utf-8')).hexdigest()


def rotate_y(points, angle_deg, pivot_m):
    """Right-handed +Y rotation: a positive angle raises LE relative to TE."""
    angle = math.radians(_number(angle_deg, 'angle_deg'))
    if not isinstance(pivot_m, (list, tuple)) or len(pivot_m) != 3:
        raise ValueError('pivot_m requires three coordinates')
    pivot = np.array([_number(v, 'pivot_m') for v in pivot_m])
    if (not isinstance(points, (list, tuple)) or not points or
            any(not isinstance(row, (list, tuple)) or len(row) != 3 or
                any(type(v) not in (int, float) for v in row) for row in points)):
        raise ValueError('points require nonempty numeric triples without coercion')
    data = np.asarray(points, dtype=float)
    if data.ndim != 2 or data.shape[1] != 3 or not np.isfinite(data).all():
        raise ValueError('points require finite triples')
    c, s = math.cos(angle), math.sin(angle)
    matrix = np.array([[c, 0., s], [0., 1., 0.], [-s, 0., c]])
    result = (data - pivot) @ matrix.T + pivot
    if not np.isfinite(result).all():
        raise ValueError('rotated coordinates overflow')
    return result.tolist()


def wing_mesh(root='2412', tip='0012', span_m=1.2, root_chord_m=.3,
              tip_chord_m=.2, section_points=81, span_stations=9,
              angle_deg=0., pivot_m=None):
    """Loft cosine-index matched NACA sections with quarter-chord alignment.

    Returns a closed oriented triangular mesh with square tips, full-span ribs,
    unchanged reference area, transform provenance and a content geometry hash.
    Section TE duplicates are welded, not capped with zero-area triangles.
    """
    if not isinstance(root, str) or not isinstance(tip, str):
        raise ValueError('root and tip must be NACA strings')
    span = _number(span_m, 'span_m', True)
    cr = _number(root_chord_m, 'root_chord_m', True)
    ct = _number(tip_chord_m, 'tip_chord_m', True)
    if min(span, cr, ct) < 1e-6 or max(span, cr, ct) > 1e6:
        raise ValueError('recipe dimensions must be 1e-6..1e6 metres')
    if type(section_points) is not int or not 21 <= section_points <= 401 or section_points % 2 != 1:
        raise ValueError('section_points must be an odd integer from 21 to 401')
    if type(span_stations) is not int or not 3 <= span_stations <= 65 or span_stations % 2 != 1:
        raise ValueError('span_stations must be an odd integer from 3 to 65')
    alpha = _number(angle_deg, 'angle_deg')
    pivot = [.25 * cr, 0., 0.] if pivot_m is None else pivot_m
    root_xy = np.array(naca(root, section_points, closed=True)['coordinates'][:-1])
    tip_xy = np.array(naca(tip, section_points, closed=True)['coordinates'][:-1])
    root_xy[0] = tip_xy[0] = [1., 0.]
    ring = len(root_xy)
    vertices = []
    for y in np.linspace(-span / 2, span / 2, span_stations):
        fraction = abs(2 * y / span)
        chord = cr + (ct - cr) * fraction
        xy = ((1 - fraction) * root_xy + fraction * tip_xy) * chord
        vertices.extend([[float(x + .25 * (cr - chord)), float(y), float(z)] for x, z in xy])
    faces = []
    for station in range(span_stations - 1):
        for j in range(ring):
            a = station * ring + j
            b = station * ring + (j + 1) % ring
            faces.extend([[a, a + ring, b + ring], [a, b + ring, b]])
    # Chordwise cap strips join corresponding upper/lower cosine stations.
    # TE and LE are single vertices; skip only the resulting duplicate triples.
    for station in (0, span_stations - 1):
        for j in range(ring // 2):
            u, un = j, j + 1
            l, ln = (-j) % ring, (-(j + 1)) % ring
            for triangle in ([u, un, ln], [u, ln, l]):
                if len(set(triangle)) == 3:
                    face = [station * ring + i for i in triangle]
                    faces.append(face if station == 0 else face[::-1])
    rotated = rotate_y(vertices, alpha, pivot)
    mesh = {'vertices_m': rotated, 'triangles': faces}
    xyz = np.array(rotated)
    tri = xyz[np.asarray(faces)]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    if not np.isfinite(cross).all() or np.any(np.linalg.norm(cross, axis=1) == 0):
        raise ValueError('recipe has degenerate faces or nonfinite dimensions')
    # Volume relative to a local point avoids translation cancellation.
    shifted = tri - xyz[0]
    volume = float(np.einsum('ij,ij->i', shifted[:, 0], np.cross(shifted[:, 1], shifted[:, 2])).sum() / 6)
    if not math.isfinite(volume) or volume <= 0:
        raise ValueError('recipe must enclose positive oriented volume')
    area = span * (cr + ct) / 2
    return dict(schema='hawa-wing-recipe-1', **mesh, geometry_hash=_hash(mesh),
                root_airfoil=root, tip_airfoil=tip, span_m=span,
                root_chord_m=cr, tip_chord_m=ct, reference_area_m2=area,
                reference_chord_m=2 * (cr * cr + cr * ct + ct * ct) / (3 * (cr + ct)),
                angle_deg=alpha, pivot_m=list(pivot), volume_m3=volume,
                section_points=section_points, span_stations=span_stations,
                sections_m=np.array(rotated).reshape(span_stations, ring, 3).tolist(),
                claim='Geometry recipe only; no CFD or aerodynamic qualification')


def sweep_recipe(wing_parameters, operating_points, case_settings):
    """Return explicit ordered angle/speed candidates and their actual meshes.

    case_hash covers the recipe/operating condition and caller case settings;
    the future solver adapter must replace it with the final voxelized case hash.
    It is intentionally labelled as preflight identity, never solver evidence.
    """
    allowed = {'root', 'tip', 'span_m', 'root_chord_m', 'tip_chord_m',
               'section_points', 'span_stations', 'pivot_m'}
    if not isinstance(wing_parameters, dict) or set(wing_parameters) - allowed:
        raise ValueError('wing_parameters contains unsupported keys')
    if not isinstance(operating_points, list) or not 1 <= len(operating_points) <= 64:
        raise ValueError('provide 1..64 ordered operating points')
    if not isinstance(case_settings, dict) or not case_settings:
        raise ValueError('case_settings must be a nonempty dictionary')
    # Freeze a JSON copy; nonserializable or nonfinite configuration is rejected.
    settings = json.loads(json.dumps(case_settings, allow_nan=False))
    candidates, geometry = [], {}
    for number, point in enumerate(operating_points):
        if not isinstance(point, dict) or set(point) != {'angle_deg', 'speed_m_s'}:
            raise ValueError('each point requires angle_deg and speed_m_s only')
        alpha = _number(point['angle_deg'], 'angle_deg')
        speed = _number(point['speed_m_s'], 'speed_m_s', True)
        mesh = wing_mesh(**wing_parameters, angle_deg=alpha)
        ident = 'wing-{:03d}'.format(number)
        candidate = dict(candidate_id=ident, angle_deg=alpha, speed_m_s=speed,
                         geometry_hash=mesh['geometry_hash'],
                         case_hash=_hash(dict(geometry_hash=mesh['geometry_hash'],
                                              speed_m_s=speed, case=settings)))
        candidates.append(candidate)
        geometry[ident] = mesh
    return dict(schema='hawa-wing-sweep-recipe-1', candidates=candidates, geometry=geometry,
                case_settings=settings, identity_scope='preflight; replace case_hash after solver voxelization',
                run=False, references=dict(area_m2=mesh['reference_area_m2'],
                                           chord_m=mesh['reference_chord_m']))
