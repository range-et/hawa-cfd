import numpy as np
import pytest
from hawa.fields import isosurface,scalar,contours


def test_plane_isosurface_and_mask():
    x=np.indices((5,5,5))[0].astype(float)
    mesh=isosurface(x,2.5)
    assert len(mesh['faces'])>0
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
    with pytest.raises(ValueError,match='boundary nodes mask'):validate(dict(fields,boundary_nodes=nodes.astype(int)),dict(case={}))
