"""Laminar analytic qualification; tolerances fixed before measurement.
Run with the repository Python. Does not claim atmospheric validity.
"""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import torch
from hawa.plugin import Session
from hawa.boundaries import FACES, METHOD


def run(n, kind, device):
    dx=1/(n-1); shape=[2*(n-1)+1,n,4]
    nu=.1;rho0=1.225;peak=.1
    cs=[dict(type='periodic') for _ in FACES]
    cs[2]=dict(type='wall');cs[3]=dict(type='wall',velocity=[peak if kind=='couette' else 0,0,0])
    gradient=8*nu*rho0*peak
    if kind=='poiseuille':
        cs[0]=dict(type='pressure',pressure_pa=2*gradient)
        cs[1]=dict(type='pressure',pressure_pa=0.)
    spec=dict(shape=shape,dx=dx,speed=1.,viscosity=nu,density=rho0,mach=.05,
              collision='regularized',initial_velocity=[0.,0.,0.],boundary_method=METHOD,
              boundary_set=dict(schema=1,patches=[dict(id=f,face=f,condition=c) for f,c in zip(FACES,cs)]))
    s=Session(spec,device);f=s.flow;y=np.linspace(0,1,n)
    target=peak*(y if kind=='couette' else 4*y*(1-y))
    u=torch.zeros_like(f.u());u[0]=f.units.convert_velocity_to_lu(f.context.convert_to_tensor(target))[None,:,None]
    pressure=torch.zeros_like(f.rho())
    if kind=='poiseuille':pressure[0]=f.context.convert_to_tensor(gradient*(2-np.linspace(0,2,shape[0])))[:,None,None]
    f.f=f.equilibrium(f,f.units.convert_pressure_pu_to_density_lu(pressure),u)
    mass0=float(f.rho().sum().cpu());dt=float(f.units.convert_time_to_pu(1))
    steps=int(np.ceil(2/(nu*dt)));start=time.monotonic();s.advance(steps)
    profile=s.fields()['velocity'][0,shape[0]//2,:,2]
    error=float(np.linalg.norm(profile-target)/np.linalg.norm(target))
    wall_error=float(np.max(np.abs(profile[[0,-1]]-target[[0,-1]])))
    mass_drift=abs(float(f.rho().sum().cpu())/mass0-1)
    return dict(kind=kind,n=n,device=device,steps=steps,time_seconds=steps*dt,wall_seconds=time.monotonic()-start,
                relative_l2=error,wall_error_m_s=wall_error,relative_mass_change=mass_drift,
                boundary=s.solver.general_boundary.report,
                passed=error<.04 and wall_error<5e-6 and mass_drift<.02)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--grids',default='9,13,17');args=p.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    reports=[]
    for kind in ('couette','poiseuille'):
        for n in [int(v) for v in args.grids.split(',')]:
            report=run(n,kind,'cpu');reports.append(report);print(json.dumps(report),flush=True)
            (out/'report.json').write_text(json.dumps(dict(criteria=dict(relative_l2=.04,wall_error_m_s=5e-6,relative_mass_change=.02),cases=reports),indent=2))
    if not all(r['passed'] for r in reports):raise SystemExit(1)

if __name__=='__main__':main()
