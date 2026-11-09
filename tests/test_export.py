"""Raw exports preserve the last complete artifact if a replacement fails."""
import json

import numpy as np
import pytest

from hawa.plugin import SESSIONS, dispatch


@pytest.fixture
def export_session():
    ident = dispatch({'op': 'create', 'case': {'example': 'tgv3d-bgk', 'size': 8}, 'device': 'cpu'})['session']
    dispatch({'op': 'step', 'session': ident, 'steps': 3})
    try:
        yield ident
    finally:
        dispatch({'op': 'close', 'session': ident})


def test_export_round_trip_keeps_raw_fields_and_capture_metadata(export_session, tmp_path):
    path = tmp_path / 'nested' / 'field.npz'
    session = SESSIONS[export_session]
    expected = session.fields()
    result = dispatch({'op': 'export', 'session': export_session, 'path': str(path)})
    assert result == {'path': str(path)}
    with np.load(path, allow_pickle=False) as data:
        assert set(data.files) == set(expected) | {'metadata'}
        for name, value in expected.items():
            np.testing.assert_array_equal(data[name], value)
        metadata = json.loads(str(data['metadata']))
        assert metadata['iteration'] == 3
        assert metadata['time'] == session.flow.units.convert_time_to_pu(3)
        assert metadata['case'] == session.spec
        assert metadata['quality'] == session.quality
    dispatch({'op': 'step', 'session': export_session, 'steps': 2})
    dispatch({'op': 'export', 'session': export_session, 'path': str(path)})
    with np.load(path, allow_pickle=False) as data:
        assert json.loads(str(data['metadata']))['iteration'] == 5
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('failure', ['capture', 'write', 'flush', 'replace'])
def test_failed_export_preserves_destination_and_cleans_temporary_files(export_session, tmp_path, monkeypatch, existing, failure):
    import os
    path = tmp_path / 'field.npz'
    if existing:
        dispatch({'op': 'export', 'session': export_session, 'path': str(path)})
    before = path.read_bytes() if existing else None

    def fail_capture(*args, **kwargs):
        raise OSError('injected capture failure')

    def fail_write(stream, **kwargs):
        stream.write(b'partial archive')
        raise OSError('injected write failure')

    def fail_replace(*args, **kwargs):
        raise OSError('injected replace failure')

    if failure == 'capture':
        monkeypatch.setattr(SESSIONS[export_session], 'fields', fail_capture)
    elif failure == 'write':
        monkeypatch.setattr(np, 'savez_compressed', fail_write)
    elif failure == 'flush':
        monkeypatch.setattr(os, 'fsync', fail_replace)
    else:
        monkeypatch.setattr(os, 'replace', fail_replace)
    with pytest.raises(OSError, match='injected'):
        dispatch({'op': 'export', 'session': export_session, 'path': str(path)})
    assert path.exists() == existing
    if existing:
        assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == (['field.npz'] if existing else [])


def test_export_metadata_describes_capture_before_later_steps(export_session, tmp_path, monkeypatch):
    path = tmp_path / 'field.npz'
    session = SESSIONS[export_session]
    expected = session.fields()
    writer = np.savez_compressed

    def write_after_advance(stream, **payload):
        session.advance(2)
        return writer(stream, **payload)

    monkeypatch.setattr(np, 'savez_compressed', write_after_advance)
    dispatch({'op': 'export', 'session': export_session, 'path': str(path)})
    assert session.flow.i == 5
    with np.load(path, allow_pickle=False) as data:
        assert json.loads(str(data['metadata']))['iteration'] == 3
        for name, value in expected.items():
            np.testing.assert_array_equal(data[name], value)
