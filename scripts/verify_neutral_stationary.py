"""Stationarity/stress-budget investigation. Does not overwrite the startup test.

Targets set before execution: last two 10000-step mean profiles differ <=2%;
mean wall drag within 5% of drive; profile versus neutral log-law <=5% L2 over
0.1H..0.25H, excluding wall-model sampling plane. No experimental validation claim.
"""
import argparse,json,time
from pathlib import Path
import numpy as np
from hawa.plugin import dispatch, SESSIONS
from hawa.neutral import MODEL
from hawa.atmosphere import neutral_profile
p=argparse.ArgumentParser();p.add_argument('--steps',type=int,default=100000);p.add_argument('--device',default='mps');p.add_argument('--resume',action='store_true');p.add_argument('--sample',type=int,default=1);p.add_argument('--filter',type=float,default=3.);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
spec=dict(shape=[72,36,12],dx=1.,speed=5.,viscosity=1.5e-5,density=1.225,mach=.05,collision=MODEL,boundaries=['periodic']*4+['wall','slip'],neutral_precursor=dict(schema=1,experimental=True,reference_height_m=6.,roughness_length_m=.01,perturbation_fraction=.05,wall_sample_index=a.sample,wall_filter_seconds=a.filter))
sid=None;s=None;start=time.monotonic();rows=[]
checkpoint=str(a.output.with_suffix('.npz').resolve())
report=dict(spec=spec,device=a.device,steps=0,wall_seconds=0.,stationarity_change=None,drag_relative_error=None,log_profile_relative_l2=None,targets=dict(stationarity=.02,drag=.05,profile=.05),passed=False,physical_validation=False,samples=rows,reason='No samples advanced in this invocation')
try:
 sid=dispatch({'op':'create','case':spec,'device':a.device})['session'];s=SESSIONS[sid]
 if a.resume:
  dispatch({'op':'load','session':sid,'path':checkpoint});old=json.loads(a.output.read_text());rows=[r for r in old['samples'] if r['step']<=s.flow.i]
 for step in range(s.flow.i,a.steps,500):
  s.advance(min(500,a.steps-step));u=s.fields()['velocity'];profile=u.mean((1,2));fluct=u-profile[:,None,None,:]
  rows.append(dict(step=s.flow.i,time=float(s.flow.units.convert_time_to_pu(s.flow.i)),profile=profile.tolist(),uw=(fluct[0]*fluct[2]).mean((0,1)).tolist(),drag=-s.solver.rough_floor.report['mean_traction_on_fluid_pa'][0],quality=s.quality['status']))
  if len(rows)%10==0:print(s.flow.i,rows[-1]['time'],rows[-1]['drag'],flush=True)
  if len(rows)>=40:
   recent=np.mean([r['profile'] for r in rows[-20:]],axis=0)[0];previous=np.mean([r['profile'] for r in rows[-40:-20]],axis=0)[0]
   change=float(np.linalg.norm(recent-previous)/np.linalg.norm(recent))
   target=1.225*(.41*5/np.log1p(6/.01))**2
   dragerr=abs(np.mean([r['drag'] for r in rows[-20:]])/target-1)
   heights=np.arange(12)+.5;mask=(heights>=1.2)&(heights<=3)&(np.arange(12)!=a.sample)
   reference=neutral_profile(heights,[5.,0.,0.],6.,.01)[:,0]
   error=float(np.linalg.norm(recent[mask]-reference[mask])/np.linalg.norm(reference[mask]))
  else:change=dragerr=error=None
  report=dict(spec=spec,device=a.device,steps=s.flow.i,wall_seconds=time.monotonic()-start,stationarity_change=change,drag_relative_error=dragerr,log_profile_relative_l2=error,targets=dict(stationarity=.02,drag=.05,profile=.05),passed=bool(s.quality['status']!='rejected' and change is not None and change<=.02 and dragerr<=.05 and error<=.05),physical_validation=False,samples=rows)
  a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
  if s.quality['status']=='rejected':report['checkpoint_omitted']='Rejected state is not checkpointed'
  elif s.flow.i%5000==0 or s.flow.i==a.steps:dispatch({'op':'save','session':sid,'path':checkpoint})
  if s.quality['status']=='rejected':break
except Exception as exc:
 # Session.advance can mark quality rejected and raise before fields are safe.
 # Keep the last valid samples, invalidate earlier success, and do not save the
 # failing populations as a resumable checkpoint.
 report.update(passed=False,error=type(exc).__name__+': '+str(exc),quality_status=s.quality.get('status') if s is not None else 'unknown',checkpoint_omitted='No additional checkpoint attempted after failure')
finally:
 try:
  if sid is not None:dispatch({'op':'close','session':sid})
 except Exception as exc:
  report.update(passed=False,cleanup_error=type(exc).__name__+': '+str(exc))
 report.update(steps=s.flow.i if s is not None else 0,wall_seconds=time.monotonic()-start,samples=rows)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print({k:v for k,v in report.items() if k not in ('spec','samples')})
if not report['passed']:raise SystemExit(1)
