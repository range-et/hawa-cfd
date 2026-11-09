"""Compare CPU/MPS snapshots from all original example entrypoints."""

import json
from pathlib import Path
import numpy as np
from example_inventory import entrypoints, require_complete_reports

ROOT = Path(__file__).resolve().parents[1]
cpu = ROOT / "results/examples/backport-cpu"
gpu = ROOT / "results/examples/backport-mps"
records = []
report_path=ROOT / "results/examples/parity.json"
# A failed rerun must never leave an earlier successful report behind.
report_path.unlink(missing_ok=True)
source_root = ROOT / "vendor/lettuce/examples"
expected = [str(p.relative_to(source_root)) for p in entrypoints(source_root)]
for directory in (cpu, gpu):
    require_complete_reports(directory, expected)
for path in sorted(cpu.glob("*/report.json")):
    other = gpu / path.parent.name / "report.json"
    if not other.exists():
        raise RuntimeError("MPS example missing: " + path.parent.name)
    a, b = json.loads(path.read_text()), json.loads(other.read_text())
    if a["status"] != "passed" or b["status"] != "passed":
        raise RuntimeError("Example did not pass: " + a["source"])
    if len(a["simulations"]) != len(b["simulations"]):
        raise RuntimeError("Simulation count mismatch: " + a["source"])
    comparisons = []
    for number, (sa, sb) in enumerate(zip(a["simulations"], b["simulations"])):
        if sa["shape"] != sb["shape"] or sa["iterations"] != sb["iterations"]:
            raise RuntimeError("Example configuration mismatch: " + a["source"])
        with np.load(path.parent / ("fields_" + str(number) + ".npz")) as fa, np.load(other.parent / ("fields_" + str(number) + ".npz")) as fb:
            for name in ("f", "rho", "u", "p"):
                scale = sa["velocity_conversion_scale"] if name == "u" else sa["pressure_conversion_scale"] if name == "p" else 1
                # The 250-step intentional failure scenario checks detector behavior,
                # not equality after an unstable trajectory has diverged.
                if sa["failure_detection_example"]:
                    continue
                passed=bool(np.allclose(fb[name],fa[name],rtol=1e-3,atol=1e-5*abs(scale),equal_nan=False))
                comparisons.append({"simulation": number, "field": name,
                                    "max_abs_error": float(np.max(np.abs(fb[name] - fa[name]))),
                                    "rtol": 1e-3, "atol": 1e-5 * abs(scale),"passed":passed})
    records.append({"source": a["source"], "simulations": len(a["simulations"]),
                    "comparisons": comparisons, "passed": all(c['passed'] for c in comparisons)})
report = {"passed": all(r['passed'] for r in records), "profile": "bounded", "examples": records}
(ROOT / "results/examples/parity.json").write_text(json.dumps(report, indent=2) + "\n")
print("CPU/MPS example parity:", sum(r['passed'] for r in records),"/",len(records), "entrypoints passed")
for record in records:
    if not record['passed']:print('FAILED:',record['source'])
raise SystemExit(0 if report['passed'] else 1)
