# Local Rhino acceptance review

The PR creator runs this review on their local Rhino machine; the maintainer
reviews the evidence and owns the merge decision. It is an important **soft
acceptance gate**, separate from automated GitHub tests, mutation testing and
measured function/line coverage. It does not require a self-hosted CI runner.
Missing or failed checks must remain visible for the maintainer's decision;
a checked box, screenshot, archive audit or old report is not a fresh pass.

For code PRs, open **all supported examples**, execute their workflows, render
results, and inspect both numbers and images. Use the current source inventory,
not a historical count in a review. At this revision there are 31 supported GH
archives plus native-only example 23: 32 numbered workflows (01–33 except 09).
Include the saved native-block fixture with 21 and the canopy model with 22.
Development examples remain in scope as workflow checks with their documented
limitations; their inclusion does not qualify experimental physics.

Read the [gallery catalogue](../examples/grasshopper/README.md),
[native catalogue](../examples/native-prototype/README.md),
[example verification criteria](../examples/grasshopper/VERIFICATION.md) and
[quality gates](quality-gates.md). Agents operate through
[Rhino MCP](agents/rhino-mcp.md). Before running a revised branch, identify the
actual loaded plugin build; a checkout SHA alone does not identify installed code.
Build with `scripts/build_plugin.py` and follow the normal installation/restart
workflow if needed. Never replace a loaded assembly or kill Rhino.

## Preserve the work and define the check

- Open copies in owned documents, retaining IDs, wires and parameters. Preserve
  existing user geometry/documents. **Do not regenerate, overwrite, package or
  test-modify legacy 09**; use 10 for the supported hull-search workflow.
- Record the commit, plugin version and artifact/hash, OS, Rhino/GH versions,
  embedded Python/PyTorch versions, requested and actual device/dtype, model
  units, input assets and exact settings. Keep machine-specific paths out of
  shipped definitions; use new absolute output paths for recordings/checkpoints.
- Before each run, state the expected numerical observables and visual result,
  using its guide and verification criteria. Record reference values/tolerances
  where defined; do not invent tolerances or relax them after a failure.
- A bounded smoke configuration is acceptable for this workflow review when its
  changed settings are explicit. Complete the bounded run, recording or candidate.
  For cycle search, include settling and complete measured cycles. A short trial
  does not pass an 8000-step wake study, convergence study or full-duration gate.

## Execute and inspect every workflow

1. Open the definition/native model, confirm expected controls and report missing
   components, archive warnings and runtime errors. Begin with Run off.
2. Execute and observe progress without blocking the Rhino/GH event loop. Check
   completion identity, actual steps and physical time; use the same snapshot
   and physical time for related field, body and load views.
3. Inspect numeric reports: finite values, correct units/signs, sample counts,
   valid masks, selected field/device, expected trends or reference comparisons,
   as applicable. Record actual numbers rather than only “looks correct”.
4. Render the relevant viewport and inspect the canvas/output reports. Check
   nonempty valid geometry, expected spatial extent/orientation, body pose,
   field/legend/range agreement and unexpected clipping, stale or blank output.
   Capture both the relevant viewport and canvas/report, linked to the result
   identity. A generated image that nobody inspected is not visual acceptance.
5. Exercise applicable pause/resume/cancel, invalid-input/recovery and reopen
   checks from the example criteria; add change-specific regressions. Stop and
   dispose owned work, confirm cleanup, and preserve originals.

## Inventory and review record

Copy the table into the PR evidence record and add one result row per example.
Every row starts **not run**; this document records requirements, not results.
Record `pass`, `fail`, `blocked` or `not run`, settings/device/steps/time, numerical
observations, image/report links, reviewer and date. For a failure or omission,
include the reason, GitHub issue if needed, next action and maintainer disposition.
Reconcile added/removed examples against both catalogue directories and
`scripts/build_plugin.py`; do not silently shrink the denominator.

| ID | Workflow / required inspection focus |
| --- | --- |
| 01 | 3D TGV BGK: finite fields, velocity decay, selected backend |
| 02 | 2D TGV BGK: planar decay and physical-time reference |
| 03 | 2D TGV TRT: collision choice and matching-time comparison to 02 |
| 04 | 2D TGV Smagorinsky: finite decay and declared model/grid differences |
| 05 | 3D TGV Smagorinsky: finite fields and comparison settings |
| 06 | Cavity: wall conditions, recirculation and profile |
| 07 | Poiseuille: force convention, channel profile and mass balance |
| 08 | Block: domain units, valid slice and flow lines |
| 10 | Hull search: completed candidate/objective ownership and controls |
| 11 | 3D views: one snapshot, planes/contours/isosurfaces, field legends |
| 12 | Airfoil/wing: local data, closed wing, synthetic-polar warning |
| 13 | Recording: completed manifest, valid playback frame and metadata |
| 14 | Curved sphere: pressure/surface samples and stationary-wall limits |
| 15 | Fixed refinement: supported patch, aligned time, coarse/fine fields |
| 16 | Wake recording: completed bounded trial, final frame and wake observables; label full 8000-step run separately |
| 17 | Oscillating cylinder: trajectory, clearance, same-time field/body/loads |
| 18 | Pitching airfoil: radians, rotation origin, load signs and closure |
| 19 | Rotating paddle: RPM, torque/power signs and body/field alignment |
| 20 | Cycle search: settling, whole measured cycles, candidate ID/objective |
| 21 | Native live sync + native-block.3dm: ownership, panel/GH edits, undo/reopen and cleanup |
| 22 | Native selected geometry + canopy.3dm: selection, physical units, invalidation, display and paired reopen |
| 23 | Native curved-solid.3dm: pressure/speed slice outline, fixed ranges, equal-time spacing comparison |
| 24 | Boundary transfer: parent/capture/child completion, mapped vector inlet and matching time |
| 25 | Channel boundaries: profile, walls/open outlet, finite plane and rejected incompatible setup |
| 26 | Bidirectional faces: Y orientation, initial velocity sign and valid plane |
| 27 | Cropped solid: mixed fluid/solid boundary mask and supported donor behavior |
| 28 | Rough floor: finite fields, roughness controls and explicit atmospheric limitations |
| 29 | Roughness sensitivity: wall traction at equal physical time and changed z0 |
| 30 | Cropped buildings: geometry, boundary setup, quality report and shared slice time |
| 31 | Tunnel/probes/checkpoint: runtime/device, probe vectors, save/load/export |
| 32 | Translation/recording: completed frames, playback frame and matching body pose |
| 33 | Three-stage transfer: all recordings/captures, common final physical time, shared slice and quality/statistics limits |

Suggested per-example evidence row:

| ID | Status | Settings / device / steps / time | Observed numbers and criterion | Canvas + viewport + report | Failure/omission and disposition |
| --- | --- | --- | --- | --- | --- |
| … | not run | … | … | … | … |

Record totals for required/opened/executed/rendered/numerically inspected/visually
inspected/passed/failed/blocked/not run. Link a [review record](review-record-template.md)
and list reviewers. The maintainer records any accepted omissions explicitly.

## What the evidence means

This review supports local workflow and visual/numerical sanity acceptance. It
cannot establish engineering accuracy, convergence, atmospheric qualification,
all hardware combinations or all possible GH graphs. CPU evidence does not verify
MPS/CUDA. Historical numerical failures and unverified configurations stay open.
A full physics claim still needs its independent numerical/research gates.

Headless tests measure linked production C# against doubles. Real-host methods
remain **unmeasured** unless instrumented evidence actually measures them. Local
example review does not turn those entries into covered functions or lines, and
its omission cannot be concealed by a green automated check.
