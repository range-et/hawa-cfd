"""World-aware views of immutable frames. This does not couple solver grids.

Finest containing domain owns a sample, including its invalid/solid mask. Equal
spacing uses input order. All frames must represent the same absolute time.
"""
import itertools
import math
import numpy as np
from .boundary_data import geometry
from .fields import lattice_weights


def frame_geometry(spec):
    # Reference examples record physical_dx without a wind-case dx/shape.
    # Their displayed coordinates remain lattice coordinates (spacing=1).
    return geometry(dict(spec,dx=spec.get('physical_dx',spec.get('dx',1.)),spacing=spec.get('spacing',spec.get('dx',1.))))


class FieldCollection:
    def __init__(self, keys, name, checkpoint=lambda n:None):
        from .fields import display_solid, get, scalar, validity_mask
        if not isinstance(keys,list) or not 1<=len(keys)<=16 or any(not isinstance(k,str) for k in keys):
            raise ValueError('Use 1..16 immutable field frames')
        self.frames=[get(k) for k in dict.fromkeys(keys)]
        if any(len(a['pressure'].shape)!=3 for a,m in self.frames):raise ValueError('Multi-domain views require 3D frames')
        first=self.frames[0][1];self.origin,self.basis,self.dx=frame_geometry(first['case'])
        times=[float(m.get('time',0))+float(m['case'].get('time_origin_seconds',0)) for a,m in self.frames]
        if not np.isfinite(times).all() or not np.allclose(times,times[0],rtol=0,atol=1e-8):
            raise ValueError('Field times differ; select frames at the same absolute physical time')
        if len({bool(m.get('mean',False)) for a,m in self.frames})!=1:raise ValueError('Do not mix mean and instantaneous frames')
        if name in ('pressure','cp') and len({m['case'].get('reference_pressure',0.) for a,m in self.frames})!=1:
            raise ValueError('Pressure references differ between domains')
        self.rows=[];self.checkpoint=checkpoint;self.name=name
        for order,(arrays,meta) in enumerate(self.frames):
            checkpoint(order);o,b,dx=frame_geometry(meta['case'])
            if name in ('ux','uy','uz'):
                axis=('ux','uy','uz').index(name)
                values=np.einsum('a,a...->...',b@self.basis[axis],arrays['velocity'])
            else:
                # Cp uses one reference speed/density across the complete view.
                spec=first['case'] if name=='cp' else meta['case']
                values=scalar(arrays,name,spec)
            self.rows.append(dict(order=order,fields=arrays,meta=meta,origin=o,basis=b,dx=dx,
                values=values,invalid=validity_mask(arrays,name),shape=np.array(arrays['pressure'].shape),
                solids=np.argwhere(display_solid(arrays))))
        self.rows.sort(key=lambda row:(row['dx'],row['order']))
        self.meta=dict(first,collection=dict(domains=len(self.rows),absolute_time_seconds=times[0],
            selection='finest containing domain; equal spacing uses input order; no fallback through finer solids',
            frame_ids=list(dict.fromkeys(keys))),case=dict(first['case']))

    def sample(self, points):
        points=np.asarray(points,float)
        if points.ndim!=2 or points.shape[1]!=3 or len(points)>10000 or not np.isfinite(points).all():
            raise ValueError('Use at most 10000 finite three-coordinate samples')
        world=self.origin+points@self.basis*self.dx
        values=np.zeros(len(points));velocity=np.zeros((len(points),3));valid=np.zeros(len(points),bool);owner=np.full(len(points),-1,int)
        for row in self.rows:
            self.checkpoint(0);p=(world-row['origin'])@row['basis'].T/row['dx'];n=row['shape']
            inside=(owner<0)&np.all(p>=-1e-9,axis=1)&np.all(p<=n-1+1e-9,axis=1)
            ids=np.flatnonzero(inside)
            if not len(ids):continue
            owner[ids]=row['order'];p=np.clip(p[ids],0,n-1)
            corners,weights,ok=lattice_weights(row['invalid'],p)
            u=np.zeros((len(ids),3));v=np.zeros(len(ids))
            for c in range(weights.shape[1]):
                ix=corners[c];index=tuple(ix.T)
                v+=weights[:,c]*row['values'][index];u+=weights[:,c,None]*row['fields']['velocity'][:,ix[:,0],ix[:,1],ix[:,2]].T
            values[ids]=np.where(ok,v,0);velocity[ids]=u@row['basis']@self.basis.T;valid[ids]=ok
        velocity[~valid]=0
        return values,valid,velocity,owner

    def trace(self,seeds,steps=200,step=.4,direction=1):
        if len(seeds)>2000 or type(steps) is not int or not 1<=steps<=2000 or not .01<=step<=1 or direction not in (-1,1):
            raise ValueError('Trace limits: 2000 seeds/steps, step .01..1, direction -1 or 1')
        # Resolve the finest grid when crossing a child; avoid jumping a thin body.
        h=step*min(row['dx'] for row in self.rows)/self.dx
        paths=[];colors=[];total=0
        def tangent(p):
            _,valid,u,_=self.sample([p]);speed=np.linalg.norm(u[0])
            return direction*u[0]/speed if valid[0] and speed>1e-10 else None
        for seed in seeds:
            p=np.asarray(seed,float);path=[]
            for iteration in range(steps):
                if iteration%16==0:self.checkpoint(iteration)
                k1=tangent(p)
                if k1 is None:break
                path.append(p.tolist());total+=1
                if total>100000:raise ValueError('Flow display exceeds 100000 points; reduce seeds or steps')
                k2=tangent(p+h*k1/2)
                if k2 is None:break
                k3=tangent(p+h*k2/2)
                if k3 is None:break
                k4=tangent(p+h*k3)
                if k4 is None:break
                p=p+h*(k1+2*k2+2*k3+k4)/6
            if len(path)>1:
                paths.append(path);colors.append(self.sample(path)[0].tolist())
        return dict(paths=paths,values=colors)

    def plane(self,points,shape,levels):
        """Clip plane triangles to the union, partitioned by domain priority.

        Domain clipping is exact for oriented box extents. Solid interpolation
        validity is still sampled; this is not a CAD surface reconstruction.
        """
        from .fields import contours
        # Reuse the public plane-grid and contour-level validation.
        contours(points,np.zeros(len(points)),np.zeros(len(points),bool),shape,levels,self.checkpoint)
        points=np.asarray(points,float);vertices=[];faces=[]
        def split(polygon,row,axis,side):
            p=np.asarray(polygon);world=self.origin+p@self.basis*self.dx
            q=(world-row['origin'])@row['basis'][axis]/row['dx']
            distance=q if side==0 else row['shape'][axis]-1-q
            inside=[];outside=[]
            for i in range(len(p)):
                j=(i+1)%len(p);a,b=distance[i],distance[j]
                (inside if a>=-1e-10 else outside).append(p[i])
                if (a>=-1e-10)!=(b>=-1e-10):
                    intersection=p[i]+a/(a-b)*(p[j]-p[i]);inside.append(intersection);outside.append(intersection)
            return inside,outside
        def partition(poly,row):
            inside=poly;outside=[]
            for axis in range(3):
                for side in (0,1):
                    if len(inside)<3:return [],outside
                    inside,part=split(inside,row,axis,side)
                    if len(part)>=3:outside.append(part)
            return inside,outside
        nx,ny=shape
        for i in range(nx-1):
            self.checkpoint(i)
            for j in range(ny-1):
                a=i*ny+j
                for tri in ((a,a+ny,a+ny+1),(a,a+ny+1,a+1)):
                    remaining=[list(points[list(tri)])]
                    for row in self.rows:
                        next_parts=[]
                        for poly in remaining:
                            inside,outside=partition(poly,row);next_parts.extend(outside)
                            if len(inside)>=3:
                                fluid=[inside]
                                if len(row['solids']) and not row['meta']['case'].get('wall_links'):
                                    world=self.origin+np.asarray(inside)@self.basis*self.dx
                                    local=(world-row['origin'])@row['basis'].T/row['dx']
                                    candidates=row['solids'][np.all(row['solids']+.5>=local.min(0)-1e-10,axis=1)&np.all(row['solids']-.5<=local.max(0)+1e-10,axis=1)]
                                    for cell in candidates:
                                        box=dict(row,origin=row['origin']+(cell-.5)@row['basis']*row['dx'],shape=np.array([2,2,2]))
                                        fluid=[part for fragment in fluid for part in partition(fragment,box)[1]]
                                        if not fluid:break
                                for fragment in fluid:
                                    start=len(vertices);vertices.extend(fragment)
                                    for k in range(1,len(fragment)-1):
                                        if np.linalg.norm(np.cross(fragment[k]-fragment[0],fragment[k+1]-fragment[0]))>1e-14:
                                            faces.append((start,start+k,start+k+1))
                        remaining=next_parts
                        if len(vertices)>100000:raise ValueError('Clipped plane exceeds 100000 vertices; reduce resolution or domains')
                        if not remaining:break
        values=[];valid=[]
        for start in range(0,len(vertices),8192):
            v,ok,_,_=self.sample(vertices[start:start+8192]);values.extend(v);valid.extend(ok)
        values=np.asarray(values);valid=np.asarray(valid,bool);vertices=np.asarray(vertices).reshape(-1,3)
        faces=[f for f in faces if valid[list(f)].all()];lines=[]
        for level in levels:
            for a,b,c in faces:
                cut=[]
                for x,y in ((a,b),(b,c),(c,a)):
                    if (values[x]<=level)!=(values[y]<=level):cut.append((vertices[x]+(level-values[x])/(values[y]-values[x])*(vertices[y]-vertices[x])).tolist())
                if len(cut)==2:lines.append(cut)
                if len(lines)>100000:raise ValueError('Contours exceed 100000 segments; reduce levels or resolution')
        return dict(mesh_vertices=vertices.tolist(),mesh_faces=faces,mesh_values=values.tolist(),lines=lines,
            display_reconstruction='Halfway solid mask clipping; samples are valid inside a fluid node\'s half-cell and interpolate fluid nodes only.')

    def isosurface(self,level,stride):
        """Composed isosurface on the finest spacing, using the single-frame rule.

        A cell is drawn from its corners when every corner is valid and no
        invalid node's half-cell reaches it. Other cells are split into finest
        cells, then half cells. The grid ends on the union bounds instead of
        overshooting them.
        """
        from .fields import cell_corners, grid_lines, leaf, march
        if type(stride) is not int or not 1<=stride<=16:raise ValueError('Stride must be 1..16')
        corners=[]
        for row in self.rows:
            local=np.array(list(itertools.product(*[(0,n-1) for n in row['shape']])))
            world=row['origin']+local@row['basis']*row['dx']
            corners.extend((world-self.origin)@self.basis.T/self.dx)
        lo=np.min(corners,axis=0);hi=np.max(corners,axis=0);h=min(row['dx'] for row in self.rows)/self.dx
        budget=[0];walls=[]
        for row in self.rows:
            # Invalid nodes own a half-cell; a cell it reaches is refined.
            nodes=np.argwhere(row['invalid'])
            t=((row['origin']+nodes@row['basis']*row['dx']-self.origin)@self.basis.T/self.dx-lo)/h
            walls.append((t[np.argsort(t[:,0])] if len(t) else t,.5*row['dx']/self.dx/h*np.abs(row['basis']@self.basis.T).sum(axis=0)))
        def classify(axes):
            points=lo+np.stack(np.meshgrid(*axes,indexing='ij'),-1).reshape(-1,3)*h;budget[0]+=len(points)
            if budget[0]>250000:raise ValueError('Multi-domain isosurface exceeds 250000 display samples; change stride or select fewer frames')
            values=[];valid=[]
            for start in range(0,len(points),8192):
                self.checkpoint(start);v,ok,_,_=self.sample(points[start:start+8192]);values.extend(v);valid.extend(ok)
            size=tuple(len(a) for a in axes);values=np.asarray(values).reshape(size);valid=np.asarray(valid,bool).reshape(size)
            reached=np.zeros(tuple(n-1 for n in size),bool)
            for t,reach in walls:
                t=t[np.searchsorted(t[:,0],axes[0][0]-reach[0]):np.searchsorted(t[:,0],axes[0][-1]+reach[0],'right')]
                first=[np.searchsorted(a,t[:,k]-reach[k]+1e-9,'right')-1 for k,a in enumerate(axes)]
                last=[np.searchsorted(a,t[:,k]+reach[k]-1e-9,'left')-1 for k,a in enumerate(axes)]
                for offset in itertools.product(*[range(int(np.max(b-a,initial=0))+1) for a,b in zip(first,last)]):
                    ix=[a+o for a,o in zip(first,offset)]
                    keep=np.all([(i<=b)&(i>=0)&(i<n) for i,b,n in zip(ix,last,reached.shape)],axis=0)
                    reached[tuple(i[keep] for i in ix)]=True
            ok=cell_corners(valid)
            # Half cells use corner validity alone: a finer domain may own fluid
            # inside a coarser domain's invalid half-cell.
            return values,valid,ok.all(axis=0)&~reached,ok.any(axis=0)|reached
        def refine(axes, values, valid, cell, step):
            if step==.5:
                # Half-cell samples interpolate the valid finest corners only.
                box=tuple(slice(i,i+2) for i in cell);fluid=values[box][valid[box]]
                if not len(fluid) or not fluid.min()<=level<fluid.max():return None
            grid=[grid_lines(axes[k][cell[k]],axes[k][cell[k]+1],step) for k in range(3)]
            sub,ok,full,mixed=classify(grid)
            if step==.5:return leaf(grid,sub,ok)
            return grid,sub,full,mixed,lambda c:refine(grid,sub,ok,c,.5)
        axes=[grid_lines(0,e,stride) for e in np.maximum((hi-lo)/h,1)]
        values,valid,full,mixed=classify(axes)
        mesh=march(axes,values,level,full,mixed,lambda c:refine(axes,values,valid,c,1 if stride>1 else .5),100000,self.checkpoint)
        mesh['vertices']=(lo+np.asarray(mesh['vertices']).reshape(-1,3)*h).tolist()
        return dict(mesh,display_sampling=dict(spacing_m=h*stride*self.dx,samples=budget[0]))


def dispatch_collection(request,checkpoint=lambda n:None):
    from .fields import contours
    view=FieldCollection(request['frames'],request.get('field','speed'),checkpoint);action=request['action']
    if action in ('sample','plane','contours'):
        values,valid,velocity,owner=view.sample(request['points'])
        result=dict(values=values.tolist(),valid=valid.tolist(),velocity=velocity.tolist(),domain_index=owner.tolist())
        if action!='sample':result.update(view.plane(request['points'],request['shape'],request.get('levels',[])))
    elif action=='trace':result=view.trace(request['seeds'],request.get('steps',200),request.get('step',.4),request.get('direction',1))
    elif action=='isosurface':result=view.isosurface(request['level'],request.get('stride',1))
    else:raise ValueError('Multi-domain views support sample, plane, contours, trace and isosurface')
    return dict(result,**view.meta)
