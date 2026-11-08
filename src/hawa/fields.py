"""Immutable field frames and geometry extraction in lattice coordinates."""
from collections import OrderedDict
import itertools
import json
from pathlib import Path
import threading
import uuid
import numpy as np

FRAMES=OrderedDict()
LOCK=threading.Lock()
MAX_BYTES=256*1024**2


def capture(session, mean=False):
    with session.lock:
        arrays=session.fields(mean)
        meta={'iteration':session.flow.i,'time':session.flow.units.convert_time_to_pu(session.flow.i),
              'case':{**session.spec,'physical_dx':float(session.flow.units.convert_length_to_pu(1))},'mean':mean,'samples':session.samples}
    return store(arrays,meta)


def store(arrays,meta):
    required={'velocity','pressure','density'}
    if not required.issubset(arrays) or not isinstance(meta.get('case'),dict):
        raise ValueError('Frame requires velocity, pressure, density and case metadata')
    shape=arrays['pressure'].shape
    if len(shape) not in (2,3) or min(shape)<3 or arrays['velocity'].shape!=(len(shape),)+shape or arrays['density'].shape!=shape:
        raise ValueError('Frame field shapes do not match a 2D or 3D lattice')
    if any(not np.isfinite(arrays[k]).all() for k in required):
        raise ValueError('Frame fields must be finite')
    if 'solid' in arrays and (arrays['solid'].shape!=shape or arrays['solid'].dtype!=bool):
        raise ValueError('Frame solid mask must be a matching boolean array')
    size=sum(a.nbytes for a in arrays.values())
    if size>MAX_BYTES:raise ValueError('Frame exceeds 256 MiB budget')
    for a in arrays.values():a.setflags(write=False)
    key=str(uuid.uuid4())
    with LOCK:
        while FRAMES and (len(FRAMES)>=16 or size+sum(v[2] for v in FRAMES.values())>MAX_BYTES):FRAMES.popitem(last=False)
        FRAMES[key]=(arrays,meta,size)
    return {'frame':key,**meta}


def get(key):
    with LOCK:
        if key not in FRAMES:raise ValueError('Frame expired. Capture or load the frame again.')
        return FRAMES[key][:2]


def scalar(fields, name, spec):
    u=fields['velocity'];speed=np.linalg.norm(u,axis=0)
    if name=='speed':return speed
    if name in ('pressure','density'):return fields[name]
    if name in ('ux','uy','uz'):
        axis=('ux','uy','uz').index(name)
        return u[axis] if axis<len(u) else np.zeros_like(speed)
    if name=='cp':return (fields['pressure']-spec.get('reference_pressure',0))/(.5*spec.get('density',1.225)*spec.get('speed',1)**2)
    if name in ('vorticity','q'):
        d=len(u);g=np.zeros((3,3)+speed.shape)
        for i in range(d):
            for j in range(d):g[i,j]=np.gradient(u[i],spec.get('physical_dx',spec.get('dx',1)),axis=j,edge_order=2)
        if name=='vorticity':return np.sqrt((g[2,1]-g[1,2])**2+(g[0,2]-g[2,0])**2+(g[1,0]-g[0,1])**2)
        sym=(g+g.swapaxes(0,1))/2;rot=(g-g.swapaxes(0,1))/2
        return .5*np.sum(rot*rot-sym*sym,axis=(0,1))
    raise ValueError('Field: speed, pressure, density, ux, uy, uz, cp, vorticity or q')


def validity_mask(fields,name):
    """Exclude derivative stencils that touch a solid or a domain edge."""
    solid=fields.get('solid',np.zeros(fields['pressure'].shape,bool))
    if name not in ('vorticity','q'):return solid
    mask=solid.copy()
    for axis in range(solid.ndim):
        mask |= np.roll(solid,1,axis) | np.roll(solid,-1,axis)
        first=[slice(None)]*solid.ndim;first[axis]=0;mask[tuple(first)]=True
        last=[slice(None)]*solid.ndim;last[axis]=-1;mask[tuple(last)]=True
    return mask


def sample_scalar(fields, points, name, spec):
    from .plugin import sample_arrays
    # The interpolator applies the same solid validity rule to all fields.
    values=scalar(fields,name,spec)
    proxy={**fields,'pressure':values,'solid':validity_mask(fields,name)}
    rows=sample_arrays(proxy,points)
    return [r['pressure'] if r else 0. for r in rows],[r is not None for r in rows]


def isosurface(values, level, solid=None, stride=1, max_faces=100000, checkpoint=lambda n:None):
    if values.ndim!=3:raise ValueError('Isosurfaces require a 3D field')
    if not np.isfinite(level):raise ValueError('Level must be finite')
    stride=int(stride)
    if not 1<=stride<=16:raise ValueError('Stride must be 1..16')
    v=values[::stride,::stride,::stride];mask=solid[::stride,::stride,::stride] if solid is not None else np.zeros(v.shape,bool)
    offsets=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]])
    cells=tuple(n-1 for n in v.shape)
    corners=np.stack([v[o[0]:o[0]+cells[0],o[1]:o[1]+cells[1],o[2]:o[2]+cells[2]] for o in offsets])
    valid=np.ones(cells,bool)
    for o in offsets:valid &= ~mask[o[0]:o[0]+cells[0],o[1]:o[1]+cells[1],o[2]:o[2]+cells[2]]
    if stride>1:
        source_mask=solid if solid is not None else np.zeros(values.shape,bool)
        for offset in itertools.product(range(stride+1),repeat=3):
            valid &= ~source_mask[tuple(slice(o,o+cells[a]*stride,stride) for a,o in enumerate(offset))]
    candidates=np.argwhere(valid & (corners.min(axis=0)<=level)&(corners.max(axis=0)>level))
    tetra=[(0,5,1,6),(0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6)]
    vertices=[];faces=[]
    for cell_index,cell in enumerate(candidates):
        if cell_index%128==0:checkpoint(cell_index)
        pts=offsets+cell;vals=np.array([v[tuple(p)] for p in pts])
        for ids in tetra:
            polygon=[]
            for a,b in itertools.combinations(ids,2):
                if (vals[a]<=level)!=(vals[b]<=level):polygon.append(pts[a]+(level-vals[a])/(vals[b]-vals[a])*(pts[b]-pts[a]))
            if len(polygon)<3:continue
            polygon=np.unique(np.round(polygon,12),axis=0)
            if len(polygon)<3:continue
            center=polygon.mean(axis=0);u=polygon[0]-center;u/=np.linalg.norm(u)
            normal=np.cross(polygon[1]-polygon[0],polygon[2]-polygon[0]);norm=np.linalg.norm(normal)
            if norm<1e-12:continue
            normal/=norm;w=np.cross(normal,u)
            polygon=polygon[np.argsort(np.arctan2((polygon-center)@w,(polygon-center)@u))]
            start=len(vertices);vertices.extend((polygon*stride).tolist())
            for j in range(1,len(polygon)-1):faces.append([start,start+j,start+j+1])
            if len(faces)>max_faces:raise ValueError('Isosurface exceeds face budget. Increase stride or restrict the domain.')
    return {'vertices':vertices,'faces':faces}


def contours(points, values, valid, shape, levels, checkpoint=lambda n:None):
    points=np.asarray(points);values=np.asarray(values);valid=np.asarray(valid);lines=[]
    nx,ny=shape
    for level in levels:
        if not np.isfinite(level):raise ValueError('Contour levels must be finite')
        for i in range(nx-1):
            checkpoint(i)
            for j in range(ny-1):
                a=i*ny+j
                for ids in ([a,a+ny,a+ny+1],[a,a+ny+1,a+1]):
                    if not valid[ids].all():continue
                    cut=[]
                    for x,y in itertools.combinations(ids,2):
                        if (values[x]<=level)!=(values[y]<=level):cut.append((points[x]+(level-values[x])/(values[y]-values[x])*(points[y]-points[x])).tolist())
                    if len(cut)==2:lines.append(cut)
    return lines


def trace(fields, seeds, steps=200, step=.4, direction=1, name='speed', spec=None, checkpoint=lambda n:None):
    from .plugin import sample_arrays
    if len(seeds)>2000 or not 1<=steps<=2000 or not .01<=step<=1 or direction not in (-1,1):
        raise ValueError('Trace limits: 2000 seeds/steps, step .01..1, direction -1 or 1')
    paths=[];colors=[];total=0
    proxy={**fields,"pressure":scalar(fields,name,spec or {})}
    def tangent(p):
        r=sample_arrays(fields,[p])[0]
        if r is None or r['speed']<1e-10:return None
        return np.asarray(r['velocity'])*direction/r['speed']
    for seed in seeds:
        p=np.asarray(seed,float);path=[]
        for iteration in range(steps):
            if iteration%16==0:checkpoint(iteration)
            k1=tangent(p)
            if k1 is None:break
            total+=1
            if total>100000:raise ValueError('Flow display exceeds 100000 points. Reduce seeds or steps.')
            path.append(p.tolist())
            k2=tangent(p+step*k1/2)
            if k2 is None:break
            k3=tangent(p+step*k2/2)
            if k3 is None:break
            k4=tangent(p+step*k3)
            if k4 is None:break
            p=p+step*(k1+2*k2+2*k3+k4)/6
        if len(path)>1:
            paths.append(path);colors.append([r['pressure'] if r else 0. for r in sample_arrays(proxy,path)])
    return {'paths':paths,'values':colors}


def dispatch_field(request, session=None, checkpoint=lambda n:None):
    action=request['action']
    if action=='capture':return capture(session,request.get('mean',False))
    if action=='load':
        with np.load(request['path'],allow_pickle=False) as data:
            meta=json.loads(str(data['metadata']))
            return store({k:data[k].copy() for k in ('velocity','pressure','density','solid') if k in data},meta)
    fields,meta=get(request['frame']);spec=meta['case'];name=request.get('field','speed')
    if action=='save':
        path=Path(request['path']);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb') as f:np.savez_compressed(f,**fields,metadata=np.array(json.dumps(meta)))
        return {'path':str(path)}
    if action=='trace':return {**trace(fields,request['seeds'],request.get('steps',200),request.get('step',.4),request.get('direction',1),name,spec,checkpoint),**meta}
    if action=='plane':
        values,valid=sample_scalar(fields,request['points'],name,spec)
        return {'values':values,'valid':valid,'lines':contours(request['points'],values,valid,request['shape'],request.get('levels',[]),checkpoint),**meta}
    if action=='sample':
        if len(request['points'])>10000:raise ValueError('At most 10000 samples')
        values,valid=sample_scalar(fields,request['points'],name,spec)
        return {'values':values,'valid':valid,**meta}
    if action=='isosurface':return {**isosurface(scalar(fields,name,spec),request['level'],validity_mask(fields,name),request.get('stride',1),checkpoint=checkpoint),**meta}
    if action=='contours':
        values,valid=sample_scalar(fields,request['points'],name,spec)
        return {'lines':contours(request['points'],values,valid,request['shape'],request['levels'],checkpoint),**meta}
    raise ValueError('Unknown field operation')
