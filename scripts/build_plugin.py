"""Build a self-contained Grasshopper assembly/source bundle (dependencies via Rhino)."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", type=Path, help="Optional Grasshopper Libraries destination")
    args = parser.parse_args()
    output = ROOT / "dist/Hawa"
    subprocess.run(["dotnet", "build", str(ROOT / "plugin/Hawa.Grasshopper"), "-c", "Release",
                    "--nologo", "-v", "quiet"], check=True)
    output.mkdir(parents=True, exist_ok=True)
    assembly = output / "Hawa.Grasshopper.gha"
    shutil.copy2(ROOT / "plugin/Hawa.Grasshopper/bin/Release/net7.0/Hawa.Grasshopper.gha", assembly.with_suffix(".gha.new"))
    os.replace(assembly.with_suffix(".gha.new"), assembly)
    shutil.copy2(ROOT / "plugin/Bootstrap.py", output)
    for package, source in (("hawa", ROOT / "src/hawa"), ("lettuce", ROOT / "vendor/lettuce/lettuce")):
        destination = output / "python" / package
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        if (ROOT / name).exists():
            shutil.copy2(ROOT / name, output)
    notices = output / "licenses/lettuce"
    notices.mkdir(parents=True, exist_ok=True)
    for name in ("LICENSE", "AUTHORS.rst", "PORTING.md", "upstream.json"):
        shutil.copy2(ROOT / "vendor/lettuce" / name, notices / name)
    if (ROOT / "docs/plugin.md").exists():
        shutil.copy2(ROOT / "docs/plugin.md", output / "README.md")
        shutil.copy2(ROOT / "docs/release-notes-v0.4.0.md", output / "release-notes-v0.4.0.md")
        shutil.copy2(ROOT / "docs/verification-v0.4.json", output / "verification-v0.4.json")
        for name in ("moving-surfaces-v0.4.md", "verification-motion-v0.4.json", "hardening-v0.4.md", "hardening-v0.4.json"):
            if (ROOT / "docs" / name).exists():shutil.copy2(ROOT / "docs" / name, output / name)
    if (ROOT / "examples/grasshopper").exists():
        if (output / "examples").exists(): shutil.rmtree(output / "examples")
        shutil.copytree(ROOT / "examples/grasshopper", output / "examples", ignore=shutil.ignore_patterns("09-parametric-hull-galapagos.gh"))
    # Keep the agent workflow and its relative links usable in the installed bundle.
    (output / "AGENTS.md").write_text((ROOT / "AGENTS.md").read_text().replace("examples/grasshopper/README.md", "examples/README.md"))
    docs_output = output / "docs"
    docs_output.mkdir(exist_ok=True)
    for pattern in ("*.md", "*.json"):
        for document in (ROOT / "docs").glob(pattern):
            shutil.copy2(document, docs_output / document.name)
    shutil.copytree(ROOT / "docs/agents", docs_output / "agents", dirs_exist_ok=True)
    for guide in (output / "examples/README.md", *list((docs_output / "agents").glob("*.md"))):
        content = guide.read_text()
        content = content.replace("../../docs/", "../docs/") if guide.parent.name == "examples" else content.replace("../../examples/grasshopper/", "../../examples/")
        guide.write_text(content)
    # Include corresponding build source with GPL binary distributions.
    source_root = output / "source"
    if source_root.exists(): shutil.rmtree(source_root)
    for folder in ("plugin", "src", "scripts", "requirements", "tests", "vendor/lettuce"):
        shutil.copytree(ROOT / folder, source_root / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("bin", "obj", "__pycache__", "*.pyc", ".pytest_cache"))
    for name in ("pyproject.toml", "uv.lock", "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md", "AGENTS.md"):
        shutil.copy2(ROOT / name, source_root / name)
    archive = ROOT / "dist/Hawa-0.4.0-rh8.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for file in output.rglob("*"):
            if file.is_file():
                bundle.write(file, file.relative_to(ROOT / "dist"))
    if args.install:
        destination = args.install / "Hawa"
        for file in output.rglob("*"):
            if file.is_file():
                target = destination / file.relative_to(output)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".new")
                shutil.copy2(file, temporary)
                os.replace(temporary, target)
        print("Installed: " + str(destination))
    print("Built: " + str(archive))


if __name__ == "__main__":
    main()
