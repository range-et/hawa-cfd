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


def test_reference_example_frames_use_recorded_physical_spacing():
    from hawa.plugin import Session
    from hawa.fields import capture
    s=Session(dict(example='tgv3d-bgk',size=8),'cpu');a=capture(s);b=capture(s)
    request=dict(action='sample',field='speed',points=[[2.,2.,2.]])
    ordinary=dispatch_field(dict(request,frame=a['frame']))
    combined=dispatch_field(dict(request,frames=[a['frame'],b['frame']]))
    np.testing.assert_allclose(combined['values'],ordinary['values'],atol=1e-12)
