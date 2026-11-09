"""Immutable-frame saves publish complete files and preserve earlier exports."""
import os

import numpy as np
import pytest

from hawa.fields import FRAMES, LOCK, dispatch_field, get, read_frame, store
from hawa.jobs import Cancelled


@pytest.fixture
def frame():
    shape = (3, 4, 5)
    arrays = dict(velocity=np.arange(3*np.prod(shape), dtype=np.float32).reshape((3,)+shape),
                  pressure=np.arange(np.prod(shape), dtype=np.float64).reshape(shape),
                  density=np.ones(shape, dtype=np.float32), solid=np.zeros(shape, bool),
                  strain_rate=np.zeros((3, 3)+shape, dtype=np.float32),
                  wall_velocity=np.zeros((3,)+shape[:2], dtype=np.float32))
    arrays['solid'][1, 2, 3] = True
    metadata = dict(case=dict(dx=.25, shape=list(shape), origin=[1., 2., 3.]),
                    iteration=7, time=.125, mean=False, samples=0,
                    quality=dict(status='within-tested-envelope'))
    key = store(arrays, metadata)['frame']
    try:
        yield key
    finally:
        with LOCK:
            FRAMES.pop(key, None)


def test_frame_save_round_trips_exact_fields_and_metadata_and_overwrites(frame, tmp_path):
    path = tmp_path/'nested'/'frame.npz'
    path.parent.mkdir()
    path.write_bytes(b'previous result')
    checkpoints = []
    result = dispatch_field(dict(action='save', frame=frame, path=str(path)),
                            checkpoint=checkpoints.append)
    assert result == {'path': str(path)}
    arrays, metadata = read_frame(path)
    expected_arrays, expected_metadata = get(frame)
    assert metadata == expected_metadata
    assert set(arrays) == set(expected_arrays)
    for name in arrays:
        np.testing.assert_array_equal(arrays[name], expected_arrays[name])
        assert arrays[name].dtype == expected_arrays[name].dtype
    assert checkpoints == [0, 0]
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('failure', ['write', 'fsync', 'replace'])
def test_failed_frame_save_preserves_target_and_removes_temporary_file(frame, tmp_path, monkeypatch, existing, failure):
    path = tmp_path/'frame.npz'
    if existing:
        dispatch_field(dict(action='save', frame=frame, path=str(path)))
    before = path.read_bytes() if existing else None

    def fail_write(stream, **payload):
        stream.write(b'partial')
        raise OSError('injected compression failure')

    def fail_io(*args):
        raise OSError('injected IO failure')

    if failure == 'write':
        monkeypatch.setattr(np, 'savez_compressed', fail_write)
    else:
        monkeypatch.setattr(os, failure, fail_io)
    with pytest.raises(OSError, match='injected'):
        dispatch_field(dict(action='save', frame=frame, path=str(path)))
    assert path.exists() == existing
    if existing:
        assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == (['frame.npz'] if existing else [])


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('cancel_at', [1, 2])
def test_cancel_observed_before_write_or_publication_preserves_target(frame, tmp_path, existing, cancel_at):
    path = tmp_path/'frame.npz'
    if existing:
        dispatch_field(dict(action='save', frame=frame, path=str(path)))
    before = path.read_bytes() if existing else None
    calls = []

    def checkpoint(step):
        calls.append(step)
        if len(calls) == cancel_at:
            raise Cancelled('cancelled at save checkpoint')

    with pytest.raises(Cancelled, match='save checkpoint'):
        dispatch_field(dict(action='save', frame=frame, path=str(path)), checkpoint=checkpoint)
    assert len(calls) == cancel_at
    assert path.exists() == existing
    if existing:
        assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == (['frame.npz'] if existing else [])


@pytest.mark.parametrize('existing', [False, True])
def test_expired_frame_does_not_touch_target(tmp_path, existing):
    path = tmp_path/'frame.npz'
    if existing:
        path.write_bytes(b'previous result')
    with pytest.raises(ValueError, match='Frame expired'):
        dispatch_field(dict(action='save', frame='missing-frame', path=str(path)))
    assert path.exists() == existing
    if existing:
        assert path.read_bytes() == b'previous result'
    assert sorted(p.name for p in tmp_path.iterdir()) == (['frame.npz'] if existing else [])


@pytest.mark.parametrize('existing', [False, True])
def test_frame_save_supports_long_valid_destination_name(frame, tmp_path, existing):
    # A valid destination component must not become the temporary file's prefix.
    path = tmp_path / ('f' * 246 + '.npz')
    assert len(path.name.encode('ascii')) == 250
    path.write_bytes(b'previous result')  # Prove this filesystem accepts the target.
    if not existing:
        path.unlink()
    result = dispatch_field(dict(action='save', frame=frame, path=str(path)))
    assert result == {'path': str(path)}
    arrays, metadata = read_frame(path)
    expected_arrays, expected_metadata = get(frame)
    assert metadata == expected_metadata
    for name in expected_arrays:
        np.testing.assert_array_equal(arrays[name], expected_arrays[name])
    assert list(tmp_path.iterdir()) == [path]
