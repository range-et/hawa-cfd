"""Link-owned experimental external boundaries for shifted-population flow.

One writer per missing population. Closed source bodies supply a one-cell solid
halo so a cropped building is classified across, not capped at, a domain face.
Incoming flow uses non-equilibrium extrapolation. Outgoing populations use a
first-order convective update and pressure reference; this is not nonreflecting.
"""
import numpy as np
import torch
from .boundary_contracts import FACES, conditions
from .atmosphere import neutral_profile

METHOD='shifted-links-v1'


def compile_links(spec):
    if spec.get('boundary_method')!=METHOD: raise ValueError('External neutral flow requires '+METHOD)
    cs=conditions(spec);n=np.array(spec['shape']);shape=tuple(n)
    if cs[4]['type']!='wall' or cs[5]['type'] not in ('slip','velocity','open'):
        raise ValueError('External neutral flow requires rough Z- wall and a slip/velocity/open Z+ face')
    for c in cs[:4]:
        if c['type'] not in ('velocity','open','periodic'): raise ValueError('Horizontal faces require velocity/open/periodic')
    for a in range(2):
        if (cs[2*a]['type']=='periodic') != (cs[2*a+1]['type']=='periodic'):raise ValueError('Periodic faces must be paired')
    if not any(c['type']=='open' for c in cs):raise ValueError('External neutral flow needs an open pressure reference')
    if np.linalg.norm(cs[4].get('velocity',[0.,0.,0.]))>0:
        raise ValueError('Neutral ground must be stationary')
    for condition in cs:
        if condition.get('profile','uniform') not in ('uniform','neutral','mapped'):
            raise ValueError('External neutral boundaries support uniform, neutral or attached v2 profiles')
        pressure=condition.get('pressure_pa',0.)
        # p/(rho_ref*c_s,physical^2) is the relative density perturbation.
        density_delta=pressure/spec.get('density',1.225)*(spec.get('mach',.05)/spec['speed'])**2
        if abs(density_delta)>.02:
            raise ValueError('Exterior pressure exceeds 2% density budget')
    solid=np.zeros(shape,bool);solid.flat[spec.get('solid',[])]=True
    hn=tuple(n+2);halo=np.zeros(hn,bool)
    if spec.get('solid') and 'solid_halo' not in spec: raise ValueError('Buildings require a classified one-cell solid_halo from full closed geometry')
    hi=spec.get('solid_halo',[])
    if not isinstance(hi,list) or any(type(i) is not int or i<0 or i>=np.prod(hn) for i in hi):raise ValueError('Invalid solid halo indices')
    halo.flat[hi]=True
    if not np.array_equal(halo[1:-1,1:-1,1:-1],solid):raise ValueError('Halo interior does not match solid occupancy')
    sample=spec['neutral_precursor'].get('wall_sample_index',0)
    if np.any((~solid[:,:,0])&solid[:,:,sample]):raise ValueError('Rough-wall sample lies inside a building; lower sample height or refine geometry')
    for a in range(2):
        if cs[2*a]['type']=='periodic':
            if np.any(np.take(solid,[0,-1],axis=a)):raise ValueError('Buildings must clear periodic seams')
    # Check shared prescribed exterior data before choosing corner-link ownership.
    vectors=[np.asarray(c.get('velocity',[0,0,0]),float) for c in cs]
    for a in range(6):
        for b in range(a+1,6):
            if a//2!=b//2 and cs[a]['type']==cs[b]['type']=='velocity':
                if cs[a].get('profile')==cs[b].get('profile')=='mapped':continue
                if not np.allclose(vectors[a],vectors[b],rtol=0,atol=1e-10) or cs[a].get('profile','uniform')!=cs[b].get('profile','uniform'):
                    raise ValueError('Adjacent prescribed faces require matching exterior data')
    if any(c.get('profile')=='mapped' for c in cs):
        from .boundary_series import active_faces,geometry_key
        ref=spec.get('boundary_field',{})
        if ref.get('faces')!=active_faces(spec) or ref.get('geometry_sha256')!=geometry_key(spec):raise ValueError('Mapped field face/geometry contract does not match child')
        if any(c['type'] in ('open','velocity') and c.get('profile')!='mapped' for c in cs):raise ValueError('V2 requires data on every active exterior face')
    for c in cs:
        if c.get('profile')=='mapped':continue
        v=np.asarray(c.get('velocity',[0,0,0]),float)
        if c.get('profile')=='neutral':
            a=spec['neutral_precursor'];v=neutral_profile(n[2]*spec['dx'],v,a['reference_height_m'],a['roughness_length_m'])
        if np.linalg.norm(v)*spec.get('mach',.05)/spec['speed']>.1:raise ValueError('Exterior data exceeds lattice Mach 0.10 budget')
    import lettuce as lt
    e=np.asarray(lt.D3Q19().e,dtype=int)
    coords=np.indices(shape).reshape(3,-1).T;fluid=~solid.ravel()
    links=[];wall_masks=[np.zeros((19,n[0],n[1]),bool) for _ in range(2)]
    for q,d in enumerate(e):
        src=coords-d;outside=(src<0)|(src>=n)
        owner=np.full(len(coords),-1,dtype=np.int8)
        # Prescribed faces take priority over open at exterior corner links.
        for kind in ('open','velocity'):
            for face,c in enumerate(cs):
                if c['type']==kind:
                    a=face//2;mask=(src[:,a]<0) if face%2==0 else (src[:,a]>=n[a])
                    owner[mask]=face
        for a in range(2):
            if cs[2*a]['type']=='periodic':src[:,a]%=n[a]
        neighbour=halo[tuple((src+1).T)]
        body=np.flatnonzero(fluid&neighbour)
        exterior=np.flatnonzero(fluid&~neighbour&(owner>=0))
        links.append(dict(body=body,external=exterior,owner=owner[exterior]))
        for side,z in enumerate((0,n[2]-1)):
            wall=fluid&~neighbour&(owner<0)&outside[:,2]&(coords[:,2]==z)
            wall_masks[side][q]=wall.reshape(shape)[:,:,z]
    return dict(links=links,wall_masks=wall_masks,conditions=cs,
                report=dict(method=METHOD,body_links=sum(len(x['body']) for x in links),external_links=sum(len(x['external']) for x in links),ownership='one writer per incoming link; halo solids before exterior, then ground/lid',nonreflecting=False))


class ExternalLinks:
    """Batch all owned links, including corner links, in one tensor update."""

    def __init__(self, solver, plan):
        self.f = solver.flow
        self.plan = plan
        f = self.f
        device = f.context.device
        e = np.asarray(f.stencil.e)
        opposite = np.array([np.flatnonzero(np.all(e == -d, axis=1))[0] for d in e])
        shape = tuple(f.resolution)
        self.faces = [dict(c, density_delta=float(f.units.convert_pressure_to_lu(
            c.get('pressure_pa', 0.))/f.stencil.cs**2)) for c in plan['conditions']]

        def gather(kind):
            indices = np.concatenate([row[kind] for row in plan['links']])
            q = np.concatenate([np.full(len(row[kind]), q, dtype=int)
                                for q, row in enumerate(plan['links'])])
            return q, indices

        bq, bi = gather('body')
        q, ix = gather('external')
        self.body_q = torch.tensor(bq, device=device)
        self.body_ix = torch.tensor(bi, device=device)
        self.body_opposite = torch.tensor(opposite[bq], device=device)
        self.q = torch.tensor(q, device=device)
        self.ix = torch.tensor(ix, device=device)
        self.opposite = torch.tensor(opposite[q], device=device)
        owner = np.concatenate([row['owner'] for row in plan['links']])
        coords = np.array(np.unravel_index(ix, shape))
        donors = coords.copy()
        velocity = np.zeros((3, len(ix)))
        self.active_faces = []
        c = f.spec['neutral_precursor']
        for face, condition in enumerate(self.faces):
            mask = owner == face
            if not mask.any():
                continue
            self.active_faces.append((face, condition, torch.tensor(mask, device=device)))
            donors[face//2, mask] += 1 if face%2 == 0 else -1
            v = np.array(condition.get('velocity', [0., 0., 0.]))
            if condition.get('profile') == 'neutral':
                velocity[:, mask] = neutral_profile((coords[2, mask]+.5)*f.spec['dx'],
                    v, c['reference_height_m'], c['roughness_length_m']).T
            else:
                velocity[:, mask] = v[:, None]
        donor_indices = np.ravel_multi_index(donors, shape)
        solid = f.solid.detach().cpu().numpy().ravel()
        # Cropped bodies can occupy the inward axial donor. Use the local fluid
        # node there; never extrapolate a zeroed solid population.
        donor_indices = np.where(solid[donor_indices], ix, donor_indices)
        self.donor = torch.tensor(donor_indices, device=device)
        self.velocity = f.units.convert_velocity_to_lu(f.context.convert_to_tensor(velocity))
        self.mapped=None
        if f.spec.get('boundary_field'):
            from .boundary_series import BoundarySeries
            self.mapped=BoundarySeries(f,ix)
        self.column = torch.arange(len(ix), device=device)
        nodes, first = np.unique(ix, return_index=True)
        xyz = np.array(np.unravel_index(nodes, shape))
        protected = np.zeros((19, len(nodes)), bool)
        # Preserve every incoming population already owned by a body or wall.
        selected = np.isin(bi, nodes)
        protected[bq[selected], np.searchsorted(nodes, bi[selected])] = True
        for side, z in enumerate((0, shape[2]-1)):
            protected |= (xyz[2] == z)[None] & plan['wall_masks'][side][:, xyz[0], xyz[1]]
        # Constrained moment projection: minimum weighted change to free
        # populations, while imposing density/momentum and keeping owned links.
        # Its 4x4 system depends only on the local topology, not on flow state.
        A = np.vstack((np.ones(19), e.T)).astype(float)
        weights = (~protected).T*np.asarray(f.stencil.w)[None]
        matrices = np.einsum('aq,nq,bq->nab', A, weights, A)
        if len(nodes) and np.any(np.linalg.cond(matrices)>1e8):
            raise ValueError('Exterior/wall intersection cannot satisfy independent fluid moments')
        projection = np.einsum('nq,qa,nab->nqb', weights, A.T, np.linalg.inv(matrices))
        second = np.array([e[:,i]*e[:,j] for i,j in ((0,0),(1,1),(2,2),(0,1),(0,2),(1,2))],float)
        nullspace=np.eye(19)[None]-projection@A
        metric=(nullspace*weights[:,None,:])@nullspace.transpose(0,2,1)
        stress_projection=metric@second.T@np.linalg.pinv(second[None]@metric@second.T,rcond=1e-12)
        self.fd_nodes = torch.tensor(nodes, device=device)
        # A donor on another exterior face lacks this step's missing links.
        self.donor_complete = torch.tensor(~np.isin(donor_indices, nodes), device=device)
        self.fd_columns = torch.tensor(first, device=device)
        self.protected = torch.tensor(protected, device=device)
        self.projection = f.context.convert_to_tensor(projection)
        self.moments = f.context.convert_to_tensor(A)
        self.second_moments=f.context.convert_to_tensor(second)
        self.stress_projection=f.context.convert_to_tensor(stress_projection)
        self.Q = (torch.einsum('qa,qb->qab', f.torch_stencil.e, f.torch_stencil.e)
                  - torch.eye(3, device=device, dtype=f.context.dtype)[None]/3)
        self.report = dict(plan['report'])

    def capture(self):
        # The fixed fluid-cell count cancels analytically. Summing g avoids
        # subtracting two large, nearly equal FP32 absolute fluid masses.
        # Sum each node's populations first: single population planes reach
        # O(1) totals that cancel only across q, so a flat FP32 reduction
        # loses the budget's precision (worst on MPS).
        self.mass_before = self.f.f[:, ~self.f.solid].sum(0).sum()
        self.saved = self.f.f.reshape(19, -1).clone()

    def apply(self):
        f = self.f
        out = f.f.reshape(19, -1)
        mapped_pressure=None
        if self.mapped is not None:
            velocity,pressure=self.mapped.at(float(f.units.convert_time_to_pu(f.i+1)))
            self.velocity=f.units.convert_velocity_to_lu(velocity)
            mapped_pressure=f.units.convert_pressure_to_lu(pressure)/f.stencil.cs**2
        out[self.body_q, self.body_ix] = self.saved[self.body_opposite, self.body_ix]
        source = self.saved[:, self.donor].clone()
        delta = source.sum(0, keepdim=True)
        rho = 1 + delta
        u = torch.einsum('qd,qn->dn', f.torch_stencil.e, source)/rho
        follow = []
        # First-order one-sided convective update of outgoing characteristics.
        # A static copy/NEE outlet retains tangential disturbances at high Re.
        # The transport speed is the measured outward lattice velocity.
        for face, condition, mask in self.active_faces:
            if condition['type'] != 'open':
                continue
            normal = u[face//2]*(1 if face%2 else -1)
            parent_normal=self.velocity[face//2]*(1 if face%2 else -1) if self.mapped is not None else normal
            outgoing = mask & (parent_normal >= 0)
            speed = normal[outgoing].clamp(0, 1)
            source[:, outgoing] = (self.saved[:, self.ix[outgoing]] +
                speed[None]*source[:, outgoing])/(1+speed[None])
            if condition.get('backflow_mode') == 'pressure' and self.mapped is None:
                follow.append((face//2, mask))
        snapshot_normal = u
        delta = source.sum(0, keepdim=True)
        rho = 1 + delta
        u = torch.einsum('qd,qn->dn', f.torch_stencil.e, source)/rho
        # A pressure face's normal speed follows the fluid in both directions.
        # Convecting it at its own speed stalls at u_n=0 and blocks reversal.
        # Use the donor's current (post-stream) speed: the one-step-old
        # snapshot lags an accelerating flow, and the FD stress then reads
        # that lag as strain, shifting the pressure face by tau*a (dx/2 at tau=1/2).
        if follow:
            current = out[:, self.donor]
            current = torch.einsum('qd,qn->dn', f.torch_stencil.e, current)/(1+current.sum(0))
            current = torch.where(self.donor_complete[None], current, snapshot_normal)
        for axis, mask in follow:
            u[axis, mask] = current[axis, mask]
        target_u = u.clone()
        target_delta = delta.clone()
        incoming = f.context.zero_tensor([])
        for face, condition, mask in self.active_faces:
            if condition['type'] == 'velocity':
                target_u[:, mask] = self.velocity[:, mask]
            elif condition['type'] == 'open':
                incoming_velocity=self.velocity if self.mapped is not None else u
                inward = incoming_velocity[face//2, mask]*(1 if face%2 else -1) < 0
                incoming += inward.sum()
                target_u[:, mask] = torch.where(inward[None], self.velocity[:, mask], u[:, mask])
                target_delta[:, mask] = torch.where(inward[None], delta[:, mask],
                    mapped_pressure[None,mask] if mapped_pressure is not None else torch.full_like(delta[:, mask], condition['density_delta']))
                if self.mapped is None and condition.get('backflow_mode','velocity')=='pressure':
                    # Pressure outlet in either direction: normal speed follows
                    # the fluid; only incoming tangential data are prescribed.
                    target_u[face//2,mask]=u[face//2,mask]
                    target_delta[:,mask]=condition['density_delta']
        reconstructed = source + f.equilibrium(f, u=target_u, delta=target_delta) - f.equilibrium(f, u=u, delta=delta)
        out[self.q, self.ix] = reconstructed[self.q, self.column]
        exchange = (out[self.q, self.ix] - self.saved[self.opposite, self.ix]).sum()
        # Reconstruct all moments at exterior nodes. Copying a
        # post-collision non-equilibrium into a post-stream boundary has the
        # wrong stress phase near tau=1/2 and excites boundary kinetic modes.
        # FD regularization follows the Chapman-Enskog stress relation; it
        # changes neither molecular viscosity nor the SGS coefficient.
        ni, columns = self.fd_nodes, self.fd_columns
        before = out[:, ni].sum()
        if self.mapped is not None:
            target_u = self.velocity
            target_delta = mapped_pressure[None]
        mapped_strain=self.mapped.strain_at(float(f.units.convert_time_to_pu(f.i+1))) if self.mapped is not None else None
        if mapped_strain is not None:
            strain=mapped_strain[:,:,columns]*float(f.units.convert_time_to_pu(1))
        else:
            velocity = f.u().reshape(3, -1)
            velocity[:, ni] = target_u[:, columns]
            velocity = velocity.reshape(3, *f.resolution)
            gradient = torch.stack([torch.stack(torch.gradient(velocity[i], dim=(0,1,2), edge_order=2)) for i in range(3)]).reshape(3,3,-1)[:, :, ni]
            strain = .5*(gradient + gradient.transpose(0,1))
        c = f.spec['neutral_precursor']
        tau = (f.units.relaxation_parameter_lu + 3*c.get('smagorinsky_constant', .17)**2
               * torch.sqrt(2*(strain*strain).sum((0,1))))
        d = target_delta[:, columns]
        pi = -(2/3)*(1+d)*tau*strain
        neq = 4.5*torch.einsum('q,qab,abn->qn', f.torch_stencil.w, self.Q, pi)
        regularized = f.equilibrium(f, u=target_u[:, columns], delta=d)+neq
        candidate = torch.where(self.protected, out[:, ni], regularized)
        moments = torch.cat((d, (1+d)*target_u[:, columns]), dim=0)
        residual = moments-self.moments@candidate
        candidate = candidate+torch.einsum('nqk,kn->qn', self.projection, residual)
        # Match every stress moment compatible with protected links, in the
        # nullspace of the already-enforced mass/momentum constraints.
        stress_residual=self.second_moments@(regularized-candidate)
        out[:,ni]=candidate+torch.einsum('nqk,kn->qn',self.stress_projection,stress_residual)
        # The rest population carries no momentum and belongs to no wall link.
        # Correct reduction roundoff in tiny shifted gauge-pressure moments.
        for _ in range(2):out[0,ni] += d[0]-out[:,ni].sum(0)
        nodal_exchange = out[:, ni].sum()-before
        exchange = exchange+nodal_exchange
        f.f[:, f.solid] = 0
        storage = f.f[:, ~f.solid].sum(0).sum() - self.mass_before
        values = torch.stack((incoming, exchange, storage, storage-exchange)).detach().cpu().tolist()
        self.report.update(incoming_open_links=int(values[0]), external_mass_exchange_lu=values[1],
                           fluid_storage_change_lu=values[2], mass_budget_residual_lu=values[3],
                           regularized_exterior_nodes=len(self.fd_nodes), nodal_mass_exchange_lu=float(nodal_exchange.detach().cpu()))

    def reset(self):
        self.report = dict(self.plan['report'])
