"""Run the original suite without placing the fork on the oracle import path."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", action="store_true")
    args = parser.parse_args()
    tests = ROOT / "vendor/lettuce/tests"
    python = Path(sys.executable)
    name = "backport"
    if args.reference:
        python = ROOT / ".venv-reference" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        isolated = ROOT / ".reference/upstream-tests/tests"
        shutil.copytree(tests, isolated, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        docs = isolated.parent / "docs"
        docs.mkdir(exist_ok=True)
        shutil.copy2(ROOT / "vendor/lettuce/docs/modules.rst", docs / "modules.rst")
        tests = isolated
        name = "reference"
    output = ROOT / "results/tests"
    output.mkdir(parents=True, exist_ok=True)
    command = [str(python), "-m", "pytest", str(tests), "-q", "--disable-warnings",
               "--junitxml=" + str(output / (name + ".xml"))]
    return subprocess.call(command, cwd=ROOT, env=dict(os.environ, MPLBACKEND="Agg"))


if __name__ == "__main__":
    raise SystemExit(main())
