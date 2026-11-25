"""Unit, contract, and adverse tests for OpenFOAM handoff and comparison (#126, #127)."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest

from hawa import openfoam

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _valid_3d_bundle():
    return {
        "schema": openfoam.SCHEMA,
        "case_id": "box_3d_slip",
        "description": "3D channel with uniform inlet, pressure outlet, slip, and cyclic sides",
        "dimensions": 3,
        "domain_origin_m": [0.0, 0.0, 0.0],
        "domain_size_m": [2.0, 1.0, 1.0],
        "density_kg_m3": 1.225,
        "kinematic_viscosity_m2_s": 0.02,
        "reference_speed_m_s": 1.0,
        "reference_length_m": 1.0,
        "initial_velocity_m_s": [0.5, 0.0, 0.0],
        "pressure_reference_pa": 0.0,
        "boundaries": [
            {"id": "inlet", "face": "x-", "condition": {"type": "velocity", "velocity": [1.0, 0.0, 0.0]}},
            {"id": "outlet", "face": "x+", "condition": {"type": "pressure", "pressure_pa": 0.0}},
            {"id": "bottom", "face": "y-", "condition": {"type": "wall", "velocity": [0.0, 0.0, 0.0]}},
            {"id": "top", "face": "y+", "condition": {"type": "slip"}},
            {"id": "back", "face": "z-", "condition": {"type": "periodic"}},
            {"id": "front", "face": "z+", "condition": {"type": "periodic"}},
        ],
        "probes": [
            {"id": "p1", "location_m": [0.5, 0.5, 0.5]},
            {"id": "p2", "location_m": [1.5, 0.5, 0.5]},
        ],
        "pressure_pairs": [{"id": "dp", "a_probe_id": "p1", "b_probe_id": "p2"}],
        "mesh": {"cells": [8, 4, 4], "solver": "icoFoam", "max_iterations": 10, "delta_t": 0.01},
        "provenance": {"source": "unit-test"},
    }


def test_control_case_builders_and_schema_validation():
    spec, ch_bundle, analytic = openfoam.channel_poiseuille_case(ny_cells=10)
    assert ch_bundle["schema"] == openfoam.SCHEMA
    assert ch_bundle["domain_size_m"][0] == pytest.approx(4.0)
    assert ch_bundle["domain_size_m"][1] == pytest.approx(1.0)
    assert analytic["dp_dx_pa_m"] == pytest.approx(-8.0 * 1.225 * 0.025 * 0.5)
    assert analytic["probes"]["p_x2_mid"]["velocity_m_s"][0] == pytest.approx(0.5)
    assert spec["dx"] == pytest.approx(0.1)

    cav_cfg, cav_bundle = openfoam.cavity_control_case(n=32, reynolds=10.0, mach=0.05)
    assert cav_cfg == {"resolution": 32, "reynolds_number": 10.0, "mach_number": 0.05}
    assert cav_bundle["mesh"]["p_ref_cell"] == 0

    with pytest.raises(ValueError, match="ny_cells"):
        openfoam.channel_poiseuille_case(ny_cells=4)
    with pytest.raises(ValueError, match="integer multiple"):
        openfoam.channel_poiseuille_case(ny_cells=10, lx=4.03, ly=1.0)
    with pytest.raises(ValueError, match="n must be"):
        openfoam.cavity_control_case(n=8)
    with pytest.raises(ValueError, match="positive"):
        openfoam.cavity_control_case(n=32, reynolds=0.0)


def test_schema_rejections_cover_all_contract_invariants():
    _, base, _ = openfoam.channel_poiseuille_case(ny_cells=10)

    bad_schema = copy.deepcopy(base)
    bad_schema["schema"] = "hawa-openfoam-case-99"
    with pytest.raises(ValueError, match="schema"):
        openfoam.validate_bundle(bad_schema)

    extra = copy.deepcopy(base)
    extra["unexpected"] = 1
    with pytest.raises(ValueError, match="Extra inputs"):
        openfoam.validate_bundle(extra)

    bad_periodic = copy.deepcopy(base)
    bad_periodic["boundaries"][5]["condition"] = {"type": "slip"}
    with pytest.raises(ValueError, match="opposite-face pairs"):
        openfoam.validate_bundle(bad_periodic)

    bad_2d_z = copy.deepcopy(base)
    bad_2d_z["mesh"]["cells"] = [40, 10, 2]
    with pytest.raises(ValueError, match="exactly 1 cell"):
        openfoam.validate_bundle(bad_2d_z)

    bad_2d_faces = copy.deepcopy(base)
    bad_2d_faces["boundaries"][4]["condition"] = {"type": "slip"}
    bad_2d_faces["boundaries"][5]["condition"] = {"type": "slip"}
    with pytest.raises(ValueError, match="periodic z- and z\\+"):
        openfoam.validate_bundle(bad_2d_faces)

    no_pressure = copy.deepcopy(base)
    no_pressure["boundaries"][1]["condition"] = {"type": "wall", "velocity": [0.0, 0.0, 0.0]}
    with pytest.raises(ValueError, match="pressure reference"):
        openfoam.validate_bundle(no_pressure)

    _, cav = openfoam.cavity_control_case(n=32)
    no_pref = copy.deepcopy(cav)
    no_pref["mesh"]["p_ref_cell"] = None
    with pytest.raises(ValueError, match="p_ref_cell"):
        openfoam.validate_bundle(no_pref)

    dup_probe = copy.deepcopy(base)
    dup_probe["probes"].append(copy.deepcopy(dup_probe["probes"][0]))
    with pytest.raises(ValueError, match="Duplicate probe"):
        openfoam.validate_bundle(dup_probe)

    oob_probe = copy.deepcopy(base)
    oob_probe["probes"][0]["location_m"] = [4.0, 0.5, 0.15]
    with pytest.raises(ValueError, match="strictly inside"):
        openfoam.validate_bundle(oob_probe)

    dup_pair = copy.deepcopy(base)
    dup_pair["pressure_pairs"].append(copy.deepcopy(dup_pair["pressure_pairs"][0]))
    with pytest.raises(ValueError, match="Duplicate pressure pair"):
        openfoam.validate_bundle(dup_pair)

    unk_pair = copy.deepcopy(base)
    unk_pair["pressure_pairs"][0]["b_probe_id"] = "missing"
    with pytest.raises(ValueError, match="unknown probe"):
        openfoam.validate_bundle(unk_pair)

    zero_dist = copy.deepcopy(base)
    zero_dist["pressure_pairs"][0]["b_probe_id"] = zero_dist["pressure_pairs"][0]["a_probe_id"]
    with pytest.raises(ValueError, match="distinct locations"):
        openfoam.validate_bundle(zero_dist)


def test_bundle_from_hawa_spec_rejects_unsupported_features():
    spec, base, _ = openfoam.channel_poiseuille_case(ny_cells=10)
    with pytest.raises(ValueError, match="dictionary"):
        openfoam.bundle_from_hawa_spec("x", "d", "not-a-dict", base["probes"], [], base["mesh"])

    for key in openfoam._UNSUPPORTED_SPEC_KEYS:
        bad = copy.deepcopy(spec)
        bad[key] = [1] if key in ("solid", "moving_bodies", "wall_links") else True
        with pytest.raises(ValueError, match="Unsupported Hawa feature: " + key if False else key):
            openfoam.bundle_from_hawa_spec("x", "d", bad, base["probes"], [], base["mesh"])

    no_bset = copy.deepcopy(spec)
    del no_bset["boundary_set"]
    with pytest.raises(ValueError, match="boundary_set"):
        openfoam.bundle_from_hawa_spec("x", "d", no_bset, base["probes"], [], base["mesh"])

    bad_shape = copy.deepcopy(spec)
    bad_shape["shape"] = [2, 10, 4]
    with pytest.raises(ValueError, match="3-integer shape"):
        openfoam.bundle_from_hawa_spec("x", "d", bad_shape, base["probes"], [], base["mesh"])

    bad_dx = copy.deepcopy(spec)
    bad_dx["dx"] = float("nan")
    with pytest.raises(ValueError, match="positive dx"):
        openfoam.bundle_from_hawa_spec("x", "d", bad_dx, base["probes"], [], base["mesh"])

    open_face = copy.deepcopy(spec)
    open_face["boundary_set"]["patches"][1]["condition"] = {"type": "open", "pressure_pa": 0.0}
    with pytest.raises(ValueError, match="Open boundary"):
        openfoam.bundle_from_hawa_spec("x", "d", open_face, base["probes"], [], base["mesh"])

    mapped = copy.deepcopy(spec)
    mapped["boundary_set"]["patches"][0]["condition"]["profile"] = "mapped"
    with pytest.raises(ValueError, match="Mapped and neutral"):
        openfoam.bundle_from_hawa_spec("x", "d", mapped, base["probes"], [], base["mesh"])


def test_parabolic_centers_and_atomic_write_publish_and_rollback(tmp_path, monkeypatch):
    # Cover all three face pairs for blockMesh face-center helper
    assert len(openfoam._blockmesh_patch_face_centers([0, 0, 0], [2, 1, 1], [4, 3, 2], "x-")) == 6
    assert len(openfoam._blockmesh_patch_face_centers([0, 0, 0], [2, 1, 1], [4, 3, 2], "y+")) == 8
    assert len(openfoam._blockmesh_patch_face_centers([0, 0, 0], [2, 1, 1], [4, 3, 2], "z-")) == 12

    # 3D slip + cyclic + uniform velocity + icoFoam rendering
    b3 = _valid_3d_bundle()
    d3 = tmp_path / "case3d"
    pub3 = openfoam.write_openfoam_case(b3, d3)
    assert "type cyclic;" in (d3 / "openfoam" / "system" / "blockMeshDict").read_text()
    assert "type            slip;" in (d3 / "openfoam" / "0" / "U").read_text()
    assert "default         Euler;" in (d3 / "openfoam" / "system" / "fvSchemes").read_text()
    assert len(pub3["manifest"]["files"]) == 10

    # 2D channel parabolic + atomic overwrite/protection checks
    _, ch, _ = openfoam.channel_poiseuille_case(ny_cells=10)
    dest = tmp_path / "channel"
    pub = openfoam.write_openfoam_case(ch, dest)
    u_txt = (dest / "openfoam" / "0" / "U").read_text()
    assert "nonuniform List<vector>" in u_txt
    assert "exprFixedValue" not in u_txt
    # Verify manifest hashes match actual files
    for rel, expected_sha in pub["manifest"]["files"].items():
        actual_sha = hashlib.sha256((dest / rel).read_bytes()).hexdigest()
        assert actual_sha == expected_sha

    with pytest.raises(FileExistsError):
        openfoam.write_openfoam_case(ch, dest, overwrite=False)

    # Marker preserved on failed overwrite rollback
    marker = dest / "keep.txt"
    marker.write_text("original", encoding="utf-8")
    real_replace = openfoam.os.replace
    calls = {"n": 0}

    def fail_second_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated atomic swap failure")
        return real_replace(src, dst)

    monkeypatch.setattr(openfoam.os, "replace", fail_second_replace)
    with pytest.raises(OSError, match="simulated atomic swap failure"):
        openfoam.write_openfoam_case(ch, dest, overwrite=True)
    assert marker.read_text(encoding="utf-8") == "original"
    assert not list(tmp_path.glob(".hawa-openfoam-*"))

    monkeypatch.setattr(openfoam.os, "replace", real_replace)
    openfoam.write_openfoam_case(ch, dest, overwrite=True)
    assert not marker.exists()

    # Also test cavity moving wall rendering
    _, cav = openfoam.cavity_control_case(n=16)
    cav_dir = tmp_path / "cavity"
    openfoam.write_openfoam_case(cav, cav_dir)
    assert "value           uniform (1 0 0);" in (cav_dir / "openfoam" / "0" / "U").read_text()
    assert "pRefCell        0;" in (cav_dir / "openfoam" / "system" / "fvSolution").read_text()


def test_detect_openfoam_parsers_and_mocked_runner(tmp_path, monkeypatch):
    # Default runner smoke via python echo
    rc, out, _ = openfoam._default_runner([sys.executable, "-c", "print('ok')"], 10)
    assert rc == 0 and out.strip() == "ok"

    # Missing launcher on PATH
    monkeypatch.setattr(openfoam.shutil, "which", lambda name: None)
    missing = openfoam.detect_openfoam()
    assert missing["available"] is False

    # Failing launcher
    failed = openfoam.detect_openfoam(launcher="/fake/of", runner=lambda cmd, t: (2, "", "boom"))
    assert failed["available"] is False and "boom" in failed["reason"]

    # Partial tools
    partial = openfoam.detect_openfoam(
        launcher="/fake/of",
        runner=lambda cmd, t: (0, "VERSION=v2606\nOPTIONS=darwin\nTOOL:blockMesh=/bin/bm\n", ""),
    )
    assert partial["available"] is False and "checkMesh" in partial["missing_tools"]

    # Valid checkMesh parsing & error paths
    ok_cm = "    cells:            400\n    Overall domain bounding box (0 0 0) (4 1 0.3)\nMesh OK.\n"
    parsed = openfoam.parse_check_mesh(ok_cm, [0, 0, 0], [4, 1, 0.3])
    assert parsed["cells"] == 400 and parsed["mesh_ok"] is True

    with pytest.raises(ValueError, match="missing cell count"):
        openfoam.parse_check_mesh("Mesh OK.", [0, 0, 0], [1, 1, 1])
    with pytest.raises(ValueError, match="Malformed"):
        openfoam.parse_check_mesh("cells: 1\nOverall domain bounding box (0 0) (1 1)\nMesh OK.", [0, 0, 0], [1, 1, 1])
    with pytest.raises(ValueError, match="did not report Mesh OK"):
        openfoam.parse_check_mesh("cells: 1\nOverall domain bounding box (0 0 0) (1 1 1)\nFailed.", [0, 0, 0], [1, 1, 1])
    with pytest.raises(ValueError, match="does not match contract"):
        openfoam.parse_check_mesh(ok_cm, [0, 0, 0], [2, 1, 0.3])

    # Probe parsers
    t_s, vals_s = openfoam.parse_probes_scalar("# header\n10 1.5 2.5\n20 3.0 4.0\n", 2)
    assert t_s == 20.0 and vals_s == [3.0, 4.0]
    with pytest.raises(ValueError, match="no data rows"):
        openfoam.parse_probes_scalar("# only comments\n", 1)
    with pytest.raises(ValueError, match="Expected 2"):
        openfoam.parse_probes_scalar("10 1.0\n", 2)
    with pytest.raises(ValueError, match="Non-finite"):
        openfoam.parse_probes_scalar("10 nan 1.0\n", 2)

    t_v, vals_v = openfoam.parse_probes_vector("# h\n20 (1 2 3) (4 5 6)\n", 2)
    assert t_v == 20.0 and vals_v == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    with pytest.raises(ValueError, match="no data rows"):
        openfoam.parse_probes_vector("# comment\n", 1)
    with pytest.raises(ValueError, match="Malformed"):
        openfoam.parse_probes_vector("   onlytime\n", 1)
    with pytest.raises(ValueError, match="Expected 2"):
        openfoam.parse_probes_vector("20 (1 2 3)\n", 2)
    with pytest.raises(ValueError, match="Malformed or non-finite"):
        openfoam.parse_probes_vector("20 (1 2)\n", 1)
    with pytest.raises(ValueError, match="Non-finite time"):
        openfoam.parse_probes_vector("nan (1 2 3)\n", 1)

    # Full run_openfoam_case mocked
    _, ch, _ = openfoam.channel_poiseuille_case(ny_cells=10)
    pub = openfoam.write_openfoam_case(ch, tmp_path / "run_case")
    cdir = Path(pub["openfoam_dir"])

    with pytest.raises(RuntimeError, match="OpenFOAM unavailable"):
        openfoam.run_openfoam_case(cdir, ch, launcher="/fake/of", runner=lambda c, t: (1, "", "no"))

    def make_runner(fail_step=None, write_probes=True):
        def _run(cmd, timeout_s):
            script = cmd[-1]
            if "TOOL:blockMesh" in script:
                out = "VERSION=v2606\nOPTIONS=darwin\n" + "\n".join(
                    f"TOOL:{t}=/bin/{t}" for t in openfoam._REQUIRED_TOOLS
                )
                return 0, out, ""
            if fail_step and fail_step in script:
                return 1, "", "step failed"
            if "checkMesh" in script:
                return 0, "cells: 400\nOverall domain bounding box (0 0 0) (4 1 0.3)\nMesh OK.\n", ""
            if "simpleFoam" in script:
                return 0, "SIMPLE solution converged in 50 iterations\n", ""
            if "postProcess" in script and write_probes:
                pdir = cdir / "postProcessing" / "probes" / "0"
                pdir.mkdir(parents=True, exist_ok=True)
                p_vals = " ".join(str(0.1 * (7 - i)) for i in range(7))
                u_vals = " ".join("(0.5 0 0)" for _ in range(7))
                (pdir / "p").write_text(f"# header\n50 {p_vals}\n", encoding="utf-8")
                (pdir / "U").write_text(f"# header\n50 {u_vals}\n", encoding="utf-8")
            return 0, "ok", ""
        return _run

    with pytest.raises(RuntimeError, match="simpleFoam failed"):
        openfoam.run_openfoam_case(cdir, ch, launcher="/fake/of", runner=make_runner(fail_step="simpleFoam"))
    openfoam.write_openfoam_case(ch, tmp_path / "run_case", overwrite=True)
    with pytest.raises(RuntimeError, match="did not write probe files"):
        openfoam.run_openfoam_case(cdir, ch, launcher="/fake/of", runner=make_runner(write_probes=False))

    openfoam.write_openfoam_case(ch, tmp_path / "run_case", overwrite=True)
    res = openfoam.run_openfoam_case(cdir, ch, launcher="/fake/of", runner=make_runner())
    assert res["converged"] is True
    assert res["probes"]["p_x1_mid"]["pressure_pa"] == pytest.approx(0.7 * 1.225)
    assert res["pressure_pairs"]["dp_x1_x3"]["delta_p_pa"] == pytest.approx(0.2 * 1.225)


def test_sample_regular_grid_and_compare_probe_results():
    # 2D exact bilinear test
    ax = np.linspace(0.0, 1.0, 5)
    X, Y = np.meshgrid(ax, ax, indexing="ij")
    u2 = np.stack([2.0 * X + Y, -X + 3.0 * Y], axis=0)
    p2 = 4.0 * X - 2.0 * Y
    vals = openfoam.sample_regular_grid(u2, p2, [ax, ax], [[0.35, 0.65, 0.0]])
    assert vals[0][0] == pytest.approx([2.0 * 0.35 + 0.65, -0.35 + 3.0 * 0.65, 0.0])
    assert vals[0][1] == pytest.approx(4.0 * 0.35 - 2.0 * 0.65)

    # 3D exact trilinear test
    X3, Y3, Z3 = np.meshgrid(ax, ax, ax, indexing="ij")
    u3 = np.stack([X3, Y3, Z3], axis=0)
    p3 = X3 + 2.0 * Y3 + 3.0 * Z3
    vals3 = openfoam.sample_regular_grid(u3, p3, [ax, ax, ax], [[0.2, 0.4, 0.8]])
    assert vals3[0][0] == pytest.approx([0.2, 0.4, 0.8])
    assert vals3[0][1] == pytest.approx(0.2 + 0.8 + 2.4)

    # Rejections
    with pytest.raises(ValueError, match="dimensions must match"):
        openfoam.sample_regular_grid(u2, p3, [ax, ax], [[0.5, 0.5]])
    with pytest.raises(ValueError, match="strictly increasing"):
        openfoam.sample_regular_grid(u2, p2, [ax[::-1], ax], [[0.5, 0.5]])
    with pytest.raises(ValueError, match="Solid mask"):
        openfoam.sample_regular_grid(u2, p2, [ax, ax], [[0.5, 0.5]], solid=np.zeros((2, 2), dtype=bool))
    with pytest.raises(ValueError, match="outside Hawa grid"):
        openfoam.sample_regular_grid(u2, p2, [ax, ax], [[1.5, 0.5]])
    solid = np.zeros_like(p2, dtype=bool)
    solid[2, 2] = True
    with pytest.raises(ValueError, match="touches solid"):
        openfoam.sample_regular_grid(u2, p2, [ax, ax], [[0.5, 0.5]], solid=solid)
    p_nan = p2.copy()
    p_nan[1, 1] = float("nan")
    with pytest.raises(ValueError, match="Non-finite"):
        openfoam.sample_regular_grid(u2, p_nan, [ax, ax], [[0.25, 0.25]])

    # Comparator tests
    _, ch, analytic = openfoam.channel_poiseuille_case(ny_cells=10)
    of_like = {"probes": analytic["probes"], "pressure_pairs": analytic["pressure_pairs"]}
    hawa_good = copy.deepcopy(of_like)
    ok = openfoam.compare_probe_results(ch, hawa_good, of_like, analytic=analytic, velocity_tol=0.01, pressure_tol=0.01)
    assert ok["passed"] is True and ok["velocity_linf_norm"] == 0.0

    hawa_bad = copy.deepcopy(of_like)
    hawa_bad["probes"]["p_x1_mid"]["velocity_m_s"] = [0.0, 0.0, 0.0]
    hawa_bad["pressure_pairs"]["dp_x1_x3"]["delta_p_pa"] = 99.0
    bad = openfoam.compare_probe_results(ch, hawa_bad, of_like, analytic=analytic, velocity_tol=0.01, pressure_tol=0.01)
    assert bad["passed"] is False and len(bad["failures"]) == 2

    missing_probe = copy.deepcopy(of_like)
    del missing_probe["probes"]["p_x1_mid"]
    with pytest.raises(ValueError, match="Missing required probe"):
        openfoam.compare_probe_results(ch, missing_probe, of_like)

    missing_pair = copy.deepcopy(of_like)
    del missing_pair["pressure_pairs"]["dp_x1_x3"]
    with pytest.raises(ValueError, match="Missing required pressure pair"):
        openfoam.compare_probe_results(ch, missing_pair, of_like)


def test_hawa_control_runners_and_cli_script(tmp_path, monkeypatch):
    import compare_openfoam_controls as cli

    # Real bounded Hawa channel & cavity runs (fast, deterministic CPU)
    spec, ch_bundle, analytic = openfoam.channel_poiseuille_case(ny_cells=8)
    ch_res = openfoam.run_hawa_channel(spec, ch_bundle, device="cpu", max_steps=40, check_interval=20, settle_tol=1e6)
    assert ch_res["settled"] is True and ch_res["steps"] == 40
    assert math.isfinite(ch_res["probes"]["p_x2_mid"]["velocity_m_s"][0])
    ch_unsettled = openfoam.run_hawa_channel(spec, ch_bundle, device="cpu", max_steps=20, check_interval=10, settle_tol=1e-12)
    assert ch_unsettled["settled"] is False and ch_unsettled["steps"] == 20

    cav_cfg, cav_bundle = openfoam.cavity_control_case(n=16, reynolds=10.0, mach=0.05)
    cav_res = openfoam.run_hawa_cavity(cav_cfg, cav_bundle, device="cpu", dtype="float32", target_time_s=0.05)
    assert cav_res["steps"] >= 1 and math.isfinite(cav_res["probes"]["c_50_50"]["velocity_m_s"][0])

    # Cover MPS dtype branch & non-finite check via monkeypatch
    class _FakeDev:
        type = "mps"

    class _FakeBackend:
        device = _FakeDev()

        def info(self):
            return {"selected": "mps"}

        def synchronize(self):
            return None

    import lettuce as lt
    import torch

    orig_ctx = lt.Context
    monkeypatch.setattr("hawa.backends.select_backend", lambda d: _FakeBackend())
    monkeypatch.setattr(lt, "Context", lambda dev, dtype, use_native=False: orig_ctx(torch.device("cpu"), dtype, use_native=False))
    cav_mps_mock = openfoam.run_hawa_cavity(cav_cfg, cav_bundle, device="mps", dtype="float64", target_time_s=0.02)
    assert cav_mps_mock["dtype"] == "torch.float32"

    # Non-finite Cavity2D failure guard
    class _NanFlow:
        units = type("U", (), {"relaxation_parameter_lu": 0.6, "convert_time_to_pu": lambda self, s: 0.01 * s})()
        u_pu = torch.full((2, 16, 16), float("nan"))
        p_pu = torch.zeros((1, 16, 16))

    monkeypatch.setattr(lt, "Cavity2D", lambda *a, **k: _NanFlow())
    monkeypatch.setattr(lt, "BGKCollision", lambda tau: None)
    monkeypatch.setattr(lt, "Simulation", lambda **k: (lambda steps: None))
    with pytest.raises(RuntimeError, match="non-finite"):
        openfoam.run_hawa_cavity(cav_cfg, cav_bundle, device="cpu", target_time_s=0.02)
    monkeypatch.undo()

    # Provenance itself is exercised against a real temporary repository below.
    monkeypatch.setattr(cli, "git_provenance", lambda root: {"commit": "test", "dirty": False})
    # CLI blocked when OpenFOAM absent
    monkeypatch.setattr(openfoam.shutil, "which", lambda name: None)
    rep_blocked = tmp_path / "blocked.json"
    rc = cli.main(["--output-dir", str(tmp_path / "out_b"), "--report", str(rep_blocked)])
    assert rc == 1
    assert json.loads(rep_blocked.read_text())["status"] == "BLOCKED"

    # CLI completed with mocked OpenFOAM runner
    def _mock_of(cmd, timeout_s):
        script = cmd[-1]
        if "TOOL:blockMesh" in script:
            return 0, "VERSION=v2606\nOPTIONS=darwin\n" + "\n".join(
                f"TOOL:{t}=/bin/{t}" for t in openfoam._REQUIRED_TOOLS
            ), ""
        if "checkMesh" in script:
            if "cavity" in script:
                return 0, "cells: 256\nOverall domain bounding box (0 0 0) (1 1 0.1)\nMesh OK.\n", ""
            return 0, "cells: 256\nOverall domain bounding box (0 0 0) (4 1 0.375)\nMesh OK.\n", ""
        if "simpleFoam" in script:
            return 0, "SIMPLE solution converged in 20 iterations\n", ""
        if "postProcess" in script:
            # Extract case dir from `cd '<dir>' && ...`
            cdir = Path(script.split("cd ", 1)[1].split(" &&", 1)[0].strip("'\""))
            pdir = cdir / "postProcessing" / "probes" / "0"
            pdir.mkdir(parents=True, exist_ok=True)
            if "cavity" in str(cdir):
                (pdir / "p").write_text("# h\n20 0 0 0 0 0 0 0\n", encoding="utf-8")
                (pdir / "U").write_text("# h\n20 " + " ".join("(0 0 0)" for _ in range(7)) + "\n", encoding="utf-8")
            else:
                p_vals = " ".join(str(analytic["probes"][p["id"]]["pressure_pa"] / 1.225) for p in ch_bundle["probes"])
                u_vals = " ".join(
                    f"({analytic['probes'][p['id']]['velocity_m_s'][0]} 0 0)" for p in ch_bundle["probes"]
                )
                (pdir / "p").write_text(f"# h\n20 {p_vals}\n", encoding="utf-8")
                (pdir / "U").write_text(f"# h\n20 {u_vals}\n", encoding="utf-8")
        return 0, "ok", ""

    monkeypatch.setattr(cli, "run_hawa_channel", lambda spec, b, **kw: {
        "device": "cpu", "dtype": "torch.float32", "steps": 20, "physical_time_s": 0.1,
        "tau": 0.6, "settled": True, "final_drift": 0.0, "relative_mass_change": 0.0,
        "probes": analytic["probes"], "pressure_pairs": analytic["pressure_pairs"],
    })
    suite = cli.run_control_suite(
        tmp_path / "out_ok",
        channel_grids=(8,),
        cavity_configs=((16, 0.05),),
        launcher="/fake/of",
        runner=_mock_of,
        channel_max_steps=40,
        cavity_target_time_s=0.05,
    )
    assert suite["status"] == "COMPLETED"
    assert len(suite["channel_cases"]) == 1 and len(suite["cavity_cases"]) == 1

    # Also exercise main() happy path and __main__ entrypoint
    monkeypatch.setattr(cli, "run_control_suite", lambda *a, **k: suite)
    rep_ok = tmp_path / "ok.json"
    assert cli.main(["--output-dir", str(tmp_path / "o"), "--report", str(rep_ok)]) == 0
    assert json.loads(rep_ok.read_text())["status"] == "COMPLETED"

    import runpy
    monkeypatch.setattr(openfoam.shutil, "which", lambda name: None)
    monkeypatch.setattr(sys, "argv", ["compare_openfoam_controls.py", "--output-dir", str(tmp_path / "m"),
                                      "--report", str(tmp_path / "m_rep.json")])
    cleaned_path = [p for p in sys.path if p != str(ROOT / "src")]
    monkeypatch.setattr(sys, "path", cleaned_path)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / "scripts" / "compare_openfoam_controls.py"), run_name="__main__")
    assert exc.value.code == 1


@pytest.mark.parametrize('collision', ['smagorinsky', 'smagorinsky-v1', 'shifted-regularized-sgs-v1', 'unknown'])
def test_handoff_rejects_nonlaminar_models(collision):
    spec, bundle, _ = openfoam.channel_poiseuille_case(10)
    spec['collision'] = collision
    with pytest.raises(ValueError, match='laminar collision'):
        openfoam.bundle_from_hawa_spec('x', 'test', spec, bundle['probes'], [], bundle['mesh'])


@pytest.mark.parametrize('field,index', [('velocity', 2), ('pressure_pa', 1)])
def test_explicit_null_boundary_values_are_rejected_before_publication(tmp_path, field, index):
    _, bundle, _ = openfoam.channel_poiseuille_case(10)
    bundle['boundaries'][index]['condition'][field] = None
    with pytest.raises(ValueError, match='explicitly null'):
        openfoam.write_openfoam_case(bundle, tmp_path / 'case')
    assert not (tmp_path / 'case').exists()


def test_reference_cell_upper_bound():
    _, bundle = openfoam.cavity_control_case(16)
    bundle['mesh']['p_ref_cell'] = 255
    openfoam.validate_bundle(bundle)
    bundle['mesh']['p_ref_cell'] = 256
    with pytest.raises(ValueError, match='inside the generated cell count'):
        openfoam.validate_bundle(bundle)


def _probe_runner(cdir, bundle, outputs):
    def run(command, timeout):
        script = command[-1]
        if 'TOOL:blockMesh' in script:
            return 0, 'VERSION=v2606\nOPTIONS=test\n' + '\n'.join(
                'TOOL:' + name + '=/bin/' + name for name in openfoam._REQUIRED_TOOLS), ''
        if 'checkMesh' in script:
            return 0, 'cells: 400\nOverall domain bounding box (0 0 0) (4 1 0.3)\nMesh OK.\n', ''
        if 'postProcess' in script:
            for directory, field, sample_time, value in outputs:
                dest = cdir / 'postProcessing' / 'probes' / directory
                dest.mkdir(parents=True, exist_ok=True)
                values = ' '.join(str(value) if field == 'p' else f'({value} 0 0)' for _ in bundle['probes'])
                (dest / field).write_text(f'{sample_time} {values}\n')
        return 0, 'SIMPLE solution converged', ''
    return run


def test_run_defaults_numeric_time_selection_and_reuse_rejection(tmp_path):
    _, bundle, _ = openfoam.channel_poiseuille_case(10)
    del bundle['mesh']['solver']
    cdir = Path(openfoam.write_openfoam_case(bundle, tmp_path / 'case')['openfoam_dir'])
    outputs = [('900', 'p', 900, 9), ('900', 'U', 900, 9),
               ('1000', 'p', 1000, 1), ('1000', 'U', 1000, 1)]
    runner = _probe_runner(cdir, bundle, outputs)
    result = openfoam.run_openfoam_case(cdir, bundle, launcher='/fake', runner=runner)
    assert result['solver'] == 'simpleFoam'
    assert result['sample_time'] == result['pressure_sample_time'] == 1000
    assert result['probes']['p_x1_mid']['velocity_m_s'] == [1, 0, 0]
    assert result['probes']['p_x1_mid']['pressure_pa'] == pytest.approx(1.225)
    with pytest.raises(ValueError, match='previous run output'):
        openfoam.run_openfoam_case(cdir, bundle, launcher='/fake', runner=runner)
    assert (cdir / 'postProcessing' / 'probes' / '900' / 'p').exists()


@pytest.mark.parametrize('outputs,message', [
    ([('0', 'p', 10, 1), ('0', 'U', 11, 1)], 'sample times do not match'),
    ([('0', 'p', 10, 1), ('1', 'U', 10, 1)], 'matching probe files'),
    ([('nan', 'p', 10, 1), ('nan', 'U', 10, 1)], 'Non-finite'),
])
def test_run_rejects_unmatched_or_invalid_probe_times(tmp_path, outputs, message):
    _, bundle, _ = openfoam.channel_poiseuille_case(10)
    cdir = Path(openfoam.write_openfoam_case(bundle, tmp_path / 'case')['openfoam_dir'])
    with pytest.raises((ValueError, RuntimeError), match=message):
        openfoam.run_openfoam_case(cdir, bundle, launcher='/fake', runner=_probe_runner(cdir, bundle, outputs))


@pytest.mark.parametrize('artifact', ['.hawa-run-started', '1000', 'constant/polyMesh'])
def test_run_rejects_prior_failed_run_or_fields(tmp_path, artifact):
    _, bundle, _ = openfoam.channel_poiseuille_case(10)
    cdir = Path(openfoam.write_openfoam_case(bundle, tmp_path / 'case')['openfoam_dir'])
    dest = cdir / artifact
    if artifact.startswith('.'):
        dest.write_text('prior attempt')
    else:
        dest.mkdir()
    with pytest.raises(ValueError, match='fresh case directory'):
        openfoam.run_openfoam_case(cdir, bundle, launcher='/fake', runner=_probe_runner(cdir, bundle, []))


@pytest.mark.parametrize('kind,key', [('probes', 'velocity_m_s'), ('probes', 'pressure_pa'),
                                     ('pressure_pairs', 'delta_p_pa'), ('pressure_pairs', 'gradient_pa_m')])
@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
@pytest.mark.parametrize('side', ['hawa', 'openfoam'])
def test_compare_rejects_nonfinite_measurements(kind, key, value, side):
    _, bundle, analytic = openfoam.channel_poiseuille_case(10)
    good = {'probes': analytic['probes'], 'pressure_pairs': analytic['pressure_pairs']}
    bad = copy.deepcopy(good)
    row = next(iter(bad[kind].values()))
    row[key] = [value, 0, 0] if key == 'velocity_m_s' else value
    args = (bad, good) if side == 'hawa' else (good, bad)
    with pytest.raises(ValueError, match='finite'):
        openfoam.compare_probe_results(bundle, *args, velocity_tol=.01, pressure_tol=.01)


def test_compare_rejects_bad_vector_analytic_tolerance_and_overflow():
    _, bundle, analytic = openfoam.channel_poiseuille_case(10)
    good = {'probes': analytic['probes'], 'pressure_pairs': analytic['pressure_pairs']}
    bad = copy.deepcopy(good)
    bad['probes']['p_x1_mid']['velocity_m_s'] = [1, 2]
    with pytest.raises(ValueError, match='three-component'):
        openfoam.compare_probe_results(bundle, bad, good)
    for tolerance in [float('nan'), float('inf'), -.1]:
        with pytest.raises(ValueError, match='tolerances'):
            openfoam.compare_probe_results(bundle, good, good, velocity_tol=tolerance)
    for kind, key in [('probes', 'velocity_m_s'), ('pressure_pairs', 'gradient_pa_m')]:
        bad_analytic = copy.deepcopy(analytic)
        row = next(iter(bad_analytic[kind].values()))
        row[key] = [float('nan'), 0, 0] if key == 'velocity_m_s' else float('nan')
        with pytest.raises(ValueError, match='Analytic'):
            openfoam.compare_probe_results(bundle, good, good, analytic=bad_analytic)
    bad['probes']['p_x1_mid']['velocity_m_s'] = [1e300, 0, 0]
    with pytest.raises(ValueError, match='Non-finite velocity comparison'):
        openfoam.compare_probe_results(bundle, bad, good)


@pytest.mark.parametrize('ndim', [2, 3])
def test_generated_shifted_uneven_grids_preserve_affine_fields(ndim):
    # Deterministic generated property: multilinear interpolation is exact for
    # every affine field, independent of coordinate origin and nonuniform spacing.
    rng = np.random.default_rng(128)
    for _ in range(40):
        axes = [rng.uniform(-20, 20) + np.cumsum(rng.uniform(.1, 2, int(rng.integers(3, 8))))
                for _ in range(ndim)]
        grid = np.asarray(np.meshgrid(*axes, indexing='ij'))
        coeff = rng.uniform(-4, 4, (ndim + 1, ndim))
        offset = rng.uniform(-3, 3, ndim + 1)
        fields = np.einsum('ij,j...->i...', coeff, grid) + offset.reshape((-1,) + (1,) * ndim)
        probes = np.array([[rng.uniform(axis[0], axis[-1]) for axis in axes] for _ in range(5)])
        expected = probes @ coeff.T + offset
        samples = openfoam.sample_regular_grid(fields[:ndim], fields[-1], axes, probes)
        for sample, want in zip(samples, expected):
            np.testing.assert_allclose(sample[0][:ndim], want[:ndim], rtol=1e-12, atol=1e-12)
            assert sample[1] == pytest.approx(want[-1], rel=1e-12, abs=1e-12)


def test_git_provenance_hashes_changed_untracked_deleted_and_symlink_contents(tmp_path):
    import subprocess
    import compare_openfoam_controls as cli
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    tracked = tmp_path / 'source.py'
    tracked.write_text('first')
    subprocess.run(['git', 'add', '.'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                    'commit', '-qm', 'baseline'], cwd=tmp_path, check=True)
    clean = cli.git_provenance(tmp_path)
    assert not clean['dirty']
    assert clean['commit'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=tmp_path, text=True).strip()
    assert len(clean['dirty_digest']) == 64
    assert cli.git_provenance(tmp_path) == clean
    tracked.write_text('second')
    second = cli.git_provenance(tmp_path)
    tracked.write_text('third')
    third = cli.git_provenance(tmp_path)
    assert second['dirty'] and third['dirty']
    assert len({clean['dirty_digest'], second['dirty_digest'], third['dirty_digest']}) == 3
    untracked = tmp_path / 'new.py'
    untracked.write_text('new')
    added = cli.git_provenance(tmp_path)
    untracked.write_text('changed')
    assert cli.git_provenance(tmp_path)['dirty_digest'] != added['dirty_digest']
    (tmp_path / 'link').symlink_to('source.py')
    linked = cli.git_provenance(tmp_path)
    tracked.unlink()
    assert cli.git_provenance(tmp_path)['dirty_digest'] != linked['dirty_digest']


def test_git_provenance_rejects_unknown_source_and_hashes_symlink_targets(tmp_path):
    import subprocess
    import compare_openfoam_controls as cli
    with pytest.raises(subprocess.CalledProcessError):
        cli.git_provenance(tmp_path)
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / 'source.py').write_text('source')
    subprocess.run(['git', 'add', '.'], cwd=tmp_path, check=True)
    subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                    'commit', '-qm', 'baseline'], cwd=tmp_path, check=True)
    link = tmp_path / 'lien-é'
    link.symlink_to('source.py')
    first = cli.git_provenance(tmp_path)
    link.unlink()
    link.symlink_to('missing.py')
    assert cli.git_provenance(tmp_path)['dirty_digest'] != first['dirty_digest']
