"""Worker-side numerical envelope checks; completion and validation are separate."""
import math
import torch

POLICY = 'hawa-low-mach-v1'


def assess(session):
    flow = session.flow
    with torch.no_grad():
        rho = flow.rho()[0]
        u = flow.u()
        solid = getattr(flow, 'solid', torch.zeros_like(rho, dtype=torch.bool))
        fluid = ~solid
        finite = bool(torch.isfinite(flow.f).all().cpu())
        positive = bool((rho[fluid] > 0).all().cpu())
        mach = torch.sqrt((u * u).sum(0)) * math.sqrt(3)
        valid = finite and positive and bool(fluid.any().cpu())
        maximum = float(mach[fluid].max().cpu()) if valid else None
        deviation = float((rho[fluid] - 1).abs().max().cpu()) if valid else None
        count = int(((mach > .15) & fluid).sum().cpu()) if valid else 0
        reasons = []
        state = 'within-tested-envelope'
        if not valid:
            state = 'rejected'; reasons.append('Nonfinite populations, nonpositive density or no fluid cells')
        elif maximum > .15 or deviation > .1:
            state = 'rejected'; reasons.append('Local lattice Mach > 0.15 or density deviation > 10%')
        elif maximum > .1 or deviation > .05:
            state = 'warning'; reasons.append('Local lattice Mach > 0.10 or density deviation > 5%')
        old = getattr(session, 'quality', {})
        rank = {'unchecked': -1, 'within-tested-envelope': 0, 'warning': 1, 'rejected': 2}
        worst = old.get('status', state)
        if rank[state] > rank[worst]: worst = state
        if worst != state: reasons = old.get('reasons', [])
        flux = None
        backflow = None
        if valid and hasattr(flow, 'solid'):
            dx = float(flow.units.convert_length_to_pu(1))
            physical_u = flow.u_pu
            physical_rho = flow.rho_pu[0]
            # Nodal face quadrature, explicitly reported as an estimate.
            faces = []
            for axis in range(3):
                weights = torch.ones_like(rho.select(axis, 0))
                for a in range(2):
                    edge = [slice(None)] * 2
                    edge[a] = 0; weights[tuple(edge)] *= .5
                    edge[a] = -1; weights[tuple(edge)] *= .5
                for side in (0, -1):
                    value = physical_rho.select(axis, side) * physical_u[axis].select(axis, side)
                    value = value * fluid.select(axis, side) * weights * dx**2
                    faces.append(float(value.sum().cpu()) * (-1 if side == 0 else 1))
            types = session.spec.get('boundaries', ['inlet','outlet','periodic','periodic','wall','slip'])
            if session.spec.get('boundary_set'):
                from .boundary_contracts import conditions
                types = [c['type'] for c in conditions(session.spec)]
            if session.spec.get('neutral_precursor'):
                types = ['periodic']*4+['wall','slip']
            external = sum(value for value, kind in zip(faces, types) if kind != 'periodic')
            flux = {'outward_mass_kg_s': faces, 'net_external_mass_kg_s': external,
                    'periodic_pairs_excluded_from_net': True,
                    'method': 'nodal trapezoidal face estimate; not a discrete conservation proof'}
            backflow = {'inlet_cells': int(((physical_u[0, 0] < 0) & fluid[0]).sum().cpu()),
                        'outlet_cells': int(((physical_u[0, -1] < 0) & fluid[-1]).sum().cpu())}
        if valid and session.spec.get('boundary_set'):
            backflow = {'incoming_nodes_by_face': [int(((physical_u[i//2].select(i//2,-1 if i%2 else 0)*(1 if i%2 else -1)<0)&fluid.select(i//2,-1 if i%2 else 0)).sum().cpu()) for i in range(6)],
                        'face_order': ['x-','x+','y-','y+','z-','z+']}
        if session.spec.get('neutral_precursor'):
            # Lattice planes are cell centres; nodal flux there is not wall leakage.
            flux = None
            backflow = None
        return {'policy': POLICY, 'status': worst, 'current_status': state,
                'reasons': reasons, 'iteration': int(flow.i),
                'time_seconds': float(flow.units.convert_time_to_pu(flow.i)),
                'max_lattice_mach': maximum,
                'peak_sampled_lattice_mach': max(maximum or 0, old.get('peak_sampled_lattice_mach', 0)),
                'mach_exceedance_cells': count, 'max_density_deviation': deviation,
                'boundary_method': 'shifted-links-v1' if hasattr(session.solver,'external_links') else 'halfway-specular-stress-v1' if session.spec.get('neutral_precursor') else session.spec.get('boundary_method', 'legacy-equilibrium-v1'),
                'boundary_diagnostics': dict(session.solver.external_links.report) if hasattr(session.solver,'external_links') else dict(session.solver.general_boundary.report) if hasattr(session.solver, 'general_boundary') else None,
                'collision_method': session.spec.get('collision', 'regularized'),
                'finite': finite, 'positive_density': positive, 'boundary_flux': flux, 'backflow': backflow,
                'physical_model_status': ('unvalidated-neutral-external' if session.spec['neutral_precursor'].get('mode')=='external' else 'unvalidated-neutral-precursor') if session.spec.get('neutral_precursor') else 'not-assessed',
                'wall_diagnostics': dict(session.solver.rough_floor.report) if hasattr(session.solver, 'rough_floor') else None,
                'cadence_steps': 5, 'transfer_eligible': bool(worst == 'within-tested-envelope'),
                'transfer_scope': 'experimental-neutral-nesting' if session.spec.get('neutral_precursor') else 'numerical-envelope',
                'absolute_time_seconds': float(session.spec.get('time_origin_seconds',0.))+float(flow.units.convert_time_to_pu(flow.i)), 
                'scope': 'Sampled low-Mach envelope only; not convergence, atmospheric validation or conservation certification'}
