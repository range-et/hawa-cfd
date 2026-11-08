"""Execute an original notebook/script in an isolated output directory.

The smoke profile preserves original grids, initial conditions, geometry and
algorithms, but explicitly overrides device/dtype/native flags and limits stepping.
It does not claim original long-run convergence. --full removes the step budget.
"""

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import shlex
import shutil
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "vendor/lettuce/examples"


class BudgetReached(Exception):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--source-root", type=Path, default=EXAMPLES)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.chdir(args.output)
    import numpy as np
    import torch
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    import lettuce as lt
    original_seed = np.random.seed
    np.random.seed = lambda seed=None: original_seed(1234 if seed is None else seed)
    np.random.seed(1234)
    torch.manual_seed(1234)

    examples = args.source_root
    path = examples / args.source
    raw = path.read_text()
    if path.suffix == ".ipynb":
        cells = ["".join(c.get("source", [])) for c in json.loads(raw)["cells"] if c.get("cell_type") == "code"]
        magic = [line for c in cells for line in c.splitlines() if line.lstrip().startswith(("%", "!")) and not line.lstrip().startswith("%run ")]
        def translate(line):
            if line.lstrip().startswith("%run "):
                return "_hawa_run(" + repr(line.lstrip()[5:]) + ")"
            return "" if line.lstrip().startswith(("%", "!")) else line
        source = "\n\n".join("\n".join(translate(line) for line in cell.splitlines()) for cell in cells)
    else:
        source, magic = raw, []
    report = {"source": args.source, "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "engine_file": lt.__file__, "python": sys.version, "torch": torch.__version__,
              "numpy": np.__version__, "device": args.device,
              "profile": "full" if args.full else "50-steps-per-simulation",
              "verification_seed": 1234,
              "notebook_magics_not_executed": magic, "simulations": []}
    original_context = lt.Context.__init__

    def context(self, *a, **kw):
        kw.pop("device", None); kw.pop("dtype", None); kw.pop("use_native", None)
        original_context(self, device=args.device, dtype=torch.float32, use_native=False)
    lt.Context.__init__ = context
    simulations = []
    original_init = lt.Simulation.__init__

    def wrap_steps(method):
        def bounded(self, num_steps, _method=method):
            if args.full:
                return _method(self, num_steps)
            limit = 250 if "FailingTGV" in args.source else 50
            already = getattr(self, "_hawa_budget", 0)
            remaining = limit - already
            if remaining <= 0:
                raise BudgetReached()
            count = min(int(num_steps), remaining)
            self._hawa_budget = already + count
            result = _method(self, count)
            if int(num_steps) > count and "FailingTGV" not in args.source:
                raise BudgetReached()
            return result
        bounded._hawa_bounded = True
        return bounded

    def simulation_init(self, *a, **kw):
        original_init(self, *a, **kw)
        simulations.append(self)
        cls = type(self)
        method = cls.__dict__.get("__call__")
        if method is not None and not getattr(method, "_hawa_bounded", False):
            cls.__call__ = wrap_steps(method)
    lt.Simulation.__init__ = simulation_init
    for cls in (lt.Simulation, lt.BreakableSimulation):
        cls.__call__ = wrap_steps(cls.__call__)
    # Keep plots available for shape checks without interactive UI or huge exports.
    plt.show = lambda *a, **kw: plt.close("all")
    original_savefig = plt.savefig
    plt.savefig = lambda *a, **kw: None
    sys.path.insert(0, str(examples.parent))
    sys.path.insert(0, str(path.parent))
    project = examples / "advanced_projects/efficient_bounce_back_obstacle"
    for directory in (project, project / "boundary", project / "flow", project / "simulation", project / "reporter", project / "auxiliary_code"):
        sys.path.insert(0, str(directory))
    sys.argv = [str(path)]
    namespace = {"__name__": "__main__", "__file__": str(path)}
    def run_driver(command):
        parts = shlex.split(command)
        driver = path.parent / parts[0]
        reference_data = path.parent / "profile_reference_data"
        if reference_data.is_dir():
            shutil.copytree(reference_data, args.output / "profile_reference_data", dirs_exist_ok=True)
        previous = sys.argv
        try:
            sys.argv = [str(driver), *parts[1:]]
            runpy.run_path(str(driver), run_name="__main__")
        except BudgetReached:
            report["budget_reached"] = True
        finally:
            sys.argv = previous
    namespace["_hawa_run"] = run_driver
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                exec(compile(source, str(path), "exec"), namespace)
            except BudgetReached:
                report["budget_reached"] = True
        report["status"] = "passed" if simulations else "launcher-only"
    except Exception as exc:
        report.update(status="failed", error=type(exc).__name__ + ": " + str(exc), traceback=traceback.format_exc())
    for number, simulation in enumerate(simulations):
        flow = simulation.flow
        finite = bool(torch.isfinite(flow.f).all().cpu())
        expected_failure = "FailingTGV" in args.source
        report["simulations"].append({"flow": type(flow).__name__, "shape": flow.resolution,
                                     "iterations": flow.i, "finite": finite,
                                     "velocity_conversion_scale": float(flow.units.convert_velocity_to_pu(1.0)),
                                     "pressure_conversion_scale": float(flow.units.convert_density_lu_to_pressure_pu(2.0) - flow.units.convert_density_lu_to_pressure_pu(1.0)),
                                     "failure_reporters": {type(r).__name__: r.failed_iteration for r in simulation.reporter if hasattr(r, "failed_iteration")},
                                     "failure_detection_example": expected_failure})
        np.savez_compressed(args.output / ("fields_" + str(number) + ".npz"),
                            f=flow.f.detach().cpu().numpy(), rho=flow.rho().detach().cpu().numpy(),
                            u=flow.u_pu.detach().cpu().numpy(), p=flow.p_pu.detach().cpu().numpy())
        if hasattr(flow, "mask"):
            np.save(args.output / ("mask_" + str(number) + ".npy"), flow.context.convert_to_ndarray(flow.mask))
        if not finite and not expected_failure:
            report["status"] = "failed"
            report["error"] = "Nonfinite populations"
    (args.output / "stdout.txt").write_text(output.getvalue())
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(args.source + ": " + report["status"] + (" " + report.get("error", "")))
    return 0 if report["status"] in ("passed", "launcher-only") else 1


if __name__ == "__main__":
    raise SystemExit(main())
