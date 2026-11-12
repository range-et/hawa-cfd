"""Bounded offline frame recording and playback."""
import json
from pathlib import Path
import numpy as np


def record(session, steps, interval, directory, checkpoint):
    if type(steps) is not int or not 1<=steps<=100000:raise ValueError('Recording steps must be 1..100000')
    if type(interval) is not int or interval<1:raise ValueError('Frame interval must be positive')
    if steps < session.flow.i:raise ValueError('Recording target precedes the current simulation time')
    frame_count=1+steps//interval-session.flow.i//interval+int(steps%interval!=0 and steps>session.flow.i)
    if frame_count>1000:raise ValueError('Recording exceeds 1000 frame budget')
    case={**session.spec,'physical_dx':float(session.flow.units.convert_length_to_pu(1))}
    root=Path(directory).resolve()
    # A new directory prevents accidental overwrite of a previous run.
    root.mkdir(parents=True,exist_ok=False)
    frames=[];saved_bytes=0
    def save():
        nonlocal saved_bytes
        checkpoint(session.flow.i)
        meta={'iteration':session.flow.i,'time':session.flow.units.convert_time_to_pu(session.flow.i),'case':case,'mean':False,'samples':0,'quality':dict(session.quality)}
        if hasattr(session.solver,"moving"):meta["motion"]=session.solver.moving.metadata()
        name='frame-{:06d}.npz'.format(len(frames))
        fields=session.fields()
        if session.spec.get('neutral_precursor'):
            # Kinetic strain preserves the parent's non-equilibrium stress when
            # reconstructing a child lattice at another spacing/time step.
            import torch
            flow=session.flow;model=session.solver.collision;rho=flow.rho()
            pi=flow.shear_tensor(flow.f-flow.equilibrium(flow))
            magnitude=torch.sqrt(2*(pi*pi).sum((0,1)))/(2*rho[0]*flow.stencil.cs**2)
            tau0=.5+model.margin;b=12*model.cs**2*magnitude
            tau=tau0+.5*b/(torch.sqrt(tau0*tau0+b)+tau0)
            strain=-pi/(2*rho*flow.stencil.cs**2*tau*float(flow.units.convert_time_to_pu(1)))
            strain[:,:,flow.solid]=0
            fields['strain_rate']=strain.detach().cpu().numpy().copy()
            wall=session.solver.rough_floor
            if wall.filtered is not None:
                fields['wall_velocity']=flow.units.convert_velocity_to_pu(wall.filtered).detach().cpu().numpy().copy()
        metadata=np.array(json.dumps(meta))
        size=sum(v.nbytes for v in fields.values())+metadata.nbytes
        if saved_bytes+size>2*1024**3:raise ValueError('Recording exceeds 2 GiB uncompressed budget')
        with (root/name).open('wb') as f:np.savez_compressed(f,**fields,metadata=metadata)
        saved_bytes+=size
        frames.append({'file':name,'time':meta['time'],'iteration':meta['iteration']})
        manifest={'case':case,'frames':frames,'complete':session.flow.i==steps}
        temporary=root/'manifest.tmp';temporary.write_text(json.dumps(manifest,indent=2));temporary.replace(root/'manifest.json')
    save()
    while session.flow.i<steps:
        checkpoint(session.flow.i)
        n=min(5,steps-session.flow.i,interval-session.flow.i%interval)
        session.advance(n)
        if session.flow.i%interval==0 or session.flow.i==steps:save()
    session.target=steps;session.state='completed'
    return {'manifest':str(root/'manifest.json'),'frames':len(frames)}



def read_manifest(manifest):
    path=Path(manifest).resolve()
    if path.stat().st_size>16*1024**2:raise ValueError('Recording manifest exceeds 16 MiB')
    data=json.loads(path.read_text())
    if not isinstance(data,dict) or not isinstance(data.get('case'),dict):
        raise ValueError('Recording requires case metadata')
    frames=data.get('frames')
    if not isinstance(frames,list) or not 1<=len(frames)<=1000:
        raise ValueError('Recording requires 1..1000 frames')
    previous=-float('inf')
    for entry in frames:
        if not isinstance(entry,dict) or not isinstance(entry.get('file'),str):
            raise ValueError('Recording frame requires a filename')
        target=(path.parent/entry['file']).resolve()
        if target.parent!=path.parent:raise ValueError('Frame path must stay in the recording directory')
        time=entry.get('time')
        if not isinstance(time,(int,float)) or not np.isfinite(time) or time<=previous:
            raise ValueError('Recording times must be finite and increase')
        previous=time
    dx=data['case'].get('physical_dx',data['case'].get('dx',1.))
    if not isinstance(dx,(int,float)) or not np.isfinite(dx) or dx<=0:
        raise ValueError('Recording spacing must be finite and positive')
    return path,data,dx


def load_frame(manifest,index):
    from .fields import read_frame,store
    path,data,_=read_manifest(manifest)
    if type(index) is not int or not 0<=index<len(data['frames']):raise ValueError('Frame index outside recording')
    entry=data['frames'][index]
    arrays,meta=read_frame(path.parent/entry['file'])
    if meta['case']!=data['case'] or meta.get('time')!=entry['time']:
        raise ValueError('Recording frame metadata does not match the manifest')
    return store(arrays,meta)

