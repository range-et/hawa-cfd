"""Orchestrate isolated upstream/backport workers and compare all saved fields."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import torch

from audit_backport import audit

ROOT = Path(__file__).resolve().parents[1]


def compare(reference, candidate, device):
    reference = Path(reference)
    candidate = Path(candidate)
    ref_meta = json.loads((reference / "metadata.json").read_text())
    test_meta = json.loads((candidate / "metadata.json").read_text())
    if ref_meta["upstream_commit"] != test_meta["upstream_commit"]:
        raise RuntimeError("Engine versions do not share an upstream commit")
    if ref_meta["dtype"] != test_meta["dtype"]:
        raise RuntimeError("Precision mismatch")
    if set(ref_meta["cases"]) != set(test_meta["cases"]):
        raise RuntimeError("Case lists differ")
    records = []
    repairs = []
    for name in ref_meta["cases"]:
        if ref_meta["cases"][name].get("status") == "known-upstream-error":
            if test_meta["cases"][name].get("status") != "known-upstream-error":
                repairs.append(name)
            continue
        if ref_meta["cases"][name] != test_meta["cases"][name]:
            raise RuntimeError("Case configurations differ: " + name)
        with np.load(reference / (name + ".npz")) as ref, np.load(candidate / (name + ".npz")) as test:
            if set(ref.files) != set(test.files):
                raise RuntimeError("Missing comparison fields")
            for field in ref.files:
                if device == "cpu64":
                    rtol, atol = 1e-11, 1e-12
                elif device == "cpu":
                    rtol, atol = 3e-6, 2e-7
                else:
                    rtol, atol = 3e-4, 2e-6
                    if field.endswith("_p"):
                        # Physical pressure is an affine conversion of density.
                        # Propagate the density tolerance through that conversion.
                        atol *= ref_meta["cases"][name]["pressure_conversion_scale"]
                np.testing.assert_allclose(test[field], ref[field], rtol=rtol, atol=atol,
                                           err_msg=name + " / " + field)
                delta = test[field].astype(np.float64) - ref[field].astype(np.float64)
                records.append({"case": name, "checkpoint_field": field,
                                "max_abs_error": float(np.abs(delta).max()),
                                "rtol": rtol, "atol": atol})
    return {"candidate": test_meta, "comparisons": records,
            "repaired_upstream_cases": repairs,
            "known_upstream_errors": {name: value for name, value in ref_meta["cases"].items()
                                      if value.get("status") == "known-upstream-error"},
            "passed": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/parity")
    parser.add_argument("--reference-python", type=Path,
                        default=ROOT / ".venv-reference" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 9):
        parser.error("Run this orchestrator with Hawa's Python 3.9 environment")
    source_audit = audit()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").unlink(missing_ok=True)
    worker = ROOT / "scripts/parity_worker.py"
    env = dict(os.environ, MPLBACKEND="Agg")
    # Each interpreter loads its own engine. Neither imports the other engine.
    devices = ["cpu", "cpu64"]
    if torch.backends.mps.is_available():
        devices.append("mps")
    if torch.cuda.is_available():
        devices.append("cuda:0")
    records = {}
    for device in devices:
        reference_device = "cpu64" if device == "cpu64" else "cpu"
        reference = output / ("upstream-" + reference_device)
        if not (reference / "metadata.json").exists() or device in ("cpu", "cpu64"):
            subprocess.run([str(args.reference_python), str(worker), "--role", "upstream",
                            "--device", reference_device, "--output", str(reference)],
                           check=True, cwd=ROOT, env=env, stdout=subprocess.DEVNULL)
        candidate = output / ("backport-" + device.replace(":", "-"))
        subprocess.run([sys.executable, str(worker), "--role", "backport", "--device", device,
                        "--output", str(candidate)], check=True, cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL)
        records[device] = compare(reference, candidate, device)
        print(device + ": all fields/checkpoints passed", flush=True)
    report = {"source_audit": source_audit, "results": records,
              "cuda_tested": torch.cuda.is_available(), "passed": True}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Report: " + str(output / "report.json"))


if __name__ == "__main__":
    main()
