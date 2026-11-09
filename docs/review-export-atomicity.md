# Atomic raw-result export increment — HAWA-033 / HAWA-047

November 9, 2026. Author/reviewer: Codex primary agent, self-review.
This is the first bounded implementation increment from the issue plan, separate
from the unmerged CUDA PR. Scope: existing Python `export` operation and NPZ
writer. No new node, file format, UI or solver change.

## Problem and contract

The existing export opened/truncated the destination before capturing fields.
A capture/compression error therefore destroyed a previously saved result or
left a partial new file. HAWA-047 records this reproduced data-loss defect.

Required behavior: capture raw arrays and metadata at one solver state; preserve
the existing field names/metadata/return value; publish only a completed file.
On capture, compression, flush or replacement failure, keep the old artifact
byte-for-byte (or leave a new destination absent) and remove owned temporary files.

The implementation captures detached arrays and serialized metadata under the
session lock, then compresses outside that lock into a uniquely named sibling
file. It flushes/synchronizes, closes and replaces the destination. Same-directory
replacement avoids crossing filesystems. Existing NPZ readers remain compatible.
This does not promise recovery from abrupt process/power loss, transactional
network-filesystem semantics, or cleanup after a killed process. No cancel API
was added; cooperative job cancellation and CSV/baking remain separate scope.

## Evidence

- Before repair: one round-trip pass and six failure-injection failures. Four
  capture/write cases reproduced destination damage; two replacement tests
  demonstrated the absence of an atomic replacement stage.
- After repair: ten focused CPU tests pass, including exact raw-array/metadata
  round trips, overwrite success, existing/absent targets under capture/write/
  fsync/replace faults, cleanup, and advancing the solver before compression
  while retaining the original capture’s values/time.
- Development build: both plugin assemblies and ZIP succeed with two existing
  CA1416 icon warnings; nothing installed or released.
- Full function run: **624 passed, 32 CUDA skips, four existing MRT warnings**;
  **33 state-contract passes** with host/transport doubles. No ratchet failures
  against `0822db9`. Both committed matrices refreshed and checked. This does not
  retire all HAWA-026 debt.
- Environment: local macOS arm64, Python 3.9.25, PyTorch 2.8.0; focused filesystem
  assertions on CPU, full suite includes available native MPS. No Windows/CUDA
  hardware or Rhino-host run for this increment.
- Evidence: `results/export-before.xml`, `export-focused-final.xml`,
  `export-function-gate/`, `export-function-gate-command.log`, `export-build.log`.
  Initial implementation’s local-import scoping error was caught by focused tests
  and repaired before the final complete run.

Commands run from the main checkout:

```sh
OMP_NUM_THREADS=1 .venv/bin/python -m pytest tests/test_export.py -q
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python tools/function_coverage.py run --output results/export-function-gate --base-ref 0822db9
.venv/bin/python tools/function_coverage.py render --output results/export-function-gate > docs/function-test-matrix.md
cp results/export-function-gate/matrix.json docs/function-tests/matrix.json
.venv/bin/python tools/function_coverage.py check --output docs/function-tests --base-ref 0822db9
.venv/bin/python scripts/build_plugin.py
```

## Gate record and disposition

| Gate | Actual reviewer | Decision | Scope/reason |
| --- | --- | --- | --- |
| G0 research/evidence | Codex self-review | PASS for scoped repair | Existing export/read contracts inspected; failure criteria fixed before edit; no dependency or numerical method change |
| G1 architecture | Codex self-review | PASS | One capture under lock, detached arrays, unique temporary path, close before replacement, no schema/identity/ownership change |
| G2 reliability | Codex self-review | PASS locally | Fault/round-trip tests, complete suite, measured function gate and committed matrices; Windows remains unverified |
| G3 numerical physics | Codex self-review | NOT APPLICABLE | Exact serialization of unchanged fields; no new accuracy/convergence claim or solver modification |
| G4 UI/UX | Codex self-review | NOT APPLICABLE to core increment | Existing dispatch API only; HAWA-033 host workflow remains open and unverified |
| G5 release | Codex self-review | BLOCKED for release | Development build only; no installed plugin or clean-host test |
| G6 compatibility | Codex self-review | NOT APPLICABLE to this increment | No new/changed field format, solver combination, shared-case contract, component/archive or release candidate; existing format tested by round trip |

HAWA-047 closes for the locally verified Python failure paths. HAWA-033 remains
in progress: CSV/probe export contracts, cancellation behavior and live export
UX still need scoped work. HAWA-032 baking has not been implemented. The broader
feature is not closed by making its existing raw exporter safer.
