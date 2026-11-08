"""Completed, repeatable single-phase objective evaluations for Grasshopper."""
from collections import deque
import math
import numpy as np
import torch
import lettuce as lt


class MeasuredBounceBack(lt.BounceBackBoundary):
    """Full-way bounce-back momentum exchange on obstacle/fluid links only.

    Called before streaming: incoming populations at a solid site arrived from
    its fluid neighbour during the previous stream. Reflection transfers 2*f*e.
    Internal solid links are excluded; domain faces are measured separately.
    """
    def __init__(self, flow, mask, window):
        super().__init__(mask)
        self.links = []
        self.history = deque(maxlen=window)
        for i, e in enumerate(flow.stencil.e):
            if not any(e):
                continue
            fluid_source = ~torch.roll(mask, tuple(int(v) for v in e), (0, 1, 2))
            self.links.append((i, e, mask & fluid_source))

    def __call__(self, flow):
        force = flow.context.zero_tensor([3])
        for i, e, mask in self.links:
            incoming = 2 * flow.f[i][mask].sum()
            for axis, value in enumerate(e):
                if value:
                    force[axis] += int(value) * incoming
        self.history.append(force.detach().clone())
        return super().__call__(flow)


def evaluate(session, steps, window, reference_volume):
    """Start from an unadvanced session and return one final averaged objective."""
    if type(steps) is not int or not 2 <= steps <= 10000:
        raise ValueError("Evaluation steps must be an integer from 2 to 10000")
    if type(window) is not int or not 1 <= window < steps:
        raise ValueError("Averaging window must be positive and smaller than steps")
    if not math.isfinite(reference_volume) or reference_volume <= 0:
        raise ValueError("Reference volume must be finite and positive")
    if session.flow.i != 0 or not hasattr(session.flow, 'solid'):
        raise ValueError("Evaluate a fresh physical case with a closed obstacle")
    mask = session.flow.solid
    if not bool(mask.any().cpu()):
        raise ValueError("The hull contains no solid lattice sites; refine the grid")
    # Padding prevents wrapped links and boundary-condition overlaps.
    for axis in range(3):
        for side in (0, -1):
            if bool(mask.select(axis, side).any().cpu()):
                raise ValueError("The hull touches a domain face; enlarge the domain")
    measured = MeasuredBounceBack(session.flow, mask, window)
    session.solver.post_boundaries[-1] = measured
    # Session.advance performs finite-density/population checks every batch.
    remaining = steps
    while remaining:
        n = min(10, remaining)
        session.advance(n)
        remaining -= n
    session.state = 'completed'
    session.target = steps
    units = session.flow.units
    dx = float(session.spec['dx'])
    dt = units.convert_time_to_pu(1)
    scale = units.characteristic_density_pu / units.characteristic_density_lu * dx**4 / dt**2
    forces = torch.stack(list(measured.history)).cpu().numpy().astype(float) * scale
    mean = forces.mean(axis=0)
    denominator = .5 * session.spec.get('density', 1.225) * session.spec['speed']**2 * reference_volume**(2/3)
    fitness = float(mean[0] / denominator)
    if not math.isfinite(fitness) or fitness <= 0:
        raise RuntimeError("Nonpositive or nonfinite resistance; revise the evaluation duration or case")
    return {'fitness': fitness, 'force_newtons': mean.tolist(),
            'force_std_newtons': forces.std(axis=0).tolist(), 'samples': len(forces),
            'steps': steps, 'window': window, 'reference_volume': reference_volume,
            'voxel_volume': int(mask.sum().cpu()) * dx**3,
            'metric': 'mean X momentum exchange / (0.5 rho U^2 V_ref^(2/3))',
            'limits': 'Fixed-duration, single-phase submerged-body demonstration. No free surface or wave resistance.'}
