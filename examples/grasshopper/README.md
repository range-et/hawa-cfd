# Editable Grasshopper examples

Open these definitions in Rhino 8 with the complete Hawa plugin installed. Each supported definition has three guide panels and numbered workflow groups. Read left to right. Inputs sit near their consumers; output panels are on the right. Save a copy before changing a shipped example.

For agent operation through Rhino MCP alone, read [the MCP guide](../../docs/agents/rhino-mcp.md). The plugin bundle carries the same guide in `docs/agents/rhino-mcp.md`.

## Choose an example

| Definition | Explore | Units / main limit |
| --- | --- | --- |
| [01-tgv3d-bgk.gh](01-tgv3d-bgk.gh) | Change grid size, backend and target iterations. Inspect velocity decay. | Reference units. Use this small case to check installation and backend selection. |
| [02-tgv2d-bgk.gh](02-tgv2d-bgk.gh) | Change grid size and target iterations. Compare the same physical time. | Reference units. This is a planar numerical benchmark. |
| [03-tgv2d-trt.gh](03-tgv2d-trt.gh) | Compare the TRT collision model with example 02 at matching settings. | Reference units. Collision models can have different stability limits. |
| [04-tgv2d-smagorinsky.gh](04-tgv2d-smagorinsky.gh) | Change grid resolution and compare decay with example 02. | Reference units. Subgrid modelling does not replace a grid study. |
| [05-tgv3d-smagorinsky.gh](05-tgv3d-smagorinsky.gh) | Compare this 3D case with example 01 at matching settings. | Reference units. Begin with a small grid and increase it gradually. |
| [06-cavity2d-bgk.gh](06-cavity2d-bgk.gh) | Run the cavity and inspect the recirculation pattern. | Reference units. Wall-adjacent fields require grid refinement. |
| [07-poiseuille2d-guo.gh](07-poiseuille2d-guo.gh) | Inspect the velocity profile across the channel. | Reference units. Compare profiles after the flow has settled. |
| [08-wind-around-block.gh](08-wind-around-block.gh) | Edit domain, closed mesh, grid spacing and physics. Inspect slice and flow lines. | Geometry uses metres. Demonstration viscosity is not atmospheric air. |
| [10-responsive-hull-search.gh](10-responsive-hull-search.gh) | Enable evaluation and Run search. Pause holds the current candidate; disabling cancels. | Single fluid, submerged hull. No waves or buoyancy. Short scores demonstrate search; they do not establish an optimum. |
| [11-block-3d-visualization.gh](11-block-3d-visualization.gh) | Use the shared snapshot to compare planes, tubes, contours and isosurfaces. Change field and colour map. | Use one snapshot for comparisons. Keep colour ranges fixed when comparing cases. |
| [12-local-airfoil-rc-wing.gh](12-local-airfoil-rc-wing.gh) | Choose an offline NACA code or local coordinate file. Edit wing span/chord. Load your own local polar. | The bundled polar is synthetic format data. Lifting-line results assume attached flow; stall is not predicted. |
| [13-record-and-playback.gh](13-record-and-playback.gh) | Choose a new absolute output directory. Start Record, wait for completion, then change Frame. | Recording creates files. Use a new directory for each run. Playback must use the returned manifest. |
| [14-curved-sphere-pressure.gh](14-curved-sphere-pressure.gh) | Use the closed Brep on Geometry S; cell size controls tessellation. Inspect pressure and compare spacings. | Experimental stationary curved links. Do not combine with refinement or moving bodies. |
| [15-fixed-refinement.gh](15-fixed-refinement.gh) | Edit the domain and interior patch; run both grids and compare their field planes. | One fixed 2:1 BGK patch. Keep interpolation stencils in fluid. No automatic adaptive mesh. |
| [16-cylinder-wake-recording.gh](16-cylinder-wake-recording.gh) | Set a new absolute directory, then record the wake. Pause/resume or cancel. Replay saved frames. | The full recording runs 8000 steps. Use a smaller trial first. Outlet and domain size affect the wake. |
| [17-oscillating-cylinder.gh](17-oscillating-cylinder.gh) | Set travel amplitude in metres. Run the case; inspect the shared field snapshot and moved body. | Prescribed motion, uniform BGK. Keep the full trajectory two cells from domain faces. Check grids and cycle averages. |
| [18-pitching-airfoil.gh](18-pitching-airfoil.gh) | Edit the offline NACA section and wing. Set pitch amplitude in radians; run and inspect loads. | Coarse thick-foil demonstration. RC boundary layers are not resolved. Motion does not respond to fluid forces. |
| [19-rotating-paddle.gh](19-rotating-paddle.gh) | Set RPM and run. Inspect body pose, torque and signed fluid power. | Single fluid. No water surface, cavitation or free-body response. This is not a validated propeller model. |
| [20-motion-cycle-search.gh](20-motion-cycle-search.gh) | Run search. Each amplitude is evaluated only after settling and complete measured cycles. Pause or cancel as needed. | Default objective is input power. Compare longer settling, more cycles and finer grids before ranking designs. |
| [24-boundary-flow-transfer.gh](24-boundary-flow-transfer.gh) | Record a parent wake, map a time-varying vector inlet, then run a finer child. | Development feature; periodic transverse faces and stationary uniform child. Read [transfer instructions](../../docs/boundary-transfer.md). |
| [25-channel-boundaries.gh](25-channel-boundaries.gh) | Six physical patches: profile inflow, walls and open outlet. | Stationary uniform NEE; wait for ready, then Run. |
| [26-bidirectional-open-faces.gh](26-bidirectional-open-faces.gh) | Y-oriented open pair; edit initial velocity sign. | Approximate open condition; no nonreflection claim. |
| [27-cropped-solid-boundary.gh](27-cropped-solid-boundary.gh) | Closed box crosses X-, leaving mixed fluid/solid sites. | Unsupported solid donors and curved cuts reject. |

Example **09** is a historical Galapagos definition with user edits. It is preserved in this checkout and excluded from the supported package. Use **10** for asynchronous hull search. It is not part of the layout cleanup.

## Run and inspect

1. Start with example 01 and a small grid. Rhino installs pinned dependencies on first use. This needs internet access and can take time.
2. Select `cpu`, `mps`, `cuda:0` or `auto`. `auto` chooses an available accelerator; small moving cases can be faster on CPU.
3. Wait for geometry/case preparation, then enable the run control. Target iterations is an absolute total.
4. Solve uses Run false to pause and Run true to resume. Reset true then false clears state. Evaluate and Record use Enable/Run false to cancel. Search uses completed candidate IDs; do not feed it partial fitness.
5. Read errors and reports. Require valid output geometry and a completed result before describing a run as successful.
6. Compare the same physical time and fixed colour limits. Check grid, domain-size and settling sensitivity before using loads.

## Recording and moving bodies

Examples 13, 16 and 17–19 include recording controls. Set a **new absolute directory** before starting Record. Use its completed manifest for Playback, then move the Frame slider. Do not point separate runs at the same directory.

Moving bodies use uniform BGK and prescribed rigid motion. Body Preview and the field views should use the same snapshot. Force is fluid force on the body; power is signed fluid work. Motion Evaluate defaults to input power, the negative of fluid power. No waves, buoyancy, free-body response, contact or thermal transport are modelled. Read [the moving-surface guide](../../docs/moving-surfaces-v0.4.md).

## Local airfoil data

Example 12 uses `data/naca0012.dat` and `data/polar-format.csv`. Relative paths resolve from the definition folder; keep the `data` folder beside the definitions. The polar is synthetic format data, not measured aerodynamic evidence. Users supply their own coordinate and polar files. No database or website is queried.

## Maintainer checks

Use [the verification matrix](VERIFICATION.md) for required checks and supported
node-combination variations. Each example is a reusable workflow fixture for
humans and agents. Follow [the review gates](../../docs/quality-gates.md) and record
the exact configuration and results with [the review template](../../docs/review-record-template.md).
The matrix defines coverage obligations; it does not claim that every combination
has already been tested.

`annotations.json` contains the example-specific descriptions. Run `scripts/annotate_grasshopper_examples.cs` through Rhino MCP after regenerating definitions. It checks that connections are unchanged and saves local backups. `scripts/capture_example_layouts.cs` renders each supported canvas without running its solver. Adjust the checkout path in either script before use on another machine.

The gallery covers selected workflows. It is separate from the sixteen upstream Lettuce entrypoints and does not claim to wrap every upstream example. CPU/MPS PorousMedium parity remains a documented open issue.

Native Rhino examples 21 and 22 are in [the native example folder](../native-prototype/README.md). Example 22 combines selected Rhino geometry, editable domains and two-way GH controls.

Example 10 builds its hull with ordinary Grasshopper expressions, Construct Mesh,
Mesh Volume, Scale NU and Move. The construction is editable example content; it
adds no Hawa hull node. The hidden legacy archive reader is retained only so old
user definitions can still open.

Examples 25–27 use `hawa-nee-v1` and `smagorinsky-v1`. Read
[the boundary guide](../../docs/general-boundaries.md) before editing their patches.
All start idle; unsupported corners fail preflight. These are short workflow
examples, not atmospheric validation.

## Experimental neutral precursors

- `28-neutral-rough-floor.gh`: shifted-population air solver and planar rough-floor stress.
- `29-neutral-roughness-sensitivity.gh`: change the z0 slider and compare wall traction at equal physical time.

Both open idle and carry explicit research warnings. Transfer is disabled: the finest-grid profile-preservation gate failed. These are not validated city-to-pond simulations. See [the review](../../docs/neutral-precursor-review.md) and [MCP instructions](../../docs/agents/rhino-mcp.md).

## 30 — Neutral flow with cropped buildings

Open [30-neutral-cropped-buildings.gh](30-neutral-cropped-buildings.gh). Closed box
bodies feed Geometry; one extends through the inlet. Six Boundary Patch objects
feed Neutral Flow. Ground is rough, X+ and Z+ are open, and Y is periodic. The
32×18×16 grid uses dx=1 m, air viscosity 1.5e-5 m²/s and Uref=5 m/s at 6 m.
The wall sample is 1.5 m above ground with a 3 s reference-velocity filter.

Wait for preparation, then enable Run for 1000 MPS steps. Run false pauses. Reset
clears the solution. Save a copy before editing boxes, z0 or patch values. The
blue-green XY slice at z=2.5 m, domain frame and Quality report share the case.
This is a short workflow example; atmospheric engineering accuracy and boundary
transfer remain unqualified. See [the current review](../../docs/neutral-coupling-review.md).

## Coverage-library workflows

- **31 — Tunnel, probes and checkpoint:** closed mesh → Wind Tunnel → Geometry/Case
  → Solve → Sample/Vectors. Runtime reports the embedded environment. Checkpoint
  demonstrates save, load and export; set an absolute `.npz` path and toggle
  Execute off/on. Use metres in Rhino. Default CPU60 is a smoke demonstration.
- **32 — Translation and recorded particles:** closed mesh → Translation/Moving
  Body/Motion Case → Record → Playback/Particles and Body Preview. Choose a new
  absolute directory, then Record. Default CPU40 saves frames 0–4. Inspect three
  particle paths and the final body pose. Motion is prescribed; no free-body dynamics.

The [G6 compatibility gate](../../docs/compatibility-matrix.md) connects these
annotated workflows to the finite machine-generated contract matrix. Every public
node has an example; this does not mean every possible GH assembly is enumerated.


## 33 — Three-stage neutral boundary transfer (development)

This is an **outer parent → local child → finer child** chain of separate cases.
The existing canvas calls them city, neighbourhood and pond. Those are application
labels, not required domain types. Read the [parent/child guide](../../docs/parent-child-domains.md)
for the label/resolution map and the distinction between offline transfer,
coupled refinement and combined views. The finest region simulates air, not water.

Open [33-neutral-city-to-pond.gh](33-neutral-city-to-pond.gh). It is an annotated
Grasshopper assembly of reusable tools. Save a copy and replace the three recording
directories and two boundary-file paths with new absolute paths. The source opens
idle. Enable the five Record/Capture controls; each waits for its upstream result.
Pause controls act on their own recordings. Disable Record to cancel.

The city grid is 32×24×16 at 1 m; neighbourhood is 24×24×16 at 0.5 m; pond is
24×24×16 at 0.25 m. They share full closed building geometry. The atmosphere is
neutral air at molecular viscosity, with a stationary rough ground. The pond is
a low-roughness region on that air boundary. It does not model water circulation.

The supplied CPU demonstration uses 512/1024/1792 steps. Pond capture starts at
neighbourhood time 0.3695041722813605 s to exclude its startup pressure transient.
Playback frames 64/64/56 end at the same absolute time, 2.9560333782508845 s.
Changes to speed, Mach, cell width or capture window require matching child duration
and playback time. An import can reject startup pressure even when general health
reports finite fields. Keep that guard and select a physically appropriate window.

All three Playback outputs feed Shared slice. Move **Shared slice height / m**
to cut through the nested domains. A child supplies data where it contains the
sample; the parent supplies the rest. Plane Field, Flow Display, Isosurface and
Surface Field also accept multiple same-time frames. They reject mismatched times
and preserve the finer solid mask. Halfway-wall slices retain fluid portions of
partially intersected triangles. Boundary colours are reconstructed display values;
the Values output remains raw samples with conservative validity in the engine.

Hide an unrelated native case with its Domain, Body and Field checkboxes before
comparing previews. The domain labels identify the three sample extents. The
stationary ground is half a cell below the first centre; displaying sample extents
does not add or remove simulated cells.

**Qualification remains open.** This short run tests the complete data path and
views. Longer nested mean/RMS and experimental atmospheric checks still fail.
Read [the acceptance contract](../../docs/atmospheric-nesting-implementation.md)
and the quality/statistics reports before using results for design decisions.
