"""Immutable field frames and geometry extraction in lattice coordinates."""
from collections import OrderedDict
import itertools
import json
import os
from pathlib import Path
import threading
import tempfile
import uuid
import zipfile
import numpy as np

FRAMES=OrderedDict()
LOCK=threading.Lock()
MAX_BYTES=256*1024**2


def capture(session, mean=False):
    with session.lock:
        arrays=session.fields(mean)
        meta={'iteration':session.flow.i,'time':session.flow.units.convert_time_to_pu(session.flow.i),
              'case':{**session.spec,'physical_dx':float(session.flow.units.convert_length_to_pu(1))},'mean':mean,'samples':session.samples,'quality':dict(session.quality)}
        if hasattr(session.solver,"moving"):meta["motion"]=session.solver.moving.metadata()
    return store(arrays,meta)


def validate(arrays,meta):
    required={'velocity','pressure','density'}
    if not required.issubset(arrays) or not isinstance(meta,dict) or not isinstance(meta.get('case'),dict):
        raise ValueError('Frame requires velocity, pressure, density and case metadata')
    shape=arrays['pressure'].shape
    if len(shape) not in (2,3) or min(shape)<3 or arrays['velocity'].shape!=(len(shape),)+shape or arrays['density'].shape!=shape:
        raise ValueError('Frame field shapes do not match a 2D or 3D lattice')
    if any(not np.isfinite(arrays[k]).all() for k in required):
        raise ValueError('Frame fields must be finite')
    if np.any(arrays['density']<=0):raise ValueError('Frame density must be positive')
    for key in ('solid','boundary_nodes'):
        if key in arrays and (arrays[key].shape!=shape or arrays[key].dtype!=bool):
            raise ValueError('Frame '+key.replace('_',' ')+' mask must be a matching boolean array')
    if 'strain_rate' in arrays and (arrays['strain_rate'].shape!=(3,3)+shape or not np.isfinite(arrays['strain_rate']).all()):
        raise ValueError('Frame strain rate must be a finite 3x3 tensor on the lattice')
    if 'wall_velocity' in arrays and (arrays['wall_velocity'].shape!=(3,)+shape[:2] or not np.isfinite(arrays['wall_velocity']).all()):
        raise ValueError('Frame wall velocity must be finite on the ground plane')
    size=sum(a.nbytes for a in arrays.values())
    if size>MAX_BYTES:raise ValueError('Frame exceeds 256 MiB budget')
    return size


def read_frame(path):
    # Check expanded size before NumPy allocates compressed archive members.
    with zipfile.ZipFile(path) as archive:
        if sum(entry.file_size for entry in archive.infolist())>MAX_BYTES:
            raise ValueError('Frame exceeds 256 MiB budget')
    with np.load(path,allow_pickle=False) as data:
        meta=json.loads(str(data['metadata']))
        arrays={k:data[k] for k in ('velocity','pressure','density','solid','boundary_nodes','strain_rate','wall_velocity') if k in data}
    validate(arrays,meta)
    return arrays,meta


def store(arrays,meta):
    size=validate(arrays,meta)
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


def display_solid(fields):
    """Nodes views must not show as flow: obstacles plus no-flow boundary nodes."""
    solid=fields.get('solid',np.zeros(fields['pressure'].shape,bool))
    nodes=fields.get('boundary_nodes')
    return solid if nodes is None else solid|nodes


def lattice_weights(mask, points):
    """Halfway-wall sampling rule shared by every view.

    ``points`` are lattice coordinates (n, d). A point is valid inside the
    lattice when some unmasked corner lies within half a cell on every axis,
    so ties on a halfway wall belong to the fluid side. Returns the corner
    indices (2**d, n, d), their weights (n, 2**d) renormalised over unmasked
    corners (zero for masked ones), and the validity array (n,).
    """
    points=np.asarray(points,float).reshape(-1,mask.ndim)
    n=np.array(mask.shape);count=len(points)
    finite=np.isfinite(points).all(axis=1)
    inside=finite&np.all(np.where(np.isfinite(points),points,-1)>=0,axis=1)&np.all(np.where(np.isfinite(points),points,np.inf)<=n-1,axis=1)
    p=np.where(inside[:,None],points,0.)
    lo=np.minimum(np.floor(p).astype(int),n-1);hi=np.minimum(lo+1,n-1);w=p-lo
    corners=np.zeros((2**mask.ndim,count,mask.ndim),int);weights=np.zeros((count,2**mask.ndim));near=np.zeros(count,bool)
    for c,corner in enumerate(itertools.product((0,1),repeat=mask.ndim)):
        ix=np.where(corner,hi,lo);index=tuple(ix.T);fluid=~mask[index]
        weights[:,c]=np.prod(np.where(corner,w,1-w),axis=1)*fluid
        near|=fluid&np.all(np.abs(p-ix)<=.5+1e-9,axis=1)
        corners[c]=ix
    valid=inside&near
    support=weights.sum(axis=1)
    weights=np.where(valid[:,None],weights/np.maximum(support,1e-30)[:,None],0.)
    return corners,weights,valid


def validity_mask(fields,name):
    """Exclude derivative stencils that touch a solid or a domain edge."""
    solid=display_solid(fields)
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


CUBE=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]])
TETRA=[(0,5,1,6),(0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6)]
CORNER=np.zeros((2,2,2),int);CORNER[tuple(CUBE.T)]=np.arange(8)


def tetra_value(lo, hi, corners, points):
    """Value of a cell's marching-tetrahedra interpolant at points in the cell.

    TETRA splits the cell along the 0-6 diagonal into the six simplices that
    order the normalised coordinates, so the interpolant follows that order.
    """
    t=np.clip((points-lo)/(hi-lo),0,1);rows=np.arange(len(t));bits=np.zeros(t.shape,int)
    value=previous=corners[0]
    for axis in np.argsort(-t,axis=1,kind='stable').T:
        bits[rows,axis]=1;current=corners[CORNER[tuple(bits.T)]]
        value=value+t[rows,axis]*(current-previous);previous=current
    return value


def cell_corners(grid):
    """Stack the eight corner views of every cell in a 3D node array."""
    cells=tuple(n-1 for n in grid.shape)
    return np.stack([grid[o[0]:o[0]+cells[0],o[1]:o[1]+cells[1],o[2]:o[2]+cells[2]] for o in CUBE])


def match_faces(axes, values, corners, corner_valid):
    """Give a half-cell grid the marching-tetrahedra interpolant of each lattice
    cell edge whose two nodes, and face whose four nodes, are valid, as a
    neighbour sharing it draws.

    A neighbour drawn from its corners and a refined neighbour applying the same
    rule then meet; other edges and faces keep their samples on both sides.
    """
    lo=np.array([a[0] for a in axes],float);hi=np.array([a[-1] for a in axes],float)
    points=np.stack(np.meshgrid(*axes,indexing='ij'),-1)
    for axis in range(3):
        others=[a for a in range(3) if a!=axis]
        for sides in itertools.product((0,1),repeat=2):
            edge=(CUBE[:,others[0]]==sides[0])&(CUBE[:,others[1]]==sides[1])
            if corner_valid[edge].all():
                index=[slice(None)]*3;index[others[0]]=-sides[0];index[others[1]]=-sides[1]
                values[tuple(index)]=tetra_value(lo,hi,corners,points[tuple(index)].reshape(-1,3)).reshape(values[tuple(index)].shape)
    for axis in range(3):
        for side in (0,1):
            face=CUBE[:,axis]==side
            if corner_valid[face].all():
                index=[slice(None)]*3;index[axis]=-side
                values[tuple(index)]=tetra_value(lo,hi,corners,points[tuple(index)].reshape(-1,3)).reshape(values[tuple(index)].shape)
    return values


def leaf(axes, values, valid):
    """Final refinement level: draw cells whose corner samples are all valid."""
    return axes,values,cell_corners(valid).all(axis=0),None,None


def march(axes, values, level, full, mixed, refine, max_faces, checkpoint, out=None, drawn=()):
    """Marching tetrahedra on a rectilinear grid with masked-cell refinement.

    ``axes`` hold the grid-line coordinates and ``values`` the samples on their
    nodes. Cells marked ``full`` contain only simulated fluid and use their
    corners. Each other ``mixed`` cell is passed to ``refine(cell, extra)``,
    which returns the same five arguments for a finer grid inside it, or None
    when nothing there can cross the level, given that its boundary may also
    take values in the range ``extra``. Finer points on the boundary of a cell
    drawn from its corners take that cell's interpolant, so the surfaces meet
    on the shared face. ``drawn`` lists such cells from coarser levels.
    """
    vertices,faces=out if out is not None else ([],[])
    corners=cell_corners(values)
    for count,cell in enumerate(np.argwhere(full&(corners.min(axis=0)<=level)&(corners.max(axis=0)>level))):
        if count%128==0:checkpoint(count)
        ids=CUBE+cell;pts=np.array([[axes[a][i[a]] for a in range(3)] for i in ids]);v=values[tuple(ids.T)]
        for tet in TETRA:
            polygon=[pts[a]+(level-v[a])/(v[b]-v[a])*(pts[b]-pts[a]) for a,b in itertools.combinations(tet,2) if (v[a]<=level)!=(v[b]<=level)]
            if len(polygon)<3:continue
            polygon=np.unique(np.round(polygon,12),axis=0)
            if len(polygon)<3:continue
            center=polygon.mean(axis=0);u=polygon[0]-center;u/=np.linalg.norm(u)
            normal=np.cross(polygon[1]-polygon[0],polygon[2]-polygon[0]);norm=np.linalg.norm(normal)
            if norm<1e-12:continue
            w=np.cross(normal/norm,u)
            polygon=polygon[np.argsort(np.arctan2((polygon-center)@w,(polygon-center)@u))]
            start=len(vertices);vertices.extend(polygon.tolist())
            faces.extend([start,start+j,start+j+1] for j in range(1,len(polygon)-1))
            if len(faces)>max_faces:raise ValueError('Isosurface exceeds face budget. Increase stride or restrict the domain.')
    if mixed is not None:
        around=np.pad(full,1)
        for count,cell in enumerate(np.argwhere(mixed&~full)):
            if count%16==0:checkpoint(count)
            # Plain floats: these boxes are tested once per refined cell.
            lo=[float(axes[a][cell[a]]) for a in range(3)];hi=[float(axes[a][cell[a]+1]) for a in range(3)]
            touching=[box for box in drawn if all(box[0][a]<=hi[a]+1e-9 and box[1][a]>=lo[a]-1e-9 for a in range(3))]
            for step in np.argwhere(around[tuple(slice(c,c+3) for c in cell)])-1:
                near=tuple(int(c)+int(d) for c,d in zip(cell,step))
                if any(step):
                    touching.append(([float(axes[a][near[a]]) for a in range(3)],[float(axes[a][near[a]+1]) for a in range(3)],values[tuple((CUBE+near).T)]))
            extra=(min(box[2].min() for box in touching),max(box[2].max() for box in touching)) if touching else None
            sub=refine(tuple(cell),extra)
            if sub is None:continue
            grid,sampled=sub[:2];points=np.stack(np.meshgrid(*grid,indexing='ij'),-1)
            for box in touching:
                on=np.all((points>=np.subtract(box[0],1e-9))&(points<=np.add(box[1],1e-9)),axis=-1)
                if on.any():sampled[on]=tetra_value(np.array(box[0]),np.array(box[1]),box[2],points[on])
            march(grid,sampled,level,*sub[2:],max_faces,checkpoint,(vertices,faces),touching)
    return {'vertices':vertices,'faces':faces}


def uniform_cells(axes):
    """Cells with equal edges. A partial last cell is refined instead of drawn
    from its corners, because its face diagonals do not align with the square
    sub-cells of a refined neighbour."""
    widths=np.meshgrid(*[np.diff(a) for a in axes],indexing='ij')
    return np.isclose(widths[0],widths[1])&np.isclose(widths[1],widths[2])


def grid_lines(start, end, stride):
    """Lines every ``stride`` units from ``start``, ending exactly at ``end``."""
    return np.r_[np.arange(start,end-1e-9,stride),end]


def isosurface(values, level, solid=None, stride=1, max_faces=100000, checkpoint=lambda n:None):
    """Lattice isosurface over the fluid half-cell region.

    Coarse cells every ``stride`` nodes are drawn from their corners when every
    node inside is unmasked. Other cells are split into lattice cells, and
    lattice cells with a masked node are resampled on half-cell lines with
    fluid-normalised interpolation, so the surface stops on halfway walls at
    every stride. The last partial cell on each axis is kept.
    """
    if values.ndim!=3:raise ValueError('Isosurfaces require a 3D field')
    if not np.isfinite(level):raise ValueError('Level must be finite')
    stride=int(stride)
    if not 1<=stride<=16:raise ValueError('Stride must be 1..16')
    mask=solid if solid is not None else np.zeros(values.shape,bool)
    total=np.pad(mask.astype(np.int64).cumsum(0).cumsum(1).cumsum(2),((1,0),)*3)
    def classify(axes):
        lo=np.ix_(*[a[:-1] for a in axes]);hi=np.ix_(*[a[1:]+1 for a in axes])
        masked=sum((-1)**(3-sum(c))*total[tuple(h if k else l for k,l,h in zip(c,lo,hi))] for c in itertools.product((0,1),repeat=3))
        size=np.prod(np.meshgrid(*[np.diff(a)+1 for a in axes],indexing='ij'),axis=0)
        return masked==0,masked<size
    def box(axes, cell, extra):
        box=tuple(slice(axes[a][cell[a]],axes[a][cell[a]+1]+1) for a in range(3))
        fluid=np.r_[values[box][~mask[box]],extra or []]
        return box if len(fluid) and fluid.min()<=level<fluid.max() else None
    def half(axes, nodes, cell, extra):
        b=box(axes,cell,extra)
        if b is None:return None
        grid=[grid_lines(s.start,s.stop-1,.5) for s in b]
        corners,weights,valid=lattice_weights(mask,np.stack(np.meshgrid(*grid,indexing='ij'),-1).reshape(-1,3))
        sampled=sum(weights[:,c]*values[tuple(corners[c].T)] for c in range(len(corners)))
        shape=tuple(len(g) for g in grid);ids=tuple((CUBE+cell).T)
        # Lattice nodes carry any drawn coarse neighbour's interpolant (nodes).
        sampled=match_faces(grid,sampled.reshape(shape),nodes[ids],~mask[tuple(np.asarray(axes[a])[ids[a]] for a in range(3))])
        return leaf(grid,sampled,valid.reshape(shape))
    def unit(axes, cell, extra):
        b=box(axes,cell,extra)
        if b is None:return None
        grid=[np.arange(s.start,s.stop) for s in b];nodes=values[np.ix_(*grid)]
        return (grid,nodes)+classify(grid)+(lambda c,e:half(grid,nodes,c,e),)
    axes=[grid_lines(0,n-1,stride).astype(int) for n in values.shape]
    full,mixed=classify(axes);cubic=uniform_cells(axes);nodes=values[np.ix_(*axes)]
    refine=((lambda c,e:unit(axes,c,e)) if stride>1 else
            (lambda c,e:half(axes,nodes,c,e)))
    return march(axes,nodes,level,full&cubic,mixed|~cubic,refine,max_faces,checkpoint)


def contours(points, values, valid, shape, levels, checkpoint=lambda n:None):
    points=np.asarray(points);values=np.asarray(values);valid=np.asarray(valid);lines=[]
    if len(shape)!=2 or any(type(n) is not int or not 2<=n<=100 for n in shape) or len(points)!=shape[0]*shape[1]:
        raise ValueError('Contours require a matching 2..100 by 2..100 plane grid')
    if len(levels)>100:raise ValueError('At most 100 contour levels')
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
                    if len(cut)==2:
                        if len(lines)>=100000:raise ValueError('Contours exceed 100000 segment budget; reduce levels or resolution')
                        lines.append(cut)
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
        return np.asarray(r['velocity'])[:len(p)]*direction/r['speed']
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
    if request.get('frames') is not None:
        from .field_collection import dispatch_collection
        return dispatch_collection(request,checkpoint)
    if action=='capture':return capture(session,request.get('mean',False))
    if action=='load':
        return store(*read_frame(request['path']))
    fields,meta=get(request['frame']);spec=meta['case'];name=request.get('field','speed')
    if action=='save':
        checkpoint(0)
        metadata=np.array(json.dumps(meta))
        path=Path(request['path']);path.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            # Publish only a completed sibling file, preserving any prior export.
            with tempfile.NamedTemporaryFile(mode='wb',dir=path.parent,
                    prefix='.hawa-frame.',suffix='.tmp',delete=False) as output:
                temporary=Path(output.name)
                np.savez_compressed(output,**fields,metadata=metadata)
                output.flush()
                os.fsync(output.fileno())
            # Compression is synchronous; cancellation is observed at these boundaries.
            checkpoint(0)
            os.replace(temporary,path)
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
        return {'path':str(path)}
    if action=='trace':return {**trace(fields,request['seeds'],request.get('steps',200),request.get('step',.4),request.get('direction',1),name,spec,checkpoint),**meta}
    if action=='plane':
        # Same partition as composed views; a 2D frame is one flat lattice layer.
        from .field_collection import FieldCollection
        view=FieldCollection.lattice(fields,meta,name,checkpoint)
        points=[list(p)+[0.]*(3-len(p)) for p in request['points']]
        values,valid,_,_=view.sample(points)
        return {'values':values.tolist(),'valid':valid.tolist(),**view.plane(points,request['shape'],request.get('levels',[])),**view.meta}
    if action=='sample':
        if len(request['points'])>10000:raise ValueError('At most 10000 samples')
        values,valid=sample_scalar(fields,request['points'],name,spec)
        return {'values':values,'valid':valid,**meta}
    if action=='isosurface':return {**isosurface(scalar(fields,name,spec),request['level'],validity_mask(fields,name),request.get('stride',1),checkpoint=checkpoint),**meta}
    if action=='contours':
        values,valid=sample_scalar(fields,request['points'],name,spec)
        return {'lines':contours(request['points'],values,valid,request['shape'],request['levels'],checkpoint),**meta}
    raise ValueError('Unknown field operation')
