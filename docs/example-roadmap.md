# Hawa example catalogue and future examples

> Direction and reference material; actionable feature, build and example work is
> tracked in [GitHub Issues](https://github.com/range-et/hawa-cfd/issues).
> Create or update a linked issue for new work instead of adding a parallel task list.


This catalogue separates existing editable definitions from proposed examples.
It supports the [project roadmap](roadmap.md). Future entries are candidates,
not implemented capabilities or a release commitment. New examples are outside
the fixed 0.5 native prototype unless they are already part of its baseline.

The primary application audience is RC drones, small boats and related small
vehicles and parts. Lead the user gallery with those examples. Architectural
cases are a secondary backlog; numerical benchmarks remain essential regardless
of the application used to introduce the product.

## Existing definitions

The supported inventory is 19 GH definitions plus one native/GH shared-case
example. Existing means the file and workflow are present; the evidence column
does not assert engineering validation. See the
[GH instructions](../examples/grasshopper/README.md),
[native example](../examples/native-prototype/README.md) and linked release
reports for the run conditions and verification history.

| ID | Existing example | Purpose and evidence boundary |
| --- | --- | --- |
| 01 | [3D Taylor–Green BGK](../examples/grasshopper/01-tgv3d-bgk.gh) | Backend/setup and decay workflow; gallery execution alone does not establish a convergence study. |
| 02 | [2D Taylor–Green BGK](../examples/grasshopper/02-tgv2d-bgk.gh) | Analytic benchmark workflow; compare equal physical times. |
| 03 | [2D Taylor–Green TRT](../examples/grasshopper/03-tgv2d-trt.gh) | Collision-model comparison; match physical settings. |
| 04 | [2D Taylor–Green Smagorinsky](../examples/grasshopper/04-tgv2d-smagorinsky.gh) | Subgrid-model exploration; model selection is not a grid study. |
| 05 | [3D Taylor–Green Smagorinsky](../examples/grasshopper/05-tgv3d-smagorinsky.gh) | 3D model comparison and resource scaling. |
| 06 | [Lid-driven cavity](../examples/grasshopper/06-cavity2d-bgk.gh) | Recirculation workflow; add quantitative profiles for benchmark qualification. |
| 07 | [Poiseuille flow](../examples/grasshopper/07-poiseuille2d-guo.gh) | Channel profile and body forcing; compare after settling. |
| 08 | [Wind around a block](../examples/grasshopper/08-wind-around-block.gh) | Geometry/domain/field setup; demonstration viscosity is not atmospheric air. |
| 10 | [Responsive hull search](../examples/grasshopper/10-responsive-hull-search.gh) | Completed-candidate search and pause/cancel; submerged single fluid, no wave resistance or buoyancy. |
| 11 | [3D visualization](../examples/grasshopper/11-block-3d-visualization.gh) | Planes, tubes, contours and isosurfaces of a shared snapshot. |
| 12 | [Local airfoil and wing](../examples/grasshopper/12-local-airfoil-rc-wing.gh) | Geometry, local polars and attached-flow lifting line; bundled polar is synthetic format data. |
| 13 | [Record and playback](../examples/grasshopper/13-record-and-playback.gh) | Saved fields and playback; use a new recording directory. |
| 14 | [Sphere pressure](../examples/grasshopper/14-curved-sphere-pressure.gh) | Experimental stationary curved walls and surface sampling; full force convergence remains open. |
| 15 | [Fixed refinement](../examples/grasshopper/15-fixed-refinement.gh) | One fixed 2:1 BGK patch; not automatic adaptive refinement. |
| 16 | [Cylinder wake recording](../examples/grasshopper/16-cylinder-wake-recording.gh) | Transient recording and wake views; sensitivity and quantitative validation are additional work. |
| 17 | [Oscillating cylinder](../examples/grasshopper/17-oscillating-cylinder.gh) | Prescribed translation and loads; no force-driven body motion. |
| 18 | [Pitching airfoil](../examples/grasshopper/18-pitching-airfoil.gh) | Prescribed pitch and loads; coarse demonstration, unresolved RC boundary layers. |
| 19 | [Rotating paddle](../examples/grasshopper/19-rotating-paddle.gh) | Prescribed rotation, torque and signed power; no free surface, cavitation or validated propeller model. |
| 20 | [Motion cycle search](../examples/grasshopper/20-motion-cycle-search.gh) | Complete-cycle objectives after settling; longer runs and finer grids required before design ranking. |
| 21 | [Native live sync](../examples/native-prototype/21-native-live-sync.gh) | Shared case through panel and GH; settings example in `native-block.3dm`; interaction evidence. |

Historical **09** is a modified legacy Galapagos definition. Preserve its geometry,
object IDs, wires and edits. Do not regenerate it or add it to releases; use 10
for supported asynchronous search. Proposed entries below have catalogue keys,
not allocated GH filenames or component IDs.

## Proposed workflow examples

Priority P1 means the first backlog after the bounded 0.5 work; P2 follows the
shared setup and evidence foundation; Research requires a separate feasibility
decision. A proposed example may need new functionality even when it uses LBM.

| Key | Proposed example | Dependency | Required outcome |
| --- | --- | --- | --- |
| W01 | Select a Rhino solid and create an air domain | P1 native geometry | Clear units, body selection and visible domain; public operations reproduce the setup. |
| W02 | Import a mesh with holes, thin faces and reversed normals | P1 geometry checks | Locate defects and explain rejection or repair; never silently substitute geometry. |
| W03 | Metres, millimetres and document transforms | P1 units | Equivalent physical cases produce equivalent settings and measurements. |
| W04 | Name inlet, outlet, ground and body walls | P1 boundary editor | Show assignments in the viewport and detect gaps/conflicts. |
| W05 | Panel, direct GH sliders and computed inputs | P1 shared ownership | Demonstrate each input owner and explain read-only driven values. |
| W06 | Agent creates, inspects, edits and runs a case | P1 public API | Use supported operations and polling; report revisions, completion and failures. |
| W07 | Save, reopen and undo a case edit | P1 persistence | Preserve settings and geometry references; reopen idle; invalidate obsolete results. |
| W08 | Multiple independent cases in one document | P2 case management | Isolate settings/jobs/results and compare selected variants. |
| W09 | Geometry edited or deleted during a run | P1 lifecycle | Detect changed inputs, preserve user edits and prevent stale-result attribution. |
| W10 | Budgeted run and out-of-memory recovery | P1 resource reporting | Estimate cost, report failure and leave Rhino responsive. |
| W11 | Repeatable batch of design variants | P2 batch management | Track immutable candidate/run IDs and completed-result objectives. |
| W12 | Compare fields and export a reproducible report | P2 result schema | Same units, colour range, physical sampling, reference quantities and provenance. |
| W13 | Inspect flow with movable vector slices | P1 visualization; GH_Wind design reference | Velocity arrows over optional scalar colour; adjustable density/scale, fixed comparison legends, explicit in-plane versus full-vector mode, invalid-sample masking and shared snapshots; moving the slice does not restart the solver. |

## Proposed numerical benchmark examples

These turn numerical questions into measurable acceptance gates. References,
regimes and tolerances must be selected before promoting each candidate into a
verification or validation example. Analytical/manufactured comparisons verify
implementation; experimental comparisons validate a stated physical prediction.

| Key | Proposed example | Method or prerequisite | Measurements |
| --- | --- | --- | --- |
| B01 | Taylor–Green grid and timestep studies | LBM; extend 01–05 | Velocity error, decay, observed convergence and conservation at equal physical time. |
| B02 | Poiseuille wall-location study | LBM; extend 07 | Profile error, pressure drop/body-force balance and refinement sensitivity. |
| B03 | Couette shear flow | New LBM benchmark | Linear profile, viscosity and wall shear with explicit wall placement. |
| B04 | Quantitative cavity benchmark | Extend 06 | Centreline profiles and vortex location at specified Reynolds numbers. |
| B05 | Low-Reynolds-number sphere | Resolved stationary walls | Drag against the appropriate analytic limit, blockage and grid sensitivity. |
| B06 | Laminar cylinder shedding | Extend 16 | Strouhal number, mean drag, lift amplitude, domain and averaging sensitivity. |
| B07 | Inlet/outlet disturbance test | LBM boundary study | Reflection, mass balance and downstream-domain sensitivity. |
| B08 | Uniform versus refined grid | Extend 15; future multi-region hierarchy | Conservation, interface error and cost at equal physical time; disjoint/nested/overlapping regions and boundary contacts; then separately qualify obstacle and curved-wall combinations. |
| B09 | Curved versus voxel walls | Extend 14 | Geometry error and force/profile convergence without unsupported refinement combinations. |
| B10 | Device reproducibility matrix | CPU/MPS; CUDA hardware | Declared pointwise and integral tolerances with device and precision metadata. |
| B11 | PorousMedium discrepancy reproducer | Existing unresolved issue | Minimal case, growth history and unchanged comparison criteria. |
| B12 | Moving-wall conservation and load balance | Extend 17–19 | Cycle drift, timestep/grid sensitivity and force/power sign consistency. |
| B13 | Low-Mach scaling sensitivity | LBM | Hold physical conditions fixed while varying lattice scaling; quantify observable changes. |
| B14 | Restart and chunk equivalence | Engine checkpoint capability | Compare continuous/chunked runs; distinguish pause from persisted numerical restart. |

## Proposed shared solver examples

These examples are the proof of the shared-case product idea. Do not compare
methods on physical models they do not both support.

| Key | Proposed example | Dependency | Required outcome |
| --- | --- | --- | --- |
| S01 | Channel with LBM and finite volume | Second engine and common schema | Same material, domain, forcing and sample locations; independent grids and matching profile/flow-rate definitions. |
| S02 | Cylinder with LBM and finite volume | S01 plus transient capability | Match Reynolds number, geometry and averaging window; compare shedding and loads with a chosen reference. |
| S03 | Reuse block setup for an engineering run | Native geometry and FV adapter | Preserve physical settings; show mesh/model changes and preparation cost. |
| S04 | Request an unsupported thermal or free-surface case | Capability checks | Block with an actionable explanation; no silently ignored physics. |
| S05 | Switch method after a completed run | Run history | Retain both results, start a distinct run and compare only compatible observables. |
| S06 | Compare methods at a fixed resource budget | Qualified overlapping case | Report error and full workflow cost, including preparation and field extraction. |
| ~~S07~~ | ~~Liquid particle preview and reference method~~ | Descoped with particle methods (owner decision, November 2026, [#22](https://github.com/range-et/hawa-cfd/issues/22)) | None |
| S08 | Solver failure and unavailable engine | Adapter lifecycle | Preserve case intent and other results; provide recovery without blocking Rhino. |

## Priority RC drone and small boat examples

These are the primary application track. Early means a post-0.5 workflow
candidate subject to existing model limits, not a validated design tool today.
Powered propulsion and surface-running boats require additional physics and
evidence beyond the present demonstrations.

| Key | Proposed example | Stage and scope | Question and acceptance needs |
| --- | --- | --- | --- |
| R01 | Drone canopy or fuselage in forward airflow | Early stationary single-phase workflow | Where does the wake form? Compare movable vector slices; qualify pressure/drag only after resolution, domain and reference checks. |
| R02 | Drone arm and payload-mount variants | Early geometry comparison | How do section shape and orientation change the flow? Use equal physical conditions and sampling; begin with qualitative comparisons. |
| R03 | Propeller guard or duct geometry | Stationary airflow first; powered case later | Separate flow around an unpowered guard from its interaction with a working propeller; thrust claims require the latter model. |
| R04 | Small wing or control-surface incidence sweep | Later aerodynamic qualification | Compare lift, drag and pressure in a stated operating range using suitable reference data; do not use the synthetic sample polar as evidence. |
| R05 | Isolated drone rotor thrust and torque | Later rotating-flow capability | Specify geometry, RPM and fluid; compare thrust/torque and wake against measurements before propeller ranking. |
| R06 | Submerged boat rudder or fin | Early single-fluid workflow | Inspect incidence and wake; qualify side force, drag and moment separately; no water surface in this case. |
| R07 | Submerged hull and appendage variants | Extend existing hull workflow | Compare supported hydrodynamic observables at matched conditions; explicitly exclude wave resistance, flotation and trim. |
| R08 | Small underwater pod or motor fairing | Early stationary single-fluid workflow | Compare shape and alignment using slices and pressure views; qualify loads against a reference case. |
| R09 | Small boat hull at the water surface | Research free-surface track | Prescribe initial draft/attitude; resolve water/air interface and assess waves and resistance against reference data. |
| R10 | Boat flotation and free trim response | Research hydrostatics and coupled motion | Establish buoyancy and force/moment balance, then validate heave/pitch response; separate from fixed-attitude resistance. |
| R11 | Small marine propeller | Later rotating-flow capability | Compare thrust/torque in stated noncavitating conditions; surface effects need a separately supported model. |
| R12 | Complete drone or boat propulsion interaction | Later integrated application | Qualify rotor/frame or propeller/hull coupling only after isolated component studies; report energy and force conventions. |

## Broader application backlog

Applications must earn their own evidence. They do not inherit validation from a
cavity or vortex test. Begin with stationary single-phase cases; broader physics
tracks require explicit implementation and acceptance work.

| Key | Proposed example | Earliest scope | Evidence needed before engineering claims |
| --- | --- | --- | --- |
| A05 | Duct bend or diffuser | P2 internal flow | Pressure loss and profile comparisons; turbulence/wall modelling where required. |
| A06 | Perforated screen or porous barrier | Research geometry/model | Resolved-hole convergence or calibrated porous model; unresolved parity issue addressed for applicable path. |
| A07 | Vehicle or bicycle fairing | Later resolved external flow | Adequate near-wall/turbulence treatment and published pressure/drag reference. |
| A08 | Airfoil angle-of-attack study | Later aerodynamic capability | Suitable Reynolds range, resolved walls/models and measured or otherwise qualified reference data; no synthetic polar evidence. |
| A09 | Finite wing and tip vortex | Later aerodynamic capability | Lift/induced drag convergence; distinguish lifting-line estimates from CFD results. |
| A10 | Submerged hull variant study | Extend 10 | Skin/friction treatment, settled loads and common budgets; no wave-resistance claim. |
| A11 | Oscillating body and cycle power | Extend 17/20 | Settling, cycle count, load balance and motion-resolution studies. |
| A12 | Rotor or propeller in one fluid | Later motion models | Torque/thrust validation, rotating-boundary suitability; no cavitation or waves by default. |
| A13 | Tank sloshing or dam break | Research free surface | Surface position, volume conservation, boundary forces and experimental comparison. |
| ~~A14~~ | ~~Pouring and splashing around geometry~~ | Descoped with particle methods (owner decision, November 2026, [#22](https://github.com/range-et/hawa-cfd/issues/22)) | None |
| A16 | Electronics enclosure cooling | Later conjugate heat transfer | Material interfaces, heat-source balance and temperature references. |
| A17 | Passive tracer transport | Later scalar transport | Scalar conservation, numerical diffusion and boundary flux tests; no health/exposure inference from a flow image. |
| A18 | Floating or freely moving body | Research force coupling | Fluid/body momentum balance, buoyancy and coupled-motion references. |
| A01 | Wind around a single building | Secondary architectural track | Boundary-layer inlet, ground treatment, blockage and pressure/velocity references. |
| A02 | Building spacing and courtyard flow | Secondary architectural track | Multi-building geometry checks, domain/grid studies and suitable experimental data. |
| A03 | Wind directions around a site | Secondary architectural track | Direction conventions, consistent sampling and per-direction evidence; comfort needs separate criteria/weather inputs. |
| A04 | Isothermal cross ventilation | Secondary architectural track | Opening flow rates, pressure balance and internal recirculation references. |
| A19 | Building entrance pressure and vortices | Future user-defined refinement regions | Coarse site and fine entrance grid; pressure histories, conservation, interface and resolution studies; atmospheric-flow assumptions qualified separately. |
| A15 | Buoyancy-driven room or chimney | Secondary architectural and thermal track | Energy balance and coupled velocity/temperature validation. |

### A19 — Building entrance pressure and vortices

Proposed secondary architectural example, dependent on
[user-defined local refinement regions](roadmap.md#user-defined-local-refinement-regions).
Build the site, building and entrance with ordinary GH geometry. Define a coarse
base domain, a fine entrance region requesting a subdivision factor of 10, and
optional intermediate building/wake regions. Display the requested and actual
cell sizes, transition levels and memory estimate before running. Unsupported
ratios require an explicit user choice.

Provide an annotated, editable GH definition with separate geometry, refinement,
solver, probe and visualization groups. Show domain and refinement wireframes,
3D streamlines, pressure slices and entrance pressure probes. Record pressure
reference, units, probe location, physical time and averaging interval. Include a
small smoke configuration and a larger study configuration with stated budgets.

Compare coarse-only and locally refined runs, plus a bounded uniform-fine
reference for verification. Study pressure histories, mean/peak pressure over a
stated interval, vortex behavior, conservation, resolution sensitivity, runtime
and memory. Atmospheric inlet, ground/wall treatment, turbulence assumptions and
domain extent need their own evidence before making building-pressure claims.

The future video should show users placing regions and changing their factors,
inspect the generated levels, then animate settling flow and pressure histories
at matching physical times. Label which frames are workflow demonstrations and
which comparisons have passed numerical checks. Exercise overlap, invalid input,
cancel and edit/restart behavior in the accompanying verification recipe.

### A20 — City → neighbourhood → whole-pond boundary transfer

Follow the [nested-study plan](nested-flow-roadmap.md). Deliver three annotated
uniform-grid cases plus boundary capture/mapping connections, matching-time probes,
quality reports and a synchronized animation. Begin with an analytic time-varying
inlet verification example before the urban demonstration. Show missing coverage,
solid intersections, unsupported backflow and an over-limit local Mach result as
explicit rejection examples. Atmospheric qualification and boundary capabilities
must match the study before making wind predictions. The first pond case models
airflow over a prescribed stationary surface; water motion is separate scope.

## First additions to prioritize

After 0.5, start with W01, W03–W07, W09 and W13 to demonstrate native setup and the
same public case operations for a person or agent. In parallel as a project
workstream, qualify B01, B02 and B06 and retain B11 as an explicit numerical
issue. These supply useful evidence before a larger application gallery.

Use S01 as the first solver-adapter milestone. A13 stays a free-surface research
candidate, not a prerequisite for the next LBM release; S07 and A14 were descoped
with particle methods.
Lead application work with R01/R02 for drones and R06/R08 for underwater parts,
starting with setup and qualitative fields. R07 extends the existing submerged
hull search. Gather appropriate reference data before promoting load comparisons.
R05/R11 and R09/R10 are later propulsion and surface-boat tracks respectively;
their importance to the audience does not make those capabilities available now.

## Contribution and packaging rules

Every proposed example needs a physical question, dependency checklist, reference
data rights, input assets, small smoke configuration, analysis configuration,
expected observables, acceptance criteria and maintenance owner. Record the
engine version, device, physical duration, resolution, runtime and checks actually
run. A render or successful completion is not a validation result.

Add future files without changing existing functional IDs, wires or archives.
Run the repository annotation and connection checks after regenerating supported
GH examples. Separate numerical analysis from UI smoke runs and report skipped
hardware checks. Keep large generated result sets outside the example package;
ship sufficient settings and scripts to regenerate them.
