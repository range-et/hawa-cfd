# Real CPU headless sweep integration — #40 partial

Date: November 17, 2026. Integrator: Codex root. Implementers: measurements
(executor), wing_example (voxelized wing preparation), root (headless driver).
Independent review/tests: sweeps (real-session replay and lifecycle), wing_example
(frame/provenance and driver review). These are actual agent activities, not
independent physical-validation or maintainer approvals.

Source base remains `12dc774`; foundation evidence is in the
[earlier review](review-measurement-foundation.md). This increment's executable
source is `76c019a`; subsequent changes record evidence only.

## Delivered behavior

[Headless guide](headless-wing-sweeps.md). The existing controller now has a real
CPU float32 executor using fresh private Sessions, a closed blended-wing mesh
voxelizer, exact final case/geometry hashes, step-aligned physical windows,
pressure/load histories, retained field/session provenance and three plot-data
views. No production solver, runtime dispatcher, exporter or Rhino adapter was
edited. No global Session registration or GPU fallback occurs.

The worker owns allocation and one-step advancement. Pause/cancel signal a
condition; only the worker waits. Close retains ownership until thread exit,
including preparation, errors and delayed result publication. Detailed results
survive close. Unknown/unstarted results remain absent, not fabricated. The
blocking CLI driver drains on cancellation/KeyboardInterrupt and belongs outside
a host solution thread.

Pressure and momentum-exchange observations share the actual
`after-collision-before-obstacle-reflection-and-stream` phase, rather than merely
sharing a step number. An independent direct Session replay verifies the values
at that phase. Reports retain elapsed source times and actual session IDs; they
are not relabelled as later field snapshots. Quality is assessed during capture
and after advancement, including sticky warnings/rejections.

## Review findings repaired before final measurement

- World-frame metadata initially could disagree with the hashed case while
  changing torque arms and probe sampling. Admission now compares against the
  authoritative case geometry, including the dx/spacing origin conversion.
- Existing `sample_arrays` returns a NumPy scalar; the strict pressure contract
  requires a Python scalar. The adapter converts explicitly before validation.
- Per-case limits were insufficient when detailed histories accumulated across
  64 cases. Admission now bounds aggregate retained rows, field cells and mesh
  data before duplication (100000 rows, 1500000 cells, 200000 vertices/400000 faces).
- The example voxelizer requires oriented closed manifold topology and nonzero
  triangles before ray classification; open faces parallel to a ray cannot evade
  closure admission. Analytic inclusive boxes, shared edges, translation,
  partial-cell and overlapping-shell controls supplement generated-wing tests.

Prepared mappings remain a trusted internal adapter boundary: both input mesh
and final solver case are hash-checked, but the executor does not independently
prove arbitrary mesh-to-mask equivalence. The wing producer performs voxelization.
The original scalar measurement/sweep schemas are unchanged; the detailed
Python result envelope is versioned `hawa-cpu-sweep-result-1`. Final review added
that explicit tag before final measurement. This is internal result provenance,
not an export interchange contract.

## Real numerical workflow evidence

macOS arm64, PyTorch 2.8.0; explicit CPU float32, single OMP/MKL thread, reduced
process priority. Synthetic demo: NACA 2418 root / 0018 tip, span 0.6 m,
root/tip chords 0.3/0.2 m, fixed area 0.15 m², MAC 0.2533333333 m. Domain
33×41×25, dx0.025 m, origin[-0.2,-0.5,-0.2] m; speed1 m/s, density1 kg/m³,
kinematic viscosity0.01 m²/s, lattice Mach0.03; stationary full-way BGK.

Both −3°/+3° geometries were separately voxelized (269/249 solid nodes). Exact
case and geometry hashes are retained in the console evidence. The initial
10-settling/8-sample run rejected both for stationarity. A 200/32 run accepted
−3° and rejected +3°. The 1000/64 run accepted both under the **unchanged 0.05
absolute coefficient drift criterion**. The latter duration is now the default.
This is a settling exploration at fixed grid/domain, not a convergence study or
predeclared physical benchmark. Earlier rejected results were retained.

| Angle | CL | CD | Workflow status |
| --- | --- | --- | --- |
| −3° | 0.1312022747 | 1.3315546401 | Accepted numerical envelope/window/stationarity |
| +3° | 0.1737013760 | 1.3287346632 | Accepted numerical envelope/window/stationarity |

These numbers are experimental coarse-grid workflow output, not qualified wing
performance. All three ordered plot-data views contain the two accepted points.
Each demo attempt ended with zero executor handles, workers and session IDs.
Raw console evidence: `results/headless-sweep-demo/{console,settled-console,longer-console}.json`.
The [committed final-source capture](verification-real-headless-sweeps.json)
repeats the 1000/64 solve on `76c019a`: both complete in 31.99 s total, each with
1064 retained loads and 1064 valid upstream pressure samples. Session IDs, source
field stamps, array hashes, references, quality and stationarity diagnostics are
retained. Final ownership audit is zero handles/workers/sessions.
The long run used explicit `--settling-steps 1000 --sample-steps 64` on unchanged
solver/geometry source, before those values became the defaults.

## Automated evidence

99 focused tests passed on the integrated Python3.9 source. This includes eight
independent real-pipeline tests: fresh sessions and repeatable identities,
low-Mach rest controls, genuine warning gaps, exact-phase pressure replay,
transformed/invalid probes, pause/resume/cancel/dispose, admission before
allocation and real short-wing rejection. Per-lane Python3.12 checks also pass.
The final Python3.9 combined suite passed **2197 tests, 176 skipped** (226.11 s),
with **127** linked C# state contracts. The strict headless coverage gate and
trusted-base ratchet passed with **1086 covered functions, 299 existing unmeasured
host functions and 60 declarations, zero failures**. The committed matrix was
refreshed from `results/real-sweep-function-gate-final` and rechecked against
`12dc774`. The earlier run also passed but predates the result-envelope tag.
All 463 executable statements in this increment
(executor280, voxel recipe120, driver63) were measured; existing host debt was
not hidden. Executor branch coverage is 95/96 (the terminal-but-still-alive
close branch was not deterministically forced); driver and voxelizer branches
are fully covered. This is not exhaustive interleaving evidence. Ruff and local
documentation link checks pass.

The complete Python3.12 suite passed **2187 tests, 186 skipped** (164.15 s),
recorded in `results/real-sweep-py312.xml`. Suite accelerator checks were
intentionally disabled using the CPU-only availability shim; interpreter-specific
skips remain explicit. Skips are not device qualification. Existing plotting
and dependency deprecations account for recorded warnings (211/213 respectively).
The final-source real-sweep capture and CPU smoke are recorded below.

The final explicit CPU smoke gate passed **5/5**, with unchanged source and
zero module-identity errors, against the existing CPU FP64 reference policy
(`results/real-sweep-cpu-smoke-final/manifest.json`). The earlier smoke attempt
passed all five numerical comparisons but was correctly invalidated by a
concurrent documentation edit (`source_unchanged=false`); that failed evidence
is retained in `results/real-sweep-cpu-smoke`. The frozen rerun is the pass.
No numerical criterion, tolerance or source policy was changed.

## Gate disposition and remaining scope

| Gate | Disposition | Evidence / boundary |
| --- | --- | --- |
| G0 | PASS for bounded software workflow; physical reference BLOCKED | Existing solver/measurement contract, fixed acceptance criterion; no new physical benchmark or experimental drag reference |
| G1 | PASS for headless ownership | Worker-only solving, exact candidate/session/source provenance, frame binding, aggregate budgets, retained cleanup; public host adapter remains open |
| G2 | PASS for automated suite/coverage scope; new-module mutation study OPEN | Fresh combined headless measurement and real/fault tests; targeted mutation study remains outstanding, no merge-ready claim |
| G3 | PASS for implementation/replay and bounded workflow; physical qualification BLOCKED | Independent same-phase sampling and deterministic replay, accepted/rejected real cases; no accuracy, grid/domain/time convergence or device-parity claim |
| G4 | BLOCKED by explicit CPU/headless scope | No Rhino/GH scheduling, canvas/viewport or host lifecycle execution |
| G5 | NOT APPLICABLE | Source draft only; no package/install/release or merge claim |
| G6 | Bounded internal contract tests PASS; public host/device extension BLOCKED | No new public node, enum, archive or existing advertised solver combination; no full G6/host acceptance claimed |

#40 remains open for public runtime/GH adapters and plotting, #35 interchange
integration, archive/readback/live-host acceptance, targeted mutation studies,
physical reference protocol and device/release qualification. Export and Rhino
remain with the other chat. No installed assemblies, existing examples or legacy
example09 were touched. User-authorized CPU/headless work is complete at the
internal executor/driver boundary; headless success must not close the full issue.
