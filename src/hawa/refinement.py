"""Experimental two-level, 2:1 BGK coupling with a fixed rectangular patch.

Cubic reconstruction and filtered nonequilibrium restriction follow Lagrava
et al., JCP 231 (2012), doi:10.1016/j.jcp.2012.03.015. This is a node-based
coupling, not a conservative finite-volume refluxing method. The plugin exposes it as experimental; validate each geometry and grid.
"""
import numpy as np
import torch


class RefinedStepper:
    def __init__(self, coarse, fine, lower, upper):
        self.coarse=coarse;self.fine=fine
        self.lower=tuple(lower);self.upper=tuple(upper)
        c=coarse.flow;f=fine.flow;self.d=c.stencil.d
        if len(lower)!=self.d or len(upper)!=self.d:raise ValueError('Patch dimension mismatch')
        if c.stencil.q!=f.stencil.q:raise ValueError('Matching stencils required')
        if any(type(x) is not int for x in (*lower,*upper)):raise ValueError('Patch corners must be integer coarse indices')
        if any(lo<2 or hi>n-3 or hi-lo<4 for lo,hi,n in zip(lower,upper,c.resolution)):raise ValueError('Patch needs cubic-stencil clearance and at least four coarse intervals')
        if tuple(f.resolution)!=tuple(2*(b-a)+1 for a,b in zip(lower,upper)):raise ValueError('Fine patch resolution must be 2*(upper-lower)+1')
        if type(coarse.collision).__name__!='BGKCollision' or type(fine.collision).__name__!='BGKCollision':raise ValueError('Refinement currently supports BGK only')
        tc=float(coarse.collision.tau);tf=float(fine.collision.tau)
        if abs(tf-(2*tc-.5))>1e-6:raise ValueError('Fine relaxation must equal 2*tau_coarse - 0.5')
        self.scale=tf/(2*tc)
        self.maps=[]
        for a,b in zip(lower,upper):
            x=np.arange(2*(b-a)+1)/2+a;k=np.floor(x).astype(int);t=x-k
            weights=np.stack((-t*(t-1)*(t-2)/6,(t+1)*(t-1)*(t-2)/2,-(t+1)*t*(t-2)/2,(t+1)*t*(t-1)/6))
            self.maps.append((torch.tensor(k[None,:]+np.arange(-1,3)[:,None],device=c.context.device,dtype=torch.long),c.context.convert_to_tensor(weights)))
        mask=np.zeros(f.resolution,bool)
        for axis in range(self.d):
            for side in (0,-1):
                ix=[slice(None)]*self.d;ix[axis]=side;mask[tuple(ix)]=True
        self.boundary=torch.tensor(mask,device=f.context.device)
        if hasattr(f,'solid') and bool(f.solid[self.boundary].any().cpu()):raise ValueError('Refinement interface must stay in fluid')
        self.c_slice=(slice(None),)+tuple(slice(a+1,b) for a,b in zip(lower,upper))
        self.f_slice=(slice(None),)+tuple(slice(2,-2,2) for _ in lower)

    def interpolate(self,value):
        for axis,(indices,weights) in enumerate(self.maps,1):
            shape=[1]*value.ndim;shape[axis]=indices.shape[1]
            value=sum(torch.index_select(value,axis,indices[j])*weights[j].reshape(shape) for j in range(4))
        return value

    @staticmethod
    def equilibrium(flow,populations):
        rho=populations.sum(0,keepdim=True)
        u=torch.einsum('qd,q...->d...',flow.torch_stencil.e,populations)/rho
        return flow.equilibrium(flow,rho,u)

    def inject(self,coarse):
        f=self.fine.flow;value=self.interpolate(coarse);eq=self.equilibrium(f,value)
        value=eq+self.scale*(value-eq)
        f.f[:,self.boundary]=value[:,self.boundary]

    def restrict(self):
        f=self.fine.flow;c=self.coarse.flow
        eq=self.equilibrium(f,f.f);neq=f.f-eq
        filtered=sum(torch.roll(neq,tuple(int(x) for x in e),tuple(range(1,self.d+1))) for e in f.stencil.e)/f.stencil.q
        c.f[self.c_slice]=(eq+filtered/self.scale)[self.f_slice]

    @torch.no_grad()
    def __call__(self,steps,checkpoint=lambda n:None):
        for _ in range(steps):
            checkpoint(self.coarse.flow.i)
            old=self.coarse.flow.f.clone()
            self.coarse(1)
            new=self.coarse.flow.f
            self.fine(1);self.inject((old+new)*.5)
            self.fine(1);self.inject(new)
            self.restrict()

    def composite_mass(self):
        c=self.coarse.flow;f=self.fine.flow
        def integral(rho):
            for axis in range(rho.ndim):
                weight=torch.ones(rho.shape[axis],device=rho.device,dtype=rho.dtype);weight[0]=weight[-1]=.5
                shape=[1]*rho.ndim;shape[axis]=-1;rho=rho*weight.reshape(shape)
            return rho.sum()
        region=tuple(slice(a,b+1) for a,b in zip(self.lower,self.upper))
        return c.rho().sum()-integral(c.rho()[0][region])+integral(f.rho()[0])/2**self.d


def run_refined(request,checkpoint):
    """Run a fixed two-level physical case and return independent field frames."""
    import lettuce as lt
    from .plugin import Session,WindFlow,check_case
    from .fields import store
    coarse_spec=request['case'];fine_spec=request['fine_case'];steps=request.get('steps',200)
    if type(steps) is not int or not 1<=steps<=10000:raise ValueError('Refined steps must be 1..10000')
    if coarse_spec.get('collision')!='bgk' or fine_spec.get('collision')!='bgk':raise ValueError('Select BGK in both refinement cases')
    if coarse_spec.get('wall_links') or fine_spec.get('wall_links'):raise ValueError('Refinement currently uses voxel walls; disable curved walls')
    coarse_check=check_case(coarse_spec);fine_check=check_case(fine_spec)
    if coarse_check['estimated_peak_mb']+fine_check['estimated_peak_mb']>coarse_spec.get('memory_limit_mb',1024):raise ValueError('Combined coarse/fine memory exceeds budget')
    lower=fine_spec['refinement_lower'];upper=fine_spec['refinement_upper']
    if not np.isclose(fine_spec['dx']*2,coarse_spec['dx']):raise ValueError('Fine cell size must be half the coarse size')
    for key in ('speed','viscosity','density','mach'):
        if coarse_spec.get(key)!=fine_spec.get(key):raise ValueError('Both grids need identical physical conditions')
    if coarse_spec.get('basis')!=fine_spec.get('basis'):raise ValueError('Grid axes must match')
    basis=np.asarray(coarse_spec.get('basis',np.eye(3)),float)
    expected=np.asarray(coarse_spec.get('origin',[0,0,0]))+np.asarray(lower)@basis*coarse_spec.get('spacing',coarse_spec['dx'])
    if not np.allclose(expected,fine_spec.get('origin',[0,0,0]),atol=1e-7):raise ValueError('Fine grid origin does not match its parent patch')
    checkpoint(0)
    coarse=Session(coarse_spec,request.get('device','auto'))
    class PatchFlow(WindFlow):
        @property
        def post_boundaries(self):return [lt.BounceBackBoundary(self.solid)]
    fine=PatchFlow(coarse.flow.context,fine_spec)
    fine_solver=lt.Simulation(fine,lt.BGKCollision(fine.units.relaxation_parameter_lu),[])
    coupled=RefinedStepper(coarse.solver,fine_solver,lower,upper)
    # No wall or unresolved geometry may touch the cubic interpolation stencil.
    mask=coarse.flow.solid.cpu().numpy();halo=mask[tuple(slice(a-1,b+2) for a,b in zip(lower,upper))].copy()
    halo[tuple(slice(3,-3) for _ in lower)]=False
    if halo.any():raise ValueError('Move the refinement interface at least two coarse cells away from solids')
    initial=float(coupled.composite_mass().cpu())
    while coarse.flow.i<steps:
        coupled(min(5,steps-coarse.flow.i),checkpoint)
        coarse.backend.synchronize()
        for flow in (coarse.flow,fine):
            if not bool(torch.isfinite(flow.f).all().cpu()) or not bool((flow.rho()>0).all().cpu()):raise RuntimeError('Refined simulation became unstable')
    checkpoint(steps)
    def frame(flow,spec,covered=False):
        arrays={'velocity':flow.u_pu.detach().cpu().numpy().copy(),'pressure':flow.p_pu[0].detach().cpu().numpy().copy(),
                'density':flow.rho_pu[0].detach().cpu().numpy().copy(),'solid':flow.solid.detach().cpu().numpy().copy()}
        if covered:arrays['solid'][tuple(slice(a+1,b) for a,b in zip(lower,upper))]=True
        return store(arrays,{'iteration':flow.i,'time':float(flow.units.convert_time_to_pu(flow.i)),
                            'case':{**spec,'physical_dx':float(flow.units.convert_length_to_pu(1))},'mean':False,'samples':0})
    return {'coarse_frame':frame(coarse.flow,coarse_spec,True),'fine_frame':frame(fine,fine_spec),
            'steps':steps,'backend':coarse.backend.info(),'relative_mass_change':float(coupled.composite_mass().cpu())/initial-1,
            'report':'Experimental static 2:1 BGK coupling. Fine grid takes two steps per coarse step. Open-domain mass change includes inlet/outlet flux. No automatic moving refinement.'}
