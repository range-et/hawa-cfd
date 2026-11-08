"""Load packaged Python 3.9 wheels inside Rhino; run the real Lettuce fork."""

from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".runtime/rhino39-lettuce"
loaded_numpy = sys.modules.get("numpy")
if loaded_numpy is not None and loaded_numpy.__version__ != "2.0.2":
    if not globals().get("HAWA_ALLOW_EXISTING_NUMPY", False):
        raise RuntimeError("Rhino already loaded NumPy {}. Restart Rhino before loading Hawa's NumPy 2.0.2 environment.".format(loaded_numpy.__version__))
sys.path.insert(0, str(target))

import numpy as np
import torch
from hawa.engine import LettuceSimulation

sim = LettuceSimulation(case=globals().get("HAWA_CASE", "tgv3d-bgk"),
                       device=globals().get("HAWA_DEVICE", "auto"))
sim.advance(10).advance(40)
report = sim.diagnostics()
report.update({"host": "rhino-embedded", "python": sys.version, "pid": os.getpid(),
               "numpy": np.__version__, "torch": torch.__version__,
               "strict_dependency_versions": np.__version__ == "2.0.2"})
output = ROOT / "results/rhino-lettuce"
output.mkdir(parents=True, exist_ok=True)
np.savez_compressed(output / "fields.npz", **sim.snapshot())
(output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
if not report["passed"]:
    raise RuntimeError("Embedded Lettuce simulation failed")
