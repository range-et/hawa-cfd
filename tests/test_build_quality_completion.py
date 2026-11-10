"""Exercise the real bundle writer using synthetic files and temporary destinations."""
import runpy
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts import build_plugin


@pytest.fixture
def package_tree(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    for folder in ("src/hawa", "vendor/lettuce/lettuce", "vendor/monad_system", "scripts",
                   "requirements", "tests", "tools", ".config", "docs/agents",
                   "examples/grasshopper", "examples/native-prototype"):
        (root / folder).mkdir(parents=True)
    files = {
        "plugin/Hawa.Rhino/bin/Release/net7.0/Hawa.Rhino.rhp": "rhino assembly",
        "plugin/Hawa.Rhino/bin/Release/net7.0/Hawa.Shared.dll": "shared assembly",
        "plugin/Hawa.Grasshopper/bin/Release/net7.0/Hawa.Grasshopper.gha": "GH assembly",
        "plugin/Bootstrap.py": "bootstrap",
        "src/hawa/__init__.py": "hawa source",
        "src/hawa/__pycache__/stale.pyc": "ignored cache",
        "vendor/lettuce/lettuce/__init__.py": "lettuce source",
        "vendor/monad_system/LICENSE": "vendored notice",
        "docs/plugin.md": "plugin guide",
        "docs/native-v0.5.md": "[capture](captures/test.png) [example](../examples/01.gh)",
        "docs/release-notes-v0.4.0.md": "release notes",
        "docs/verification-v0.4.json": "{}",
        "docs/moving-surfaces-v0.4.md": "motion limits",
        "docs/guide.md": "[example](../examples/grasshopper/01-test.gh)",
        "docs/agents/rhino-mcp.md": "[example](../../examples/grasshopper/01-test.gh)",
        "docs/captures/v05/test.png": "image fixture",
        "examples/grasshopper/01-test.gh": "supported archive",
        "examples/grasshopper/09-parametric-hull-galapagos.gh": "preserved user archive",
        "examples/grasshopper/README.md": "[guide](../../docs/guide.md)",
        "examples/native-prototype/native.3dm": "native model",
        "examples/native-prototype/native.3dmbak": "ignored backup",
        "examples/native-prototype/native.rhl": "ignored lock",
        "AGENTS.md": "[examples](examples/grasshopper/README.md)",
    }
    for name in ("pyproject.toml", "uv.lock", "LICENSE", "THIRD_PARTY_NOTICES.md",
                 "README.md", "features.md", "issues.md"):
        files[name] = name
    for name in ("LICENSE", "AUTHORS.rst", "PORTING.md", "upstream.json"):
        files["vendor/lettuce/" + name] = name
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    monkeypatch.setattr(build_plugin, "ROOT", root)
    output, archive = tmp_path / "bundle", tmp_path / "bundle.zip"
    monkeypatch.setattr(sys, "argv", ["build_plugin", "--output", str(output), "--archive", str(archive)])
    return root, output, archive


def test_refresh_build_bundle_and_temporary_install(package_tree, monkeypatch, tmp_path, capsys):
    root, output, archive = package_tree
    for folder in ("python/hawa", "python/lettuce", "examples", "source"):
        stale = output / folder / "removed.txt"
        stale.parent.mkdir(parents=True)
        stale.write_text("stale")
    libraries = tmp_path / "synthetic-Libraries"
    sys.argv += ["--install", str(libraries)]
    commands = []
    monkeypatch.setattr(build_plugin.subprocess, "run", lambda command, **kwargs: commands.append((command, kwargs)))
    build_plugin.main()
    assert [Path(command[2]).name for command, _ in commands] == ["Hawa.Grasshopper", "Hawa.Rhino"]
    assert all(command[:2] == ["dotnet", "build"] and kwargs == {"check": True} for command, kwargs in commands)
    assert not list(output.rglob("removed.txt"))
    assert not list(output.rglob("*.new"))
    assert not list(output.rglob("*.pyc"))
    assert not list(output.rglob("09-parametric-hull-galapagos.gh"))
    assert (root / "examples/grasshopper/09-parametric-hull-galapagos.gh").read_text() == "preserved user archive"
    assert not (output / "examples/native-prototype/native.3dmbak").exists()
    assert not (output / "examples/native-prototype/native.rhl").exists()
    assert (output / "README.md").read_text() == "[capture](docs/captures/test.png) [example](examples/01.gh)"
    assert (output / "examples/README.md").read_text() == "[guide](../docs/guide.md)"
    assert (output / "docs/guide.md").read_text() == "[example](../examples/01-test.gh)"
    assert (output / "docs/agents/rhino-mcp.md").read_text() == "[example](../../examples/01-test.gh)"
    assert (output / "AGENTS.md").read_text() == "[examples](examples/README.md)"
    assert (output / "docs/captures/v05/test.png").read_text() == "image fixture"
    assert (output / "moving-surfaces-v0.4.md").read_text() == "motion limits"
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        for source in output.rglob("*"):
            if source.is_file():
                relative = source.relative_to(output)
                assert bundle.read(str(Path("Hawa") / relative)) == source.read_bytes()
                assert (libraries / "Hawa" / relative).read_bytes() == source.read_bytes()
    assert not list(libraries.rglob("*.new"))
    assert "Installed: " in capsys.readouterr().out


def test_invalid_install_path_is_rejected_before_any_build(package_tree, monkeypatch, tmp_path):
    _, output, archive = package_tree
    sys.argv += ["--install", str(tmp_path / "HaWa")]
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid destination started a compiler")
    monkeypatch.setattr(build_plugin.subprocess, "run", unexpected)
    with pytest.raises(SystemExit) as error:
        build_plugin.main()
    assert error.value.code == 2
    assert not output.exists() and not archive.exists()


def test_compiler_failure_does_not_publish_a_bundle(package_tree, monkeypatch):
    _, output, archive = package_tree
    def failed(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(build_plugin.subprocess, "run", failed)
    with pytest.raises(subprocess.CalledProcessError):
        build_plugin.main()
    assert not output.exists() and not archive.exists()


def test_package_only_requires_the_tested_release_assemblies(package_tree, monkeypatch):
    root, _, archive = package_tree
    sys.argv += ["--package-only"]
    (root / "plugin/Hawa.Rhino/bin/Release/net7.0/Hawa.Rhino.rhp").unlink()
    def unexpected(*args, **kwargs):
        pytest.fail("Package-only mode started a compiler")
    monkeypatch.setattr(build_plugin.subprocess, "run", unexpected)
    with pytest.raises(FileNotFoundError, match="Hawa.Rhino.rhp"):
        build_plugin.main()
    assert not archive.exists()


def test_cli_entrypoint_help_never_builds(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["build_plugin", "--help"])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(Path(build_plugin.__file__)), run_name="__main__")
    assert error.value.code == 0
    assert "--package-only" in capsys.readouterr().out
