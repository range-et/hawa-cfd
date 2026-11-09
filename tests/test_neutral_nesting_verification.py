"""Frozen-reference harness integrity and preserved numerical acceptance criteria."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('nesting_study',ROOT/'scripts/verify_neutral_nesting.py')
study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)


def signals():
    t=np.arange(16,dtype=float)
    u=np.zeros((16,2,3));u[:,:,0]=5+np.tile([-.1,.1],8)[:,None]
    p=np.zeros((16,2))
    return t,u,p


@pytest.mark.parametrize('fault',['none','mean','rms','pressure','reference_drift','health'])
def test_metrics_preserve_seeded_failures(fault):
    t,u,p=signals();v=u.copy();q=p.copy();health='within-tested-envelope'
    if fault=='mean':v[:,:,0]+=1
    elif fault=='rms':v[:,:,0]=5+2*(u[:,:,0]-5)
    elif fault=='pressure':q+=2
    elif fault=='reference_drift':u[12:,:,0]+=2;v=u.copy()
    elif fault=='health':health='rejected'
    result=study.metrics(t,u,p,v,q,health)
    assert result['passed']==(fault=='none')
    assert result['analysis_start']==8 and result['analysis_end']==15 and result['samples']==8
    assert 'child_stationarity_change' in result and 'reference_rms_m_s' in result
    assert study.THRESHOLDS==dict(mean_relative_l2=.05,rms_relative_l2=.1,cp_rmse=.1,reference_stationarity=.05)


def test_explicit_window_and_invalid_sampling():
    t,u,p=signals()
    result=study.metrics(t,u,p,u,p,'within-tested-envelope',2,9)
    assert result['analysis_start']==2 and result['analysis_end']==9 and result['samples']==8
    for start,end in [(-1,10),(5,4),(0,30),(2,3),(float('nan'),10)]:
        with pytest.raises(ValueError,match='window'):study.window_indices(t,start,end)
    with pytest.raises(ValueError,match='uniformly'):study.window_indices([0,1,2,4],0,4)
    with pytest.raises(ValueError,match='increasing'):study.window_indices([0,1,1,2])
    with pytest.raises(ValueError,match='matching'):study.metrics(t,u,p,u[:2],p,'within-tested-envelope')
    with pytest.raises(ValueError,match='too small'):study.metrics(t,u*0,p,u*0,p,'within-tested-envelope')
    with pytest.raises(SystemExit):study.main(['--output','unused','--window-start','nan'])


def descriptor(tmp_path,monkeypatch):
    from test_boundary_series import recording
    # Keep real frame validation and world sampling, but use cheap manufactured frames.
    monkeypatch.setattr(study,'POINTS',np.array([[2.,2.,2.],[3.,3.,2.]]))
    folder=tmp_path/'frozen';folder.mkdir()
    parent=study.reference_case(1)
    dt=parent['dx']*parent['mach']/(np.sqrt(3)*parent['speed'])
    manifest=recording(folder/'parent',parent,times=tuple(np.arange(8)*dt),vary=False)
    bundle=dict(schema=1,config=dict(warmup=0,steps=7,interval=1,ratios=[1],fine_reference=False),
                device='cpu',sources=study.sources(),points=study.POINTS.tolist(),recordings={
                    'parent':dict(manifest='parent/manifest.json',backend=dict(requested='cpu',selected='cpu',torch='test-double'),**study.recording_identity(manifest))})
    path=folder/'reference.json';path.write_text(json.dumps(bundle))
    return path,manifest,bundle


@pytest.mark.parametrize('fault',['none','frame_changed','missing','corrupt','incomplete','stale','path_escape','missing_role','wrong_points','clock','metadata','geometry'])
def test_frozen_reference_requires_complete_current_immutable_input(tmp_path,monkeypatch,fault):
    path,manifest,bundle=descriptor(tmp_path,monkeypatch)
    frame=manifest.parent/'frame0.npz'
    if fault=='frame_changed':frame.write_bytes(frame.read_bytes()+b'changed')
    elif fault=='missing':frame.unlink()
    elif fault=='corrupt':frame.write_bytes(b'not a zip')
    elif fault=='incomplete':
        data=json.loads(manifest.read_text());data['complete']=False;manifest.write_text(json.dumps(data))
    elif fault=='stale':bundle['sources']={}
    elif fault=='path_escape':bundle['recordings']['parent']['manifest']='../../elsewhere/manifest.json'
    elif fault=='missing_role':bundle['recordings']={}
    elif fault=='wrong_points':bundle['points']=[[0,0,0]]
    elif fault=='geometry':
        data=json.loads(manifest.read_text());data['case']['origin'][0]+=1;manifest.write_text(json.dumps(data))
        bundle['recordings']['parent'].update(study.recording_identity(manifest))
    elif fault in ('clock','metadata'):
        with np.load(frame) as data:arrays={k:data[k] for k in data.files}
        meta=json.loads(str(arrays['metadata']));meta['time']+=1 if fault=='clock' else 0
        if fault=='metadata':meta['case']['speed']=4
        arrays['metadata']=np.array(json.dumps(meta));np.savez_compressed(frame,**arrays)
        # Even a descriptor deliberately refreshed after corruption cannot waive semantic checks.
        bundle['recordings']['parent'].update(study.recording_identity(manifest))
    path.write_text(json.dumps(bundle))
    if fault=='none':
        loaded,paths=study.load_reference(path)
        assert paths['parent']==manifest and loaded['device']=='cpu'
        assert study.main(['--output',str(tmp_path/'analysis'),'--reuse-reference',str(path),'--reference-only','--window-start','0'])==0
        result=json.loads((tmp_path/'analysis/result.json').read_text())
        assert result['passed'] and not result['full_nesting_passed']
    else:
        with pytest.raises((ValueError,OSError)):study.load_reference(path)
        assert study.main(['--output',str(tmp_path/'failed'),'--reuse-reference',str(path)])==1
        assert not json.loads((tmp_path/'failed/result.json').read_text())['passed']


def test_reuse_rejects_argument_mismatch_and_recording_changed_during_analysis(tmp_path,monkeypatch):
    path,manifest,bundle=descriptor(tmp_path,monkeypatch)
    for option,value in [('--steps','8'),('--ratios','2')]:
        output=tmp_path/option[2:]
        assert study.main(['--output',str(output),'--reuse-reference',str(path),option,value])==1
        assert 'differs' in (output/'result.json').read_text() or 'absent' in (output/'result.json').read_text()
    original=study.sample_parent
    def mutate(*args,**kwargs):
        result=original(*args,**kwargs)
        manifest.write_text(manifest.read_text()+' ')
        return result
    monkeypatch.setattr(study,'sample_parent',mutate)
    with pytest.raises(ValueError,match='changed during analysis'):study.series(manifest,study.POINTS)


@pytest.mark.parametrize('key,value',[('steps',0),('ratios',[]),('ratios',[1,1]),('ratios',[3]),('interval',2),('steps',1)])
def test_reference_configuration_is_bounded(key,value):
    config=dict(warmup=0,steps=7,interval=1,ratios=[1],fine_reference=False);config[key]=value
    with pytest.raises(ValueError):study.validate_config(config)


def test_real_cpu_reference_smoke_and_replay(tmp_path):
    output=tmp_path/'reference-run'
    code=study.main(['--output',str(output),'--device','cpu','--warmup','0','--steps','8',
                     '--interval','1','--ratios','1','--reference-only'])
    report=json.loads((output/'result.json').read_text())
    assert 'error' not in report and code==int(not report['passed'])
    assert not report['full_nesting_passed']
    frozen,paths=study.load_reference(output/'reference.json')
    t,u,p,q=study.series(paths['parent'],study.POINTS)
    assert len(t)==9 and u.shape==(9,7,3) and np.isfinite(p).all()
    replay=tmp_path/'replay'
    assert study.main(['--output',str(replay),'--reuse-reference',str(output/'reference.json'),
                       '--reference-only'])==code
    replay_report=json.loads((replay/'result.json').read_text())
    assert replay_report['reference_checks']==report['reference_checks']
    with pytest.raises(FileExistsError):study.main(['--output',str(output),'--reference-only'])


def test_child_stationarity_diagnostic_does_not_change_original_gate():
    t,u,p=signals();u[:,:,0]=5+np.tile([-1.,1.],8)[:,None];v=u.copy()
    v[8:12,:,0]=4;v[12:,:,0]=6
    result=study.metrics(t,u,p,v,p,'within-tested-envelope')
    assert result['passed'] and result['child_stationarity_change']>.05
    assert result['reference_stationarity_change']==0


def test_descriptor_iteration_inventory_cannot_silently_change(tmp_path,monkeypatch):
    path,manifest,bundle=descriptor(tmp_path,monkeypatch)
    bundle['config']['steps']=8
    path.write_text(json.dumps(bundle))
    with pytest.raises(ValueError,match='iteration inventory'):study.load_reference(path)


def test_full_child_orchestration_and_failed_reference_requires_diagnostic_opt_in(tmp_path,monkeypatch):
    path,manifest,bundle=descriptor(tmp_path,monkeypatch)
    monkeypatch.setattr(study,'capture',lambda *args,**kwargs: {'case': {}})
    monkeypatch.setattr(study,'create_recording',lambda *args,**kwargs: dict(manifest=str(manifest),backend=dict(requested='cpu',selected='cpu',torch='test-double')))
    assert study.main(['--output',str(tmp_path/'complete'),'--reuse-reference',str(path)])==0
    result=json.loads((tmp_path/'complete/result.json').read_text())
    assert result['full_nesting_passed'] and len(result['rows'])==1
    assert (tmp_path/'complete/comparison-1.npz').exists()
    original=study.metrics
    def failed_reference(*args,**kwargs):
        result=original(*args,**kwargs)
        result['reference_stationarity_change']=.2
        result['passed']=False
        return result
    monkeypatch.setattr(study,'metrics',failed_reference)
    assert study.main(['--output',str(tmp_path/'blocked'),'--reuse-reference',str(path)])==1
    result=json.loads((tmp_path/'blocked/result.json').read_text())
    assert not result['rows'] and 'Reference stationarity' in result['error']
    assert study.main(['--output',str(tmp_path/'diagnostic'),'--reuse-reference',str(path),
                       '--diagnostic-nonstationary-reference'])==1
    result=json.loads((tmp_path/'diagnostic/result.json').read_text())
    assert len(result['rows'])==1 and not result['full_nesting_passed']


def test_subset_replay_is_explicitly_not_a_full_scope_pass(tmp_path,monkeypatch):
    path,manifest,bundle=descriptor(tmp_path,monkeypatch)
    # Coarse-reference bundle can declare both ratios without a fine-reference recording.
    bundle['config']['ratios']=[1,2]
    path.write_text(json.dumps(bundle))
    monkeypatch.setattr(study,'capture',lambda *args,**kwargs: {'case': {}})
    monkeypatch.setattr(study,'create_recording',lambda *args,**kwargs: dict(manifest=str(manifest),backend=dict(requested='cpu',selected='cpu',torch='test-double')))
    assert study.main(['--output',str(tmp_path/'subset'),'--reuse-reference',str(path),'--ratios','1'])==0
    result=json.loads((tmp_path/'subset/result.json').read_text())
    assert result['passed'] and not result['full_nesting_passed'] and not result['full_scope']
    assert result['requested_ratios']==result['evaluated_ratios']==[1]
    assert result['available_ratios']==[1,2]


def test_rehashed_consistent_but_wrong_clock_is_rejected(tmp_path,monkeypatch):
    path,manifest,bundle=descriptor(tmp_path,monkeypatch)
    data=json.loads(manifest.read_text())
    for entry in data['frames']:
        file=manifest.parent/entry['file']
        with np.load(file) as record:arrays={k:record[k] for k in record.files}
        meta=json.loads(str(arrays['metadata']));meta['time']+=1
        entry['time']+=1
        arrays['metadata']=np.array(json.dumps(meta));np.savez_compressed(file,**arrays)
    manifest.write_text(json.dumps(data))
    bundle['recordings']['parent'].update(study.recording_identity(manifest))
    path.write_text(json.dumps(bundle))
    with pytest.raises(ValueError,match='absolute clock differs'):study.load_reference(path)


@pytest.mark.parametrize('value',[[],None,'reference',3,False])
def test_nonobject_descriptor_saves_failed_report(tmp_path,value):
    path=tmp_path/'reference.json';path.write_text(json.dumps(value))
    output=tmp_path/'result'
    assert study.main(['--output',str(output),'--reuse-reference',str(path)])==1
    result=json.loads((output/'result.json').read_text())
    assert not result['passed'] and not result['full_nesting_passed']
    assert 'descriptor must be an object' in result['error']


@pytest.mark.parametrize('part,value',[('config',[]),('config',None),('config',3),
                                        ('recordings',[]),('recording',[]),('backend',None),
                                        ('backend',{'requested':'auto','selected':'auto','torch':'test'})])
def test_malformed_nested_descriptor_saves_failed_report(tmp_path,monkeypatch,part,value):
    path,manifest,bundle=descriptor(tmp_path,monkeypatch)
    if part=='recording':bundle['recordings']['parent']=value
    elif part=='backend':bundle['recordings']['parent']['backend']=value
    else:bundle[part]=value
    path.write_text(json.dumps(bundle))
    output=tmp_path/'result'
    assert study.main(['--output',str(output),'--reuse-reference',str(path)])==1
    result=json.loads((output/'result.json').read_text())
    assert not result['passed'] and not result['full_nesting_passed'] and 'error' in result


def test_real_fine_reference_replay_with_nonzero_warmup_and_auto_cpu(tmp_path,monkeypatch):
    import torch
    # Exercise real auto selection while avoiding GPU work in the focused CPU lane.
    monkeypatch.setattr(torch.cuda,'is_available',lambda:False)
    monkeypatch.setattr(torch.backends.mps,'is_available',lambda:False)
    output=tmp_path/'fine-source'
    code=study.main(['--output',str(output),'--device','auto','--warmup','200','--steps','8',
                    '--interval','1','--ratios','2','--fine-reference','--reference-only'])
    source=json.loads((output/'result.json').read_text())
    assert 'error' not in source and code==int(not source['passed'])
    bundle,paths=study.load_reference(output/'reference.json')
    assert set(paths)=={'parent','reference-2'}
    parent_times,*_=study.series(paths['parent'],study.POINTS)
    fine_times,*_=study.series(paths['reference-2'],study.POINTS)
    np.testing.assert_allclose(parent_times,fine_times,rtol=0,atol=1e-10)
    for name,warmup,step in [('parent',200,1),('reference-2',400,2)]:
        manifest=json.loads(paths[name].read_text())
        assert [e['iteration'] for e in manifest['frames']]==list(range(warmup,warmup+8*step+1,step))
        backend=bundle['recordings'][name]['backend']
        assert backend['requested']=='auto' and backend['selected']=='cpu'
        assert backend['torch']==torch.__version__ and backend['notes']
    replay=tmp_path/'fine-replay'
    code=study.main(['--output',str(replay),'--device','auto','--reuse-reference',str(output/'reference.json'),
                    '--diagnostic-nonstationary-reference'])
    result=json.loads((replay/'result.json').read_text())
    assert 'error' not in result and code==int(not result['passed'])
    assert result['evaluated_ratios']==[2] and result['full_scope']
    row=result['rows'][0]
    assert row['reference']=='reference-2' and row['backend']['selected']=='cpu'
    assert row['backend']['requested']=='auto'
    assert result['reference']['recordings']['reference-2']['backend']==bundle['recordings']['reference-2']['backend']
    with np.load(replay/'comparison-2.npz') as data:
        np.testing.assert_allclose(data['times'],fine_times,rtol=0,atol=1e-10)
        assert data['reference_velocity'].shape==data['child_velocity'].shape==(9,7,3)
