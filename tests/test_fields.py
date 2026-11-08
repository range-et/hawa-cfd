import numpy as np
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
