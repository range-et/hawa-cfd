"""Independent CSV readback and publication failure contracts."""
import csv
import json
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from hawa import exports
from hawa.jobs import Cancelled, Job
from hawa.plugin import SESSIONS, dispatch


@pytest.fixture
def snapshot():
    shape = (3, 4, 3)
    arrays = {'velocity': np.arange(108, dtype=np.float32).reshape((3,) + shape) / 7,
              'pressure': np.linspace(-2, 3, 36).reshape(shape),
              'density': np.full(shape, 1.225),
              'solid': np.zeros(shape, bool), 'boundary_nodes': np.zeros(shape, bool)}
    arrays['solid'][0, 0, 0] = True
    arrays['boundary_nodes'][1, 0, 0] = True
    session = SimpleNamespace(lock=threading.RLock(), fields=lambda: arrays,
                              spec={'dx': .5, 'spacing': 2., 'origin': [8., 12., 16.],
                                    'basis': [[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]],
                                    'label': '=danger,\n"quoted"'},
                              flow=SimpleNamespace(i=7, units=SimpleNamespace(
                                  convert_length_to_pu=lambda n: n * .5,
                                  convert_time_to_pu=lambda n: n * .125)),
                              id='s', key='hash', quality={'warnings': ['x,\ny']},
                              backend=SimpleNamespace(info=lambda: {'device': 'cpu'}))
    return session, arrays


def read_table(path):
    with path.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.reader(stream))
    assert rows[0][0] == 'hawa-field-csv-1' and len(rows[0]) == 2
    meta = json.loads(rows[0][1])
    assert rows[1] == meta['columns']
    assert len(rows) - 2 == meta['rows'], 'incomplete table'
    return meta, rows[2:]


def request(destination, **options):
    return {'op': 'export', 'session': 's', 'path': str(destination), 'format': 'csv', **options}


def test_exact_values_coordinates_masks_units_and_escaped_metadata(snapshot, tmp_path):
    session, arrays = snapshot
    path = tmp_path / 'nested' / 'deeper' / 'field.csv'
    assert exports.export_csv(session, request(path)) == {'path': str(path), 'format': 'csv', 'rows': 36}
    meta, rows = read_table(path)
    assert meta == {
        'schema': 'hawa-field-csv-1', 'rows': 36, 'shape': [3, 4, 3], 'columns': exports.HEADER,
        'units': {'position': 'm', 'velocity': 'm/s', 'pressure': 'Pa', 'density': 'kg/m^3', 'time': 's'},
        'unit_system': 'SI', 'session': 's', 'case_hash': 'hash', 'case': session.spec,
        'hawa_version': '0.5.0', 'backend': {'device': 'cpu'}, 'iteration': 7, 'local_time': .875, 'time_origin': 0., 'absolute_time': .875,
        'quality': session.quality, 'sampling': 'instantaneous lattice nodes',
        'origin': [2., 3., 4.], 'basis': session.spec['basis'], 'dx': .5,
        'velocity_axes': 'domain; world vector = domain vector @ basis',
        'pressure_reference': 'solver gauge pressure relative to rest density; no coefficient conversion',
        'validity': 'valid = not (solid or boundary_node); invalid quantities are empty',
        'precision': 'Python float round-trip decimal; float32 values promoted exactly',
    }
    assert exports.HEADER == ['i', 'j', 'k', 'x', 'y', 'z', 'solid', 'boundary_node', 'valid',
                              'u_domain', 'v_domain', 'w_domain', 'pressure', 'density']
    for index, row in zip(np.ndindex(arrays['pressure'].shape), rows):
        i, j, k = index
        assert list(map(int, row[:3])) == [i, j, k]
        assert list(map(float, row[3:6])) == [2 - j * .5, 3 + i * .5, 4 + k * .5]
        flags = [int(arrays['solid'][index]), int(arrays['boundary_nodes'][index])]
        assert list(map(int, row[6:9])) == flags + [int(not any(flags))]
        if any(flags):
            assert row[9:] == [''] * 5
        else:
            assert list(map(float, row[9:])) == list(arrays['velocity'][(slice(None),) + index]) + [arrays['pressure'][index], arrays['density'][index]]
    assert list(path.parent.iterdir()) == [path]


def test_real_2d_benchmark_and_npz_extension_compatibility(tmp_path):
    ident = dispatch({'op': 'create', 'case': {'example': 'tgv2d-bgk', 'size': 8}, 'device': 'cpu'})['session']
    try:
        path = tmp_path / 'named.csv'
        dispatch({'op': 'export', 'session': ident, 'path': str(path)})
        with np.load(path, allow_pickle=False) as archive:
            np.testing.assert_array_equal(archive['velocity'], SESSIONS[ident].fields()['velocity'])
        result = dispatch({'op': 'export', 'session': ident, 'path': str(path), 'format': 'csv'})
        meta, rows = read_table(path)
        assert result['rows'] == 64
        assert meta['unit_system'] == 'benchmark-normalized'
        assert meta['units'] == dict(position='normalized length', velocity='normalized velocity', pressure='normalized pressure', density='normalized density', time='normalized time')
        assert meta['iteration'] == 0 and meta['local_time'] == meta['absolute_time'] == meta['time_origin'] == 0
        assert all(row[2] == '0' and row[5] == '0.0' and row[11] == '0.0' for row in rows)
        assert meta['dx'] == float(SESSIONS[ident].flow.units.convert_length_to_pu(1))
        with pytest.raises(ValueError, match='format=csv'):
            dispatch({'op': 'export', 'session': ident, 'path': str(path), 'format': 'unknown'})
    finally:
        dispatch({'op': 'close', 'session': ident})


@pytest.mark.parametrize('options', [{'format': 'bad'}, {'path': None}, {'path': ''}, {'path': '  '}, {'mean': True}])
def test_bad_request_does_not_touch_destination(snapshot, tmp_path, options):
    path = tmp_path / 'field.csv'
    with pytest.raises(ValueError, match='CSV export requires'):
        exports.export_csv(snapshot[0], request(path, **options))
    assert not path.exists()


@pytest.mark.parametrize('failure', ['nan', 'size', 'geometry', 'capture', 'write', 'flush', 'replace', 'create'])
@pytest.mark.parametrize('existing', [False, True])
def test_failed_publication_preserves_previous_file(snapshot, tmp_path, monkeypatch, failure, existing):
    session, arrays = snapshot
    path = tmp_path / 'field.csv'
    if existing:
        path.write_text('previous complete result')
    def fail(*args, **kwargs):
        raise OSError('injected IO failure')
    if failure == 'nan': arrays['pressure'][0, 0, 0] = float('nan')
    elif failure == 'size': monkeypatch.setattr(exports, 'MAX_ROWS', 35)
    elif failure == 'geometry': session.spec['basis'][0][0] = 4
    elif failure == 'capture': session.fields = fail
    elif failure == 'write': monkeypatch.setattr(exports.csv, 'writer', fail)
    elif failure == 'flush': monkeypatch.setattr(exports.os, 'fsync', fail)
    elif failure == 'replace': monkeypatch.setattr(exports.os, 'replace', fail)
    else: monkeypatch.setattr(exports.tempfile, 'NamedTemporaryFile', fail)
    with pytest.raises((OSError, ValueError)):
        exports.export_csv(session, request(path))
    assert path.read_text() == 'previous complete result' if existing else not path.exists()
    assert list(tmp_path.iterdir()) == ([path] if existing else [])


@pytest.mark.parametrize('cancel_call', [1, 2, 3])
def test_cancel_before_capture_during_rows_and_before_replace(snapshot, tmp_path, cancel_call):
    path = tmp_path / 'field.csv'
    path.write_text('previous')
    calls = []
    def checkpoint(steps):
        calls.append(steps)
        if len(calls) == cancel_call:
            raise Cancelled('cancel now')
    with pytest.raises(Cancelled):
        exports.export_csv(snapshot[0], request(path), checkpoint)
    assert calls == [0, 0, 36][:cancel_call]
    assert path.read_text() == 'previous' and list(tmp_path.iterdir()) == [path]


def test_capture_provenance_is_frozen_before_io_and_long_names(snapshot, tmp_path):
    session, _ = snapshot
    path = tmp_path / ('x' * 246 + '.csv')
    def checkpoint(steps):
        if steps == 36:
            session.quality['warnings'].append('later')
            session.spec['label'] = 'later'
            session.flow.i += 1
    exports.export_csv(session, request(path), checkpoint)
    meta, _ = read_table(path)
    assert meta['quality'] == {'warnings': ['x,\ny']} and meta['case']['label'] != 'later' and meta['iteration'] == 7
    lines = path.read_text().splitlines(keepends=True)
    path.write_text(''.join(lines[:-1]))
    with pytest.raises(AssertionError, match='incomplete table'):
        read_table(path)


def test_query_job_routes_csv_without_device_lock_and_cancels(snapshot, tmp_path, monkeypatch):
    session, _ = snapshot
    monkeypatch.setitem(SESSIONS, 's', session)
    path = tmp_path / 'field.csv'
    job = Job({'kind': 'query', 'request': request(path)})
    def forbidden(*args):
        raise AssertionError('CPU export took device slot')
    monkeypatch.setattr(job, 'take_device', forbidden)
    job.work()
    assert job.state == 'completed' and job.result == {'path': str(path), 'format': 'csv', 'rows': 36}
    read_table(path)
    before = path.read_bytes()
    job = Job({'kind': 'query', 'request': request(path)})
    original = job.checkpoint
    def cancel_before_replace(steps, state='running'):
        if steps == 36:
            job.cancelled = True
        original(steps, state)
    monkeypatch.setattr(job, 'checkpoint', cancel_before_replace)
    job.work()
    assert job.state == 'cancelled' and job.result is None and path.read_bytes() == before


def test_multi_chunk_checkpoints_and_partial_write_cleanup(snapshot, tmp_path, monkeypatch):
    session, arrays = snapshot
    shape = (11, 11, 11)
    arrays.clear()
    arrays.update(velocity=np.zeros((3,) + shape), pressure=np.zeros(shape), density=np.ones(shape))
    path = tmp_path / 'field.csv'
    calls = []
    monkeypatch.setattr(exports, 'MAX_ROWS', 1331)
    exports.export_csv(session, request(path), calls.append)
    assert calls == [0, 0, 1024, 1331]
    assert len(read_table(path)[1]) == 1331
    before = path.read_bytes()
    real_writer = csv.writer
    class PartialWriter:
        def __init__(self, stream):
            self.stream = stream
            self.writer = real_writer(stream)
            self.calls = 0
        def writerow(self, row):
            self.calls += 1
            if self.calls == 4:
                self.stream.write('partial,row')
                raise OSError('partial write')
            self.writer.writerow(row)
    monkeypatch.setattr(exports.csv, 'writer', PartialWriter)
    with pytest.raises(OSError, match='partial write'):
        exports.export_csv(session, request(path))
    assert path.read_bytes() == before and list(tmp_path.iterdir()) == [path]


def test_absolute_time_and_transport_identifiers(snapshot, tmp_path):
    session, _ = snapshot
    session.spec['time_origin_seconds'] = 12.25
    path = tmp_path / 'time.csv'
    exports.export_csv(session, request(path, request_id='transport-only', revision=7))
    meta, _ = read_table(path)
    assert meta['time_origin'] == 12.25 and meta['local_time'] == .875 and meta['absolute_time'] == 13.125
    assert meta['case']['time_origin_seconds'] == 12.25
    assert 'revision' not in meta and 'request_id' not in meta


@pytest.mark.parametrize('has_dx', [False, True])
def test_fallback_display_spacing_preserves_origin(snapshot, tmp_path, has_dx):
    session, _ = snapshot
    del session.spec['spacing']
    if not has_dx:
        del session.spec['dx']
        session.spec['example'] = 'reference'
    path = tmp_path / 'fallback.csv'
    exports.export_csv(session, request(path))
    meta, rows = read_table(path)
    expected = [8., 12., 16.] if has_dx else [4., 6., 8.]
    assert meta['origin'] == expected
    assert list(map(float, rows[0][3:6])) == expected


def test_nonfinite_metadata_cannot_publish(snapshot, tmp_path):
    session, _ = snapshot
    session.quality['bad'] = float('nan')
    path = tmp_path / 'bad.csv'
    path.write_text('previous')
    with pytest.raises(ValueError, match='JSON compliant'):
        exports.export_csv(session, request(path))
    assert path.read_text() == 'previous' and list(tmp_path.iterdir()) == [path]


def test_portable_temporary_location_encoding_and_newlines(snapshot, tmp_path, monkeypatch):
    session, _ = snapshot
    session.spec['label'] = 'é,中文\nnext'
    path = tmp_path / 'portable.csv'
    real_temporary = exports.tempfile.NamedTemporaryFile
    def temporary(**kwargs):
        # Same-directory publication must work even when the system temporary
        # directory is on a different volume. Explicit text settings avoid the
        # host locale and Windows newline translation changing exported bytes.
        assert kwargs['dir'] == path.parent
        assert kwargs['encoding'].lower() == 'utf-8'
        assert kwargs['newline'] == ''
        return real_temporary(**kwargs)
    monkeypatch.setattr(exports.tempfile, 'NamedTemporaryFile', temporary)
    exports.export_csv(session, request(path))
    assert read_table(path)[0]['case']['label'] == 'é,中文\nnext'
    assert b'\r\r\n' not in path.read_bytes()


def test_npz_query_is_not_routed_to_csv(snapshot, tmp_path, monkeypatch):
    session, _ = snapshot
    monkeypatch.setitem(SESSIONS, 's', session)
    path = tmp_path / 'still-npz.csv'
    job = Job({'kind': 'query', 'request': request(path, format='npz')})
    job.work()
    assert job.state == 'completed' and job.result == {'path': str(path)}
    with np.load(path, allow_pickle=False) as data:
        np.testing.assert_array_equal(data['pressure'], session.fields()['pressure'])
