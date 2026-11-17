"""Adversarial native-data boundaries found by scoped mutation review."""
import copy
import json
import time
import uuid
import zipfile
from types import SimpleNamespace

import numpy as np
import pytest

from hawa import native_data as data
from hawa.plugin import Session, case_key
from test_native_data import session as session, request


def rejects(call):
    with pytest.raises(ValueError) as error: call()
    assert str(error.value) not in ('', 'None')


@pytest.fixture
def payload(session, tmp_path):
    path = tmp_path / 'capture.npz'
    data.save(session, request(session, path))
    return data.read_archive(path)


@pytest.mark.parametrize('links', [
    [1, 10, .5], [[1, 10]], [[1, 10, .5, 1]], [[1.5, 10, .5]], [[1, 10.5, .5]],
    [[19, 10, .5]], [[0, 10, .5]], [[1, -1, .5]], [[1, 240, .5]],
    [[1, 10, 0]], [[1, 10, 1.1]], [[1, 10, float('nan')]],
])
def test_link_boundaries_reject_before_construction(session, links):
    rejects(lambda: data.validate_case({**session.spec, 'wall_links': links}))


def test_native_case_options_and_geometry_tolerances(session):
    spec = {**session.spec, 'kind': 'Case', 'label': 'native', 'hawa_block_width': .5,
            'basis': np.eye(3).tolist(), 'memory_limit_mb': 128,
            'boundaries': ['inlet', 'outlet', 'periodic', 'periodic', 'wall', 'slip'],
            'wall_links': [[1, 0, 1.], [18, 239, .1]]}
    data.validate_case(spec)
    rejects(lambda: data.validate_case({**spec, 'moving_bodies': []}))
    rejects(lambda: data.validate_case({**spec, 'basis': [[0, 1, 0], [-1, 0, 0], [0, 0, 1]]}))
    for delta in (1e-7, 1e-9):
        rejects(lambda: data.validate_case({**spec, 'origin_m': [1 + delta, 2, 3]}))
    data.validate_case({**spec, 'origin_m': [1 + 1e-13, 2, 3]})


@pytest.mark.parametrize('state', ['ready', 'completed'])
def test_zero_iteration_defaults_and_stopped_states(session, tmp_path, state):
    spec = dict(session.spec); spec.pop('time_origin_seconds'); spec.pop('mach')
    fresh = Session(spec, 'cpu'); fresh.state = state
    req = request(fresh, tmp_path / 'a' / 'b' / 'file.npz')
    req.pop('native_settings'); req.pop('attribution')
    result = data.save(fresh, req)
    meta = result['metadata']
    assert meta['iteration'] == meta['local_time'] == meta['time_origin'] == meta['absolute_time'] == 0
    assert meta['source_state'] == state and meta['native_settings'] == meta['attribution'] == {}
    assert str(uuid.UUID(meta['artifact_id'])) == meta['artifact_id']


def test_restore_status_mass_timestamp_and_small_baseline(session, payload):
    populations, meta, means = payload
    meta['initial_mass'] = .5
    restored = Session(meta['case'], 'cpu')
    before = time.time(); data.restore(restored, populations, meta, means); after = time.time()
    assert restored.target == meta['iteration']
    assert before <= restored.updated <= after
    assert restored.relative_mass_change == (float(restored.flow.rho().sum().cpu()) - .5) / .5


@pytest.mark.parametrize('key,bad', [('op', 'save'), ('action', 'load'), ('path', 1)])
def test_wrong_save_request_rejects(session, tmp_path, key, bad):
    req = request(session, tmp_path / 'x'); req[key] = bad
    rejects(lambda: data.save(session, req))


@pytest.mark.parametrize('stamp', [
    dict(case_hash='h', iteration=-1, state='paused'), dict(case_hash='h', iteration=True, state='paused'),
    dict(case_hash='', iteration=0, state='paused'), dict(case_hash=1, iteration=0, state='paused'),
])
def test_invalid_stamp_rejects_before_solver_lock(session, tmp_path, stamp):
    class ForbiddenLock:
        def __enter__(self): pytest.fail('Malformed stamp reached solver lock')
        def __exit__(self, *args): pass
    session.lock = ForbiddenLock()
    req = request(session, tmp_path / 'x'); req['expected'] = stamp
    rejects(lambda: data.save(session, req))
    # Fixture teardown closes a CPU session using its normal reentrant lock.
    import threading
    session.lock = threading.RLock()


def test_worker_alive_rejects_and_distinct_destination_can_progress(session, tmp_path):
    path = tmp_path / 'x'; req = request(session, path)
    session.thread = SimpleNamespace(is_alive=lambda: True)
    rejects(lambda: data.save(session, req))
    session.thread = None
    def checkpoint(n):
        if n == 0: data.save(session, request(session, tmp_path / 'other'))
    result = data.save(session, req, checkpoint)
    assert result['metadata']['attribution'] == req['attribution']
    assert str(uuid.UUID(result['metadata']['artifact_id'])) == result['metadata']['artifact_id']


def test_same_directory_publication(session, tmp_path, monkeypatch):
    target = tmp_path / 'deep' / 'deeper' / 'data.npz'
    original = data.os.replace
    def replace(source, destination):
        assert source.parent == destination.parent == target.parent
        original(source, destination)
    monkeypatch.setattr(data.os, 'replace', replace)
    data.save(session, request(session, target))
    assert target.is_file() and list(target.parent.iterdir()) == [target]


@pytest.mark.parametrize('key,value', [
    ('artifact_id', ''), ('artifact_id', 1), ('source_session', ''), ('hawa_version', ''),
    ('iteration', -1), ('iteration', 1.), ('local_time', True), ('time_origin', float('inf')),
    ('initial_mass', True), ('native_settings', {'bad': float('nan')}),
])
def test_capture_types_are_checked(payload, key, value):
    populations, meta, means = payload
    meta[key] = value
    rejects(lambda: data.validate_payload(populations, meta, means))


@pytest.mark.parametrize('change', ['time', 'time-relative', 'quality-time', 'quality-relative', 'quality-iteration', 'quality-type'])
def test_capture_times_and_quality_have_matching_identity(payload, change):
    populations, meta, means = payload
    if change.startswith('quality'):
        if change == 'quality-iteration': meta['quality']['iteration'] -= 1
        elif change == 'quality-type': meta['quality']['iteration'] = float(meta['iteration'])
        else: meta['quality']['time_seconds'] += 1e-11 if change == 'quality-relative' else .01
    else:
        meta['local_time'] += 1e-11 if change == 'time-relative' else .01
        meta['absolute_time'] = meta['local_time'] + meta['time_origin']
    rejects(lambda: data.validate_payload(populations, meta, means))


@pytest.mark.parametrize('status', ['warning', 'rejected'])
def test_saved_quality_severity_is_preserved(payload, status):
    populations, meta, means = payload
    meta['quality']['status'] = status
    data.validate_payload(populations, meta, means)


def test_nondefault_time_scaling_and_defaults(payload):
    populations, meta, means = payload
    for speed, mach in ((2., .07), (1., None)):
        modified = copy.deepcopy(meta)
        for name, value in (('speed', speed), ('mach', mach)):
            if value is None: modified['case'].pop(name)
            else: modified['case'][name] = value
        modified['case_hash'] = case_key(modified['case'])
        modified['local_time'] = float(3 * .5 * (mach or .05) / (np.sqrt(3) * (speed or 1)))
        modified['absolute_time'] = 10 + modified['local_time']
        modified['quality']['time_seconds'] = modified['local_time']
        data.validate_payload(populations, modified, means)


def test_subunit_positive_mean_density_and_first_average(session, tmp_path):
    session.advance(2)
    path = tmp_path / 'means'; data.save(session, request(session, path))
    populations, meta, means = data.read_archive(path)
    assert meta['iteration'] == 5 and meta['samples'] == 1
    means['mean_rho'].fill(.5)
    data.validate_payload(populations, meta, means)


def test_tiny_timestamp_roundoff_is_accepted(payload):
    populations, meta, means = payload
    meta['local_time'] += 1e-13; meta['absolute_time'] = meta['time_origin'] + meta['local_time']
    meta['quality']['time_seconds'] += 2e-13
    data.validate_payload(populations, meta, means)


def test_archive_and_writer_exact_budgets(session, tmp_path, monkeypatch):
    session.advance(3)
    path = tmp_path / 'data'; req = request(session, path)
    # Freeze the unique ID so calculating the exact metadata byte budget is stable.
    monkeypatch.setattr(data.uuid, 'uuid4', lambda: uuid.UUID(int=1))
    result = data.save(session, req)
    populations, meta, means = data.read_archive(path)
    metadata_bytes = np.array(json.dumps(meta, allow_nan=False)).nbytes
    exact_writer = metadata_bytes + populations.nbytes + sum(a.nbytes for a in means.values()) + 4096
    monkeypatch.setattr(data, 'MAX_BYTES', exact_writer)
    monkeypatch.setattr(data, 'MAX_METADATA', metadata_bytes)
    assert data.save(session, req) == result
    monkeypatch.setattr(data, 'MAX_BYTES', exact_writer - 1)
    rejects(lambda: data.save(session, req))
    with zipfile.ZipFile(path) as z: exact_read = sum(i.file_size for i in z.infolist())
    monkeypatch.setattr(data, 'MAX_BYTES', exact_read)
    data.read_archive(path)
    monkeypatch.setattr(data, 'MAX_BYTES', exact_read - 1)
    rejects(lambda: data.read_archive(path))


def test_density_finiteness_is_per_cell_not_global_or_spatial_sum(payload):
    populations, meta, means = payload
    with np.errstate(over='ignore'):
        populations.fill(np.finfo(np.float32).max / 20)
        data.validate_payload(populations, meta, means)
        populations.fill(np.finfo(np.float32).max / 10)
        rejects(lambda: data.validate_payload(populations, meta, means))


def test_nonuniform_mass_diagnostic_uses_solver_reduction(payload):
    populations, meta, means = payload
    populations = np.random.default_rng(0).uniform(.01, .1, populations.shape).astype('float32')
    restored = Session(meta['case'], 'cpu')
    data.restore(restored, populations, meta, means)
    expected_mass = float(restored.flow.rho().sum().cpu())
    assert expected_mass != float(populations.sum()), 'Fixture must distinguish reduction ordering'
    assert restored.relative_mass_change == (expected_mass - meta['initial_mass']) / meta['initial_mass']


@pytest.mark.parametrize('key', ['shape', 'dx', 'speed', 'viscosity'])
def test_native_case_requires_solver_constructor_fields(session, key):
    spec = dict(session.spec); spec.pop(key)
    rejects(lambda: data.validate_case(spec))


@pytest.mark.parametrize('change', ['time', 'time-relative', 'quality-policy', 'extra-key', 'float-step', 'bool-origin'])
def test_metadata_invariants_are_independent_of_downstream_checks(payload, change):
    populations, meta, means = payload
    if change.startswith('time'):
        meta['local_time'] += 1e-11 if change == 'time-relative' else .01
        meta['absolute_time'] = meta['local_time'] + meta['time_origin']
        meta['quality']['time_seconds'] = meta['local_time']
    elif change == 'quality-policy': meta['quality']['policy'] = 'other'
    elif change == 'extra-key': meta['extra'] = 'unexpected'
    elif change == 'float-step': meta['iteration'] = float(meta['iteration'])
    else:
        meta['case']['time_origin_seconds'] = True
        meta['case_hash'] = case_key(meta['case'])
        meta['time_origin'] = True
        meta['absolute_time'] = meta['local_time'] + 1
    rejects(lambda: data.validate_payload(populations, meta, means))


def test_positive_subunit_mass_baseline_is_valid(payload):
    populations, meta, means = payload
    meta['initial_mass'] = .5
    data.validate_payload(populations, meta, means)


@pytest.mark.parametrize('member,bad', [('metadata', np.array(['not scalar'])), ('populations', np.ones((19, 4, 4, 4), 'float64')), ('populations', np.ones((19, 4, 4), 'float32'))])
def test_invalid_member_headers_reject_before_numpy_allocation(session, tmp_path, monkeypatch, member, bad):
    import io
    path = tmp_path / 'bad'; data.save(session, request(session, path))
    with zipfile.ZipFile(path) as z: members = {n: z.read(n) for n in z.namelist()}
    stream = io.BytesIO(); np.save(stream, bad); members[member + '.npy'] = stream.getvalue()
    with zipfile.ZipFile(path, 'w') as z:
        for name, value in members.items(): z.writestr(name, value)
    monkeypatch.setattr(data.np, 'load', lambda *a, **k: pytest.fail('Invalid header reached array allocation'))
    rejects(lambda: data.read_archive(path))


def test_validation_diagnostics_remain_actionable(session, payload, tmp_path):
    populations, meta, means = payload
    rejects(lambda: data.context({'extra': 1}))
    rejects(lambda: data.restore(session, populations, {**meta, 'case_hash': 'other'}, means))
    rejects(lambda: data.validate_payload(populations, {**meta, 'native_settings': []}, means))
    rejects(lambda: data.validate_payload(populations, {**meta, 'schema': 'other'}, means))
    changed = copy.deepcopy(meta); changed['samples'] = 1; changed['iteration'] = 5
    changed['local_time'] *= 5/3; changed['absolute_time'] = 10 + changed['local_time']
    changed['quality']['iteration'] = 5; changed['quality']['time_seconds'] = changed['local_time']
    bad_means = {name: np.zeros((3 if name == 'mean_u' else 1, *meta['case']['shape']), 'float32') for name in ('mean_u', 'mean_p', 'mean_rho')}
    rejects(lambda: data.validate_payload(populations, changed, bad_means))
    path = tmp_path / 'bad'
    with zipfile.ZipFile(path, 'w') as z: z.writestr('extra.npy', b'wrong')
    rejects(lambda: data.read_archive(path))
    data.save(session, request(session, path))
    with zipfile.ZipFile(path) as z: members = {n: z.read(n) for n in z.namelist()}
    members['populations.npy'] = b'\x93NUMPY\x03\x00' + members['populations.npy'][8:]
    with zipfile.ZipFile(path, 'w') as z:
        for name, value in members.items(): z.writestr(name, value)
    rejects(lambda: data.read_archive(path))


def test_checkpoint_progress_values_are_nonnegative_integers(session, tmp_path):
    seen = []
    def checkpoint(n):
        assert type(n) is int and n >= 0
        seen.append(n)
    path = tmp_path / 'progress'
    data.save(session, request(session, path), checkpoint)
    data.read_archive(path, checkpoint)
    assert len(seen) == 5


def test_lexical_save_path_and_canonical_alias_reservation(session, tmp_path):
    import os
    real = tmp_path / 'RealDestination'; real.mkdir()
    if os.name == 'nt':
        # A case alias exercises Windows canonical path identity without requiring
        # the administrator/developer privilege needed to create a symlink.
        alias = real.with_name(real.name.swapcase())
    else:
        alias = tmp_path / 'alias'; alias.symlink_to(real, target_is_directory=True)
    chosen = alias / 'data.npz'
    def checkpoint(n):
        if n == 0:
            with pytest.raises(ValueError, match='already being exported'):
                data.save(session, request(session, real / 'data.npz'))
    result = data.save(session, request(session, chosen), checkpoint)
    assert result['path'] == os.path.abspath(str(chosen))
    assert chosen.is_file() and (real / 'data.npz').is_file()
    assert data.read_archive(chosen)[1] == result['metadata']
    assert not data.DESTINATIONS
