import time
import numpy as np
from hawa.plugin import dispatch, Session, sample_arrays
from hawa.jobs import JOBS
from test_optimization import spec


def wait(job, state):
    end=time.monotonic()+15
    while time.monotonic()<end:
        v=dispatch(dict(op='evaluate_poll',job=job))
        if v['state'] in state:return v
        time.sleep(.01)
    raise AssertionError(v)


def test_job_controls_and_completed_identity(solver_device):
    req=dict(op='evaluate_submit',case=spec(),device=solver_device,steps=40,window=10,reference_volume=6)
    a=dispatch(req)['job']
    try:
        done=wait(a,{'completed','failed'})
        assert done['state']=='completed' and done['result']['fitness']>0
        assert done['job']==a
    finally:dispatch(dict(op='evaluate_control',job=a,action='close'))
    assert a not in JOBS


def test_queued_pause_and_cancel_are_nonblocking(solver_device):
    from hawa.jobs import DEVICE_SLOT
    DEVICE_SLOT.acquire()
    a=dispatch(dict(op='evaluate_submit',case=spec(),device=solver_device,steps=100,window=10,reference_volume=6))['job']
    try:
        dispatch(dict(op='evaluate_control',job=a,action='pause'))
        assert wait(a,{'paused'})['result'] is None
        dispatch(dict(op='evaluate_control',job=a,action='cancel'))
        assert wait(a,{'cancelled'})['result'] is None
    finally:
        DEVICE_SLOT.release()
        dispatch(dict(op='evaluate_control',job=a,action='close'))


def test_mean_independent_of_call_batch(solver_device):
    a=Session({'example':'tgv3d-bgk','size':8},solver_device)
    b=Session({'example':'tgv3d-bgk','size':8},solver_device)
    a.advance(10)
    for _ in range(10):b.advance(1)
    np.testing.assert_array_equal(a.mean_u.cpu().numpy(),b.mean_u.cpu().numpy())
    assert a.samples==b.samples==2


def test_wall_interpolation_does_not_mix_solid():
    f=dict(velocity=np.ones((3,4,4,4)),pressure=np.ones((4,4,4)),density=np.ones((4,4,4)),solid=np.zeros((4,4,4),bool))
    f['solid'][2,1,1]=True
    f['velocity'][:,2,1,1]=99
    # Nearest node fluid: valid, weighted over fluid corners only (#81).
    assert sample_arrays(f,[[1.49,1,1]])[0]['velocity']==[1,1,1]
    assert sample_arrays(f,[[1.51,1,1]])==[None]
    assert sample_arrays(f,[[1,1,1]])[0]['speed']>0


def test_quick_pause_resume_does_not_lose_run(solver_device):
    s=Session({'example':'tgv3d-bgk','size':8},solver_device)
    s.start(300)
    for _ in range(10):
        s.stop.set()
        s.start(300)
    end=time.monotonic()+10
    while s.thread is not None and time.monotonic()<end:time.sleep(.01)
    assert s.state=='completed' and s.flow.i==300


def test_background_creation_cleanup(solver_device):
    from hawa.plugin import SESSIONS
    job=dispatch(dict(op='evaluate_submit',kind='create',case={'example':'tgv3d-bgk','size':8},device=solver_device))['job']
    done=wait(job,{'completed','failed'})
    assert done['state']=='completed'
    session=done['result']['status']['session']
    assert session in SESSIONS
    dispatch(dict(op='evaluate_control',job=job,action='close'))
    assert session not in SESSIONS


def test_cancelled_candidate_never_publishes_or_leaks(solver_device):
    from hawa.jobs import DEVICE_SLOT
    from hawa.plugin import SESSIONS
    before=set(SESSIONS)
    DEVICE_SLOT.acquire()
    try:
        job=dispatch(dict(op='evaluate_submit',case=spec(),device=solver_device,steps=40,window=10,reference_volume=6))['job']
        worker=JOBS[job]
        dispatch(dict(op='evaluate_control',job=job,action='close'))
    finally:DEVICE_SLOT.release()
    worker.thread.join(timeout=5)
    assert not worker.thread.is_alive()
    assert worker.result is None and worker.session is None
    assert set(SESSIONS)==before


def test_query_failure_preserves_diagnostic():
    job=dispatch(dict(op='evaluate_submit',kind='query',request={'op':'field','action':'load','path':'/missing/hawa-field.npz'}))['job']
    try:
        value=wait(job,{'completed','failed'})
        assert value['state']=='failed' and value['error']
        assert value['result'] is None
    finally:dispatch(dict(op='evaluate_control',job=job,action='close'))


def test_closing_creation_job_stops_running_solver(solver_device):
    from hawa.plugin import SESSIONS
    job=dispatch(dict(op='evaluate_submit',kind='create',case={'example':'tgv3d-bgk','size':8},device=solver_device))['job']
    done=wait(job,{'completed','failed'})
    assert done['state']=='completed'
    session=SESSIONS[done['result']['status']['session']]
    session.start(100000)
    worker=session.thread
    dispatch(dict(op='evaluate_control',job=job,action='close'))
    worker.join(timeout=5)
    assert not worker.is_alive() and session.id not in SESSIONS
    assert session.flow.i<100000


def test_close_missing_job_is_idempotent():
    from hawa.jobs import dispatch_job
    assert dispatch_job({'op': 'evaluate_control', 'job': 'already-closed', 'action': 'close'}) == {'closed': True}
