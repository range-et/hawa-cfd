"""Bounded closed triangular mesh classification for stationary CPU cases."""
import math
from collections import Counter
import numpy as np
from .measurements import finite_vectors
from .stationary_loads import MAX_GRID_CELLS


def _number(value, name, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + ' must be a finite number')
    if positive and value <= 0:
        raise ValueError(name + ' must be positive')
    return float(value)


def _domain(domain):
    if not isinstance(domain, dict) or set(domain) != {'shape', 'dx', 'origin_world_m'}:
        raise ValueError('domain requires shape, dx and origin_world_m only')
    shape = domain['shape']
    if (not isinstance(shape, list) or len(shape) != 3 or
            any(type(n) is not int or n < 4 for n in shape) or math.prod(shape) > MAX_GRID_CELLS):
        raise ValueError('domain requires three dimensions and at most {} cells'.format(MAX_GRID_CELLS))
    dx = _number(domain['dx'], 'dx', True)
    origin = domain['origin_world_m']
    if not isinstance(origin, list) or len(origin) != 3:
        raise ValueError('origin_world_m requires three coordinates')
    origin = np.array([_number(v, 'origin_world_m') for v in origin])
    upper = origin + (np.array(shape) - 1) * dx
    if not np.isfinite(upper).all() or np.any(upper <= origin):
        raise ValueError('domain extents overflow or collapse')
    return shape, dx, origin


def voxelize_mesh(geometry, domain, checkpoint=None):
    """Classify nodes against the closed triangular recipe using signed X rays.

    Surface ties are inside. Shared-edge ray crossings are deduplicated; opposing
    tangent crossings cancel. This bounded classifier is not a CAD repair or boolean API.
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
        raise ValueError('mesh requires two clear lattice spacings at every domain face')
    # Work only on rays intersecting the mesh's YZ bounds; no tensor/GPU path.
    ys = origin[1] + np.arange(shape[1]) * dx
    zs = origin[2] + np.arange(shape[2]) * dx
    eps = dx * 1e-8
    pairs = [(j, k) for j in range(shape[1]) for k in range(shape[2])
             if vertices[:, 1].min() - eps <= ys[j] <= vertices[:, 1].max() + eps
             and vertices[:, 2].min() - eps <= zs[k] <= vertices[:, 2].max() + eps]
    if not pairs:
        raise ValueError('mesh is unresolved on this grid')
    rays = np.array([[ys[j], zs[k]] for j, k in pairs])
    intersections = [[] for _ in pairs]
    for face in faces:
        if checkpoint is not None:
            checkpoint(0)
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
        raise ValueError('mesh is unresolved on this grid')
    return solid

