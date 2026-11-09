"""Experimental rough-floor precursor and external flow; shifted D3Q19 storage.

g=f-w is a distinct checkpoint representation. Numerical qualification and
atmospheric accuracy are separate from finite-state diagnostics.
"""
import math
import numpy as np
import torch
import lettuce as lt
from .atmosphere import neutral_profile, scaling_report, _positive

MODEL = 'shifted-regularized-sgs-v1'


def validate(spec):
    c = spec.get('neutral_precursor')
    if not isinstance(c, dict) or c.get('schema') != 1 or c.get('experimental') is not True:
        raise ValueError('Neutral precursor requires schema 1 and explicit experimental=true')
    if spec.get('collision') != MODEL:
        raise ValueError('Neutral precursor requires '+MODEL)
    external=c.get('mode','precursor')=='external'
    if c.get('mode','precursor') not in ('precursor','external'):raise ValueError('Unknown neutral mode')
    for key in (('wall_links','moving_bodies','refinement_lower') if external else ('solid','solid_halo','wall_links','moving_bodies','boundary_field','boundary_set','refinement_lower')):
        if spec.get(key): raise ValueError('Neutral precursor does not support '+key)
    if external and spec.get('boundary_field') and spec['boundary_field'].get('schema')!='hawa-boundary-series-2':raise ValueError('Neutral external flow requires BoundarySeries v2; recapture the parent for this child')
    unknown = set(c)-{'schema','experimental','reference_height_m','roughness_length_m','direction','smagorinsky_constant','perturbation_fraction','wall_sample_index','wall_filter_seconds','mode'}
    if unknown: raise ValueError('Unknown neutral parameters: '+', '.join(sorted(unknown)))
    if not external and spec.get('boundaries') != ['periodic']*4+['wall','slip']:
        raise ValueError('Neutral precursor requires periodic X/Y, rough Z- and slip Z+ topology')
    z0 = _positive(c.get('roughness_length_m'), 'roughness length')
    href = _positive(c.get('reference_height_m'), 'reference height')
    dx = spec['dx']; height = spec['shape'][2]*dx
    if not z0 < dx/2 or not z0 < href < height:
        raise ValueError('Require z0 < dx/2 and z0 < reference height < channel height')
    from .roughness import grid as roughness_grid
    roughness_grid(spec)
    direction = np.asarray(c.get('direction', [1.,0.,0.]), dtype=float)
    if direction.shape != (3,) or not np.isfinite(direction).all() or abs(direction[2])>1e-12 or not np.isclose(np.linalg.norm(direction),1.,rtol=0,atol=1e-10):
        raise ValueError('Neutral direction must be a horizontal unit vector')
    cs = float(c.get('smagorinsky_constant', .17))
    amplitude = float(c.get('perturbation_fraction', .02))
    if not math.isfinite(cs) or not 0 <= cs <= .3 or not math.isfinite(amplitude) or not 0 <= amplitude <= .1:
        raise ValueError('Require 0 <= Cs <= 0.3 and perturbation fraction <= 0.1')
    sample=c.get('wall_sample_index',0); filter_seconds=c.get('wall_filter_seconds',0.)
    if type(sample) is not int or not 0 <= sample < spec['shape'][2]-1:
        raise ValueError('Wall sample index must be an interior Z lattice index')
    if not isinstance(filter_seconds,(int,float)) or not math.isfinite(filter_seconds) or filter_seconds<0:
        raise ValueError('Wall filter seconds must be finite and nonnegative')
    top_speed = np.linalg.norm(neutral_profile(height, direction*spec['speed'], href, z0))
    if spec.get('mach',.05)*top_speed/spec['speed']*(1+amplitude*(2+spec['shape'][1]/spec['shape'][0])) > .1:
        raise ValueError('Neutral initial profile exceeds conservative lattice Mach 0.10 budget')
    return dict(method=MODEL, storage='g=f-w', experimental=True,
                wall_location='half cell below/above first/last Z lattice plane',
                height_m=height, atmospheric_validation=False,
                limits=('external flow; stationary halo-classified bodies, planar rough floor, velocity/open faces; BoundarySeries v2 supported; no curved links or refinement'
                        if external else 'periodic horizontal precursor; planar rough floor and free-slip lid; no buildings or open boundaries'))


class ShiftedEquilibrium(lt.Equilibrium):
    def __call__(self, flow, rho=None, u=None, delta=None):
        if delta is None:delta = flow.f.sum(0,keepdim=True) if rho is None else rho-1
        rho = 1+delta
        u = flow.u() if u is None else u
        eu = torch.einsum('qd,d...->q...', flow.torch_stencil.e, u)
        uu = (u*u).sum(0)
        return torch.einsum('q,q...->q...', flow.torch_stencil.w,
                            delta+rho*(3*eu+4.5*eu*eu-1.5*uu))
    def native_available(self): return False
    def native_generator(self, index): raise NotImplementedError


class ShiftedRegularizedSGS(lt.Collision):
    def __init__(self, margin, cs=.17, acceleration=(0.,0.,0.)):
        self.margin = _positive(margin, 'relaxation margin')
        self.cs = float(cs)
        if not math.isfinite(self.cs) or not 0 <= self.cs <= .3: raise ValueError('Invalid Cs')
        self.acceleration = acceleration
        self.Q = None

    def __call__(self, flow):
        rho=flow.rho(); u=flow.u(); eq=flow.equilibrium(flow, u=u)
        pi=flow.shear_tensor(flow.f-eq)
        magnitude=torch.sqrt(2*(pi*pi).sum((0,1)))/(2*rho[0]*flow.stencil.cs**2)
        # Rationalised quadratic root: never subtract two nearly equal taus.
        tau0=.5+self.margin
        b=12*self.cs**2*magnitude
        delta=self.margin+.5*b/(torch.sqrt(tau0*tau0+b)+tau0)
        self.relaxation_margin=delta
        if self.Q is None:
            e=flow.torch_stencil.e
            self.Q=torch.einsum('qa,qb->qab', e,e)-torch.eye(3,device=e.device,dtype=e.dtype)[None]/3
        neq=torch.einsum('q,qab,ab...->q...', flow.torch_stencil.w,self.Q,pi)*4.5
        # 1-1/tau = -1 + 4*delta/(1+2*delta). Keep small term separate.
        result=(eq-neq)+(4*delta/(1+2*delta))*neq
        a=flow.context.convert_to_tensor(self.acceleration)[:,None,None,None]
        # Exact-difference forcing, using the same density deviation in both eqs.
        result += flow.equilibrium(flow,u=u+a)-eq
        return result

    def native_available(self): return False
    def native_generator(self, index): raise NotImplementedError


def make(spec, context):
    from .plugin import WindFlow
    validate(spec)
    c=spec['neutral_precursor']
    imported=None
    if spec.get('boundary_field'):
        from .boundary_series import read,validate_attachment
        imported,metadata=read(spec['boundary_field']['path'],spec['boundary_field']['sha256'])
        validate_attachment(spec,imported,metadata)
    ustar=.41*spec['speed']/math.log1p(c['reference_height_m']/c['roughness_length_m'])
    accel=np.asarray(c.get('direction',[1.,0.,0.]))*ustar**2/(spec['shape'][2]*spec['dx'])
    if c.get('mode')=='external':accel*=0
    dt=spec.get('mach',.05)*spec['dx']/(math.sqrt(3)*spec['speed'])
    class NeutralFlow(WindFlow):
        def __init__(self):
            # WindFlow initialization calls our initial_pu; change equilibrium
            # afterwards and reinitialize to avoid reinterpreting absolute f.
            super().__init__(context,spec)
            self.equilibrium=ShiftedEquilibrium()
            self.initialize()
        def rho(self, f=None):
            return 1+(self.f if f is None else f).sum(0,keepdim=True)
        @property
        def p_pu(self):
            # Avoid subtracting one from a rounded density in pressure conversion.
            scale=self.units.convert_density_lu_to_pressure_pu(2.)-self.units.convert_density_lu_to_pressure_pu(1.)
            return self.f.sum(0,keepdim=True)*scale
        @property
        def u_pu(self):
            correction=self.context.convert_to_tensor(accel*.5*dt)[:,None,None,None]
            return (self.units.convert_velocity_to_pu(self.u())+correction)*(~self.solid)[None]
        def initial_pu(self):
            if imported is not None:
                return self.context.convert_to_tensor(imported['initial_pressure'][None]),self.context.convert_to_tensor(imported['initial_velocity'])
            c=spec['neutral_precursor']; n=spec['shape']; dx=spec['dx']
            v=neutral_profile((np.arange(n[2])+.5)*dx,
                np.asarray(c.get('direction',[1.,0.,0.]))*spec['speed'],c['reference_height_m'],c['roughness_length_m'])
            u=self.context.convert_to_tensor(v.T[:,None,None,:]).expand(3,*n).clone()
            # Deterministic divergence-free horizontal perturbation, zero at lids.
            x=torch.arange(n[0],device=context.device,dtype=context.dtype)*2*math.pi/n[0]
            y=torch.arange(n[1],device=context.device,dtype=context.dtype)*2*math.pi/n[1]
            z=(torch.arange(n[2],device=context.device,dtype=context.dtype)+.5)*math.pi/n[2]
            amp=c.get('perturbation_fraction',.02)*spec['speed']
            u[0]+=amp*torch.sin(x)[:,None,None]*torch.cos(y)[None,:,None]*torch.sin(z)[None,None,:]
            u[1]-=amp*(n[1]/n[0])*torch.cos(x)[:,None,None]*torch.sin(y)[None,:,None]*torch.sin(z)[None,None,:]
            u-=self.context.convert_to_tensor(accel*.5*dt)[:,None,None,None]
            u[:,self.solid]=0
            return self.context.zero_tensor([1,*n]),u
        @property
        def post_boundaries(self): return []
    f=NeutralFlow(); c=spec['neutral_precursor']
    # Pressure-gradient forcing balances the reference rough-floor stress.
    ustar=.41*spec['speed']/math.log1p(c['reference_height_m']/c['roughness_length_m'])
    accel=np.asarray(c.get('direction',[1.,0.,0.]))*ustar**2/(spec['shape'][2]*spec['dx'])
    if c.get('mode')=='external':accel*=0
    accel_lu=f.units.convert_acceleration_to_lu(accel)
    model=ShiftedRegularizedSGS(scaling_report(spec['dx'],spec['speed'],spec['viscosity'],spec.get('mach',.05))['tau_minus_half'],c.get('smagorinsky_constant',.17),accel_lu)
    if imported is not None:
        pressure=f.context.convert_to_tensor(imported['initial_pressure'][None])
        velocity=f.units.convert_velocity_to_lu(f.context.convert_to_tensor(imported['initial_velocity']))
        f.f=f.equilibrium(f,u=velocity,delta=f.units.convert_pressure_to_lu(pressure)/f.stencil.cs**2)
        # Chapman-Enskog strain reconstruction supplies the resolved initial stress.
        # Its zeroth/first moments are zero; mapped density and momentum survive.
        if 'initial_strain_rate' in imported:
            strain=f.context.convert_to_tensor(imported['initial_strain_rate'])*float(f.units.convert_time_to_pu(1))
        else:
            u=f.u();gradient=torch.stack([torch.stack(torch.gradient(u[i],dim=(0,1,2),edge_order=2)) for i in range(3)])
            strain=(gradient+gradient.transpose(0,1))*.5
        magnitude=torch.sqrt(2*(strain*strain).sum((0,1)))
        tau=.5+model.margin+3*model.cs**2*magnitude
        pi=-(2/3)*f.rho()*tau*strain
        e=f.torch_stencil.e;Q=torch.einsum('qa,qb->qab',e,e)-torch.eye(3,device=e.device,dtype=e.dtype)[None]/3
        f.f+=4.5*torch.einsum('q,qab,ab...->q...',f.torch_stencil.w,Q,pi)
        f.f[:,f.solid]=0
    solver=lt.Simulation(f,model,[])
    wall=RoughFloor(solver,c['roughness_length_m'])
    if imported is not None and 'initial_wall_velocity' in imported:
        wall.filtered=f.units.convert_velocity_to_lu(f.context.convert_to_tensor(imported['initial_wall_velocity']))
    from .step import coordinator
    coordinator(solver).register('rough-floor',after_collision=wall.capture,after_stream=wall.apply)
    solver.rough_floor=wall
    if c.get('mode')=='external':
        from .neutral_external import compile_links,ExternalLinks
        plan=compile_links(spec)
        wall.link_masks=[torch.tensor(m,device=f.context.device) for m in plan['wall_masks']]
        solver.external_links=ExternalLinks(solver,plan)
        coordinator(solver).register('external-links',after_collision=solver.external_links.capture,after_stream=solver.external_links.apply)
    return f,solver


class RoughFloor:
    """Halfway specular reflection with prescribed tangential momentum deficit.

    Outgoing populations are shifted in the tangent directions before reflection.
    Diagonal corrections impose tangential impulse. At external corners the
    normal population balances mass when only one diagonal is available.
    """
    def __init__(self,solver,z0):
        self.f=solver.flow; f=self.f
        c=f.spec['neutral_precursor']; self.sample=c.get('wall_sample_index',0)
        from .roughness import grid as roughness_grid
        self.factor=f.context.convert_to_tensor(.41/np.log1p((self.sample+.5)*f.spec['dx']/roughness_grid(f.spec)))
        seconds=c.get('wall_filter_seconds',0.)
        self.alpha=-math.expm1(-float(f.units.convert_time_to_pu(1))/seconds) if seconds else 1.
        self.filtered=None
        self.e=np.asarray(f.stencil.e,dtype=int)
        self.report={}
    def capture(self):
        f=self.f
        self.saved=[f.f[:,:,:,0].clone(),f.f[:,:,:,-1].clone()]
        u=f.units.convert_velocity_to_lu(f.u_pu[:,:,:,self.sample]).clone(); u[2]=0
        if self.filtered is None: self.filtered=u.clone()
        else: self.filtered.add_(self.alpha*(u-self.filtered))
        u=self.filtered
        rho=f.rho()[0,:,:,0]
        self.impulse=-rho[None]*self.factor**2*torch.linalg.vector_norm(u,dim=0)[None]*u
    def apply(self):
        f=self.f
        corrections={}
        if hasattr(self,'link_masks'):
            masks=self.link_masks[0]
            normal=int(np.flatnonzero(np.all(self.e==[0,0,1],axis=1))[0])
            corrections[normal]=torch.zeros_like(self.impulse[0])
            for axis in (0,1):
                diagonal=[q for q,e in enumerate(self.e) if e[2]==1 and abs(e[axis])==1]
                available=sum(masks[q].to(f.context.dtype) for q in diagonal)
                for q in diagonal:
                    value=self.e[q,axis]*self.impulse[axis]*masks[q]*masks[normal]/available.clamp_min(1)
                    corrections[q]=value
                    corrections[normal]-=value
            applied=torch.zeros_like(self.impulse)
            for q,v in corrections.items():
                for a in (0,1):applied[a]+=int(self.e[q,a])*v
        else:applied=self.impulse
        for side,sign in ((0,-1),(-1,1)):
            source=self.saved[0 if side==0 else 1]
            for q,e in enumerate(self.e):
                if e[2]!=sign: continue
                reflect=e.copy();reflect[2]*=-1
                r=int(np.flatnonzero(np.all(self.e==reflect,axis=1))[0])
                value=torch.roll(source[q],(int(e[0]),int(e[1])),(0,1))
                if side==0:
                    # D3Q19: two incoming diagonals per tangent, +/-1.
                    if hasattr(self,'link_masks'):value=value+corrections.get(r,0)
                    else:value=value+.5*(e[0]*self.impulse[0]+e[1]*self.impulse[1])
                if hasattr(self,'link_masks'):
                    mask=self.link_masks[0 if side==0 else 1][r]
                    f.f[r,:,:,side]=torch.where(mask,value,f.f[r,:,:,side])
                else:f.f[r,:,:,side]=value
        exchanges=[]
        for side,sign,saved in ((0,-1,self.saved[0]),(-1,1,self.saved[1])):
            outgoing=[q for q,e in enumerate(self.e) if e[2]==sign]
            incoming=[q for q,e in enumerate(self.e) if e[2]==-sign]
            exchanges.append(float((f.f[incoming,:,:,side].sum()-saved[outgoing].sum()).detach().cpu()))
        density_ref=f.spec.get('density',1.225)
        velocity_scale=float(f.units.convert_velocity_to_pu(1.))
        traction=applied*density_ref*velocity_scale**2
        self.report={'method':'halfway-specular-stress-v1',
                     'mean_traction_on_fluid_pa':traction.mean((1,2)).detach().cpu().tolist(),
                     'wall_impulse_lu':applied.sum((1,2)).detach().cpu().tolist(),
                     'wall_mass_exchange_lu':None if hasattr(self,'link_masks') else exchanges,
                     'sample_height_m':(self.sample+.5)*f.spec['dx'],
                     'atmospheric_validation':False}
    def reset(self):
        self.report={}
        self.filtered=None
