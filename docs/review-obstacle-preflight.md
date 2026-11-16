# Obstacle admission (#83)

Date: November 16, 2026. Author: Codex issue83 agent. Self-review: G0–G6.
Additional code review: coordinating Codex root agent (topology/intersection
bounds, cancellation, diagnostics and host preservation). Neither agent's code
review is independent physical validation.

## Scope and contract

User question: refuse invalid obstacle meshes before voxelization, identify the
body and defect, and preserve supported closed multipart/cropped inputs. This is
implementation verification, not a claim of mesh repair, full solid certification
or physical validation. No public node, GUID, port order or archive schema added.

`ObstaclePreflight` reads double-precision vertices, counts exactly coincident
vertices as the same topology vertex without editing the mesh, rejects invalid
indices/nonfinite points/zero-area faces and edges with incidence other than two.
Specific structural findings precede Rhino's generic `IsValid` fallback. A BVH
checks transverse segment/triangle intersections; triangle seam hits are included,
vertex-only contact, coplanarity and near-tangency are outside certification.
The candidate budget is 2,000,000 fully overlapping triangle AABB pairs per mesh;
exhaustion refuses with a simplify/split instruction. Cancellation is checked
through topology capture, tree construction and every traversal stack item.
This is a bounded diagnostic, **not** a proof of no self-intersection. Single
self-intersecting meshes remain unsupported even when the bounded test misses
coplanar or nearly coincident contact. Separate mesh inputs may overlap, touch or
be disjoint; a nested closed shell retains parity-based cavities. The tests use
an explicit inner-cavity sample, not just surface nodes.

GH Geometry, Moving Body and Geometry Check use this shared check in background
workers. Geometry Check reports the same admission result plus explicit limits.
Geometry/Body outputs expose the limits too. Native selection keeps its cheap
valid/closed/type check (with an object ID and specific safe structural errors
for rejected meshes); native preparation performs detailed admission before any
voxelization. Native selected-case budget admission now occurs before preparation,
and the final prepared spec still receives its original downstream check.

Standalone GH Domain has no fluid/collision/capture settings or memory-budget
input: its preflight can check dimensions, finite positive spacing, basis and the
existing two-million-cell limit, but cannot claim the final case/capture estimate.
That remaining #75 scope is explicit. Existing curved-wall and native two-cell
clearance is checked before voxelization. Non-curved GH child cropping and halo
classification remain supported; outside bodies remain ignored. Wind Tunnel
sizing meshes, boundary faces, refinement boxes and Surface Field display meshes
are not obstacle inputs. Legacy Hull remains a geometry recipe/archive reader;
its output is checked when passed to an actual Geometry obstacle input.

Three GH component classes and native preparation were moved to dedicated source
files so the actual adapters could be linked into StateContracts. These are
source moves, not replacement nodes. Previously unmeasured functions are now
exercised, including worker replacement/removal, fault reporting and disposal.
`Task.Run` has no scheduler cancellation token deliberately: captured geometry
must always enter `finally`. Normal input/document removal cancels the worker
and clears its task reference; detached work cannot publish. Removed IsCanceled
UI branches were not reachable through this lifecycle. Contracts cover a worker
OCE as a fault, and normal removal/replacement while kernel work is blocked.

## Sources and decisions

- [RhinoCommon Mesh documentation](https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/T_Rhino_Geometry_Mesh.htm),
  checked November 16: closure alone is insufficient for manifold admission.
- [MeshVertexList.Point3dAt](https://mcneel.github.io/rhinocommon-api-docs/api/RhinoCommon/html/M_Rhino_Geometry_Collections_MeshVertexList_Point3dAt.htm),
  checked November 16: use the double-precision accessor, not a float vertex-index
  conversion that collapses a small body far from the origin.
- Transverse intersection uses normalized segment/triangle barycentrics, the
  scalar-triple-product method described by Möller and Trumbore (1997),
  [author publication list](https://fileadmin.cs.lth.se/cs/Personal/Tomas_Akenine-Moller/publications.html).
  The implementation is original Hawa GPL-3.0-only code; no external code or new
  dependency is incorporated. Relative cutoffs (determinant 1e-12, barycentrics
  1e-10) define diagnostic exclusions, not modified solver tolerances.

## Gates and evidence

| Gate | Decision | Evidence / limits |
| --- | --- | --- |
| G0 | PASS for bounded admission contract | Explicit exclusions and original issue fixtures; source/API review above |
| G1 | PASS for code review | Copies and workers own disposal; caller meshes unchanged; no solver or state schema migration; exact GUID/port contracts tested |
| G2 | PASS for measured headless scope | 3.9: 1821 passes / 87 skips; 3.12: 1811 passes / 97 skips; 120 StateContracts; strict headless 994 covered functions, 308 unmeasured host functions; five seeded faults detected |
| G3 | PASS for unchanged numerical method scope | No solver, viscosity, collision, field or load arithmetic changes; intentionally rejects invalid geometry earlier. Kernel/solid classification acceptance remains G4 |
| G4 | PASS for listed live fixtures; broader acceptance BLOCKED | Combined candidate real-kernel, GH Geometry/Check and native CPU fixtures passed; no full example sweep or live Moving Body/lifecycle audit |
| G5 | BLOCKED for release | Local build passed; coordinating agent installed combined development candidate for acceptance, hashes verified. No release, Windows or CUDA claim |
| G6 | BLOCKED pending final checks | Existing node IDs and ports preserved; final matrix/archive checks and host omissions to be recorded |

## Fixture specification and remaining acceptance

Use an isolated owned Rhino/GH document, one fixture at a time. All fixture shapes
are provided by `ObstacleContracts.Box` and `GeometryAdmissionContracts` for
headless reference. Real Rhino fixtures must be independently constructed and
measured; the doubles script analytic box kernel answers.

- Native: domain [0,8]^3, dx=1, box [3,4]^3. Verify 8 surface-inclusive sites.
- Invalid: remove one face; add a third incident face on an existing edge; add a
  zero-area triangle; combine two offset intersecting closed shells into one
  mesh. Expect named actionable refusal before voxelization.
- Separate valid meshes: overlap, touching and disjoint controls; verify union
  solid count. GH child crop [-0.5,0.5] × [1,2] × [1,2] stays supported with halo.
- Hollow: outer [2,5]^3, inner [3,4]^3, dx=0.5; center (3.5,3.5,3.5) is fluid,
  (2.5,3.5,3.5) is material, inner surface (3,3.5,3.5) remains solid.
- Curved walls retain their clearance guard; invalid domain/clearance/budget
  must refuse before voxel work. Cancel/remove/repeat, then verify owned work is
  gone and source geometry unchanged.
- Run supported examples on the tested combined candidate, preserving user
  documents and example 09. Record actual omissions instead of claiming a sweep.

#83 remains open for the acceptance omissions and pick-time scope below.

## Measured candidate evidence

[Machine-readable evidence](verification-obstacle-preflight.json) identifies the
source and the separately built combined host candidate. Source `31368cb` passed
the Python 3.9.25 suite (1821 passed, 87 skipped), 120 linked StateContracts and
the strict headless gate against base `1b4e6c7`: 994 covered functions, 58
declarations and 308 unmeasured host functions. The committed matrix is refreshed.
The raw Coverlet total includes host/test doubles; the strict gate evaluates the
linked production-source scope. Five deliberate C# faults in topology, degeneracy,
intersection and GH/native admission produced inspected assertion failures at
`34f4c7f`; these files are unchanged at `31368cb`. This is bounded seeded-fault
evidence, not an exhaustive mutation score. Build and Ruff passed.

The earlier interrupted measured run is discarded. A separate aborted #98
mutation study may have probed MPS concurrently with the fresh 3.9 suite; no
failure was observed, but these runs support correctness checks only, not
performance comparisons. Python 3.12.4 subsequently passed 1811 tests with 97 skips. Both isolated
environments use pinned PyTorch 2.8.0. CPU/MPS cases ran where supported; CUDA
was unavailable. No tolerances were relaxed. During the 3.12 suite, the #98 host check may
have briefly initialized an auto-selected device on an idle GH08 first solution
before switching to CPU; no solver steps were reported. Absence of device
overlap is not established, and no timing/performance claim relies on this run.

Through Rhino MCP, the issue83 agent verified the loaded hashes of combined
candidate `6ed1012` before testing. Nine real-kernel fixtures agreed with admission
expectations, including a 2048-face meshed sphere. GH Geometry produced 8 closed
box, 8 overlapping, 12 touching, 16 disjoint and 4 cropped solid sites. Hollow
outer [2,5]^3 / inner [3,4]^3 at dx=.5 produced 342 sites and excluded the cavity
center; direct kernel tests retained inner surface/material membership. Open,
zero-area, nonmanifold and intersecting meshes gave specific obstacle diagnostics.
Geometry Check reported the same results for 13 input meshes without errors.

Native open-mesh pick refused with object ID. Rhino itself refused insertion of
the zero-area and nonmanifold-fin meshes (empty GUID); this is explicitly **not**
a native preflight pass. Closed intersecting shells were selectable, then Run
failed before a solver session existed, at zero steps, with object ID and faces.
Native valid box, hollow and touching cases completed one CPU step with 8, 342
and 12 solids respectively; hollow cavity center remained fluid. These are
admission/scheduling smoke checks, not convergence or physical accuracy results.

The owned GH definition was removed/disposed, owned Rhino objects deleted,
CaseHub case closed, and later read-only checks showed zero undeleted objects,
zero retained cleanup and zero pending polling. Original documents were not
opened, closed or replaced. Full examples, live Moving Body and blocked-worker
cancellation/replacement remain unrun on this combined candidate; headless tests
do cover those lifecycle paths. #83 must not be closed as full pick-time solid
certification or complete release acceptance.

No viewport or canvas screenshots were captured or visually inspected. The live
checks inspected actual volatile outputs/runtime messages and public native
Describe/Spec data. Visual presentation and the complete example gallery remain
explicitly unverified.
