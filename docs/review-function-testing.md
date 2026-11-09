# Function testing review

November 9, 2026. Reviewer: Codex, separate self-review passes. No independent
reviewer or live Rhino session is claimed for this developer-tool change.

The [matrix](function-test-matrix.md) inventories 1,118 explicit Python/C#
functions, callbacks and declarations. The gate records actual Python calls
during passing tests and instruments the separate .NET state-contract executable.
Every one of the 20 Python functions in the new coverage tool has measured test
execution. Existing debt is frozen in the reviewed baseline, not labelled passed.

| Gate | Decision and evidence |
| --- | --- |
| G0 research | PASS for instrumentation scope: Python AST/profiling and coverage.py API; SDK Roslyn syntax parsing; pinned Coverlet console instrumentation. References and limitations in the [policy](function-testing.md). These are developer dependencies and are not added to the embedded solver requirements. |
| G1 architecture | PASS for bounded inventory/evidence contracts: explicit source roots, unique function identities, unchanged-input hashes, actual function entry, partial/failed-run rejection, immutable initial debt and trusted-base PR checking. Host-only coverage remains explicitly unmeasured. |
| G2 reliability | PASS locally: 14 gate regressions within 614 passing Python cases; 32 CUDA skips; four existing upstream MRT warnings. Instrumented state contracts: 33 passes. Tests exercise nested/async/property/lambda inventory, C# parsing, ambiguous lines, import-only rejection, failed cases, worker attribution, selector removal, stale/duplicate/missing evidence, Markdown drift and base-commit enforcement. |
| G3 physics | No solver or numerical policy change. Existing bounded numerical tests run in the Python suite. Long atmospheric/transfer benchmarks and upstream parity were not rerun; their recorded failures remain open. |
| G4 host/UI | Not applicable to runtime behavior: no assembly, GH archive, native panel or installed plugin changes. Generated Markdown links and matrix/source agreement checked locally. |
| G5 integration | Local tool, pinned developer dependencies, generated matrix and baseline verified. GitHub Actions workflow is added but has not run remotely. No plugin package, release or deployment is claimed. |
| G6 combinations | Existing finite-product logic and its unit tests are unchanged. The 102,459-row runtime matrix was not rerun for this tooling change. Function execution is a separate coverage dimension. |

Local raw evidence: `results/function-coverage-commit/`. The committed
[machine record](function-tests/matrix.json) contains source/test/tool hashes,
test outcomes and every function row. The gate requires a new output directory
and rejects source changes during measurement. No old run can satisfy changed
source/test fingerprints.

Remaining debt is HAWA-026. Function execution does not establish assertion
quality, causal attribution of background work, exhaustive branches, host
behavior or numerical accuracy. C# attribution is at state-suite level. Same-line
ambiguous callables receive no automatic function credit.
