"""Inventory first-party functions and reject new or changed coverage debt.

Python 3.9. AST inspection never imports product modules. Coverage.py measures
lines/branches; call profiling prevents import-only and nested-definition false
positives. C# uses Roslyn syntax and Coverlet data from the state-contract host.
"""
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "tests/coverage/function-baseline.json"
SCHEMA = 1


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sources(root):
    """All maintained first-party Python plus plugin C#; no vendored/generated code."""
    paths = []
    for directory in ("src/hawa", "scripts", "tools", "plugin"):
        for path in (root / directory).rglob("*"):
            if any(p in ("bin", "obj", "__pycache__") for p in path.parts):
                continue
            if path.suffix == ".py" or (path.suffix == ".cs" and directory == "plugin"):
                paths.append(path.relative_to(root).as_posix())
    return sorted(paths)


def snapshot(root):
    """Bind evidence to sources, tests, toolchain and coverage policy, including additions."""
    paths = set(sources(root))
    for directory in ("tests", "tools/FunctionInventory"):
        paths.update(p.relative_to(root).as_posix() for p in (root / directory).rglob("*")
                     if p.suffix in (".py", ".cs", ".csproj") and not {"bin", "obj", "__pycache__"}.intersection(p.parts))
    paths.update(p for p in ("pyproject.toml", ".config/dotnet-tools.json") if (root / p).exists())
    return {p: digest((root / p).read_bytes()) for p in sorted(paths)}


def python_functions(path, text):
    """Include methods, properties, nested/async functions and anonymous lambdas."""
    tree = ast.parse(text, filename=path)
    rows = []
    counts = Counter()

    def visit(node, parents=()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            name = getattr(node, "name", "<lambda>")
            key = (parents, name)
            counts[key] += 1
            suffix = "#" + str(counts[key]) if counts[key] > 1 or isinstance(node, ast.Lambda) else ""
            qualified = ".".join(parents + (name + suffix,))
            decorators = getattr(node, "decorator_list", [])
            start = min([node.lineno] + [n.lineno for n in decorators])
            if isinstance(node, ast.Lambda):
                body_lines = set(range(node.body.lineno, node.end_lineno + 1))
            else:
                body_lines = set(range(node.body[0].lineno, node.end_lineno + 1))
            for child in ast.walk(node):
                if child is not node and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                    body_lines.difference_update(range(child.lineno, child.end_lineno + 1))
            returns = ast.unparse(node.returns) if getattr(node, "returns", None) else "unannotated"
            signature = name + "(" + ast.unparse(node.args) + ") -> " + returns
            if decorators:
                signature = " ".join("@" + ast.unparse(d) for d in decorators) + " " + signature
            rows.append(dict(path=path, language="Python", name=qualified,
                             signature=signature, kind=type(node).__name__, line=node.lineno,
                             end_line=node.end_lineno, first_line=start, code_name=name,
                             body_lines=sorted(body_lines), declaration=False,
                             visibility="private" if name.startswith("_") else "public/conventional",
                             summary=(ast.get_docstring(node) or "").split("\n")[0] if not isinstance(node, ast.Lambda) else "",
                             fingerprint=digest(ast.dump(node, include_attributes=False).encode())))
            parents = parents + (name + suffix,)
        elif isinstance(node, ast.ClassDef):
            parents = parents + (node.name,)
        for child in ast.iter_child_nodes(node):
            visit(child, parents)

    visit(tree)
    return rows


def inventory(root):
    rows, cs = [], []
    for path in sources(root):
        if path.endswith(".py"):
            rows.extend(python_functions(path, (root / path).read_text(encoding="utf-8-sig")))
        else:
            cs.append(path)
    if cs:
        project = ROOT / "tools/FunctionInventory/FunctionInventory.csproj"
        subprocess.run(["dotnet", "build", str(project), "--nologo", "-v:q"], check=True, capture_output=True)
        dll = project.parent / "bin/Debug/net10.0/FunctionInventory.dll"
        result = subprocess.run(["dotnet", str(dll)] + cs, cwd=root, check=True, capture_output=True, text=True)
        rows.extend(json.loads(result.stdout))
    for row in rows:
        row["id"] = row["path"] + "::" + row["name"]
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate function identities; inventory cannot be trusted")
    return sorted(rows, key=lambda r: (r["path"], r["line"], r["name"]))


class CallEvidence:
    """Record actual entries during passing pytest cases, including worker threads.

    Worker attribution is temporal (PYTEST_CURRENT_TEST), not causal tracing.
    Names identify tests that exercised a function, not necessarily direct tests.
    """
    def __init__(self, root, paths):
        self.files = {str((root / p).resolve()): p for p in paths}
        self.calls = defaultdict(set)
        self.outcomes = defaultdict(list)
        self.collected = []

    def profile(self, frame, event, arg):
        if event == "call":
            code = frame.f_code
            path = self.files.get(code.co_filename)
            if path:
                case = os.environ.get("PYTEST_CURRENT_TEST", "").rsplit(" (", 1)[0]
                if case:
                    self.calls[(path, code.co_firstlineno, code.co_name)].add(case)

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report):
        self.outcomes[report.nodeid].append((report.when, report.outcome))

    def report(self):
        passed = {case for case, results in self.outcomes.items()
                  if ("call", "passed") in results and all(result == "passed" for _, result in results)}
        return dict(collected=self.collected, passed=sorted(passed),
                    outcomes=dict(self.outcomes), calls=[dict(path=p, first_line=n, code_name=f, tests=sorted(t & passed))
                    for (p, n, f), t in sorted(self.calls.items())])


def measure_python(root, output):
    """Run the complete suite in a fresh process; no test selectors are accepted."""
    import coverage
    import pytest
    os.chdir(root)
    sys.path.insert(0, str(root))
    paths = [p for p in sources(root) if p.endswith(".py")]
    evidence = CallEvidence(root, paths)
    cov = coverage.Coverage(data_file=str(output / ".coverage"), branch=True, config_file=False,
                            source=[str(root / p) for p in ("src/hawa", "scripts", "tools", "plugin") if (root / p).is_dir()])
    cov.start()
    sys.setprofile(evidence.profile)
    threading.setprofile(evidence.profile)
    try:
        code = int(pytest.main(["tests", "-q", "-o", "addopts=", "--junitxml=" + str(output / "pytest.xml")], plugins=[evidence]))
    finally:
        sys.setprofile(None)
        threading.setprofile(None)
        cov.stop()
        cov.save()
    cov.json_report(outfile=str(output / "python.json"))
    result = evidence.report()
    result["exit_code"] = code
    (output / "calls.json").write_text(json.dumps(result, indent=2) + "\n")
    return code


def csharp_lines(data, root):
    result = defaultdict(dict)
    for files in data.values():
        for filename, classes in files.items():
            try:
                path = Path(filename).resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            for methods in classes.values():
                for method in methods.values():
                    for line, hits in method.get("Lines", {}).items():
                        n = int(line)
                        result[path][n] = max(result[path].get(n, 0), hits)
    return result


def annotate(rows, python, calls, cs):
    entries = {(c["path"], c["first_line"], c["code_name"]): c["tests"] for c in calls["calls"]}
    keys = Counter((r["path"], r.get("first_line"), r.get("code_name")) for r in rows if r["language"] == "Python")
    owners = Counter((r["path"], n) for r in rows if r["language"] == "C#" for n in r["body_lines"])
    result = []
    for original in rows:
        row = dict(original)
        own = set(row.pop("body_lines"))
        if row["language"] == "Python":
            file = python.get("files", {}).get(row["path"], {})
            executed = set(file.get("executed_lines", [])) & own
            missing = set(file.get("missing_lines", [])) & own
            key = (row["path"], row["first_line"], row["code_name"])
            tests = entries.get(key, []) if keys[key] == 1 else []
            branches = [b for b in file.get("executed_branches", []) if b[0] in own]
            missing_branches = [b for b in file.get("missing_branches", []) if b[0] in own]
            row["branches"] = dict(hit=len(branches), total=len(branches) + len(missing_branches))
        else:
            file = cs.get(row["path"], {})
            executed = {n for n, hits in file.items() if hits > 0} & own
            missing = {n for n, hits in file.items() if hits == 0} & own
            # A line shared by multiple methods/closures cannot prove which ran.
            unique_hits = {n for n in executed if owners[(row["path"], n)] == 1}
            tests = ["tests/dotnet/StateContracts (suite-level)"] if unique_hits else []
            row["branches"] = None
        row.update(tests=tests, lines=dict(hit=len(executed), total=len(executed | missing)),
                   status="declaration" if row["declaration"] else "covered" if tests else "uncovered" if file else "unmeasured")
        result.append(row)
    return result


def strict_gate(root, report, python, cs, scope="all"):
    """Require every executable function and measured source line; no debt allowance."""
    failures = []
    for row in report['functions']:
        if scope == 'headless' and row['language'] == 'C#' and row['path'] not in cs:
            continue
        if row['status'] not in ('covered', 'declaration'):
            failures.append('Function not covered: ' + row['id'])
    cs_paths = {r['path'] for r in report['functions']
                if r['language'] == 'C#' and not r['declaration']}
    for path in sources(root):
        if path.endswith('.py'):
            evidence = python.get('files', {}).get(path)
            if evidence is None:
                failures.append('Python source unmeasured: ' + path)
                continue
            required = {'executed_lines', 'missing_lines', 'excluded_lines', 'summary'}
            if not required.issubset(evidence):
                failures.append('Incomplete Python line evidence: ' + path)
                continue
            executed = set(evidence['executed_lines'])
            missing = evidence['missing_lines']
            excluded = evidence['excluded_lines']
            if executed.intersection(missing) or evidence['summary'].get('num_statements') != len(executed | set(missing)):
                failures.append('Inconsistent Python line evidence: ' + path)
            if missing:
                failures.append('Python lines not covered: ' + path + ': ' + str(missing))
            if excluded:
                failures.append('Python line exclusions require removal: ' + path + ': ' + str(excluded))
        elif path in cs_paths:
            if scope == 'headless' and path not in cs:
                continue
            evidence = cs.get(path)
            if not evidence:
                failures.append('C# source unmeasured: ' + path)
            else:
                missing = sorted(n for n, hits in evidence.items() if hits <= 0)
                if missing:
                    failures.append('C# lines not covered: ' + path + ': ' + str(missing))
    return failures


def gate(rows, baseline):
    """Existing debt is allowed only while the exact function remains unchanged."""
    if baseline.get("schema") != SCHEMA or not isinstance(baseline.get("functions"), dict):
        raise ValueError("Invalid function baseline")
    failures = []
    for row in rows:
        if row["status"] in ("covered", "declaration"):
            continue
        old = baseline["functions"].get(row["id"])
        if not old:
            failures.append("NEW untested: " + row["id"])
        elif old["status"] == "covered":
            failures.append("LOST coverage: " + row["id"])
        elif old["fingerprint"] != row["fingerprint"]:
            failures.append("CHANGED untested: " + row["id"])
    return failures


def validate_report(root, report):
    if report.get("schema") != SCHEMA or report.get("snapshot") != snapshot(root):
        raise ValueError("Missing or stale evidence: sources, tests or tooling changed; rerun")
    if report.get("python_exit") != 0 or not report.get("tests", {}).get("passed"):
        raise ValueError("Missing or failed test execution")
    tests = report["tests"]
    collected = tests.get("collected", [])
    outcomes = tests.get("outcomes", {})
    if not collected or len(set(collected)) != len(collected) or set(collected) != set(outcomes):
        raise ValueError("Incomplete or duplicated test execution inventory")
    passed = sorted(case for case, values in outcomes.items()
                    if ["call", "passed"] in values and all(result == "passed" for _, result in values))
    if passed != tests["passed"] or any(result == "failed" for values in outcomes.values() for _, result in values):
        raise ValueError("Test outcome evidence disagrees or contains failures")
    expected = inventory(root)
    actual = report.get("functions", [])
    if [(r["id"], r["fingerprint"]) for r in actual] != [(r["id"], r["fingerprint"]) for r in expected]:
        raise ValueError("Incomplete, duplicated or altered function inventory")
    if any(r["status"] == "covered" and not r.get("tests") for r in actual):
        raise ValueError("Covered function lacks test evidence")
    if any(r["language"] == "Python" and not set(r["tests"]).issubset(passed) for r in actual):
        raise ValueError("Function names an absent or unsuccessful test")


def render(report):
    """Portable committed view; raw measurements remain in the run directory."""
    counts = Counter(r["status"] for r in report["functions"])
    lines = ["# Function test matrix", "", "Generated by `tools/function_coverage.py`; see [policy and reproduction](function-testing.md).", "",
             "Coverage records execution, not assertion quality or physical validation. C# state coverage is suite-level; host-only methods remain unmeasured.", "",
             "Inventory: " + ", ".join(str(v) + " " + k for k, v in sorted(counts.items())) + ".", "",
             "| Function / source | Surface | Coverage | Tests |", "| --- | --- | --- | --- |"]
    for row in report["functions"]:
        link = "[" + html.escape(row["name"]) + "](../" + row["path"] + "#L" + str(row["line"]) + ")"
        surface = row["language"] + "; " + row["visibility"] + "; `" + row["signature"].replace("`", "'") + "`"
        if row["summary"]:
            surface += " — " + html.escape(row["summary"].replace("\n", " "))
        coverage = row["status"] + "; lines " + str(row["lines"]["hit"]) + "/" + str(row["lines"]["total"])
        if row["branches"] is not None:
            coverage += "; branches " + str(row["branches"]["hit"]) + "/" + str(row["branches"]["total"])
        tests = "<br>".join(row["tests"][:4]) or "—"
        if len(row["tests"]) > 4:
            tests += "<br>+" + str(len(row["tests"]) - 4) + " more in [JSON](function-tests/matrix.json)"
        lines.append("| " + " | ".join(v.replace("|", "&#124;").replace("\n", " ") for v in (link, surface, coverage, tests)) + " |")
    return "\n".join(lines) + "\n"


def run(root, output):
    """Fresh output and unchanged inputs are mandatory; failures never reuse old data."""
    output.mkdir(parents=True, exist_ok=False)
    before = snapshot(root)
    rows = inventory(root)
    env = dict(os.environ)
    env.pop("PYTEST_ADDOPTS", None)
    with (output / "pytest.log").open("w") as log:
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "_measure", "--root", str(root), "--output", str(output)],
                              cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
    if proc.returncode:
        raise ValueError("Python test/measurement failure; inspect " + str(output / "pytest.log"))
    calls = json.loads((output / "calls.json").read_text())
    cs = {}
    state_project = root / "tests/dotnet/StateContracts/StateContracts.csproj"
    if state_project.exists():
        with (output / "state-contracts.log").open("w") as log:
            subprocess.run(["dotnet", "tool", "restore"], cwd=root, stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(["dotnet", "build", str(state_project), "-o", str(output / "state")], cwd=root, stdout=log, stderr=subprocess.STDOUT, check=True)
            dll = output / "state/StateContracts.dll"
            subprocess.run(["dotnet", "tool", "run", "coverlet", str(dll), "--target", "dotnet", "--targetargs", '"' + str(dll) + '"',
                            "--include-test-assembly", "--format", "json", "--output", str(output / "state.json")],
                           cwd=root, stdout=log, stderr=subprocess.STDOUT, check=True)
        cs = csharp_lines(json.loads((output / "state.json").read_text()), root)
        if not cs:
            raise ValueError("Empty C# instrumentation; cannot claim state coverage")
    if before != snapshot(root):
        raise ValueError("Inputs changed during measurement; discard and rerun")
    rows = annotate(rows, json.loads((output / "python.json").read_text()), calls, cs)
    report = dict(schema=SCHEMA, snapshot=before, python_exit=calls["exit_code"],
                  environment=dict(python=sys.version.split()[0], platform=platform.platform()),
                  tests={k: calls[k] for k in ("collected", "passed", "outcomes")}, functions=rows)
    (output / "matrix.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "matrix.md").write_text(render(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "check", "render", "_measure"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True, help="Fresh directory for run; existing run for check/render")
    parser.add_argument("--baseline", type=Path, default=Path(BASELINE))
    parser.add_argument("--base-ref", help="Read the baseline from a trusted Git base rather than this checkout")
    parser.add_argument("--strict", action="store_true", help="Require 100% first-party executable functions and lines; no historical debt allowance")
    parser.add_argument("--coverage-scope", choices=("all", "headless"), default="all", help="Headless scopes C# to instrumented source files; unmeasured host code remains reported")
    args = parser.parse_args(argv)
    root, output = args.root.resolve(), args.output.resolve()
    if args.command == "_measure":
        return measure_python(root, output)
    report = run(root, output) if args.command == "run" else json.loads((output / "matrix.json").read_text())
    validate_report(root, report)
    if args.command == "check" and output == root / "docs/function-tests":
        markdown = root / "docs/function-test-matrix.md"
        if not markdown.exists() or markdown.read_text() != render(report):
            raise ValueError("Committed Markdown matrix is stale; regenerate it from this report")
    if args.command == "render":
        print(render(report), end="")
        return 0
    if args.base_ref:
        result = subprocess.run(["git", "show", args.base_ref + ":" + args.baseline.as_posix()], cwd=root, capture_output=True, text=True, check=True)
        baseline = json.loads(result.stdout)
    else:
        baseline = json.loads((root / args.baseline).read_text())
    failures = gate(report["functions"], baseline)
    if args.strict:
        python = json.loads((output / "python.json").read_text())
        state = json.loads((output / "state.json").read_text())
        failures.extend(strict_gate(root, report, python, csharp_lines(state, root), args.coverage_scope))
    print(json.dumps(dict(scope=args.coverage_scope if args.strict else "baseline ratchet", functions=dict(Counter(r["status"] for r in report["functions"])), unmeasured_host_functions=sum(r["language"] == "C#" and r["status"] == "unmeasured" for r in report["functions"]), failures=failures), indent=2))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
