"""Public session admission, dispatch and failure contracts beyond happy paths."""
import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from hawa import plugin


@pytest.fixture
def session():
    value=plugin.Session(dict(example='tgv3d-bgk',size=8),'cpu')
    plugin.SESSIONS[value.id]=value
    yield value
    plugin.SESSIONS.pop(value.id,None)


def wind():
    return dict(shape=[8,8,8],dx=1.,speed=1.,viscosity=.1,boundaries=['inlet','outlet','periodic','periodic','wall','slip'])


@pytest.mark.parametrize('patch,match', [({'time_origin_seconds':-1},'time origin'),({'shape':[3,8,8]},'resolutions'),
    ({'mach':.16},'Mach'),({'collision':'unknown'},'collision'),({'collision':'shifted-regularized-sgs-v1'},'explicit experimental'),
    ({'boundaries':['wall']},'Six face'),({'boundaries':['wall']*6},'inlet at X-'),
    ({'solid':[-1]},'outside'),({'solid':[0]},'intersect'),({'initial_velocity':[1,2]},'Initial velocity'),
    ({'boundary_method':'missing'},'boundary set'),({'boundary_field':{},'memory_limit_mb':-1},'case budget')])
def test_rejected_case_contracts(patch,match):
    with pytest.raises(ValueError,match=match):plugin.check_case(dict(wind(),**patch))


@pytest.mark.parametrize('variant,match', [('refinement','stationary uniform'),('transverse','periodic transverse'),
    ('curved','overlaps'),('grid','Import boundary'),('time','positive finite')])
def test_mapped_boundary_admission_rejects_incompatible_inputs(variant,match):
    from hawa.boundary_data import grid_key
    spec=wind();spec['boundaries']=['inlet','outlet']+['periodic']*4
    ref=dict(grid=grid_key(spec),sha256='a'*64,end_time=2.)
    spec['boundary_field']=ref
    if variant=='refinement':spec['refinement_lower']=[2,2,2]
    elif variant=='transverse':spec['boundaries'][4:]=['wall','slip']
    elif variant=='curved':spec['wall_links']=[[1,0,.5]]
    elif variant=='grid':ref['grid']='wrong'
    else:ref['end_time']=0
    with pytest.raises(ValueError,match=match):plugin.check_case(spec)


def test_start_lifecycle_failure_and_pause_timeout(session,monkeypatch):
    with pytest.raises(ValueError,match='Target steps'):session.start(-1)
    session.state='resetting'
    with pytest.raises(ValueError,match='reset'):session.start(1)
    session.state='ready';pending=[]
    class Thread:
        def __init__(self,target,**kwargs):self.target=target
        def start(self):pending.append(self.target)
        def is_alive(self):return True
        def join(self,timeout):assert timeout==30
    monkeypatch.setattr(plugin.threading,'Thread',Thread)
    session.start(5);session.start(6)
    assert len(pending)==1 and session.target==6
    with pytest.raises(RuntimeError,match='cancellation boundary'):session.pause()
    session.stop.clear()
    def fail(steps):raise RuntimeError('solver failure')
    monkeypatch.setattr(session,'advance',fail)
    pending.pop()()
    assert session.state=='failed' and session.error=='solver failure' and session.thread is None


def test_advance_unstable_output_fails_and_time_coverage_is_checked(session,monkeypatch):
    session.spec['boundary_field']=dict(end_time=0.)
    with pytest.raises(ValueError,match='time coverage'):session.advance(1)
    session.spec.pop('boundary_field')
    def unstable(steps):session.flow.f.fill_(float('nan'));session.flow.i+=steps
    session.solver=unstable
    with pytest.raises(RuntimeError,match='unstable'):session.advance(1)


def test_dispatch_information_and_scalar_routes(monkeypatch):
    from hawa import flow_statistics,roughness,boundary_data,recording,fields
    assert plugin.dispatch(dict(op='info'))['python']==sys.version
    assert plugin.dispatch(dict(op='check',case=wind()))['valid']
    observed=[]
    def target(*args,**kwargs):observed.append((args,kwargs));return {'result':'sentinel'}
    routes=[(flow_statistics,'analyze',dict(op='statistics',manifest='m',points=[[1,2,3]],start_time=2.,end_time=3.),('m',[[1,2,3]],2.,3.),{}),
        (roughness,'apply',dict(op='wall_roughness',case={'c':1},regions=[1]),({'c':1},[1]),{}),
        (boundary_data,'capture',dict(op='boundary',action='capture',manifest='m',case={},path='p',start_time=2,end_time=3),('m',{},'p'),dict(start_time=2,end_time=3)),
        (boundary_data,'attach',dict(op='boundary',action='attach',path='p',case={}),('p',{}),{}),
        (recording,'load_frame',dict(op='recording',action='load',manifest='m',index=2),('m',2),{}),
        (recording,'pathlines',dict(op='recording',action='particles',manifest='m',seeds=[[1,2,3]],last=4),('m',[[1,2,3]],4),{})]
    for module,name,request,args,kwargs in routes:
        monkeypatch.setattr(module,name,target)
        assert plugin.dispatch(request)=={'result':'sentinel'}
        assert observed.pop()==(args,kwargs)
    for op in ('recording','boundary'):
        with pytest.raises(ValueError):plugin.dispatch(dict(op=op,action='unknown'))
    monkeypatch.setattr(fields,'dispatch_field',target)
    request=dict(op='field',action='sample')
    assert plugin.dispatch(request)=={'result':'sentinel'} and observed.pop()==((request,None),{})


def test_dispatch_slice_and_load_errors(session,tmp_path):
    key=session.id
    for options,match in [(dict(axis=4),'axis'),(dict(index=-1),'index'),(dict(field='unknown'),'field')]:
        with pytest.raises(ValueError,match=match):plugin.dispatch(dict(op='slice',session=key,**options))
    with pytest.raises(ValueError,match='10000'):plugin.dispatch(dict(op='sample',session=key,points=[[0,0,0]]*10001))
    with pytest.raises(ValueError,match='no moving'):plugin.dispatch(dict(op='body_loads',session=key))
    with pytest.raises(ValueError,match='Unknown'):plugin.dispatch(dict(op='unknown',session=key))
    path=tmp_path/'state.npz';plugin.dispatch(dict(op='save',session=key,path=str(path)))
    with np.load(path,allow_pickle=False) as data:original={k:data[k].copy() for k in data.files}
    variants=[dict(spec=np.array('{}')),dict(populations=np.full_like(original['populations'],np.nan)),dict(quality=np.array('{}'))]
    for changed,match in zip(variants,['different case','nonfinite','quality history']):
        np.savez(path,**dict(original,**changed))
        with pytest.raises(ValueError,match=match):plugin.dispatch(dict(op='load',session=key,path=str(path)))
        np.testing.assert_array_equal(session.flow.f.cpu().numpy(),original['populations'])


def test_two_dimensional_slice_and_moving_load_metadata(session):
    other=plugin.Session(dict(example='tgv2d-bgk',size=8),'cpu');plugin.SESSIONS[other.id]=other
    try:
        result=plugin.dispatch(dict(op='slice',session=other.id))
        assert result['shape']==[8,8] and len(result['values'])==64
        assert all(p[2]==0 for p in result['coordinates'])
    finally:plugin.SESSIONS.pop(other.id,None)
    session.solver=SimpleNamespace(moving=SimpleNamespace(metadata=lambda:dict(identity='body'),history=[dict(force=2)]))
    report=plugin.dispatch(dict(op='body_loads',session=session.id))
    assert report['identity']=='body' and report['history']==[dict(force=2)] and report['case']==session.spec


def test_streamlines_terminate_at_missing_or_stationary_samples(session,monkeypatch):
    value=dict(velocity=[1.,0,0],speed=1.)
    for responses in ([None],[value,None],[value,value,None]):
        queue=iter(responses)
        monkeypatch.setattr(plugin,'sample_arrays',lambda *args:[next(queue)])
        assert plugin.dispatch(dict(op='streamlines',session=session.id,seeds=[[1,1,1]],steps=1))['paths']==[[[1.,1.,1.]]]


def test_filtered_wall_checkpoint_rejects_invalid_or_missing_history(tmp_path):
    from test_neutral import case
    spec=case();spec['neutral_precursor']['wall_filter_seconds']=1.
    value=plugin.Session(spec,'cpu');plugin.SESSIONS[value.id]=value
    try:
        path=tmp_path/'wall.npz';plugin.dispatch(dict(op='save',session=value.id,path=str(path)))
        with np.load(path,allow_pickle=False) as data:original={k:data[k].copy() for k in data.files}
        for history,iteration,match in [(np.ones(2),0,'Invalid wall'),(np.empty(0),1,'requires wall')]:
            np.savez(path,**dict(original,wall_reference=history,iteration=np.array(iteration)))
            with pytest.raises(ValueError,match=match):plugin.dispatch(dict(op='load',session=value.id,path=str(path)))
    finally:plugin.SESSIONS.pop(value.id,None)
