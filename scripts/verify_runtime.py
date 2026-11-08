"""Run headlessly or with runpy inside Rhino; compare CPU and available GPUs."""

import json
import os
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if sys.version_info[:2] == (3, 9):
    sys.path.insert(0, str(ROOT / ".runtime" / "rhino-py39"))

import torch
from hawa.backends import select_backend
from hawa.lbm import VortexSimulation

reports = {}
states = {}
devices = ["cpu"]
if torch.backends.mps.is_available():
    devices.append("mps")
if torch.cuda.is_available():
    devices.append("cuda:0")
devices.append("auto")
for device in devices:
    sim = VortexSimulation(select_backend(device))
    sim.advance(75).advance(125)
    reports[device] = sim.diagnostics()
    states[device] = sim.f.cpu().clone()
    if not reports[device]["passed"]:
        raise RuntimeError("Verification failed on " + device)

differences = {}
for device, state in states.items():
    torch.testing.assert_close(state, states["cpu"], rtol=2e-5, atol=2e-6)
    differences[device] = float((state - states["cpu"]).abs().max())

host = "rhino-embedded" if "Rhino" in sys.modules else "headless"
report = {
    "host": host, "pid": os.getpid(), "python": sys.version,
    "executable": sys.executable, "architecture": platform.machine(),
    "torch_file": torch.__file__,
    "mps_cpu_fallback_environment": os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "unset"),
    "reports": reports, "max_population_difference_from_cpu": differences,
    "cuda_hardware_tested": torch.cuda.is_available(), "passed": True,
}
output = ROOT / "results" / (host + "-verification.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
