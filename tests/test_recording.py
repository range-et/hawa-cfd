import json
import numpy as np
from hawa.plugin import Session
from hawa.recording import record,load_frame
from hawa.fields import get


def test_record_and_playback(tmp_path, solver_device):
    session=Session({'example':'tgv3d-bgk','size':8},solver_device)
    r=record(session,10,5,tmp_path/'run',lambda n:None)
    manifest=json.loads(open(r['manifest']).read());assert [x['iteration'] for x in manifest['frames']]==[0,5,10]
    frame=load_frame(r['manifest'],2);arrays,meta=get(frame['frame'])
    np.testing.assert_allclose(arrays['velocity'],session.flow.u_pu.cpu().numpy())
    assert meta['iteration']==10


def recording_fixture(tmp_path):
    case={'physical_dx':1.}
    frames=[]
    for i in range(3):
        name='frame-%d.npz'%i
        shape=(5,5,5)
        np.savez_compressed(tmp_path/name,velocity=np.zeros((3,)+shape),pressure=np.zeros(shape),
                            density=np.ones(shape),metadata=np.array(json.dumps({'case':case,'time':i})))
        frames.append({'file':name,'time':i})
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'case':case,'frames':frames}))
    return manifest


def test_recording_rejects_invalid_metadata_and_paths(tmp_path):
    import pytest
    manifest=recording_fixture(tmp_path)
    original=json.loads(manifest.read_text())
    for bad in (float('nan'),0,-1):
        data={**original,'case':{'physical_dx':bad}}
        manifest.write_text(json.dumps(data))
        with pytest.raises(ValueError,match='spacing'):load_frame(manifest,0)
    original['frames'][1]['file']='../outside.npz'
    manifest.write_text(json.dumps(original))
    with pytest.raises(ValueError,match='directory'):load_frame(manifest,0)


def test_load_frame_rejects_inconsistent_frames(tmp_path):
    import pytest
    manifest=recording_fixture(tmp_path)
    with np.load(tmp_path/'frame-1.npz') as archive:fields={k:archive[k] for k in archive.files}
    fields['velocity'][0,0,0,0]=float('nan')
    np.savez_compressed(tmp_path/'frame-1.npz',**fields)
    with pytest.raises(ValueError,match='finite'):load_frame(manifest,1)
    fields['velocity'][0,0,0,0]=0
    fields['metadata']=np.array(json.dumps({'case':{'physical_dx':2},'time':1}))
    np.savez_compressed(tmp_path/'frame-1.npz',**fields)
    with pytest.raises(ValueError,match='metadata'):load_frame(manifest,1)


def test_removed_particles_action_is_rejected(tmp_path):
    import pytest
    from hawa.plugin import dispatch
    # Particles and pathlines were removed by owner decision; the old query is an unknown action.
    with pytest.raises(ValueError,match='^Recording action must be load$'):
        dispatch(dict(op='recording',action='particles',manifest=str(recording_fixture(tmp_path)),seeds=[[1,2,3]]))


def test_recording_budget_counts_only_new_frames_after_warmup(tmp_path):
    import pytest
    session=Session({'example':'tgv3d-bgk','size':8},'cpu')
    session.advance(1001)
    result=record(session,1003,1,tmp_path/'after-warmup',lambda n:None)
    manifest=json.loads(open(result['manifest']).read())
    assert [r['iteration'] for r in manifest['frames']]==[1001,1002,1003]
    assert manifest['complete']
    with pytest.raises(ValueError,match='precedes'):record(session,1002,1,tmp_path/'past',lambda n:None)


def test_recorded_frames_keep_boundary_nodes(tmp_path):
    session=Session({'example':'poiseuille2d-guo','size':16},'cpu')
    r=record(session,2,2,tmp_path/'run',lambda n:None)
    arrays,_=get(load_frame(r['manifest'],1)['frame'])
    np.testing.assert_array_equal(arrays['boundary_nodes'],session.fields()['boundary_nodes'])
