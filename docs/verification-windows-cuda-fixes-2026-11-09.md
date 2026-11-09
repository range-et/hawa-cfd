# Windows CUDA numerical repairs — 2026-11-09

Branch: `codex/windows-cuda`, based on `d8d8040`. Author and reviewer: Codex,
self-review in separate research, architecture, reliability and numerical passes;
no independent reviewer. This record concerns headless implementation verification,
not physical validation or an installed Rhino release. The
[initial report](verification-windows-cuda-2026-11-09.md) preserves the failures.

## Changes and acceptance criteria

**Moving geometry:** four surface cells differed between CPU and CUDA at sphere
radius 1 and dx=1/3. Replace backend-dependent norm/matrix reductions with ordered
small reductions and evaluate radial distance as `(r_squared-R_squared)/(r+R)`.
The numerator determines the surface sign; classification and wall links use the
same distance. No mask epsilon or comparison tolerance is added. Tests include
immediate FP32 neighbours of the surface and off-pivot sphere/cylinder rotations.

**PorousMedium:** FP32 moment cancellation in KBC's higher-order stabilizer
amplified small backend differences. Compute the collision in FP64 on the selected
CPU/CUDA device, round the returned populations to FP32, and keep storage,
streaming and the existing degeneracy guard in storage precision. The original
flow/context/stencil remain untouched. FP64 inputs retain their existing path.
MPS retains its previous FP32 path; its historical parity issue is unresolved.
No CPU fallback, new dependency or changes to upstream tests/notebooks are used.

Acceptance was fixed before the repair: exact sphere-mask equality; all bounded
example fields at existing `rtol=1e-3`, `atol=1e-5` scaled to physical units;
benchmark scalar parity at `rtol=3e-4`, `atol=2e-6`; existing motion invariance,
refinement improvement and mass-drift thresholds. A captured near-equilibrium KBC
cell now also checks rounded FP64 agreement, mass/momentum conservation, original
input preservation and dtype/device retention. D2Q9/D3Q27 equilibrium is tested.

Alternatives investigated: computing shear directly from `f-feq` did not repair
the 50-step PorousMedium difference. Merely ordering the norm leaves avoidable
sqrt-minus-radius cancellation; rationalization supplies a consistent sign rule.
Promoting the whole simulation was unnecessary. The collision promotion has a
real resource cost, measured below.

Primary references: the unchanged KBC model is described by
[Bösch, Chikatamarla and Karlin (2015)](https://arxiv.org/abs/1507.02518).
[PyTorch numerical accuracy](https://docs.pytorch.org/docs/main/notes/numerical_accuracy.html)
describes floating-point/backend reduction limits. These explain the investigation;
the repair is supported by repository measurements, not certified by those sources.
Upstream MIT attribution and Hawa GPL-3.0-only licensing are retained.

## Configuration and reproduction

Windows 11 Pro (Python reports build 26300), RTX 5070 Ti 16 GB, driver 621.14,
Python 3.9.25, PyTorch 2.8.0+cu128, CUDA runtime 12.8, NumPy 2.0.2. Requested and
selected backend `cuda:0`; compute capability 12.0. Oracle: isolated Python 3.12,
unmodified Lettuce `88a6559def2a49fd7f425fd05954ec1e3db2cdb6`, CPU PyTorch 2.8.
Use the explicit CUDA environment setup in [windows-cuda.md](windows-cuda.md).

```powershell
$env:PYTHONUTF8='1'
.venv\Scripts\python.exe scripts/verify_cuda.py --output results/windows-cuda-fixes/2026-11-09/final --repeats 3
.venv\Scripts\python.exe scripts/verify_cuda_benchmarks.py --output results/windows-cuda-fixes/2026-11-09/benchmarks.json
.venv-reference\Scripts\python.exe -m pytest .reference/upstream-tests/tests -q -ra --junitxml=results/windows-cuda-fixes/2026-11-09/oracle-isolated.xml
dotnet run --project tests/dotnet/StateContracts
.venv\Scripts\python.exe scripts/build_plugin.py
```

Use fresh output paths when repeating; the runners reject existing results.
The isolated test copy is prepared by `scripts/run_upstream_tests.py --reference`.
Raw evidence lives under `results/windows-cuda-fixes/2026-11-09/` (ignored by Git).
The tracked JSON summary retains counts, source hashes and numerical results.

The original PorousMedium notebook runs its 512×512 FP32 case for 50 steps;
its actual relaxation time is 0.5009765625. Both devices use the unchanged source
and matching obstacle mask. Other upstream entrypoints run 50 bounded steps,
except the intentional failure-detector scenario (250), whose divergent fields
are excluded by the pre-existing comparison policy.

Rotating-sphere checks use dx=0.5, 1/3, 0.25 in an 8-unit periodic finite box,
radius 1, viscosity 0.2, density 1, angular speed 0.1, Mach 0.1 and BGK. Run to
physical time 20 and average torque after time 15. The finite-box analytic error
is reported rather than claimed as unbounded-domain validation. Supplemental
coverage includes comoving invariance, three refinement grids and six fractional
wall configurations. This is a declared test matrix, not exhaustive CUDA coverage.

## Results

| Check | Result | Evidence under the raw root |
| --- | --- | --- |
| Hawa suite, three consecutive runs | 204 passed / 77 skipped each; 78 named CUDA cases, zero CUDA skips each | `final/hawa-{1,2,3}.xml` |
| Portable upstream suite | 750 passed / 123 skipped / 424 native-parameter cases deselected | `final/upstream-portable.xml` |
| Isolated unmodified CPU oracle | 419 passed / 884 skipped | `oracle-isolated.xml` |
| Core comparison | 96 arrays per device/dtype; CPU FP32/FP64 bitwise; CUDA within unchanged tolerances | `final/parity/report.json` |
| Original bounded examples | 16/16 execute on each device and pass comparison policy | `final/examples/parity.json` |
| Supplemental benchmarks | 13/13 configurations pass | `benchmarks.json` |
| State contracts | 33 passed, host/transport doubles | `state-contracts.log` |
| Windows plugin builds | Both succeeded; existing CA1416 icon warnings | `build.log` |
| Local ZIP | Integrity, selected binary/source bytes and upstream notices match; legacy example 09 excluded | `package-check.json` (archive SHA256) |
| Upstream source audit | 16 declared changed modules, 62 unchanged modules, 61 unchanged test files | `final/report.json` |

The Hawa skips are 76 unavailable MPS cases and one CPU-default check inapplicable
when CUDA exists. Upstream portable skips are intrinsic unsupported/TODO/precision
cases; generated native CUDA tests are excluded. The CPU-only reference wheel
cannot run CUDA. Warnings concern existing experimental moment implementations,
deprecated upstream interfaces/indexing, matplotlib parsing and platform icons.
No warning is treated as proof of numerical correctness.

PorousMedium maximum CPU/CUDA differences after 50 steps:

| Field | Before repair | After repair |
| --- | --- | --- |
| Populations | 7.72208e-4 | 1.78813934e-7 |
| Density | 6.06954e-4 | 4.76837158e-7 |
| Physical velocity | 2.71833e-2 | 1.04904175e-5 |
| Physical pressure | 2.42783e-1 | 1.92642212e-4 |

All four fields now pass the original tolerances. A separate diagnostic against a
full-FP64 trajectory reduced CPU population error from about 7.73e-4 to 4.33e-5.
This is evidence of improved numerical agreement, not convergence of the physical
problem. The diagnostic is in `porous-trace.json` / `porous-wide-storage-guard.json`;
the authoritative acceptance is the original example field report.

Rotating sphere torque (CPU / CUDA):

| dx | Steps | CPU | CUDA | CPU error vs unbounded analytic torque |
| --- | --- | --- | --- | --- |
| 0.5 | 693 | -0.5710429604 | -0.5710407328 | 13.61% |
| 1/3 | 1040 | -0.5312922752 | -0.5312904149 | 5.70% |
| 0.25 | 1386 | -0.5176972931 | -0.5176945396 | 2.99% |

The middle-grid CPU/CUDA difference decreases from 8.531e-4 to 1.8603e-6.
CPU torque also changes because the repaired surface classification changes the
discrete geometry; this is not a CUDA-only adjustment to match an old CPU answer.
The grid trend improves, but the finite domain remains a limitation. Comoving
force stays below 3.16e-4 N (limit 0.002 N). Across the refinement grids, refined
errors are lower than coarse errors and maximum relative mass drift is 1.20e-6
(limit 3e-6). All six fractional-wall speed comparisons pass.

KBC resource diagnostic: three fresh 512×512 PorousMedium simulations per
implementation/device, one CPU thread, five warm-up steps followed by 50 timed
steps. CUDA is synchronized around timing; other verification jobs had finished.
Old collision source is loaded from `d8d8040`; the rest of the solver and inputs
are identical. Python garbage collection separates repetitions.

| Device | Old median seconds | Fixed median seconds | Ratio |
| --- | --- | --- | --- |
| CPU | 1.6011 | 2.8306 | 1.77× |
| CUDA | 0.2151 | 0.2602 | 1.21× |

Peak CUDA tensor allocation increases from 73,929,728 bytes to at most
145,234,944 bytes (70.5 to 138.5 MiB). This is PyTorch allocated memory, not total
driver/process memory. CPU peak memory was not measured. The precision repair is
therefore about 21% slower on this CUDA case and uses about twice the temporary
tensor memory; it does not change BGK/TRT collisions. These small-run timings are
a local cost diagnostic, not a general GPU speed claim. Raw measurements and
reproduction script: `kbc-cost.json` and `time_kbc.py` under the evidence root.

## Review gates and exclusions

| Gate | Actual reviewer | Decision | Scope and evidence |
| --- | --- | --- | --- |
| G0 research | Codex, self-review | PASS | Scoped claim, primary references, unchanged acceptance criteria, alternatives recorded |
| G1 architecture | Codex, self-review | PASS | Device/state ownership preserved, no host/schema changes, 33 state contracts pass |
| G2 reliability | Codex, self-review | PASS for headless repair | Regressions, three complete suite runs, unchanged upstream tests, both plugin builds |
| G3 numerical verification | Codex, self-review | PASS for declared matrix | Full bounded examples, isolated reference, core parity and 13 benchmark configurations; no physical-validation claim |
| G4 UI/UX | Codex, scope review | NOT APPLICABLE to headless change | No UI changes; live Rhino/GH remains unverified |
| G5 release/integration | Unassigned host reviewer | BLOCKED for installed release | Local build/package checks only; clean-host CUDA installation and host behavior remain open |

Live Rhino/GH UI, clean-host CUDA dependency selection, generated native CUDA
extensions, MPS and long-duration engineering validation are outside this
headless repair claim. Follow-up owner is the maintainer assigning the host/MPS
reviewer: repeat the original strict PorousMedium comparison on Apple hardware;
for host acceptance, verify a clean CUDA install, selected `cuda:0`, example
execution, pause/cancel/close and saved/reopened graphs.
No host adapter, case ownership, archive schema or public node changes were made.
The plain Rhino bootstrap torch pin remains a separate installation issue.
No assemblies are installed over a running Rhino and no release is published.
