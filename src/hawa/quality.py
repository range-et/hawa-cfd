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
        violations = []
        iteration = int(flow.i)
        time_seconds = float(flow.units.convert_time_to_pu(flow.i))
        state = 'within-tested-envelope'
        if not valid:
            state = 'rejected'; reasons.append('Nonfinite populations, nonpositive density or no fluid cells')
        elif maximum > .15 or deviation > .1:
            state = 'rejected'; reasons.append('Local lattice Mach > 0.15 or density deviation > 10%')
        elif maximum > .1 or deviation > .05:
            state = 'warning'; reasons.append('Local lattice Mach > 0.10 or density deviation > 5%')
        if valid and state != 'within-tested-envelope':
            limits = (.15, .1) if state == 'rejected' else (.1, .05)
            for quantity, value, limit in zip(
                    ('max_lattice_mach', 'max_density_deviation'),
                    (maximum, deviation), limits):
                if value > limit:
                    violations.append({'quantity': quantity, 'value': value, 'limit': limit})
            reasons = []
            for v in violations:
                density_metric = v['quantity'] == 'max_density_deviation'
                scale = 100 if density_metric else 1
                amount, bound = v['value'] * scale, v['limit'] * scale
                displayed, threshold = f"{amount:.6g}", f"{bound:.6g}"
                if displayed == threshold:
                    displayed = repr(amount)  # Never display a false "5% > 5%".
                label, unit = ('density deviation', '%') if density_metric else ('lattice Mach', '')
                detail = f"{label} {displayed}{unit} > {threshold}{unit}"
                reasons.append(f"Sampled {detail} at step {iteration} (t={time_seconds:.6g} s)")
        elif not valid:
            violations = [{'quantity': 'finite_positive_fluid', 'value': False, 'limit': True}]
            reasons = [reasons[0] + f' at step {iteration} (t={time_seconds:.6g} s)']
        trigger = ({'status': state, 'iteration': iteration, 'time_seconds': time_seconds,
                    'violations': violations} if violations else None)
        old = getattr(session, 'quality', {})
        rank = {'unchecked': -1, 'within-tested-envelope': 0, 'warning': 1, 'rejected': 2}
        worst = old.get('status', 'unchecked')
        if rank[state] > rank[worst]:
            worst = state
        elif rank[worst] > 0:
            # Keep the first assessment that established the worst severity.
            # Older checkpoints cannot supply provenance they never recorded.
            reasons = old.get('reasons', [])
            trigger = old.get('trigger')
        peaks = {}
        for quantity, value in (('lattice_mach', maximum), ('density_deviation', deviation)):
            key = 'peak_sampled_' + quantity
            previous = old.get(key, 0)
            increased = value is not None and value > previous
            peaks[key] = value if increased else previous
            peaks[key + '_iteration'] = iteration if increased else old.get(key + '_iteration')
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
                'reasons': reasons, 'trigger': trigger, 'iteration': iteration,
                'time_seconds': time_seconds,
                'max_lattice_mach': maximum,
                **peaks,
                'mach_exceedance_cells': count, 'max_density_deviation': deviation,
                'boundary_method': 'shifted-links-v1' if hasattr(session.solver,'external_links') else 'halfway-specular-stress-v1' if session.spec.get('neutral_precursor') else session.spec.get('boundary_method', 'legacy-equilibrium-v1'),
                'boundary_diagnostics': dict(session.solver.external_links.report) if hasattr(session.solver,'external_links') else dict(session.solver.general_boundary.report) if hasattr(session.solver, 'general_boundary') else None,
                'collision_method': session.spec.get('collision', 'regularized'),
                'finite': finite, 'positive_density': positive, 'boundary_flux': flux, 'backflow': backflow,
                'physical_model_status': ('unvalidated-neutral-external' if session.spec['neutral_precursor'].get('mode')=='external' else 'unvalidated-neutral-precursor') if session.spec.get('neutral_precursor') else 'not-assessed',
                'wall_diagnostics': dict(session.solver.rough_floor.report) if hasattr(session.solver, 'rough_floor') else None,
                'dissipation_storage': session.solver.collision.storage_resolution(flow, fluid) if valid and hasattr(session.solver.collision, 'storage_resolution') else None,
                'cadence_steps': 5, 'transfer_eligible': bool(worst == 'within-tested-envelope'),
                'transfer_scope': 'experimental-neutral-nesting' if session.spec.get('neutral_precursor') else 'numerical-envelope',
                'absolute_time_seconds': float(session.spec.get('time_origin_seconds',0.))+float(flow.units.convert_time_to_pu(flow.i)), 
                'scope': 'Sampled low-Mach envelope only; not convergence, atmospheric validation or conservation certification'}


def validate_provenance(quality, iteration):
    """Reject malformed new checkpoint history before any solver state is changed.

    Missing fields remain valid for legacy checkpoints; unknown peak locations
    and trigger provenance stay unknown rather than being inferred on reload.
    """
    for quantity in ('lattice_mach', 'density_deviation'):
        key = 'peak_sampled_' + quantity
        peak = quality.get(key, 0)
        step = quality.get(key + '_iteration')
        if (type(peak) not in (int, float) or not math.isfinite(peak) or peak < 0
                or (step is not None and (type(step) is not int or not 0 <= step <= iteration))):
            raise ValueError('Checkpoint quality provenance is invalid')
    trigger = quality.get('trigger')
    if trigger is None:
        return
    if not isinstance(trigger, dict):
        raise ValueError('Checkpoint quality trigger is invalid')
    state = trigger.get('status')
    step, time = trigger.get('iteration'), trigger.get('time_seconds')
    violations = trigger.get('violations')
    if (state not in ('warning', 'rejected') or state != quality['status']
            or type(step) is not int or not 0 <= step <= iteration
            or type(time) not in (int, float) or not math.isfinite(time) or time < 0
            or not isinstance(violations, list) or not violations):
        raise ValueError('Checkpoint quality trigger is invalid')
    limits = {'max_lattice_mach': .15 if state == 'rejected' else .1,
              'max_density_deviation': .1 if state == 'rejected' else .05}
    for violation in violations:
        if not isinstance(violation, dict):
            raise ValueError('Checkpoint quality violation is invalid')
        quantity, value, limit = (violation.get(k) for k in ('quantity', 'value', 'limit'))
        if quantity == 'finite_positive_fluid':
            valid = state == 'rejected' and value is False and limit is True
        else:
            valid = (isinstance(quantity, str) and quantity in limits
                     and type(value) in (int, float) and math.isfinite(value)
                     and type(limit) in (int, float) and limit == limits[quantity] and value > limit)
        if not valid:
            raise ValueError('Checkpoint quality violation is invalid')
