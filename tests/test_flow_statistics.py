import json
import numpy as np
import pytest
from hawa.flow_statistics import summarize,analyze
from hawa.roughness import apply,grid
from hawa.plugin import Session
from test_boundary_series import case,recording


def test_statistics_covariance_spectrum_and_pressure():
    t=np.arange(256)*.1;signal=np.sin(2*np.pi*10*np.arange(256)/256)
    u=np.zeros((256,2,3));u[:,:,0]=2+signal[:,None];u[:,:,1]=.5*signal[:,None];p=np.ones((256,2))*4
    r=summarize(t,u,p)
    np.testing.assert_allclose(r['mean_velocity'],[[2,0,0]]*2,atol=1e-12)
    np.testing.assert_allclose(np.array(r['reynolds_covariance'])[:,0,1],.25,atol=1e-12)
    np.testing.assert_allclose(r['resolved_tke'],.3125,atol=1e-12)
    assert np.argmax(np.array(r['velocity_psd'])[:,0,0])==10
    assert r['frequency_hz'][10]==pytest.approx(10/25.6)
    assert r['mean_pressure']==[4.,4.] and r['blocks']==8


def test_statistics_rejects_bad_windows_and_warns_short_records(tmp_path):
    manifest=recording(tmp_path/'parent',case(),times=tuple(np.arange(10)*.2+2))
    r=analyze(manifest,[[2,2,2]],start_time=2.4)
    assert r['samples']==8 and r['status']=='insufficient-statistical-evidence'
    assert r['source']['frame_sha256']
    with pytest.raises(ValueError,match='four'):analyze(manifest,[[2,2,2]],start_time=3.6)
    with pytest.raises(ValueError,match='fluid'):analyze(manifest,[[-1,2,2]])
    with pytest.raises(ValueError,match='uniformly'):summarize([0,1,2,4],np.ones((4,1,3)),np.zeros((4,1)))


def test_spatial_roughness_impulse_and_no_mutation():
    spec=case();result=apply(spec,[dict(polygon=[[-1,-1],[6,-1],[6,13],[-1,13]],length_m=.001)])
    assert 'wall_roughness' not in spec
    assert np.all(grid(result['case'])[:6]==.001) and np.all(grid(result['case'])[6:]==.01)
    s=Session(result['case'],'cpu');wall=s.solver.rough_floor;wall.capture()
    # At matching velocities, smoother half must exert less traction.
    assert abs(float(wall.impulse[0,:6].mean()))<abs(float(wall.impulse[0,6:].mean()))
    s.advance(10);assert s.quality['finite']
    with pytest.raises(ValueError,match='roughness'):apply(spec,[dict(polygon=[[0,0],[5,0],[5,5]],length_m=.6)])
    with pytest.raises(ValueError,match='no ground'):apply(spec,[dict(polygon=[[30,30],[35,30],[35,35]],length_m=.001)])
