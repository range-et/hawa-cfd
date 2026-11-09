"""Finite v2 import product with an independent acceptance oracle.

Manufactured parent fields exercise import contracts, not physical validation.
"""
import copy,itertools,json
from pathlib import Path
import numpy as np
from .cases import base,neutral,patches


def nesting_cases():
    for mode,geometry,direction,roughness,ratio,duration,backflow in itertools.product(
            ('external','precursor','legacy'),('empty','interior','cropped'),
            ('through','side','top','reverse'),('uniform','regional'),(1,2),('covered','exhausted'),('velocity','pressure')):
        yield dict(id='nesting/'+ '/'.join(map(str,(mode,geometry,direction,roughness,ratio,duration,backflow))),
                   mode=mode,geometry=geometry,direction=direction,roughness=roughness,ratio=ratio,duration=duration,backflow=backflow,
                   expected=mode=='external' and duration=='covered')


def exercise_nesting(row,directory,device):
    from hawa.boundary_data import capture
    from hawa.plugin import Session
    from hawa.roughness import apply
    root=Path(directory)/('nesting-'+str(len(list(Path(directory).glob('nesting-*')))));root.mkdir()
    parent=base();parent['origin']=[.5,.5,.5];neutral(parent,'external');parent['viscosity']=1.5e-5
    parent.update(boundary_method='shifted-links-v1',boundary_set=patches(('open','open','open','open','wall','open')))
    for patch in parent['boundary_set']['patches']:
        if patch['condition']['type']=='open':patch['condition']['backflow_mode']=row['backflow']
    child=copy.deepcopy(parent);dx=1./row['ratio'];child.update(shape=[8,8,8],dx=dx,spacing=dx,origin=[2+dx/2,2+dx/2,dx/2]);child['neutral_precursor']['reference_height_m']=2.
    def solid(spec):
        n=np.array(spec['shape']);p=np.indices(tuple(n+2)).reshape(3,-1).T-1;p=np.array(spec['origin'])+p*spec['dx']
        x=(1.,3.) if row['geometry']=='cropped' else (4.,5.)
        h=(p[:,0]>=x[0])&(p[:,0]<x[1])&(p[:,1]>=4)&(p[:,1]<5)&(p[:,2]<2)
        if row['geometry']=='empty':h[:]=False
        h=h.reshape(tuple(n+2));spec['solid']=np.flatnonzero(h[1:-1,1:-1,1:-1]).tolist();spec['solid_halo']=np.flatnonzero(h).tolist();return h[1:-1,1:-1,1:-1]
    mask=solid(parent);solid(child)
    if row['roughness']=='regional':child=apply(child,[dict(polygon=[[0,0],[7,0],[7,7],[0,7]],length_m=.002)])['case']
    vector={'through':[.4,.01,0],'side':[.01,.4,0],'top':[.2,0,-.02],'reverse':[-.4,.01,0]}[row['direction']]
    z=np.indices(parent['shape'])[2];shape=tuple(parent['shape']);frames=[]
    for i,t in enumerate((0.,.5)):
        u=np.asarray(vector,np.float32)[:,None,None,None]*np.broadcast_to((z+.5)/12,shape)[None]*(1+.01*i);u[:,mask]=0
        meta=dict(case=parent,time=t,iteration=i,quality=dict(policy='hawa-low-mach-v1',status='within-tested-envelope',finite=True,positive_density=True,transfer_eligible=True,transfer_scope='experimental-neutral-nesting',physical_model_status='manufactured-fixture'))
        name='frame%d.npz'%i;np.savez_compressed(root/name,velocity=u.astype(np.float32),pressure=np.zeros(shape,np.float32),density=np.ones(shape,np.float32)*1.225,solid=mask,metadata=np.array(json.dumps(meta)));frames.append(dict(file=name,time=t,iteration=i))
    path=root/'manifest.json';path.write_text(json.dumps(dict(case=parent,frames=frames,complete=True)))
    if row['mode']=='precursor':child['neutral_precursor']['mode']='precursor';child.pop('boundary_set');child.pop('boundary_method')
    if row['mode']=='legacy':child.pop('neutral_precursor');child.pop('boundary_set');child.pop('boundary_method');child['collision']='regularized';child['viscosity']=.1
    # A v2 service must reject unrelated child capabilities; do not silently
    # dispatch legacy v1 for the unsupported rows in this family.
    from hawa.boundary_series import capture as capture_v2
    result=capture_v2(path,child,root/'boundary.npz');session=Session(result['case'],device)
    if row['duration']=='exhausted':session.start(10000)
    else:
        session.advance(8);assert session.quality['finite'] and session.quality['positive_density']
        assert abs(session.solver.external_links.report['mass_budget_residual_lu'])<1e-4
