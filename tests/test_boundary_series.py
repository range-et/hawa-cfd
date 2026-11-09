import copy
import json
import numpy as np
import pytest
import torch
from hawa.plugin import Session,check_case
from hawa.boundary_data import capture,attach,digest
from hawa.boundary_series import SCHEMA,read,layout,geometry_key,BoundarySeries,solid_mask
from hawa.neutral import MODEL


def case(shape=(12,12,12),dx=1.,origin=None):
    names=('x-','x+','y-','y+','z-','z+')
    return dict(shape=list(shape),dx=dx,spacing=dx,origin=origin or [0,0,dx/2],speed=1.,viscosity=1.5e-5,density=1.225,mach=.05,collision=MODEL,solid=[],solid_halo=[],boundaries=['periodic']*4+['wall','slip'],
        neutral_precursor=dict(schema=1,experimental=True,mode='external',reference_height_m=shape[2]*dx/2,roughness_length_m=.01,perturbation_fraction=0.),boundary_method='shifted-links-v1',
        boundary_set=dict(schema=1,patches=[dict(id=f,face=f,condition=dict(type='wall' if i==4 else 'open',velocity=[0,0,0],pressure_pa=0.)) for i,f in enumerate(names)]))


def recording(directory,spec,times=(2.,3.,4.),vary=True):
    directory.mkdir();g=np.indices(spec['shape']).astype(float);n=spec['shape'];frames=[]
    for i,t in enumerate(times):
        velocity=np.stack((1.+.01*g[0]+.02*g[2]+(.03*(t-2) if vary else 0),.01*g[1],.005*g[2]))
        pressure=.01*g[0]+.02*g[2]+(.02*(t-2) if vary else 0)
        q=dict(policy='hawa-low-mach-v1',status='within-tested-envelope',transfer_eligible=True,finite=True,positive_density=True,physical_model_status='unvalidated-neutral-external')
        meta=dict(case=spec,time=t,iteration=i,quality=q);name='frame%d.npz'%i
        np.savez_compressed(directory/name,velocity=velocity,pressure=pressure,density=np.ones(n)*1.225,solid=solid_mask(spec),metadata=np.array(json.dumps(meta)))
        frames.append(dict(file=name,time=t,iteration=i))
    path=directory/'manifest.json';path.write_text(json.dumps(dict(case=spec,frames=frames,complete=True)));return path


def mapped(tmp_path,child=None):
    parent=case();child=child or case((6,6,8),.5,[2,2,.25]);manifest=recording(tmp_path/'parent',parent)
    return capture(manifest,child,tmp_path/'mapped.npz'),parent


def test_v2_time_pressure_ground_initialization_and_live_step(tmp_path):
    result,parent=mapped(tmp_path);spec=result['case'];a,m=read(spec['boundary_field']['path'])
    assert m['schema']==SCHEMA and m['faces']==['x-','x+','y-','y+','z+']
    assert spec['time_origin_seconds']==2.
    assert m['sampling']['ground_extended']>0
    # At child integer z index 2, parent coordinates are (2,2,.75).
    np.testing.assert_allclose(a['initial_velocity'][:,0,0,2],[1+.02+.02*.75,.02,.005*.75],atol=1e-7)
    ground_ratio=np.log1p(.25/.01)/np.log1p(.5/.01)
    assert a['initial_velocity'][0,0,0,0]==pytest.approx(1.02*ground_ratio,abs=1e-7)
    s=Session(spec,'cpu')
    np.testing.assert_allclose(s.fields()['velocity'],a['initial_velocity'],atol=5e-6)
    np.testing.assert_allclose(s.fields()['pressure'],a['initial_pressure'],atol=5e-5)
    bc=BoundarySeries(s.flow);v,p=bc.at(.5)
    np.testing.assert_allclose(v.numpy(),(a['velocity'][0]+a['velocity'][1])*.5,atol=1e-7)
    np.testing.assert_allclose(p.numpy(),(a['pressure'][0]+a['pressure'][1])*.5,atol=1e-7)
    s.advance(20)
    assert s.quality['finite'] and s.quality['transfer_eligible']
    assert s.quality['physical_model_status']=='unvalidated-neutral-external'
    with pytest.raises(ValueError,match='coverage'):bc.at(3.)
    with pytest.raises(ValueError,match='coverage'):s.start(1000)


def test_v2_rotated_world_velocity_and_millimetres(tmp_path):
    parent=case();parent['basis']=[[0,1,0],[-1,0,0],[0,0,1]]
    manifest=recording(tmp_path/'parent',parent)
    child=case((6,6,8),.5,[-8,2,.25]);result=capture(manifest,child,tmp_path/'rotated.npz');a,_=read(result['case']['boundary_field']['path'])
    # child (0,0,2) corresponds to parent local (2,8,.75); rotate vector to world.
    np.testing.assert_allclose(a['initial_velocity'][:,0,0,2],[-.08,1.035,.00375],atol=1e-7)
    child_mm=copy.deepcopy(child);child_mm['spacing']=500;child_mm['origin']=[-8000,2000,250]
    mm=capture(manifest,child_mm,tmp_path/'mm.npz');b,_=read(mm['case']['boundary_field']['path'])
    np.testing.assert_array_equal(a['velocity'],b['velocity'])


def test_v2_geometry_time_hash_and_quality_rejections(tmp_path):
    result,parent=mapped(tmp_path);spec=result['case'];path=spec['boundary_field']['path']
    changed=copy.deepcopy(spec);changed['solid']=[0]
    with pytest.raises(ValueError,match='geometry'):attach(path,changed)
    with open(path,'ab') as f:f.write(b'changed')
    with pytest.raises(ValueError,match='changed'):Session(spec,'cpu')
    manifest=tmp_path/'parent/manifest.json'
    with pytest.raises(ValueError,match='frames'):capture(manifest,case((6,6,8),.5,[2,2,.25]),tmp_path/'window.npz',start_time=4.)
    with pytest.raises(ValueError,match='coverage'):capture(manifest,case((6,6,8),.5,[100,2,.25]),tmp_path/'missing.npz')
    file=tmp_path/'parent/frame1.npz'
    with np.load(file) as z:data={k:z[k] for k in z.files}
    meta=json.loads(str(data['metadata']));meta['quality']['status']='rejected';data['metadata']=np.array(json.dumps(meta));np.savez_compressed(file,**data)
    with pytest.raises(ValueError,match='quality'):capture(manifest,case((6,6,8),.5,[2,2,.25]),tmp_path/'bad.npz')
    assert not (tmp_path/'bad.npz').exists()


def building(spec):
    n=np.array(spec['shape']);ix=np.indices(tuple(n+2)).reshape(3,-1).T-1;world=np.array(spec['origin'])+ix*spec['dx']
    mask=(world[:,0]>=4)&(world[:,0]<=6)&(world[:,1]>=5)&(world[:,1]<=7)&(world[:,2]<=3)
    halo=mask.reshape(tuple(n+2));spec['solid']=np.flatnonzero(halo[1:-1,1:-1,1:-1]).tolist();spec['solid_halo']=np.flatnonzero(halo).tolist()


def test_cropped_solid_masks_and_partial_stencils(tmp_path):
    parent=case();child=case((8,8,8),.5,[4.5,3,.25]);building(parent);building(child)
    result=capture(recording(tmp_path/'parent',parent),child,tmp_path/'crop.npz')
    a,m=read(result['case']['boundary_field']['path']);assert a['solid'].any() and m['sampling']['partial_fluid_stencil']>0
    assert not a['velocity'][:,:,a['solid']].any()
    s=Session(result['case'],'cpu');s.advance(20)
    assert s.solver.external_links.report['body_links']>0 and s.quality['finite']


@pytest.mark.parametrize('device',['cpu','mps','cuda:0'])
def test_mapped_neutral_backend_parity(tmp_path,device):
    if device=='mps' and not torch.backends.mps.is_available():pytest.skip('MPS unavailable')
    if device.startswith('cuda') and not torch.cuda.is_available():pytest.skip('CUDA hardware unavailable')
    result,_=mapped(tmp_path);spec=result['case'];ref=Session(spec,'cpu');test=Session(spec,device)
    ref.advance(40);test.advance(40)
    np.testing.assert_allclose(test.fields()['velocity'],ref.fields()['velocity'],atol=5e-5,rtol=5e-4)


def test_v2_cancellation_preserves_files(tmp_path):
    from hawa.jobs import Cancelled
    parent=case();manifest=recording(tmp_path/'parent',parent);out=tmp_path/'cancel.npz'
    def cancel(n):raise Cancelled()
    with pytest.raises(Cancelled):capture(manifest,case((6,6,8),.5,[2,2,.25]),out,cancel)
    assert not out.exists()


def test_three_stage_recording_preserves_absolute_clock_and_kinetic_stress(tmp_path):
    from hawa.recording import record
    result,_=mapped(tmp_path);child=Session(result['case'],'cpu')
    rec=record(child,40,10,tmp_path/'child-recording',lambda n:None)
    grand=case((4,4,4),.25,[3,3,.125]);dt=float(child.flow.units.convert_time_to_pu(1))
    nested=capture(rec['manifest'],grand,tmp_path/'grand.npz',start_time=10*dt)
    arrays,meta=read(nested['case']['boundary_field']['path'])
    assert meta['sampling']['stress_sources']==['kinetic']
    assert nested['case']['time_origin_seconds']==pytest.approx(2+10*dt)
    assert arrays['strain_rate'].shape[:3]==(4,3,3)
    s=Session(nested['case'],'cpu');s.advance(20)
    assert s.quality['finite'] and s.quality['transfer_eligible']
    assert s.quality['absolute_time_seconds']==pytest.approx(2+20*dt)


def test_v2_reader_bounds_grid_and_source_clock(tmp_path):
    result,_=mapped(tmp_path);path=result['case']['boundary_field']['path']
    with np.load(path) as z:original={k:z[k] for k in z.files}
    for field,value in (('grid',[2000000,2000000,2000000]),('clock',float('nan'))):
        data=dict(original);m=json.loads(str(data['metadata']))
        if field=='grid':m['grid']['shape']=value
        else:m['source']['absolute_start_seconds']=value
        data['metadata']=np.array(json.dumps(m));target=tmp_path/(field+'.npz');np.savez_compressed(target,**data)
        with pytest.raises(ValueError,match='grid|clock'):read(target)


def test_wall_filter_memory_transfers_only_at_matching_physical_height(tmp_path):
    from hawa.recording import record
    parent=case();parent['neutral_precursor']['wall_filter_seconds']=.3
    for patch in parent['boundary_set']['patches']:
        if patch['condition']['type']=='open':patch['condition']['backflow_mode']='pressure'
    parent['boundary_set']['patches'][0]['condition']=dict(type='velocity',velocity=[1.,0,0],profile='neutral')
    source=Session(parent,'cpu');source.advance(20)
    wall=source.flow.units.convert_velocity_to_pu(source.solver.rough_floor.filtered).cpu().numpy().copy()
    rec=record(source,24,1,tmp_path/'record',lambda n:None)
    child=case((6,6,8),1.,[2,2,.5]);child['neutral_precursor']['wall_filter_seconds']=.3
    result=capture(rec['manifest'],child,tmp_path/'wall.npz');a,m=read(result['case']['boundary_field']['path'])
    np.testing.assert_allclose(a['initial_wall_velocity'],wall[:,2:8,2:8],atol=1e-7)
    flow=Session(result['case'],'cpu')
    np.testing.assert_allclose(flow.flow.units.convert_velocity_to_pu(flow.solver.rough_floor.filtered).cpu(),wall[:,2:8,2:8],atol=1e-7)
    changed=copy.deepcopy(result['case']);changed['neutral_precursor']['wall_filter_seconds']=.1
    with pytest.raises(ValueError,match='Wall sampling/filter'):attach(tmp_path/'wall.npz',changed)
    refined=case((6,6,8),.5,[2,2,.25]);refined['neutral_precursor']['wall_filter_seconds']=.3
    r=capture(rec['manifest'],refined,tmp_path/'fine-wall.npz');arrays,meta=read(r['case']['boundary_field']['path'])
    assert 'initial_wall_velocity' not in arrays and 'spin-up required' in meta['sampling']['wall_history']


def test_v2_missing_required_array_is_actionable(tmp_path):
    result,_=mapped(tmp_path)
    with np.load(result['case']['boundary_field']['path']) as z:data={k:z[k] for k in z.files if k!='times'}
    path=tmp_path/'missing-array.npz';np.savez_compressed(path,**data)
    with pytest.raises(ValueError,match='missing required arrays'):read(path)
