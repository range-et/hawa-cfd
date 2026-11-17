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
| G2 software/reliability | author self-review | IN PROGRESS | 35 CSV tests, existing NPZ/frame tests and 121 StateContracts pass. Scoped mutation policy passes; measured gate pending. |
| G3 numerical physics | author self-review | NOT APPLICABLE | No solver change. Exact data preservation is tested; engineering accuracy and convergence not claimed. |
| G4 UI/UX and examples | unassigned | BLOCKED | Headless existing-node action/rising-edge/format mapping passes. Live Checkpoint CSV action and supported-gallery review not yet run. |
| G5 release/integration | unassigned | BLOCKED | Build, ready PR, CI and Greptile 5/5 pending; no package installed or released. |
| G6 compatibility/example inventory | root live audit; author self-review | PARTIAL | Installed combined build archive audit passed 53 nodes / 31 examples; only the two Checkpoint input descriptions are refreshed here. Existing public-node GUID/ports unchanged; no new node. Runtime combinations remain separately unverified. |

## Checks and disposition

- `.venv/bin/python -m pytest tests/test_csv_export.py tests/test_export.py tests/test_field_export.py -q`: 62 passed (35 CSV cases).
- `dotnet run --project tests/dotnet/StateContracts`: 121 passed. Existing nullable warning in FieldTools.cs; host doubles do not prove Rhino scheduling or saved archives.
- `.venv-dev/bin/ruff check src/hawa/exports.py tests/test_csv_export.py`: passed.
- `MUTMUT_MAX_CHILDREN=4 bash tools/mutation/run_numerical_export.sh results/numerical-export-mutation-35-v3`: 368 mutants, 353 assertion kills, 15 reviewed equivalent survivors; all 47 Python 3.12 controls passed. `check_results.py` passes the committed [exact policy](../tools/mutation/numerical-export-policy.json). No timeouts/errors count as kills. Survivors concern equivalent temporary names, false-valued optional flags, UTF-8 codec case and zero-mask dtype. Earlier runs exposed missing assertions, which were added before the final run.
- `.venv/bin/python scripts/build_plugin.py --archive dist/Hawa-export-35.zip`: initial build at03b8f78 passed, 0 errors; existing nullable warnings. This binary predates the absolute-time Python follow-up; final combined host build is coordinated by root.
- First full measurement was intentionally interrupted before completion when review required new tests; it is not a pass. Fresh final measurement is running in `results/function-coverage-export-35-v2`.
- Historical validity-foundation/status-truth studies are not refreshed claims: their module source hashes changed. This new study measures only this PR's export/routing diff.

Sequential host harness: `scripts/verify_coverage_examples.cs`, example31. Use
separate MCP calls for `open`, `run`, `state`/`report`, `export csv`, `execute`,
`report`, then `close`. It keeps the source archive and writes only its owned
output. The CSV's report must match the captured session/iteration and the
filesystem artifact; verify through the declared parser. Final code tests also
cover normalized2D output and nonzero absolute time offsets; the host demo does
not establish those numerical cases by itself.

No tolerance was introduced or relaxed. Quality records are carried through,
not promoted to validation. Session identity and case hash describe the captured
solver state; an optional caller revision is not a verified source revision.
Job cancellation after publication cannot roll back a completed filesystem
replacement. Default NPZ output remains the raw interchange escape hatch.

Issue #35 must remain open after this increment: probe/load interchange and
installed/native UX need their own scoped contract, round-trip checks and host
review. #34 is independent baking work. Owner/closure decisions remain with the
coordinating maintainer after the PR gates.

Root-reported installed audit: integration `1ea7314` (domain `0e76b95` plus
export production `de2003d`), 53 public nodes / 31 example archives passed.
This branch copies only the Path/Operation descriptions for Checkpoint; unrelated
Geometry Check descriptions and example33 changes remain in their own PRs.
