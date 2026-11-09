"""AIJ Case I mean-flow comparison. Targets declared before runs; no tuning of limits.

Measurement data: Kondo, Mutou, Hori et al., Zenodo 15430019, CC BY 4.0.
H=0.1 m, U_H=1.7 m/s, nu=1.5e-5 m2/s. No concentration calculation.
"""
import argparse,csv,json,time,sys
from pathlib import Path
import numpy as np
from hawa.plugin import Session
from hawa.boundary_series import sample_parent
from hawa.neutral import MODEL

ROOT=Path(__file__).resolve().parents[1]

def measurements():
    root=ROOT/'tests/reference_data/aij-case-i'
    def rows(path):
        with path.open(encoding='utf-8-sig',newline='') as f:
            return np.array([list(map(float,r)) for r in list(csv.reader(f))[1:] if r and r[0].strip() and r[0][0].isdigit() or r and r[0].startswith('-')])
    return rows(root/'AF_caseI.csv'),rows(root/'RS-w_caseI.csv')


def case(cells,device='cpu'):
    H=.1;dx=H/cells;n=[15*cells,8*cells,8*cells]
    spec=dict(shape=n,dx=dx,spacing=dx,origin=[-.5+dx/2,-.4+dx/2,dx/2],speed=1.7,viscosity=1.5e-5,density=1.225,mach=.05,memory_limit_mb=4096,
        collision=MODEL,boundaries=['periodic']*4+['wall','slip'],neutral_precursor=dict(schema=1,experimental=True,mode='external',reference_height_m=.1,roughness_length_m=.0000455,perturbation_fraction=.02,wall_sample_index=0,wall_filter_seconds=.01),boundary_method='shifted-links-v1')
    names=('x-','x+','y-','y+','z-','z+');kinds=('velocity','open','periodic','periodic','wall','open')
    spec['boundary_set']=dict(schema=1,patches=[dict(id=f,face=f,condition=dict(type=k,velocity=[1.7 if i in (0,5) else 0,0,0],pressure_pa=0.,profile='neutral' if i in (0,1,5) else 'uniform')) for i,(f,k) in enumerate(zip(names,kinds))])
    xyz=np.indices(tuple(np.array(n)+2)).reshape(3,-1).T-1;world=np.asarray(spec['origin'])+xyz*dx
    solid=(abs(world[:,0])<.05)&(abs(world[:,1])<.05)&(world[:,2]<.1)
    halo=solid.reshape(tuple(np.array(n)+2));spec['solid']=np.flatnonzero(halo[1:-1,1:-1,1:-1]).tolist();spec['solid_halo']=np.flatnonzero(halo).tolist()
    return spec


def main():
    p=argparse.ArgumentParser();p.add_argument('--cells',type=int,default=4);p.add_argument('--steps',type=int,default=40000);p.add_argument('--device',default='cpu');p.add_argument('--top',choices=('open','slip'),default='open');p.add_argument('--mach',type=float,default=.05);p.add_argument('--inflow',choices=('measured','log'),default='measured');p.add_argument('--backflow-mode',choices=('velocity','pressure'),default='pressure');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);approach,obs=measurements();spec=case(a.cells);spec['mach']=a.mach
    for patch in spec['boundary_set']['patches']:
        if patch['condition']['type']=='open':patch['condition']['backflow_mode']=a.backflow_mode
    if a.top=='slip':spec['boundary_set']['patches'][5]['condition']=dict(type='slip',velocity=[0,0,0])
    s=Session(spec,a.device)
    if a.inflow=='measured':
        import torch
        def measured(height):
            profile=np.interp(height,approach[:,0],approach[:,1])
            below=height<approach[0,0];profile[below]=approach[0,1]*np.log1p(height[below]/.0000455)/np.log1p(approach[0,0]/.0000455)
            return profile
        # Verification fixture: impose the published tabulated mean at exactly
        # the same boundary operator used in production. No turbulence claim.
        f=s.flow;u=f.u();u[0]=f.context.convert_to_tensor(f.units.convert_velocity_to_lu(measured((np.arange(spec['shape'][2])+.5)*spec['dx'])))[None,None,:];u[:,f.solid]=0;f.f=f.equilibrium(f,u=u)
        bc=s.solver.external_links;xyz=np.array(np.unravel_index(bc.ix.cpu().numpy(),spec['shape']))
        values=measured((xyz[2]+.5)*spec['dx']);sign=np.sign(bc.velocity[0].cpu().numpy());bc.velocity[0]=f.context.convert_to_tensor(f.units.convert_velocity_to_lu(values*sign))
    start=time.monotonic();samples=[];history=[]
    # Published locations inside/on the model are outside the fluid observable.
    inside=(abs(obs[:,0])<.05-1e-10)&(abs(obs[:,1])<.05-1e-10)&(obs[:,2]<.1-1e-10)
    points=obs[~inside,:3];reference=obs[~inside,3:6];ks=obs[~inside,6]
    for _ in range(0,a.steps,100):
        s.advance(min(100,a.steps-s.flow.i));fields=s.fields()
        velocity,pressure,sampling=sample_parent(fields,spec,points,np.zeros(len(points),bool))
        history.append(dict(step=s.flow.i,time=float(s.flow.units.convert_time_to_pu(s.flow.i)),max_mach=s.quality['max_lattice_mach'],density_deviation=s.quality['max_density_deviation'],max_speed_index=list(map(int,np.unravel_index(np.linalg.norm(fields['velocity'],axis=0).argmax(),spec['shape']))),mean_density=float(fields['density'].mean()),mass_budget=s.solver.external_links.report['mass_budget_residual_lu']))
        if s.flow.i>a.steps//2:samples.append(velocity)
        if s.flow.i%1000==0:
            print(s.flow.i,'seconds',round(time.monotonic()-start,2),'Mach',s.quality['max_lattice_mach'],flush=True)
            (a.output/'progress.json').write_text(json.dumps(dict(steps=s.flow.i,quality=s.quality,wall_seconds=time.monotonic()-start)))
        if s.flow.i%5000==0 or s.quality['status']=='rejected':
            np.savez_compressed(a.output/'latest-state.npz',populations=s.flow.f.detach().cpu().numpy(),iteration=s.flow.i,velocity=fields['velocity'],pressure=fields['pressure'],solid=fields['solid'])
        if s.quality['status']=='rejected':break
    if len(samples)<4:
        report=dict(case=spec,steps=s.flow.i,quality=s.quality,passed=False,reason='Numerical envelope failed before sufficient averaging',history=history)
        (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(report['reason'],s.flow.i,s.quality['max_lattice_mach']);return 1
    samples=np.asarray(samples);mean=samples.mean(0);rms=np.std(samples,axis=0);tke=.5*np.sum(rms*rms,axis=1)
    hit=np.abs(mean-reference)<=np.maximum(.25*np.abs(reference),.05*1.7)
    half=len(samples)//2;stationarity=np.linalg.norm(samples[half:].mean(0)-samples[:half].mean(0))/np.linalg.norm(mean)
    report=dict(case=spec,device=a.device,steps=s.flow.i,physical_time=float(s.flow.units.convert_time_to_pu(s.flow.i)),wall_seconds=time.monotonic()-start,points=len(points),excluded_inside_model=int(inside.sum()),
        hit_rate_components=hit.mean(0).tolist(),mean_velocity_relative_l2=float(np.linalg.norm(mean-reference)/np.linalg.norm(reference)),stationarity_change=float(stationarity),
        tke_relative_l2=float(np.linalg.norm(tke-ks)/np.linalg.norm(ks)),quality=s.quality,sampling=sampling,
        thresholds=dict(streamwise_hit_rate_min=.66,relative_error_or_absolute=[.25,.085],stationarity_max=.05),
        passed=bool(hit[:,0].mean()>=.66 and stationarity<=.05 and s.quality['status']=='within-tested-envelope'),
        inlet=a.inflow+' mean profile; deterministic initial perturbation; no sustained measured turbulent inlet',approach_data='tests/reference_data/aij-case-i/AF_caseI.csv')
    np.savez_compressed(a.output/'samples.npz',points=points,reference=reference,reference_tke=ks,samples=samples,mean=mean,rms=rms)
    (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');(a.output/'history.json').write_text(json.dumps(history));print({k:v for k,v in report.items() if k not in ('case','quality')})
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
