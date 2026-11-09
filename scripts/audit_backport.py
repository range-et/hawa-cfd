"""Verify that only explicitly reviewed upstream modules were modified."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "lettuce"
ALLOWED = {
    "lettuce/__init__.py", "lettuce/_context.py", "lettuce/cli.py",
    "lettuce/ext/_flows/liddrivencavity.py", "lettuce/ext/_flows/couette.py",
    "lettuce/ext/_flows/obstacle.py", "lettuce/ext/_flows/decayingturbulence.py",
    "lettuce/ext/_equilibrium/incompressible_quadratic_equilibrium.py",
    "lettuce/util/moments.py",
    "lettuce/ext/_collision/kbc_collision.py",
    "lettuce/ext/_reporter/observable_reporter.py", "lettuce/ext/_reporter/write_image.py",
    "lettuce/ext/_reporter/vtk_reporter.py", "lettuce/ext/_reporter/failure_reporter.py",
    "lettuce/ext/_boundary/equilibrium_boundary_pu.py", "lettuce/ext/_force/shan_chen.py",
}


def source_digest(path):
    """Ignore Git's Windows CRLF checkout conversion, but no other byte changes."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def audit():
    manifest = json.loads((VENDOR / "upstream.json").read_text())
    changed = []
    for name, digest in manifest["source_sha256"].items():
        path = VENDOR / name
        if not path.exists():
            raise RuntimeError("Missing upstream module: " + name)
        if source_digest(path) != digest:
            changed.append(name)
    unexpected = set(changed) - ALLOWED
    extra = {p.relative_to(VENDOR).as_posix() for p in (VENDOR / "lettuce").rglob("*.py")} - set(manifest["source_sha256"])
    if unexpected or extra:
        raise RuntimeError("Unreviewed source changes: " + repr(unexpected | extra))
    for name, digest in manifest.get("test_sha256", {}).items():
        if source_digest(VENDOR / name) != digest:
            raise RuntimeError("Original upstream test modified: " + name)
    return {"commit": manifest["commit"], "changed_modules": changed,
            "unchanged_modules": len(manifest["source_sha256"]) - len(changed),
            "unchanged_test_files": len(manifest.get("test_sha256", {}))}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
