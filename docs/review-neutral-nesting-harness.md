# HAWA-021/022 C1 — Frozen-reference nesting study harness

November 9, 2026. Author/reviewer: transfer-study agent (self-review), coordinated
by the primary Codex agent. Base: `a26924caa9ef5da070c0a82f2f8a8bf3ddf5782d`.
Python-only developer tooling; no solver, recording API, dependency, C#, public
node, Rhino archive or CUDA-candidate modification.

## Problem and scope

The original nesting script regenerated parent, child and fine reference in one
run, obscuring which comparison reused the same source/window. Historical
HAWA-021/022 failures combine insufficient reference stationarity and nested RMS
error. The wall-filter transfer and constrained boundary reconstruction repairs
already exist; this change does not replace them or claim a numerical repair.

The harness can now prepare a frozen source bundle and replay children against
it, so settling, same-grid transfer and resolution changes can be studied in order.
The ordinary `--output ... --device ... --warmup ... --steps ... --ratios ...`
invocation remains supported for the declared ratios 1 and 2. Configuration now
requires aligned warmup/steps/cadence, 8–1000 frames and the existing 100,000-step
recording limit; incomplete or insufficient comparisons are errors.

## Contract

- `--reference-only` prepares parent and optional full fine-domain recordings and
  checks their numerical health and reference stationarity. It cannot claim a
  child/nesting pass. This is an implementation-study criterion, not physical
  validation or proof of adequate atmospheric averaging.
- `--reuse-reference <reference.json>` reuses those exact completed files. Source
  fingerprints include the entire first-party Python engine, vendored engine,
  this harness, `pyproject.toml` and `uv.lock`. **Any such source change makes the
  bundle stale.** Regenerate after a solver fix, harness edit, dependency change
  or integration; there is no ignore-staleness switch.
- Every manifest/frame hash must match. Files stay inside the bundle directory;
  original recording path validation still applies. Frame metadata must agree
  with its manifest. Complete iteration inventories, generated case geometry/model
  and absolute clocks must agree with the experiment configuration; rehashing a
  malformed recording does not waive these semantic checks. Sources and inputs
  are rechecked at the end. Snapshots detect boundary-observed changes; do not
  edit and restore files concurrently between checks.
- Device and runtime provenance are recorded for both preparation and execution.
  Replay can deliberately compare another device against the frozen source;
  runtime differences remain visible and require review. Source matching alone
  does not establish hardware parity or a clean installed environment.
- `--window-start`/`--window-end` select **absolute seconds** within coverage,
  requiring at least four uniformly timed frames. With neither supplied, use the
  historical latter half. Reports identify actual selected times/sample count.
- Acceptance remains mean relative L2 ≤5%, fluctuation RMS relative L2 ≤10%,
  mean-pressure Cp RMSE ≤0.1, reference stationarity change ≤5%, and numerical
  health within the tested envelope. Absolute/component RMS and mean errors,
  plus child stationarity, are diagnostics. Child stationarity is not a new
  hidden acceptance criterion.
- Failed reference checks stop ordinary child comparison. The explicit
  `--diagnostic-nonstationary-reference` option permits collecting diagnostic
  child rows but **cannot turn a failed reference into a nesting pass**.
- `requested_ratios`, `evaluated_ratios`, `available_ratios` and `full_scope` are
  explicit. A passing subset can have `passed=true` for that requested subset,
  but `full_nesting_passed=false`. Full scope means the declared bundle's ratios,
  not every possible ratio or physical regime. Without `--fine-reference`, a
  refined child is compared with the coarse parent and includes discretization
  differences; even a full-scope pass is not a uniform-fine-reference qualification. Reference-only always has false
  `full_scope` and `full_nesting_passed`.
- Fresh output directories are mandatory. Failed evidence remains with
  `passed=false`, `full_nesting_passed=false` and an error where appropriate.
  Numerical failures retain their actual comparison metrics and arrays.

The descriptor is a reproducibility record, not a signed authenticity certificate.
Keep source recordings immutable. Recording paths are relative to the bundle directory, so the directory tree
can be relocated on the same platform; cross-platform path transfer has not been
qualified. Reports retain the path used during that execution. No capture/recording schema
or runtime client contract changes.

## Usage and ordered study

From this candidate checkout, using the pinned environment:

```sh
# First qualify a source window; example budget, not a promised passing result.
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/verify_neutral_nesting.py \
  --output results/nesting-reference-NEW --device cpu \
  --warmup 5000 --steps 1000 --interval 10 --ratios 1 --reference-only

# Only a passing reference is eligible for ordinary child comparison.
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/verify_neutral_nesting.py \
  --output results/nesting-replay-NEW --device cpu \
  --reuse-reference results/nesting-reference-NEW/reference.json
```

Inspect source and child diagnostics independently. Freeze the passing reference
and window before varying one transfer input at a time. Then prepare a separate
bundle with `--ratios 1,2 --fine-reference` for the full fine-domain comparison;
that larger run has a separate resource/device reservation. A refined child may
reset incompatible wall-filter history and require spin-up: retain that behavior
and diagnose it rather than removing the guard. A later production repair gets
its own PR and newly prepared references.

## Evidence and remaining checks

Local environment: macOS arm64, Python 3.9.25, PyTorch 2.8.0, NumPy 2.0.2. All
runs here explicitly use CPU with one OMP/MKL thread. No Rhino, CUDA or MPS run.

- Final focused harness run: **32 passed**, including seeded mean/RMS/pressure/
  health/reference-stationarity failures; changed/missing/corrupt recordings;
  source/config/geometry/clock mismatch; complete vs partial scope; live short CPU
  reference/replay; and refusal to overwrite prior evidence.
  `results/study/harness-focused-freeze.xml` and `.log`.
- Earlier combined operator/statistics run: 65 passed, four GPU cases deliberately
  deselected. Later final harness tests supersede that harness snapshot; the full
  function gate is required on final source before merge.
- Final bounded real CPU run and frozen replay both finish with exit 1 and
  `passed=false`, preserving the same numerical failure: 200 parent warmup steps,
  40 recorded steps, interval 2, ratio 1; 21 recorded frames and 11 analysis samples.
  Mean error 2.2161%, RMS error **32.6437%** (10% limit), Cp RMSE 0.038388,
  reference stationarity 1.4304%, child stationarity 1.2538% diagnostic.
  The source run takes 10.80 s and replay 4.91 s; no timeout. Metrics match exactly.
  This short smoke/debugging study is **not** long-window statistical qualification.
  Evidence: `results/study/cpu-final-commands.json`, `cpu-smoke-final/`,
  `cpu-replay-final/` and `cpu-final-{0,1}.log`. Earlier smoke outputs are retained
  but are stale after harness edits; only the final folders match current source.
- Full function gate on final source: **656 passed, 32 CUDA skips, four existing
  MRT warnings**, 167.16 seconds; **33 production-linked state contracts pass**.
  Zero ratchet failures against `a26924c`; committed matrices refreshed and checked.
  Inventory: 297 covered, 142 uncovered, 630 unmeasured, 58 declarations. Historical
  HAWA-026 debt remains visible; no baseline exemption. Evidence:
  `results/study/function-gate/`, `function-gate.log`, `function-matrix-check.log`.
- Both plugin assemblies build with zero errors. Existing CA1416 platform warnings:
  **103 Grasshopper + 2 Rhino = 105 total** (neither project was edited).
  Source/binaries packaged in the fresh development ZIP
  `dist/Hawa-transfer-c1-final.zip`; no plugin installation or public release.
  Evidence: `results/study/build.log`, `package-final.log`, `package-checks.json`.

| Gate | Actual reviewer | Disposition | Scope |
| --- | --- | --- | --- |
| G0 | Transfer-study agent self-review | PASS | Existing fixed completion contract and source reviewed; no new numerical method or dependency |
| G1 | Transfer-study agent self-review | PASS | Immutable source/reference identity, explicit scope/time/ownership and fail-closed replay |
| G2 | Transfer-study agent self-review | PASS locally | 32 focused tests, 656 full-suite passes, 33 contracts, zero coverage failures, fresh matrices and development build; hardware skips explicit |
| G3 | Transfer-study agent self-review | FAIL for numerical qualification | Harness preserves failures and unchanged criteria; no HAWA-021/022 physics closure |
| G4 | Transfer-study agent self-review | NOT APPLICABLE | No UI/host/node/archive change |
| G5 | Transfer-study agent self-review | BLOCKED for release | Developer harness only; no installation or release |
| G6 | Transfer-study agent self-review | NOT APPLICABLE to C1 | No production solver combination, field format, shared state or public node changed; descriptor is developer-only study evidence |

HAWA-021 and HAWA-022 remain open. Harness readiness does not qualify the parent,
child turbulence, atmospheric model, refined transfer, installed workflow or
engineering predictions. Preserve all failed reports when advancing to C2.
