"""Bounded offline frame recording and time-dependent particle advection."""
import json
from pathlib import Path
import numpy as np


def record(session, steps, interval, directory, checkpoint):
    if type(steps) is not int or not 1<=steps<=100000:raise ValueError('Recording steps must be 1..100000')
    if type(interval) is not int or interval<1:raise ValueError('Frame interval must be positive')
    if steps//interval+2>1000:raise ValueError('Recording exceeds 1000 frame budget')
    case={**session.spec,'physical_dx':float(session.flow.units.convert_length_to_pu(1))}
    root=Path(directory).resolve()
    # A new directory prevents accidental overwrite of a previous run.
    root.mkdir(parents=True,exist_ok=False)
    frames=[]
    def save():
        checkpoint(session.flow.i)
        meta={'iteration':session.flow.i,'time':session.flow.units.convert_time_to_pu(session.flow.i),'case':case,'mean':False,'samples':0}
        name='frame-{:06d}.npz'.format(len(frames))
        fields=session.fields()
        if (len(frames)+1)*sum(v.nbytes for v in fields.values())>2*1024**3:raise ValueError('Recording exceeds 2 GiB uncompressed budget')
        with (root/name).open('wb') as f:np.savez_compressed(f,**fields,metadata=np.array(json.dumps(meta)))
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


MAX_PATH_POINTS = 100000


def read_manifest(manifest):
    path=Path(manifest).resolve()
    if path.stat().st_size>2_000_000:raise ValueError('Recording manifest exceeds 2 MB')
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


def pathlines(manifest,seeds,last=None,checkpoint=lambda n:None):
    from .plugin import sample_arrays
    from .fields import read_frame
    root,data,dx=read_manifest(manifest);frames=data['frames']
    last=len(frames)-1 if last is None else last
    if type(last) is not int or not 0<=last<len(frames):raise ValueError('Invalid final frame index')
    points=np.asarray(seeds,float)
    if points.ndim!=2 or points.shape[1]!=3 or not 1<=len(points)<=200 or not np.isfinite(points).all():
        raise ValueError('Use 1..200 finite three-coordinate seeds')
    points=points.copy()
    paths=[[p.tolist()] for p in points];alive=np.ones(len(points),bool);total=len(points)
    def read(entry):
        checkpoint(0)
        arrays,meta=read_frame(root.parent/entry['file'])
        if meta['case']!=data['case'] or meta.get('time')!=entry['time']:
            raise ValueError('Recording frame metadata does not match the manifest')
        return arrays
    before=read(frames[0])
    for k in range(last):
        after=read(frames[k+1]);dt=frames[k+1]['time']-frames[k]['time']
        if after['velocity'].shape!=before['velocity'].shape:
            raise ValueError('Recording frame lattice shapes must match')
        speed=max(np.linalg.norm(before['velocity'],axis=0).max(),np.linalg.norm(after['velocity'],axis=0).max())
        sub=max(1,int(np.ceil(dt*speed/dx/.4)))
        if sub>1000:raise ValueError('Frames too far apart for pathline integration')
        for j in range(sub):
            checkpoint(k*1000+j)
            t=(j+.5)/sub;h=dt/sub/dx
            for i,p in enumerate(points):
                if not alive[i]:continue
                a=sample_arrays(before,[p])[0];b=sample_arrays(after,[p])[0]
                if a is None or b is None:alive[i]=False;continue
                v=(1-t)*np.array(a['velocity'])+t*np.array(b['velocity'])
                mid=p+h*v/2
                a=sample_arrays(before,[mid])[0];b=sample_arrays(after,[mid])[0]
                if a is None or b is None:alive[i]=False;continue
                q=p+h*((1-t)*np.array(a['velocity'])+t*np.array(b['velocity']))
                if sample_arrays(after,[q])[0] is None:alive[i]=False;continue
                if total>=MAX_PATH_POINTS:raise ValueError('Pathlines exceed 100000 point budget; reduce seeds or frame range')
                points[i]=q;paths[i].append(q.tolist());total+=1
        before=after
    return {'paths':paths,'time':frames[last]['time'],'case':data['case']}
