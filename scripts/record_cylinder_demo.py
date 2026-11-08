"""Record a seeded, spanwise-periodic cylinder wake at Re=100."""
import json
from pathlib import Path
import numpy as np
import torch
from hawa.plugin import Session
from hawa.recording import record

root=Path(__file__).resolve().parents[1]
shape=[161,81,4];dx=.15
x,y,z=np.indices(shape);solid=(x-40)**2+(y-40.3)**2<=(1/.15)**2
spec={'shape':shape,'dx':dx,'spacing':dx,'origin':[0,0,0], 'speed':1.,'viscosity':.02,'density':1.225,
      'mach':.1,'collision':'bgk','boundaries':['inlet','outlet','periodic','periodic','periodic','periodic'],
      'solid':np.flatnonzero(solid).tolist()}
s=Session(spec,'mps')
# Small reproducible transverse perturbation breaks exact reflection symmetry.
u=s.flow.u();perturb=.0001*np.exp(-((x-55)**2+(y-40.3)**2)/50)*np.sin(y*.7)
u[1]+=torch.tensor(perturb,device=u.device,dtype=u.dtype)
s.flow.f=s.flow.equilibrium(s.flow,s.flow.rho(),u)
out=root/'results/v04/cylinder-recording-outflow'
print(record(s,8000,100,out,lambda n:print('step',n,flush=True) if n%500==0 else None),flush=True)
