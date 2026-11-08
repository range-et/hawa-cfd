"""Record actual moving-cylinder fields for the motion demonstration."""
import json,time
from pathlib import Path
from hawa.plugin import Session
from hawa.recording import record
ROOT=Path(__file__).resolve().parents[1]
case=dict(shape=[33,25,17],dx=.25,speed=1.,viscosity=.05,density=1.,mach=.04,collision='bgk',
          moving_bodies=[dict(id='body',pivot=[3,3,2],geometry=dict(type='cylinder',center=[3,3,2],radius=.5,length=2.),
                              motion=dict(type='oscillation',axis=[0,1,0],amplitude=.25,frequency=.5,ramp=.5))])
s=Session(case,'mps');start=time.monotonic();folder=ROOT/'results/motion/cylinder-recording-refill'
def checkpoint(n):
    if n%100==0:print(n,round(time.monotonic()-start,2),flush=True)
r=record(s,1000,10,folder,checkpoint)
(ROOT/'results/motion/cylinder-loads.json').write_text(json.dumps(list(s.solver.moving.history)))
(ROOT/'results/motion/cylinder-summary.json').write_text(json.dumps(dict(**r,seconds=time.monotonic()-start,status=s.status(),motion=s.solver.moving.metadata()),indent=2))
print(r,flush=True)
