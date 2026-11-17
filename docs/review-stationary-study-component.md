# Grasshopper stationary-study adapter review

November 17, 2026. Author/test operator: Codex `wing_wrapup` agent. Independent
wire/unit/lifecycle review: Codex `gh_study_backend` agent. Root owns combined
Python/G6/host/package acceptance and final merge gates.

The new Stationary Study component submits the CPU-only study service; no
voxelization, solve, UI-thread wait or unfinished Task.Result occurs in the
adapter. It builds a bounded angle-outer/speed-inner crossproduct (maximum 64),
normalizes physical coordinates using Case dx/spacing, and welds exact seam
vertices on a temporary mesh copy. The caller's mesh is unchanged. Backend
worker admission remains authoritative for manifold topology and solver support.

Job ownership survives until explicit Run off, Cancel, changed physics/geometry,
invalid input, lock, unload or removal. Changed input requires a Run off/on rearm;
saved Run true opens idle. Retained HawaPollScheduler polling survives intervening
solutions. CaseHub.ReleaseJob retains failed cleanup acknowledgements for retry.
Changing Selected case only polls the existing job.

Completed coefficient lists preserve candidate indices and null rejected slots.
Selected mesh, immutable field and whole-body window means require matching
candidate/case/geometry/generation identities, usable single-body summary and
matching field snapshot session/phase/step/time. Raw whole-body Force and Moment
remain N and N m in world axes; Lift/Drag are +Z/+X projections. These are not
per-face pressure forces. Field capture is instantaneous, while force/moment
are averaging-window statistics; the Identity output records both scopes.

The field descriptor's display copy maps origin/spacing back into model units,
while dx/physical_dx, frame UUID and SI source identity remain intact. Stored
backend frames are not mutated. Selected mesh maps through the same scale.
Unusable selected candidates withhold field/mesh/load outputs. Any malformed
reply withholds all outputs and releases ownership; provisional meshes are
disposed on geometry conversion failures.

## Checks actually run

- Linked .NET 10 StateContracts: **152 passed**, including six new scenario
  groups covering port defaults, saved-true idle, request units/crossproduct,
  mm display and probe mapping, nullable index alignment, selection without
  restart, edits/rearm, pause/cancel, document transitions, missing/invalid
  inputs, stale/malformed provenance, summary usability, mesh cleanup,
  source-mesh preservation, item multiplicity and failed-close retry.
- Fresh Coverlet instrumented run: all **207/207 executable lines** in the new
  component executed with assertions. This is not exhaustive branch/concurrency
  proof. Combined committed function matrix is the root integrator's gate.
- Actual .NET 7 Grasshopper project build passes (103 existing platform/nullability
  warnings, zero errors); no assembly was installed or loaded by this lane.
- Whitespace check passes. Backend contract was checked against its actual
  service implementation, including top-level per-record CM and SI frame fields.

G1/G2: pass within these linked-test bounds. G3: no new solver method, physical
qualification or threshold change; units/projections are asserted, experimental
loads remain unqualified. G4/G6 live GH geometry, archives, scheduling, views and
full-node mapping await root's Rhino checks. G5 installation/package/release
remains root-owned. Test doubles never establish live Rhino acceptance.
