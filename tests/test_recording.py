import json
import numpy as np
from hawa.plugin import Session
from hawa.recording import record,load_frame,pathlines
from hawa.fields import get


def test_record_and_playback(tmp_path):
    session=Session({'example':'tgv3d-bgk','size':8},'cpu')
    r=record(session,10,5,tmp_path/'run',lambda n:None)
    manifest=json.loads(open(r['manifest']).read());assert [x['iteration'] for x in manifest['frames']]==[0,5,10]
    frame=load_frame(r['manifest'],2);arrays,meta=get(frame['frame'])
    np.testing.assert_allclose(arrays['velocity'],session.flow.u_pu.numpy())
    assert meta['iteration']==10
    p=pathlines(r['manifest'],[[2,2,2]],2)
    assert len(p['paths'][0])>=2
