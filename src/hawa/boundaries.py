"""Physical boundary contracts and portable full-node NEE LBM adapter.

The physical schema contains face identity and SI data; numerical method selection
is separate. Version 1 supports complete Cartesian faces on stationary uniform
grids. No rough-wall, atmospheric, nonreflecting or arbitrary patch claims.
"""
import numpy as np
import torch

from .boundary_contracts import FACES, conditions
METHOD = 'hawa-nee-v1'


def velocity_plane(spec, face, c):
    shape = spec['shape']; axis = face//2
    v = np.broadcast_to(np.asarray(c.get('velocity', [0.,0.,0.]))[:,None,None],
                        (3, *[n for a,n in enumerate(shape) if a != axis])).copy()
    if c.get('profile') == 'parabolic':
        a = [i for i in range(3) if i != axis].index(c['profile_axis'])
        coordinate = np.linspace(0,1,v.shape[a+1]); weights = 4*coordinate*(1-coordinate)
        sizes = [1,1,1]; sizes[a+1] = len(weights); v *= weights.reshape(sizes)
    return v


def compile_plan(spec):
    if spec.get('boundary_method') != METHOD:
        raise ValueError('Boundary set requires explicit boundary_method '+METHOD)
    if spec.get('moving_bodies') or spec.get('refinement_lower'):
        raise ValueError('NEE boundaries support stationary uniform grids only')
    cs = conditions(spec); shape = tuple(spec['shape'])
    if any(c.get('backflow_mode')=='pressure' for c in cs):
        raise ValueError('Pressure-derived backflow currently requires Neutral Flow external mode')
    if spec.get('boundary_field') and sum(c.get('profile')=='mapped' for c in cs)!=1:
        raise ValueError('Attached field requires exactly one mapped velocity condition')
    solid = np.zeros(shape, bool); solid.flat[spec.get('solid', [])] = True
    for c in cs:
        if np.linalg.norm(c.get('velocity',[0.,0.,0.]))*spec.get('mach',.05)/spec['speed'] > .15:
            raise ValueError('Boundary velocity exceeds lattice Mach 0.15')
    active = [i for i,c in enumerate(cs) if c['type'] in ('velocity','pressure','open')]
    for a in range(3):
        if any(c['type']=='periodic' for c in cs[2*a:2*a+2]) and any(c['type']!='periodic' for c in cs[2*a:2*a+2]):
            raise ValueError('Periodic boundaries must occur in opposite-face pairs')
    if any(a//2 != b//2 for a in active for b in active):
        raise ValueError('Adjacent open/velocity/pressure faces are not qualified; use one opposite-face pair')
    if not any(c['type'] in ('pressure','open') for c in cs) and active:
        raise ValueError('Velocity boundaries require a pressure or open reference face')
    owner = np.full(shape, -1, dtype=np.int8)
    # Walls own shared boundary nodes. Compatibility is checked below.
    for kinds in (('velocity','pressure','open'), ('slip',), ('wall',)):
        for face,c in enumerate(cs):
            if c['type'] in kinds:
                sl=[slice(None)]*3; sl[face//2] = -1 if face%2 else 0
                owner[tuple(sl)] = face
    owner[solid] = -1
    for face,c in enumerate(cs):
        if c['type'] not in ('velocity','wall','open'): continue
        if c.get('profile') == 'mapped':
            from .boundary_data import read
            _, values, _ = read(spec['boundary_field']['path'], spec['boundary_field']['sha256'], allow_wall_zero=True)
            if np.any(values[:,0,owner[0]==face] < 0):
                raise ValueError('Mapped fluid inflow cannot reverse; open series are not supported')
        else: values = velocity_plane(spec,face,c)[None]
        tangents = [a for a in range(3) if a != face//2]
        for other,wall in enumerate(cs):
            if other//2 == face//2 or wall['type'] not in ('wall','slip'): continue
            edge = [slice(None)]*4; edge[2+tangents.index(other//2)] = -1 if other%2 else 0
            v = values[tuple(edge)]
            expected = np.asarray(wall.get('velocity',[0.,0.,0.]))[None,:,None]
            if wall['type']=='wall' and not np.allclose(v, expected, atol=5e-6*spec['speed'] if c.get('profile')=='mapped' else 1e-8, rtol=0):
                raise ValueError('Velocity must match the wall at shared edge nodes; use a compatible profile')
            if wall['type']=='slip' and np.any(np.abs(v[:,other//2]) > (5e-6*spec['speed'] if c.get('profile')=='mapped' else 1e-8)):
                raise ValueError('Velocity must have zero normal component at a slip edge')
    # Every reconstruction uses an interior fluid donor from an immutable snapshot.
    indices = np.flatnonzero(owner >= 0); coords=np.array(np.unravel_index(indices,shape)).T
    donor = coords.copy()
    for a,n in enumerate(shape):
        if cs[2*a]['type'] != 'periodic': donor[coords[:,a]==0,a]=1
        if cs[2*a+1]['type'] != 'periodic': donor[coords[:,a]==n-1,a]=n-2
    donors = np.ravel_multi_index(donor.T,shape)
    if np.any(solid.flat[donors]):
        raise ValueError('Boundary reconstruction donor is solid; enlarge the window or refine geometry')
    if spec.get('wall_links'):
        links=np.asarray(spec['wall_links']); sites=links[:,1].astype(int)
        if np.any(owner.flat[sites]>=0) or np.isin(sites, donors).any():
            raise ValueError('Curved-wall corrections overlap NEE boundary nodes; add clearance')
    return dict(conditions=cs, owner=owner, indices=indices, donors=donors,
                report=dict(method=METHOD, schema=1, boundary_nodes=int(len(indices)),
                            solid_boundary_nodes=int(sum(np.count_nonzero(np.take(solid,0 if i%2==0 else -1,axis=i//2)) for i in range(6))),
                            ownership='disjoint full-node NEE; solid sites excluded',
                            limits='stationary uniform grid; one opposite open pair; no atmospheric or nonreflection qualification'))


class NEEBoundary:
    def __init__(self, simulation, plan):
        self.sim = simulation; self.flow = simulation.flow; self.plan = plan
        f=self.flow; device=f.context.device
        self.ix=torch.tensor(plan['indices'],device=device,dtype=torch.long)
        self.donor=torch.tensor(plan['donors'],device=device,dtype=torch.long)
        self.owner=plan['owner'].flat[plan['indices']]
        self.velocity=[]; self.select=[]; self.rho=[]; self.mapped=None
        for face,c in enumerate(plan['conditions']):
            selected=self.owner==face
            self.select.append(torch.tensor(selected, device=device))
            coords=np.array(np.unravel_index(plan['indices'][selected],tuple(f.resolution)))
            axes=[a for a in range(3) if a!=face//2]
            plane=velocity_plane(f.spec,face,c)
            v=plane[:,coords[axes[0]],coords[axes[1]]]
            self.velocity.append(f.units.convert_velocity_to_lu(f.context.convert_to_tensor(v)))
            rho=1+float(f.units.convert_pressure_pu_to_density_lu(c.get('pressure_pa',0.)))-float(f.units.convert_pressure_pu_to_density_lu(0.))
            if not np.isfinite(rho) or abs(rho-1)>.1:
                raise ValueError('Pressure exceeds supported 10% density range')
            self.rho.append(rho)
            if c.get('profile')=='mapped':
                from .boundary_data import FieldInlet
                self.mapped=FieldInlet(f,f.context.zero_tensor(f.resolution,dtype=torch.bool))
                self.mapped_coords=coords[1:]
        self.slip_projections = []
        coords = np.array(np.unravel_index(plan['indices'], tuple(f.resolution)))
        e = np.asarray(f.stencil.e)
        for face,c in enumerate(plan['conditions']):
            if c['type'] != 'slip': continue
            axis=face//2
            edge=coords[axis] == (f.resolution[axis]-1 if face%2 else 0)
            reflected=e.copy();reflected[:,axis]*=-1
            reflection=[int(np.flatnonzero(np.all(e==v,axis=1))[0]) for v in reflected]
            self.slip_projections.append((axis,torch.tensor(edge,device=device),reflection))
        self.report = dict(plan['report'])

    def reset(self):
        self.report = dict(self.plan["report"])

    def reconstruct(self):
        f=self.flow
        # Compact pseudo-lattice: all moments/equilibrium use trailing dimensions.
        source=f.f.reshape(f.stencil.q,-1)[:,self.donor].clone()
        rho=source.sum(0,keepdim=True)
        u=torch.einsum('qd,qn->dn',f.torch_stencil.e,source)/rho
        neq=source-f.equilibrium(f,rho,u)
        # Remove roundoff in conserved moments before repeated extrapolation.
        # The correction changes neither the intended second-order stress nor
        # the exact-arithmetic NEE scheme.
        mass=neq.sum(0)
        momentum=torch.einsum('qd,qn->dn',f.torch_stencil.e,neq)
        neq-=f.torch_stencil.w[:,None]*(mass[None]+torch.einsum('qd,dn->qn',f.torch_stencil.e,momentum)/f.stencil.cs**2)
        target_rho=rho.clone(); target_u=u.clone(); reversed_nodes=0
        if self.mapped is not None:
            self.mapped(f)
            physical=self.mapped.velocity[:,0]
        for face,c in enumerate(self.plan['conditions']):
            mask=self.select[face]; kind=c['type']
            if kind in ('velocity','wall'):
                v=self.velocity[face]
                if c.get('profile')=='mapped':
                    v=f.units.convert_velocity_to_lu(physical[:,self.mapped_coords[0],self.mapped_coords[1]])
                target_u[:,mask]=v
            elif kind=='slip': target_u[face//2,mask]=0
            elif kind=='pressure': target_rho[:,mask]=self.rho[face]
            elif kind=='open':
                inward=u[face//2,mask]*(1 if face%2 else -1)<0
                reversed_nodes+=int(inward.sum().cpu())
                target_u[:,mask]=torch.where(inward[None],self.velocity[face],u[:,mask])
                target_rho[:,mask]=torch.where(inward[None],rho[:,mask],torch.full_like(rho[:,mask],self.rho[face]))
        # Impose every incident symmetry plane, including shared slip/slip edges.
        # Even reflection removes normal momentum and normal/tangential stress.
        for axis, mask, reflection in self.slip_projections:
            target_u[axis,mask]=0
            neq[:,mask]=.5*(neq[:,mask]+neq[reflection][:,mask])
        values=f.equilibrium(f,target_rho,target_u)+neq
        # Match prescribed/extrapolated moments after FP32 equilibrium evaluation.
        drho=target_rho[0]-values.sum(0)
        dm=target_rho*target_u-torch.einsum('qd,qn->dn',f.torch_stencil.e,values)
        values+=f.torch_stencil.w[:,None]*(drho[None]+torch.einsum('qd,dn->qn',f.torch_stencil.e,dm)/f.stencil.cs**2)
        old=f.f.reshape(f.stencil.q,-1)[:,self.ix]
        delta=(values-old).sum()
        f.f.reshape(f.stencil.q,-1)[:,self.ix]=values
        self.report.update(reconstruction_mass_lu=float(delta.cpu()), open_incoming_nodes=reversed_nodes,
                           conservation_claim=False, method_note='full-node NEE; open sign switch is approximate and may reflect disturbances')
