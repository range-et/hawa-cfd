#! python 3
# venv: hawa-py39
# requirements: torch==2.8.0, numpy==2.0.2, click==8.1.8, h5py==3.14.0, matplotlib==3.9.4, mmh3==5.2.0, packaging==26.0, pyevtk==1.7.0, setuptools==82.0.1
"""Development component: add repo (text), run (bool), device (text) inputs.

Output a is a diagnostics dictionary. Set repo to the checkout folder. Rhino
processes the requirements above before executing this component. The Python
sources ship in the checkout; production distribution will ship the built wheels.
This file must be run by the Grasshopper Python 3 component, not legacy GhPython.
"""

from pathlib import Path
import sys

loaded_numpy = sys.modules.get("numpy")
if loaded_numpy is not None and loaded_numpy.__version__ != "2.0.2":
    raise RuntimeError("Restart Rhino before using Hawa's NumPy 2.0.2 environment")
root = Path(repo)
if sys.version_info[:2] != (3, 9):
    raise RuntimeError("This build targets Grasshopper's Python 3.9 runtime")
for path in (root / "src", root / "vendor/lettuce"):
    if not path.is_dir():
        raise RuntimeError("repo must point to the Hawa checkout")
    sys.path.insert(0, str(path))

from hawa.engine import LettuceSimulation

a = {"status": "ready"}
if run:
    simulation = LettuceSimulation("tgv3d-bgk", device=device or "auto")
    simulation.advance(50)
    a = simulation.diagnostics()
