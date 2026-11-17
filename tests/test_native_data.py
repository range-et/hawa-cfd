"""Native data integrity, paused fresh-session import and transactional publication."""
import copy
import io
import json
import zipfile

import numpy as np
import pytest

from hawa import native_data as data
from hawa.jobs import Cancelled, Job
from hawa.plugin import Session, SESSIONS, dispatch


@pytest.fixture
def session():
    s = Session(dict(shape=[8, 6, 5], dx=.5, spacing=500., origin=[1000., 2000., 3000.],
                     origin_m=[1., 2., 3.], speed=1., viscosity=.05, density=1.2,
                     mach=.05, collision='bgk', solid=[(3*6+3)*5+2],
                     time_origin_seconds=10.), 'cpu')
    s.advance(3)
    s.state = 'paused'
    SESSIONS[s.id] = s
    try: yield s
    finally: dispatch({'op': 'close', 'session': s.id})


def request(s, path, **extra):
    return dict(op='data', action='save', session=s.id, path=str(path),
                expected=dict(case_hash=s.key, iteration=s.flow.i, state=s.state),
                native_settings={'field': 'speed', 'foreign_context': {'a': [1]}},
                attribution=dict(case_id='caller', revision=1, generation=2, version=3), **extra)


def archive(path, populations, metadata):
    with path.open('wb') as stream:
        np.savez_compressed(stream, populations=populations, metadata=np.array(json.dumps(metadata)))


def test_exact_roundtrip_paused_import_continuation_and_job_ownership(session, tmp_path):
    path = tmp_path / 'nested' / 'native.npz'
    result = dispatch(request(session, path))
    populations, meta, means = data.read_archive(path)
    assert result == dict(path=str(path), format='npz', schema='hawa-native-data-1', metadata=meta)
    np.testing.assert_array_equal(populations, session.flow.f.numpy())
    assert meta['case_hash'] == session.key and meta['case'] == session.spec
    assert meta['iteration'] == 3 and meta['source_state'] == 'paused' and meta['source_session'] == session.id
    assert meta['local_time'] == session.status()['physical_time']
    assert meta['absolute_time'] == 10 + meta['local_time'] and meta['time_origin'] == 10
    caller = dict(case_id='new', revision=0, generation=1, version=2)
    job = Job(dict(kind='native_data_import', path=str(path), device='cpu', context=caller))
    job.work()
    try:
        assert job.state == 'completed', job.error
        restored = job.session
        assert restored.id != session.id and restored.state == 'paused' and restored.thread is None
        assert job.result == dict(case=meta['case'], metadata=meta, context=caller, status=restored.status())
        assert job.steps == 3 and job.target == 3 and restored.id in SESSIONS
        np.testing.assert_array_equal(restored.flow.f.numpy(), session.flow.f.numpy())
        for name, value in session.fields().items(): np.testing.assert_array_equal(restored.fields()[name], value)
        session.advance(2); restored.advance(2)
        np.testing.assert_array_equal(restored.flow.f.numpy(), session.flow.f.numpy())
        restored_id = restored.id
    finally: job.control('close')
    assert restored_id not in SESSIONS and session.id in SESSIONS and job.session is None


def test_save_query_cancellation_and_reservation_release(session, tmp_path, monkeypatch):
    path = tmp_path / 'native.npz'; path.write_bytes(b'old')
    req = request(session, path)
    class CancelSave(Job):
        def checkpoint(self, n, state='running'):
            if n == 1: raise Cancelled('before publish')
            super().checkpoint(n, state)
    job = CancelSave(dict(kind='query', request=req)); job.work()
    assert job.state == 'cancelled' and path.read_bytes() == b'old'
    assert list(tmp_path.iterdir()) == [path] and not data.DESTINATIONS
    for failure in ('write', 'replace'):
        with monkeypatch.context() as patch:
            def fail(*args, **kwargs): raise OSError(failure)
            patch.setattr(data.np if failure == 'write' else data.os, 'savez_compressed' if failure == 'write' else 'replace', fail)
            with pytest.raises(OSError): data.save(session, req)
        assert path.read_bytes() == b'old' and not data.DESTINATIONS
    def checkpoint(n):
        if n == 0:
            with pytest.raises(ValueError, match='already being exported'): data.save(session, req)
    data.save(session, req, checkpoint)
    assert data.read_archive(path)[1]['case_hash'] == session.key


@pytest.mark.parametrize('stage', ['before', 'allocated', 'restored'])
def test_import_cancel_never_publishes_or_changes_old_session(session, tmp_path, stage):
    path = tmp_path / 'native.npz'; data.save(session, request(session, path))
    before = session.flow.f.numpy().copy(); keys = set(SESSIONS)
    class CancelImport(Job):
        def checkpoint(self, n, state='running'):
            if stage == 'before' or (stage == 'allocated' and self.session is not None) or (stage == 'restored' and self.session is not None and self.session.state == 'paused'):
                raise Cancelled('cancel import')
            super().checkpoint(n, state)
    job = CancelImport(dict(kind='native_data_import', path=str(path), device='cpu')); job.work()
    assert job.state == 'cancelled' and job.session is None and job.result is None and set(SESSIONS) == keys
    np.testing.assert_array_equal(session.flow.f.numpy(), before)


@pytest.mark.parametrize('failure', ['schema', 'storage', 'hash', 'iteration', 'state', 'time', 'absolute', 'quality', 'settings', 'attribution', 'dtype', 'shape', 'nan', 'density'])
def test_corrupt_artifact_rejected_before_session_creation(session, tmp_path, monkeypatch, failure):
    path = tmp_path / 'native.npz'; data.save(session, request(session, path))
    populations, meta, means = data.read_archive(path)
    if failure == 'schema': meta['schema'] = 'unknown'
    elif failure == 'storage': meta['population_storage'] = 'g=f-w'
    elif failure == 'hash': meta['case_hash'] = 'bad'
    elif failure == 'iteration': meta['iteration'] = True
    elif failure == 'state': meta['source_state'] = 'running'
    elif failure == 'time': meta['local_time'] = -1
    elif failure == 'absolute': meta['absolute_time'] += 1
    elif failure == 'quality': meta['quality']['status'] = 'unknown'
    elif failure == 'settings': meta['native_settings'] = []
    elif failure == 'attribution': meta['attribution']['revision'] = True
    elif failure == 'dtype': populations = populations.astype('float64')
    elif failure == 'shape': populations = populations[:, :-1]
    elif failure == 'nan': populations[0, 0, 0, 0] = np.nan
    elif failure == 'density': populations[:, 0, 0, 0] = 0
    archive(path, populations, meta)
    def forbidden(*args): pytest.fail('Invalid archive allocated a solver')
    monkeypatch.setattr('hawa.jobs.Session', forbidden)
    job = Job(dict(kind='native_data_import', path=str(path), device='cpu')); job.work()
    assert job.state == 'failed' and job.error and job.session is None and job.result is None


@pytest.mark.parametrize('failure', ['extra', 'truncated', 'duplicate', 'object', 'declared_size', 'version', 'metadata_type', 'metadata_budget', 'total_budget'])
def test_bounded_archive_headers(session, tmp_path, monkeypatch, failure):
    path = tmp_path / 'native.npz'; data.save(session, request(session, path))
    if failure == 'truncated': path.write_bytes(path.read_bytes()[:50])
    elif failure == 'metadata_budget': monkeypatch.setattr(data, 'MAX_METADATA', 1)
    elif failure == 'total_budget': monkeypatch.setattr(data, 'MAX_BYTES', 1)
    else:
        with zipfile.ZipFile(path) as z: members = {n: z.read(n) for n in z.namelist()}
        if failure == 'extra': members['extra.npy'] = b'x'
        elif failure == 'declared_size':
            stream = io.BytesIO(); np.lib.format.write_array_header_1_0(stream, dict(descr='<f4', fortran_order=False, shape=(19, 999999999, 4, 4)))
            members['populations.npy'] = stream.getvalue()
        elif failure == 'version': members['populations.npy'] = b'\x93NUMPY\x03\x00' + members['populations.npy'][8:]
        elif failure in ('object', 'metadata_type'):
            stream = io.BytesIO(); np.save(stream, np.array([{}], object) if failure == 'object' else np.array(1))
            members['metadata.npy'] = stream.getvalue()
        with zipfile.ZipFile(path, 'w') as z:
            for name, value in members.items(): z.writestr(name, value)
            if failure == 'duplicate': z.writestr('metadata.npy', members['metadata.npy'])
    with pytest.raises((ValueError, zipfile.BadZipFile)): data.read_archive(path)


def test_save_guard_detaches_metadata_and_preserves_old_file(session, tmp_path):
    path = tmp_path / 'native.npz'; path.write_bytes(b'old')
    req = request(session, path)
    for bad in ({**req, 'unexpected': 1}, {**req, 'expected': {}}, {**req, 'expected': {**req['expected'], 'iteration': 1}}, {**req, 'path': ''}):
        with pytest.raises(ValueError): data.save(session, bad)
        assert path.read_bytes() == b'old' and not data.DESTINATIONS
    def checkpoint(n):
        if n == 1: req['native_settings']['field'] = 'pressure'; session.quality['reasons'].append('later')
    result = data.save(session, req, checkpoint)
    assert result['metadata']['native_settings']['field'] == 'speed'
    assert 'later' not in data.read_archive(path)[1]['quality']['reasons']


@pytest.mark.parametrize('extra', [{'moving_bodies': []}, {'boundary_field': {}}, {'example': 'tgv3d-bgk'}, {'basis': [[0,1,0],[1,0,0],[0,0,1]]}, {'origin_m': [0,0,0]}, {'wall_links': [[0, 1, .5]]}])
def test_unsupported_case_rejected(session, extra):
    with pytest.raises(ValueError): data.validate_case({**session.spec, **extra})


def test_restore_mismatch_and_import_option_validation(session, tmp_path):
    path = tmp_path / 'native.npz'; data.save(session, request(session, path))
    populations, meta, means = data.read_archive(path)
    altered = copy.deepcopy(meta); altered['case_hash'] = 'other'
    with pytest.raises(ValueError): data.restore(session, populations, altered, means)
    job = Job(dict(kind='native_data_import', path=str(path), device='cpu', unknown=1)); job.work()
    assert job.state == 'failed' and job.error == 'Unsupported native import options'


def test_mean_history_and_original_mass_baseline_continue_exactly(session, tmp_path):
    session.advance(3)
    session.initial_mass *= 1.01
    path = tmp_path / 'means.npz'
    data.save(session, request(session, path))
    populations, meta, means = data.read_archive(path)
    assert meta['samples'] == 1 and meta['initial_mass'] == session.initial_mass
    assert set(means) == {'mean_u', 'mean_p', 'mean_rho'}
    for name, array in means.items(): np.testing.assert_array_equal(array, getattr(session, name).numpy())
    restored = Session(meta['case'], 'cpu')
    data.restore(restored, populations, meta, means)
    assert restored.samples == session.samples and restored.initial_mass == session.initial_mass
    for name, array in session.fields(True).items(): np.testing.assert_array_equal(array, restored.fields(True)[name])
    session.advance(6); restored.advance(6)
    for name in means: np.testing.assert_array_equal(getattr(session, name).numpy(), getattr(restored, name).numpy())
    np.testing.assert_array_equal(session.flow.f.numpy(), restored.flow.f.numpy())
    assert restored.samples == session.samples == 2


@pytest.mark.parametrize('failure', ['baseline', 'count', 'missing', 'dtype', 'shape', 'nonfinite', 'density'])
def test_invalid_mean_state_rejects_before_allocation(session, tmp_path, failure):
    session.advance(3)
    path = tmp_path / 'means.npz'; data.save(session, request(session, path))
    populations, meta, means = data.read_archive(path)
    if failure == 'baseline': meta['initial_mass'] = 0
    elif failure == 'count': meta['samples'] = 2
    elif failure == 'missing': means.pop('mean_u')
    elif failure == 'dtype': means['mean_u'] = means['mean_u'].astype('float64')
    elif failure == 'shape': means['mean_u'] = means['mean_u'][:, :-1]
    elif failure == 'nonfinite': means['mean_p'][0, 0, 0, 0] = np.nan
    else: means['mean_rho'][0, 0, 0, 0] = 0
    with pytest.raises(ValueError): data.validate_payload(populations, meta, means)


def test_versions_limits_and_finite_context(session, tmp_path, monkeypatch):
    path = tmp_path / 'data.npz'
    with pytest.raises(ValueError): data.context({'extra': 1})
    with pytest.raises(ValueError): data.context({'case_id': ''})
    with pytest.raises(ValueError): data.frozen({'nan': float('nan')})
    with monkeypatch.context() as patch:
        patch.setattr(data, 'MAX_METADATA', 1)
        with pytest.raises(ValueError, match='archive budget'): data.save(session, request(session, path))
    data.save(session, request(session, path))
    with zipfile.ZipFile(path) as z: members = {n: z.read(n) for n in z.namelist()}
    arr = session.flow.f.numpy(); stream = io.BytesIO()
    np.lib.format.write_array(stream, arr, version=(2, 0), allow_pickle=False)
    members['populations.npy'] = stream.getvalue()
    with zipfile.ZipFile(path, 'w') as z:
        for name, value in members.items(): z.writestr(name, value)
    np.testing.assert_array_equal(data.read_archive(path)[0], arr)


def test_native_curved_case_admission_preserves_links(session):
    spec = {**session.spec, 'wall_links': [[1, 10, .25], [2, 11, .75]]}
    before = copy.deepcopy(spec)
    data.validate_case(spec)
    assert spec == before
