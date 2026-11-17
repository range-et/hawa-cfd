# Numerical CSV export review — #35 / HAWA-033

Date: November 16, 2026. Author/self-review: Codex numerical_exports agent.
Read-only review: Codex atmosphere_qualification agent identified the nonzero nested-time origin ambiguity; explicit local/absolute times and a regression now address it. Final root review, CI and Greptile approval remain pending. This is a bounded
field interchange increment, not completion of #35 and not physical validation.

Scope: existing Checkpoint operation `export csv`, explicit Python `format=csv`,
instantaneous field table only. No node/port/GUID, solver, NPZ archive or default
path-format changes. Probe/load CSV, native controls, baking (#34), coefficients,
mean fields and checkpoint reimport are excluded. The
[contract](numerical-export.md) fixes units, row order, validity, precision,
provenance, 250,000-node bound and atomic publication behavior.

Acceptance fixed before execution: exact float64 parsing of valid float32/float64
source values; exact indices/flags; independent rotated-position expectations;
JSON metadata preserving quotes, commas and newlines; explicit normalized units
for benchmarks; unchanged legacy NPZ even at a `.csv` path. Failed capture,
validation, temporary creation, partial write, fsync, replacement or cooperative
cancellation must preserve an existing artifact and leave no temporary file.
Expected-row-count checking must detect a truncated exported table.

Environment: macOS, isolated worktree `.venv` Python 3.9.25, PyTorch 2.8.0; `.venv-dev`
Python 3.12.4 for pinned mutmut 3.7.0/ruff. Focused solver case: CPU TGV2D BGK,
8×8, initialization snapshot. Other tests use explicit float32/float64 deterministic
arrays, 2D/3D lattices and a rotated/translated physical coordinate basis.

| Gate | Reviewer | Status | Evidence and limits |
| --- | --- | --- | --- |
| G0 research | author self-review | PASS, scoped | Standard CSV quoting and NumPy C-order iteration; no new numerical model or dependency. Existing physical-unit conversion and case mapping reused. |
| G1 architecture | author self-review | PASS, scoped | Explicit opt-in preserves NPZ/path compatibility. One atomic file, detached captured metadata; query checkpoint route avoids holding device lock during CPU file IO. |
| G2 software/reliability | agents + root | PASS | Final combined suite: 1,978 Python tests, 87 explicit skips, 127 instrumented contracts; strict headless/base gates and all exact mutation policies pass. |
| G3 numerical physics | author self-review | NOT APPLICABLE | No solver change. Exact data preservation is tested; engineering accuracy and convergence not claimed. |
| G4 UI/UX and examples | root live verification; author evidence review | PASS, bounded | Existing Checkpoint CSV and legacy NPZ actions passed on example31 in Rhino 8.37/macOS/CPU; exact readback and cleanup verified. Wider gallery, native-panel export UX and CUDA/MPS export acceptance are not covered by this pass. |
| G5 release/integration | root | BLOCKED | Combined build, installed runtime checks and archive audit pass. Ready PR #116 awaits final CI and Greptile 5/5; no release claim. |
| G6 compatibility/example inventory | root live audit | PASS, local | Final 53-node/31-example archive inventory passes; combined finite matrix has 100,010 passed, zero failed and 2,449 unavailable CUDA rows blocked. No new node or all-device qualification. |

## Checks and disposition

- `.venv/bin/python -m pytest tests/test_csv_export.py tests/test_export.py tests/test_field_export.py -q`: 62 passed (35 CSV cases).
- `dotnet run --project tests/dotnet/StateContracts`: 121 passed. Existing nullable warning in FieldTools.cs; host doubles do not prove Rhino scheduling or saved archives.
- `.venv-dev/bin/ruff check src/hawa/exports.py tests/test_csv_export.py`: passed.
- `MUTMUT_MAX_CHILDREN=4 bash tools/mutation/run_numerical_export.sh results/numerical-export-mutation-combined`: Combined source `5f58de7`, export-only diff against domain production `0e76b95`: 368 mutants, 353 assertion kills, 15 reviewed equivalent survivors; all 47 Python 3.12 controls passed. `check_results.py` passes the committed [exact policy](../tools/mutation/numerical-export-policy.json). No timeouts/errors count as kills. Survivors concern equivalent temporary names, false-valued optional flags, UTF-8 codec case and zero-mask dtype. Earlier runs exposed missing assertions, which were added before the final run.
- `.venv/bin/python scripts/build_plugin.py --archive dist/Hawa-export-35.zip`: initial build at03b8f78 passed, 0 errors; existing nullable warnings. This binary predates the absolute-time Python follow-up; final combined host build is coordinated by root.
- First full measurement was intentionally interrupted for review fixes. The second (`results/function-coverage-export-35-v2`) finished 1,952 passed / 87 skipped / 2 failed; both failures were stale historical mutation-policy hashes. It is **not** a measured-gate pass and generated no accepted matrix. The final combined measurement after policy refresh passes: 1,978 tests / 87 skips
  and 127 instrumented contracts; strict headless function/line coverage and
  trusted-base `d12fd069` checks pass. Both committed matrices are refreshed.
- Combined status study: `MUTMUT_MAX_CHILDREN=4 bash tools/mutation/run_status_truth.sh results/status-truth-mutation-combined-v2`, 56 mutants / 55 assertion kills / 1 equivalent false-valued ownership survivor; all 143 controls passed. The [exact status policy](../tools/mutation/status-truth-policy.json) passes. Existing `cpu_only` isolates forked workers; the explicit bounded lock fixture still enables device locking. Its reversed-acquire-loop mutant exits 1 (assertion kill). An earlier SIGXCPU run was discarded, never counted as passing evidence.
- `.venv/bin/python -m pytest tests/test_csv_export.py tests/test_runtime_job_contracts.py tests/test_refinement_preflight.py tests/test_export.py -q`: 143 passed on combined production in Python 3.9.
- [Combined machine record](verification-combined-export-mutation.json) records commands, versions, discarded run and exact results. Domain agent separately owns validity-foundation refresh; final complete-suite and live host evidence remain with root.

## Bounded live host result

Root ran `scripts/verify_coverage_examples.cs` through separate Rhino MCP calls
for example31, using the existing Checkpoint CSV and legacy NPZ actions. On
Rhino 8.37/macOS, CPU, PyTorch 2.8.0, the captured result at iteration60 had
5,376 rows (21×16×16): all 4,677 valid rows matched NPZ quantities exactly,
positions and mask flags matched exactly, and all 699 invalid rows had blank
quantities. Units were SI; local and absolute time both equalled
0.0017320508075688776 seconds at zero time origin. The quality warning remained
present; this is not convergence or engineering validation.

The [host machine record](verification-numerical-export-host.json) pins the final
Grasshopper assembly SHA-256
`bf99fd985183443fe4a9181d671a06a9e2c8661635acb8423df355a4e8f08993`, artifact
hashes, captured case/session and readback assertions. After disposing the owned
graph, the runtime audit found zero jobs, sessions and workers, zero live native
objects, and the two original empty graphs restored.

This passes the scoped existing-node CSV/NPZ host workflow. Normalized 2D cases
and nonzero time origins have headless regression evidence, not this host run.
Live cancellation/failure-path injection, CUDA/MPS CSV workflows, wider gallery
acceptance, probe/load export and native-panel export UX are not established by
this result.

No tolerance was introduced or relaxed. Quality records are carried through,
not promoted to validation. Session identity and case hash describe the captured
solver state; an optional caller revision is not a verified source revision.
Job cancellation after publication cannot roll back a completed filesystem
replacement. Default NPZ output remains the raw interchange escape hatch.

Issue #35 must remain open after this increment: probe/load interchange and
installed/native UX need their own scoped contract, round-trip checks and host
review. #34 is independent baking work. Owner/closure decisions remain with the
coordinating maintainer after the PR gates.

Final installed archive audit passes: 53 public nodes, 31 definitions and 188
observed port combinations. The [combined G6 record](verification-working-30-35-g6.json)
pins exact source hashes; zero source changes during measurement. Example 33
presentation was separately merged in #114 before this combined final check.
