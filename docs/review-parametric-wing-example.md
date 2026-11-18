# Parametric wing example — geometry and integration review

November 17, 2026. Geometry/example author: Codex `examples_review` agent.
Live geometry/lifecycle operator: Codex root via Rhino MCP. Evidence reconciliation:
Codex `wing_wrapup` agent. Root owns final fine-host, viewport, package and merge
acceptance. The fine run, pressure sampling, video and scoped new-assembly host checks
completed. Final package and exact-head merge approval remain separate.

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

## Completed fine run and pressure samples

The owned `235231` run completed both cases on CPU at 499041 cells (0.01 m),
3000 settling steps + 201 samples, unchanged 0.05 stationarity tolerance.
At -3/+3 degrees, CL was 0.002896908470910844 / 0.291155128765001 and CD was
1.3452878861284967 / 1.3570599610499743. Both retained fields are source step
3200 at 0.5542562584220407 s. Candidate, summary and field identities agree.
Each selected rotated mesh has 5288 vertices and 10572 triangles; all 5288
surface-pressure samples are valid for each case. Ranges are respectively
2.7189455216754883–3.869348076404643 Pa and
2.6610638027578046–3.844629386682881 Pa.

The prior display range -2…2 Pa clipped every valid sample. A view-only change
to the shared 0…4 Pa range preserves gauge zero and covers both actual ranges;
identity, solver Run state and original archive remained unchanged. The source archive now carries these view defaults: its patch preserves 138
objects and 144 wires, changes only the two pressure sliders and passes staged
reopening. A fresh archive graph audit passes.
Both corrected-range probes retain 5288 valid samples with zero saturation.
Selection 0→1→0 preserves the exact original field/identity and coefficient
arrays. Two 72-frame orbit sequences and three native scatter plots appear in
the [28-second 1080p video](../examples/grasshopper/videos/35-wing-pressure-study.mp4).
The agent and root each inspected 20 encoded frames/contact-sheet views; root
also inspected an actual middle pressure frame. The initial legend-clipped
orbit is excluded. The video retains its original installed-source provenance.

Wall time was 5050.168001 seconds, including 1678 seconds of low-power sleep
recorded by macOS. Concurrent work and an inconclusive UI-poll experiment prevent
an isolated performance claim. No source performance defect is established.

The installed Grasshopper binary was `1df564e82a9aaeacaadd88b018d2e938d226fcd6aa763d9fd90be9d5db3d78f1`
from source `300dd62`. It predates queued-startup and mesh-precision repairs.
A read-only audit compared float enumeration and Point3dAt for all 5288 original
and normalized vertices: maximum difference zero, no differing vertices and
unchanged source CRC. This supports carrying these specific completed fine
results forward; it does not claim a new-binary run or general precision safety.
The machine record retains full assembly hashes, identities and raw-file hashes.

## Final installed-host acceptance

Root normally restarted Rhino and installed source `717e997`; the loaded
Grasshopper assembly SHA256 is
`eba06c834781dabb96ff12b494ba14f38bd47119af10bfb037a673652e7b2469`.
An actual production SerializeMesh call through developer-only reflection on a
native far-origin seam mesh returned four distinct vertices; the known native
CombineIdentical control still collapsed to one. This validates the repaired
serializer on that fixture, not full far-origin Submission or CFD accuracy.

On the default metre-scaled wing, new production geometry JSON equals legacy
output exactly for all 5288 vertices; source CRC3226656946 is unchanged. This
supports reuse of the earlier fine result for this mesh without relabelling it
as a new-binary solve. Idle opening shows one valid geometry preview and zero
points in each of three plots, with no errors.

The newly installed assembly passed all ten coarse lifecycle phases with two
accepted candidates at 0.025 m, 1200+81 steps and unchanged 0.05 tolerance. Its
embedded Python 3.9.10/PyTorch 2.8 environment had 12 foreground/background threads
and no OMP/MKL overrides; it is separate from the single-threaded fine run.
Final jobs, sessions, frames and workers are all zero. Both original empty
Rhino models and both original empty GH documents were restored with recorded
units/IDs and source hashes preserved. One empty MCP verification document was
explicitly retained; no user geometry was replaced.

## Remaining package and scientific scope

The final package-only artifact refresh and exact-head CI/Greptile approval
remain integration steps. Host and video checks above are complete within their
stated scopes; previous failed presentation/native-welding attempts remain
historical evidence.

The frozen [headless fine-run protocol](wing-fine-report-protocol.md) uses a
different indexed wing geometry; its results do not qualify this CAD loft.
Existing grid/domain sensitivity failures and the missing matched physical
reference remain open in #40. Neither finer sampling nor a solid loft establishes
engineering accuracy. No Windows host or CUDA/MPS simulation pass is claimed;
the stationary-study service rejects accelerator requests.
