"""Developer-only oracle setup; Grasshopper users do not need this environment."""

from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
environment = ROOT / ".venv-reference"
python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not python.exists():
    subprocess.run(["uv", "venv", "--python", "3.12", str(environment)], check=True, cwd=ROOT)
subprocess.run(["uv", "pip", "install", "--python", str(python), "-r",
                str(ROOT / "requirements/reference-py312.txt")], check=True, cwd=ROOT)
