"""Import admission, progress and default-device contracts at the Job boundary."""
import zipfile

from hawa import jobs, native_data
from hawa.plugin import SESSIONS
from test_native_data import session, request, close_and_wait


def test_native_import_forwards_default_device_without_selecting_accelerator(session, tmp_path, monkeypatch):
    path = tmp_path/'native.npz'
    native_data.save(session, request(session, path))
    selected = []
    original = jobs.Session
    def construct(spec, device):
        selected.append(device)
        return original(spec, 'cpu')
    monkeypatch.setattr(jobs, 'Session', construct)
    job = jobs.Job(dict(kind='native_data_import', path=str(path)))
    try:
        job.work()
        assert job.state == 'completed', job.error
        assert selected == ['auto']
    finally:
        close_and_wait(job)


def test_native_import_cancel_during_archive_read_prevents_solver_allocation(session, tmp_path, monkeypatch):
    path = tmp_path/'native.npz'
    native_data.save(session, request(session, path))
    before = set(SESSIONS)
    job = jobs.Job(dict(kind='native_data_import', path=str(path), device='cpu'))
    original = zipfile.ZipFile
    allocated = []
    class CancelAtOpen(original):
        def __enter__(self):
            value = super().__enter__()
            job.control('cancel')
            return value
    def forbidden(*args):
        allocated.append(True)
        raise AssertionError('Cancelled archive read allocated a solver')
    monkeypatch.setattr(native_data.zipfile, 'ZipFile', CancelAtOpen)
    monkeypatch.setattr(jobs, 'Session', forbidden)
    job.work()
    assert job.state == 'cancelled' and job.result is None and job.session is None
    assert not allocated and set(SESSIONS) == before


def test_native_import_reports_restored_iteration_before_publication(session, tmp_path):
    path = tmp_path/'native.npz'
    native_data.save(session, request(session, path))
    observed = []
    class ObserveImport(jobs.Job):
        def checkpoint(self, steps, state='running'):
            super().checkpoint(steps, state)
            if self.session is not None and self.session.state == 'paused':
                observed.append(self.snapshot())
    job = ObserveImport(dict(kind='native_data_import', path=str(path), device='cpu'))
    try:
        job.work()
        assert job.state == 'completed', job.error
        assert len(observed) == 1
        assert observed[0]['steps'] == observed[0]['target'] == session.flow.i
        assert observed[0]['result'] is None and observed[0]['state'] == 'running'
    finally:
        close_and_wait(job)
