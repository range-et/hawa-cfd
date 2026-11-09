"""Creeping rotating sphere: torque vs -8*pi*mu*R^3*Omega.

Periodic finite box; reports grid trend, not an unbounded-domain validation.
"""
import json,time
from pathlib import Path
import numpy as np
import torch
import lettuce as lt
from hawa.plugin import WindFlow
from hawa.moving_boundaries import MovingBoundaries
ROOT=Path(__file__).resolve().parents[1]


def benchmark(dx,device='cpu'):
    case=dict(shape=[round(8/dx)+1]*3,dx=dx,speed=1.,viscosity=.2,density=1.,mach=.1,collision='bgk',moving_bodies=[dict(id='sphere',pivot=[4,4,4],geometry=dict(type='sphere',center=[4,4,4],radius=1.),motion=dict(type='rotation',axis=[0,0,1],rpm=.1*60/(2*np.pi),ramp=1.))])
    class Periodic(WindFlow):
        @property
        def post_boundaries(self):return [lt.BounceBackBoundary(self.solid)]
    flow=Periodic(lt.Context(device,torch.float32,use_native=False),case);flow.f=flow.equilibrium(flow,flow.rho(),torch.zeros_like(flow.u()))
    sim=lt.Simulation(flow,lt.BGKCollision(flow.units.relaxation_parameter_lu),[]);moving=MovingBoundaries(sim,case)
    steps=int(np.ceil(20/moving.dt));start=time.monotonic()
    sim(steps)
    measured=float(np.mean([h['loads'][0]['torque'][2] for h in moving.history if h['time']>15]))
    expected=-8*np.pi*.2*.1
    r=dict(device=device,dx=dx,steps=steps,torque=measured,analytic_unbounded=expected,relative_error=abs(measured/expected-1),seconds=time.monotonic()-start)
    return r


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--output', type=Path, default=ROOT/'results/motion/rotating-sphere.json')
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    reports=[]
    for dx in [.5,1/3,.25]:
        r=benchmark(dx,args.device)
        reports.append(r);print(r,flush=True)
        args.output.write_text(json.dumps(reports,indent=2))
