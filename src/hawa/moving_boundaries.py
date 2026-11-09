"""Experimental prescribed rigid bodies on a uniform D3Q19 BGK lattice.

Interpolated moving bounce-back with neighbour equilibrium/nonequilibrium
refill. All spatial arrays remain on the selected tensor device. Body poses
are evaluated at step endpoints; links use endpoint wall velocities.
"""
from collections import deque
import itertools
import numpy as np
import torch
from .motion import pose


def _rotate(vector, matrix):
    """Small geometry transforms with the same summation order on every device."""
    return ((vector[..., 0, None] * matrix[0] + vector[..., 1, None] * matrix[1])
            + vector[..., 2, None] * matrix[2])


def _radial_distance(vector, radius):
    """Signed radial distance without subtracting two nearly equal square roots.

    The numerator determines the inside/outside predicate. Explicitly ordered
    squares avoid backend-dependent norm reductions at a surface lattice site;
    rationalization keeps sqrt rounding from flipping that predicate. The same
    signed distance is used for classification and interpolated wall links.
    """
    squared = vector[..., 0] * vector[..., 0]
    for axis in range(1, vector.shape[-1]):
        squared = squared + vector[..., axis] * vector[..., axis]
    radius = vector.new_tensor(radius)
    return (squared - radius * radius) / (torch.sqrt(squared) + radius)


def moving_reflection(incoming, opposite, back, q, rho, wall_dot_e, weight):
    """Bouzidi linear interpolation plus wall velocity in lattice units."""
    return torch.where(q<.5,2*q*incoming+(1-2*q)*back-6*weight*rho*wall_dot_e,
                       incoming/(2*q)+(1-1/(2*q))*opposite-3*weight*rho*wall_dot_e/q)


class MovingBoundaries:
    def __init__(self, simulation, spec):
        self.sim=simulation;self.flow=simulation.flow;self.spec=spec;self.bodies=spec['moving_bodies']
        self.dx=spec['dx'];self.dt=float(self.flow.units.convert_time_to_pu(1))
        self.tensor=self.flow.context.convert_to_tensor
        self.points=torch.stack(self.flow.grid,-1)
        self.border=torch.zeros_like(self.flow.solid)
        for axis in range(3):
            self.border.narrow(axis,0,2).fill_(True)
            self.border.narrow(axis,self.border.shape[axis]-2,2).fill_(True)
        self.static=self.flow.solid.clone();self.base_mask=simulation.no_collision_mask.clone()
        self.boundary_index=simulation.collision_index+len(simulation.post_boundaries)
        self.sdfs={b['id']:self.tensor(b['geometry']['values']).reshape(b['geometry']['shape']) for b in self.bodies if b['geometry']['type']=='sdf'}
        self.history=deque(maxlen=10000);self.transition_mass=0.;self.poses=[]
        self.update(0,False)
        simulation._collide_and_stream=self.step

    def distance(self,body,state):
        g=body['geometry']
        if g['type']=='sphere':
            center=_rotate(self.tensor(g['center'])-self.tensor(body['pivot']),self.tensor(state['rotation']).T)+self.tensor(state['pivot'])
            return _radial_distance(self.points-center,g['radius'])
        p=_rotate(self.points-self.tensor(state['pivot']),self.tensor(state['rotation']))+self.tensor(body['pivot'])
        if g['type']=='cylinder':
            p=p-self.tensor(g['center']);a=_radial_distance(p[...,:2],g['radius']);b=torch.abs(p[...,2])-g['length']/2
            return torch.sqrt(torch.clamp(a,min=0)**2+torch.clamp(b,min=0)**2)+torch.minimum(torch.maximum(a,b),torch.zeros_like(a))
        x=(p-self.tensor(g['origin']))/g['spacing'];grid=self.sdfs[body['id']];n=torch.tensor(g['shape'],device=x.device)
        valid=((x>=0)&(x<=n-1)).all(-1);lo=torch.floor(x).long();lo=torch.maximum(torch.minimum(lo,n-2),torch.zeros_like(lo));f=x-lo
        value=torch.zeros_like(x[...,0])
        for corner in itertools.product((0,1),repeat=3):
            w=torch.ones_like(value);indices=[]
            for a,c in enumerate(corner):w=w*(f[...,a] if c else 1-f[...,a]);indices.append(lo[...,a]+c)
            value=value+w*grid[tuple(indices)]
        # Outside the padded local volume there is no body. Avoid extrapolation.
        return torch.where(valid,value,torch.full_like(value,2*self.dx))

    def velocity(self,state,points):
        return self.tensor(state['velocity'])+torch.linalg.cross(self.tensor(state['omega']).expand_as(points),points-self.tensor(state['pivot']),dim=-1)

    def update(self,time,refill=True):
        flow=self.flow;old=flow.solid.clone();occupied=self.static.clone();self.poses=[pose(b,time) for b in self.bodies];self.distances=[];self.masks=[]
        for b,state in zip(self.bodies,self.poses):
            sdf=self.distance(b,state);mask=sdf<=0
            if not bool(mask.any().cpu()):raise ValueError('Moving body is unresolved or has left the domain')
            if bool((mask&self.border).any().cpu()):raise ValueError('Moving body needs two-cell clearance from every domain face')
            if bool((mask&occupied).any().cpu()):raise ValueError('Moving bodies overlap another body or stationary geometry')
            occupied|=mask;self.distances.append(sdf);self.masks.append(mask)
        self.impulses=[self.tensor([0.,0.,0.]) for _ in self.bodies];self.impulse_torques=[x.clone() for x in self.impulses]
        if refill:
            emerged=old&~occupied;covered=~old&occupied
            rho=flow.rho()
            # Average distributions from adjacent sites that remain fluid.
            donor=~old&~occupied;count=torch.zeros_like(rho);total=torch.zeros_like(flow.f)
            for a in range(3):
                for sign in (-1,1):
                    valid=torch.roll(donor,sign,a);count+=valid
                    total+=torch.roll(flow.f,sign,a+1)*valid
            if bool((emerged&(count[0]==0)).any().cpu()):raise ValueError('No fluid neighbour for newly exposed cell; refine geometry/time step')
            average=total/torch.clamp(count,min=1)
            before_mass=rho[0][~old].sum()
            for i,(mask,state) in enumerate(zip(self.masks,self.poses)):
                # Assign newly uncovered sites to their previous owner.
                was=self.previous_masks[i] if hasattr(self,'previous_masks') else mask
                removed=covered&mask;added=emerged&was
                wall=self.velocity(state,self.points)*self.dt/self.dx
                average_rho=average.sum(0,keepdim=True)
                average_u=torch.einsum('qd,q...->d...',flow.torch_stencil.e,average)/torch.clamp(average_rho,min=1e-12)
                # Refill at the moving-wall velocity with neighbour density and
                # non-equilibrium stress. Raw population averages can assign
                # an unrelated velocity to a cell exposed next to the wall.
                refill=flow.equilibrium(flow,average_rho,wall.movedim(-1,0))+average-flow.equilibrium(flow,average_rho,average_u)
                average[:,added]=refill[:,added]
                momentum=torch.einsum('qd,q...->...d',flow.torch_stencil.e,flow.f)
                new_momentum=torch.einsum('qd,q...->...d',flow.torch_stencil.e,average)
                momentum=momentum-rho[0][...,None]*wall
                new_momentum=new_momentum-average.sum(0)[...,None]*wall
                self.impulses[i]=momentum[removed].sum(0)-new_momentum[added].sum(0)
                arm=(self.points-self.tensor(state['pivot']))/self.dx
                self.impulse_torques[i]=(torch.linalg.cross(arm[removed],momentum[removed],dim=-1).sum(0)-torch.linalg.cross(arm[added],new_momentum[added],dim=-1).sum(0))
            flow.f[:,emerged]=average[:,emerged]
            # Solid reservoirs are initialized at local wall velocity, never streamed into a fluid link without correction.
            for mask,state in zip(self.masks,self.poses):
                wall=self.velocity(state,self.points).movedim(-1,0)*self.dt/self.dx
                solid_eq=flow.equilibrium(flow,rho,wall)
                flow.f[:,mask]=solid_eq[:,mask]
            self.transition_mass+=float((flow.rho()[0][~occupied].sum()-before_mass).cpu())
        flow.solid.copy_(occupied)
        self.sim.no_collision_mask.copy_(self.base_mask)
        self.sim.no_collision_mask[occupied]=self.boundary_index
        self.previous_masks=[m.clone() for m in self.masks]

    def step(self,*args):
        f=self.flow;self.update((f.i+1)*self.dt)
        self.sim._collide();post=f.f;rho=f.rho()[0];corrections=[];forces=[];torques=[];gap=torch.zeros((),dtype=torch.bool,device=f.context.device)
        for k,(sdf,mask,state) in enumerate(zip(self.distances,self.masks,self.poses)):
            force=self.impulses[k].clone();torque=self.impulse_torques[k].clone()
            for direction,e in enumerate(f.stencil.e):
                if direction==0:continue
                e=tuple(int(x) for x in e);op=int(f.stencil.opposite[direction])
                link=(~f.solid)&torch.roll(mask,tuple(-x for x in e),(0,1,2))
                ahead=torch.roll(sdf,tuple(-x for x in e),(0,1,2))
                q=torch.clamp(sdf[link]/(sdf[link]-ahead[link]),1e-4,1.)
                behind=torch.roll(f.solid,e,(0,1,2))[link]
                gap|=((q<.5)&behind).any()
                incoming=post[direction][link];opposite=post[op][link];back=torch.roll(post[direction],e,(0,1,2))[link]
                ev=self.tensor(e);position=self.points[link]+q[:,None]*ev*self.dx
                wall=self.velocity(state,position)*self.dt/self.dx
                dot=(wall*ev).sum(-1);w=float(f.stencil.w[direction])
                reflected=moving_reflection(incoming,opposite,back,q,rho[link],dot,w)
                transfer=(incoming+reflected)[:,None]*ev+(reflected-incoming)[:,None]*wall
                force+=transfer.sum(0);torque+=torch.linalg.cross((position-self.tensor(state['pivot']))/self.dx,transfer,dim=-1).sum(0)
                corrections.append((op,link,reflected))
            forces.append(force);torques.append(torque)
        if bool(gap.cpu()):raise ValueError('Moving wall has an unresolved narrow gap; refine the grid')
        self.sim._stream()
        for op,mask,value in corrections:f.f[op][mask]=value
        scale=self.spec.get('density',1.225)*self.dx**4/self.dt**2
        loads=[]
        for b,s,force,torque in zip(self.bodies,self.poses,forces,torques):
            force=force.cpu().numpy()*scale;torque=torque.cpu().numpy()*scale*self.dx
            loads.append(dict(id=b['id'],force=force.tolist(),torque=torque.tolist(),power=float(force@np.asarray(s['velocity'])+torque@np.asarray(s['omega']))))
        self.history.append(dict(time=(f.i+1)*self.dt,loads=loads))

    def metadata(self):
        return dict(schema=1,poses=self.poses,loads=self.history[-1]['loads'] if self.history else [],transition_mass_lu=self.transition_mass)

    def reset(self,iteration=0):
        self.history.clear();self.transition_mass=0.;self.update(iteration*self.dt,False)
