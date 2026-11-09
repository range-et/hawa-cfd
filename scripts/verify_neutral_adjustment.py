"""Longer precursor adjustment experiment; does not certify atmospheric validation."""
import json,math,time
from pathlib import Path
import numpy as np
from hawa.plugin import Session
from hawa.neutral import MODEL
p=Path('results/neutral-precursor/adjustment-mps.json')
spec=dict(shape=[72,36,12],dx=1.,speed=5.,viscosity=1.5e-5,density=1.225,mach=.05,
 collision=MODEL,boundaries=['periodic']*4+['wall','slip'],
 neutral_precursor=dict(schema=1,experimental=True,reference_height_m=6.,roughness_length_m=.01,perturbation_fraction=.05))
s=Session(spec,'mps');dt=float(s.flow.units.convert_time_to_pu(1));start=time.monotonic();rows=[]
for block in range(40):
 s.advance(500)
 u=s.fields()['velocity']; mean=u.mean((1,2)); fluct=u-mean[:,None,None,:]
 rows.append(dict(time_seconds=float(s.flow.units.convert_time_to_pu(s.flow.i)),profile=mean.tolist(),
  resolved_variance=(fluct*fluct).mean((1,2)).tolist(),wall=s.solver.rough_floor.report,
  mass_change=s.relative_mass_change,quality=s.quality))
 print(block+1,s.flow.i,rows[-1]['time_seconds'],s.quality['status'],flush=True)
 if s.quality['status']=='rejected':break
report=dict(spec=spec,device='mps',steps=s.flow.i,wall_seconds=time.monotonic()-start,
 atmospheric_validation=False,scope='adjustment and resolved spatial variance; no experimental reference',samples=rows)
p.write_text(json.dumps(report,indent=2)+'\n')
