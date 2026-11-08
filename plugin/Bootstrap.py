#! python 3
# venv: hawa-py39
# requirements: torch==2.8.0, numpy==2.0.2, click==8.1.8, h5py==3.14.0, matplotlib==3.9.4, mmh3==5.2.0, packaging==26.0, pyevtk==1.7.0, setuptools==82.0.1
# hawa-bootstrap-root
"""Executed by Rhino's Python 3 engine; Rhino handles package installation."""

from pathlib import Path
import os
import sys

if sys.version_info[:2] != (3, 9):
    raise RuntimeError("This Hawa build requires Rhino's Python 3.9 runtime")

root = Path(HAWA_PACKAGE_DIR) if "HAWA_PACKAGE_DIR" in globals() else Path(__file__).resolve().parent
sys.path.insert(0, str(root / "python"))
diagnostic = os.environ.get("HAWA_DIAGNOSTIC_ALLOW_EXISTING_NUMPY") == "1"
loaded = sys.modules.get("numpy")
if loaded is not None and loaded.__version__ != "2.0.2":
    if not diagnostic:
        raise RuntimeError("NumPy {} was already loaded. Restart Rhino before initializing Hawa's NumPy 2.0.2 environment.".format(loaded.__version__))
for name in ("hawa", "lettuce"):
    module = sys.modules.get(name)
    if module is not None and Path(module.__file__).resolve().parent != root / "python" / name:
        if not diagnostic:
            raise RuntimeError("Another {} build is already loaded; restart Rhino to load this Hawa package".format(name))
        # Developer-only reload of our pure-Python modules, not native dependencies.
        for key in list(sys.modules):
            if key == name or key.startswith(name + "."):
                del sys.modules[key]
os.environ.setdefault("MPLBACKEND", "Agg")
from hawa.plugin import dispatch_json
