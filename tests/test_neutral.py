import copy
import numpy as np
import pytest
import torch
import lettuce as lt
from hawa.plugin import Session,check_case
from hawa.neutral import MODEL, make


def case(dx=1.):
    return dict(shape=[12,12,12],dx=dx,speed=5.,viscosity=1.5e-5,density=1.225,mach=.05,
                collision=MODEL,boundaries=['periodic']*4+['wall','slip'],
                neutral_precursor=dict(schema=1,experimental=True,reference_height_m=6*dx,
                    roughness_length_m=.01*dx,perturbation_fraction=0.))


def test_strict_capabilities():
    s=case(); assert check_case(s)['valid']
    s['neutral_precursor']['experimental']=False
    with pytest.raises(ValueError): check_case(s)
    for field,value in [('solid',[5]),('boundary_set',{'schema':1}),('wall_links',[[1,2,.5]])]:
        s=case();s[field]=value
        with pytest.raises(ValueError): check_case(s)
    s=case();s.pop('neutral_precursor')
    with pytest.raises(ValueError):check_case(s)


def test_shifted_equilibrium_moments():
    f,sim=make(case(),lt.Context('cpu',torch.float64,use_native=False))
    torch.testing.assert_close(f.rho(),torch.ones_like(f.rho()),atol=1e-15,rtol=0)
    from hawa.atmosphere import neutral_profile
    expected=neutral_profile((np.arange(12)+.5),[5.,0.,0.],6.,.01).T[:,None,None,:]
    np.testing.assert_allclose(f.u_pu.numpy(),np.broadcast_to(expected,(3,12,12,12)),atol=1e-13)
    assert f.f.abs().max()<.02
    assert f.p_pu.abs().max()<1e-10


def test_wall_mass_and_impulse_budget():
    f,sim=make(case(),lt.Context('cpu',torch.float64,use_native=False))
    # Exact per-step identity on periodic planes, including drive and both walls.
    for _ in range(3):
        mass=f.f.sum().item(); momentum=f.j().sum((1,2,3)).clone(); rho=f.rho().sum()
        acceleration=torch.as_tensor(sim.collision.acceleration,dtype=torch.float64)
        sim(1)
        torch.testing.assert_close(f.f.sum(),torch.tensor(mass,dtype=torch.float64),atol=2e-14,rtol=0)
        expected=rho*acceleration+sim.rough_floor.impulse.sum((1,2))
        # Floor/lid reflect normal momentum; tangential impulse is prescribed.
        torch.testing.assert_close((f.j().sum((1,2,3))-momentum)[:2],expected[:2],atol=2e-14,rtol=1e-9)


@pytest.mark.parametrize('dx',[.1,1.,10.])
def test_high_re_preserves_positive_margin_and_health(dx):
    s=Session(case(dx),'cpu');s.advance(100)
    assert s.quality['finite'] and s.quality['max_lattice_mach']<.1
    assert s.solver.collision.relaxation_margin.min()>0
    assert s.quality['transfer_eligible'] is True
    assert s.quality['transfer_scope']=='experimental-neutral-nesting'
    assert s.quality['physical_model_status']=='unvalidated-neutral-precursor'
    assert s.quality['boundary_method']=='halfway-specular-stress-v1'
    assert s.quality['boundary_flux'] is None
    assert np.max(np.abs(s.quality['wall_diagnostics']['wall_mass_exchange_lu']))<1e-6
    assert s.quality['physical_model_status']=='unvalidated-neutral-precursor'


def test_cpu_mps_reference():
    if not torch.backends.mps.is_available():pytest.skip('MPS unavailable')
    spec=case(10.);ref,sim=make(spec,lt.Context('cpu',torch.float64,use_native=False));sim(100)
    for device in ['cpu','mps']:
        s=Session(spec,device);s.advance(100)
        np.testing.assert_allclose(s.fields()['velocity'],ref.u_pu.numpy(),atol=3e-5,rtol=3e-4)
        assert abs(s.relative_mass_change)<1e-6


def test_shifted_regularization_matches_absolute_reference():
    from hawa.neutral import ShiftedRegularizedSGS
    f,sim=make(case(),lt.Context('cpu',torch.float64,use_native=False))
    e=f.torch_stencil.e;w=f.torch_stencil.w[:,None,None,None]
    f.f += 1e-5*w*e[:,0,None,None,None]*e[:,2,None,None,None]
    shifted=ShiftedRegularizedSGS(.3,cs=0)(f)
    from hawa.plugin import WindFlow
    spec=case();spec.pop('neutral_precursor');spec['collision']='regularized';spec['boundaries']=['inlet','outlet']+['periodic']*4
    absolute=WindFlow(f.context,spec);absolute.f=f.f+w
    reference=lt.RegularizedCollision(.8)
    # Upstream overwrites constructor tau on first call; use matching units here.
    reference(absolute);reference.tau=.8
    torch.testing.assert_close(shifted+w,reference(absolute),rtol=2e-13,atol=1e-15)


def _uniform_shear(flow, velocity, strain):
    """Shifted populations w(3eu+4.5(eu)^2-1.5u^2) + 4.5 w Q:Pi with Pi_xy=Pi_yx=strain."""
    e=np.asarray(flow.stencil.e,dtype=float);w=np.asarray(flow.stencil.w,dtype=float)
    pi=np.zeros((3,3));pi[0,1]=pi[1,0]=strain
    q=np.einsum('qa,qb->qab',e,e)-np.eye(3)[None]/3
    eu=e@velocity
    eq=w*(3*eu+4.5*eu*eu-1.5*velocity@velocity)
    neq=4.5*w*np.einsum('qab,ab->q',q,pi)
    return eq,neq


def test_storage_resolution_threshold_tracks_fp32_roundoff():
    from hawa.neutral import ShiftedRegularizedSGS
    f,_=make(case(),lt.Context('cpu',torch.float32,use_native=False))
    velocity=np.array([.02,0.,.01]);eq,neq=_uniform_shear(f,velocity,1e-4)
    f.f[:]=torch.tensor(eq+neq,dtype=torch.float32)[:,None,None,None]
    # Independent R: dissipative update / FP32 half-ulp of the stored population.
    m=np.abs(neq).max()/(2.**-24*np.abs(eq-neq).max())
    threshold=10/(4*m-20)   # solves 4d/(1+2d)*m = 10
    below=ShiftedRegularizedSGS(.7*threshold,cs=0).storage_resolution(f)
    above=ShiftedRegularizedSGS(1.4*threshold,cs=0).storage_resolution(f)
    assert below['unit_roundoff']==2.**-24 and below['storage_dtype']=='float32'
    assert below['model_resolved_share']==0 and below['model_status']=='below-storage-precision'
    assert below['molecular_status']=='below-storage-precision'
    assert above['model_resolved_share']==1 and above['model_status']=='resolved'
    assert above['molecular_resolved_share']==1 and above['molecular_status']=='resolved'
    # FP64 storage represents the same weak increment.
    f64,_=make(case(),lt.Context('cpu',torch.float64,use_native=False))
    f64.f[:]=torch.tensor(eq+neq,dtype=torch.float64)[:,None,None,None]
    assert ShiftedRegularizedSGS(.7*threshold,cs=0).storage_resolution(f64)['molecular_status']=='resolved'
    # SGS adds a strain-dependent increment that can resolve model dissipation alone.
    sgs=ShiftedRegularizedSGS(.7*threshold,cs=.17).storage_resolution(f)
    assert sgs['model_status']=='resolved' and sgs['molecular_status']=='below-storage-precision'


def test_storage_resolution_weights_dissipation_and_fluid_mask():
    from hawa.neutral import ShiftedRegularizedSGS
    f,_=make(case(),lt.Context('cpu',torch.float32,use_native=False))
    velocity=np.array([.02,0.,0.])
    strong=_uniform_shear(f,velocity,1e-3);weak=_uniform_shear(f,velocity,2e-5)
    f.f[:,:6]=torch.tensor(sum(strong),dtype=torch.float32)[:,None,None,None]
    f.f[:,6:]=torch.tensor(sum(weak),dtype=torch.float32)[:,None,None,None]
    m=np.abs(strong[1]).max()/(2.**-24*np.abs(strong[0]-strong[1]).max())
    collision=ShiftedRegularizedSGS(2*10/(4*m-20),cs=0)   # strong resolved, weak 50x lower
    expected=1e-6/(1e-6+(2e-5)**2)                         # equal cell counts, weight ~ Pi:Pi
    result=collision.storage_resolution(f)
    assert result['model_resolved_share']==pytest.approx(expected,rel=1e-4)
    weak_only=torch.zeros(12,12,12,dtype=torch.bool);weak_only[6:]=True
    assert collision.storage_resolution(f,weak_only)['model_resolved_share']==0
    assert collision.storage_resolution(f,~weak_only)['model_resolved_share']==pytest.approx(1)
    f.f.zero_()   # rest: nothing to dissipate
    rest=collision.storage_resolution(f)
    assert rest['model_resolved_share'] is None and rest['model_status']=='no-strain'
    assert rest['molecular_status']=='no-strain'


@pytest.mark.parametrize('dx',[1.,10.])
def test_session_quality_reports_unresolved_molecular_dissipation(dx):
    s=Session(case(dx),'cpu');s.advance(100)
    storage=s.quality['dissipation_storage']
    assert storage['policy']=='hawa-storage-dissipation-v1' and storage['storage_dtype']=='float32'
    # The near-wall shear is resolved through SGS; molecular air is below FP32 storage.
    assert storage['model_status']=='resolved' and storage['molecular_status']=='below-storage-precision'
    legacy=Session(dict(shape=[8,8,8],dx=.001,speed=1.,viscosity=1.5e-5),'cpu')
    assert legacy.quality['dissipation_storage'] is None


def test_reversal_and_checkpoint_reset(tmp_path):
    from hawa.plugin import dispatch
    for direction in ([1.,0.,0.],[-1.,0.,0.],[0.,1.,0.]):
        spec=case();spec['neutral_precursor']['direction']=direction
        s=Session(spec,'cpu');s.advance(15)
        traction=np.array(s.solver.rough_floor.report['mean_traction_on_fluid_pa'])
        assert traction @ direction < 0
    s=dispatch({'op':'create','case':case(),'device':'cpu'})
    sid=s['session'];path=str(tmp_path/'neutral.npz')
    try:
        dispatch({'op':'step','session':sid,'steps':10})
        dispatch({'op':'save','session':sid,'path':path})
        dispatch({'op':'reset','session':sid})
        assert dispatch({'op':'status','session':sid})['quality']['wall_diagnostics']=={}
        dispatch({'op':'load','session':sid,'path':path})
        dispatch({'op':'step','session':sid,'steps':5})
        assert dispatch({'op':'status','session':sid})['steps']==15
    finally: dispatch({'op':'close','session':sid})


def test_empty_contract_is_not_silently_ignored():
    spec=case();spec['collision']='regularized';spec['neutral_precursor']={}
    with pytest.raises(ValueError,match='schema'):check_case(spec)


def test_filter_checkpoint_continuation(tmp_path):
    from hawa.plugin import dispatch,SESSIONS
    spec=case();spec['neutral_precursor'].update(wall_sample_index=1,wall_filter_seconds=3.)
    sid=dispatch({'op':'create','case':spec,'device':'cpu'})['session']
    path=str(tmp_path/'filter.npz')
    try:
        dispatch({'op':'step','session':sid,'steps':20});dispatch({'op':'save','session':sid,'path':path})
        dispatch({'op':'step','session':sid,'steps':20});expected=SESSIONS[sid].flow.f.clone()
        dispatch({'op':'load','session':sid,'path':path});dispatch({'op':'step','session':sid,'steps':20})
        torch.testing.assert_close(SESSIONS[sid].flow.f,expected,atol=0,rtol=0)
    finally:dispatch({'op':'close','session':sid})
