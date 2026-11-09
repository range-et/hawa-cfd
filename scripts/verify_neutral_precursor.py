"""Run reproducible precursor checks. Model validation is a separate failed gate.

Profile target is <=5% relative L2 drift from the initial surface-layer profile.
This short homogeneous run is verification, not experimental urban validation.
"""
import argparse,json,time,platform
from pathlib import Path
import numpy as np
import torch
from hawa.plugin import Session
from hawa.neutral import MODEL


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--steps',type=int,default=4000);p.add_argument('--device',default='cpu')
    args=p.parse_args()
    rows=[]
    for n in (12,16,24):
        dx=12/n
        spec=dict(shape=[n,n,n],dx=dx,speed=5.,viscosity=1.5e-5,density=1.225,mach=.05,
            collision=MODEL,boundaries=['periodic']*4+['wall','slip'],
            neutral_precursor=dict(schema=1,experimental=True,reference_height_m=6.,roughness_length_m=.01,
                perturbation_fraction=.02))
        session=Session(spec,args.device);start=time.monotonic()
        initial=session.fields()['velocity'][0].mean((0,1))
        # Same physical duration on all grids; supplied steps refer to 12^3.
        steps=round(args.steps*n/12);session.advance(steps)
        final=session.fields()['velocity'][0].mean((0,1))
        # Lower quarter, excluding first cell: claimed surface-layer interval.
        sl=slice(1,max(3,n//4))
        drift=float(np.linalg.norm(final[sl]-initial[sl])/np.linalg.norm(initial[sl]))
        rows.append(dict(shape=spec['shape'],dx=dx,steps=steps,
            physical_seconds=float(session.flow.units.convert_time_to_pu(steps)),
            wall_seconds=time.monotonic()-start,mass_change=session.relative_mass_change,
            initial_profile=initial.tolist(),final_profile=final.tolist(),
            surface_layer_relative_l2_drift=drift,profile_target=.05,profile_pass=drift<=.05,
            quality=session.quality))
    report=dict(environment=dict(python=platform.python_version(),torch=torch.__version__,device=args.device),
        cases=rows,profile_preservation_pass=all(r['profile_pass'] for r in rows),
        atmospheric_validation=False,reason='No experimental comparison or converged turbulence statistics in this harness')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'}))
    print([(r['shape'][0],r['surface_layer_relative_l2_drift']) for r in rows])
    return 0 if report['profile_preservation_pass'] else 2
if __name__=='__main__':raise SystemExit(main())
