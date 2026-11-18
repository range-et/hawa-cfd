# Grasshopper stationary-study adapter review

November 17, 2026. Author/test operator: Codex `wing_wrapup` agent. Independent
wire/unit/lifecycle review: Codex `gh_study_backend` agent. Root owns combined
Python/G6/host/package acceptance and final merge gates.

The new Stationary Study component submits the CPU-only study service; no
voxelization, solve, UI-thread wait or unfinished Task.Result occurs in the
adapter. It builds a bounded angle-outer/speed-inner crossproduct (maximum 64),
normalizes physical coordinates using Case dx/spacing, and indexes exact
Point3dAt coordinate triples to remap duplicate seam vertices and faces. Native
CombineIdentical is not used. The caller's mesh is unchanged. Backend
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

- Linked .NET 10 StateContracts: **155 passed** after exact-double seam repair
  `717e997`. Existing scenarios cover ports, explicit start, SI/model-unit
  mapping, aligned nulls, selection without restart, invalidation/rearm,
  pause/cancel, document transitions, malformed provenance, ownership and
  cleanup retry. The queued-start regression retains ownership while queued
  and then transitions to running. The far-origin precision regressions check
  actual submitted coordinates and source preservation.
- Native Rhino testing of the preceding `efa79a...` assembly found that
  `DuplicateMesh().Vertices.CombineIdentical(true,true)` collapses a valid
  five-vertex double-precision tetrahedron at coordinates 1e9, with 0.25 offsets,
  to one invalid vertex. The original mesh remains unchanged. This reproduced
  defect is retained in `results/precision-audit/native-combine-identical-repro.json`.
  Point3dAt reading alone did not fix native welding. `717e997` instead maps
  exact source coordinate triples and remaps triangle indices without native
  welding. Its modeled regression fails before and passes after the repair;
  actual repaired-helper native acceptance subsequently passed on the installed
  `717e997` assembly; see the final host evidence below.
- Fresh whole-suite coverage: **244/244 component lines and 24 explicit
  functions** covered; the new serializer helper measures **26/26 lines**.
  The Python suite passes 2757 tests with 176 skips. Strict headless and
  committed-matrix checks against origin/main pass: **1201 covered functions,
  299 historical host-only gaps and 72 declarations**, zero failures.
- The earlier lambda-formatting correction separately covered all ten lambdas;
  its 23 syntax fingerprints and 29 linked method IL hashes were unchanged
  ([historical proof](verification-stationary-study-lambda-coverage.json)). That
  comparison does not cover subsequent queued-state or precision repairs.
  Execution coverage is not exhaustive branch/event-order or physical evidence.
- Actual .NET 7 Grasshopper project build passes (103 existing platform/nullability
  warnings, zero errors); no assembly was installed or loaded by this lane.
- Whitespace check passes. Backend contract was checked against its actual
  service implementation, including top-level per-record CM and SI frame fields.

G1/G2 pass within these measured bounds. G3 adds no solver-method or threshold
change; experimental loads remain unqualified. The completed fine run on source
`300dd62`, pressure sampling and selection roundtrip retain that provenance;
they are not a fine solve on `717e997`.

Root installed `717e997` through normal Rhino restart and verified the actual
production serializer on a native far-origin mesh: four distinct vertices,
while the native CombineIdentical control still collapses to one. The complete
default-wing geometry JSON equals legacy output exactly; original CRC is
unchanged. The new assembly also passed all ten coarse lifecycle phases with
two accepted candidates, idle preview/empty plots, and final zero jobs, sessions,
frames and workers. Original empty documents were restored. This is bounded
native helper and lifecycle acceptance, not general far-origin CFD qualification.
See the [host review](review-parametric-wing-example.md) and
[machine evidence](verification-parametric-wing-host.json).

G6, CPU smoke and package records retain their exact source scopes. The final
package-only refresh and exact-head CI/Greptile approval remain root-owned;
video and the scoped installed-host checks are complete. Earlier test doubles
or linked-test IL equality are not substituted for these native observations.
