"""Diagnostic evidence must preserve failures, device identity and original limits."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import torch
import lettuce as lt

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('kbc_parity',ROOT/'scripts/diagnose_kbc_parity.py')
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
    assert result['passed']==all(row['public_vs_reference']['passed'] for row in result['rows'])
    # The harness observes the current solver. It must not require the defect forever.
    # When the original population criterion fails, evidence keeps that failure visible.
    for row in result['rows']:
        comparison=row['public_vs_reference']
        assert comparison['passed']==(comparison['failed_values']==0)
        assert comparison['rtol']==1e-3 and comparison['atol']==1e-5
        if device=='mps':assert row['public_vs_raw']['max_abs']==0
    assert not result['reference']['negative_reset']['count']
