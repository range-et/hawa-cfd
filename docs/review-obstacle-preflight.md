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
| G2 | PENDING final measured run | Focused C# contracts and development build pass; final source-bound full gate and seeded-fault results to be recorded |
| G3 | PASS for unchanged numerical method scope | No solver, viscosity, collision, field or load arithmetic changes; intentionally rejects invalid geometry earlier. Kernel/solid classification acceptance remains G4 |
| G4 | BLOCKED pending serial host acceptance | Headless doubles do not establish Rhino kernel geometry or GH scheduling; native/GH fixtures and supported examples still required |
| G5 | BLOCKED for release | Local development build only; no install/release, Windows or CUDA claim |
| G6 | PENDING | Existing node IDs and ports preserved; final matrix/archive checks and host omissions to be recorded |

## Live acceptance queue

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

#83 remains open until live scope is verified or explicitly re-scoped.
