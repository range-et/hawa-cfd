"""HAWA-003 storage-dissipation diagnostic and physical-viscosity precision harness."""
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest
import torch
import lettuce as lt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import verify_atmospheric_precision as precision
from hawa.neutral import MODEL, ShiftedRegularizedSGS, _storage_status, make
from hawa.plugin import Session, WindFlow


def case(dx=1.):
    return dict(shape=[12,12,12],dx=dx,speed=5.,viscosity=1.5e-5,density=1.225,mach=.05,
                collision=MODEL,boundaries=['periodic']*4+['wall','slip'],
                neutral_precursor=dict(schema=1,experimental=True,reference_height_m=6*dx,
                    roughness_length_m=.01*dx,perturbation_fraction=0.))


def _uniform_shear(flow, velocity, strain):
    """Shifted populations w(3eu+4.5(eu)^2-1.5u^2) + 4.5 w Q:Pi with Pi_xy=Pi_yx=strain."""
    e=np.asarray(flow.stencil.e,dtype=float);w=np.asarray(flow.stencil.w,dtype=float)
    pi=np.zeros((3,3));pi[0,1]=pi[1,0]=strain
    q=np.einsum('qa,qb->qab',e,e)-np.eye(3)[None]/3
    eu=e@velocity
    eq=w*(3*eu+4.5*eu*eu-1.5*velocity@velocity)
    neq=4.5*w*np.einsum('qab,ab->q',q,pi)
    return eq,neq


def _threshold(eq, neq, ratio=10.):
    """Margin d at which 4d/(1+2d) max|neq| equals ratio FP32 half-ulps of max|eq-neq|."""
    m=np.abs(neq).max()/(2.**-24*np.abs(eq-neq).max())
    return ratio/(4*m-2*ratio)


def test_storage_status_boundaries_and_device_qualification():
    for qualified in (True,False):
        assert _storage_status(None,qualified)=='no-strain'
        assert _storage_status(.4999999,qualified)=='below-storage-precision'
        assert _storage_status(0.,qualified)=='below-storage-precision'
    assert _storage_status(.5,True)=='resolved' and _storage_status(1.,True)=='resolved'
    # Unqualified arithmetic (MPS) never claims resolved dissipation.
    assert _storage_status(.5,False)=='indeterminate-device-arithmetic'
    assert _storage_status(1.,False)=='indeterminate-device-arithmetic'


def test_collision_relaxation_matches_absolute_regularized_reference():
    # Large margin: the dissipative fraction 4d/(1+2d) differs from nearby forms.
    f,_=make(case(),lt.Context('cpu',torch.float64,use_native=False))
    e=f.torch_stencil.e;w=f.torch_stencil.w[:,None,None,None]
    f.f += 1e-5*w*e[:,0,None,None,None]*e[:,2,None,None,None]
    collision=ShiftedRegularizedSGS(.3,cs=0)
    shifted=collision(f)
    assert torch.equal(collision.relaxation_margin,torch.full_like(collision.relaxation_margin,.3))
    spec=case();spec.pop('neutral_precursor');spec['collision']='regularized';spec['boundaries']=['inlet','outlet']+['periodic']*4
    absolute=WindFlow(f.context,spec);absolute.f=f.f+w
    reference=lt.RegularizedCollision(.8)
    reference(absolute);reference.tau=.8
    torch.testing.assert_close(shifted+w,reference(absolute),rtol=2e-13,atol=1e-15)


def test_storage_resolution_threshold_tracks_fp32_roundoff():
    f,_=make(case(),lt.Context('cpu',torch.float32,use_native=False))
    velocity=np.array([.02,0.,.01]);eq,neq=_uniform_shear(f,velocity,1e-4)
    f.f[:]=torch.tensor(eq+neq,dtype=torch.float32)[:,None,None,None]
    threshold=_threshold(eq,neq)
    # +/-5% around the independently derived threshold: ratio 10, roundoff 2^-24.
    below=ShiftedRegularizedSGS(.95*threshold,cs=0).storage_resolution(f)
    above=ShiftedRegularizedSGS(1.05*threshold,cs=0).storage_resolution(f)
    assert below=={'policy':'hawa-storage-dissipation-v2','storage_dtype':'float32',
                   'unit_roundoff':2.**-24,'ratio_threshold':10.,'device':'cpu','arithmetic_qualified':True,
                   'model_resolved_share':0.,'model_status':'below-storage-precision',
                   'molecular_resolved_share':0.,'molecular_status':'below-storage-precision',
                   'scope':'Storage representation of collision dissipation only; not accuracy or atmospheric validation'}
    assert above['model_resolved_share']==1 and above['model_status']=='resolved'
    assert above['molecular_resolved_share']==1 and above['molecular_status']=='resolved'
    # FP64 storage represents the same weak increment.
    f64,_=make(case(),lt.Context('cpu',torch.float64,use_native=False))
    f64.f[:]=torch.tensor(eq+neq,dtype=torch.float64)[:,None,None,None]
    fp64=ShiftedRegularizedSGS(.95*threshold,cs=0).storage_resolution(f64)
    assert fp64['storage_dtype']=='float64' and fp64['unit_roundoff']==2.**-53
    assert fp64['molecular_status']=='resolved'
    # SGS adds a strain-dependent increment that can resolve model dissipation alone.
    sgs=ShiftedRegularizedSGS(.95*threshold,cs=.17).storage_resolution(f)
    assert sgs['model_resolved_share']==1 and sgs['molecular_resolved_share']==0


def test_storage_floor_uses_post_collision_population():
    # Density excess plus isotropic stress: the post-collision population eq-neq (1-1/tau ~ -1)
    # has a much larger rest value than eq+neq, so the floor must use eq-neq.
    f,_=make(case(),lt.Context('cpu',torch.float32,use_native=False))
    e=np.asarray(f.stencil.e,dtype=float);w=np.asarray(f.stencil.w,dtype=float)
    eq=w*3e-3
    neq=4.5*w*np.einsum('qab,ab->q',np.einsum('qa,qb->qab',e,e)-np.eye(3)[None]/3,4e-4*np.eye(3))
    assert np.abs(eq-neq).max()/np.abs(eq+neq).max()>3
    f.f[:]=torch.tensor(eq+neq,dtype=torch.float32)[:,None,None,None]
    threshold=_threshold(eq,neq)
    assert ShiftedRegularizedSGS(.95*threshold,cs=0).storage_resolution(f)['model_resolved_share']==0
    assert ShiftedRegularizedSGS(1.05*threshold,cs=0).storage_resolution(f)['model_resolved_share']==1


def test_storage_ratio_boundary_counts_as_resolved():
    # Pure shear Pi_xy=2^-10 at rest: eq=0 exactly, so max|neq|/(2^-24 max|eq-neq|) = 2^24 exactly.
    f,_=make(case(),lt.Context('cpu',torch.float32,use_native=False))
    eq,neq=_uniform_shear(f,np.zeros(3),2.**-10)
    f.f[:]=torch.tensor(neq,dtype=torch.float32)[:,None,None,None]
    # FP32 margin whose 4d/(1+2d) is exactly 10*2^-24, so R == 10 exactly.
    margin=float(np.float32(1.4901166878189542e-07))
    from hawa.neutral import _relaxed_fraction
    assert float(_relaxed_fraction(torch.tensor(margin,dtype=torch.float32))*2**24)==10.
    at=ShiftedRegularizedSGS(margin,cs=0).storage_resolution(f)
    assert at['model_resolved_share']==1 and at['molecular_resolved_share']==1
    below=float(np.nextafter(np.float32(margin),np.float32(0)))
    assert ShiftedRegularizedSGS(below,cs=0).storage_resolution(f)['model_resolved_share']==0


def test_storage_resolution_weights_dissipation_and_fluid_mask():
    f,_=make(case(),lt.Context('cpu',torch.float32,use_native=False))
    velocity=np.array([.02,0.,0.])
    strong=_uniform_shear(f,velocity,1e-3);weak=_uniform_shear(f,velocity,2e-5)
    f.f[:,:6]=torch.tensor(sum(strong),dtype=torch.float32)[:,None,None,None]
    f.f[:,6:]=torch.tensor(sum(weak),dtype=torch.float32)[:,None,None,None]
    collision=ShiftedRegularizedSGS(2*_threshold(*strong),cs=0)   # strong resolved, weak 50x lower
    expected=1e-6/(1e-6+(2e-5)**2)                                # equal cell counts, weight ~ Pi:Pi
    result=collision.storage_resolution(f)
    assert result['model_resolved_share']==pytest.approx(expected,rel=1e-4)
    assert result['molecular_resolved_share']==pytest.approx(expected,rel=1e-4)
    weak_only=torch.zeros(12,12,12,dtype=torch.bool);weak_only[6:]=True
    assert collision.storage_resolution(f,weak_only)['model_resolved_share']==0
    assert collision.storage_resolution(f,~weak_only)['model_resolved_share']==pytest.approx(1)
    f.f.zero_()   # rest: nothing to dissipate
    rest=collision.storage_resolution(f)
    assert rest['model_resolved_share'] is None and rest['model_status']=='no-strain'
    assert rest['molecular_resolved_share'] is None and rest['molecular_status']=='no-strain'


@pytest.mark.parametrize('dx',[1.,10.])
def test_session_quality_reports_unresolved_molecular_dissipation(dx):
    s=Session(case(dx),'cpu');s.advance(100)
    storage=s.quality['dissipation_storage']
    assert storage['policy']=='hawa-storage-dissipation-v2' and storage['storage_dtype']=='float32'
    # The near-wall shear is resolved through SGS; molecular air is below FP32 storage.
    assert storage['model_status']=='resolved' and storage['molecular_status']=='below-storage-precision'
    legacy=Session(dict(shape=[8,8,8],dx=.001,speed=1.,viscosity=1.5e-5),'cpu')
    assert legacy.quality['dissipation_storage'] is None


def test_invalid_neutral_state_reports_no_storage_diagnostic():
    from hawa.quality import assess
    s=Session(case(),'cpu');s.flow.f[0,0,0,0]=float('nan')
    quality=assess(s)
    assert quality['finite'] is False and quality['dissipation_storage'] is None


def test_shear_wave_initial_state_is_analytic():
    margin,amp,n=1e-3,.1,16
    flow = precision.ShearWave(lt.Context('cpu', torch.float64, use_native=False), n, amp, margin)
    scale,k=.05/math.sqrt(3),2*math.pi/n
    x=torch.arange(n,dtype=torch.float64)[:,None,None]
    expected=torch.zeros(3,n,4,4,dtype=torch.float64)
    expected[1]=amp*scale*torch.sin(k*x);expected[2]=scale
    torch.testing.assert_close(flow.u(),expected,atol=1e-17,rtol=1e-13)
    torch.testing.assert_close(flow.rho(), torch.ones_like(flow.rho()), atol=1e-15, rtol=0)
    # Shifted second moment = rho u u + Chapman-Enskog stress -(2/3) tau S, S_xy = A k cos/2.
    second=expected[:,None]*expected[None]
    stress=-(2/3)*(.5+margin)*.5*amp*scale*k*torch.cos(k*x).expand(n,4,4)
    second[0,1]=second[0,1]+stress;second[1,0]=second[1,0]+stress
    torch.testing.assert_close(flow.shear_tensor(),second,atol=1e-17,rtol=1e-12)
    assert precision.amplitude(flow)==pytest.approx(amp*scale,rel=1e-12)
    assert flow.post_boundaries == []
    with pytest.raises(NotImplementedError, match='^ShearWave initializes populations directly$'):
        flow.initial_pu()
    # Density of supplied shifted populations: 1 + sum over q, keeping the lattice axis.
    supplied=torch.full_like(flow.f,.5/19)
    torch.testing.assert_close(flow.rho(supplied),torch.full((1,n,4,4),1.5,dtype=torch.float64),atol=1e-15,rtol=0)


def test_amplitude_projects_only_the_sine_mode():
    flow = precision.ShearWave(lt.Context('cpu', torch.float64, use_native=False), 8, 0., 1e-3)
    x=torch.arange(8,dtype=torch.float64)[:,None,None]
    e=flow.torch_stencil.e;w=flow.torch_stencil.w[:,None,None,None]
    for mode,expected in ((torch.sin(2*math.pi*x/8),.003),(torch.cos(2*math.pi*x/8),0.)):
        flow.f=3*w*e[:,1,None,None,None]*(.003*mode)   # j_y = rho u_y for rho=1
        assert precision.amplitude(flow)==pytest.approx(expected,abs=1e-15)


def test_measure_contract_and_analytic_fp64_decay():
    # nu_lu = margin/3: the analytic shear-wave decay gives delta_ratio = 1.
    result = precision.measure(1., 0., .01, 'cpu', torch.float64, n=16, steps=1000, sample=100, margin=1e-2)
    assert set(result)=={'dx_m','cs','wave_fraction','device','dtype','n','steps','samples','physical_time_s',
                         'margin','delta_effective','delta_ratio','storage'}
    assert (result['dx_m'],result['cs'],result['wave_fraction'],result['device'],result['dtype'],result['n'],
            result['steps'],result['samples'],result['margin'])==(1.,0.,.01,'cpu','float64',16,1000,11,1e-2)
    assert result['delta_ratio'] == pytest.approx(1., abs=.02)
    assert result['delta_effective'] == pytest.approx(result['delta_ratio']*1e-2, rel=1e-12)
    assert result['physical_time_s'] == pytest.approx(1000*.05/(math.sqrt(3)*5.), rel=1e-12)
    assert result['storage']['molecular_status'] == 'resolved'
    for steps, sample in ((900, 100), (1050, 100)):
        with pytest.raises(ValueError, match='^Steps must be a multiple of sample and contain at least ten samples$'):
            precision.measure(1., 0., .01, steps=steps, sample=sample)


def test_measure_fits_log_amplitude_over_last_ninety_percent(monkeypatch):
    # Curved log-amplitude: the fitted slope depends on exactly which samples are kept.
    calls=[]
    def fake(flow):
        t=5*len(calls);calls.append(t)
        return math.exp(-1e-3*t+2e-5*t*t)
    monkeypatch.setattr(precision,'amplitude',fake)
    result=precision.measure(1.,0.,.01,'cpu',torch.float64,n=16,steps=100,sample=5,margin=1e-2)
    times=np.arange(0,101,5.);keep=times>=10
    slope=np.polyfit(times[keep],-1e-3*times[keep]+2e-5*times[keep]**2,1)[0]
    assert calls==list(range(0,101,5)) and result['samples']==21
    assert result['delta_effective']==pytest.approx(-3*slope/(2*math.pi/16)**2,rel=1e-9)


@pytest.mark.parametrize('value',[0.,float('nan'),float('inf')])
def test_vanished_or_nonfinite_amplitude_is_an_error_not_a_fit(monkeypatch, value):
    monkeypatch.setattr(precision, 'amplitude', lambda flow: value)
    with pytest.raises(RuntimeError, match='^Shear-wave amplitude became nonfinite or vanished$'):
        precision.measure(1., 0., .01, n=16, steps=100, sample=10)


def test_compare_applies_five_percent_tolerance_and_flags_disagreement():
    resolved=dict(model_status='resolved');below=dict(model_status='below-storage-precision')
    result = precision.compare(dict(delta_effective=2.), dict(delta_effective=2.08, storage=below))
    assert result == dict(relative_error_vs_fp64=pytest.approx(.04), represented=True,
                          diagnostic_predicted_resolved=False, diagnostic_agrees=False)
    assert precision.compare(dict(delta_effective=2.), dict(delta_effective=1.88, storage=resolved)) == dict(
        relative_error_vs_fp64=pytest.approx(-.06), represented=False,
        diagnostic_predicted_resolved=True, diagnostic_agrees=False)
    assert precision.compare(dict(delta_effective=2.), dict(delta_effective=1.902, storage=resolved))['diagnostic_agrees'] is True
    assert precision.compare(dict(delta_effective=2.), dict(delta_effective=-1., storage=below))['diagnostic_agrees'] is True


def test_declared_inventory_is_frozen():
    import inspect
    defaults={k:v.default for k,v in inspect.signature(precision.measure).parameters.items()}
    assert defaults==dict(dx=inspect.Parameter.empty,cs=inspect.Parameter.empty,wave=inspect.Parameter.empty,
                          device='cpu',dtype=torch.float32,n=32,steps=4000,sample=100,margin=None)
    assert precision.SPEED==5. and precision.VISCOSITY==1.5e-5 and precision.MACH==.05 and precision.TOLERANCE==.05
    assert precision.CASES=={
        'physical':[dict(dx=.1,cs=0.,wave=.01),dict(dx=1.,cs=0.,wave=.01),dict(dx=10.,cs=0.,wave=.01),
                    dict(dx=.1,cs=.17,wave=.1),dict(dx=.1,cs=.17,wave=.01),dict(dx=1.,cs=.17,wave=.1),
                    dict(dx=1.,cs=.17,wave=.01),dict(dx=10.,cs=.17,wave=.1),dict(dx=10.,cs=.17,wave=.01)],
        'calibration':[dict(dx=1.,cs=0.,wave=.01,margin=m) for m in (1e-5,1e-4,1e-3,1e-2)],
        'validation':[dict(dx=1.,cs=.17,wave=.03),dict(dx=10.,cs=.17,wave=.1,n=16),
                      dict(dx=1.,cs=.17,wave=.1,n=64,steps=8000),dict(dx=1.,cs=0.,wave=.01,margin=3e-4),
                      dict(dx=1.,cs=0.,wave=.01,margin=3e-3),dict(dx=1.,cs=.3,wave=.01),dict(dx=1.,cs=.17,wave=.3)]}


def _fake_measure(ratios, statuses, calls):
    def measure(dx, cs, wave, device='cpu', dtype=torch.float32, **entry):
        calls.append((dx, cs, wave, device, dtype, entry))
        key='ref' if dtype==torch.float64 else device
        return dict(dx_m=dx, cs=cs, delta_effective=ratios[(dx,key)], delta_ratio=ratios[(dx,key)],
                    storage=dict(model_status=statuses.get((dx,key),'below-storage-precision')))
    return measure


def test_run_acceptance_logic(monkeypatch):
    cases={'physical':[dict(dx=1.,cs=0.,wave=.01,n=16),dict(dx=1.,cs=.17,wave=.1)],
           'validation':[dict(dx=2.,cs=0.,wave=.01,margin=1e-3)]}
    snapshot=json.dumps(cases)
    ratios={(1.,'ref'):1.04,(1.,'cpu'):1.04,(1.,'mps'):-2.,(2.,'ref'):1.,(2.,'cpu'):1.,(2.,'mps'):1.}
    statuses={(1.,'cpu'):'resolved',(2.,'cpu'):'resolved',(2.,'mps'):'resolved'}
    calls=[]
    monkeypatch.setattr(precision,'measure',_fake_measure(ratios,statuses,calls))
    rows,summary=precision.run(['cpu','mps'],cases)
    assert json.dumps(cases)==snapshot          # declared entries are not consumed
    assert calls[:3]==[(1.,0.,.01,'cpu',torch.float64,{'n':16}),(1.,0.,.01,'cpu',torch.float32,{'n':16}),
                       (1.,0.,.01,'mps',torch.float32,{'n':16})]
    assert [r['group'] for r in rows]==['physical','physical','validation']
    assert rows[0]['fp32']['mps']['represented'] is False and rows[0]['fp32']['mps']['diagnostic_agrees'] is True
    assert summary==dict(collision_fp64_represents_molecular=True,diagnostic_agrees_on_all_fp32_cases=True,
                         fp32_molecular_represented={'cpu:1.0':True,'mps:1.0':False},
                         false_resolved_cases=0,conservative_misses=0,passed=True)
    # A diagnostic disagreement fails the gate even when the collision passes.
    statuses[(2.,'mps')]='below-storage-precision'
    summary=precision.run(['cpu','mps'],cases)[1]
    assert summary['collision_fp64_represents_molecular'] is True and summary['diagnostic_agrees_on_all_fp32_cases'] is False
    assert (summary['false_resolved_cases'],summary['conservative_misses'],summary['passed'])==(0,1,False)
    # A false 'resolved' is counted separately from conservative misses.
    statuses[(2.,'mps')]='resolved';ratios[(2.,'mps')]=1.2
    summary=precision.run(['cpu','mps'],cases)[1]
    assert (summary['false_resolved_cases'],summary['conservative_misses'],summary['passed'])==(1,0,False)
    ratios[(2.,'mps')]=1.
    # FP64 molecular error above 5% fails criterion 1.
    statuses[(2.,'mps')]='resolved';ratios[(1.,'ref')]=1.06
    summary=precision.run(['cpu','mps'],cases)[1]
    assert summary['collision_fp64_represents_molecular'] is False and summary['passed'] is False
    ratios[(1.,'ref')]=.94
    assert precision.run(['cpu','mps'],cases)[1]['collision_fp64_represents_molecular'] is False
    # Without a zero-SGS physical case, criterion 1 has no evidence and cannot pass.
    summary=precision.run(['cpu'],{'validation':cases['validation']})[1]
    assert summary['collision_fp64_represents_molecular'] is False and summary['fp32_molecular_represented']=={}


def test_main_writes_report_and_exit_code(tmp_path, monkeypatch):
    seen=[]
    def run(devices):
        seen.append(devices)
        return [dict(group='physical')], dict(passed=len(seen)==1, collision_fp64_represents_molecular=True)
    monkeypatch.setattr(precision,'run',run)
    output=tmp_path/'new'/'nested'/'report.json'
    with pytest.raises(SystemExit):
        precision.main([])   # --output is required
    assert precision.main(['--output',str(output)])==0
    report=json.loads(output.read_text())
    assert seen==[['cpu']]
    assert {k:report[k] for k in ('schema','issue','claim','air','tolerance','cases','passed')}==dict(
        schema=1, issue='HAWA-003 / range-et/hawa-cfd#13',
        claim='storage/collision representation of declared dissipation; not atmospheric validation',
        air=dict(speed_m_s=5., viscosity_m2_s=1.5e-5, mach=.05), tolerance=.05,
        cases=[dict(group='physical')], passed=True)
    assert set(report['environment'])=={'python','torch','numpy','os','devices'} and report['environment']['devices']==['cpu']
    assert report['collision_fp64_represents_molecular'] is True
    # Existing parent directory, repeated devices and a failed gate.
    assert precision.main(['--output',str(output),'--device','cpu','--device','mps'])==2
    assert seen[-1]==['cpu','mps'] and json.loads(output.read_text())['passed'] is False


def test_fp32_physical_air_loses_molecular_dissipation():
    rows, summary = precision.run(['cpu'], {'physical': [dict(dx=.1, cs=0., wave=.01, n=16, steps=1000, sample=50)]})
    reference, fp32 = rows[0]['reference_fp64'], rows[0]['fp32']['cpu']
    # Molecular increment 3 nu dt/dx^2 with dt = Ma dx/(sqrt(3) U); FP64 keeps it, FP32 storage cannot.
    assert reference['margin'] == pytest.approx(3*1.5e-5*(.05*.1/(math.sqrt(3)*5))/.01, rel=1e-12)
    assert reference['delta_ratio'] == pytest.approx(1., abs=.05)
    assert fp32['represented'] is False and fp32['storage']['molecular_status'] == 'below-storage-precision'
    assert summary == dict(collision_fp64_represents_molecular=True, diagnostic_agrees_on_all_fp32_cases=True,
                           fp32_molecular_represented={'cpu:0.1': False}, false_resolved_cases=0,
                           conservative_misses=0, passed=True)


def test_script_entry_point_runs_main(monkeypatch, capsys):
    import runpy
    script=Path(__file__).resolve().parents[1]/'scripts'/'verify_atmospheric_precision.py'
    monkeypatch.setattr(sys,'argv',[str(script),'--help'])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(script),run_name='__main__')
    assert exit_info.value.code==0
    out=capsys.readouterr().out
    assert out.startswith('usage:') and '--output' in out
