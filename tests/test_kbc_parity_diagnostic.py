"""Diagnostic evidence must preserve failures, device identity and original limits."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import torch
import lettuce as lt

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('diagnose_kbc_parity',ROOT/'scripts/diagnose_kbc_parity.py')
study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)


def test_frozen_cell_reference_and_raw_cpu_control():
    flow=study.make_flow('cpu',1,torch.float64)
    np.testing.assert_array_equal(flow.f[:,0,0].numpy(),np.array(study.POPULATIONS,dtype=np.float32).astype(np.float64))
    stages=study.inspect_collision(flow)
    assert flow.units.relaxation_parameter_lu==0.5009765625
    assert stages['raw_gamma'].item()==pytest.approx(.0016176334459674369,rel=1e-8)
    assert not stages['near_zero'].any() and not stages['negative_reset'].any()
    raw=study.study('cpu',[1,8])
    assert raw['passed'] and all(row['initial_identical'] for row in raw['rows'])
    assert raw['rows'][0]['raw_vs_reference']['max_abs'] > 0
    assert raw['rows'][0]['public_vs_raw']['max_abs'] > 0
    for row in raw['rows']:
        assert row['device']=='cpu' and row['dtype']=='torch.float32'
        assert row['public_vs_reference']['max_abs']==0
        assert row['compensated_exact'] and row['compensated_vs_reference']['max_abs']==0
        assert row['mass_error']['passed'] and row['momentum_error']['passed']


@pytest.mark.parametrize('size',[0,-1,513,1.5,True])
def test_invalid_size_is_rejected_before_flow_allocation(size):
    with pytest.raises(ValueError,match='side length'):study.make_flow('cpu',size)


@pytest.mark.parametrize('device,sizes',[('auto',[1]),('cpu',[]),('cpu',[1,1]),('cpu',[1,2,3,4,5])])
def test_invalid_study_scope(device,sizes):
    with pytest.raises(ValueError):study.study(device,sizes)


def test_comparison_preserves_original_population_threshold_and_nonfinite_failure():
    reference=torch.tensor([0.,1.],dtype=torch.float64)
    assert study.compare(reference,reference+torch.tensor([1e-6,1e-4]))['passed']
    result=study.compare(reference,reference+torch.tensor([2e-5,.002]))
    assert not result['passed'] and result['failed_values']==2
    assert result['rtol']==1e-3 and result['atol']==1e-5
    for candidate in [torch.tensor([float('nan'),1]),torch.ones(3)]:
        with pytest.raises(ValueError,match='matching finite'):study.compare(reference,candidate)
    with pytest.raises(ValueError,match='Nonfinite'):study.summarize({'bad':torch.tensor([float('inf')])})


def test_main_cpu_reports_exact_scope_and_provenance(tmp_path):
    output=tmp_path/'evidence'
    assert study.main(['--device','cpu','--sizes','1','--output',str(output)])==0
    result=json.loads((output/'result.json').read_text())
    assert result['passed'] and result['completed']
    assert not result['original_512x512_50_step_qualified']
    assert result['source_before']==result['source_after']==study.source_hashes()
    assert 'vendor/lettuce/lettuce/ext/_collision/kbc_collision.py' in result['source_before']
    with pytest.raises(FileExistsError):study.main(['--device','cpu','--sizes','1','--output',str(output)])


@pytest.mark.parametrize('failure',['numeric','exception','source_drift','size'])
def test_main_saves_failed_evidence(tmp_path,monkeypatch,failure):
    if failure=='numeric':
        monkeypatch.setattr(study,'study',lambda *args:dict(passed=False,rows=[dict(public_vs_reference=dict(passed=False))]))
    elif failure=='exception':
        def unavailable(*args):raise RuntimeError('requested device unavailable')
        monkeypatch.setattr(study,'study',unavailable)
    elif failure=='source_drift':
        hashes=iter([{'source':'before'},{'source':'after'}])
        monkeypatch.setattr(study,'source_hashes',lambda:next(hashes))
    output=tmp_path/'failed'
    assert study.main(['--device','cpu','--sizes','0' if failure=='size' else '1','--output',str(output)])==1
    result=json.loads((output/'result.json').read_text())
    assert not result['passed'] and not result['original_512x512_50_step_qualified']
    assert result['completed']==(failure=='numeric')
    if failure!='numeric':assert 'error' in result


@pytest.mark.parametrize('device',['mps','cuda:0'])
def test_accelerator_shape_control_reports_actual_device_and_observed_failure(device):
    if device=='mps' and not torch.backends.mps.is_available():pytest.skip('MPS unavailable')
    if device=='cuda:0' and not torch.cuda.is_available():pytest.skip('CUDA unavailable')
    result=study.study(device,[1,512])
    assert all(torch.device(row['device']).type==torch.device(device).type and row['dtype']=='torch.float32' and row['initial_identical'] for row in result['rows'])
    assert result['passed']==all(row['public_vs_reference']['passed'] and row['compensated_vs_reference']['passed']
                                 for row in result['rows'])
    # The harness observes the current solver. It must not require the defect forever.
    # When the original population criterion fails, evidence keeps that failure visible.
    for row in result['rows']:
        comparison=row['public_vs_reference']
        assert comparison['passed']==(comparison['failed_values']==0)
        assert comparison['rtol']==1e-3 and comparison['atol']==1e-5
        # MPS has no FP64: its public collision is the double-float FP32 kernel.
        if device=='mps':assert comparison==row['compensated_vs_reference']
    assert not result['reference']['negative_reset']['count']


@pytest.mark.parametrize('mismatch',['package','submodule','missing_file'])
def test_main_rejects_wrong_loaded_sources_before_measurement(tmp_path,monkeypatch,mismatch):
    import types
    if mismatch=='package':
        monkeypatch.setattr(study.lt,'__file__',str(tmp_path/'foreign/__init__.py'))
    else:
        module=types.ModuleType('lettuce.foreign')
        if mismatch=='submodule':module.__file__=str(tmp_path/'foreign.py')
        monkeypatch.setitem(study.sys.modules,'lettuce.foreign',module)
    def forbidden(*args):raise AssertionError('measurement must not start')
    monkeypatch.setattr(study,'study',forbidden)
    output=tmp_path/'wrong-import'
    assert study.main(['--device','cpu','--sizes','1','--output',str(output)])==1
    result=json.loads((output/'result.json').read_text())
    assert not result['completed'] and not result['passed']
    assert 'Loaded module is outside' in result['error']
    assert 'loaded_modules_before' in result and 'rows' not in result


def test_loaded_module_validator_requires_package():
    with pytest.raises(ValueError,match='provenance is missing'):study.validate_loaded_modules({})


@pytest.mark.parametrize('failure',['device','nonfinite'])
def test_main_retains_completed_rows_when_later_size_fails(tmp_path,monkeypatch,failure):
    original=study.make_flow
    def fail_second(device,size,dtype=torch.float32):
        if size==8 and dtype==torch.float32:
            if failure=='device':raise RuntimeError('device lost at second size')
            flow=original(device,size,dtype);flow.f.fill_(float('nan'));return flow
        return original(device,size,dtype)
    monkeypatch.setattr(study,'make_flow',fail_second)
    output=tmp_path/'partial'
    assert study.main(['--device','cpu','--sizes','1','8','--output',str(output)])==1
    result=json.loads((output/'result.json').read_text())
    assert not result['completed'] and not result['passed']
    assert result['completed_sizes']==[1] and result['failed_size']==8
    assert len(result['rows'])==1 and result['rows'][0]['size']==1
    assert result['rows'][0]['public_vs_reference']['passed']
    assert 'error' in result


def test_main_rejects_changed_loaded_module_paths(tmp_path,monkeypatch):
    original=study.loaded_module_paths()
    changed=dict(original)
    # Both files are local: a module changing identity still invalidates attribution.
    changed['lettuce']=str(ROOT/'vendor/lettuce/lettuce/_flow.py')
    sequence=iter([original,changed])
    monkeypatch.setattr(study,'loaded_module_paths',lambda:next(sequence))
    output=tmp_path/'changed-import'
    assert study.main(['--device','cpu','--sizes','1','--output',str(output)])==1
    result=json.loads((output/'result.json').read_text())
    assert result['error']=='ValueError: Loaded module provenance changed during diagnostic'
    assert not result['completed']
    assert len(result['rows'])==1


@pytest.mark.parametrize('offset',['ulp','criterion'])
def test_study_fails_when_only_the_double_float_kernel_disagrees(monkeypatch,offset):
    # The CPU public collision still matches the reference; the MPS kernel row
    # must independently fail the original criterion and clear exactness.
    original=lt.KBCCollision._collide_compensated
    def shifted(self,flow,epsilon):
        out=original(self,flow,epsilon)
        return torch.nextafter(out,torch.full_like(out,2.)) if offset=='ulp' else out+2e-3
    monkeypatch.setattr(lt.KBCCollision,'_collide_compensated',shifted)
    result=study.study('cpu',[1])
    row=result['rows'][0]
    assert row['public_vs_reference']['passed'] and row['public_vs_reference']['max_abs']==0
    assert not row['compensated_exact'] and row['compensated_vs_reference']['max_abs']>0
    assert row['compensated_vs_reference']['passed']==(offset=='ulp')
    assert result['passed']==(offset=='ulp')


def test_script_entrypoint_exits_with_report_status(tmp_path,monkeypatch,capsys):
    import runpy,sys
    output=tmp_path/'entrypoint'
    monkeypatch.setattr(sys,'argv',['diagnose_kbc_parity.py','--device','cpu','--sizes','1','--output',str(output)])
    with pytest.raises(SystemExit) as stop:
        runpy.run_path(str(ROOT/'scripts/diagnose_kbc_parity.py'),run_name='__main__')
    assert stop.value.code==0
    assert json.loads(capsys.readouterr().out)=={'completed':True,'passed':True,'scope':'repeated-single-cell KBC diagnostic'}
    assert json.loads((output/'result.json').read_text())['rows'][0]['compensated_exact']


# --- Whole-script contracts (targeted mutation of the diagnostic) -------------
import re
import time

STAGES={'rho','velocity','equilibrium','shear','higher','numerator','denominator',
        'raw_gamma','applied_gamma','near_zero','negative_reset','output'}
ROW_KEYS={'size','device','dtype','initial_identical','stages','public_vs_reference',
          'raw_vs_reference','public_vs_raw','compensated_vs_reference','compensated_exact',
          'mass_error','momentum_error'}
HIGHER=torch.tensor([1,-.5,-.5,-.5,-.5,.25,.25,.25,.25],dtype=torch.float64)  # m22 basis
SHEAR=torch.tensor([0,0,0,0,0,.25,-.25,.25,-.25],dtype=torch.float64)        # m11 basis


def exact(message):
    return '^'+re.escape(message)+'$'


def designed_cell(rho,shear,higher):
    flow=study.make_flow('cpu',1,torch.float64)
    u=torch.tensor([.02,-.01],dtype=torch.float64).view(2,1,1)
    feq=flow.equilibrium(flow,torch.full((1,1,1),rho,dtype=torch.float64),u)[:,0,0]
    flow.f=(feq+shear*SHEAR+higher*HIGHER)[:,None,None].clone()
    return flow


def test_inspection_reports_named_stages_and_reproduces_guard_and_reset():
    threshold=(9*study.EPSILON)**2
    # rho = 4: sum_h = 2 (q eps)^2 is below the density-scaled guard only.
    guarded=designed_cell(4.,0.,(2*threshold*4/20.25)**.5)
    stages=study.inspect_collision(guarded)
    assert set(stages)==STAGES
    assert threshold<stages['denominator'].item()<4*threshold
    assert stages['near_zero'].item() and stages['applied_gamma'].item()==2
    # A shear-dominated residual drives the raw stabilizer below zero.
    reset=study.inspect_collision(designed_cell(1.,-1e-3,3.16e-7))
    assert reset['raw_gamma'].item()<0 and not reset['near_zero'].item()
    assert reset['negative_reset'].item() and reset['applied_gamma'].item()==2
    regular=study.inspect_collision(designed_cell(1.,-1e-3,1e-5))
    assert not regular['negative_reset'].item() and regular['applied_gamma'].item()==regular['raw_gamma'].item()


@pytest.mark.parametrize('fault',['output','input'])
def test_inspection_rejects_kernel_output_or_input_drift_of_one_ulp(monkeypatch,fault):
    original=lt.KBCCollision._collide
    def drift(self,flow,epsilon):
        # Input drift happens first, so the output still matches the drifted
        # populations and only the unchanged-input check can reject it.
        if fault=='input':flow.f[0,0,0]=torch.nextafter(flow.f[0,0,0],torch.tensor(2.,dtype=flow.f.dtype))
        out=original(self,flow,epsilon)
        return torch.nextafter(out,torch.full_like(out,2.)) if fault=='output' else out
    monkeypatch.setattr(lt.KBCCollision,'_collide',drift)
    with pytest.raises(AssertionError):study.inspect_collision(study.make_flow('cpu',1,torch.float64))


def test_comparison_reports_exact_statistics_at_the_criterion_boundary():
    reference=torch.tensor([0.,0.,100.],dtype=torch.float64)
    result=study.compare(reference,reference+torch.tensor([1e-5,0.,.1+1e-5],dtype=torch.float64))
    assert result==dict(max_abs=pytest.approx(.1+1e-5),rms=pytest.approx(((1e-10+(.1+1e-5)**2)/3)**.5),
                        failed_values=0,values=3,passed=True,rtol=1e-3,atol=1e-5)
    assert study.RTOL==1e-3 and study.ATOL==1e-5
    result=study.compare(torch.tensor([0.,0.]),torch.tensor([3.,4.]))
    assert result['rms']==pytest.approx(12.5**.5) and result['failed_values']==2 and not result['passed']
    with pytest.raises(ValueError,match=exact('Comparison requires matching finite tensors')):
        study.compare(reference,torch.ones(2))


def test_summary_reports_min_max_first_and_boolean_counts():
    summary=study.summarize({'values':torch.tensor([3.,1.,2.]),'flags':torch.tensor([True,False,True])})
    assert summary=={'values':dict(min=1.,max=3.,first=3.),'flags':dict(min=0.,max=1.,first=1.,count=2)}
    with pytest.raises(ValueError,match=exact('Nonfinite diagnostic stage: bad')):
        study.summarize({'bad':torch.tensor([float('nan')])})


def test_frozen_cell_inputs_and_size_bounds():
    largest=study.make_flow('cpu',512)
    assert largest.f.shape==(9,512,512) and largest.f.dtype==torch.float32
    assert largest.units.relaxation_parameter_lu==0.5009765625
    np.testing.assert_array_equal(largest.f[:,511,0].numpy(),np.array(study.POPULATIONS,dtype=np.float32))
    for size in (0,513):
        with pytest.raises(ValueError,match=exact('Diagnostic side length must be an integer in [1, 512]')):
            study.make_flow('cpu',size)


class _Reached(Exception):
    pass


def _stop_at_measurement(monkeypatch):
    calls=[]
    def reached(device,size,dtype=torch.float32):
        calls.append((device,size,dtype));raise _Reached
    monkeypatch.setattr(study,'make_flow',reached)
    return calls


# Explicit ids: the CPU mutation study deselects ids containing cuda or mps.
@pytest.mark.parametrize('device',['cpu','mps','cuda:0'],ids=['host','apple-gpu','nvidia-gpu'])
def test_study_accepts_each_explicit_device_and_up_to_four_sizes(monkeypatch,device):
    calls=_stop_at_measurement(monkeypatch)
    with pytest.raises(_Reached):study.study(device,[1,2,3,4])
    # The FP64 CPU reference is always built first, from one cell.
    assert calls==[('cpu',1,torch.float64)]


@pytest.mark.parametrize('device,sizes,message',[
    ('auto',[1],'Explicit cpu, mps or cuda:0 device required'),
    ('cpu',[],'Require one to four distinct diagnostic sizes'),
    ('cpu',[1,1],'Require one to four distinct diagnostic sizes'),
    ('cpu',[1,2,3,4,5],'Require one to four distinct diagnostic sizes')],
    ids=['unknown-device','no-size','duplicate-size','five-sizes'])
def test_study_scope_messages(device,sizes,message):
    with pytest.raises(ValueError,match=exact(message)):study.study(device,sizes)


def test_study_rows_and_evidence_bookkeeping():
    evidence={}
    result=study.study('cpu',[1,2],evidence)
    assert result is evidence and result['passed'] and result['failed_size'] is None
    assert result['completed_sizes']==[1,2] and set(result['reference'])==STAGES
    for size,row in zip((1,2),result['rows']):
        assert set(row)==ROW_KEYS and row['size']==size and set(row['stages'])==STAGES
        assert row['device']=='cpu' and row['dtype']=='torch.float32' and row['initial_identical']
        assert row['public_vs_reference']['values']==9*size*size
        assert row['mass_error']['values']==size*size and row['momentum_error']['values']==2*size*size
        assert row['raw_vs_reference']['max_abs']>0 and row['public_vs_raw']['max_abs']>0


def test_main_defaults_and_report_contract(tmp_path,monkeypatch):
    seen=[]
    def recorded(device,sizes,evidence):
        seen.append((device,sizes));return dict(passed=True,rows=[])
    monkeypatch.setattr(study,'study',recorded)
    monkeypatch.setenv('PYTORCH_ENABLE_MPS_FALLBACK','0')
    before=time.monotonic()
    assert study.main(['--output',str(tmp_path/'defaults')])==0
    elapsed=time.monotonic()-before
    assert seen==[('mps',[1,8,32,512])]
    report=json.loads((tmp_path/'defaults'/'result.json').read_text())
    assert report['device']=='mps' and report['sizes']==[1,8,32,512] and report['completed']
    assert report['scope']=='repeated-single-cell KBC diagnostic' and 0<=report['wall_seconds']<=elapsed
    assert set(report['environment'])=={'python','torch','numpy','platform','mps_fallback_env'}
    assert report['environment']['mps_fallback_env']=='0' and report['environment']['torch']==torch.__version__
    assert report['loaded_modules_before']==report['loaded_modules_after']


def test_main_records_exact_error_text(tmp_path,monkeypatch):
    hashes=iter([{'source':'before'},{'source':'after'}])
    monkeypatch.setattr(study,'source_hashes',lambda:next(hashes))
    monkeypatch.setattr(study,'study',lambda *args:dict(passed=True,rows=[]))
    assert study.main(['--device','cpu','--output',str(tmp_path/'drift')])==1
    report=json.loads((tmp_path/'drift'/'result.json').read_text())
    assert report['error']=='ValueError: Source changed during diagnostic' and not report['passed']


def test_provenance_helpers_cover_package_submodules_and_inputs():
    paths=study.loaded_module_paths()
    assert 'lettuce' in paths and 'lettuce.ext._collision.kbc_collision' in paths
    assert all(name=='lettuce' or name.startswith('lettuce.') for name in paths)
    hashes=study.source_hashes()
    for name in ('vendor/lettuce/lettuce/ext/_collision/kbc_collision.py','scripts/diagnose_kbc_parity.py',
                 'pyproject.toml','uv.lock','vendor/lettuce/examples/advanced_flows/PorousMedium.ipynb'):
        assert re.fullmatch('[0-9a-f]{64}',hashes[name])
    assert list(hashes)==sorted(hashes)
    with pytest.raises(ValueError,match=exact('Loaded Lettuce package provenance is missing')):
        study.validate_loaded_modules({})
    with pytest.raises(ValueError,match=exact('Loaded module is outside this checkout vendor source: lettuce.x')):
        study.validate_loaded_modules(dict(paths,**{'lettuce.x':None}))
    # A real file outside the vendor tree, and a missing file inside it, are each rejected.
    vendor=ROOT/'vendor/lettuce/lettuce'
    for location in (__file__,str(vendor/'missing.py')):
        with pytest.raises(ValueError,match=exact('Loaded module is outside this checkout vendor source: lettuce.x')):
            study.validate_loaded_modules(dict(paths,**{'lettuce.x':location}))


def test_inspection_guard_includes_exact_storage_threshold(monkeypatch):
    flow=designed_cell(1.,-1e-3,1e-5)
    stages=study.inspect_collision(flow)
    assert not stages['near_zero'].item() and stages['applied_gamma'].item()==stages['raw_gamma'].item()
    # Choose the epsilon whose guard equals this cell's sum_h bit for bit.
    rho,denominator=flow.rho(),stages['denominator']
    epsilon=np.sqrt((denominator/rho).item())/9
    for _ in range(60):epsilon=np.nextafter(epsilon,0)
    for _ in range(120):
        if torch.equal((9*float(epsilon))**2*rho,denominator):break
        epsilon=np.nextafter(epsilon,1)
    else:pytest.fail('no epsilon reproduces the guard equality')
    monkeypatch.setattr(study,'EPSILON',float(epsilon))
    equal=study.inspect_collision(flow)
    assert torch.equal(equal['denominator'],denominator) and equal['near_zero'].item()
    assert equal['applied_gamma'].item()==2 and abs(equal['raw_gamma'].item()-2)>.9


def test_inspection_keeps_a_positive_stabilizer_just_above_the_reset_threshold():
    # FP64 cell found by search: its stabilizer is a few 2**-52 steps, inside [1e-15, 2e-15).
    flow=study.make_flow('cpu',1,torch.float64)
    cell=['0x1.c6cf77fead18cp-2','0x1.e2d079470d06fp-4','0x1.b93d6d662e342p-4',
          '0x1.ac3375dd3cd01p-4','0x1.d48bef1b164f9p-4','0x1.07fd91560ba14p-6',
          '0x1.364ecada43647p-5','0x1.d95e1f42470bep-7','0x1.5f448d699f8d4p-5']
    flow.f=torch.tensor([float.fromhex(x) for x in cell],dtype=torch.float64)[:,None,None].clone()
    stages=study.inspect_collision(flow)
    gamma=stages['raw_gamma'].item()
    assert 1e-15<=gamma<2e-15 and stages['applied_gamma'].item()==gamma
    assert not stages['near_zero'].item() and not stages['negative_reset'].item()


def test_study_fails_closed_when_a_later_size_raises(monkeypatch):
    original=study.make_flow
    def fail_second(device,size,dtype=torch.float32):
        if size==2:raise RuntimeError('device lost')
        return original(device,size,dtype)
    monkeypatch.setattr(study,'make_flow',fail_second)
    evidence={}
    with pytest.raises(RuntimeError,match=exact('device lost')):study.study('cpu',[1,2],evidence)
    assert evidence['passed'] is False and evidence['completed_sizes']==[1] and evidence['failed_size']==2


def test_study_rejects_a_collision_that_changes_its_input_populations(monkeypatch):
    original=lt.KBCCollision._collide_compensated
    def drift(self,flow,epsilon):
        out=original(self,flow,epsilon)
        flow.f[0,0,0]=torch.nextafter(flow.f[0,0,0],torch.tensor(2.,dtype=flow.f.dtype))
        return out
    monkeypatch.setattr(lt.KBCCollision,'_collide_compensated',drift)
    evidence={}
    with pytest.raises(AssertionError):study.study('cpu',[1],evidence)
    assert evidence['rows']==[] and evidence['failed_size']==1


@pytest.mark.parametrize('device',['mps','cuda:0'],ids=['apple-gpu','nvidia-gpu'])
def test_main_accepts_each_accelerator_device_name(tmp_path,monkeypatch,device):
    seen=[]
    monkeypatch.setattr(study,'study',lambda *args:seen.append(args[:2]) or dict(passed=True,rows=[]))
    output=tmp_path/'nested'/'run'
    assert study.main(['--device',device,'--sizes','1','--output',str(output)])==0
    assert seen==[(device,[1])] and json.loads((output/'result.json').read_text())['device']==device


@pytest.mark.parametrize('argv',[['--device','auto','--output','unused'],['--device','cpu']],
                         ids=['unknown-device','missing-output'])
def test_main_rejects_invalid_arguments(argv,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as stop:study.main(argv)
    assert stop.value.code==2 and not (tmp_path/'unused').exists()


def test_main_fails_closed_without_an_explicit_pass_and_writes_strict_json(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'study',lambda *args:dict(rows=[]))
    assert study.main(['--device','cpu','--output',str(tmp_path/'silent')])==1
    assert json.loads((tmp_path/'silent'/'result.json').read_text())['passed'] is False
    monkeypatch.setattr(study,'study',lambda *args:dict(passed=True,rows=[],value=float('nan')))
    with pytest.raises(ValueError,match='JSON compliant'):
        study.main(['--device','cpu','--output',str(tmp_path/'nan')])
    assert not (tmp_path/'nan'/'result.json').exists()
