"""Run Slice 1 Hawa vs local OpenFOAM v2606 control comparisons (Channel 07 & Cavity 06; #126, #127)."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from hawa.openfoam import (  # noqa: E402
    ADAPTER_VERSION,
    cavity_control_case,
    channel_poiseuille_case,
    compare_probe_results,
    detect_openfoam,
    run_hawa_cavity,
    run_hawa_channel,
    run_openfoam_case,
    write_openfoam_case,
)


def git_provenance(root):
    """Capture current commit and dirty-worktree status for report provenance."""
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), text=True, capture_output=True, check=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
        cwd=str(root), capture_output=True, check=True
    ).stdout
    # Hash all tracked and nonignored untracked contents, including staged edits,
    # deletions and symlink targets. Status text alone cannot identify edited code.
    paths = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(root), capture_output=True, check=True
    ).stdout.split(b"\0")
    digest = hashlib.sha256(status)
    for name in sorted(set(paths) - {b""}):
        path = Path(root) / name.decode("utf-8", errors="surrogateescape")
        digest.update(name + b"\0")
        if path.is_symlink():
            import os
            digest.update(b"symlink\0" + os.fsencode(os.readlink(path)))
        elif path.is_file():
            digest.update(b"file\0" + hashlib.sha256(path.read_bytes()).digest())
        else:
            digest.update(b"missing\0")
    return {
        "commit": commit,
        "dirty": bool(status),
        "dirty_digest": digest.hexdigest(),
    }



def run_control_suite(output_dir, device="cpu", channel_grids=(10, 20, 40),
                      cavity_configs=((32, 0.05), (64, 0.05), (64, 0.015)),
                      launcher=None, runner=None, channel_max_steps=28000,
                      cavity_target_time_s=3.5):
    """Execute Channel (07) and Cavity (06) grid-sensitivity comparisons against OpenFOAM."""
    if not channel_grids or not cavity_configs:
        raise ValueError("Channel and cavity control inventories must both be nonempty")
    of_info = detect_openfoam(launcher=launcher, runner=runner)
    if not of_info["available"]:
        return {
            "status": "BLOCKED",
            "reason": of_info.get("reason", "OpenFOAM launcher unavailable"),
            "openfoam": of_info,
            "adapter_version": ADAPTER_VERSION,
            "provenance": git_provenance(ROOT),
            "platform": platform.platform(),
            "channel_cases": [],
            "cavity_cases": [],
        }

    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    channel_rows = []
    for ny in channel_grids:
        spec, bundle, analytic = channel_poiseuille_case(ny_cells=ny)
        case_root = out_root / bundle["case_id"]
        published = write_openfoam_case(bundle, case_root, overwrite=True)
        of_res = run_openfoam_case(published["openfoam_dir"], bundle, launcher=launcher, runner=runner)
        hawa_res = run_hawa_channel(
            spec, bundle, device=device, max_steps=channel_max_steps, check_interval=1000, settle_tol=1e-3
        )
        v_tol = 0.02 if ny >= 20 else None
        p_tol = 0.05 if ny >= 20 else None
        comp = compare_probe_results(
            bundle, hawa_res, of_res, analytic=analytic, velocity_tol=v_tol, pressure_tol=p_tol
        )
        channel_rows.append({
            "ny_cells": ny,
            "case_id": bundle["case_id"],
            "role": "resolved_gate" if ny >= 20 else "coarse_sensitivity_baseline",
            "openfoam": {
                "solver": of_res["solver"],
                "converged": of_res["converged"],
                "sample_time": of_res["sample_time"],
                "check_mesh": of_res["check_mesh"],
            },
            "hawa": {
                "device": hawa_res["device"],
                "dtype": hawa_res["dtype"],
                "steps": hawa_res["steps"],
                "physical_time_s": hawa_res["physical_time_s"],
                "tau": hawa_res["tau"],
                "settled": hawa_res["settled"],
                "final_drift": hawa_res["final_drift"],
                "relative_mass_change": hawa_res["relative_mass_change"],
            },
            "comparison": comp,
        })

    cavity_rows = []
    of_cache = {}
    for n, mach in cavity_configs:
        hawa_cfg, bundle = cavity_control_case(n=n, reynolds=10.0, mach=mach)
        if n not in of_cache:
            case_root = out_root / bundle["case_id"]
            published = write_openfoam_case(bundle, case_root, overwrite=True)
            of_cache[n] = run_openfoam_case(published["openfoam_dir"], bundle, launcher=launcher, runner=runner)
        of_res = of_cache[n]
        hawa_res = run_hawa_cavity(
            hawa_cfg, bundle, device=device, dtype="float64", target_time_s=cavity_target_time_s
        )
        comp = compare_probe_results(bundle, hawa_res, of_res)
        cavity_rows.append({
            "resolution": n,
            "mach_number": mach,
            "case_id": f"{bundle['case_id']}_ma{str(mach).replace('.', 'p')}",
            "openfoam": {
                "solver": of_res["solver"],
                "converged": of_res["converged"],
                "sample_time": of_res["sample_time"],
                "check_mesh": of_res["check_mesh"],
            },
            "hawa": {
                "device": hawa_res["device"],
                "dtype": hawa_res["dtype"],
                "steps": hawa_res["steps"],
                "physical_time_s": hawa_res["physical_time_s"],
                "tau": hawa_res["tau"],
            },
            "comparison": comp,
        })

    monotonic_u = all(
        channel_rows[i]["comparison"]["velocity_l2_norm"] > channel_rows[i + 1]["comparison"]["velocity_l2_norm"]
        for i in range(len(channel_rows) - 1)
    )
    all_channel_ok = monotonic_u and all(
        r["comparison"]["passed"] and r["openfoam"]["converged"] and r["hawa"]["settled"]
        for r in channel_rows
    )
    return {
        "status": "COMPLETED" if all_channel_ok else "FAILED",
        "adapter_version": ADAPTER_VERSION,
        "provenance": git_provenance(ROOT),
        "platform": platform.platform(),
        "openfoam": of_info,
        "monotonic_channel_velocity_convergence": monotonic_u,
        "channel_cases": channel_rows,
        "cavity_cases": cavity_rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Hawa vs OpenFOAM control comparisons (#126, #127)")
    parser.add_argument("--output-dir", default=str(ROOT / "results" / "openfoam" / "controls"))
    parser.add_argument("--report", default=str(ROOT / "docs" / "verification-openfoam-controls.json"))
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    report_path.write_text(json.dumps({"status": "RUNNING", "run_id": run_id}) + "\n", encoding="utf-8")
    try:
        report = run_control_suite(args.output_dir, device=args.device)
    except Exception as exc:
        report_path.write_text(json.dumps({"status": "FAILED", "run_id": run_id, "reason": str(exc)})
                               + "\n", encoding="utf-8")
        raise
    report["run_id"] = run_id
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(report_path)}, indent=2))
    return 0 if report["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
