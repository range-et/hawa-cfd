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


def load_frame(manifest,index):
    from .fields import dispatch_field
    path=Path(manifest);data=json.loads(path.read_text())
    if type(index) is not int or not 0<=index<len(data['frames']):raise ValueError('Frame index outside recording')
    target=(path.parent/data['frames'][index]['file']).resolve()
    if target.parent!=path.parent.resolve():raise ValueError('Frame path must stay in the recording directory')
    return dispatch_field({'action':'load','path':str(target)})


def pathlines(manifest,seeds,last=None,checkpoint=lambda n:None):
    from .plugin import sample_arrays
    root=Path(manifest);data=json.loads(root.read_text());frames=data['frames'];last=len(frames)-1 if last is None else int(last)
    if len(seeds)>200 or not 0<=last<len(frames):raise ValueError('At most 200 seeds and a valid final frame index')
    points=np.asarray(seeds,float);paths=[[p.tolist()] for p in points];alive=np.ones(len(points),bool)
    def read(entry):
        path=(root.parent/entry['file']).resolve()
        if path.parent!=root.parent.resolve():raise ValueError('Invalid recording path')
        with np.load(path,allow_pickle=False) as f:return {k:f[k].copy() for k in ('velocity','pressure','density','solid') if k in f}
    before=read(frames[0]);dx=data['case'].get('physical_dx',data['case'].get('dx',1.))
    for k in range(last):
        after=read(frames[k+1]);dt=frames[k+1]['time']-frames[k]['time']
        if dt<=0:raise ValueError('Recording times must increase')
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
                points[i]=q;paths[i].append(q.tolist())
        before=after
    return {'paths':paths,'time':frames[last]['time'],'case':data['case']}
