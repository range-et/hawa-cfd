"""Headless moving-sphere invariance and oscillation checks, with raw evidence."""
import json
from pathlib import Path
import numpy as np
import torch
import lettuce as lt
from hawa.plugin import WindFlow,Session
from hawa.moving_boundaries import MovingBoundaries

ROOT=Path(__file__).resolve().parents[1]

def spec(dx=.25):
    return dict(shape=[round(5/dx),round(4/dx),round(3/dx)],dx=dx,speed=1.,viscosity=.05,density=1.,mach=.04,collision='bgk',
                moving_bodies=[dict(id='body',pivot=[2,2,1.5],geometry=dict(type='sphere',center=[2,2,1.5],radius=.55),
                                    motion=dict(type='oscillation',axis=[0,1,0],amplitude=.15,frequency=.5))])


def comoving(device='cpu',steps=100):
    case=spec();case['moving_bodies'][0]['motion']=dict(type='translation',axis=[1,0,0],speed=.2)
    class Periodic(WindFlow):
        @property
        def post_boundaries(self):return [lt.BounceBackBoundary(self.solid)]
    flow=Periodic(lt.Context(device,torch.float32,use_native=False),case);u=torch.zeros_like(flow.u());u[0]=flow.units.convert_velocity_to_lu(.2)
    flow.f=flow.equilibrium(flow,flow.rho(),u);sim=lt.Simulation(flow,lt.BGKCollision(flow.units.relaxation_parameter_lu),[])
    wall=MovingBoundaries(sim,case);before=flow.f.clone();sim(steps)
    return dict(device=device,steps=steps,max_fluid_population_error=float((flow.f-before)[:,~flow.solid].abs().max().cpu()),
                max_force_newtons=max(float(np.linalg.norm(h['loads'][0]['force'])) for h in wall.history),
                transition_mass_lu=wall.transition_mass)

if __name__=='__main__':
    out=ROOT/'results/motion';out.mkdir(parents=True,exist_ok=True)
    reports=[comoving(d) for d in ['cpu']+(['mps'] if torch.backends.mps.is_available() else [])]
    (out/'comoving.json').write_text(json.dumps(reports,indent=2))
    print(json.dumps(reports,indent=2))
    assert all(r['max_fluid_population_error']<3e-6 and r['max_force_newtons']<.002 for r in reports)
