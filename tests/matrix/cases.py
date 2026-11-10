"""Compatibility inventory v1: explicit dimensions and independent acceptance rules.

This describes finite representative contracts, not arbitrary graphs or continuous
parameters. Add new capabilities here before advertising their combinations.
"""
import copy
import itertools
import json
from pathlib import Path
import numpy as np
import lettuce as lt

COLLISIONS = ('bgk', 'trt', 'regularized', 'smagorinsky', 'smagorinsky-v1', 'shifted-regularized-sgs-v1')
MODES = ('legacy', 'nee', 'precursor', 'external')
GEOMETRIES = ('empty', 'interior', 'curved', 'cropped', 'moving')
FACE_TYPES = ('wall', 'slip', 'periodic', 'velocity', 'open', 'pressure')
FACES = ('x-', 'x+', 'y-', 'y+', 'z-', 'z+')
DEVICES = ('cpu', 'mps', 'cuda:0')


def base(shape=(12,12,12)):
    return dict(shape=list(shape),dx=1.,spacing=1.,origin=[0.,0.,.5],speed=1.,viscosity=.1,
                density=1.225,mach=.05,collision='regularized',solid=[],
                boundaries=['inlet','outlet']+['periodic']*4)


def patches(kinds, speed=0.):
    rows=[]
    for face,kind in enumerate(kinds):
        v=[0.,0.,0.]
        if kind=='velocity': v[face//2]=speed*(1 if face%2==0 else -1)
        rows.append(dict(id=FACES[face],face=FACES[face],condition=dict(type=kind,velocity=v,pressure_pa=0.)))
    return dict(schema=1,patches=rows)


def neutral(spec, mode):
    spec['collision']=COLLISIONS[-1]
    spec['boundaries']=['periodic']*4+['wall','slip']
    spec['neutral_precursor']=dict(schema=1,experimental=True,mode=mode,
        reference_height_m=spec['shape'][2]/2,roughness_length_m=.01,perturbation_fraction=0.)


def combination_expected(mode, collision, geometry, mapped):
    if mode in ('precursor','external'):
        if collision!=COLLISIONS[-1] or mapped: return False
        return geometry=='empty' if mode=='precursor' else geometry in ('empty','interior','cropped')
    if collision==COLLISIONS[-1]:return False
    if geometry=='moving':return mode=='legacy' and collision=='bgk' and not mapped
    if geometry=='cropped' and mode=='legacy':return False
    return True


def combinations():
    for mode,collision,geometry,mapped in itertools.product(MODES,COLLISIONS,GEOMETRIES,(False,True)):
        yield dict(id='solver/'+ '/'.join((mode,collision,geometry,'mapped' if mapped else 'uniform')),
                   mode=mode,collision=collision,geometry=geometry,mapped=mapped,
                   expected=combination_expected(mode,collision,geometry,mapped))


def make_combination(row, directory):
    from hawa.boundary_data import SCHEMA,grid_key,digest
    spec=base();mode=row['mode'];geometry=row['geometry']
    if mode=='nee':
        spec.update(boundary_method='hawa-nee-v1',initial_velocity=[0.,0.,0.],
                    boundary_set=patches(('velocity','open','periodic','periodic','periodic','periodic'),1.))
    elif mode in ('precursor','external'):
        neutral(spec,mode)
        if mode=='external':spec.update(boundary_method='shifted-links-v1',boundary_set=patches(('velocity','open','periodic','periodic','wall','slip'),1.))
    spec['collision']=row['collision']
    if geometry in ('interior','curved','cropped'):
        n=np.array(spec['shape']);xyz=np.indices(tuple(n+2))-1
        occupied=(xyz[0]>=( -2 if geometry=='cropped' else 5))&(xyz[0]<=(2 if geometry=='cropped' else 6))&(xyz[1]>=5)&(xyz[1]<=6)&(xyz[2]>=4)&(xyz[2]<=5)
        spec['solid']=np.flatnonzero(occupied[1:-1,1:-1,1:-1]).tolist()
        if mode in ('precursor','external'):spec['solid_halo']=np.flatnonzero(occupied).tolist()
        if geometry=='curved':
            solid=set(spec['solid']);links=[]
            for site in solid:
                location=np.array(np.unravel_index(site,spec['shape']))
                for q,e in enumerate(lt.D3Q19().e[1:],1):
                    fluid=location-e;index=int(np.ravel_multi_index(fluid,spec['shape']))
                    if index not in solid:links.append([q,index,.5])
            spec['wall_links']=links
    elif geometry=='moving':
        spec['moving_bodies']=[dict(id='body',pivot=[6,6,6],geometry=dict(type='sphere',center=[6,6,6],radius=1.3),motion=dict(type='translation',axis=[1,0,0],speed=.05,ramp=.1))]
    if row['mapped']:
        path=Path(directory)/('boundary-'+str(len(list(Path(directory).glob('boundary-*.npz'))))+'.npz')
        velocity=np.zeros((2,3,*spec['shape'][1:]),np.float32);velocity[:,0]=1.
        meta=dict(schema=SCHEMA,grid=grid_key(spec),source=dict(test='manufactured-matrix'),quality=dict(policy='hawa-low-mach-v1',status='within-tested-envelope',transfer_eligible=True))
        np.savez_compressed(path,times=np.array([0.,1.]),velocity=velocity,metadata=np.array(json.dumps(meta)))
        spec['boundary_field']=dict(path=str(path.resolve()),sha256=digest(path),grid=grid_key(spec),end_time=1.)
        if spec.get('boundary_set'):spec['boundary_set']['patches'][0]['condition']['profile']='mapped'
    return spec


def topology_expected(mode, kinds):
    paired=all((kinds[2*a]=='periodic')==(kinds[2*a+1]=='periodic') for a in range(3))
    if not paired:return False
    if mode=='external':
        return (kinds[4]=='wall' and kinds[5] in ('slip','velocity','open') and
                all(k in ('velocity','open','periodic') for k in kinds[:4]) and 'open' in kinds)
    active={i//2 for i,k in enumerate(kinds) if k in ('velocity','open','pressure')}
    return len(active)<=1 and ('velocity' not in kinds or 'open' in kinds or 'pressure' in kinds)


def topologies():
    for mode in ('nee','external'):
        for kinds in itertools.product(FACE_TYPES,repeat=6):
            yield dict(id='faces/'+mode+'/'+','.join(kinds),mode=mode,kinds=kinds,expected=topology_expected(mode,kinds))


def make_topology(row):
    spec=base((4,4,4));spec['initial_velocity']=[0.,0.,0.]
    if row['mode']=='external':neutral(spec,'external')
    spec.update(boundary_method='shifted-links-v1' if row['mode']=='external' else 'hawa-nee-v1',boundary_set=patches(row['kinds']))
    return spec
