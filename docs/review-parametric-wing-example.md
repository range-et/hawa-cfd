# Parametric wing example — geometry and integration review

November 17, 2026. Geometry/example author: Codex `examples_review` agent.
Live geometry/lifecycle operator: Codex root via Rhino MCP. Evidence reconciliation:
Codex `wing_wrapup` agent. Root owns final fine-host, viewport, package and merge
acceptance. The current fine run is pending; no pressure/video pass is claimed.

## Product and measurement boundary

Example 35 uses existing Airfoil nodes and ordinary Grasshopper expressions,
vectors, Move, Loft, Cap Holes Ex, Mesh Brep, Mesh Join, Weld and Mesh Unify Normals.
The capped solid and closed mesh are graph data, not a precomputed replacement.
Quarter-chords align at root chord/4; analytic planform area and MAC remain fixed
across operating angles. No Hawa wing-construction component was introduced.

The reusable CPU-only Stationary Study receives that mesh, an empty-solid
world-axis physical BGK case, SI references, angle/speed lists and explicit Run.
Background classification and sequential independent candidates retain immutable
selected snapshots and whole-body loads. Physical edits invalidate results and
require Run off/on; selection alone does not advance physics. See the
[service contract](stationary-study.md) and [measurement contract](measurement-contract-v1.md).

Selected mesh, field and window means share candidate/generation identities.
Model coordinates convert to metres for submission and back for display. Drag
and lift project whole-body force onto +X and +Z; torque is about the specified
pivot. Surface Field samples pressure at an outward offset, with invalid samples
black. These colours are not local traction or another force integration.
Three stock-GH scatter plots use returned angle/coefficient lists, preserve
cross-product indexing and omit rejected pairs. Plot scaling does not change
reported coefficients.

## Final explicit-mesh geometry preflight

Root's transient owned-document preflight passed three actual loft variants.
`results/parametric-wing-geometry/preflight.json` records solid Breps, closed
meshes and positive volumes with explicit meshing independent of document defaults:
minimum edge 0.01 m, maximum edge 0.03 m, distance 0.0005 m and angle 10 degrees.

| Root / tip | Chords (m) | Span (m) | Vertices / mesh faces | Selected triangles | Volume (m³) |
| --- | --- | --- | --- | --- | --- |
| 2418 / 0018 | 0.3 / 0.2 | 0.6 | 5288 / 5409 | 10572 | 0.005293200448810192 |
| 0012 / 2412 | 0.35 / 0.18 | 0.7 | 6528 / 6854 | 13052 | 0.005063569125053551 |
| 2418 / 0018 | 0.25 / 0.15 | 0.5 | 5281 / 5382 | 10558 | 0.0029302017002051004 |

Selected vertex counts are respectively 5288, 6528 and 5281, below the existing
10000-point Surface Field request cap. This establishes geometry/resource
admission, not successful pressure sampling. Earlier implicit-mesh runs had
different vertex counts and volumes; those are historical and do not describe
the final archive. The solver grid remains 499041 cells at 0.01 m: changing CAD
tessellation does not itself refine the flow grid.

## Verified host lifecycle and graph behavior

The [host machine record](verification-parametric-wing-host.json) records Mac
Rhino 8.37, embedded Python 3.9.10/PyTorch 2.8.0 and CPU. Root ran
`scripts/verify_stationary_study.cs` on an owned archive copy at 0.025 m,
1200 settling steps + 81 samples and unchanged 0.05 tolerance. Both candidates
completed with usable windows. All ten lifecycle phases passed: explicit start,
automatic polling, selection/capture identity, re-selection without advancement,
geometry invalidation, cooperative pause/cancel, saved-Run-true idle reopening
and document disposal/restoration. Original IDs/wires and user documents were
preserved. Public cleanup/refresh counts and a separate registry/thread audit
reported zero jobs, sessions and workers afterward.

That lifecycle run used installed component source `9583f3a`. Subsequent lambda
layout changes preserve all 23 syntax fingerprints and all 29 linked compiled
method IL hashes; see [the exact comparison](verification-stationary-study-lambda-coverage.json).
This preserves the scoped behavioral relevance of the earlier lifecycle run;
it is not a new installed-assembly or final-archive acceptance run.

Live scatter tests reproduced missing-value Expression errors, Cull Pattern's
keep-true behavior and variable-arity arithmetic producing phantom points.
The correction uses Null Item + NOR for a shared keep mask, paired Cull Pattern
nodes and fixed-arity Multiply/Add. Mixed-null, all-pending and valid-pair tests
passed, including actual ConstructPoint counts/coordinates and no points for
pending coefficients. Those stock arithmetic components are internally marked
obsolete in the tested Rhino installation; other-version host compatibility is
not established. Patches preserve original functional IDs and unrelated wires.

The idle preview graph uses NOT Run / Cull Pattern: Run off displays editable
geometry; Run on withholds the unrotated upstream preview. Its archive patch
preserved 143 original IDs and all original wires while adding two objects.
Final viewport acceptance remains pending. Example 35 annotation/connection
checks passed. The current [G6 evidence](verification-wing-gh-compatibility.json)
checks 54 public nodes, 32 definitions and 242 observed unique edges against
current archive hashes; this does not substitute for viewport inspection.

## Remaining acceptance and qualification

The final explicit-mesh fine run (root run identifier `235231`) and its pressure
surface, legend, selected-case view and video remain pending. Earlier progress
paths in the host machine record are historical, not a final-run pass. Root
must record final source/archive/package identities and inspect both canvas and
viewport before closing these UI gates. Package/release acceptance is separate.

The frozen [headless fine-run protocol](wing-fine-report-protocol.md) uses a
different indexed wing geometry; its results do not qualify this CAD loft.
Existing grid/domain sensitivity failures and the missing matched physical
reference remain open in #40. Neither finer sampling nor a solid loft establishes
engineering accuracy. No Windows host or CUDA/MPS simulation pass is claimed;
the stationary-study service rejects accelerator requests.
