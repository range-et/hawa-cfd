"""Same-grid / refined offline nesting against the actual parent solution.

Thresholds: mean U relative L2 <=5%, fluctuation RMS <=10%, Cp RMSE <=0.1.
Small deterministic building experiment, not an atmospheric engineering benchmark.
"""
import argparse, copy, json, time
from pathlib import Path
import numpy as np
from hawa.plugin import Session
from hawa.recording import record, read_manifest
from hawa.fields import read_frame
from hawa.boundary_data import capture, geometry
from hawa.boundary_series import sample_parent
from hawa.neutral import MODEL


def case(shape, dx, origin, parent=False):
    s=dict(shape=shape,dx=dx,spacing=dx,origin=origin,speed=5.,viscosity=1.5e-5,density=1.225,mach=.05,
        collision=MODEL,boundaries=['periodic']*4+['wall','slip'],neutral_precursor=dict(schema=1,experimental=True,mode='external',reference_height_m=6.,roughness_length_m=.01,perturbation_fraction=.02,wall_sample_index=0,wall_filter_seconds=.1),boundary_method='shifted-links-v1')
    names=('x-','x+','y-','y+','z-','z+');kinds=('velocity','open','periodic','periodic','wall','slip') if parent else ('open','open','open','open','wall','open')
    s['boundary_set']=dict(schema=1,patches=[dict(id=f,face=f,condition=dict(type=k,velocity=[5. if parent and i==0 else 0,0,0],pressure_pa=0.,profile='neutral' if i in (0,1) else 'uniform',**({'backflow_mode':'pressure'} if k=='open' else {}))) for i,(f,k) in enumerate(zip(names,kinds))])
    n=np.array(shape);ix=np.indices(tuple(n+2)).reshape(3,-1).T-1;xyz=origin+ix*dx
    mask=(xyz[:,0]>=8)&(xyz[:,0]<12)&(xyz[:,1]>=8)&(xyz[:,1]<12)&(xyz[:,2]<4)
    halo=mask.reshape(tuple(n+2));s['solid']=np.flatnonzero(halo[1:-1,1:-1,1:-1]).tolist();s['solid_halo']=np.flatnonzero(halo).tolist()
    return s


def series(path,points):
    p,data,_=read_manifest(path);u=[];v=[];t=[]
    for entry in data['frames']:
        arrays,meta=read_frame(p.parent/entry['file']);a,b,_=sample_parent(arrays,data['case'],points,np.zeros(len(points),bool));u.append(a);v.append(b);t.append(entry['time']+data['case'].get('time_origin_seconds',0.))
    return np.asarray(t),np.asarray(u),np.asarray(v)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--device',default='cpu');p.add_argument('--warmup',type=int,default=5000);p.add_argument('--steps',type=int,default=1000);p.add_argument('--ratios',default='1,2');p.add_argument('--interval',type=int,default=10);p.add_argument('--fine-reference',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();parent=case([32,24,16],1.,np.array([.5,.5,.5]),True);parent['origin']=parent['origin'].tolist()
    s=Session(parent,a.device);s.advance(a.warmup);print('parent warmup',s.flow.i,s.quality['status'],flush=True)
    result=record(s,a.warmup+a.steps,a.interval,str(a.output/'parent'),lambda n:None);manifest=result['manifest']
    points=np.array([[6.5,6.5,2.5],[10.5,6.5,2.5],[14.5,10.5,2.5],[18.5,10.5,2.5],[22.5,10.5,2.5],[14.5,14.5,6.5],[18.5,10.5,8.5]])
    pt,pu,pp=series(manifest,points);rows=[]
    for ratio in map(int,a.ratios.split(',')):
        dx=1./ratio;child=case([20*ratio,16*ratio,12*ratio],dx,np.array([4+dx/2,4+dx/2,dx/2]));child['origin']=child['origin'].tolist()
        mapped=capture(manifest,child,a.output/('boundary-%d.npz'%ratio));cs=Session(mapped['case'],a.device)
        output=record(cs,a.steps*ratio,a.interval*ratio,str(a.output/('child-%d'%ratio)),lambda n:None);ct,cu,cp=series(output['manifest'],points)
        np.testing.assert_allclose(ct,pt,atol=1e-10,rtol=0)
        reference_u,reference_p=pu,pp
        if a.fine_reference and ratio>1:
            full=case([32*ratio,24*ratio,16*ratio],dx,np.array([dx/2]*3),True);full['origin']=full['origin'].tolist();fs=Session(full,a.device);fs.advance(a.warmup*ratio)
            print('fine reference warmup',ratio,fs.quality['status'],flush=True)
            fr=record(fs,(a.warmup+a.steps)*ratio,a.interval*ratio,str(a.output/('reference-%d'%ratio)),lambda n:None)
            ft,reference_u,reference_p=series(fr['manifest'],points);np.testing.assert_allclose(ft,pt,atol=1e-10,rtol=0)
        cut=len(ct)//2;u=reference_u[cut:];v=cu[cut:];pr=reference_p[cut:];pc=cp[cut:]
        split=len(u)//2;stationarity=float(np.linalg.norm(u[:split].mean(0)-u[split:].mean(0))/np.linalg.norm(u.mean(0)))
        mean=float(np.linalg.norm(v.mean(0)-u.mean(0))/np.linalg.norm(u.mean(0)))
        rms=float(np.linalg.norm(v.std(0)-u.std(0))/max(np.linalg.norm(u.std(0)),1e-12));pressure=float(np.sqrt(np.mean((pc.mean(0)-pr.mean(0))**2))/(.5*1.225*25))
        row=dict(ratio=ratio,mean_velocity_relative_l2=mean,fluctuation_rms_relative_l2=rms,cp_rmse=pressure,quality=cs.quality,reference_stationarity_change=stationarity,reference='full child-resolution domain' if a.fine_reference else 'coarse parent',absolute_start=ct[0],absolute_end=ct[-1],passed=mean<=.05 and rms<=.1 and pressure<=.1 and cs.quality['status']=='within-tested-envelope' and stationarity<=.05)
        np.savez_compressed(a.output/('comparison-%d.npz'%ratio),points=points,times=ct,parent_velocity=pu,child_velocity=cu,parent_pressure=pp,child_pressure=cp,reference_velocity=reference_u,reference_pressure=reference_p)
        rows.append(row);print({k:v for k,v in row.items() if k!='quality'},flush=True)
    report=dict(thresholds=dict(mean_relative_l2=.05,rms_relative_l2=.1,cp_rmse=.1),rows=rows,passed=all(r['passed'] for r in rows),wall_seconds=time.monotonic()-start,scope='Offline nested cropped building; refined comparison includes discretization difference; not physical validation')
    (a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
