"""Bounded open-face and wall verification; not atmospheric validation.

Declared criteria: advected transverse pulse, small versus doubled X domain:
velocity L-infinity error / initial pulse amplitude <= 10% after pulse exit.
Wall analytic checks use <=0.1% relative L2 and <=0.1% drive/drag mismatch.
The pulse tests a smooth convected disturbance, not arbitrary acoustic reflection.
"""
import argparse
import json
import math
from pathlib import Path
import numpy as np
import torch
import lettuce as lt
from hawa.neutral import make, MODEL
from hawa.neutral_external import METHOD
from hawa.boundary_contracts import FACES


def base(n,dx=1.,speed=5.,viscosity=1.5e-5):
    return dict(shape=n,dx=dx,speed=speed,viscosity=viscosity,density=1.225,mach=.05,
        collision=MODEL,boundaries=['periodic']*4+['wall','slip'],neutral_precursor=dict(schema=1,
        experimental=True,reference_height_m=6.,roughness_length_m=.01,perturbation_fraction=0.))


def analytic(nz):
    h=12.; dx=h/nz; nu=.1; speed=.1; z0=.01
    spec=base([8,8,nz],dx,speed,nu);spec['neutral_precursor']['smagorinsky_constant']=0.
    f,sim=make(spec,lt.Context('cpu',torch.float64,use_native=False))
    ustar=.41*speed/math.log1p(6/z0); g=ustar**2/h
    z=(np.arange(nz)+.5)*dx;zs=.5*dx
    expected=ustar*np.log1p(zs/z0)/.41+g/nu*(h*(z-zs)-.5*(z*z-zs*zs))
    u=torch.zeros_like(f.u());u[0]=torch.tensor(f.units.convert_velocity_to_lu(expected))[None,None,:]-.5*sim.collision.acceleration[0]
    f.f=f.equilibrium(f,u=u);steps=2000*nz//12;sim(steps)
    actual=f.u_pu[0].mean((0,1)).numpy()
    error=float(np.linalg.norm(actual-expected)/np.linalg.norm(expected))
    drag=-sim.rough_floor.report['mean_traction_on_fluid_pa'][0]
    drag_error=abs(drag/(1.225*ustar**2)-1)
    return dict(nz=nz,steps=steps,profile_relative_l2=error,drag_error=drag_error,
                passed=error<=.001 and drag_error<=.001)


def pulse(nx):
    spec=base([nx,8,8]);spec['neutral_precursor']['mode']='external'
    cs=[dict(type='velocity',velocity=[5.,0,0]),dict(type='open',velocity=[-5.,0,0]),dict(type='periodic'),dict(type='periodic'),dict(type='wall'),dict(type='slip')]
    spec.update(boundary_method=METHOD,boundary_set=dict(schema=1,patches=[dict(id=f,face=f,condition=c) for f,c in zip(FACES,cs)]))
    f,sim=make(spec,lt.Context('cpu',torch.float64,use_native=False))
    sim.rough_floor.factor=0.  # Isolate the outlet from wall-model transients.
    u=torch.zeros_like(f.u());u[0]=f.units.convert_velocity_to_lu(5.)
    x=np.arange(nx);u[1]=torch.tensor(f.units.convert_velocity_to_lu(.2*np.exp(-((x-10)/4)**2)))[:,None,None]
    f.f=f.equilibrium(f,u=u);sim(1600)
    return f.u_pu.numpy(),sim.external_links.report


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    walls=[analytic(n) for n in (12,24)]
    small,budget=pulse(32);large,_=pulse(64)
    error=float(np.max(np.abs(small-large[:,:32]))/.2)
    tail=float(np.max(np.abs(small[1]))/.2)
    report=dict(walls=walls,pulse=dict(relative_linf=error,residual_fraction=tail,criterion=.1,steps=1600,passed=error<=.1,budget=budget),physical_validation=False)
    report['passed']=all(r['passed'] for r in walls) and report['pulse']['passed']
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
