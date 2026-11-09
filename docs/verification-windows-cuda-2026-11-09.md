# Windows CUDA verification — November 9, 2026

**Decision: CUDA execution works in the tested headless environment, but the
complete numerical parity matrix does not pass.** PorousMedium exceeds the
existing pointwise CPU/CUDA tolerances. A rotating-sphere case also has a
CPU/CUDA surface-mask discrepancy and fails torque parity. Clean Rhino CUDA installation and live
Windows host behavior are not verified by this run.

- Source: `d3a5793` plus the local verification/test changes recorded in the
  evidence directory. No production numerical code or upstream tests changed.
- Author/reviewer: Codex, self-review across the gates below; no independent
  human, numerical specialist or second agent approval is claimed.
- Environment: Windows 11 Pro, build 26300; RTX 5070 Ti, 16,303 MiB VRAM;
  driver 621.14; Python 3.9.25, PyTorch 2.8.0+cu128, CUDA runtime 12.8,
  NumPy 2.0.2. GPU capability 12.0; the wheel includes `sm_120`.
- Both explicit `cuda:0` and `auto` selected the GPU and completed the operation
  probe. The tested solver uses portable PyTorch tensors (`use_native=False`).
- Acceptance criteria: existing test assertions and parity tolerances retained;
  actual CUDA execution required; missing inventories fail; skips do not pass.
  The supplemental benchmark criteria are declared in its runner before execution.
- Scope: implementation verification and bounded workflow execution. This is not
  engineering validation, full upstream convergence or a GPU speed benchmark.

## Measured results

| Check | Result | Evidence |
| --- | --- | --- |
| Hawa repeated suite before the newly discovered geometry regression | 187 passed, 71 skipped per run, four successful runs after coverage expansion | `final/hawa-{1,2,3}.xml`, `counter-recheck/hawa-1.xml` |
| Final Hawa suite with geometry regression | **187 passed, 1 failed, 71 skipped**; the only failure is the new surface-mask regression | `with-geometry-regression/hawa-1.xml` |
| Explicit CUDA test parameters | 69 passed per run, zero CUDA skips; six additional CPU/GPU parity tests exercised CUDA | Same JUnit files; test source |
| Hawa skips | 70 MPS-only cases; one CPU-default test inapplicable when CUDA is available | JUnit skip reasons |
| Portable vendored upstream suite | 750 passed, 123 upstream skips, 424 native parameter cases deselected; native test directory excluded | `final/upstream-portable.xml` |
| Upstream explicitly parametrized CUDA subset | 331 passed, 61 upstream skips | Same JUnit file |
| Isolated unmodified upstream CPU oracle suite | 419 passed, 884 skipped | `upstream-reference.log`, `upstream-reference.xml` |
| Core oracle comparison | CPU FP32/FP64 bitwise equal; CUDA passes all 96 array comparisons at 0, 1, 10, 50 steps | `final/parity/report.json` |
| Upstream example execution | All 16 entrypoints complete on CPU and CUDA; bounded 50 steps, 250 for the intentional failure example | `repaired-examples/backport-cpu/report.json`, `final/examples/backport-cuda-0/report.json` |
| Example field parity | **15/16 pass; PorousMedium fails** | `example-parity.json` |
| Supplemental numerical benchmarks | **12/13 pass; rotating sphere at dx=1/3 fails CPU/CUDA torque parity** | `benchmarks.json` |
| Original source/test audit | Expected 16 changed source modules, 62 unchanged modules, all 61 upstream test files unchanged after CRLF normalization | Runner source audit |
| Shared state contracts | 33 passed on .NET 10, using production service source with host/transport doubles | `state-contracts.log` |
| Windows plugin build/package | Both assemblies built; ZIP integrity checked; legacy example 09 excluded | `build-plugin.log`, `build-hashes.json` |

Raw evidence is under [`results/windows-cuda/2026-11-09`](../results/windows-cuda/2026-11-09).
The compact [machine-readable summary](verification-windows-cuda-2026-11-09.json)
records the final outcomes and supplemental benchmark measurements.

The core comparison covers six common cases. Cavity is identified as an upstream
constructor repair, not compared against a failing oracle constructor; Hawa's
own CUDA cavity tests and example execute separately. CUDA comparison tolerances
remain `rtol=3e-4`, `atol=2e-6`, with the existing physical-pressure conversion
scale applied to pressure. Upstream skips include unsupported stencil/model
combinations, precision exclusions and upstream TODO tests.

## PorousMedium failure

The 512 × 512 FP32 KBC example completes 50 steps with finite populations on
both devices. The obstacle masks are exactly equal. These pointwise checks fail:

| Field | Maximum absolute CPU/CUDA difference | Relative L2 difference | Existing pointwise result |
| --- | ---: | ---: | --- |
| Populations | 0.000772208 | 9.92e-6 | FAIL |
| Density | 0.000606954 | 4.56e-6 | PASS |
| Physical velocity | 0.0271833 | 1.68e-4 | FAIL |
| Physical pressure | 0.242783 | 2.29e-4 | FAIL |

The example comparator retains `rtol=1e-3` and `atol=1e-5`, scaled to the physical
units for velocity/pressure. Small aggregate norms do not waive the pointwise
failure. A fresh repeat of the CUDA PorousMedium run produced bitwise-identical
populations, density, velocity and pressure, reproducing the same CPU discrepancy
(`porous-repeatability.json`). The previously documented CPU/MPS discrepancy remains unresolved too;
similar symptoms do not establish the same cause on CUDA. Do not claim universal
device parity. Follow-up owner: maintainer, unassigned. Next check: isolate KBC
checkpoint/collision differences, compare FP64 behavior, and retain the current
tolerances as the acceptance test.

## Rotating-sphere geometry and torque failure

The existing rotating-sphere benchmark runs to physical time 20 and averages
torque after time 15. It uses radius 1, angular speed 0.1 rad/s, density 1,
viscosity 0.2 and a periodic finite box. The CPU/CUDA comparison was fixed at
`rtol=3e-4, atol=2e-6` before measurement.

| Cell size | Steps | CPU mean Z torque | CUDA mean Z torque | Device parity |
| --- | ---: | ---: | ---: | --- |
| 0.5 | 693 | -0.5710439223 | -0.5710410400 | PASS |
| 1/3 | 1040 | -0.5356813699 | -0.5348282566 | **FAIL** |
| 0.25 | 1386 | -0.5176966488 | -0.5176944953 | PASS |

At dx=1/3, torque differs by 0.0008531133 (0.159258% relative to CPU). A separate
initial-geometry diagnostic finds identical coordinates and 109 solid cells on
each device, but **four different cell classifications**. At those sites, the
signed distance is zero on one device and `1.1920928955078125e-7` on the other;
`sdf <= 0` changes the mask. The other resolutions have identical masks. This is
a concrete geometry defect and a candidate contributor to torque disagreement;
this run does not isolate its entire contribution to the final force history.

`test_rotating_sphere_surface_mask_matches_cpu[cuda:0]` now captures this defect
as a fast regression. It is deliberately not marked xfail, and must fail until a
numerically justified classification/link-distance policy fixes the discrepancy.
Evidence: `rotation-geometry-diagnostics.json` and its reproduction script,
`diagnose_rotation_geometry.py`, in the raw evidence directory.
Follow-up owner: maintainer, unassigned. Acceptance: identical masks for the
surface-cell regression plus all three torque comparisons at unchanged
tolerances; repeat moving-body/reflection/conservation checks after any repair.

The other ten benchmark pairs pass: comoving-body invariance, three refinement
grids, and six fractional-wall channels. CUDA refinement relative L2 errors
decrease from 0.00314085 to 0.00118033 to 0.000558717, outperforming the coarse
reference; mass drift stays below 1.14e-6. Fractional-wall analytic errors decrease
from about 3.7–3.9% at n=8 to 0.52–0.57% at n=16. These finite-grid measurements
do not establish general physical validity.

## Harness and environment findings

1. Plain `uv sync --extra test` installed CPU-only PyTorch on Windows. The initial
   baseline passed 118 tests and skipped 59, including CUDA. Installing the
   official CUDA wheel enabled actual GPU tests. The Rhino bootstrap still asks
   for plain `torch==2.8.0`; clean-host CUDA dependency selection remains open.
2. Windows manifest separators and CRLF checkout conversion broke the source
   audit. Normalization is limited to those differences; a regression confirms
   that substantive source changes, changed tests and extra files still fail.
3. Relative worker output paths and nested example paths prevented valid evidence
   from being written. The harness now resolves paths before changing directory.
4. Two upstream cylinder entrypoints imported Unix `resource` only for a memory
   diagnostic. The isolated Windows worker supplies real peak working-set data
   through `psutil`; original example files and solver calculations are unchanged.
5. Four upstream tests implicitly requested generated native CUDA kernels and
   failed without `CUDA_HOME`/the compiler toolkit. All four pass with the explicit
   portable test adapter. The native extension is excluded, not certified.
6. The first new summary counter mistook the skipped CPU test named
   `non_cuda_machine` for a CUDA case. Its raw report marks the three Hawa stages
   FAIL despite exit code 0 and passing JUnit results. The counter now inspects
   parameter IDs; `counter-recheck/report.json` confirms PASS with 69 CUDA cases
   and no CUDA skips. The original report is retained rather than overwritten.
7. NuGet had no configured sources. Explicit restoration from the official
   NuGet feed allowed both plugin builds. Global configuration was not changed.
   The build retains CA1416 platform warnings; they are not CUDA test failures.

## Gate decisions and remaining work

| Gate | Reviewer | Decision | Scope/reason |
| --- | --- | --- | --- |
| G0 research/evidence | Codex, self-review | PASS | Scoped hardware claim, pinned reference, criteria fixed before measurement; PyTorch's official wheel instructions linked in setup guide |
| G1 architecture | Codex, self-review | PASS for this verification change | No production ownership/threading changes; 33 state contracts pass |
| G2 software/reliability | Codex, self-review | **FAIL for the newly exposed geometry regression** | Earlier repeated tests pass; the new regression exposes backend-dependent solid classification; harness repairs and builds pass |
| G3 numerical verification | Codex, self-review | **FAIL for universal parity** | Core checks pass; PorousMedium pointwise and middle-grid rotating-sphere torque comparisons fail |
| G4 UI/UX/examples in host | Unassigned | BLOCKED | No Rhino MCP connection; no live Windows Rhino/GH run or screenshots |
| G5 release/integration | Unassigned | BLOCKED | Local build/ZIP checks pass; clean Rhino CUDA installation and installed-binary host behavior remain unverified |

See [Windows CUDA setup and repeat commands](windows-cuda.md). The verification
commands intentionally exit unsuccessfully while the surface-mask, strict
PorousMedium parity and rotating-sphere failures remain. Follow-up host acceptance requires a clean Rhino environment,
reported `cuda:0` selection, actual example execution, pause/cancel/close checks,
and valid saved/reopened graphs. No release is published by this work.
