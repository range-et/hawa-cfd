"""Report fixed-window sensitivity and momentum balance from the saved history."""
import argparse,json
from pathlib import Path
import numpy as np
from hawa.atmosphere import neutral_profile
p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=json.loads(a.input.read_text());c=r['spec'];rows=r['samples'];height=c['shape'][2]*c['dx'];rho=c['density'];cfg=c['neutral_precursor']
ustar=.41*c['speed']/np.log1p(cfg['reference_height_m']/cfg['roughness_length_m']);drive=rho*ustar**2
reference=neutral_profile((np.arange(c['shape'][2])+.5)*c['dx'],[c['speed'],0.,0.],cfg['reference_height_m'],cfg['roughness_length_m'])[:,0]
windows=[]
for steps in (10000,30000,50000):
 n=steps//500
 if len(rows)<2*n:continue
 last=rows[-n:];previous=rows[-2*n:-n]
 profile=np.mean([x['profile'] for x in last],0)[0];prev=np.mean([x['profile'] for x in previous],0)[0]
 windows.append(dict(window_steps=steps,mean_profile_change=float(np.linalg.norm(profile-prev)/np.linalg.norm(profile)),mean_drag_error=float(abs(np.mean([x['drag'] for x in last])/drive-1))))
# A fixed post-spinup interval, independent of the last window's success/failure.
settled=[x for x in rows if x['step']>=100000]
t=np.array([x['time'] for x in settled]);drag=np.array([x['drag'] for x in settled]);bulk=np.array([np.mean(x['profile'][0]) for x in settled])
measured=(bulk[-1]-bulk[0])/(t[-1]-t[0]);expected=(drive-np.trapz(drag,t)/(t[-1]-t[0]))/(rho*height)
report=dict(source=str(a.input),final_predeclared_check={k:r[k] for k in ('steps','stationarity_change','drag_relative_error','log_profile_relative_l2','passed')},window_sensitivity=windows,post_spinup=dict(start_step=settled[0]['step'],end_step=settled[-1]['step'],time_seconds=float(t[-1]-t[0]),mean_drag_error=float(abs(np.trapz(drag,t)/(t[-1]-t[0])/drive-1)),bulk_acceleration_m_s2=float(measured),drive_minus_wall_acceleration_m_s2=float(expected),momentum_residual_relative_to_drive=float(abs(measured-expected)/(ustar**2/height))),physical_validation=False,profile_probe_count=1,limitations=['12 Z planes: only one independent log-law probe in declared surface interval','No experimental atmospheric validation','Long-window sensitivity is additional evidence; original criteria unchanged'])
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
all_t=[x['time'] for x in rows];axes[0].plot(all_t,[x['drag']/drive for x in rows],lw=.7);axes[0].axhline(1,color='black',lw=.8);axes[0].set(xlabel='Time [s]',ylabel='Wall drag / pressure drive',title='Settling and fluctuations')
z=(np.arange(c['shape'][2])+.5)*c['dx'];mean=np.mean([x['profile'] for x in settled],0)[0];axes[1].plot(reference,z,'k--',label='Initial log law');axes[1].plot(mean,z,label='Mean, steps 100k–200k');axes[1].set(xlabel='Mean velocity [m/s]',ylabel='Height [m]',title='Coarse channel mean');axes[1].legend(fontsize=8)
axes[2].plot(all_t,[np.mean(x['profile'][0]) for x in rows]);axes[2].set(xlabel='Time [s]',ylabel='Bulk velocity [m/s]',title='Momentum adjustment')
fig.suptitle('Experimental rough-floor channel • CPU FP32 • nu = 1.5e-5 m²/s')
fig.savefig(a.output.with_suffix('.png'),dpi=160)
