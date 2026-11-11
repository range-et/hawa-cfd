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

Run the gate in the Python 3.9 `.venv`, never in the Python 3.12 `.venv-dev`. The
call profiler relies on Python 3.9 `sys.setprofile` and line-event behaviour, and
the committed matrix and baseline were measured on 3.9; CI runs this gate on
3.9.25. `.venv-dev` is for developer tools only (ruff, and mutmut 3.x once
[#67](https://github.com/range-et/hawa-cfd/issues/67) ports the studies). See the
[README](../README.md#development) for both environments.

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
GitHub runs the gate for pull requests and pushes to `main`.

G2 requires this function gate for code changes. G6 still checks supported node
combinations and examples. CUDA/MPS skips on CPU CI remain unverified hardware,
and passing this gate cannot close atmospheric numerical-validation failures.

## Tool references

- [Python profiling interface](https://docs.python.org/3.9/library/sys.html#sys.setprofile)
- [Coverage.py API](https://coverage.readthedocs.io/en/7.10.7/api_coverage.html)
- [Coverlet console instrumentation](https://github.com/coverlet-coverage/coverlet/blob/master/Documentation/GlobalTool.md)

## Local Rhino acceptance alongside automated coverage

For code PRs, the creator also performs the
[local Rhino acceptance review](local-rhino-acceptance.md): open all supported
examples, execute and render each workflow, inspect its numbers and images, and
record the actual build/environment/device, settings, steps/time, evidence,
failures and omissions. Preserve user documents and modified legacy 09.

This is an important soft gate reviewed by the maintainer, with explicit
responsibility for the merge decision; it does not require a self-hosted CI
runner. Automated GitHub tests and mutation/coverage checks remain independent.
Host example attestation does not count as instrumented function/line coverage,
and headless doubles do not establish native scheduling or geometry correctness.
Unmeasured host code stays visible. Numerical sanity and rendered fields also do
not replace the independent physical-qualification gates.

## Strict headless line and function check

The target is **100% executable functions and 100% executable lines** across
first-party Hawa Python and C#. CI enforces that threshold for all first-party
Python and the instrumented headless C# files, in addition to the base-commit
ratchet. It rejects missing line evidence and Python line exclusions. It does
not claim complete branch coverage or instrumented Rhino-host coverage.

```sh
.venv/bin/python tools/function_coverage.py check --output results/function-coverage-NEW --strict --coverage-scope headless
```

Omit `--coverage-scope headless` to audit the entire inventory: unmeasured
Rhino-dependent C# remains a reported failure of the global 100% target. The
local example acceptance review above supplies separate host evidence; it does
not convert those rows into measured passes. Making GitHub checks required for
merging is a repository branch-protection/ruleset decision owned by maintainers.

## Mutation checks

The Python mutation workflow runs on PRs and pushes to `main`. It currently
covers the CLI and runtime admission (`backends`, `cases`, `boundary_contracts`)
with pinned mutmut 2.4.5 in fresh copied source trees, in the Python 3.9 `.venv`.
mutmut 3.x needs Python 3.10 or newer, so
[#67](https://github.com/range-et/hawa-cfd/issues/67) will move these studies to
the Python 3.12 `.venv-dev` (mutmut 3.7.0 in the `tools` dependency group; 3.8
needs a newer click than the production pin). Mutation results measured on 3.12
cover test logic, not interpreter behaviour: the same tests must also pass on 3.9,
which stays the authoritative environment. On 3.12 the suite skips tests marked
`production_python` (entry points such as `parity_worker.py`, `compare_engines.py`
and `verify_cuda.py` that refuse non-3.9 interpreters), so 3.12 mutation runs get
no kills from them. This is four-module scope,
not whole-codebase mutation coverage. Install the isolated developer dependencies:

```sh
.venv/bin/python -m pip install -r tools/mutation/requirements.txt
bash tools/mutation/run_cli.sh results/cli-mutation-NEW
.venv/bin/python tools/mutation/check_results.py results/cli-mutation-NEW
bash tools/mutation/run_runtime_admission.sh results/admission-mutation-NEW
.venv/bin/python tools/mutation/check_results.py results/admission-mutation-NEW --policy tools/mutation/runtime-admission-policy.json
```

The HAWA-001 KBC studies are run locally, not in the workflow. The collision
study mutates only the lines of vendored `kbc_collision.py` changed since the PR
base (mutmut patch mode needs `whatthepatch` and full Git history). The diagnostic
study mutates the whole of `scripts/diagnose_kbc_parity.py`, which is new to main
with that PR. CUDA/MPS hardware cases are deselected by name (so CPU-run tests
must not carry `cuda` or `mps` in their ids), and actual device runs are separate
evidence:

```sh
bash tools/mutation/run_kbc.sh collision results/kbc-collision-mutation-NEW
.venv/bin/python tools/mutation/check_results.py results/kbc-collision-mutation-NEW --policy tools/mutation/kbc-collision-policy.json
bash tools/mutation/run_kbc.sh diagnostic results/kbc-diagnostic-mutation-NEW
.venv/bin/python tools/mutation/check_results.py results/kbc-diagnostic-mutation-NEW --policy tools/mutation/kbc-diagnostic-policy.json
```

Do not run `mutmut results` inside a study directory while it is still mutating:
it reads the temporarily mutated source and corrupts the run's cache.

mutmut 2.4.5 marks a mutant killed only when the test command exits with 1. A
mutant that breaks import makes pytest stop at collection (exit 2), which mutmut
reports as survived. Review such survivors as collection errors: they are
detected, but they are neither assertion kills nor equivalents.

The helpers preserve mutmut's raw exit (2 when mutants survive); run the policy
checker afterward. Acceptance requires the exact reviewed source/test hashes,
all collected controls passing, a complete mutation inventory, no timeout/error/
skip, and the exact reviewed survivor diffs. Unexpected survivors fail; reviewed
equivalents and diagnostic decorations are reported separately, never as kills.
Source or test edits require a fresh run and review, not blind policy regeneration.

The HAWA-003 scope (`run_atmospheric_precision.sh`, `atmospheric-precision-policy.json`)
mutates only the lines in `tools/mutation/atmospheric-precision.patch`: the
`storage_resolution` diagnostic and helpers in `neutral.py`, the `dissipation_storage`
quality field and `scripts/verify_atmospheric_precision.py`. It uses mutmut's
`--use-patch-file`, which needs `whatthepatch`. Regenerate the patch only together
with a fresh run and review. Two mutmut 2.4.5 behaviours matter here:
- mutmut counts any pytest exit other than 1 as survival. A mutant that breaks
  import (pytest exit 2) is recorded in the policy as a collection error, not a kill.
- Do not run `mutmut show` against a cache while a run is in progress. It rewrites
  cached line records from the currently mutated file and crashes the run with
  `Attribute Mutant.line is required`.

See the [CLI record](verification-cli-mutation.json),
[runtime study](review-runtime-quality.md) and
[mutmut 2.4.5 package](https://pypi.org/project/mutmut/2.4.5/).

The HAWA-004 boundary study is a separate local run. It mutates only lines the
PR changes (`--use-patch-file`, with whatthepatch 1.0.7): in
`src/hawa/neutral_external.py` and `tools/mutation/check_results.py` against
`f29fe01`, plus the reflection-harness lines changed by the PR #66 review fixes
(against `d0b54e2`). The rest of the harness is new in that PR and is
line-covered by asserting tests, but it is outside the mutation scope. The tests
are `test_mutation_policy.py`, `test_neutral_external.py` (without the CPU/MPS
device test) and `test_boundary_reflection.py`:

```sh
bash tools/mutation/run_boundary_reflection.sh results/boundary-mutation-NEW
.venv/bin/python tools/mutation/check_results.py results/boundary-mutation-NEW --policy tools/mutation/boundary-reflection-policy.json
```

It takes about 30 minutes on one CPU and stays local, outside CI. A policy may list
several `control_test_files`. See the [HAWA-004 record](boundary-reflection-review.md).

For changed lines only, `tools/mutation/run_device_smoke.sh NEW_DIR BASE` passes
`git diff BASE` to mutmut's `--use-patch-file` for the device smoke gate's added
lines; check it with `--policy tools/mutation/device-smoke-policy.json` (494 mutants,
485 killed, 9 reviewed). It needs `whatthepatch` from the same requirements file and
is a local PR record, not a CI study.
