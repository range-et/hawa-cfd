# HAWA-001 — bounded CPU/MPS KBC diagnosis

> **Follow-up (November 10, 2026):** the root cause is repaired by a candidate
> double-float KBC path for devices without FP64; see the
> [repair record](review-porous-kbc-repair.md). The text below is the earlier
> diagnosis, retained as historical evidence.

November 9, 2026. Author/reviewer: parity-study agent, self-review with primary
agent coordination. Diagnostic increment only; no production or vendor changes.
Initial numerical experiments used integrated base `abe7545`. The [compact
machine evidence](verification-porous-kbc-diagnostic.json) preserves results when
local scratch artifacts are unavailable. HAWA-001 remains open. This does not repeat the integrated CPU/CUDA precision
repair or claim MPS FP64 support, CPU fallback, CUDA qualification or physical
validation.

## Fixed question and criteria

Why does the original PorousMedium example still disagree between CPU and MPS
after integration? Keep the original notebook, 512×512 grid, 50 steps, geometry,
forcing, FP32 storage and population/density/physical-velocity/physical-pressure
criteria: `rtol=1e-3`, `atol=1e-5` multiplied by the existing velocity or pressure
conversion scale for those fields. Do not replace trajectory acceptance with a
finite-output or one-cell check.

Reference sources: bundled PorousMedium notebook and Lettuce KBC implementation
at upstream commit [88a6559](https://github.com/lettucecfd/lettuce/blob/88a6559def2a49fd7f425fd05954ec1e3db2cdb6/lettuce/ext/_collision/kbc_collision.py),
plus the integrated precision repair and [original review](review-cuda-pr2.md).
Existing bundled licence notices remain intact. No numerical method or dependency
is introduced. The comparison below distinguishes identical-input operator
verification from the evolving full trajectory.

## Reproduced original failure

Both original workers complete with finite fields on CPU and actual MPS. Masks
are bit-identical. Maximum absolute differences reproduce the preserved review:

| Field | Maximum absolute difference | Original criterion |
| --- | ---: | --- |
| Populations | 0.0007722377777099609 | FAIL |
| Density | 0.0006060004234313965 | PASS |
| Physical velocity | 0.027186395600438118 | FAIL |
| Physical pressure | 0.2424001693725586 | FAIL |

Velocity conversion is 34.64101615137754; pressure conversion is 400. Exact
commands (checkout `.venv`, `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`, own TMPDIR):

```sh
.venv/bin/python scripts/example_worker.py advanced_flows/PorousMedium.ipynb --device cpu --output results/parity-001/original-cpu
.venv/bin/python scripts/example_worker.py advanced_flows/PorousMedium.ipynb --device mps --output results/parity-001/original-mps
```

Reports and frame arrays are under those two directories; original criteria and
comparison results are in `results/parity-001/original-comparison.json`. This is
one entrypoint, not the entire upstream example inventory. The notebook's driving
term is its periodic pressure-increment boundary; it does not use a separate
Guo/body-force object.

## Local mechanism and controls

At the CPU checkpoint immediately before step 50, cell `(294,125)` supplies the
nine exact FP32 populations frozen in `scripts/diagnose_kbc_parity.py`. Identical
stored values are repeated at different array sizes; they are not independently
initialized on different devices. All reference values are first rounded to
FP32, then promoted for the CPU FP64 control. The diagnostic records density,
velocity, equilibrium, shear/higher residuals, entropy numerator/denominator,
raw/applied stabilizer, reset counts, output, and mass/momentum differences.

The local FP64 raw stabilizer is **+0.0016176334459674369**, away from the
near-zero higher-order-entropy guard. The CPU raw FP32 control is
+0.005347132682800293. On actual MPS the repeated cell gives:

| Array shape | Raw stabilizer at first cell | Consequence |
| --- | ---: | --- |
| 1×1 | +0.00018346309661865234 | No negative reset |
| 8×8 | +0.00018346309661865234 | No negative reset |
| 32×32 | +0.00018155574798583984 | No negative reset |
| 512×512 | **−0.00475919246673584** | Existing negative-value branch resets to **2** |

The large-array collision population difference is about **1.85e-4** before
streaming, failing the original population criterion despite identical inputs.
This demonstrates shape-dependent FP32 cancellation crossing the inherited
stabilizer branch. It does not prove that every trajectory difference has this
single cause. Small-array tests alone miss the observed branch change.

Pinned upstream collision source was executed separately on the same backported
Flow and exact FP32-derived FP64 cell: output matches the current FP64 operator
exactly. This is an isolated operator control, **not** an unmodified-upstream
runtime/suite pass. Its negative-stabilizer reset is inherited upstream.
Evidence: `upstream-cell.log`, `cell.log`, `mps-control.log`, `mps-shapes.log`
under `results/parity-001/`.

Independent matched-input pressure-increment and bounceback controls return
bit-identical CPU/MPS outputs; matched streaming was exact in the scratch trace.
An earlier scratch full-domain trace showed tiny bounceback differences without
archived per-stage input identities. Those values are excluded from attribution:
the independent reset/input checks do not reproduce a boundary defect. This is
a correction to preliminary tracing, not a newly claimed solver bug. Raw scratch
evidence remains in `stages.{py,json,log}` and `boundary-control.{py,log}`.

## Rejected experiment and next work

A scratch-only FP32 variant computes shear from the population residual before
moment transformation, avoiding subtraction of two large shear estimates. This
algebraic rearrangement improves the local stabilizer and full-run errors, but
still fails the unchanged original 50-step population/velocity/pressure limits:
max differences 0.00018522143363952637, 0.004967806860804558 and
0.07431507110595703 respectively. Density passes. **Do not adopt this candidate
as a repair.** It exists only under `results/parity-001/`, not production code.

Further work needs a justified FP32 stabilization/conditioning strategy that
preserves the declared method and conservation, then identical-input shape
controls, the original full trajectory and unaffected CPU/upstream controls.
Do not widen tolerances, arbitrarily smooth the reset threshold or claim MPS
FP64/CPU fallback. Longer physics and GPU performance claims require separate
measurements.

## Replayable diagnostic and evidence contract

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/diagnose_kbc_parity.py --device cpu --output results/parity-001/final-cpu
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/diagnose_kbc_parity.py --device mps --output results/parity-001/final-mps
```

The default sizes are 1, 8, 32 and 512. Exit 1 preserves a failed local population
comparison; `completed` distinguishes that from an execution error. Every report
sets `original_512x512_50_step_qualified=false`, because repeating a cell cannot
qualify the original trajectory. Explicit devices, actual output device/dtype,
source fingerprints, software/environment versions and MPS fallback environment
are recorded. CPU FP64 is a separately labelled reference, not execution of the
MPS collision on CPU. Evidence directories must be new; no stale report reuse.
Runtime device errors, nonfinite stages or changed sources preserve failure.

## Initial published validation and gate disposition

Initial published source is based on integration `977bb78aee6041cf40cd31c4c90d75d68207a913`.
The vendor engine, original notebook and original example worker are byte-unchanged
from `abe7545`; the original full-trajectory experiment remains attributed to its
initial snapshot, not relabelled as a new run. The final diagnostic was rerun on
the refreshed base.

Actual MPS FP32 diagnostic: **completed=true, passed=false, exit 1** in 0.487 s.
At 512×512 all 262,144 cells take the negative reset and 1,310,720 of 2,359,296
populations fail the original local comparison; maximum difference is
0.00018513202667236328. Maximum cell mass/momentum differences are
5.96046e-8 / 7.45058e-9: conserved moments do not imply population parity.
CPU public collisions agree exactly with the rounded FP64 reference at all four
sizes (0.145 s). Reports: `results/parity-001/final/{cpu,mps}/result.json`.

Final focused native regression checks: **17 passed, one CUDA skip in 0.42 s**.
The passing tests verify accurate success/failure reporting and actual MPS
execution; they do not turn the deliberately failed diagnostic into a parity pass.
Both assemblies build with zero errors and existing platform warnings:
103 Grasshopper + 2 Rhino = 105. No installation. Full gate and final package
evidence follow below.
G0/G1 are scoped diagnostic self-review; G2 requires the final measured function
gate and meaningful tests of success, failure and provenance. G3 remains **FAIL**
for original CPU/MPS parity. G4/G6 are **NOT APPLICABLE** to this harness/test-only
increment: no solver/node/field/shared-state contract changes. G5 is **BLOCKED**
for release; development packaging does not constitute installation or release.


Initial published full function gate: **827 passed, 83 skipped, 18 warnings in 152.77 s**;
**33 production-linked state contracts pass**; zero ratchet failures against
`977bb78`. Skips: 82 unavailable CUDA cases and one unsupported MPS FP64 case.
Warnings: 14 existing Matplotlib/pyparsing deprecations and four upstream MRT
warnings. Matrices are refreshed and checked: 343 covered, 127 uncovered,
630 unmeasured, 58 declarations. Historical coverage debt remains visible.
Evidence: `results/parity-001/final/function-gate/`, `function-gate.log`,
`matrix-check.log`.

Final restricted Linux CPU run: **16 passed, two accelerator tests deliberately
deselected in 0.23 s**, no warnings. Python 3.9.25, PyTorch 2.8.0+cpu, NumPy 2.0.2,
aarch64 image `sha256:6b367745131c89cf349cd005532efe5ac708f871b1758105669406e468e18e93`;
one CPU, 2 GiB, no network, read-only source/root, writable temporary/results
storage. Evidence: `results/docker-parity-001-final/focused.{log,xml}`. This is a
focused CPU scope, not accelerator qualification or a Linux full function gate.

Final development package: `dist/Hawa-parity-001-final.zip`, with exact diagnostic
source, AGENTS/pyproject/lock inputs and no legacy example 09. Build and package
checks are in `results/parity-001/final/{build.log,package-final.log,package.json}`.
The final package refresh reuses the assemblies built above. No installation.

| Gate | Actual reviewer | Disposition | Scope |
| --- | --- | --- | --- |
| G0 | Parity-study agent, self-review | PASS | Pinned upstream/code reference; unchanged criteria and no numerical-method change |
| G1 | Parity-study agent, self-review | PASS | Explicit finite diagnostic scope, bounded sizes, exact initial tensors and provenance |
| G2 | Parity-study agent, self-review | PASS locally | Native/Docker focused checks, full measured gate, state contracts, matrices and developer package |
| G3 | Parity-study agent, self-review | FAIL for original parity | Full case remains failing; local sign/reset mechanism isolated; still-failing candidate rejected |
| G4 | Parity-study agent, self-review | NOT APPLICABLE | No UI, node, archive or installed-host change |
| G5 | Parity-study agent, self-review | BLOCKED for release | Developer package only; no installation or unrestricted numerical qualification |
| G6 | Parity-study agent, self-review | NOT APPLICABLE | No production solver, field format, shared state or node-contract change |


## PR #9 review follow-up

Integrated shared base `9999481daf13ae30725acb8f09e24717bbad4778` after PR #7
merged, preserving both diagnostic and domain-contract histories. Review findings
4519369173/4519369177 are tracked as HAWA-056/057, repaired in this PR candidate.

The previous diagnostic was run against an actual copied Lettuce package selected
through PYTHONPATH: it returned exit 0 while its report hashed the checkout's
vendor files. The candidate now records loaded `lettuce` module file paths,
requires every path to resolve inside this checkout's vendor package before
measuring, checks again afterward, and rejects changed module identities. The
same foreign-package command now saves `completed=false`, `passed=false` with its
actual foreign path and an explicit provenance error before measurement.

A second-size device error injected into the previous implementation dropped all
prior rows and the failing-size label. The candidate incrementally retains rows,
`completed_sizes` and `failed_size`; overall completion/pass remain false after
an error. Tests exercise both later device errors and nonfinite input, proving
that the first completed row survives. Evidence: `results/parity-001/review/`
(`reproduced.log`, `old-foreign-report/`, `old-partial-report/`,
`fixed-foreign-report/`, `focused.{log,xml}`). The foreign copy is scratch test
evidence, not a dependency or production change.

Fresh focused native checks: **24 passed, one CUDA skip in 0.60 s**. Final CPU
and actual-MPS CLI diagnostics were rerun after source freeze with loaded-path
provenance; CPU comparisons pass and MPS still completes with the expected
numerical-failure exit 1. The older diagnostic outputs above are historical
snapshots, not reused evidence for this revised source. No numerical thresholds
or production code changed; HAWA-001 remains open.


Final review-fix combined gate on `9999481`: **876 passed, 83 skipped, 18 existing
warnings in 151.65 s; 33 state contracts passed; zero ratchet failures**. Skips
remain 82 unavailable CUDA cases and one unsupported MPS FP64 case. Matrices are
regenerated and checked: 346 covered, 127 uncovered, 630 unmeasured, 58 declarations.
Evidence: `results/parity-001/review/function-gate/`, `function-gate.log`,
`matrix-check.log`. Final restricted Linux CPU focused check: **23 passed,
two accelerator tests deliberately deselected in 0.42 s**, no warnings, same
pinned image/restrictions; `results/docker-parity-001-review/focused.{log,xml}`.

Final review package-only refresh: `dist/Hawa-parity-001-review-final.zip`, using
the previously tested assemblies and exact combined source/build inputs, excluding
legacy example 09. Evidence: `results/parity-001/review/package-final.log` and
`package.json`. No C# source/build, installation, G6 or release claim is added in
this follow-up. G2 is refreshed by the combined checks; the other gate decisions
above remain unchanged. HAWA-056/057 await integration; HAWA-001 remains open.
