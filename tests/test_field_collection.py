import numpy as np
import pytest
from hawa.fields import store,dispatch_field


def frame(dx=1.,origin=(0,0,0),basis=None,time=2.,speed=1.,solid=False):
    shape=(7,7,7);g=np.indices(shape);u=np.zeros((3,)+shape);u[0]=speed
    mask=np.zeros(shape,bool)
    if solid:mask[2:4,2:4,2:4]=True
    spec=dict(shape=list(shape),dx=dx,spacing=dx,origin=list(origin),basis=basis or np.eye(3).tolist(),speed=1.,density=1.,reference_pressure=0.)
    fields=dict(velocity=u,pressure=(origin[0]+g[0]*dx).astype(float),density=np.ones(shape),solid=mask)
    return store(fields,dict(case=spec,time=time,iteration=0,mean=False))['frame']


def test_nested_finest_owner_and_no_fallback_through_child_solid():
    a=frame();b=frame(.5,(2,2,2),speed=3.,solid=True)
    r=dispatch_field(dict(action='sample',frames=[a,b],field='speed',points=[[1,1,1],[2.5,2.5,2.5],[3,3,3],[6,6,6],[7,7,7]]))
    assert r['valid']==[True,True,False,True,False]
    assert r['values']==[1.,3.,0.,1.,0.]
    assert r['domain_index']==[0,1,1,0,-1]


def test_world_rotation_units_and_time_alignment():
    a=frame();b=frame(.5,(4,2,0),basis=[[0,1,0],[-1,0,0],[0,0,1]],speed=3.)
    r=dispatch_field(dict(action='sample',frames=[a,b],field='uy',points=[[3,3,1],[.5,.5,.5]]))
    assert r['values']==[3.,0.]
    np.testing.assert_allclose(r['velocity'],[[0,3,0],[1,0,0]],atol=1e-12)
    c=frame(time=3.)
    with pytest.raises(ValueError,match='times differ'):dispatch_field(dict(action='sample',frames=[a,c],points=[[0,0,0]]))


def test_disjoint_domains_and_shared_plane_contours():
    a=frame();b=frame(.5,(8,0,0),speed=2.)
    p=[[x,y,1.] for x in (0.,4.,8.,10.) for y in (1.,2.)]
    r=dispatch_field(dict(action='plane',frames=[a,b],field='pressure',points=p,shape=[4,2],levels=[2.]))
    assert all(r['valid']) and len(r['lines'])>0
    np.testing.assert_allclose(r['values'],[0,0,4,4,8,8,10,10])
    vertices=np.asarray(r['mesh_vertices'])
    for face in r['mesh_faces']:
        xs=vertices[list(face),0]
        assert xs.max()<=6+1e-10 or xs.min()>=8-1e-10
    gap=dispatch_field(dict(action='sample',frames=[a,b],points=[[7,1,1]]))
    assert gap['valid']==[False]


def test_streamline_crosses_parent_child_and_isosurface_is_continuous():
    a=frame();b=frame(.5,(2,1,1),speed=2.)
    r=dispatch_field(dict(action='trace',frames=[a,b],seeds=[[1,2,2]],steps=20,step=.4))
    p=np.array(r['paths'][0]);assert p[0,0]==1 and p[-1,0]>4
    np.testing.assert_allclose(p[:,1:],[[2,2]]*len(p))
    assert min(r['values'][0])==1 and max(r['values'][0])==2
    iso=dispatch_field(dict(action='isosurface',frames=[a,b],field='pressure',level=3.25,stride=1))
    assert iso['faces'];np.testing.assert_allclose(np.array(iso['vertices'])[:,0],3.25)


@pytest.mark.parametrize('stride',[1,2,4])
def test_composed_isosurface_equals_single_frame(stride):
    key=frame(solid=True)
    for level in (1.25,3.25,4.6):
        single=dispatch_field(dict(action='isosurface',frame=key,field='pressure',level=level,stride=stride))
        composed=dispatch_field(dict(action='isosurface',frames=[key],field='pressure',level=level,stride=stride))
        assert composed['faces']==single['faces'] and single['faces']
        np.testing.assert_allclose(composed['vertices'],single['vertices'],atol=1e-9)


def plate_frame(stride_bump=False):
    # dx 0.5 child whose lattice is offset from the view origin on every axis,
    # with a one-node plate at odd x (between stride-2 and stride-4 lines).
    shape=(13,13,13);origin=np.array([-1.5,-1.,-.5]);g=np.indices(shape)
    mask=np.zeros(shape,bool);mask[11,2:11,3:10]=True
    pressure=origin[0]+g[0]*.5+(3*np.exp(-((g[0]-9.)**2+(g[1]-6.)**2+(g[2]-6.)**2)) if stride_bump else 0)
    spec=dict(shape=list(shape),dx=.5,spacing=.5,origin=origin.tolist(),basis=np.eye(3).tolist(),speed=1.,density=1.,reference_pressure=0.)
    return store(dict(velocity=np.zeros((3,)+shape),pressure=pressure,density=np.ones(shape),solid=mask),dict(case=spec,time=2.,iteration=0,mean=False))['frame'],origin


@pytest.mark.parametrize('stride',[1,2,4])
def test_composed_isosurface_matches_offset_child_with_thin_plate(stride):
    # A coarser reference frame inside the child sets the view: dx 2 from
    # (.5,.5,.5), so the child owns every sample. The plate lies between coarse
    # lines, so only its node half-cells can mark those cells. The bump peaks
    # inside a coarse cell whose corners never reach level 5.
    ref=store(dict(velocity=np.zeros((3,3,3,3)),pressure=np.indices((3,3,3))[0]*2.+.5,density=np.ones((3,3,3))),
              dict(case=dict(shape=[3,3,3],dx=2.,spacing=2.,origin=[.5,.5,.5],basis=np.eye(3).tolist(),speed=1.,density=1.,reference_pressure=0.),time=2.,iteration=0,mean=False))['frame']
    for bump in (False,True):
        key,origin=plate_frame(bump)
        for level in (3.,3.5,3.75,4.1)+((5.,) if bump else ()):
            single=dispatch_field(dict(action='isosurface',frame=key,field='pressure',level=level,stride=stride))
            composed=dispatch_field(dict(action='isosurface',frames=[ref,key],field='pressure',level=level,stride=stride))
            assert composed['faces']==single['faces']
            # At stride 2 the peak lies inside an all-fluid coarse cell, whose
            # corners are its only samples; mixed cells (stride 4) resolve it.
            assert single['faces'] or (level==5. and stride==2)
            np.testing.assert_allclose(np.reshape(composed['vertices'],(-1,3))*2+.5,origin+np.reshape(single['vertices'],(-1,3))*.5,atol=1e-9)
            assert composed['display_sampling']['spacing_m']==.5*stride


def test_composed_isosurface_reports_samples_and_full_budget_message():
    iso=dispatch_field(dict(action='isosurface',frames=[frame()],field='pressure',level=2.5,stride=2))
    # No masked nodes: only the 4 x 4 x 4 coarse lines are sampled.
    assert iso['display_sampling']['samples']==64
    solid=dispatch_field(dict(action='isosurface',frames=[frame(solid=True)],field='pressure',level=2.5,stride=2))
    assert solid['display_sampling']['samples']>64
    far=frame(origin=(100000,0,0))
    with pytest.raises(ValueError,match='^Multi-domain isosurface exceeds 250000 display samples; change stride or select fewer frames$'):
        dispatch_field(dict(action='isosurface',frames=[frame(),far],level=.5))


def test_composed_isosurface_ends_on_union_bounds():
    # The child's y edges (.25 and 3.25) fall between stride-2 lines.
    a=frame();b=frame(.5,(6.25,.25,0))
    iso=dispatch_field(dict(action='isosurface',frames=[a,b],field='pressure',level=9.1,stride=2))
    v=np.asarray(iso['vertices'])
    assert iso['faces'] and v[:,0].max()<=9.25 and iso['display_sampling']['spacing_m']==1.
    np.testing.assert_allclose(v[:,0],9.1)
    # Area covers the child's full cross-section (3 x 3).
    f=np.asarray(iso['faces']);area=np.abs(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])[:,0]).sum()/2
    assert area==pytest.approx(9.)


def test_collection_cancellation_budget_and_equal_spacing_order():
    a=frame();b=frame(speed=2.)
    req=dict(action='sample',frames=[a,b],points=[[1,1,1]])
    assert dispatch_field(req)['values']==[1.]
    def stop(n):raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError,match='cancelled'):dispatch_field(req,checkpoint=stop)
    far=frame(origin=(100000,0,0))
    with pytest.raises(ValueError,match='display samples'):dispatch_field(dict(action='isosurface',frames=[a,far],level=.5))


def test_plane_trims_crossing_triangles_without_a_blank_fluid_band():
    key=frame(solid=True)
    points=[[x,y,2.5] for x in (0.,6.) for y in (0.,6.)]
    r=dispatch_field(dict(action='plane',frames=[key],field='speed',points=points,shape=[2,2],levels=[]))
    v=np.asarray(r['mesh_vertices']);f=np.asarray(r['mesh_faces'])
    area=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1).sum()/2
    # The represented 2x2 building footprint occupies [1.5,3.5]^2.
    assert area==pytest.approx(36-4,abs=1e-10)
    # Wall-edge vertices show the adjacent fluid nodes' values (uniform 1 here), not an invented zero.
    boundary=np.isclose(v[:,0],1.5)&(v[:,1]>=1.5)&(v[:,1]<=3.5)
    assert boundary.any() and np.allclose(np.asarray(r['mesh_values'])[boundary],1)
    # Halfway wall at x=1.5: the fluid side is valid and fluid-only; the solid node's half-cell is not.
    raw=dispatch_field(dict(action='sample',frames=[key],points=[[1.25,2.5,2.5],[1.5,2.5,2.5],[1.75,2.5,2.5]]))
    assert raw['valid']==[True,True,False] and raw['values'][:2]==[1.,1.]


def plane_grid(x0,x1,y0,y1,z,n):
    return [[x,y,z] for x in np.linspace(x0,x1,n) for y in np.linspace(y0,y1,n)]


@pytest.mark.parametrize('n,dx,origin',[(2,1.,(0,0,0)),(9,.5,(1,2,3)),(30,1.,(0,0,0))])
def test_plane_classes_tile_the_rectangle_with_indexed_vertices(n,dx,origin):
    # View coordinates are the first frame's lattice coordinates at any dx/origin.
    key=frame(dx,origin,solid=True)
    # Halfway rule at z=2.5: the 2x2 block owns [1.5,3.5]^2. For q, the
    # derivative mask adds the block's +-1 cross (8 nodes) and the domain
    # edge nodes, leaving fluid half-cells [0.5,5.5]^2 minus 12 nodes.
    expected=dict(speed=dict(fluid=32,solid=4,invalid=0,no_data=0),q=dict(fluid=13,solid=4,invalid=19,no_data=0))
    for field,areas in expected.items():
        r=dispatch_field(dict(action='plane',frames=[key],field=field,points=plane_grid(0,6,0,6,2.5,n),shape=[n,n],levels=[]))
        assert r['class_areas']==pytest.approx(areas,abs=1e-9)
        v=np.asarray(r['mesh_vertices']);faces=[f for k in ('mesh_faces','solid_faces','invalid_faces','no_data_faces') for f in r[k]]
        assert len(np.unique(np.round(v,9),axis=0))==len(v) and set(np.ravel(faces))==set(range(len(v)))
        f=np.asarray(faces);assert np.all(np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)>1e-14)
        assert r['iteration']==0 and r['case']['dx']==dx
        if field=='speed':np.testing.assert_allclose(np.asarray(r['mesh_values'])[np.ravel(r['mesh_faces'])],1)


def test_tilted_plane_solid_area_matches_nearest_node_sampling():
    key=frame(solid=True)
    # Plane z=x+0.5 rises through the block's layers inside its footprint and
    # leaves the domain (z>6) near x=6.
    corner=lambda x,y:[x,y,x+.5]
    r=dispatch_field(dict(action='plane',frames=[key],field='speed',points=[corner(x,y) for x in (0.,6.) for y in (0.,6.)],shape=[2,2],levels=[]))
    # Independent check: dense points, solid where the nearest node is a block node.
    u=(np.arange(600)+.5)/600*6;x,y=np.meshgrid(u,u,indexing='ij');z=x+.5
    near=np.rint(np.stack([x,y,z],-1)).astype(int);inside=np.all((near>=2)&(near<=3),axis=-1)
    slant=np.sqrt(2)
    assert r['class_areas']['no_data']==pytest.approx(.5*6*slant)
    assert r['class_areas']['solid']==pytest.approx(inside.mean()*36*slant,abs=.05)
    assert sum(r['class_areas'].values())==pytest.approx(36*slant)


def test_plane_reports_gaps_between_domains_as_no_data():
    a=frame();b=frame(.5,(8,0,0),speed=2.)
    r=dispatch_field(dict(action='plane',frames=[a,b],field='pressure',points=plane_grid(-1,12,-1,7,1.,20),shape=[20,20],levels=[2.]))
    # Rectangle 13 x 8; parent covers 6 x 6, child 3 x 3.
    assert r['class_areas']==pytest.approx(dict(fluid=45,solid=0,invalid=0,no_data=59),abs=1e-9)
    assert r['lines'] and r['collection']['domains']==2


@pytest.mark.parametrize('dx,origin',[(1.,[0,0,0]),(.5,[1,2,3])])
def test_plane_classifies_rejected_faces_of_curved_wall_frames(dx,origin):
    shape=(7,7,7);g=np.indices(shape);u=np.zeros((3,)+shape);u[0]=1
    mask=np.zeros(shape,bool);mask[2:4,2:4,2:4]=True
    spec=dict(shape=list(shape),dx=dx,spacing=dx,origin=origin,basis=np.eye(3).tolist(),speed=1.,density=1.,reference_pressure=0.,wall_links=True)
    key=store(dict(velocity=u,pressure=g[0].astype(float),density=np.ones(shape),solid=mask),dict(case=spec,time=2.,iteration=0,mean=False))['frame']
    # Unclipped unit triangles: whole faces inside the block's half-cells are
    # solid; faces with a solid corner but a fluid centroid are invalid.
    r=dispatch_field(dict(action='plane',frames=[key],field='speed',points=plane_grid(0,6,0,6,2.5,7),shape=[7,7],levels=[]))
    assert r['class_areas']==pytest.approx(dict(fluid=28,solid=4,invalid=4,no_data=0),abs=1e-9)


def test_reference_example_frames_use_recorded_physical_spacing():
    from hawa.plugin import Session
    from hawa.fields import capture
    s=Session(dict(example='tgv3d-bgk',size=8),'cpu');a=capture(s);b=capture(s)
    request=dict(action='sample',field='speed',points=[[2.,2.,2.]])
    ordinary=dispatch_field(dict(request,frame=a['frame']))
    combined=dispatch_field(dict(request,frames=[a['frame'],b['frame']]))
    np.testing.assert_allclose(combined['values'],ordinary['values'],atol=1e-12)


def test_collection_sample_interpolates_each_velocity_axis_to_the_far_face():
    shape=(7,7,7);g=np.indices(shape).astype(float)
    spec=dict(shape=list(shape),dx=1.,spacing=1.,origin=[0,0,0],basis=np.eye(3).tolist(),speed=1.,density=1.,reference_pressure=0.)
    key=store(dict(velocity=np.stack([g[0],10*g[1],100*g[2]]),pressure=g[0].copy(),density=np.ones(shape),solid=np.zeros(shape,bool)),
              dict(case=spec,time=2.,iteration=0,mean=False))['frame']
    # Off-diagonal point, a point in the last cell and one within the 1e-9 face tolerance.
    r=dispatch_field(dict(action='sample',frames=[key],field='pressure',points=[[1.25,2.5,3.75],[5.5,5.5,5.5],[6+5e-10,6,6]]))
    assert r['valid']==[True,True,True]
    np.testing.assert_allclose(r['values'],[1.25,5.5,6],atol=1e-8)
    np.testing.assert_allclose(r['velocity'],[[1.25,25,375],[5.5,55,550],[6,60,600]],atol=1e-6)
