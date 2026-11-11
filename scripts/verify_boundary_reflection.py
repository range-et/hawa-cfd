"""HAWA-004 open-boundary reflection, corner, reversal and cut-face measurements.

Criteria are fixed in docs/boundary-reflection-review.md and repeated in
CRITERIA. Every case compares a small domain with an enlarged reference (or an
analytic plug flow for reversal) at equal step counts. CPU64 is primary; FP32
rows also run on --device (MPS) for declared-backend qualification.
These are verification measurements, not validation.
"""
import argparse
import json
import math
import time
from pathlib import Path
from unittest import mock
import numpy as np
import torch
import lettuce as lt
from hawa import plugin
from hawa.boundary_contracts import FACES
from hawa.boundaries import METHOD as NEE
from hawa.neutral import MODEL
from hawa.neutral_external import METHOD as EXTERNAL

SPEED = 5.
SOUND = 1/math.sqrt(3)
CRITERIA = dict(acoustic=.10, vortex=.10, uniform_m_s=3e-5, mass_lu=1e-10, reversal_mean=.02,
                reversal_node=.05, cut_interior_l2=.02, cut_interior_linf=.05, cut_band_l2=.05,
                cut_band_linf=.10, settled=.01)


def lattice_speed(value):
    """Physical m/s to lattice units at the harness Mach 0.05 and 5 m/s scale."""
    return value*.05/(math.sqrt(3)*SPEED)


def build(spec, dtype=torch.float64, device='cpu'):
    """Production make_solver with the lattice dtype selected for measurement."""
    context = lt.Context
    with mock.patch.object(plugin.lt, 'Context', lambda name, _, use_native: context(name, dtype, use_native=use_native)):
        _, flow, solver = plugin.make_solver(spec, device)
    if hasattr(solver, 'rough_floor'):
        solver.rough_floor.factor = 0.  # specular floor; isolates the open faces
    return flow, solver


def spec_for(system, shape, faces, dx=1., viscosity=None, cs=.17, block=None):
    """Case for system 'S' (shifted external) or 'N' (general NEE)."""
    spec = dict(shape=[int(n) for n in shape], dx=dx, speed=SPEED, density=1.225, mach=.05,
                boundary_set=dict(schema=1, patches=[dict(id=f, face=f, condition=c) for f, c in zip(FACES, faces)]))
    if system == 'S':
        spec.update(viscosity=1.5e-5 if viscosity is None else viscosity, collision=MODEL, boundary_method=EXTERNAL,
                    neutral_precursor=dict(schema=1, experimental=True, mode='external', perturbation_fraction=0.,
                                           reference_height_m=shape[2]*dx/2, roughness_length_m=.01*dx,
                                           smagorinsky_constant=cs))
    elif system == 'N':
        # tau-1/2 = 0.01 unless a physical viscosity is given.
        dt = .05*dx/(math.sqrt(3)*SPEED)
        spec.update(viscosity=.01*dx*dx/(3*dt) if viscosity is None else viscosity, collision='regularized',
                    boundary_method=NEE, initial_velocity=[0., 0., 0.])
    else:
        raise ValueError('System must be S or N')
    if block is not None:
        halo = block(np.indices(tuple(np.array(shape)+2))-1)
        spec['solid'] = np.flatnonzero(halo[1:-1, 1:-1, 1:-1]).tolist()
        if system == 'S':
            spec['solid_halo'] = np.flatnonzero(halo).tolist()
    return spec


def faces_x(system, inflow, outflow=None):
    """X- velocity, X+ open; Y periodic; Z specular floor/slip (S) or periodic (N)."""
    z = [dict(type='wall'), dict(type='slip')] if system == 'S' else [dict(type='periodic')]*2
    return [dict(type='velocity', velocity=list(inflow)), outflow or dict(type='open', velocity=[0., 0., 0.]),
            dict(type='periodic'), dict(type='periodic')] + z


def set_state(flow, delta, u):
    """Equilibrium populations for density deviation delta and lattice velocity u."""
    delta = flow.context.convert_to_tensor(delta)[None]
    u = flow.context.convert_to_tensor(u)*(~flow.solid)[None]
    if 'Shifted' in type(flow.equilibrium).__name__:
        flow.f = flow.equilibrium(flow, u=u, delta=delta)
        flow.f[:, flow.solid] = 0
    else:
        flow.f = flow.equilibrium(flow, 1+delta, u)


def state(flow):
    """Density deviation and lattice velocity, zero inside solids."""
    shifted = 'Shifted' in type(flow.equilibrium).__name__
    delta = flow.f.sum(0) if shifted else flow.rho()[0]-1
    fluid = (~flow.solid).to(flow.f.dtype)
    return (delta*fluid).cpu().numpy(), (flow.u()*fluid[None]).cpu().numpy()


def finite(runs, *metrics):
    """Every population and every metric sample is finite; Python max() skips NaN."""
    return all(bool(torch.isfinite(run[0].f).all()) for run in runs) and all(map(math.isfinite, metrics))


def incoming_links(solver):
    """Incoming open-face count of the last step, for either boundary system."""
    links = getattr(solver, 'external_links', None)
    if links is not None:
        return int(links.report['incoming_open_links'])
    return int(solver.general_boundary.report['open_incoming_nodes'])


def acoustic_setup(scale=1, side='outlet'):
    """Pulse geometry, window and reference extension (offset when upstream)."""
    n, sigma = int(64*scale), 4.*scale
    U = lattice_speed(SPEED); x0 = n/2
    if side == 'outlet':
        steps = (n-x0)/(SOUND+U)+(n-4)/(SOUND-U)
        offset, returned = 0, (3*n-x0)/(SOUND+U)+2*n/(SOUND-U)
    elif side == 'inlet':
        steps = x0/(SOUND-U)+(n-4)/(SOUND+U)
        offset, returned = 2*n, (x0+2*n)/(SOUND-U)+2*n/(SOUND+U)
    else:
        raise ValueError('Side must be outlet or inlet')
    return dict(n=n, sigma=sigma, amplitude=1e-3, centre=x0, steps=int(math.ceil(steps)), reference_length=3*n,
                offset=offset, reference_return_steps=returned, direction=1 if side == 'outlet' else -1)


def acoustic(system, scale=1, dtype=torch.float64, side='outlet', steps=None, device='cpu'):
    """Planar Gaussian pulse into the open X+ face ('outlet') or velocity X- face."""
    g = acoustic_setup(scale, side)
    n, sigma, eps = g['n'], g['sigma'], g['amplitude']
    end = g['steps'] if steps is None else steps
    if g['reference_return_steps'] <= end+3*sigma/(SOUND-lattice_speed(SPEED)):
        raise ValueError('Reference too short for causal separation')
    runs = []
    for length, shift in ((n, 0), (g['reference_length'], g['offset'])):
        flow, solver = build(spec_for(system, (length, 4, 4), faces_x(system, (SPEED, 0., 0.))), dtype, device)
        profile = eps*np.exp(-.5*((np.arange(length)-shift-g['centre'])/sigma)**2)
        delta = np.broadcast_to(profile[:, None, None], flow.resolution).copy()
        u = np.zeros((3, *flow.resolution)); u[0] = lattice_speed(SPEED)+g['direction']*SOUND*delta
        set_state(flow, delta, u)
        runs.append((flow, solver, shift))
    history = []
    for step in range(0, end+1, 10):
        if step:
            for flow, solver, _ in runs:
                solver(10)
        a, b = (state(flow)[0][shift:shift+n] for flow, _, shift in runs)
        history.append(float(np.max(np.abs(a-b))/eps))
    ok, limit = finite(runs, *history), CRITERIA['acoustic'] if side == 'outlet' else None
    return dict(case='A1' if side == 'outlet' else 'A2', system=system, dtype=str(dtype), scale=scale,
                steps=end//10*10, requested_steps=end,
                reflection=max(history), history_max_every_10=history, finite=ok, criterion=limit,
                passed=None if limit is None else bool(ok and max(history) <= limit))


def taylor(shape, center, radius, peak):
    """Velocity (u, v) and incompressible pressure/rho of a Taylor vortex about Z."""
    x, y = np.indices(shape[:2]).astype(float)
    dx, dy = x-center[0], y-center[1]
    g = np.exp(.5*(1-(dx*dx+dy*dy)/radius**2))
    return -peak*dy/radius*g, peak*dx/radius*g, -.5*peak*peak*g*g


def vortex_setup(scale=1, oblique=False):
    """Domain, vortex centre/radius, window and reference shape."""
    R, U, n = 5.*scale, lattice_speed(SPEED), int(64*scale)
    if oblique:
        direction, centre = np.array([.6, .8]), np.array([40., 32.])*scale
        steps = max((n+6*R-centre[0])/direction[0], (n+6*R-centre[1])/direction[1])/U
        side = int(math.ceil(max(centre+direction*U*steps)+8*R))
        shapes = [(n, n), (side, side)]
    else:
        direction, centre = np.array([1., 0.]), np.array([32., 24.])*scale
        steps = (n+6*R-centre[0])/U
        shapes = [(n, int(48*scale)), (int(math.ceil(centre[0]+U*steps+8*R)), int(48*scale))]
    return dict(radius=R, direction=direction, centre=centre, steps=int(math.ceil(steps)), shapes=shapes)


def vortex(system, scale=1, dtype=torch.float64, strength=.5, oblique=False, backflow='velocity', steps=None, device='cpu'):
    """Convected Taylor vortex leaving through X+ (or the X+/Y+ corner if oblique)."""
    g = vortex_setup(scale, oblique)
    U, direction = lattice_speed(SPEED), g['direction']
    V = strength*U
    end = g['steps'] if steps is None else steps
    inflow = (SPEED*direction[0], SPEED*direction[1], 0.)
    outflow = dict(type='open', velocity=[0., 0., 0.], backflow_mode=backflow)
    runs = []
    for nx, ny in g['shapes']:
        faces = faces_x(system, inflow, outflow)
        if oblique:
            faces[2], faces[3] = dict(type='velocity', velocity=list(inflow)), outflow
        flow, solver = build(spec_for(system, (nx, ny, 4), faces), dtype, device)
        u_v, v_v, p = taylor((nx, ny), g['centre'], g['radius'], V)
        u = np.zeros((3, nx, ny, 4)); u[0] = (U*direction[0]+u_v)[..., None]; u[1] = (U*direction[1]+v_v)[..., None]
        set_state(flow, np.broadcast_to((3*p)[..., None], (nx, ny, 4)).copy(), u)
        runs.append((flow, solver))
    (n, ny), history, incoming = g['shapes'][0], [], 0
    for step in range(0, end+1, 10):
        if step:
            for flow, solver in runs:
                solver(10)
            incoming = max(incoming, incoming_links(runs[0][1]))
        a, b = state(runs[0][0])[1], state(runs[1][0])[1][:, :n, :ny]
        history.append(float(np.max(np.linalg.norm(a-b, axis=0))/V))
    ok = finite(runs, *history)
    return dict(case='C2' if oblique else ('V1' if strength <= .5 else 'V2'), system=system, dtype=str(dtype),
                scale=scale, strength=strength, backflow_mode=backflow, steps=end//10*10, requested_steps=end,
                reference_shape=list(g['shapes'][1]),
                error=max(history), history_max_every_10=history, max_incoming_open=incoming, finite=ok,
                criterion=CRITERIA['vortex'], passed=bool(ok and max(history) <= CRITERIA['vortex']))


def uniform_corner(dtype=torch.float64, steps=200, device='cpu'):
    """Uniform oblique flow through two velocity and two open faces with shared corners."""
    inflow = [3., 4., 0.]
    faces = [dict(type='velocity', velocity=inflow), dict(type='open', velocity=[0., 0., 0.]),
             dict(type='velocity', velocity=inflow), dict(type='open', velocity=[0., 0., 0.]),
             dict(type='wall'), dict(type='slip')]
    flow, solver = build(spec_for('S', (16, 16, 4), faces), dtype, device)
    u = np.zeros((3, *flow.resolution)); u[0], u[1] = lattice_speed(3.), lattice_speed(4.)
    set_state(flow, np.zeros(flow.resolution), u)
    residual = error = 0.
    for step in range(1, steps+1):
        solver(1)
        residual = float(np.maximum(residual, abs(solver.external_links.report['mass_budget_residual_lu'])))
        if step % 10 == 0 or step == steps:  # protocol samples every 10 steps, plus the endpoint
            error = float(np.maximum(error, np.max(np.abs(flow.u_pu.cpu().numpy()-np.array(inflow)[:, None, None, None]))))
    ok = finite([(flow,)], error, residual)
    mass_ok = dtype != torch.float64 or residual < CRITERIA['mass_lu']
    return dict(case='C1', system='S', dtype=str(dtype), steps=steps, max_velocity_error_m_s=error,
                max_mass_budget_residual_lu=residual, criterion_m_s=CRITERIA['uniform_m_s'], finite=ok,
                passed=bool(ok and error <= CRITERIA['uniform_m_s'] and mass_ok))


def reversal_setup(dx=1.):
    """Grid, declared analytic length L=(Nx-1)dx between boundary nodes, and
    the matching initial linear pressure."""
    nx = int(round(63/dx))+1
    length, drop = (nx-1)*dx, 20.
    return dict(nx=nx, length=length, drop=drop, density=1.225, start=-1.,
                pressure=drop*(1-np.arange(nx)*dx/length), period=2*1.225*length/drop)


def reversal(dx=1., dtype=torch.float64, steps=None, device='cpu'):
    """Pressure-driven reversal through two pressure-backflow open faces."""
    g = reversal_setup(dx)
    faces = [dict(type='open', velocity=[0., 0., 0.], pressure_pa=g['drop'], backflow_mode='pressure'),
             dict(type='open', velocity=[0., 0., 0.], pressure_pa=0., backflow_mode='pressure'),
             dict(type='periodic'), dict(type='periodic'), dict(type='wall'), dict(type='slip')]
    flow, solver = build(spec_for('S', (g['nx'], 4, 4), faces, dx=dx), dtype, device)
    delta = np.asarray(flow.units.convert_pressure_to_lu(g['pressure']), float)/flow.stencil.cs**2
    u = np.zeros((3, *flow.resolution)); u[0] = lattice_speed(g['start'])
    set_state(flow, np.broadcast_to(delta[:, None, None], flow.resolution).copy(), u)
    dt = float(flow.units.convert_time_to_pu(1))
    rate = g['drop']/(g['density']*g['length'])
    end = int(math.ceil(2*g['period']/dt)) if steps is None else steps
    mean_error = node_error = residual = 0.
    incoming = dict(outlet=False, inlet=False)
    for step in range(10, end+1, 10):
        solver(10)
        expected = g['start']+rate*step*dt
        ux = flow.u_pu[0].cpu().numpy()
        # np.maximum propagates NaN; max() would keep an earlier passing value.
        mean_error = float(np.maximum(mean_error, abs(float(ux.mean())-expected)))
        node_error = float(np.maximum(node_error, np.max(np.abs(ux-expected))))
        residual = float(np.maximum(residual, abs(solver.external_links.report['mass_budget_residual_lu'])))
        if incoming_links(solver):
            incoming['outlet' if ux.mean() < 0 else 'inlet'] = True
    mass_ok = dtype != torch.float64 or residual < CRITERIA['mass_lu']
    ok, done = finite([(flow,)], mean_error, node_error, residual), end//10*10
    return dict(case='R1', system='S', dtype=str(dtype), dx=dx, steps=done, requested_steps=end, finite=ok,
                physical_seconds=done*dt, final_expected_m_s=g['start']+rate*done*dt, max_mean_error_m_s=mean_error,
                max_node_error_m_s=node_error, incoming_observed=incoming, max_mass_budget_residual_lu=residual,
                passed=bool(mean_error <= CRITERIA['reversal_mean'] and node_error <= CRITERIA['reversal_node']
                            and all(incoming.values()) and mass_ok and ok))


def cut_setup(system, scale=1.):
    """Small-domain grid and block placement; the reference doubles X."""
    n, ny = int(40*scale), int(36*scale)
    width = int(6*scale)
    return dict(n=n, ny=ny, nz=int(12*scale) if system == 'S' else 4, edge=n-int(12*scale),
                width=width, low=ny//2-width//2)


def cut_status(ok, settled, interior, band):
    """INCONCLUSIVE if non-finite or unsettled; PASS only inside every limit."""
    if not ok or settled > CRITERIA['settled']:
        return 'INCONCLUSIVE'
    within = (interior[0] <= CRITERIA['cut_interior_l2'] and interior[1] <= CRITERIA['cut_interior_linf']
              and band[0] <= CRITERIA['cut_band_l2'] and band[1] <= CRITERIA['cut_band_linf'])
    return 'PASS' if within else 'FAIL'


def cut_face(system, flowthroughs=4., dtype=torch.float64, scale=1., device='cpu'):
    """Long laminar block crossing the open X+ face, against a longer reference."""
    g = cut_setup(system, scale)
    n, U = g['n'], lattice_speed(SPEED)

    def block(c):
        inside = (c[0] >= g['edge']) & (c[1] >= g['low']) & (c[1] < g['low']+g['width'])
        return inside & (c[2] < g['nz']//2) if system == 'S' else inside
    runs = []
    for nx in (n, 2*n):
        spec = spec_for(system, (nx, g['ny'], g['nz']), faces_x(system, (SPEED, 0., 0.)), viscosity=.3, cs=0., block=block)
        flow, solver = build(spec, dtype, device)
        u = np.zeros((3, *flow.resolution)); u[0] = U
        set_state(flow, np.zeros(flow.resolution), u)
        runs.append((flow, solver))
    end = int(math.ceil(flowthroughs*2*n/U))
    check = max(end-1000, 0)
    for flow, solver in runs:
        solver(check)
    before = [state(flow)[1] for flow, _ in runs]
    for flow, solver in runs:
        solver(end-check)
    after = [state(flow)[1] for flow, _ in runs]
    settled = max(float(np.linalg.norm(a-b)/np.linalg.norm(a)) for a, b in zip(after, before))
    small, ref = after[0], after[1][:, :n]
    fluid = ~runs[0][0].solid.cpu().numpy()

    def compare(region):
        mask = fluid & region[:, None, None]
        d = (small-ref)[:, mask]
        return float(np.linalg.norm(d)/np.linalg.norm(ref[:, mask])), float(np.max(np.linalg.norm(d, axis=0))/U)
    x = np.arange(n)
    interior, band = compare(x <= n-7), compare(x > n-7)
    backflow, ok = incoming_links(runs[0][1]), finite(runs, settled, *interior, *band)
    status = cut_status(ok, settled, interior, band)
    return dict(case='K1', system=system, dtype=str(dtype), scale=scale, steps=end, shape=[n, g['ny'], g['nz']],
                reference_shape=[2*n, g['ny'], g['nz']], interior_l2=interior[0], interior_linf_over_u=interior[1],
                band_l2=band[0], band_linf_over_u=band[1], settled_change=settled, incoming_open_at_end=backflow,
                separated_cut=backflow > 0, finite=ok, status=status, passed=status == 'PASS')


F32 = dict(dtype=torch.float32)
CASES = {  # name: (function, arguments); '-fp32' rows also run on --device
    'A1-S': (acoustic, dict(system='S')), 'A1-N': (acoustic, dict(system='N')),
    'A1-S-fp32': (acoustic, dict(system='S', **F32)), 'A1-N-fp32': (acoustic, dict(system='N', **F32)),
    'A1-S-fine': (acoustic, dict(system='S', scale=2)),
    'A2-S': (acoustic, dict(system='S', side='inlet')), 'A2-N': (acoustic, dict(system='N', side='inlet')),
    'V1-S': (vortex, dict(system='S')), 'V1-N': (vortex, dict(system='N')),
    'V1-S-fp32': (vortex, dict(system='S', **F32)), 'V1-N-fp32': (vortex, dict(system='N', **F32)),
    'V1-S-fine': (vortex, dict(system='S', scale=2)),
    'V2-S': (vortex, dict(system='S', strength=1.5)),
    'V2-S-pressure': (vortex, dict(system='S', strength=1.5, backflow='pressure')),
    'C1-S': (uniform_corner, {}), 'C1-S-fp32': (uniform_corner, F32),
    'C2-S': (vortex, dict(system='S', oblique=True)), 'C2-S-fp32': (vortex, dict(system='S', oblique=True, **F32)),
    'R1-S': (reversal, {}), 'R1-S-fine': (reversal, dict(dx=.5)), 'R1-S-fp32': (reversal, F32),
    'K1-S': (cut_face, dict(system='S')), 'K1-N': (cut_face, dict(system='N')),
    'K1-S-fp32': (cut_face, dict(system='S', **F32)), 'K1-N-fp32': (cut_face, dict(system='N', **F32)),
}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cases', default=None, help='comma-separated; default all (CPU) or all -fp32 rows')
    p.add_argument('--device', default='cpu', help='cpu, mps or cuda:0; non-CPU devices run FP32 rows only')
    a = p.parse_args(argv)
    names = a.cases.split(',') if a.cases else [k for k in CASES if a.device == 'cpu' or k.endswith('-fp32')]
    unknown = sorted(set(names)-set(CASES))
    if unknown:
        raise SystemExit('Unknown cases: '+', '.join(unknown))
    if a.device != 'cpu' and not all(k.endswith('-fp32') for k in names):
        raise SystemExit('Only -fp32 rows run on '+a.device+' (no float64 there)')
    reports = {}
    for name in names:
        start = time.monotonic()
        function, arguments = CASES[name]
        reports[name] = dict(function(device=a.device, **arguments), device=a.device, wall_seconds=time.monotonic()-start)
        print(name, json.dumps({k: v for k, v in reports[name].items() if k != 'history_max_every_10'}), flush=True)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(dict(criteria=CRITERIA, device=a.device, physical_validation=False,
                                            torch=torch.__version__, cases=reports), indent=2)+'\n')
    failed = [k for k, r in reports.items() if r['passed'] is False]
    print('failed:', ', '.join(failed) or 'none')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
