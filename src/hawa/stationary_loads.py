"""CPU-only per-body full-way bounce-back loads; opt-in, no service wiring."""
import math
from collections import deque

import lettuce as lt
import numpy as np
import torch

from .measurements import Body, finite_vectors
from .motion import check


def validate_case(spec, body_indices, device='cpu'):
    """Validate supported ownership before allocating a solver/session."""
    if device != 'cpu':
        raise ValueError('Stationary measurements require explicit cpu')
    forbidden = ('example', 'wall_links', 'moving_bodies', 'boundary_set', 'neutral_precursor',
                 'boundary_field', 'refinement', 'refinement_patch', 'patch')
    if not isinstance(spec, dict) or any(key in spec for key in forbidden) or spec.get('collision') != 'bgk':
        raise ValueError('Only physical uniform BGK full-way stationary cases are supported')
    shape = spec.get('shape')
    if not isinstance(shape, list) or len(shape) != 3 or any(type(n) is not int or n < 4 for n in shape) or math.prod(shape) > 150000:
        raise ValueError('Measurement grid requires 3 dimensions and at most 150000 cells')
    for key in ('dx', 'speed', 'viscosity', 'density'):
        value = spec.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Measurement case requires positive finite ' + key)
    boundaries = spec.get('boundaries')
    if not isinstance(boundaries, list) or len(boundaries) != 6 or boundaries[:2] != ['inlet', 'outlet']:
        raise ValueError('Use legacy X inlet/outlet boundaries')
    for pair in (boundaries[2:4], boundaries[4:6]):
        if any(face not in ('wall', 'slip', 'periodic') for face in pair) or ('periodic' in pair and pair != ['periodic', 'periodic']):
            raise ValueError('Use paired periodic or wall/slip transverse boundaries')
    solid = spec.get('solid')
    count = math.prod(shape)
    if not isinstance(solid, list) or not solid or any(type(index) is not int or not 0 <= index < count for index in solid) or len(set(solid)) != len(solid):
        raise ValueError('Case solid indices must be unique, nonempty and inside the grid')
    if not isinstance(body_indices, dict) or not 1 <= len(body_indices) <= 4:
        raise ValueError('Provide 1..4 named body index sets')
    owner = np.zeros(shape, dtype=np.int8)
    for number, (body_id, indices) in enumerate(body_indices.items(), 1):
        if not isinstance(body_id, str) or not body_id or not isinstance(indices, list) or not indices or any(type(index) is not int or not 0 <= index < count for index in indices) or len(set(indices)) != len(indices):
            raise ValueError('Body IDs and solid index sets must be nonempty, unique and valid')
        coords = np.asarray(np.unravel_index(indices, shape)).T
        if np.any(coords == 0) or np.any(coords == np.asarray(shape)-1):
            raise ValueError('Bodies need one clear node layer at every domain face')
        flat = owner.reshape(-1)
        if np.any(flat[indices]):
            raise ValueError('Body solid sets overlap')
        flat[indices] = number
    if set(np.flatnonzero(owner)) != set(solid):
        raise ValueError('Body union must equal the case obstacle set')
    boundary_nodes = np.zeros(shape, dtype=bool)
    for face, kind in enumerate(boundaries):
        if kind in ('wall', 'slip'):
            plane = [slice(None)] * 3
            plane[face // 2] = -1 if face % 2 else 0
            boundary_nodes[tuple(plane)] = True
    for e in lt.D3Q19().e:
        if not any(e):
            continue
        offset = tuple(int(v) for v in e)
        if np.any((owner > 0) & np.roll(boundary_nodes, offset, (0, 1, 2))):
            raise ValueError('Bodies require fluid padding, not wall/slip boundary nodes')
        neighbour = np.roll(owner, offset, (0, 1, 2))
        if np.any((owner > 0) & (neighbour > 0) & (owner != neighbour)):
            raise ValueError('Differently named bodies touch along a D3Q19 link')
    return owner


def world_basis(origin_world_m, basis):
    """Validate the physical origin and orthonormal right-handed basis rows."""
    origin = finite_vectors([origin_world_m], 1)[0]
    basis = finite_vectors(basis, 3)
    if not np.allclose(basis @ basis.T, np.eye(3), rtol=0., atol=1e-10) or not np.isclose(np.linalg.det(basis), 1., rtol=0., atol=1e-10):
        raise ValueError('World basis must be orthonormal and right handed')
    return origin, basis


class StationaryLoads(lt.BounceBackBoundary):
    """Drop-in obstacle boundary preserving reflection; bounded raw load history.

    Call validate_case before constructing a Session, then construct this boundary
    with its flow and install it in place of the matching full-way obstacle
    boundary. No implicit install or global/session registration occurs here.
    Each history entry is tagged with source_step/source_time_s: the pre-stream
    state used by the reflection. A caller must not relabel it as a later field.
    """
    def __init__(self, flow, spec, body_indices, bodies, origin_world_m=(0., 0., 0.),
                 basis=((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)), capacity=100000):
        owner = validate_case(spec, body_indices, str(flow.context.device))
        if getattr(flow, 'spec', None) != spec:
            raise ValueError('Collector case must match actual flow specification')
        if flow.stencil.q != 19 or flow.stencil.d != 3 or tuple(flow.resolution) != tuple(spec['shape']):
            raise ValueError('Collector requires matching D3Q19 flow')
        if flow.f.dtype not in (torch.float32, torch.float64):
            raise ValueError('Collector supports CPU float32 or float64')
        if not isinstance(bodies, list) or not 1 <= len(bodies) <= 4:
            raise ValueError('Provide body moment references')
        parsed = [check(Body, body, 'Body') for body in bodies]
        if [body.body_id for body in parsed] != list(body_indices):
            raise ValueError('Body reference order must match ownership IDs')
        if type(capacity) is not int or not 1 <= capacity <= 100000:
            raise ValueError('History capacity must be 1..100000')
        origin, transform = world_basis(origin_world_m, basis)
        # CPU admission also binds allocations under an ambient device context.
        mask = torch.as_tensor(owner > 0, dtype=torch.bool, device='cpu')
        if not torch.equal(mask, flow.solid):
            raise ValueError('Flow solid mask differs from declared ownership')
        super().__init__(mask)
        self.flow = flow
        self.capacity = capacity
        self.history = deque()
        self.dtype = str(flow.f.dtype)
        self.dx = float(spec['dx'])
        self.dt = float(flow.units.convert_time_to_pu(1))
        rho_pu = float(flow.units.characteristic_density_pu)
        rho_lu = float(flow.units.characteristic_density_lu)
        actual_dx = float(flow.units.convert_length_to_pu(1))
        if not all(math.isfinite(v) and v > 0 for v in (self.dt, rho_pu, rho_lu, actual_dx)):
            raise ValueError('Force conversion scales must be positive finite')
        if not math.isclose(actual_dx, self.dx, rel_tol=1e-12) or not math.isclose(rho_pu, spec['density'], rel_tol=1e-12):
            raise ValueError('Flow units differ from declared physical case')
        try:
            self.scale = rho_pu / rho_lu * self.dx**4 / self.dt**2
        except (OverflowError, ZeroDivisionError) as error:
            raise ValueError('Force conversion overflow or underflow') from error
        if not math.isfinite(self.scale) or self.scale <= 0:
            raise ValueError('Force conversion scale must be positive finite')
        self.links = []
        for number, body in enumerate(parsed, 1):
            links = []
            for i, e in enumerate(flow.stencil.e):
                if not any(e):
                    continue
                e = np.asarray(e, dtype=int)
                fluid = np.roll(owner == 0, tuple(int(v) for v in e), (0, 1, 2))
                link_mask = (owner == number) & fluid
                coords = np.argwhere(link_mask)
                world_position = origin + (coords - .5 * e) * self.dx @ transform
                arm = torch.tensor(world_position - np.asarray(body.moment_origin_world_m), dtype=torch.float64, device='cpu')
                vector = torch.tensor(e @ transform, dtype=torch.float64, device='cpu')
                links.append((i, torch.tensor(link_mask, device='cpu'), arm, vector))
            self.links.append((body.body_id, links))

    def __call__(self, flow):
        if flow is not self.flow:
            raise ValueError('Collector belongs to a different flow')
        if len(self.history) >= self.capacity:
            raise ValueError('Measurement history capacity exhausted; no samples discarded')
        loads = []
        for body_id, links in self.links:
            force = torch.zeros(3, dtype=torch.float64, device='cpu')
            torque = torch.zeros(3, dtype=torch.float64, device='cpu')
            for direction, mask, arm, vector in links:
                # Multiply populations in solver precision, reduce in float64.
                transfer = (2 * flow.f[direction][mask]).to(torch.float64)[:, None] * vector
                force += transfer.sum(0)
                torque += torch.linalg.cross(arm, transfer, dim=-1).sum(0)
            force *= self.scale
            torque *= self.scale
            if not bool(torch.isfinite(force).all()) or not bool(torch.isfinite(torque).all()):
                raise ValueError('Nonfinite population-derived loads')
            loads.append(dict(body_id=body_id, force_world_n=force.tolist(), torque_world_nm=torque.tolist()))
        self.history.append(dict(source_step=int(flow.i), source_time_s=float(flow.i*self.dt),
                                 loads=loads, solver_dtype=self.dtype, reduction_dtype='float64',
                                 method='full-way momentum exchange; pre-stream source state'))
        return super().__call__(flow)

    def native_available(self):
        """Native bounce-back would bypass the Python load collector."""
        return False

    def native_generator(self, index):
        raise NotImplementedError('Stationary load collection requires portable CPU tensors')
