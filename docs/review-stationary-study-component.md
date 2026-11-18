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

- Linked .NET 10 StateContracts: **153 passed** after queued-startup repair `0fdc363`, including six original scenario
  groups covering port defaults, saved-true idle, request units/crossproduct,
  mm display and probe mapping, nullable index alignment, selection without
  restart, edits/rearm, pause/cancel, document transitions, missing/invalid
  inputs, stale/malformed provenance, summary usability, mesh cleanup,
  source-mesh preservation, item multiplicity and failed-close retry. The added
  regression holds the worker queued, verifies retained ownership and polling,
  then transitions to running without releasing the job.
- Fresh Coverlet instrumented run after lambda layout correction: **227/227
  executable lines, 23/23 explicit functions and 10/10 lambdas** covered under
  the unchanged function gate. The earlier 207-line report could not attribute
  shared lines to individual lambdas. For that formatting-only change, all 23 syntax fingerprints and 29 linked
  compiled method IL hashes were identical; see [the measured proof](verification-stationary-study-lambda-coverage.json).
  The fresh queued-fix measurement retains 227/227 lines and all 23 functions
  covered; 2756 Python tests and 153 StateContracts pass. The strict headless
  gate and committed matrix pass. These checks do not establish exhaustive
  branches or event ordering. The earlier token/IL comparison does not cover
  the subsequent behavioral queued-state repair.
- Actual .NET 7 Grasshopper project build passes (103 existing platform/nullability
  warnings, zero errors); no assembly was installed or loaded by this lane.
- Whitespace check passes. Backend contract was checked against its actual
  service implementation, including top-level per-record CM and SI frame fields.

G1/G2: pass within these linked-test bounds. G3: no new solver method, physical
qualification or threshold change; units/projections are asserted, experimental
loads remain unqualified. G4 has scoped ten-phase coarse lifecycle and scatter
host passes on installed source `9583f3a`; final explicit-mesh fine pressure and
viewport acceptance remain pending. See the [reconciled host review](review-parametric-wing-example.md).
G6's current CPU/MPS finite matrix and 54-node/32-example archive inventory pass;
2490 unavailable CUDA rows remain blocked, not passed. Fresh CPU smoke passes
5/5 under its pinned policy ([evidence](verification-wing-queued-cpu-smoke.json)).
`dist/Hawa-wing-queued.zip` builds successfully without installation; the running
Rhino assembly predates the queued-state fix, whose fresh installed-host checks
remain pending. G5 final package/release
acceptance remains root-owned. Earlier linked-test IL equality was limited to
the formatting change and is not an installed-binary comparison.
Test doubles never establish live Rhino acceptance.
