# Example verification and node-combination coverage

The annotated definitions are executable workflow fixtures for humans and agents.
Use [the example catalogue](README.md), [Rhino MCP instructions](../../docs/agents/rhino-mcp.md)
and [review gates](../../docs/quality-gates.md). The table below defines required
checks, not fresh pass results. Historical evidence lives in the 0.4 closeout and
0.5 verification reports. Record each new run against its exact build.

## Baseline workflows

Each row identifies a graph family. Run the saved baseline, then variations on a
copy. Each supported example needs all applicable gates, not only the main gate
shown here. The native example is in the sibling `native-prototype` directory in
the checkout; installed packages place it inside `examples/native-prototype`.

| ID / family | Required observable checks | Focused evidence / test entrypoints |
| --- | --- | --- |
| 01 3D TGV BGK | Installation/backend selection, finite fields, decay and equal-time comparison | `tests/test_engine.py`, `test_lbm.py`, `test_port_features.py`; native baseline harness below |
| 02 2D TGV BGK | Planar field, decay; establish reference settings for 03/04 | Same numerical suite; baseline harness |
| 03 2D TGV TRT | Correct collision selection, matching physical setup to 02 | `test_port_features.py`; reference/backport comparison; baseline harness |
| 04 2D TGV Smagorinsky | Finite fields, declared model/grid sensitivity relative to 02 | `test_port_features.py`; baseline harness |
| 05 3D TGV Smagorinsky | Same checks in 3D; allocation/backend limits | `test_port_features.py`; baseline harness |
| 06 cavity | Correct walls and recirculation; profile/reference criteria for quantitative claims | `test_lbm.py`, upstream suite; baseline harness |
| 07 forced channel | Force convention, settled velocity profile and mass balance | `test_port_features.py`, upstream suite; baseline harness |
| 08 block | Geometry/domain units, valid slice/flow lines, visible domain | `test_plugin_service.py`, `test_outflow.py`; baseline harness |
| 10 asynchronous hull search | Completed candidate IDs, objective ownership, pause/resume/cancel/input-change | `test_optimization.py`, `test_jobs.py`; `verify_async_controls.cs`, `verify_invalid_input_cleanup.cs` |
| 11 3D visualization | One snapshot feeds planes, contours, isosurfaces and flow display; field/legend/units agree | `test_fields.py`; `verify_v04_examples.cs` |
| 12 local airfoil/wing | Offline coordinate/polar import, closed wing, useful malformed-data errors; synthetic-data label | `test_airfoils.py`; `verify_v04_examples.cs` |
| 13 record/playback | New directory, completed manifest, valid final frame and metadata; interruption/missing frame | `test_recording.py`; `verify_recording_examples.cs` |
| 14 curved sphere | Stationary curved-wall capability, surface samples/pressure conventions | `test_walls.py`, `benchmark_curved_walls.py`; `verify_curved_gallery.cs`, `verify_curved_geometry.cs`, `verify_geometry_inputs.cs` |
| 15 fixed refinement | Supported 2:1 BGK patch, interpolation validity, coarse/fine time alignment and conservation | `test_refinement.py`, `benchmark_refinement.py`; `verify_recording_examples.cs` (recording/refinement group) |
| 16 cylinder wake | Small smoke run plus separately specified full-duration recording; final frame and wake observables | `test_recording.py`, `test_fields.py`; `verify_recording_examples.cs` |
| 17 oscillating cylinder | Translation trajectory, domain clearance, same-time body/field/loads | `test_motion.py`, `benchmark_motion.py`; `verify_motion_examples.cs`, `verify_motion_controls.cs` |
| 18 pitching airfoil | Rotation origin/radians, body closure, load signs and motion limits | Same motion tests/harnesses; airfoil tests |
| 19 rotating paddle | RPM conversion, torque/power sign, same-time body/field; single-fluid limits | Motion tests/harnesses; `benchmark_rotating_sphere.py` is a separate reference geometry |
| 20 motion-cycle search | Settling followed by complete measured cycles; candidate ID and objective sign | `test_motion.py`, `test_optimization.py`; `verify_motion_controls.cs` plus explicit Search run |
| 21 native live sync | Panel↔GH ownership, lock/edit/unlock, duplicate/stale writers, undo/reopen/units and cleanup | `tests/dotnet/StateContracts`; `verify_native_prototype.cs`, `verify_state_hardening.cs`, `verify_binding_callbacks.cs` |
| 22 selected native canopy | Closed mesh/Brep selection, editable physical domain, native CPU/MPS, deletion/replacement/units invalidation, palette/slice, persistence and two-input GH sync | `verify_native_geometry.cs`; selected example UI/public API run; state contracts |
| 23 native curved solid | Saved idle curved-wall setup, fractional slice outline, speed/pressure on all axes, unchanged raw samples and session | `verify_native_curved.cs`, `verify_native_slice_display.cs`; three-grid geometry and CPU/MPS parity checks |

Python paths above are under `tests/`; scripts are under `scripts/`. These are
entrypoints, not a claim that one script fully asserts every item in its row.
`verify_curved_gallery.cs` provides the current nonblocking baseline for 01–08,
11, 12 and 14; it does not cover 15. Inspect its actual selection and settings before
running. The old `verify_grasshopper_examples.cs` is historical and blocking: do
not use it. Agent operators use installed public nodes/APIs; developer harnesses
may perform internal inspection and require an isolated session.

**09 is excluded:** preserve the user's legacy Galapagos file unchanged. **22
supported workflows** means 19 GH gallery files, native GH examples 21 and 22,
and native-only example 23, not the
16 upstream Lettuce entrypoints. Neither inventory covers every possible graph.

## Combination strategy

An arbitrary graph product is unbounded. Cover supported edges, meaningful pairs
and high-risk triples, then vary event ordering. Add an example or regression
fixture for every new node family and every integration bug. Never silently
include an unsupported physics combination in the pass denominator.

For each change, enumerate affected node types and input/output contracts. Record
which upstream producers and downstream consumers changed. Select relevant values
from these dimensions, assign combination IDs, and record actual coverage:

| Dimension | Values to consider |
| --- | --- |
| Runtime | CPU / MPS / CUDA when available; explicit device / auto / unavailable-device request; supported dtype |
| Case | 2D / 3D; built-in / geometry-derived; supported collision and boundary choices; coarse / finer grid |
| Geometry and units | Valid closed mesh / open or degenerate mesh; metres / millimetres; transforms; thin or unresolved body |
| Ownership | Direct slider / computed input / panel; one writer / duplicate writer; bound / unbound / replacement case |
| Execution state | Idle / preparing / running / pausing / paused / completed / failed / outdated / closed |
| Views | Speed / pressure / density; supported colour maps; plane / flow / contour / isosurface / body / loads |
| Data source | Live session / shared snapshot / completed recording; missing or corrupt frame |
| Input validity | One value / disconnected / multiple items / NaN / infinity / out-of-range / unavailable file |
| Motion and search | Stationary / prescribed translation / pitch / rotation; completed candidate / pending candidate / cancelled candidate |
| Persistence | Fresh template / saved pair / reopen idle / undo / redo / document close / unit change |

Minimum selection rules:

1. **Changed node:** test every supported producer/consumer contract it touches,
   including empty/error output. Record graph edges by node type and port.
2. **Routine change:** baseline affected examples plus representative valid pairs
   from changed dimensions and their rejection cases. Record omitted pairs and why.
3. **High-risk triples:** ownership × lifecycle × delayed callback; motion × field
   capture × recording/playback; candidate ID × cancellation × objective publication;
   geometry units × discretization × preview. Pairwise tests alone miss these bugs.
4. **Release candidate:** open/inspect all 22 supported workflows, run bounded smoke
   configurations for each, then run full recordings/cycles and numerical studies
   required by the advertised claims. Run applicable hardware configurations or
   mark them unverified. A reduced smoke target does not pass a cycle/full-run gate.
5. **Unsupported combinations:** explicitly test rejection, e.g. moving bodies
   with unsupported curved-wall/refinement modes, or a second case writer. Check
   the declared capability before generating cases; do not assume all matrix
   values compose freely.
6. **Regression history:** repeat bug-triggering event sequences exactly, then
   reverse/interleave relevant events. Fail on stale field attribution, partial
   slider updates, orphan workers or recovery requiring a forced quit.

Track required / exercised / passed / failed / blocked combinations, plus planned
pairs or triples still uncovered. “100%” is meaningful only against a named,
versioned finite inventory; it never means all possible Grasshopper graphs.
G6 now generates a finite solver/boundary/field compatibility matrix and audits all shipped GH graphs. See [the compatibility guide](../../docs/compatibility-matrix.md). Arbitrary graph generation and continuous-input enumeration are outside that finite scope.

## Repeatable human / agent recipe

1. Read the example's guide panels and limits. Open a copy in an isolated document;
   preserve the original IDs/wires/assets and keep Run off until inputs are checked.
2. Record build/environment and exact inputs before execution. Define expected
   observable values/geometry, reference criteria and failure behavior first.
3. Use UI controls or public MCP operations. Return to the event loop after submit;
   observe progress on later turns. Check errors and non-null output geometry.
4. Exercise the named variation and control sequence. Require the matching result
   identity and completion, including physical capture time for shared views.
5. Capture the relevant canvas/viewport and output report. Save useful variations
   as new fixtures; do not overwrite shipped baselines or user files.
6. Stop/dispose owned work. Confirm cleanup. Record failures and missing checks
   using the [review record](../../docs/review-record-template.md).

A new fixture must carry purpose, units, required assets, supported devices/physics,
small smoke settings, separate analysis settings, start/pause/cancel instructions,
expected outputs/rejections and known limits. Put these in its guide panels and
README; link its tests and coverage IDs here. Keep baseline `annotations.json`
entries synchronized and run the annotation connection check after regeneration.
For example 21, preserve its native generator annotations and unbound saved ID.

Native example 23 adds a saved idle curved-solid case; `verify_native_curved.cs` checks the shared native path. See `docs/verification-boundaries-v0.5.json` for scope and results.

## Boundary annotation previews (#38)

Hawa Case and Hawa Boundary Set draw their accepted output case only while
selected. Native example 22 draws the same annotations while Domain wireframe is
on. Covered headlessly by `tests/dotnet/StateContracts/PreviewContracts.cs`
(positions, labels, periodic pairs, selection gating, hiding while a result is
outdated).

One live run on macOS (branch a5bdef2) passed:

- 22: labels, the Y± → wall edit and the toggle.
- 25: Boundary Set, selected versus unselected, with a real canvas click.
- 08: Case, the legacy periodic pair.

Open limits:

- Opaque field meshes depth-occlude GH labels.
- The native inlet arrow and outlet tick were not visible at 22's framing.
- Windows has not been checked.

The two display gaps are tracked in #108.

## Boundary-transfer development coverage

Example 24: coarse parent Record → Boundary Capture → Boundary Data → child Solve,
with Result Quality and fixed-range field views. See [the gate record](../../docs/boundary-transfer-review.md).
Required combinations: CPU/MPS imported vector field, uniform regression, temporal
profile, rotated coordinates, model-unit conversion, missing/solid coverage,
stale file hash, source quality rejection, time exhaustion and checkpoint history.
Live MPS checks cover completed parent/child at matching physical time, valid
meshes, target rejection/recovery, annotation wire preservation and idle reopen.
CUDA/Windows remain unverified; atmospheric and wall-contact combinations are
unsupported. No engineering validation is claimed.

## Boundary foundation development examples (November 9, 2026)

| Example | Live MCP coverage | Numerical claim |
| --- | --- | --- |
| 25 | MPS 400 steps; profile/wall/open assembly; valid plane; pause; incompatible-profile rejection; repair | Workflow; separate analytic channel benchmarks in boundary report |
| 26 | MPS 400 steps; Y-oriented open pair; valid plane | Uniform directional workflow; no nonreflection claim |
| 27 | MPS 400 steps; full closed mesh crossing X-; valid plane with solid mask | Cropped occupancy workflow, not general cut-face accuracy |

Definitions are annotated and saved idle. `scripts/verify_general_boundary_examples.cs`
uses one action per MCP call and preserves source files. Evidence and remaining
G3/G5 limits: [boundary gate record](../../docs/general-boundaries-review.md).

## Neutral precursor development checks (November 9, 2026)

Examples 28 and 29: macOS Rhino 8.36 / embedded MPS, 400 steps each, 2.309401 seconds, no component errors, valid 841-face slice. Example 28 also exercised pause, invalid roughness, output withholding, recovery and close during run; cleanup count zero. Definitions are idle and annotated. Atmospheric qualification is **FAIL**, CUDA/Windows are unverified. See [gate record](../../docs/neutral-precursor-review.md).

## Neutral coupling follow-up

Example 30: embedded MPS 1000 steps at 5.773503 s; max Mach 0.074773; valid
743-face slice and matching snapshot time. Pause, invalid z0/output withholding,
repair/CPU400, close during run and zero pending cleanup verified. 28–29 each
repeat MPS400 and 841-face slices. Archive migration tests preserve old GUIDs and
wires with zero missing-chunk warnings. [Review](../../docs/neutral-coupling-review.md).
The old startup-profile failure remains historical; the 200k-step stationary
verification passes. Full atmospheric validation remains open.

## G6 coverage-library additions

Examples 31 and 32 cover the remaining reusable public operations: Wind Tunnel,
Runtime, Sample, Vectors, Checkpoint and Translation (Particles was later removed by owner decision; see features history, November 12, 2026). Native examples
21–22 cover Linked Case. The archive inventory now covers all 52 public nodes
across 30 GH definitions, excluding preserved legacy 09. All are annotated, idle
and read without missing/corrupt archive messages. This is archive coverage;
it does not assert a fresh numerical run of every older example.

Live checks: 31 completes CPU60 with three valid probes/vectors and save/load/export;
32 completed CPU40 with five recorded frames, three particle paths and a matching
body pose (historical: the Particles node is removed in the next re-save). Source files remain idle. See [G6 evidence](../../docs/compatibility-matrix.md).


## Neutral transfer and shared-view development checks

Example 33 now runs the full CPU and MPS chain in embedded Rhino: city512,
neighbourhood1024, pond1792, final absolute time 2.9560333782508845 s. All three
recordings complete with valid plane meshes and quality/statistics outputs.
Statistics correctly report insufficient evidence for this short demonstration.
MPS pause holds the pond at 0/1792, survives a display edit, then resumes.
A saved enabled copy reopens with all five controls requiring re-enabling.

A shared slice at z=9 m spans the parent above both children; z=1.5 intersects
all three. Additional owned test consumers produce seven 3D streamlines and a
valid pressure isosurface. Final scope, hashes, lifecycle checks and remaining
numerical failures are in [the transfer review](../../docs/neutral-transfer-review.md).
31 supported archives round-trip with original IDs/wires and migrated frame-list
inputs. Example 09 remains excluded. This is not a rerun of every old simulation.
