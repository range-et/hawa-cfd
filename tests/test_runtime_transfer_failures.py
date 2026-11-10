"""Offline transfer validation and partial-file cleanup contracts."""
import json
import numpy as np
import pytest
from hawa import boundary_data as v1, boundary_series as v2
from hawa.plugin import Session
from hawa.recording import record
from test_boundary_data import case, series
from test_boundary_series import case as external_case, recording


@pytest.mark.parametrize('change', [{'basis': [[1,0,0],[0,1,0],[0,0,-1]]},
    {'basis': [[2,0,0],[0,1,0],[0,0,1]]}, {'origin': [float('nan'),0,0]}, {'spacing': -1.}])
def test_transfer_geometry_rejects_invalid_coordinate_frames(change):
    spec = case(); spec.update(change)
    with pytest.raises(ValueError, match='right-handed orthonormal'): v1.geometry(spec)


@pytest.mark.parametrize('mode', ['shape', 'nan', 'quality'])
def test_v1_read_rejects_bad_velocity_or_quality(tmp_path, mode):
    spec = case(); path = series(tmp_path/'in.npz', spec)
    with np.load(path) as archive: data = {key: archive[key] for key in archive}
    if mode == 'shape': data['velocity'] = np.zeros((2,2,6,6))
    if mode == 'nan': data['velocity'][0,0,0,0] = np.nan
    if mode == 'quality':
        meta = json.loads(str(data['metadata'])); meta['quality']['transfer_eligible'] = False
        data['metadata'] = np.array(json.dumps(meta))
    np.savez_compressed(path, **data)
    with pytest.raises(ValueError, match='quality' if mode == 'quality' else 'velocity shape'): v1.read(path)


def test_v1_requires_velocity_xminus_attachment(tmp_path):
    from test_general_boundaries import channel
    spec = channel(wall=False); path = series(tmp_path/'in.npz', spec)
    spec['boundary_set']['patches'][0]['condition']['type'] = 'open'
    with pytest.raises(ValueError, match='velocity X-'): v1.attach(path, spec)


@pytest.mark.parametrize('version', [1, 2])
@pytest.mark.parametrize('failure', ['write', 'attachment'])
def test_transfer_failure_removes_partial_output(tmp_path, monkeypatch, version, failure):
    if version == 1:
        spec = case(origin=[.2,0,0]); parent = Session(case(), 'cpu')
        manifest = record(parent, 2, 1, str(tmp_path/'parent'), lambda _: None)['manifest']; module = v1
    else:
        manifest = recording(tmp_path/'parent', external_case()); spec = external_case((6,6,8), .5, [2,2,.25]); module = v2
    path = tmp_path/'output.npz'
    def fail(*args, **kwargs): raise OSError('injected transfer failure')
    if failure == 'write': monkeypatch.setattr(module.np, 'savez_compressed', fail)
    else: monkeypatch.setattr(module, 'attach', fail)
    with pytest.raises(OSError, match='injected transfer'): module.capture(manifest, spec, path)
    assert not path.exists()
    assert (tmp_path/'parent'/'manifest.json').exists()


def test_v1_capture_frame_count_and_provenance(tmp_path):
    parent = Session(case(), 'cpu'); manifest = record(parent, 2, 1, str(tmp_path/'parent'), lambda _: None)['manifest']
    from pathlib import Path
    manifest = Path(manifest); data = json.loads(manifest.read_text()); original = json.loads(manifest.read_text())
    data['frames'] = data['frames'][:1]; manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='2..1000'): v1.capture(manifest, case(), tmp_path/'few.npz')
    original['frames'][0]['time'] = -.1; manifest.write_text(json.dumps(original))
    with pytest.raises(ValueError, match='provenance'): v1.capture(manifest, case(), tmp_path/'wrong.npz')
    assert not (tmp_path/'few.npz').exists() and not (tmp_path/'wrong.npz').exists()


@pytest.mark.parametrize('spec', [{}, {'neutral_precursor': {'mode': 'external'}, 'boundary_set': {'patches': []}}])
def test_v2_requires_external_active_faces(spec):
    with pytest.raises(ValueError, match='neutral external child'): v2.active_faces(spec)
