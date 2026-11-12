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
- The Grasshopper host harness in the same executable links whole component
  source files (`Runtime.cs`, `FieldTools.cs`, `FieldViewComponents.cs`,
  `ResultsComponents.cs`, `SolveComponents.cs`, `AnimationComponents.cs`) against Grasshopper and
  RhinoCommon doubles (`GrasshopperDouble.cs`, `HostDouble.cs`). Its tests
  (`ComponentContracts.cs`) drive `SolveInstance`, archive reads and document
  context changes and assert outputs, labels, runtime messages and bridge
  requests. The strict headless check covers every linked file, so a file is
  linked only when all of its functions and lines are tested. Unlinked
  component types that linked code names get empty test stand-ins
  (`ComponentStandIns.cs`) and stay unmeasured. To measure another
  component, link its whole file or move it into a file the harness links. The
  doubles do not prove GH solution ordering, scheduling or canvas drawing.
- The inventory credits a lambda only from a line that holds its own body
  tokens. In linked files, put each lambda body on its own line. Token
  fingerprints ignore whitespace, so this layout does not change a function's
  fingerprint.
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
3.9.25. `.venv-dev` is for developer tools only (ruff and the
[mutation checks](#mutation-checks)). See the
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

Mutation studies use pinned **mutmut 3.7.0** in the Python 3.12 `.venv-dev`
(the `tools` dependency group; 3.8 needs a newer click than the production pin).
mutmut 3 forks one worker per CPU and runs each mutant against only the tests
that reached its function during a stats run. Each study runs in a fresh copied
source tree with no cache. The Python mutation workflow runs the CLI and runtime
admission (`backends`, `cases`, `boundary_contracts`) studies on PRs and pushes
to `main`; its required checks keep their names, `cli mutations` and
`runtime-admission mutations`. The other studies are local PR records.

Mutation results measured on 3.12 cover test logic, not interpreter behaviour:
the same tests must also pass on 3.9, which stays the authoritative environment.
On 3.12 the suite skips tests marked `production_python` (entry points such as
`parity_worker.py`, `compare_engines.py` and `verify_cuda.py` that refuse non-3.9
interpreters), so 3.12 mutation runs get no kills from them; a study deselects
them (`-m 'not production_python'`), and a mutant only they could reach is
`no tests` (no selected test ran its function) or `survived` (another test ran
it without asserting the change). Either way it is a reviewed survivor, never a
kill. This matters for the device smoke study: 136 of its 209 reviewed survivors
are reached only by the deselected `production_python` test
`test_real_builders_pass_their_criteria_on_the_cpu_proxy`, which the 3.9 suite
still runs (see [the device smoke gate](device-smoke.md#verification-of-the-gate-itself)).
These are bounded scopes, not whole-codebase mutation coverage.

```sh
UV_PROJECT_ENVIRONMENT=.venv-dev uv sync --python 3.12 --extra test --group tools
bash tools/mutation/run_cli.sh results/cli-mutation-NEW
.venv-dev/bin/python tools/mutation/check_results.py results/cli-mutation-NEW
bash tools/mutation/run_runtime_admission.sh results/admission-mutation-NEW
.venv-dev/bin/python tools/mutation/check_results.py results/admission-mutation-NEW --policy tools/mutation/runtime-admission-policy.json
```

`MUTMUT_MAX_CHILDREN` overrides the worker count (default: the CPU count). The
runners pin one CPU thread per process and hide CUDA: workers fork from a parent
that has imported torch, so a study must not initialise an accelerator.
mutmut 3 forks with `os.fork` directly and has no `forkserver` option. macOS and
Linux work; Windows needs WSL.

### How a study is built

Each `tools/mutation/run_*.sh` names its files and tests and sources
[`lib.sh`](../tools/mutation/lib.sh), which copies the tree, hashes the reviewed
files before and after, runs the control suite, runs mutmut through
[`mutmut3.py`](../tools/mutation/mutmut3.py) and exports the evidence.
`mutmut3.py` adds two things around the pinned release:

- **Changed lines only.** mutmut 3 dropped `--use-patch-file`. A PR-scoped runner
  prints `git diff --no-prefix BASE -- FILES`; `mutmut3.py changed-lines` turns
  the lines that diff adds into `scope.json`, and only nodes starting on those
  lines are mutated. Removed and context lines, and files the patch does not
  name, get no mutants. `tests/test_mutation_policy.py` runs the real mutmut on a
  small project and checks that a line outside the patch is not mutated.
- **Import roots.** mutmut names a mutant after its file's module path and only
  activates it when the running function's `__module__` matches. Tests import
  harness scripts as top-level modules (`scripts` and `tools/mutation` on
  `sys.path`), so `--import-root scripts` names `scripts/device_smoke.py` as
  `device_smoke`, and puts the mutated copy first on `sys.path`. A test that loads
  a script with `importlib` must use that same module name.

`mutmut3.py` patches two internal functions of mutmut 3.7.0 for this and refuses
any other version. Bumping mutmut needs a review of those hooks and fresh runs.

### What mutmut 3 does not mutate

mutmut 3 mutates only code inside functions and methods. These are outside every
3.x inventory: module-level statements and tables, class bodies, functions with
any decorator other than a single `@staticmethod` or `@classmethod`, every method
of a decorated class (for example `@dataclass`), arguments of `len()` and
`isinstance()` calls, non-literal default arguments and annotations. Cover
behaviour there with direct asserting tests. mutmut 3 also has more operators
than 2.4.5 (for example removing one call argument or changing string case), so
a 3.x inventory is larger and is not comparable mutant by mutant with a 2.x one.

### Acceptance rules

[`check_results.py`](../tools/mutation/check_results.py) accepts only the exact
reviewed inventory, never a score threshold. It requires:

- the reviewed source and test hashes, unchanged during the run, in both the
  checkout and the study copy, and the policy's mutmut version;
- every collected control test passing, from every listed control file;
- `mutmut run` exit 0 (mutmut exits 1 when its clean run, forced-failure check
  or stats run fails);
- exactly the reviewed mutant names (count and SHA-256 of the sorted names);
- every survivor (`survived`, exit 0) and every `no tests` mutant (exit 33, no
  selected test reached its function) listed with its exact diff hash, status
  and a non-empty reason. Neither counts as a kill.

Only exit 1 (tests failed) is a kill. Any other outcome fails the check: timeouts,
signals and segfaults, `suspicious`, skipped, type-check filtered, not checked,
and pytest's internal-error exit 3, which mutmut itself reports as killed.

After a fresh run, `check_results.py DIR --policy POLICY --draft` prints the
policy the run implies. It keeps a survivor's reason only when its status and
diff hash are unchanged; new or changed survivors get an empty reason, which
the check rejects until someone reviews the diff in `mutations.diff` and writes
one. Kill non-equivalent survivors with tests instead. A non-equivalent
survivor accepted for now gets a reason starting `Unresolved` and stays a
tracked test gap; the 39 recorded by the 3.x port are listed in
[#85](https://github.com/range-et/hawa-cfd/issues/85). Source or test edits
need a fresh run and review, never blind regeneration.

### Studies

| Study | Scope | Tests | Run |
| --- | --- | --- | --- |
| `run_cli.sh` | whole `src/hawa/cli.py` | `test_cli.py` | CI |
| `run_runtime_admission.sh` | whole `backends`, `cases`, `boundary_contracts` | `test_runtime_admission.py` | CI |
| `run_boundary_reflection.sh` | HAWA-004 lines: `neutral_external.py` against `f29fe01` (now including the #73 lines), reflection-harness review-fix lines against `d0b54e2` | `test_neutral_external.py` (without the CPU/MPS device test), `test_boundary_reflection.py` (without the MPS mass-budget test) | local |
| `run_kbc.sh collision` | HAWA-001 lines of vendored `kbc_collision.py` against `f9a3a13` | `test_kbc_precision.py`, CPU cases | local |
| `run_kbc.sh diagnostic` | whole `scripts/diagnose_kbc_parity.py` | `test_kbc_parity_diagnostic.py`, CPU cases | local |
| `run_atmospheric_precision.sh` | HAWA-003 lines in `atmospheric-precision.patch` | `test_atmospheric_precision.py` | local |
| `run_device_smoke.sh` | device smoke gate lines against `8daf810` | `test_device_smoke.py`, without `production_python` | local |
| `run_mps_mass_budget.sh` | #73 node-first mass-budget lines of `neutral_external.py` against `cc407cc` | `test_neutral_external.py` (without the CPU/MPS device test) | local |
| `run_mutation_tooling.sh` | #67 lines of `check_results.py` and `mutmut3.py` against `5f2c899` | `test_mutation_policy.py` | local |
| `run_motion_schema.sh` | #68 lines of `src/hawa/motion.py` against `cc407cc` | `test_motion.py`, `test_payload_schemas.py`, two motion tests in `test_runtime_rejection_edges.py`; CPU cases | local |
| `run_validity_foundation.sh` | #80/#81/#82/#99 lines (validity foundation, item 5 field views: isosurface and plane partition, item 6 traces, and the shared MPS device lock) of `src/hawa/plugin.py`, `fields.py`, `field_collection.py` and `refinement.py` against `56b0728` (pathlines and their `recording.py` lines were removed by owner decision) | `test_fields.py`, `test_field_collection.py`, `test_plugin_service.py`, `test_recording.py`, `test_refinement.py`; CPU cases | local |
| `run_status_truth.sh` | #74 queued-state lines of `src/hawa/jobs.py` against `6b0744a` | `test_runtime_job_contracts.py`; CPU cases | local |

Commit before running a PR-scoped study: its patch is `git diff BASE` of the
committed files. PR #66 was squash-merged, so run `git fetch origin refs/pull/66/head`
once before the boundary reflection study to get `d0b54e2`. Each study's policy is `tools/mutation/<study>-policy.json`
(`kbc-collision` and `kbc-diagnostic` for the two KBC studies). Results are in
the [#67 record](https://github.com/range-et/hawa-cfd/issues/67).

The [CLI record](verification-cli-mutation.json) and
[runtime study](review-runtime-quality.md) describe the earlier mutmut 2.4.5
runs. Those policies are kept unchanged in
[`tools/mutation/mutmut2-historical`](../tools/mutation/mutmut2-historical/) as
historical evidence; the current tools do not check them.
