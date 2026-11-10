"""Probe statistics from a completed recording; explicit sampling limitations."""
import numpy as np
from .recording import read_manifest
from .fields import read_frame
from .plugin import sample_arrays
from .boundary_data import digest


def summarize(times,velocity,pressure):
    t=np.asarray(times,float);u=np.asarray(velocity,float);p=np.asarray(pressure,float)
    if t.ndim!=1 or len(t)<4 or not np.isfinite(t).all() or u.ndim!=3 or u.shape[0]!=len(t) or u.shape[-1]!=3 or u.shape[1]<1 or p.shape!=u.shape[:2] or not np.isfinite(u).all() or not np.isfinite(p).all() or np.any(np.diff(t)<=0):raise ValueError('Statistics need at least four finite increasing samples and matching probe arrays')
    dt=np.diff(t)
    if not np.allclose(dt,dt.mean(),rtol=1e-5,atol=1e-10):raise ValueError('Statistics require uniformly timed frames; select a window excluding a shorter final interval')
    mean=u.mean(0);fluct=u-mean;cov=np.einsum('tpi,tpj->pij',fluct,fluct)/len(t);variance=np.diagonal(cov,axis1=1,axis2=2)
    half=len(t)//2;scale=max(float(np.linalg.norm(mean)),1e-12)
    drift=float(np.linalg.norm(u[half:].mean(0)-u[:half].mean(0))/scale)
    blocks=min(8,len(t)//4);length=len(t)//blocks
    batch=np.array([u[i*length:(i+1)*length].mean(0) for i in range(blocks)])
    # Two-sided Student critical values for 95% with 1..7 degrees of freedom.
    critical=(12.706,4.303,3.182,2.776,2.571,2.447,2.365)[blocks-2] if blocks>=2 else None
    ci=critical*batch.std(0,ddof=1)/np.sqrt(blocks) if blocks>=2 else None
    window=np.hanning(len(t));spectrum=np.abs(np.fft.rfft(fluct*window[:,None,None],axis=0))**2*dt.mean()/sum(window*window)
    if len(t)%2==0:spectrum[1:-1]*=2
    else:spectrum[1:]*=2
    frequencies=np.fft.rfftfreq(len(t),dt.mean())
    integral=np.zeros((u.shape[1],3))
    autocorrelation=np.fft.irfft(np.abs(np.fft.rfft(fluct,n=2*len(t),axis=0))**2,n=2*len(t),axis=0)[:len(t)]
    for probe in range(u.shape[1]):
        for component in range(3):
            r=autocorrelation[:,probe,component]
            if r[0]<=1e-25:continue
            r=r/r[0];negative=np.flatnonzero(r<=0);end=int(negative[0]) if len(negative) else len(r)//2
            integral[probe,component]=dt.mean()*float(np.sum((r[:end]+r[1:end+1])*.5))
    warnings=[]
    if len(t)<64:warnings.append('Fewer than 64 snapshots; turbulence statistics and uncertainty are poorly sampled')
    if drift>.05:warnings.append('First/second-half mean change exceeds 5%; increase spin-up or averaging')
    if blocks<8:warnings.append('Fewer than eight time blocks for the approximate 95% mean interval')
    if np.any(integral>0) and t[-1]-t[0]<20*float(integral.max()):warnings.append('Window shorter than 20 estimated integral times')
    return dict(samples=len(t),duration_seconds=float(t[-1]-t[0]),frame_interval_seconds=float(dt.mean()),mean_velocity=mean.tolist(),mean_pressure=p.mean(0).tolist(),
        reynolds_covariance=cov.tolist(),resolved_tke=(.5*variance.sum(1)).tolist(),rms_velocity=np.sqrt(np.maximum(variance,0)).tolist(),
        mean_velocity_95_half_width=ci.tolist() if ci is not None else None,integral_time_seconds=integral.tolist(),
        frequency_hz=frequencies.tolist(),velocity_psd=spectrum.tolist(),stationarity_relative_change=drift,blocks=blocks,warnings=warnings,
        status='sampling-checks-met' if not warnings else 'insufficient-statistical-evidence',scope='Resolved probe statistics; block interval is approximate and does not include grid or model error')


def analyze(manifest,points,start_time=0.,end_time=None,checkpoint=lambda n:None):
    root,data,_=read_manifest(manifest);before=digest(root)
    if not data.get('complete'):raise ValueError('Statistics require a completed recording')
    points=np.asarray(points,float)
    if points.ndim!=2 or points.shape[1]!=3 or not 1<=len(points)<=200 or not np.isfinite(points).all():raise ValueError('Use 1..200 finite lattice-coordinate probes')
    if not np.isfinite(start_time) or start_time<0 or (end_time is not None and (not np.isfinite(end_time) or end_time<=start_time)):raise ValueError('Invalid statistics time window')
    entries=[e for e in data['frames'] if e['time']>=start_time-1e-10 and (end_time is None or e['time']<=end_time+1e-10)]
    u=[];p=[];times=[];hashes=[];quality=[]
    for i,entry in enumerate(entries):
        checkpoint(i);path=root.parent/entry['file'];sha=digest(path);arrays,meta=read_frame(path)
        if meta['case']!=data['case'] or meta['time']!=entry['time']:raise ValueError('Statistics frame provenance mismatch')
        values=sample_arrays(arrays,points)
        if any(v is None for v in values):raise ValueError('Statistics probes require fluid coverage in every frame')
        u.append([v['velocity'] for v in values]);p.append([v['pressure'] for v in values]);times.append(meta['time']);quality.append(meta.get('quality',{}))
        if sha!=digest(path):raise ValueError('Recording frame changed during statistics')
        hashes.append(sha)
    if len(times)<4:raise ValueError('Statistics window requires at least four frames')
    if before!=digest(root):raise ValueError('Recording changed during statistics')
    result=summarize(times,u,p)
    result.update(case=data['case'],start_time=times[0],end_time=times[-1],absolute_start_seconds=times[0]+data['case'].get('time_origin_seconds',0.),
                  source=dict(manifest_sha256=before,frame_sha256=hashes),numerical_statuses=sorted(set(q.get('status','unchecked') for q in quality)),
                  physical_model_statuses=sorted(set(q.get('physical_model_status','not-assessed') for q in quality)))
    return result
