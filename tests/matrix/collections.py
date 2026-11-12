"""Finite shared-view product; the oracle does not call production validation."""
import itertools
import numpy as np
from .operations import SCALARS,FIELD_ACTIONS


def collection_cases():
    for layout,masked,time,storage,field,action in itertools.product(
            ('single','nested','disjoint','rotated'),(False,True),('aligned','different'),('memory','reload'),SCALARS,FIELD_ACTIONS):
        yield dict(id='collection/'+'/'.join(map(str,(layout,masked,time,storage,field,action))),
            layout=layout,masked=masked,time=time,storage=storage,field=field,action=action,
            expected=layout=='single' or time=='aligned')


def exercise_collection(row,directory):
    from hawa.fields import store,dispatch_field
    frames=[]
    for i in range(1 if row['layout']=='single' else 2):
        dx=1. if i==0 else .5;basis=np.eye(3);origin=np.zeros(3) if i==0 else np.array([2.,2.,2.])
        if i and row['layout']=='disjoint':origin=np.array([8.,0.,0.])
        if i and row['layout']=='rotated':origin=np.array([5.,2.,0.]);basis=np.array([[0,1,0],[-1,0,0],[0,0,1]])
        g=np.indices((7,7,7)).astype(float);velocity=np.array([.5+.01*g[0],.02*g[1],.03*g[2]])
        solid=np.zeros((7,7,7),bool)
        if row['masked']:solid[2,2,2]=True
        spec=dict(shape=[7]*3,dx=dx,spacing=dx,origin=origin.tolist(),basis=basis.tolist(),density=1.225,speed=1.)
        key=store(dict(velocity=velocity,pressure=g[0]+origin[0],density=np.full((7,7,7),1.225),solid=solid),
            dict(case=spec,time=2. if i==0 or row['time']=='aligned' else 3.,mean=False))['frame']
        if row['storage']=='reload':
            path=str(directory/('collection-%d.npz'%i));dispatch_field(dict(action='save',frame=key,path=path));key=dispatch_field(dict(action='load',path=path))['frame']
        frames.append(key)
    request=dict(action=row['action'],field=row['field'],frames=frames,points=[[x,y,3.5] for x in (3.5,4.) for y in (3.5,4.)],shape=[2,2],levels=[2.5],level=2.5,seeds=[[4.,4.,4.]],steps=4,step=.1,stride=2)
    result=dispatch_field(request)
    assert result['collection']['domains']==len(frames)
    if row['action'] in ('sample','plane','contours'):
        assert len(result['values'])==4 and np.isfinite(result['values']).all()
    if row['action']=='plane':assert result['mesh_faces'] and np.isfinite(result['mesh_vertices']).all()
    if row['action']=='trace':assert len(result['paths'])==1 and len(result['paths'][0])==5 and result['reasons']==['completed']
    if row['action']=='isosurface':assert np.isfinite(result['vertices']).all()
