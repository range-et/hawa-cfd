# Function coverage gate

[Function matrix](function-test-matrix.md) · [Complete machine record](function-tests/matrix.json) · [Baseline](../tests/coverage/function-baseline.json)

[Local review and gate results](review-function-testing.md).

The matrix records each function's source, signature, visibility, available
docstring, executed lines/branches and tests that exercised it. It is generated
from source syntax and fresh test execution. A function with no docstring retains
its signature; the tool does not invent a behavioral contract.

## Scope and evidence

- All first-party Python under `src/hawa`, `scripts`, `tools` and `plugin`:
  functions, methods, async functions, properties, nested functions and lambdas.
- All explicit C# methods, constructors, accessors, operators, local functions
  and lambdas under `plugin`. Roslyn parses the syntax without loading Rhino.
- Coverage.py 7.10.7 measures Python lines and branches. Python's call profiler
  records actual function entries during passing pytest cases. Imports and
  defining an unused function do not earn function coverage. Worker-thread test
  attribution is temporal, using pytest's current test; it is not causal tracing.
- Coverlet 10.1.0 instruments the separate .NET StateContracts executable. It
  exercises linked production sources with Rhino/transport doubles. C# evidence
  names the suite, not an individual case. Shared source lines cannot distinguish
  two methods and do not earn either method automatic credit.
- C# host-only code is **unmeasured**, not passed. Abstract declarations and
  compiler-generated auto-accessors have no explicit source body and are marked
  `declaration`. Implicit compiler-generated methods are outside the inventory.
- Third-party `vendor/lettuce`, tests themselves, generated `bin`/`obj` output,
  C# verification scripts and the Roslyn extractor's top-level implementation
  are excluded from the product inventory. The extractor has an executable
  parser regression test. Upstream parity, host gates and scientific benchmarks
  remain separate requirements.

Python lambdas sharing one source line cannot be distinguished by the Python 3.9
profiler. They receive no automatic coverage credit; split them onto separate
lines or use named functions. Function coverage means observed execution in a
passing test. It cannot prove assertion quality, all branches, or physical accuracy.

## Run locally

Install the repository's test extra (now including coverage.py), and the .NET 10
SDK used by the existing state contracts. No production/runtime dependency changes.
The runner restores the repository-pinned Coverlet developer tool automatically.

```sh
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/python tools/function_coverage.py run --output results/function-coverage-NEW
.venv/bin/python tools/function_coverage.py render --output results/function-coverage-NEW > docs/function-test-matrix.md
cp results/function-coverage-NEW/matrix.json docs/function-tests/matrix.json
.venv/bin/python tools/function_coverage.py check --output docs/function-tests
```

Use a new output directory on every run. The runner executes the full Python
suite and state contracts, rejects failed runs and checks that source/tests/tools
did not change during measurement. Checks reject stale source hashes, missing or
duplicate function rows and incomplete test outcomes. Coverage does not start
Rhino, install a plugin, run the long atmospheric benchmarks or silently reuse
an old report. `PYTEST_ADDOPTS` and configured selectors cannot narrow the run.

## Ratchet policy

The initial baseline records the existing covered functions and outstanding
coverage debt. It is not a claim of complete coverage. The gate fails when:

1. A new executable function has no measured coverage.
2. A previously covered function loses coverage.
3. An uncovered/unmeasured function changes without gaining coverage.
4. The source, tests, toolchain or inventory no longer match the report.

Unchanged historical gaps remain visible under HAWA-026. There is no automatic
baseline regeneration or exemption command. When retiring a gap, update that
baseline entry to its freshly measured `covered` status and fingerprint so future
regressions also fail. Deleting a function is allowed. Tests for a new host method
should extract/link testable logic into StateContracts, or extend the instrumented
host evidence pipeline; a written test name alone is not execution evidence.

Pull-request CI reads the baseline from the base commit using `--base-ref`, so a
PR cannot exempt its new functions by editing its own baseline. The initial
adoption run uses the introduced baseline only when the base has none; that initial
debt must be reviewed. CI also checks that the committed matrix matches the source.
The workflow is added locally; a GitHub-hosted run still requires pushing it.

G2 requires this function gate for code changes. G6 still checks supported node
combinations and examples. CUDA/MPS skips on CPU CI remain unverified hardware,
and passing this gate cannot close atmospheric numerical-validation failures.

## Tool references

- [Python profiling interface](https://docs.python.org/3.9/library/sys.html#sys.setprofile)
- [Coverage.py API](https://coverage.readthedocs.io/en/7.10.7/api_coverage.html)
- [Coverlet console instrumentation](https://github.com/coverlet-coverage/coverlet/blob/master/Documentation/GlobalTool.md)
