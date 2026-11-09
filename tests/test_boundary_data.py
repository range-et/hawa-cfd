import json
import numpy as np
import pytest
import torch
from hawa.plugin import Session, check_case
from hawa.recording import record
from hawa.boundary_data import capture, attach, read, digest, grid_key, SCHEMA
from hawa.quality import assess


def case(**kw):
    return dict(shape=[10, 6, 6], dx=.1, spacing=.1, speed=1., viscosity=.01,
                boundaries=['inlet','outlet','periodic','periodic','periodic','periodic'], **kw)


def series(path, spec, velocity=None, times=None):
    if times is None: times=np.array([0., 1.])
    if velocity is None:
        velocity=np.zeros((len(times),3,*spec['shape'][1:]),np.float32);velocity[:,0]=1
    meta={'schema':SCHEMA,'grid':grid_key(spec),'source':{'test':'analytic'},
          'quality':{'policy':'hawa-low-mach-v1','status':'within-tested-envelope','transfer_eligible':True}}
    with path.open('wb') as f:np.savez_compressed(f,times=times,velocity=velocity,metadata=np.array(json.dumps(meta)))
    return path


def test_uniform_regression_and_time_profile(tmp_path):
    spec=case();path=series(tmp_path/'bc.npz',spec)
    plain=Session(spec,'cpu'); mapped=Session(attach(path,spec)['case'],'cpu')
    plain.advance(20);mapped.advance(20)
    np.testing.assert_allclose(plain.flow.f.numpy(),mapped.flow.f.numpy(),atol=2e-7,rtol=2e-6)
    velocity=np.zeros((2,3,6,6)); velocity[0,0]=1;velocity[1,0]=1.2
    velocity[:,1]=np.linspace(-.02,.02,6)[:,None]
    path=series(tmp_path/'vary.npz',spec,velocity)
    s=Session(attach(path,spec)['case'],'cpu');s.advance(10)
    t=s.flow.units.convert_time_to_pu(10)
    np.testing.assert_allclose(s.fields()['velocity'][0,0],1+.2*t,atol=5e-6)
    np.testing.assert_allclose(s.fields()['velocity'][1,0],velocity[0,1],atol=5e-6)


def test_capture_parent_child_units_and_coverage(tmp_path):
    parent=Session(case(),'cpu');record(parent,20,5,str(tmp_path/'record'),lambda n:None)
    child=case(origin=[.2,0,0])
    result=capture(tmp_path/'record/manifest.json',child,tmp_path/'transfer.npz')
    assert result['report']['frames']==5
    s=Session(result['case'],'cpu');s.advance(20)
    np.testing.assert_allclose(s.fields()['velocity'][0],1,atol=1e-5)
    millimetres=case(origin=[200,0,0]);millimetres['spacing']=100
    result2=capture(tmp_path/'record/manifest.json',millimetres,tmp_path/'mm.npz')
    np.testing.assert_allclose(result2['case']['boundary_field']['grid']['origin_m'],result['case']['boundary_field']['grid']['origin_m'],atol=1e-14)
    with pytest.raises(ValueError,match='coverage'):capture(tmp_path/'record/manifest.json',case(origin=[2,0,0]),tmp_path/'bad.npz')
    with pytest.raises(ValueError,match='coverage'):s.advance(1)
    with pytest.raises(ValueError,match='coverage'):s.start(21)


def test_quality_finite_high_mach_sticky_and_source_rejection(tmp_path):
    s=Session(case(),'cpu')
    u=s.flow.u().clone();u[0]=.46/np.sqrt(3)
    s.flow.f=s.flow.equilibrium(s.flow,s.flow.rho(),u)
    s.quality=assess(s)
    assert s.quality['finite'] and s.quality['status']=='rejected'
    assert s.quality['max_lattice_mach']==pytest.approx(.46,rel=1e-5)
    s.flow.f.copy_(s.initial_f);s.quality=assess(s)
    assert s.quality['status']=='rejected' and not s.quality['transfer_eligible']
    record(s,5,5,str(tmp_path/'record'),lambda n:None)
    with pytest.raises(ValueError,match='quality'):capture(tmp_path/'record/manifest.json',case(),tmp_path/'bad.npz')


def test_invalid_files_changed_grid_and_changed_file(tmp_path):
    spec=case();p=series(tmp_path/'bc.npz',spec);attached=attach(p,spec)['case']
    p.write_bytes(p.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='changed'):Session(attached,'cpu')
    p=series(p,spec)
    with pytest.raises(ValueError,match='different child'):attach(p,case(origin=[1,0,0]))
    with pytest.raises(ValueError,match='increase'):read(series(p,spec,times=np.array([0.,0.])))
    v=np.zeros((2,3,6,6))
    with pytest.raises(ValueError,match='backflow'):read(series(p,spec,v))
    v[:,0]=4
    with pytest.raises(ValueError,match='Mach'):attach(series(p,spec,v),spec)
    with pytest.raises(ValueError,match='stationary'):check_case(dict(attached,refinement_lower=[1,1,1]))


@pytest.mark.parametrize('device',['cpu','mps','cuda:0'])
def test_nonuniform_device_parity(tmp_path,device):
    if device=='mps' and not torch.backends.mps.is_available():pytest.skip('MPS unavailable')
    if device.startswith('cuda') and not torch.cuda.is_available():pytest.skip('CUDA unavailable')
    spec=case();v=np.zeros((2,3,6,6));v[0,0]=1;v[1,0]=1.05;v[:,1]=.01
    spec=attach(series(tmp_path/'bc.npz',spec,v),spec)['case']
    reference=Session(spec,'cpu');reference.advance(20)
    s=Session(spec,device);s.advance(20)
    np.testing.assert_allclose(s.fields()['velocity'],reference.fields()['velocity'],atol=2e-5,rtol=3e-4)
    assert s.quality['status']==reference.quality['status']


def test_rotated_mapping_mask_rejection_and_cancel(tmp_path):
    from hawa.fields import read_frame
    from hawa.jobs import Cancelled
    parent=Session(case(),'cpu');record(parent,10,5,str(tmp_path/'record'),lambda n:None)
    # Rotate child's Y/Z axes about X. Velocity components must rotate too.
    child=case(origin=[.2, .5, 0],basis=[[1,0,0],[0,0,1],[0,-1,0]])
    for file in (tmp_path/'record').glob('frame-*.npz'):
        arrays,meta=read_frame(file);arrays['velocity'][1]=.02
        with file.open('wb') as f:np.savez_compressed(f,**arrays,metadata=np.array(json.dumps(meta)))
    capture(tmp_path/'record/manifest.json',child,tmp_path/'rotated.npz')
    _,v,_=read(tmp_path/'rotated.npz')
    np.testing.assert_allclose(v[:,2],-.02,atol=1e-7)
    np.testing.assert_allclose(v[:,1],0,atol=1e-7)
    def cancel(n):raise Cancelled('test cancellation')
    with pytest.raises(Cancelled):capture(tmp_path/'record/manifest.json',child,tmp_path/'cancel.npz',cancel)
    assert not (tmp_path/'cancel.npz').exists()
    file=tmp_path/'record/frame-000001.npz';arrays,meta=read_frame(file);arrays['solid'][2,2,2]=True
    with file.open('wb') as f:np.savez_compressed(f,**arrays,metadata=np.array(json.dumps(meta)))
    with pytest.raises(ValueError,match='solid parent'):capture(tmp_path/'record/manifest.json',child,tmp_path/'solid.npz')


def test_quality_flux_and_record_provenance(tmp_path):
    s=Session(case(),'cpu');s.advance(5)
    q=s.quality
    assert abs(q['boundary_flux']['net_external_mass_kg_s'])<1e-6
    assert q['backflow']=={'inlet_cells':0,'outlet_cells':0}
    record(s,10,5,str(tmp_path/'record'),lambda n:None)
    from hawa.fields import read_frame
    _,meta=read_frame(tmp_path/'record/frame-000000.npz')
    assert meta['quality']['iteration']==5
    assert meta['time']==meta['quality']['time_seconds']


def test_checkpoint_keeps_rejected_history(tmp_path):
    from hawa.plugin import dispatch, SESSIONS
    s=Session(case(),'cpu');SESSIONS[s.id]=s
    try:
        s.quality=dict(s.quality,status='rejected',transfer_eligible=False,reasons=['Earlier exceedance'],peak_sampled_lattice_mach=.46)
        dispatch(dict(op='save',session=s.id,path=str(tmp_path/'checkpoint.npz')))
        dispatch(dict(op='reset',session=s.id))
        assert s.quality['status']=='within-tested-envelope'
        dispatch(dict(op='load',session=s.id,path=str(tmp_path/'checkpoint.npz')))
        assert s.quality['status']=='rejected' and not s.quality['transfer_eligible']
    finally:dispatch(dict(op='close',session=s.id))
