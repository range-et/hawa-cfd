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
