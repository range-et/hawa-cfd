# HAWA-048 — Atomic immutable-frame NPZ save

November 9, 2026. Author/reviewer: Codex export agent, self-review.
Base: `a26924caa9ef5da070c0a82f2f8a8bf3ddf5782d`; isolated branch
`codex/python-export-033`. Scope: `fields.dispatch_field(action='save')` and its
regressions. Existing session export's HAWA-047 repair remains separate and intact.

## Reproduction and repair contract

The immutable-frame writer opened the destination with `wb` before compression.
An injected writer emitted `partial` then raised `OSError`: an existing valid
887-byte NPZ became a 7-byte partial file; a new target also remained as 7 bytes.
The study's exact bytes/hash evidence is `results/study/frame-save-failure.json`.
This is a reproduced data-loss defect, not the broader CSV/baking request.

The repair serializes metadata before opening output, writes into a uniquely named
sibling temporary file, flushes/synchronizes, closes, then replaces the destination.
Cleanup runs in `finally`. Existing request/return shape, arrays and metadata are
unchanged. A failed write/fsync/replace preserves the previous target byte-for-byte,
or leaves a new target absent. The existing immutable frame is saved; no live
session recapture or solver advancement occurs.

The supplied checkpoint callback runs before writing and immediately before
replacement. Cancellation **observed** at either checkpoint prevents publication
and cleans temporary output. Compression remains synchronous, so cancellation
latency is not bounded within `np.savez_compressed`. A request arriving after the
last checkpoint can race with publication; this is not an atomic cancel/commit
protocol and does not change `Job` ownership semantics.

Filesystem guarantees are scoped to normal local filesystem calls. This does not
promise recovery from abrupt process/power loss, filesystem permission changes,
transactional network storage, or directory durability after a crash. Closing
before replacement is compatible with the intended Windows workflow, but this
repair has not been executed on Windows.

## Tests and actual evidence

Environment: own `.venv`, macOS arm64, Python 3.9.25, pinned PyTorch 2.8.0 and
NumPy 2.0.2. Tests use CPU arrays; existing session-export tests run the CPU solver.
Both Hawa and Lettuce import from this isolated checkout.

1. Before repair: **11 failed, 2 passed**, `before.xml`. The compression cases
   reproduce target damage; remaining failures expose absent synchronization,
   replacement and checkpoint stages. The expired-frame cases already pass.
2. After repair: **31 passed**, zero skips/warnings, 4.51 seconds, `focused.xml`:
   13 new frame-save regressions, 10 existing session-export tests, 8 field tests.
   Regressions assert exact arrays/dtypes/metadata through `read_frame`, overwrite,
   existing/absent destinations under compression/fsync/replace faults, two
   cancellation boundaries, cleanup, and expired-frame rejection.
3. Full function gate, matrix refresh and any applicable integration checks are
   queued with the coordinator; no full-suite pass is claimed yet.

Logs and JUnit are in `results/field-export-atomicity/`. Commands:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m pytest tests/test_field_export.py -q --junitxml=results/field-export-atomicity/before.xml
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m pytest tests/test_field_export.py tests/test_export.py tests/test_fields.py -q --junitxml=results/field-export-atomicity/focused.xml
```

No dependency/baseline changes, C# edits, Rhino session, GPU run, installed plugin
update or release occurred. `git diff --check` and local document links pass.

## Gate disposition

| Gate | Actual reviewer | Decision and evidence |
| --- | --- | --- |
| G0 evidence | Export agent self-review | PASS for scoped repair: before-failure artifact, existing compatibility contract, fixed preservation criteria |
| G1 architecture | Export agent self-review | PASS: immutable-frame source, single-file publication, explicit observed-cancellation boundaries; no shared-case or worker ownership change |
| G2 reliability | Export agent self-review | Focused checks PASS; full measured gate pending coordinator slot |
| G3 physics | Export agent self-review | NOT APPLICABLE: unchanged values/units/schema; no numerical or accuracy claim |
| G4 UI/UX | Export agent self-review | NOT APPLICABLE to this Python repair: host export UX remains HAWA-033 |
| G5 release | Export agent self-review | BLOCKED: no package/install/release verification in this increment |
| G6 compatibility | Export agent self-review | NOT APPLICABLE to unchanged NPZ schema and dispatch contract; round-trip compatibility tested; no new node, format or supported solver combination |

HAWA-048 remains in progress pending the full gate and integration. HAWA-033 stays
open for CSV/probe export, artifact provenance, broader cancellation and host UX;
HAWA-032 baking is unaffected. Other workers own `field_collection.py` and transfer
logic; no files in those surfaces changed here.
