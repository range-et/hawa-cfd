"""Runs the shared cases with exactly one engine in the current interpreter."""

import argparse
import hashlib
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import sys
from audit_backport import source_digest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def run(role, device, output, cases=None):
    import lettuce as lt
    import numpy as np
    import torch
    from hawa.cases import CASES, make_case

    manifest = json.loads((ROOT / "vendor/lettuce/upstream.json").read_text())
    source = Path(lt.__file__).resolve().parent
    if role == "upstream":
        dist = distribution("lettucecfd")
        direct = json.loads(dist.read_text("direct_url.json"))
        if direct.get("vcs_info", {}).get("commit_id") != manifest["commit"]:
            raise RuntimeError("Reference installation is not the pinned upstream commit")
        if source == ROOT / "vendor/lettuce/lettuce":
            raise RuntimeError("Reference accidentally imported the compatibility fork")
        for name, digest in manifest["source_sha256"].items():
            actual = source_digest(source.parent / name)
            if actual != digest:
                raise RuntimeError("Reference source was modified: " + name)
    else:
        dist = distribution("hawa-lettuce")
        if sys.version_info[:2] != (3, 9):
            raise RuntimeError("The compatibility engine must be tested on Python 3.9")
        for name in manifest["source_sha256"]:
            expected = ROOT / "vendor/lettuce" / name
            actual = source.parent / name
            if hashlib.sha256(actual.read_bytes()).hexdigest() != hashlib.sha256(expected.read_bytes()).hexdigest():
                raise RuntimeError("Compatibility source mismatch: " + name)
    if device == "mps" and os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK") == "1":
        raise RuntimeError("Disable CPU fallback for MPS parity validation")
    dtype = torch.float32 if device != "cpu64" else torch.float64
    actual_device = "cpu" if device == "cpu64" else device
    context = lt.Context(device=actual_device, dtype=dtype, use_native=False)
    torch.manual_seed(0)
    torch.set_num_threads(1)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for name in CASES if cases is None else cases:
        try:
            flow, simulation = make_case(name, context)
        except TypeError as exc:
            # This signature mismatch exists in the pinned unmodified upstream.
            # Record it on BOTH engines rather than silently fixing the oracle.
            if name != "cavity2d-bgk" or "missing 1 required positional argument: 'velocity'" not in str(exc):
                raise
            reports[name] = {"status": "known-upstream-error", "error": "EquilibriumBoundaryPU missing velocity argument"}
            continue
        values = {}
        for checkpoint in (0, 1, 10, 50):
            with torch.no_grad():
                simulation(checkpoint - flow.i)
            context.synchronize()
            for field, tensor in (("f", flow.f), ("rho", flow.rho()),
                                  ("u", flow.u()), ("p", flow.p_pu)):
                array = tensor.detach().cpu().numpy().copy()
                if not np.isfinite(array).all():
                    raise RuntimeError("Nonfinite values in " + name)
                values["{}_{}".format(checkpoint, field)] = array
            if not bool((flow.rho() > 0).all().cpu()):
                raise RuntimeError("Nonpositive density in " + name)
        np.savez_compressed(output / (name + ".npz"), **values)
        reports[name] = {"resolution": flow.resolution, "steps": flow.i,
                         "tau": flow.units.relaxation_parameter_lu,
                         "pressure_conversion_scale": float(abs(
                             flow.units.convert_density_lu_to_pressure_pu(2.0)
                             - flow.units.convert_density_lu_to_pressure_pu(1.0)))}
    metadata = {
        "role": role, "device": actual_device, "dtype": str(dtype),
        "python": sys.version, "python_executable": sys.executable, "pid": os.getpid(),
        "torch": torch.__version__, "numpy": np.__version__,
        "engine_distribution": dist.metadata["Name"], "engine_version": dist.version,
        "engine_source": str(source), "upstream_commit": manifest["commit"],
        "host": "rhino-embedded" if "Rhino" in sys.modules else "headless",
        "cases": reports, "passed": True,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["upstream", "backport"], required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.role, args.device, args.output), indent=2))
