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
    parser.add_argument("--package-only", action="store_true", help="Refresh the bundle using existing tested Release assemblies; do not compile")
    args = parser.parse_args()
    output = ROOT / "dist/Hawa"
    if not args.package_only:
        subprocess.run(["dotnet", "build", str(ROOT / "plugin/Hawa.Grasshopper"), "-c", "Release",
                        "--nologo", "-v", "quiet"], check=True)
        subprocess.run(["dotnet", "build", str(ROOT / "plugin/Hawa.Rhino"), "-c", "Release", "--nologo", "-v", "quiet"], check=True)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("Hawa.Rhino.rhp", "Hawa.Shared.dll"):
        shutil.copy2(ROOT / "plugin/Hawa.Rhino/bin/Release/net7.0" / name, output / name)
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
        (output / "README.md").write_text((ROOT / "docs/native-v0.5.md").read_text().replace("](captures/", "](docs/captures/").replace("](verification-v0.5.json)", "](docs/verification-v0.5.json)").replace("](verification-boundaries-v0.5.json)", "](docs/verification-boundaries-v0.5.json)").replace("](curved-boundaries-v0.5.md)", "](docs/curved-boundaries-v0.5.md)").replace("](../examples/", "](examples/"))
        shutil.copy2(ROOT / "docs/release-notes-v0.4.0.md", output / "release-notes-v0.4.0.md")
        shutil.copy2(ROOT / "docs/verification-v0.4.json", output / "verification-v0.4.json")
        for name in ("moving-surfaces-v0.4.md", "verification-motion-v0.4.json", "hardening-v0.4.md", "hardening-v0.4.json"):
            if (ROOT / "docs" / name).exists():shutil.copy2(ROOT / "docs" / name, output / name)
    if (ROOT / "examples/grasshopper").exists():
        if (output / "examples").exists(): shutil.rmtree(output / "examples")
        shutil.copytree(ROOT / "examples/grasshopper", output / "examples", ignore=shutil.ignore_patterns("09-parametric-hull-galapagos.gh"))
    shutil.copytree(ROOT / "examples/native-prototype", output / "examples/native-prototype", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.rhl", "*.3dmbak", "*.ghbak"))
    # Keep the agent workflow and its relative links usable in the installed bundle.
    (output / "AGENTS.md").write_text((ROOT / "AGENTS.md").read_text().replace("examples/grasshopper/", "examples/"))
    docs_output = output / "docs"
    docs_output.mkdir(exist_ok=True)
    for pattern in ("*.md", "*.json"):
        for document in (ROOT / "docs").glob(pattern):
            shutil.copy2(document, docs_output / document.name)
    shutil.copytree(ROOT / "docs/agents", docs_output / "agents", dirs_exist_ok=True)
    shutil.copytree(ROOT / "docs/captures/v05", docs_output / "captures/v05", dirs_exist_ok=True)
    for guide in (*list((output / "examples").glob("*.md")), *list(docs_output.glob("*.md")), *list((docs_output / "agents").glob("*.md"))):
        content = guide.read_text()
        if guide.parent.name == "examples":
            content = content.replace("../../docs/", "../docs/")
        else:
            content = content.replace("examples/grasshopper/", "examples/")
        guide.write_text(content)
    # Include corresponding build source with GPL binary distributions.
    source_root = output / "source"
    if source_root.exists(): shutil.rmtree(source_root)
    for folder in ("plugin", "src", "scripts", "requirements", "tests", "vendor/lettuce"):
        shutil.copytree(ROOT / folder, source_root / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("bin", "obj", "__pycache__", "*.pyc", ".pytest_cache"))
    for name in ("pyproject.toml", "uv.lock", "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md", "AGENTS.md"):
        shutil.copy2(ROOT / name, source_root / name)
    archive = ROOT / "dist/Hawa-0.5.0-rh8.zip"
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
