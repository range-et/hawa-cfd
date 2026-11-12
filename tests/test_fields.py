import numpy as np
import pytest
from hawa.fields import grid_lines,isosurface,scalar,contours


def test_plane_isosurface_and_mask():
    x=np.indices((5,5,5))[0].astype(float)
    mesh=isosurface(x,2.5)
    assert len(mesh['faces'])>0 and mesh==isosurface(x,2.5,stride=1)!=isosurface(x,2.5,stride=2)
    np.testing.assert_allclose(np.array(mesh['vertices'])[:,0],2.5)
    assert isosurface(x,2.5,np.ones_like(x,bool))['faces']==[]


def test_rigid_rotation_vorticity_q():
    x,y,z=np.indices((5,5,5));u=np.array([-y,x,0*z],float)
    fields={'velocity':u}
    np.testing.assert_allclose(scalar(fields,'vorticity',{'dx':1}),2)
    np.testing.assert_allclose(scalar(fields,'q',{'dx':1}),1)


def test_contour_crossing():
    points=[[0,0,0],[0,1,0],[1,0,0],[1,1,0]]
    lines=contours(points,[0,0,1,1],[True]*4,[2,2],[.5])
    np.testing.assert_allclose(np.array(lines)[:,:,0],.5)


def test_derivative_mask_excludes_wall_stencils():
    from hawa.fields import sample_scalar
    fields={'velocity':np.ones((3,7,7,7)), 'pressure':np.zeros((7,7,7)),
            'density':np.ones((7,7,7)), 'solid':np.zeros((7,7,7),bool)}
    fields['solid'][3,3,3]=True
    _,valid=sample_scalar(fields,[[2,3,3],[1,2,2],[0,2,2]],'q',{'dx':1})
    assert valid==[False,True,False]


def test_strided_isosurface_cannot_skip_thin_wall():
    x=np.indices((5,5,5))[0].astype(float);solid=np.zeros_like(x,bool)
    solid[1,:,:]=True
    assert isosurface(x,.5,solid,stride=2)['faces']==[]


def projected_area(mesh):
    v=np.asarray(mesh['vertices']).reshape(-1,3);f=np.asarray(mesh['faces']).reshape(-1,3)
    return np.abs(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])[:,0]).sum()/2


@pytest.mark.parametrize('stride',[1,2,3,4,16])
def test_linear_isosurface_covers_planar_fluid_area_beside_box_and_plate(stride):
    n=24;x=np.indices((n,n,n))[0]*1.7-3
    box=np.zeros(x.shape,bool);box[3:9,4:10,5:12]=True
    plate=np.zeros(x.shape,bool);plate[:,6,2:n-3]=True
    edge=np.r_[.5,np.ones(n-2),.5];half_cells=np.outer(edge,edge)
    # Isoplane x=L covers the half-cells of fluid nodes on lattice plane round(L).
    for solid in (box,plate):
        for node in (22.5,5.3,5.):
            mesh=isosurface(x,node*1.7-3,solid,stride)
            assert projected_area(mesh)==pytest.approx((half_cells*~solid[int(round(node))]).sum(),abs=1e-9)
            np.testing.assert_allclose(np.asarray(mesh['vertices'])[:,0],node)
            assert all(len(set(face))==3 for face in mesh['faces'])


def t_junctions(mesh):
    # Welded edges used by one triangle whose midpoint lies on another such edge:
    # a vertex of one side sits on an unsplit edge of the other side.
    import collections
    v=np.asarray(mesh['vertices'],float);keys,ids=np.unique(np.round(v,9),axis=0,return_inverse=True)
    count=collections.Counter(tuple(sorted(e)) for f in ids.ravel()[np.asarray(mesh['faces'])] for e in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])) if e[0]!=e[1])
    naked=np.array([e for e,c in count.items() if c==1]).reshape(-1,2)
    a,b=keys[naked[:,0]],keys[naked[:,1]];d=b-a;found=0
    for i,m in enumerate((a+b)/2):
        t=np.clip(((m-a)*d).sum(1)/(d*d).sum(1),0,1);dist=np.linalg.norm(a+t[:,None]*d-m,axis=1);dist[i]=np.inf
        found+=bool(dist.min()<1e-7)
    return found


def seam_gaps(mesh, axis, at, mask):
    # Points where the surface meets the plane from one side but no segment from
    # the other side passes through them; points near a masked node are skipped.
    v=np.asarray(mesh['vertices']).reshape(-1,3);p=v[np.asarray(mesh['faces']).reshape(-1,3)]
    on=np.abs(p[:,:,axis]-at)<=1e-9;center=p[:,:,axis].mean(axis=1)
    sides={-1:[],1:[]}
    for tri,flags,c in zip(p,on,center):
        if flags.sum()>=2 and abs(c-at)>1e-9:sides[int(np.sign(c-at))].append(tri[np.flatnonzero(flags)[:2]])
    masked=np.argwhere(mask);gaps=0
    for side in (-1,1):
        other=np.array(sides[-side]).reshape(-1,2,3);a=other[:,0];ab=other[:,1]-a
        for point in np.reshape(sides[side],(-1,3)):
            if np.any(np.all(np.abs(masked-point)<=.5+1e-9,axis=1)):continue
            t=np.clip(((point-a)*ab).sum(1)/np.maximum((ab*ab).sum(1),1e-30),0,1)
            gaps+=not len(a) or np.min(np.linalg.norm(a+t[:,None]*ab-point,axis=1))>1e-7
    return gaps


def test_refined_cells_meet_their_drawn_neighbours_without_cracks(monkeypatch):
    # Greptile's case: the stride-2 cell beside the masked node is refined; the
    # quadratic field made its face samples disagree with the drawn neighbour.
    g=np.indices((5,5,5)).astype(float);mask=np.zeros(g[0].shape,bool);mask[4,2,2]=True
    mesh=isosurface(g[2]+g[1]**2,2.,mask,2)
    assert seam_gaps(mesh,0,2.,np.zeros_like(mask))==0
    # Cells refined beside drawn cells of a coarser level and of other coarse cells.
    g=np.indices((9,9,9)).astype(float);mask=np.zeros(g[0].shape,bool);mask[3,2,2]=True
    values=g[0]*.3+(g[1]-2)**2*.4+(g[2]-2.5)**2*.3
    for level in (1.5,2.,2.6):
        mesh=isosurface(values,level,mask,4)
        assert mesh['faces'] and sum(seam_gaps(mesh,axis,at,mask) for axis in range(3) for at in np.arange(.5,8,.5))==0
    # Nonlinear field, scattered masked nodes, strides with a partial last cell.
    g=np.indices((11,11,11)).astype(float);values=np.sin(.3*g[0])+np.cos(.5*g[1])+.1*g[2]+.02*(g[0]-5)**2
    mask=np.random.default_rng(3).random(g[0].shape)<.03
    # The mirror puts the edge-only matches on the low sides of their cells.
    mirror=(slice(None,None,-1),slice(None),slice(None,None,-1))
    for stride,flip in ((1,()),(2,()),(3,()),(4,()),(2,mirror)):
        mesh=isosurface(values[flip],float(np.median(values)),mask[flip],stride)
        assert mesh['faces'] and sum(seam_gaps(mesh,axis,at,mask[flip]) for axis in range(3) for at in np.arange(.5,10,.5))==0
        # Live example 11: the welded mesh also has no T-junction where a refined
        # cell meets a drawn one, so no pinholes appear at the seam.
        assert t_junctions(mesh)==0
    g=np.indices((9,9,9)).astype(float);mask=np.zeros(g[0].shape,bool);mask[4,4,4]=True
    for stride in (1,2):
        mesh=isosurface((g[0]-4)**2+(g[1]-4.3)**2+(g[2]-3.8)**2,2.2,mask,stride)
        assert t_junctions(mesh)==0 and len(mesh['faces'])==452
        # The face budget also counts the triangles split at seams.
        assert len(isosurface((g[0]-4)**2+(g[1]-4.3)**2+(g[2]-3.8)**2,2.2,mask,stride,max_faces=452)['faces'])==452
        with pytest.raises(ValueError,match=r'^Isosurface exceeds face budget\. Increase stride or restrict the domain\.$'):
            isosurface((g[0]-4)**2+(g[1]-4.3)**2+(g[2]-3.8)**2,2.2,mask,stride,max_faces=451)
    # The query checkpoint reaches the seam split, so cancelling there stops the query.
    import hawa.fields as fields
    stage=[];split=fields.close_seams
    def seams(*args):
        stage.append('seams');return split(*args)
    def cancel(n):
        if stage:raise RuntimeError('cancelled in seams')
    monkeypatch.setattr(fields,'close_seams',seams)
    with pytest.raises(RuntimeError,match='^cancelled in seams$'):isosurface((g[0]-4)**2+(g[1]-4.3)**2+(g[2]-3.8)**2,2.2,mask,2,checkpoint=cancel)


def test_close_seams_splits_triangles_at_t_junctions():
    from hawa.fields import close_seams
    # One triangle has neighbour vertices on two of its edges; another on one edge.
    vertices=[[0,0,0],[2,0,0],[0,2,0],[1,0,0],[1,-1,0],[-1,1,0],[0,1,0],[5,0,0],[7,0,0],[5,2,0],[6,0,0],[6,-1,0]]
    faces=[[0,1,2],[0,4,3],[3,4,1],[0,6,5],[6,2,5],[7,8,9],[7,11,10],[10,11,8]]
    out,split=close_seams(vertices,faces)
    v=np.asarray(out,float);f=np.asarray(split)
    area=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])[:,2]/2
    # Area and winding are kept, no triangle is degenerate and the mesh welds without T-junctions.
    assert np.isclose(area.sum(),sum(np.cross(np.subtract(vertices[c[1]],vertices[c[0]]),np.subtract(vertices[c[2]],vertices[c[0]]))[2]/2 for c in faces))
    assert (area>0).all() and t_junctions(dict(vertices=out,faces=split))==0
    # The doubly split triangle is fanned from its centroid; the singly split one keeps its corners.
    assert np.allclose(out[12],[2/3,2/3,0]) and len(out)==13 and [7,10,9] in split and [10,8,9] in split and len(split)==len(faces)-2+5+2
    closed=dict(vertices=[[0,0,0],[1,0,0],[0,1,0],[0,0,1]],faces=[[0,2,1],[0,1,3],[1,2,3],[0,3,2]])
    assert close_seams(closed['vertices'],closed['faces'])==(closed['vertices'],closed['faces'])
    assert close_seams([],[])==([],[])
    # Both loops call checkpoint every 64 items, so a query can be cancelled during the pass.
    copies=[[x+10*c,y,z] for c in range(40) for x,y,z in vertices];tiled=[[i+12*c for i in f] for c in range(40) for f in faces]
    welded=np.unique(np.asarray(copies),axis=0,return_inverse=True)[1].ravel()[np.asarray(tiled)]
    _,uses=np.unique(np.sort(np.concatenate([welded[:,[0,1]],welded[:,[1,2]],welded[:,[2,0]]]),axis=1),axis=0,return_counts=True)
    calls=[];close_seams(copies,tiled,calls.append)
    assert (uses==1).sum()>128 and calls==list(range(0,int((uses==1).sum()),64))+list(range(0,len(tiled),64))
    def cancel(n):raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError,match='^cancelled$'):close_seams(copies,tiled,cancel)
    # A triangle that welds to a line adds no seam vertex.
    line=[[0,0,0],[1,0,0],[1+1e-12,0,0]]
    assert close_seams(line,[[0,1,2]])==(line,[[0,1,2]])


def test_tetra_value_is_the_marching_tetrahedra_interpolant():
    from hawa.fields import CUBE,march,tetra_value,uniform_cells
    corners=np.array([0.,3.,1.,2.,5.,-1.,4.,2.]);lo=np.array([1.,2.,3.]);hi=np.array([3.,3.,5.])
    np.testing.assert_allclose(tetra_value(lo,hi,corners,lo+CUBE*(hi-lo)),corners)
    # Every vertex march() draws in the cell lies on the interpolant's level set.
    grid=[np.array([1.,3.]),np.array([2.,3.]),np.array([3.,5.])];values=np.zeros((2,2,2));values[tuple(CUBE.T)]=corners
    mesh=march(grid,values,1.5,np.ones((1,1,1),bool),None,None,100,lambda n:None)
    np.testing.assert_allclose(tetra_value(lo,hi,corners,np.asarray(mesh['vertices'])),1.5)
    linear=lambda q:q@[1.,-2.,.5]
    points=lo+np.random.default_rng(0).random((20,3))*(hi-lo)
    np.testing.assert_allclose(tetra_value(lo,hi,linear(lo+CUBE*(hi-lo)),points),linear(points))
    assert uniform_cells([np.array([0,2,3]),np.array([0,2]),np.array([0,2,4])]).tolist()==[[[True,True]],[[False,False]]]


def test_isosurface_keeps_halfway_wall_rule_beside_a_face():
    x=np.indices((17,17,17))[0].astype(float);solid=np.zeros(x.shape,bool);solid[3:9,4:10,5:12]=True
    mesh=isosurface(x,8.7,solid)
    # Between the halfway wall (8.5) and node 9 the display holds node 9's value.
    v=np.asarray(mesh['vertices']);centers=v[np.asarray(mesh['faces'])].mean(axis=1)
    assert len(centers) and not np.any((centers[:,1]>4.5)&(centers[:,1]<8.5)&(centers[:,2]>5.5)&(centers[:,2]<10.5))
    assert projected_area(mesh)>256-7*8


def test_isosurface_rejects_bad_requests_and_honours_cancellation():
    x=np.indices((5,5,5))[0].astype(float)
    with pytest.raises(ValueError,match='^Isosurfaces require a 3D field$'):isosurface(x[0],1.)
    with pytest.raises(ValueError,match='^Level must be finite$'):isosurface(x,np.nan)
    with pytest.raises(ValueError,match=r'^Stride must be 1\.\.16$'):isosurface(x,1.,stride=17)
    with pytest.raises(ValueError,match=r'^Isosurface exceeds face budget\. Increase stride or restrict the domain\.$'):isosurface(x,2.5,max_faces=3)
    # A fully masked field with partial last cells is empty, not an error.
    y=np.indices((5,5,6))[0].astype(float)
    assert isosurface(y,1.,np.ones(y.shape,bool),2)=={'vertices':[],'faces':[]}
    np.testing.assert_array_equal(grid_lines(0,4,2),[0,2,4])
    np.testing.assert_array_equal(grid_lines(1,4.5,2),[1,3,4.5])
    def stop(n):raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError,match='cancelled'):isosurface(x,2.5,checkpoint=stop)


@pytest.mark.parametrize('n',[2,13,40])
def test_2d_plane_partition_matches_the_halfway_rule(n):
    from hawa.fields import store,dispatch_field
    shape=(12,12);g=np.indices(shape);u=np.zeros((2,)+shape);u[0]=1+.05*g[0]*g[1]
    mask=np.zeros(shape,bool);mask[4:8,4:8]=True
    key=store(dict(velocity=u,pressure=g[0].astype(float),density=np.ones(shape),solid=mask),
              dict(case=dict(shape=list(shape),dx=1.,speed=1.,density=1.,reference_pressure=0.),time=1.,iteration=0,mean=False))['frame']
    # Rectangle [-1,12]^2 = 169 around the [0,11]^2 lattice: no-data ring 48,
    # block 16. Vorticity also masks the block's +-1 cross (16 nodes) and the
    # 21 units of edge half-cells. The plane's z (0.75) is ignored on one layer.
    points=[[x,y,.75] for x in np.linspace(-1,12,n) for y in np.linspace(-1,12,n)]
    for field,areas in (('speed',dict(fluid=105,solid=16,invalid=0,no_data=48)),('vorticity',dict(fluid=68,solid=16,invalid=37,no_data=48))):
        r=dispatch_field(dict(action='plane',frame=key,field=field,points=points,shape=[n,n],levels=[1.5]))
        assert r['class_areas']==pytest.approx(areas,abs=1e-9) and r['collection']['domains']==1
        np.testing.assert_allclose(np.asarray(r['mesh_vertices'])[:,2],.75)
        assert r['iteration']==0 and r['case']['dx']==1.
        assert len(r['values'])==len(points)==len(r['valid']) and r['valid'][0] is False
        # Speed reaches 1.5 only where 0.05xy > 0.5, inside the fluid.
        assert bool(r['lines'])==(field=='speed')
    flat=dispatch_field(dict(action='plane',frame=key,field='speed',points=[p[:2] for p in points],shape=[n,n]))
    speed=dispatch_field(dict(action='plane',frame=key,field='speed',points=points,shape=[n,n],levels=[]))
    assert flat['class_areas']['fluid']==pytest.approx(105) and flat['values']==speed['values'] and any(flat['valid'])==(n>2)
    assert flat['lines']==[] and np.all(np.asarray(flat['mesh_vertices'])[:,2]==0)
    def stop(count):raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError,match='cancelled'):dispatch_field(dict(action='plane',frame=key,points=points,shape=[n,n]),checkpoint=stop)


def test_frame_rejects_mismatched_shapes():
    import pytest
    from hawa.fields import store
    with pytest.raises(ValueError,match='shapes'):
        store({'velocity':np.zeros((3,5,5,5)), 'pressure':np.zeros((4,4,4)),
               'density':np.ones((4,4,4))},{'case':{}})


def test_compressed_frame_budget_checked_before_allocation(tmp_path,monkeypatch):
    import json
    import pytest
    import hawa.fields as fields
    path=tmp_path/'frame.npz'
    np.savez_compressed(path,velocity=np.zeros((3,20,20,20)),pressure=np.zeros((20,20,20)),
                        density=np.ones((20,20,20)),metadata=np.array(json.dumps({'case':{}})))
    monkeypatch.setattr(fields,'MAX_BYTES',10000)
    assert path.stat().st_size<10000
    with pytest.raises(ValueError,match='budget'):fields.read_frame(path)


def test_contour_grid_and_level_limits():
    import pytest
    points=[[0,0,0],[0,1,0],[1,0,0],[1,1,0]]
    with pytest.raises(ValueError,match='grid'):contours(points,[0,0,1,1],[True]*4,[3,2],[.5])
    with pytest.raises(ValueError,match='levels'):contours(points,[0,0,1,1],[True]*4,[2,2],[.5]*101)


def _block_frame():
    # 3x3x3 solid block (nodes 3..5) in a 9^3 lattice; fluid speed 1, solid nodes hold junk.
    shape=(9,9,9);solid=np.zeros(shape,bool);solid[3:6,3:6,3:6]=True
    u=np.zeros((3,)+shape);u[0]=1.;u[0][solid]=1000.
    return dict(velocity=u,pressure=np.where(solid,1000.,2.),density=np.ones(shape),solid=solid)


def test_halfway_sampling_drops_exactly_the_solid_cells_and_uses_fluid_nodes_only():
    from hawa.fields import lattice_weights
    from hawa.plugin import sample_arrays
    fields=_block_frame()
    # Dense grid in the plane z=4 through the block, offset so no point sits on a half-way line.
    g=np.arange(.05,8,.1);x,y=np.meshgrid(g,g,indexing='ij');pts=np.stack([x.ravel(),y.ravel(),np.full(x.size,4.)],1)
    _,weights,valid=lattice_weights(fields['solid'],pts)
    # Invalid area is the 3x3 footprint of solid half-cells, [2.5,5.5]^2 = 9 dx^2, not a 1-dx band more.
    assert (~valid).sum()*.01==pytest.approx(9.)
    np.testing.assert_allclose(weights[valid].sum(1),1)
    rows=sample_arrays(fields,pts)
    assert [r is not None for r in rows]==list(valid)
    # Fluid-only weights: no solid junk (1000) leaks into any valid sample.
    assert all(r['speed']==pytest.approx(1.) and r['pressure']==pytest.approx(2.) for r in rows if r)
    # The half-way wall belongs to the fluid side; just inside it, the solid node owns the point.
    assert [r is not None for r in sample_arrays(fields,[[2.5,4,4],[2.49,4,4],[2.51,4,4],[-.01,4,4],[8.01,4,4]])]==[True,True,False,False,False]
    assert sample_arrays(fields,[[1,2,float('nan')],[1,2]])==[None,None]


def test_boundary_nodes_mask_views_but_not_obstacles():
    from hawa.fields import display_solid,validate,validity_mask
    fields=_block_frame();nodes=np.zeros((9,9,9),bool);nodes[:,:,0]=True
    fields['boundary_nodes']=nodes
    assert display_solid(fields)[:,:,0].all() and display_solid(fields)[4,4,4] and not fields['solid'][:,:,0].any()
    assert validity_mask(fields,'speed')[:,:,0].all() and validity_mask(fields,'vorticity')[:,:,1].all()
    validate(fields,dict(case={}))
    with pytest.raises(ValueError,match='^Frame boundary nodes mask must be a matching boolean array$'):validate(dict(fields,boundary_nodes=nodes.astype(int)),dict(case={}))
    with pytest.raises(ValueError,match='^Frame solid mask must be a matching boolean array$'):validate(dict(fields,solid=fields['solid'][1:]),dict(case={}))


def test_lattice_weights_judge_each_point_alone():
    from hawa.fields import lattice_weights
    from hawa.plugin import sample_arrays
    fields=_block_frame()
    corners,weights,valid=lattice_weights(fields['solid'],[[float('nan'),1,1],[1,1,1],[3.2,4,4]])
    # A non-finite point invalidates only itself; corners keep (2**d, n, d); invalid rows weigh nothing.
    assert valid.tolist()==[False,True,False] and corners.shape==(8,3,3)
    assert not weights[~valid].any() and weights[1].sum()==pytest.approx(1)
    fields['density']=1+.1*np.indices((9,9,9))[0]
    assert sample_arrays(fields,[[1.25,1,1]])[0]['density']==pytest.approx(1.125)


def test_read_frame_keeps_every_stored_array(tmp_path):
    import json
    from hawa.fields import read_frame
    shape=(3,3,3);solid=np.zeros(shape,bool);solid[1,1,1]=True;nodes=np.zeros(shape,bool);nodes[0]=True
    arrays=dict(velocity=np.zeros((3,)+shape),pressure=np.zeros(shape),density=np.ones(shape),solid=solid,
                boundary_nodes=nodes,strain_rate=np.ones((3,3)+shape),wall_velocity=np.full((3,3,3),2.))
    np.savez_compressed(tmp_path/'frame.npz',metadata=np.array(json.dumps({'case':{}})),**arrays)
    got,_=read_frame(tmp_path/'frame.npz')
    assert sorted(got)==sorted(arrays) and all(np.array_equal(got[k],arrays[k]) for k in arrays)


def test_trace_keeps_every_seed_the_final_step_and_masks_colours_only():
    from hawa.fields import trace
    shape=(14,8,8);velocity=np.zeros((3,)+shape);velocity[0]=1.;velocity[:,:,6:]=0.
    solid=np.zeros(shape,bool);solid[11:,:4]=True;solid[:,0]=True
    fields=dict(velocity=velocity,pressure=np.zeros(shape),density=np.ones(shape),solid=solid)
    # Open flow, into the wall, inside the wall, stalled, and 0.6 above the y=0 wall.
    seeds=[[1.,5.,4.],[6.,2.,4.],[12.,1.,4.],[3.,7.,4.],[1.,.6,4.]]
    speed=trace(fields,seeds,steps=20,step=.4)
    vorticity=trace(fields,seeds,steps=20,step=.4,name='vorticity')
    assert speed['paths']==vorticity['paths'] and len(speed['paths'])==len(seeds)
    assert speed['reasons']==['completed','left_flow','invalid_seed','stalled','completed']
    open_flow=np.array(speed['paths'][0])
    assert len(open_flow)==21 and np.sum(np.linalg.norm(np.diff(open_flow,axis=0),axis=1))==pytest.approx(8.)
    wall=np.array(speed['paths'][1]);assert wall[-1,0]<=10.5 and wall[-1,0]>10.5-.4
    assert speed['paths'][2]==[] and speed['values'][2]==[] and speed['paths'][3]==[[3.,7.,4.]]
    assert all(all(v) for v in speed['valid']) and set(speed['values'][0])=={1.}
    # Vorticity has no stencil next to a solid or on the domain edge: masked, not coloured.
    beside_wall=vorticity['valid'][4]
    assert not any(beside_wall) and set(vorticity['values'][4])=={0.}
    assert any(vorticity['valid'][0]) and not vorticity['valid'][3][0]


def test_trace_is_fourth_order_on_a_rotating_flow():
    from hawa.fields import trace
    # Solid-body rotation is linear, so sampling is exact and only RK4's error remains.
    shape=(13,13,5);g=np.indices(shape).astype(float);velocity=np.zeros((3,)+shape)
    velocity[0]=-(g[1]-6);velocity[1]=g[0]-6
    fields=dict(velocity=velocity,pressure=np.zeros(shape),density=np.ones(shape),solid=np.zeros(shape,bool))
    path=np.array(trace(fields,[[10.,6.,2.]],steps=20,step=.4)['paths'][0])
    assert len(path)==21 and np.abs(np.linalg.norm(path[:,:2]-6,axis=1)-4).max()<1e-5
    def stop(n):raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError,match='cancelled'):trace(fields,[[10.,6.,2.]],steps=20,step=.4,checkpoint=stop)


def test_trace_result_keeps_the_point_budget_across_seeds():
    from hawa.fields import trace_result
    def run(lengths):
        return trace_result(lengths,lambda n:([[0.,0.,0.]]*n,'completed'),lambda path:[(0.,True)]*len(path))
    assert run([50000,50000])['reasons']==['completed']*2
    message='^Flow display exceeds 100000 points. Reduce seeds or steps.$'
    for lengths in ([50000,50001],[40000,40000,40000]):
        with pytest.raises(ValueError,match=message):run(lengths)
