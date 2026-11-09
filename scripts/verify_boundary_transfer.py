"""Bounded CPU/MPS end-to-end transfer comparison; not atmospheric validation."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from hawa.plugin import Session
from hawa.recording import record
from hawa.boundary_data import capture

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'results/boundary-transfer/final-numerical')
root=parser.parse_args().output
root.mkdir(exist_ok=False)
base={'speed':1.,'viscosity':.1,'density':1.225,'mach':.03,'collision':'regularized',
      'boundaries':['inlet','outlet','periodic','periodic','periodic','periodic']}
parent={**base,'shape':[17,9,9],'dx':.2,'spacing':.2,'solid':[(x*9+y)*9+z for x in (3,4) for y in (3,4,5) for z in (3,4,5)]}
child={**base,'shape':[13,13,13],'dx':.1,'spacing':.1,'origin':[1.2,.2,.2]}
report={'scope':'60/120-step developing-wake verification, not convergence','devices':{}}
reference=None
for device in ['cpu']+(['mps'] if torch.backends.mps.is_available() else []):
    s=Session(parent,device)
    result=record(s,60,5,str(root/(device+'-parent')),lambda n:None)
    data=capture(result['manifest'],child,root/(device+'-inlet.npz'))
    c=Session(data['case'],device);c.advance(120)
    values=c.fields()['velocity']
    if reference is None:reference=values
    np.testing.assert_allclose(values,reference,atol=2e-5,rtol=3e-4)
    assert abs(s.quality['time_seconds']-c.quality['time_seconds'])<1e-12
    report['devices'][device]={'parent':s.quality,'child':c.quality,'max_velocity_difference_from_cpu':float(np.max(np.abs(values-reference)))}
report['cuda_tested']=False
(root/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({d:v['max_velocity_difference_from_cpu'] for d,v in report['devices'].items()}))
