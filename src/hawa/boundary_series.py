"""BoundarySeries v2: bounded offline, multi-face neutral-flow nesting.

World geometry is in SI. Arrays contain child-axis velocity and gauge pressure;
full initial fields avoid starting a nested wake from an unrelated log profile.
Numerical health, model validation and sampling adequacy remain separate.
"""
import copy
import itertools
import math
import json
from pathlib import Path
import zipfile
import numpy as np
import torch
from .boundary_data import MAX_BYTES, digest, geometry, grid_key
from .boundary_contracts import FACES

SCHEMA = 'hawa-boundary-series-2'
SERIES_MAX_BYTES = 256*1024**2


def solid_mask(spec):
    value=np.zeros(spec['shape'],bool);value.flat[spec.get('solid',[])]=True
    return value


def geometry_key(spec):
    import hashlib
    return hashlib.sha256(json.dumps(dict(grid=grid_key(spec),solid=sorted(spec.get('solid',[])),halo=sorted(spec.get('solid_halo',[]))),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def active_faces(spec):
    patches=spec.get('boundary_set',{}).get('patches',[])
    faces=[f for f in FACES if any(p.get('face')==f and p.get('condition',{}).get('type') in ('velocity','open') for p in patches)]
    if not spec.get('neutral_precursor',{}).get('mode')=='external' or not faces:
        raise ValueError('BoundarySeries v2 requires a neutral external child with velocity/open patches')
    return faces


def layout(spec, faces):
    n=np.asarray(spec['shape']); mask=np.zeros(tuple(n),bool)
    for face in faces:
        i=FACES.index(face);index=[slice(None)]*3;index[i//2]=-1 if i%2 else 0;mask[tuple(index)]=True
    indices=np.column_stack(np.nonzero(mask))
    return indices,solid_mask(spec)[tuple(indices.T)]


def numerical_quality(q):
    return (q.get('policy')=='hawa-low-mach-v1' and q.get('status')=='within-tested-envelope'
            and q.get('finite',True) and q.get('positive_density',True))


def read(path, expected_hash=None):
    path=Path(path)
    if expected_hash and digest(path)!=expected_hash:raise ValueError('Boundary file changed; import again')
    if path.stat().st_size>SERIES_MAX_BYTES:raise ValueError('Boundary series exceeds 256 MiB budget')
    with zipfile.ZipFile(path) as z:
        if sum(v.file_size for v in z.infolist())>SERIES_MAX_BYTES:raise ValueError('Expanded boundary series exceeds 256 MiB')
    names=('times','indices','solid','velocity','pressure','initial_velocity','initial_pressure','world_m','strain_rate','initial_strain_rate','initial_wall_velocity')
    with np.load(path,allow_pickle=False) as z:
        meta=json.loads(str(z['metadata']));arrays={name:z[name] for name in names if name in z}
    if meta.get('schema')!=SCHEMA:raise ValueError('Unsupported boundary schema')
    if not set(names[:8]).issubset(arrays):raise ValueError('Boundary series is missing required arrays')
    grid=meta.get('grid',{});n=grid.get('shape',[])
    if len(n)!=3 or any(type(v) is not int or v<3 for v in n) or math.prod(n)>2_000_000:raise ValueError('Invalid boundary grid')
    times=arrays['times'];indices=arrays['indices'];m=len(indices)
    if times.ndim!=1 or not 2<=len(times)<=1000 or not np.isfinite(times).all() or times[0]!=0 or np.any(np.diff(times)<=0):raise ValueError('Boundary times must start at zero and strictly increase; 2..1000 frames')
    if indices.shape!=(m,3) or not np.issubdtype(indices.dtype,np.integer) or np.any(indices<0) or np.any(indices>=n):raise ValueError('Invalid boundary indices')
    faces=meta.get('faces',[])
    if not faces or len(set(faces))!=len(faces) or any(f not in FACES for f in faces):raise ValueError('Invalid mapped faces')
    pseudo=dict(shape=n,dx=grid.get('dx_m',0),origin=grid.get('origin_m'),basis=grid.get('basis'))
    expected,_=layout(pseudo,faces)
    if not np.array_equal(indices,expected):raise ValueError('Boundary indices must exactly cover the selected faces')
    shapes=dict(solid=(m,),velocity=(len(times),3,m),pressure=(len(times),m),initial_velocity=(3,*n),initial_pressure=tuple(n),world_m=(m,3))
    if 'strain_rate' in arrays or 'initial_strain_rate' in arrays:shapes.update(strain_rate=(len(times),3,3,m),initial_strain_rate=(3,3,*n))
    if 'initial_wall_velocity' in arrays:shapes['initial_wall_velocity']=(3,*n[:2])
    for name,shape in shapes.items():
        if name not in arrays or arrays[name].shape!=shape or not np.isfinite(arrays[name]).all():raise ValueError('Invalid boundary '+name+' shape or values')
    if arrays['solid'].dtype!=bool:raise ValueError('Boundary solid mask must be boolean')
    o,b,dx=geometry(pseudo)
    if not np.allclose(arrays['world_m'],o+indices@b*dx,rtol=0,atol=1e-9*max(1.,dx)):raise ValueError('Boundary world coordinates do not match grid')
    if not numerical_quality(meta.get('quality',{})):raise ValueError('Source numerical quality does not permit transfer')
    source=meta.get('source',{})
    if not isinstance(source.get('case'),dict) or not isinstance(source.get('frame_sha256'),list) or len(source['frame_sha256'])!=len(times):raise ValueError('Boundary source provenance is incomplete')
    if any(not isinstance(source.get(k),(float,int)) or not np.isfinite(source[k]) or source[k]<0 for k in ('absolute_start_seconds','time_offset_seconds')):raise ValueError('Boundary source clock must be finite and nonnegative')
    return arrays,meta


def validate_attachment(spec, arrays, meta):
    if grid_key(spec)!=meta['grid']:raise ValueError('Boundary dataset belongs to a different child grid')
    if geometry_key(spec)!=meta.get('child_geometry_sha256'):raise ValueError('Child solid/halo geometry changed; capture boundary data again')
    if active_faces(spec)!=meta['faces']:raise ValueError('Exterior face layout changed; capture boundary data again')
    if 'initial_wall_velocity' in arrays:
        c=spec['neutral_precursor'];model=dict(sample_height_m=(c.get('wall_sample_index',0)+.5)*spec['dx'],filter_seconds=c.get('wall_filter_seconds',0.))
        if meta.get('initial_wall_model')!=model:raise ValueError('Wall sampling/filter changed; capture boundary data again')
    speed=max(float(np.linalg.norm(arrays['velocity'],axis=1).max()),float(np.linalg.norm(arrays['initial_velocity'],axis=0).max()))
    maximum=speed*spec.get('mach',.05)/spec['speed']
    if maximum>.1:raise ValueError('Imported velocity exceeds child lattice Mach 0.10 budget')
    pressure=max(float(np.abs(arrays['pressure']).max()),float(np.abs(arrays['initial_pressure']).max()))
    if pressure/spec.get('density',1.225)*(spec.get('mach',.05)/spec['speed'])**2>.02:raise ValueError('Imported pressure exceeds 2% density budget')
    return maximum


def attach(path, spec):
    from .plugin import check_case
    sha=digest(path);arrays,meta=read(path,sha)
    maximum=validate_attachment(spec,arrays,meta)
    result=copy.deepcopy(spec)
    for patch in result['boundary_set']['patches']:
        if patch['face'] in meta['faces']:patch['condition']['profile']='mapped'
    result['boundary_field']=dict(schema=SCHEMA,path=str(Path(path).resolve()),sha256=sha,grid=meta['grid'],end_time=float(arrays['times'][-1]),faces=meta['faces'],geometry_sha256=meta['child_geometry_sha256'])
    result['time_origin_seconds']=meta['source']['absolute_start_seconds']
    check_case(result)
    return dict(case=result,report=dict(schema=SCHEMA,frames=len(arrays['times']),duration_seconds=float(arrays['times'][-1]),max_imported_lattice_mach=maximum,
        faces=meta['faces'],source=meta['source'],quality=meta['quality'],sampling=meta['sampling'],initialization='mapped velocity/pressure; regularized strain reconstruction',
        qualification='Experimental nesting; numerical health is not atmospheric validation'))


def sample_parent(arrays,parent,world,child_solid,checkpoint=lambda n:None,return_strain=False):
    """Vectorized fluid trilinear samples with a bounded modelled-ground extension.

    Renormalise mixed solid/fluid stencils; never use solid values or search across
    an obstacle. Missing fluid support fails. No side/top extrapolation.
    """
    origin,basis,dx=geometry(parent);points=(np.asarray(world)-origin)@basis.T/dx
    n=np.asarray(arrays['pressure'].shape); active=~np.asarray(child_solid,bool)
    points[np.abs(points)<1e-9]=0
    ground=(points[:,2]<0)&(points[:,2]>=-.5-1e-9)&active
    factors=np.ones((len(points),3))
    if ground.any():
        c=parent.get('neutral_precursor')
        if not c:raise ValueError('Child below parent sampling planes requires a declared neutral wall law')
        height=(points[ground,2]+.5)*dx
        from .roughness import grid as roughness_grid
        rough=roughness_grid(parent);xy=np.clip(points[ground,:2],0,n[:2]-1);lower=np.floor(xy).astype(int);upper=np.minimum(lower+1,n[:2]-1);weight=xy-lower
        z0=sum(np.prod(np.where(corner,weight,1-weight),axis=1)*rough[tuple(np.where(corner,upper,lower).T)] for corner in itertools.product((0,1),repeat=2))
        factors[ground,:2]=(np.log1p(height/z0)/np.log1p(.5*dx/z0))[:,None]
        factors[ground,2]=(height/(.5*dx))
        points[ground,2]=0
    points[np.abs(points-(n-1))<1e-9]=np.broadcast_to(n-1,points.shape)[np.abs(points-(n-1))<1e-9]
    if np.any(active & (np.any(points<0,axis=1)|np.any(points>n-1,axis=1))):raise ValueError('Child fluid has missing parent coverage; enlarge the parent domain')
    points=np.clip(points,0,n-1);lo=np.floor(points).astype(int);hi=np.minimum(lo+1,n-1);w=points-lo
    velocity=np.zeros((len(points),3));pressure=np.zeros(len(points));support=np.zeros(len(points));solid=arrays.get('solid',np.zeros(tuple(n),bool))
    if return_strain:
        strain_source=arrays.get('strain_rate')
        if strain_source is None:
            grad=np.array([np.gradient(v,dx,edge_order=2) for v in arrays['velocity']]);strain_source=.5*(grad+grad.swapaxes(0,1))
        strain=np.zeros((len(points),3,3))
    for corner in itertools.product((0,1),repeat=3):
        checkpoint(0);ix=np.where(corner,hi,lo);weight=np.prod(np.where(corner,w,1-w),axis=1);weight*=~solid[tuple(ix.T)]
        support+=weight
        velocity+=weight[:,None]*arrays['velocity'][:,ix[:,0],ix[:,1],ix[:,2]].T
        pressure+=weight*arrays['pressure'][tuple(ix.T)]
        if return_strain:strain+=weight[:,None,None]*strain_source[:,:,ix[:,0],ix[:,1],ix[:,2]].transpose(2,0,1)
    if np.any(active&(support<1e-8)):raise ValueError('Child fluid has no parent fluid support; move the boundary or resolve the parent geometry')
    velocity/=np.maximum(support[:,None],1e-30);pressure/=np.maximum(support,1e-30)
    if return_strain:
        strain/=np.maximum(support[:,None,None],1e-30)
        if ground.any():
            for axis in (0,1):strain[ground,axis,2]=strain[ground,2,axis]=.5*velocity[ground,axis]/(np.log1p(.5*dx/z0)*(height+z0))
            strain[ground,2,2]=velocity[ground,2]/(.5*dx)
        strain[~active]=0
    velocity*=factors;velocity[~active]=0;pressure[~active]=0
    result=(velocity@basis,pressure,dict(ground_extended=int(ground.sum()),partial_fluid_stencil=int((active&(support<1-1e-7)).sum()),minimum_fluid_support=float(support[active].min()) if active.any() else 0.))
    return result+(np.einsum('ai,nab,bj->nij',basis,strain,basis),) if return_strain else result


def capture(manifest,spec,path,checkpoint=lambda n:None,start_time=0.,end_time=None):
    from .recording import read_manifest
    from .fields import read_frame
    from .plugin import check_case
    check_case(spec);faces=active_faces(spec);indices,solid=layout(spec,faces)
    root,recording,_=read_manifest(manifest)
    if not recording.get('complete'):raise ValueError('Parent recording must be complete')
    if not np.isfinite(start_time) or start_time<0 or (end_time is not None and (not np.isfinite(end_time) or end_time<=start_time)):raise ValueError('Invalid capture time window')
    entries=[e for e in recording['frames'] if e['time']>=start_time-1e-10 and (end_time is None or e['time']<=end_time+1e-10)]
    n=spec['shape'];m=len(indices)
    if not 2<=len(entries)<=1000:raise ValueError('Capture window needs 2..1000 recorded frames')
    if len(entries)*13*m*4+np.prod(n)*13*4+indices.nbytes*4>SERIES_MAX_BYTES//2:raise ValueError('Boundary capture exceeds 128 MiB array budget; shorten the window or reduce frame cadence')
    origin,basis,dx=geometry(spec);world=origin+indices@basis*dx
    initial_indices=np.indices(n).reshape(3,-1).T;initial_world=origin+initial_indices@basis*dx
    child_solid=solid_mask(spec)
    source_hash=digest(root);hashes=[];velocities=[];pressures=[];strains=[];times=[];qualities=[];sampling=[];stress_sources=set();initial_wall=None
    for i,entry in enumerate(entries):
        checkpoint(i);frame_path=root.parent/entry['file'];before=digest(frame_path);arrays,meta=read_frame(frame_path)
        if meta['case']!=recording['case'] or not np.isclose(meta['time'],entry['time'],rtol=0,atol=1e-10):raise ValueError('Recording frame provenance does not match manifest')
        if not numerical_quality(meta.get('quality',{})):raise ValueError('Parent numerical quality does not permit transfer; re-record with diagnostics')
        v,p,report,strain=sample_parent(arrays,meta['case'],world,solid,checkpoint,True)
        strains.append(np.einsum('ia,nab,jb->ijn',basis,strain,basis));stress_sources.add('kinetic' if 'strain_rate' in arrays else 'finite-difference')
        velocities.append((v@basis.T).T);pressures.append(p);times.append(meta['time']);sampling.append(report);qualities.append(meta['quality'])
        if i==0:
            v0,p0,initial_report,strain0=sample_parent(arrays,meta['case'],initial_world,child_solid.ravel(),checkpoint,True)
            initial_strain=np.einsum('ia,nab,jb->ijn',basis,strain0,basis).reshape(3,3,*n)
            initial_velocity=(v0@basis.T).T.reshape(3,*n);initial_pressure=p0.reshape(n)
            initial_wall=sample_wall_history(arrays,meta['case'],spec,checkpoint)
        if before!=digest(frame_path):raise ValueError('Parent frame changed during capture')
        hashes.append(before)
    if digest(root)!=source_hash:raise ValueError('Parent recording changed during capture')
    offset=float(times[0]);times=np.asarray(times)-offset
    meta=dict(schema=SCHEMA,grid=grid_key(spec),faces=faces,child_geometry_sha256=geometry_key(spec),units='m/s; gauge Pa; seconds; metres',
        source=dict(manifest_sha256=source_hash,frame_sha256=hashes,case=recording['case'],time_offset_seconds=offset,absolute_start_seconds=float(recording['case'].get('time_origin_seconds',0.))+offset,
                    physical_model_status=qualities[0].get('physical_model_status','not-assessed'),numerical_quality_checked_frames=len(qualities)),
        quality=dict(qualities[-1],transfer_eligible=True,transfer_scope='experimental-neutral-nesting'),
        sampling=dict(method='trilinear fluid-normalized; neutral-ground extension; linear time; no side/top extrapolation',stress_sources=sorted(stress_sources),initial=initial_report,wall_history='mapped at equal physical sample height' if initial_wall is not None else 'reset from mapped initial velocity; spin-up required',
                      ground_extended=max(r['ground_extended'] for r in sampling),partial_fluid_stencil=max(r['partial_fluid_stencil'] for r in sampling),minimum_fluid_support=min(r['minimum_fluid_support'] for r in sampling),
                      max_frame_interval_seconds=float(np.diff(times).max()),parent_to_child_spacing_ratio=recording['case']['dx']/spec['dx']))
    if initial_wall is not None:
        c=spec['neutral_precursor'];meta['initial_wall_model']=dict(sample_height_m=(c.get('wall_sample_index',0)+.5)*spec['dx'],filter_seconds=c.get('wall_filter_seconds',0.))
    checkpoint(len(entries));path=Path(path)
    with path.open('xb') as f:
        try:np.savez_compressed(f,times=times,indices=indices,solid=solid,velocity=np.asarray(velocities,np.float32),pressure=np.asarray(pressures,np.float32),
                               initial_velocity=initial_velocity.astype(np.float32),initial_pressure=initial_pressure.astype(np.float32),strain_rate=np.asarray(strains,np.float32),initial_strain_rate=initial_strain.astype(np.float32),world_m=world,metadata=np.array(json.dumps(meta)),**({'initial_wall_velocity':initial_wall.astype(np.float32)} if initial_wall is not None else {}))
        except BaseException:f.close();path.unlink();raise
    try:return attach(path,spec)
    except BaseException:path.unlink();raise


def sample_wall_history(arrays,parent,child,checkpoint=lambda n:None):
    """Transfer filter memory only between coincident ground/sample planes.

    A changed physical sample height or filter time defines a different model
    state. Initialize that state from the mapped velocity instead and report the
    required adjustment; do not silently stretch a wall history vertically.
    """
    if 'wall_velocity' not in arrays:return None
    pc=parent.get('neutral_precursor',{});cc=child.get('neutral_precursor',{})
    po,pb,pdx=geometry(parent);co,cb,cdx=geometry(child)
    ph=(pc.get('wall_sample_index',0)+.5)*pdx;ch=(cc.get('wall_sample_index',0)+.5)*cdx
    if (not np.allclose(pb[2],cb[2],rtol=0,atol=1e-10) or
        abs(((co-.5*cdx*cb[2])-(po-.5*pdx*pb[2]))@pb[2])>1e-9 or
        not np.isclose(ph,ch,rtol=0,atol=1e-10) or
        pc.get('wall_filter_seconds',0.)!=cc.get('wall_filter_seconds',0.)):return None
    nx,ny=child['shape'][:2];xy=np.indices((nx,ny)).reshape(2,-1).T
    world=co+np.column_stack((xy,np.zeros(len(xy))))@cb*cdx
    # A constant-in-Z helper field lets the existing fluid-aware interpolator
    # map the wall-plane memory without copying through solid columns.
    ground_solid=arrays.get('solid',np.zeros(parent['shape'],bool))[:,:,0]
    proxy=dict(pressure=np.zeros((*parent['shape'][:2],3)),
        velocity=np.broadcast_to(arrays['wall_velocity'][...,None],(3,*parent['shape'][:2],3)),
        solid=np.broadcast_to(ground_solid[...,None],(*parent['shape'][:2],3)))
    world-=((world-po)@pb[2])[:,None]*pb[2]
    child_ground=solid_mask(child)[:,:,0].ravel()
    velocity,_,_=sample_parent(proxy,parent,world,child_ground,checkpoint)
    return (velocity@cb.T).T.reshape(3,nx,ny)


class BoundarySeries:
    def __init__(self,flow,indices=None):
        ref=flow.spec['boundary_field'];self.arrays,self.meta=read(ref['path'],ref['sha256']);validate_attachment(flow.spec,self.arrays,self.meta)
        self.times=self.arrays['times'];self.flow=flow;self.cached=None
        if indices is not None:
            flat=np.ravel_multi_index(self.arrays['indices'].T,flow.resolution)
            self.columns=np.searchsorted(flat,indices)
            if np.any(self.columns>=len(flat)) or not np.array_equal(flat[self.columns],indices):raise ValueError('Missing mapped exterior link samples')
        else:self.columns=slice(None)
    def at(self,time):
        if not np.isfinite(time) or time < -1e-10 or time>self.times[-1]+1e-10:raise ValueError('Boundary time coverage exhausted')
        i=max(0,min(int(np.searchsorted(self.times,time,side='right'))-1,len(self.times)-2))
        if self.cached!=i:
            self.v=[self.flow.context.convert_to_tensor(self.arrays['velocity'][j][:,self.columns]) for j in (i,i+1)]
            self.p=[self.flow.context.convert_to_tensor(self.arrays['pressure'][j][self.columns]) for j in (i,i+1)];self.cached=i
            self.strain=[self.flow.context.convert_to_tensor(self.arrays['strain_rate'][j][:,:,self.columns]) for j in (i,i+1)] if 'strain_rate' in self.arrays else None
        w=(time-self.times[i])/(self.times[i+1]-self.times[i])
        return self.v[0]*(1-w)+self.v[1]*w,self.p[0]*(1-w)+self.p[1]*w

    def strain_at(self,time):
        self.at(time)
        if self.strain is None:return None
        w=(time-self.times[self.cached])/(self.times[self.cached+1]-self.times[self.cached])
        return self.strain[0]*(1-w)+self.strain[1]*w
