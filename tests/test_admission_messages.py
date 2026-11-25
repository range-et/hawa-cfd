"""Regression tests for #75: early admission, output path validation, and actionable messages."""
from pathlib import Path
import os
import stat

import numpy as np
import pytest

from hawa.admission import (
    check_capture_budget,
    preflight_job,
    validate_new_output_dir,
    validate_new_output_file,
)
from hawa.boundary_data import capture as capture_v1
from hawa.boundary_series import capture as capture_v2, validate_attachment
from hawa.jobs import dispatch_job
from hawa.plugin import check_case
from hawa.refinement import check_refinement


def _basic_spec(shape=(8, 6, 6), memory_limit_mb=1024):
    return {
        "shape": list(shape),
        "dx": 0.1,
        "speed": 1.0,
        "viscosity": 0.01,
        "density": 1.225,
        "mach": 0.05,
        "collision": "bgk",
        "memory_limit_mb": memory_limit_mb,
    }


def _neutral_external_spec(shape=(12, 12, 12), memory_limit_mb=1024):
    patches = [
        {"id": "x-", "face": "x-", "condition": {"type": "velocity", "velocity": [5.0, 0.0, 0.0], "profile": "neutral"}},
        {"id": "x+", "face": "x+", "condition": {"type": "open", "velocity": [0.0, 0.0, 0.0], "pressure_pa": 0.0, "profile": "neutral", "backflow_mode": "velocity"}},
        {"id": "y-", "face": "y-", "condition": {"type": "open", "velocity": [5.0, 0.0, 0.0], "pressure_pa": 0.0, "profile": "neutral", "backflow_mode": "velocity"}},
        {"id": "y+", "face": "y+", "condition": {"type": "open", "velocity": [5.0, 0.0, 0.0], "pressure_pa": 0.0, "profile": "neutral", "backflow_mode": "velocity"}},
        {"id": "z-", "face": "z-", "condition": {"type": "wall", "velocity": [0.0, 0.0, 0.0]}},
        {"id": "z+", "face": "z+", "condition": {"type": "slip"}},
    ]
    return {
        "shape": list(shape),
        "dx": 0.5,
        "speed": 5.0,
        "viscosity": 1.5e-5,
        "density": 1.225,
        "mach": 0.05,
        "collision": "shifted-regularized-sgs-v1",
        "boundaries": ["periodic", "periodic", "periodic", "periodic", "wall", "slip"],
        "boundary_set": {"schema": 1, "patches": patches},
        "boundary_method": "shifted-links-v1",
        "neutral_precursor": {
            "schema": 1,
            "experimental": True,
            "mode": "external",
            "reference_height_m": 2.0,
            "roughness_length_m": 0.01,
            "smagorinsky_constant": 0.17,
            "perturbation_fraction": 0.02,
        },
        "memory_limit_mb": memory_limit_mb,
    }


def test_check_case_reports_full_estimate_with_series_reserve():
    v1_report = check_case(_basic_spec())
    assert v1_report["memory_limit_mb"] == 1024
    assert v1_report["series_reserve_mb"] == 64
    assert v1_report["estimated_peak_with_series_mb"] == pytest.approx(v1_report["estimated_peak_mb"] + 64)

    v2_report = check_case(_neutral_external_spec())
    assert v2_report["memory_limit_mb"] == 1024
    assert v2_report["series_reserve_mb"] == 512
    assert v2_report["estimated_peak_with_series_mb"] == pytest.approx(v2_report["estimated_peak_mb"] + 512)


def test_budget_refusal_messages_name_budget_and_settings():
    from hawa.cases import CASES
    example_name = next(iter(CASES))
    with pytest.raises(ValueError) as exc_example:
        check_case({"example": example_name, "size": 128, "memory_limit_mb": 1})
    msg = str(exc_example.value)
    assert "1 MiB" in msg
    assert "case memory budget" in msg
    assert "memory_limit_mb" in msg

    with pytest.raises(ValueError) as exc_case:
        check_case(_basic_spec(shape=(40, 40, 40), memory_limit_mb=10))
    msg = str(exc_case.value)
    assert "10 MiB" in msg
    assert "case budget" in msg
    assert "dx" in msg
    assert "memory_limit_mb" in msg

    coarse = _basic_spec(shape=(20, 20, 20), memory_limit_mb=8)
    fine = _basic_spec(shape=(20, 20, 20), memory_limit_mb=8)
    fine["dx"] = 0.05
    fine["refinement_lower"] = [4, 4, 4]
    fine["refinement_upper"] = [13, 13, 13]
    fine["origin"] = [0.4, 0.4, 0.4]
    with pytest.raises(ValueError) as exc_ref:
        check_refinement({"case": coarse, "fine_case": fine, "steps": 10})
    msg = str(exc_ref.value)
    assert "8 MiB" in msg
    assert "Combined coarse/fine memory" in msg
    assert "memory_limit_mb" in msg


def test_capture_refuses_over_budget_before_reading_manifest(tmp_path):
    missing_manifest = tmp_path / "never_opened_manifest.json"
    out_v1 = tmp_path / "v1.npz"
    spec_v1 = _basic_spec(shape=(10, 10, 10), memory_limit_mb=32)
    with pytest.raises(ValueError) as exc_v1:
        capture_v1(missing_manifest, spec_v1, out_v1)
    assert "64 MiB boundary series reserve" in str(exc_v1.value)
    assert "32 MiB case budget" in str(exc_v1.value)
    assert "memory_limit_mb" in str(exc_v1.value)

    out_v2 = tmp_path / "v2.npz"
    spec_v2 = _neutral_external_spec(shape=(12, 12, 12), memory_limit_mb=256)
    with pytest.raises(ValueError) as exc_v2:
        capture_v2(missing_manifest, spec_v2, out_v2)
    assert "512 MiB boundary series reserve" in str(exc_v2.value)
    assert "256 MiB case budget" in str(exc_v2.value)
    assert "memory_limit_mb" in str(exc_v2.value)

    # Already-attached spec does not double-count reserve
    spec_ok = _basic_spec(shape=(8, 6, 6), memory_limit_mb=1024)
    assert check_capture_budget(spec_ok, 64)["valid"] is True


def test_validate_new_output_file_and_dir_reject_bad_paths_cleanly(tmp_path):
    with pytest.raises(ValueError, match="Choose an output file path"):
        validate_new_output_file("   ")

    existing = tmp_path / "exists.npz"
    existing.write_bytes(b"data")
    with pytest.raises(ValueError, match="Output file already exists"):
        validate_new_output_file(existing)

    missing_dir = tmp_path / "no_such_dir" / "out.npz"
    with pytest.raises(ValueError, match="Output folder does not exist"):
        validate_new_output_file(missing_dir)

    ro_dir = tmp_path / "readonly"
    ro_dir.mkdir()
    ro_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        if not os.access(str(ro_dir), os.W_OK):
            with pytest.raises(ValueError, match="Output folder is not writable"):
                validate_new_output_file(ro_dir / "out.npz")
            with pytest.raises(ValueError, match="Output folder parent is not writable"):
                validate_new_output_dir(ro_dir / "nested" / "run_dir")
    finally:
        ro_dir.chmod(stat.S_IRWXU)

    with pytest.raises(ValueError, match="Choose an output folder path"):
        validate_new_output_dir("")

    existing_dir = tmp_path / "existing_dir"
    existing_dir.mkdir()
    with pytest.raises(ValueError, match="Output folder already exists"):
        validate_new_output_dir(existing_dir)

    valid_file = tmp_path / "fresh.npz"
    assert validate_new_output_file(valid_file) == valid_file
    valid_dir = tmp_path / "fresh_dir"
    assert validate_new_output_dir(valid_dir) == valid_dir.resolve()


def test_dispatch_job_rejects_bad_output_paths_before_starting(tmp_path):
    existing_dir = tmp_path / "taken_run"
    existing_dir.mkdir()
    with pytest.raises(ValueError, match="Output folder already exists"):
        dispatch_job({
            "op": "evaluate_submit",
            "kind": "record",
            "case": _basic_spec(),
            "steps": 10,
            "interval": 5,
            "directory": str(existing_dir),
        })

    existing_file = tmp_path / "taken.npz"
    existing_file.write_bytes(b"x")
    with pytest.raises(ValueError, match="Output file already exists"):
        dispatch_job({
            "op": "evaluate_submit",
            "kind": "query",
            "request": {
                "op": "boundary",
                "action": "capture",
                "manifest": str(tmp_path / "m.json"),
                "case": _basic_spec(),
                "path": str(existing_file),
            },
        })

    # Over-budget capture is also rejected before job creation
    with pytest.raises(ValueError, match="512 MiB boundary series reserve"):
        preflight_job({
            "kind": "query",
            "request": {
                "op": "boundary",
                "action": "capture",
                "case": _neutral_external_spec(memory_limit_mb=256),
                "path": str(tmp_path / "new.npz"),
            },
        })


def test_flush_inlet_pressure_refusal_includes_actionable_t0_hint():
    from hawa.boundary_data import grid_key
    from hawa.boundary_series import active_faces, geometry_key, layout

    spec = _neutral_external_spec(shape=(6, 6, 6))
    faces = active_faces(spec)
    indices, _ = layout(spec, faces)
    m = len(indices)
    arrays = {
        "velocity": np.zeros((2, 3, m), dtype=np.float32),
        "initial_velocity": np.zeros((3, 6, 6, 6), dtype=np.float32),
        "pressure": np.full((2, m), 1e6, dtype=np.float32),
        "initial_pressure": np.zeros((6, 6, 6), dtype=np.float32),
    }
    meta = {
        "grid": grid_key(spec),
        "child_geometry_sha256": geometry_key(spec),
        "faces": faces,
    }
    with pytest.raises(ValueError) as exc:
        validate_attachment(spec, arrays, meta)
    msg = str(exc.value)
    assert "Imported pressure exceeds 2% density budget" in msg
    assert "Start time (T0)" in msg
    assert "startup transient" in msg


def test_capture_preflight_never_compiles_grid_links(tmp_path, monkeypatch):
    from hawa import neutral_external, boundaries
    def forbidden(*args, **kwargs):
        raise AssertionError('full-grid boundary compilation reached submit')
    monkeypatch.setattr(neutral_external, 'compile_links', forbidden)
    monkeypatch.setattr(boundaries, 'compile_plan', forbidden)
    spec = _neutral_external_spec()
    preflight_job(dict(kind='query', request=dict(op='boundary', action='capture',
                  case=spec, path=str(tmp_path/'new.npz'))))
    report = check_capture_budget(spec, 512)
    assert report['boundary_plan'] is None
    assert report['estimated_boundary_preparation_mb'] > 0
    with pytest.raises(ValueError, match='512 MiB boundary series reserve'):
        check_capture_budget(_neutral_external_spec(memory_limit_mb=256), 512)
    # General NEE cases also skip compilation during admission.
    from test_general_boundaries import channel
    general = channel()
    assert check_capture_budget(general, 64)['boundary_plan'] is None
    # Full check remains the default outside capture admission.
    with pytest.raises(AssertionError, match='full-grid'):
        check_case(spec)


def test_dangling_output_link_is_refused_before_capture(tmp_path):
    target = tmp_path/'dangling.npz'
    target.symlink_to(tmp_path/'absent.npz')
    for capture, spec in ((capture_v1, _basic_spec()), (capture_v2, _neutral_external_spec())):
        with pytest.raises(ValueError, match='Output file already exists'):
            capture(tmp_path/'missing_manifest.json', spec, target)
    assert target.is_symlink() and not target.exists()


@pytest.mark.parametrize('version', [1, 2])
def test_capture_uses_expanded_home_path(tmp_path, monkeypatch, version):
    monkeypatch.setenv('HOME', str(tmp_path))
    if version == 1:
        from test_boundary_data import case
        from hawa.plugin import Session
        from hawa.recording import record
        spec = case()
        record(Session(spec, 'cpu'), 5, 5, str(tmp_path/'parent'), lambda n: None)
        manifest = tmp_path/'parent/manifest.json'
        capture = capture_v1
    else:
        from test_boundary_series import case, recording
        spec = case()
        manifest = recording(tmp_path/'parent', spec)
        capture = capture_v2
    result = capture(manifest, spec, '~/capture.npz')
    assert (tmp_path/'capture.npz').is_file()
    assert Path(result['case']['boundary_field']['path']) == tmp_path/'capture.npz'


@pytest.mark.parametrize('version', [1, 2])
def test_capture_full_validation_precedes_parent_reads(tmp_path, monkeypatch, version):
    from hawa import boundaries, neutral_external, recording
    from test_general_boundaries import channel
    capture, spec, module, compiler = ((capture_v1, channel(), boundaries, 'compile_plan')
        if version == 1 else (capture_v2, _neutral_external_spec(), neutral_external, 'compile_links'))
    calls = []
    def rejected(spec):
        calls.append('compile')
        raise ValueError('unsupported worker boundary configuration')
    def forbidden(*args):
        raise AssertionError('parent data read before full validation')
    monkeypatch.setattr(module, compiler, rejected)
    monkeypatch.setattr(recording, 'read_manifest', forbidden)
    with pytest.raises(ValueError, match='unsupported worker boundary configuration'):
        capture(tmp_path/'absent.json', spec, tmp_path/'new.npz')
    assert calls == ['compile'] and not (tmp_path/'new.npz').exists()
