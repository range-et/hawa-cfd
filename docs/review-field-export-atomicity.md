# HAWA-048 — Atomic immutable-frame NPZ save

November 9, 2026. Author/reviewer: Codex export agent, self-review.
Base: `a26924caa9ef5da070c0a82f2f8a8bf3ddf5782d`; isolated branch
`codex/python-export-033`. Scope: `fields.dispatch_field(action='save')` and its
regressions. Existing session export's HAWA-047 repair remains separate and intact.

## PR #3 review follow-up — HAWA-051

The original implementation and evidence below are retained as history. The
[current PR review](https://github.com/range-et/hawa-cfd/pull/3#discussion_r4518760541)
identified a new regression shared by **both Python atomic NPZ writers**:
`fields.dispatch_field(action='save')` and session `plugin.dispatch(op='export')`
used the entire destination basename as their temporary prefix. A valid 250-byte
ASCII destination could be created directly, but saving failed with
`ENAMETOOLONG` because the temporary name appended random characters and a suffix.
New-target and overwrite regressions failed for each writer (two cases each).
This is HAWA-051, separate from HAWA-047/048's failed-write data preservation.

Both writers now use short fixed prefixes (`.hawa-frame.` / `.hawa-export.`) with
stdlib random suffixes in the destination directory. Only those prefix expressions
changed in production for this follow-up. The atomic replacement, checkpoint,
metadata, array and API contracts remain unchanged. Four regression cases prove
long destination names round-trip exactly for creation and overwrite, with no
owned temporary files left behind.

The user-merged PR #4 was incorporated from GitHub base
`a00223f9d86e95077d1b19c6eaa00e68dd16123e`, preserving both issue histories.
Combined coverage matrices were regenerated from execution, not merged as proof.
Final evidence in `results/field-export-long-name/`:

- `before.xml` / `session-before.xml`: two expected long-name failures each.
- `focused-both.xml`: **35 passed**, zero skips/warnings, 1.18 seconds.
- `final-function-gate/`: **671 passed, 32 CUDA-unavailable skips**, four existing
  MRT warnings, 45.17 seconds; **33 state contracts passed**. Ratchet failures
  empty against `origin/codex/python-study-base-20261109` at the exact base above.
  Both committed matrices refreshed and checked (`matrix-check.log`).
- Constrained Linux CPU rerun: **35 passed**, zero skips/warnings, 1.22 seconds,
  `results/docker-review/focused.xml`. Same immutable image ID recorded below;
  source/root read-only, network disabled, one CPU / 2 GiB, separate results/tmp.
  No Windows/CUDA execution is claimed.
- Updated development build: both assemblies and `dist/HAWA-048-review.zip`
  succeed, with 105 existing CA1416 icon warnings (103 Grasshopper, 2 Rhino),
  zero errors. ZIP integrity, legacy-09 exclusion and both packaged Python writer
  sources match this checkout (`package-check.json`); nothing installed.

The intermediate `function-gate/` run with 669 passes predates the session-writer
follow-up and is not the final evidence. Domain G6 evidence belongs to PR #4's
historical record; no fresh full G6 is claimed here. This follow-up changes file
publication internals, not formats, solver combinations, nodes or shared-state
contracts; round-trip and measured suite checks cover its declared scope.
HAWA-048/051 remain pending integration, and HAWA-033's CSV/host scope remains open.

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
3. Independent constrained Linux CPU run: **31 passed**, zero skips/warnings,
   2.20 seconds (`results/docker/focused.xml` and `focused.log`). Coordinator
   executed image `hawa-python-study:20261109`, immutable ID
   `sha256:6b367745131c89cf349cd005532efe5ac708f871b1758105669406e468e18e93`;
   Python 3.9.25, torch 2.8.0+cpu, NumPy 2.0.2, Linux 6.12.76-linuxkit aarch64.
   One CPU / 2 GiB cgroup limit, network disabled, read-only root/source, dedicated
   writable results/tmp. This image excludes .NET; native measurement supplies
   the separate state-contract/function gate.
4. Full native function gate: **637 passed, 32 CUDA-unavailable skips**, four
   existing MRT warnings, 160.88 seconds; **33 instrumented state contracts pass**.
   Against base `a26924c`, ratchet failures are empty. Inventory: 281 covered,
   149 uncovered, 630 unmeasured, 58 declarations; historical debt remains visible.
   Both committed matrices refreshed and checked against the same base. Evidence:
   `function-gate/`, `function-gate.log`, `matrix-check.log`.
5. Both development assemblies and `dist/HAWA-048.zip` build successfully, with
   **105 existing CA1416 warnings in unchanged icon sources**: 103 from
   Grasshopper and 2 from Rhino, with zero errors (`build.log`). ZIP
   integrity, legacy-09 exclusion and exact packaged Python/source equality pass
   (`package-check.json`). Nothing installed.

Logs and JUnit are in `results/field-export-atomicity/`. Commands:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m pytest tests/test_field_export.py -q --junitxml=results/field-export-atomicity/before.xml
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m pytest tests/test_field_export.py tests/test_export.py tests/test_fields.py -q --junitxml=results/field-export-atomicity/focused.xml
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python tools/function_coverage.py run --output results/field-export-atomicity/function-gate --base-ref a26924c
.venv/bin/python tools/function_coverage.py render --output results/field-export-atomicity/function-gate > docs/function-test-matrix.md
cp results/field-export-atomicity/function-gate/matrix.json docs/function-tests/matrix.json
.venv/bin/python tools/function_coverage.py check --output docs/function-tests --base-ref a26924c
.venv/bin/python scripts/build_plugin.py --output dist/HAWA-048 --archive dist/HAWA-048.zip
```

No dependency/baseline changes, C# edits, Rhino session, installed plugin update
or release occurred. Focused filesystem tests were CPU-only; the full native
suite includes available MPS coverage and explicitly skips unavailable CUDA. `git diff --check` and local document links pass.

## Gate disposition

| Gate | Actual reviewer | Decision and evidence |
| --- | --- | --- |
| G0 evidence | Export agent self-review | PASS for scoped repair: before-failure artifact, existing compatibility contract, fixed preservation criteria |
| G1 architecture | Export agent self-review | PASS: immutable-frame source, single-file publication, explicit observed-cancellation boundaries; no shared-case or worker ownership change |
| G2 reliability | Export agent self-review; coordinator ran Docker checks | PASS locally: 637 tests, 33 contracts, zero ratchet failures, fresh matrices; 31 focused Linux CPU passes; Windows unverified |
| G3 physics | Export agent self-review | NOT APPLICABLE: unchanged values/units/schema; no numerical or accuracy claim |
| G4 UI/UX | Export agent self-review | NOT APPLICABLE to this Python repair: host export UX remains HAWA-033 |
| G5 release | Export agent self-review | Development build/ZIP checks PASS; BLOCKED for release: no clean installed-host or Windows qualification |
| G6 compatibility | Export agent self-review | NOT APPLICABLE to unchanged NPZ schema and dispatch contract; round-trip compatibility tested; no new node, format or supported solver combination |

HAWA-048 remains in progress pending integration; scoped local and Linux checks pass. HAWA-033 stays
open for CSV/probe export, artifact provenance, broader cancellation and host UX;
HAWA-032 baking is unaffected. Other workers own `field_collection.py` and transfer
logic; no files in those surfaces changed here.
