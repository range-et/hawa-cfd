# Hawa project roadmap

> Direction and reference material; actionable feature, build and example work is
> tracked in [GitHub Issues](https://github.com/range-et/hawa-cfd/issues).
> Create or update a linked issue for new work instead of adding a parallel task list.


Draft direction as of November 8, 2026. Hawa's primary audience is people designing
RC drones, small boats and similar small vehicles and parts in Rhino. Hawa aims
to make a physical flow case easy to create, editable through the native panel,
Grasshopper and public agent operations, and reusable across suitable numerical
solvers. The product opportunity is continuity from a design question to a
reproducible simulation, with the assumptions and evidence visible throughout.

The 0.5 native prototype remains bounded by its
existing guide. Everything beyond that baseline here
is proposed work, ordered by dependencies and acceptance gates rather than
promised dates. The [example catalogue](example-roadmap.md) records existing
definitions and a larger candidate backlog.

## Primary audience and design questions

Lead the product and example gallery with hobby-scale aerodynamics and
hydrodynamics. The main design questions are how air or water moves around a
part, how a geometry change affects its loads and wake, and which comparisons
are supported by the available model. The intended audience includes makers,
RC designers and small teams, with experts and researchers able to extend the
same open workflows.

Prioritize these journeys:

- **Drone body and attachments:** inspect flow around an unpowered frame, canopy,
  arm or payload mount; compare geometry variants with movable vector slices.
- **Small wings and control surfaces:** set incidence, examine pressure and wake,
  and eventually compare supported lift/drag measurements with reference data.
- **Drone propulsion:** later study isolated rotors, propeller guards and
  rotor/frame interactions, after the rotating-flow model has appropriate
  numerical and experimental evidence.
- **Small boats and underwater parts:** start with explicitly submerged hull,
  rudder, fin and fairing studies supported by single-fluid physics.
- **Surface-running boats:** develop a separate water/air free-surface track for
  hull waves, flotation, trim and eventually coupled body motion. A submerged
  hull demonstration must not be presented as a complete boat-resistance study.

Physical size, units, material properties and operating speed must describe the
intended RC case. A coarse demonstration using artificial viscosity is a workflow
example, not an RC performance prediction. Choose reference experiments in the
intended operating conditions before claiming useful force or efficiency results.

Building wind and ventilation remain optional secondary applications. Their
presence in comparison tools should not determine Hawa's default terminology,
onboarding, gallery order or numerical development priorities. Keep the generic
block case and analytic benchmarks as useful development fixtures; follow them
with vehicle and part examples in the user journey.

## One physical case with a choice of solvers

The intended workflow is: select geometry, describe the physical problem, choose
an eligible solver, run, inspect and compare. Changing solver should preserve the
physical case wherever the methods support the same problem.

For example, a user selects a drone canopy, places an air domain around it, specifies
inlet velocity and material properties, identifies walls and an outlet, and asks
for pressure, drag and wake probes. They first explore with LBM, then request a
finite-volume run of that case. Geometry references, physical settings and probe
definitions carry across; the new method gets its own mesh and numerical setup.
A particle solver is offered only if it supports that physical problem and the
requested outputs. A liquid splash preview is a separate physical problem from
single-phase airflow around the same body.

### What stays shared and what varies

| Preserve as physical intent | Resolve for each solver |
| --- | --- |
| Geometry identity, body groups, units and coordinate system | Geometry preparation, voxelization, surface or volume meshing |
| Physical domain and named boundaries | Computational padding, boundary discretization and supported boundary implementations |
| Fluid properties and prescribed velocity or pressure | Lattice scaling, particle spacing or finite-volume discretization |
| Gravity, prescribed motion and supported sources | Time integration, stability limits and coupling algorithms |
| Initial physical state | A new initialization or an explicitly supported field transfer |
| Force and moment requests, probes and averaging windows | Load integration, pressure reference and sampling implementation |
| Reference area, reference length and coefficient definitions | Solver diagnostics, discretization errors and supported observables |
| Design parameters, objectives and result history | Cost, memory, engine/device availability and execution environment |

Distinguish applied forces such as gravity from measured fluid loads such as drag.
The request for drag can remain identical; the resulting number is a prediction
of a particular run and must retain its method and assumptions.

Changing solver starts a new run linked to the same physical case revision. It
does not resume the old solver state. Compare physical time or a documented
steady-state criterion, not iteration counts. Record pressure conventions,
coordinate frames, force signs and reference quantities before comparing loads.
Show particle, lattice and volume-mesh results through common field views while
preserving their native data and sampling limitations.

### Capabilities are part of the user experience

Before running, each solver must report whether it supports the selected phases,
boundary types, motion, material properties, requested outputs and device. A
missing capability either blocks the run with a useful explanation or requires
an explicit change to the case. It must never silently drop gravity, change
viscosity, omit a wall or invent a force output.

Keep three choices separate: physical model, numerical method and execution
device. Offer understandable presets, with advanced controls available when
needed. Preview, Explore and Engineering are possible workflow labels; they
describe intended use and evidence requirements. They are not an automatic
accuracy ordering of particle methods, LBM and finite volume. LBM itself is used
for industrial CFD, as illustrated by
[SIMULIA PowerFLOW](https://www.3ds.com/products/simulia/powerflow/).

## Current foundation

Hawa has an embedded Python 3.9/PyTorch LBM engine, background jobs, cooperative
controls, field visualization, recording, asynchronous searches and experimental
prescribed moving bodies. The gallery has 19 supported GH definitions plus the
native live-sync example. The modified historical example 09 remains excluded
from supported packages.

The 0.5 prototype demonstrates one shared block-flow case per Rhino document,
native controls, linked GH inputs, revision tracking, undo and settings
persistence. Its public case interface provides a bounded starting point for
agent operation. Arbitrary selected geometry and a general solver-neutral case
schema are future work; existing GH functionality is broader than the panel.

The 0.4 closeout (now in the private maintainer archive),
[release limits](release-notes-v0.4.0.md) and
0.5 verification establish the present evidence.
PorousMedium CPU/MPS parity has a candidate KBC repair under review ([record](review-porous-kbc-repair.md)); it is not merged or released. Windows, CUDA and clean-machine setup
still need their documented checks. Native demonstrations and valid field meshes
do not establish engineering accuracy.

## Runtime foundation and installation

Decision recorded November 9, 2026: keep Python/PyTorch as the foundation for
Hawa's embedded numerical engine. Preserve Python 3.9 and the pinned dependencies
until a separately tested runtime migration is scoped. The Rhino/GH host remains
in C#; additional solver adapters may use their own established engines.

Make installation as seamless as possible on **macOS and Windows**. The intended
experience is: install Hawa in Rhino, let it prepare the required numerical
dependencies, then run locally on a supported device. Users should not need a
separate Python installation or manual environment management for the embedded
engine. First-use downloads, required restarts and errors must be clearly shown,
with actionable retry/recovery guidance and a small installation-check case.

Treat CPU as the baseline execution path, with MPS or CUDA acceleration on
compatible, tested hardware/builds. Report the selected device and any automatic
fallback; an unavailable explicitly requested device must produce a clear error.
PyTorch portability is a foundation for platform support, not a guarantee that
every device, operator or configuration works. Validate clean installation,
first run, reopen, update and failed/interrupted dependency preparation on each
supported OS. Record OS, architecture, Rhino/runtime versions and device; unrun
platform checks remain unverified. Future external engines must disclose their
own installation requirements.

Do not schedule a Rust rewrite. Consider a small Rust accelerator only after
profiling an actual workload identifies a material bottleneck. First distinguish
Python execution, tensor/kernel work, synchronization, data copies and viewport
cost. Compare simpler optimizations with a bounded native prototype, measuring
the complete workflow and integration/packaging cost. Adopt it only with a
demonstrated benefit, unchanged numerical acceptance criteria, and preserved
pause/cancel and cleanup behavior. Keep the public case operations stable.

This decision adds roadmap priorities, not new implementation requirements to
the agreed 0.5 scope. See the documentation review.

## Related tools and the opportunity for Hawa

This is a comparison of documented scope, not a performance ranking. Food4Rhino
is a distribution and discovery channel; the relevant comparison is with the
projects distributed there and elsewhere in the Rhino ecosystem.

| Project | Documented strength | Implication for Hawa |
| --- | --- | --- |
| [Butterfly](https://www.ladybug.tools/butterfly.html) | GH/Dynamo and Python workflows around OpenFOAM, including indoor/outdoor airflow and buoyancy | Open-source CFD in Grasshopper already exists. Reuse ecosystem knowledge and mature numerical engines. |
| [Eddy3D](https://docs.eddy3d.com/latest/) | Rhino 8 GH workflows for urban microclimate and indoor/outdoor airflow; its unified package includes FluidX3D alongside other modules | Multiple engines, LBM, examples and Rhino integration alone do not distinguish Hawa. |
| [GH_Wind](https://github.com/christophwaibel/GH_Wind) | Fast Fluid Dynamics for early building design, with published comparisons and optimization examples | Fast early-design airflow and parametric optimization are established ideas. |
| [RhinoCFD](https://rhinocfd.com/rhinocfd.php) | CFD directly in Rhino using PHOENICS, including steady/transient analyses and residual monitoring | A native Rhino interface already has precedent; Hawa needs continuity between native, GH and programmatic operation. |
| [FlexHopper](https://github.com/HeinzBenjamin/FlexCLI) | Grasshopper physics through NVIDIA Flex | Interactive particle physics in GH already has precedent. Hawa should justify its fluid model and shared-case integration. |

Eddy3D's [current FAQ](https://dev.eddy3d.com/faq/) also documents macOS support,
multiple execution arrangements and engine terms. Its
[release history](https://www.eddy3d.com/download/) includes CLI work. Hawa should
not claim exclusive cross-platform, automation or multi-engine capability.

### The proposed distinction

The preferred product experience is a focused CFD tool for Rhino: select a drone
part, small wing, hull or rudder, set up its surroundings and fluid, run, and
inspect the flow. Use direct physical language and lead with RC vehicle examples.
Building and ventilation templates are secondary extensions.

The design references express different priorities:

- **GH_Wind:** take inspiration from readable vector fields on movable slices.
  Make flow direction and recirculation easy to inspect in the Rhino viewport.
- **FlexHopper:** aim for responsive interaction while keeping the default task
  focused on fluid analysis, with sensible CFD setup and measurement controls.
- **Eddy3D:** learn from its established workflows, while giving Hawa an RC
  vehicle-and-part starting point. This is a preference for Hawa's product scope,
  not a judgment about Eddy3D's quality or supported applications.

Prioritize a vector-slice workflow after the bounded 0.5 work: place and move a
plane, sample velocity arrows over an optional scalar field, adjust arrow density
and scale, and compare with fixed legends. Distinguish velocity projected into
the plane from full 3D velocity sampled on the plane. Mark solid/invalid samples,
show physical units, and update the display without restarting the simulation.
Use the same snapshot and controls across native and GH views, with public
operations for agents. This extends the existing scalar slice and field views;
it is a proposed integrated visualization workflow, not a newly shipped feature.

Hawa should concentrate on the combination of these properties and prove it with
examples:

1. **A durable physical case in the Rhino document.** A user can start with the
   native panel, drive parameters from GH, and let an agent inspect or edit the
   same case through public operations. Ownership, revisions and stale results
   remain clear across all three interfaces.
2. **A small path to useful local feedback.** The current embedded engine runs
   inside Rhino without a separate solver service or OpenFOAM installation.
   Measure installation friction, first-field latency and editing responsiveness.
   Do not promise that every future engine will have this execution model.
3. **Continuity across numerical methods.** Preserve physical setup and comparison
   definitions while making solver-specific requirements explicit. Deliver a
   real compatible-case handoff before advertising interchangeable solvers.
4. **Evidence attached to results.** Ship runnable examples with expected checks,
   convergence studies and known limits. Let users see whether a result is a
   qualitative preview, a verified benchmark or a validated application within
   stated conditions.
5. **A public contribution surface.** Researchers can add an adapter, benchmark
   or tutorial without rewriting Rhino UI and job management. These extension
   contracts still need to be designed and tested.

This is a product hypothesis, not a claim that no other tool can offer these
properties. Hawa is worth building if it demonstrably reduces repeated setup and
allows better-supported design decisions. A larger component count or another
attractive flow render would not establish that value.

The next implementation proposal is the ten-issue Python queue: integrate the completed branches first, then prioritize numerical correctness, input contracts and usable results. C#/Rhino work remains a separate later phase; individual PR completion does not qualify an entire physical model.

## Delivery sequence

Only 0.5 has an existing release scope. Later milestones are working groups of
tasks; assign versions after feasibility and contributor capacity are known.

| Stage | Deliverable | Acceptance gate |
| --- | --- | --- |
| 0.5 native prototype | Finish the existing block-case panel and GH sync scope | Existing native lifecycle, ownership, persistence and revision checks pass; document platform and installation checks actually completed or deferred. No new solver requirement. |
| A Native case setup | Selected geometry, explicit units, editable domain, named boundaries, material settings, probes and measurement requests | A user and an agent independently reproduce one stationary block case through public operations; saving/reopening preserves intent and stays idle; invalid setup has actionable messages. |
| B LBM evidence and examples | Stronger benchmark coverage, domain/grid/time sensitivity, force conventions, memory and device reports; user-defined refinement regions after coupling verification | Publish bounded benchmark outcomes and tolerances; investigate the PorousMedium discrepancy without widening tolerances to conceal it; qualify accuracy per case. |
| C Shared solver contract | Physical-case schema, capability checks, adapter lifecycle, result metadata and solver-specific preparation | Two actual methods accept one overlapping case; round-trip intent and detect unsupported features; retain GH archives and migrate saved case schemas explicitly. |
| D Particle feasibility | One bounded physics prototype independent of rendering, with a PyTorch candidate implementation | Choose liquid/free-surface or airflow scope first; measure stability, conservation, boundary behavior, neighbour-search cost and responsiveness on named hardware; adopt, revise or stop based on the evidence. |
| E Finite-volume integration | One established engine connected to the shared case, initially one stationary isothermal flow class | Generate a mesh, run asynchronously, inspect convergence and conservation, obtain comparable fields/loads, and reproduce a published benchmark with documented settings. |
| F Reusable engineering studies | Case variants, batch runs, comparisons, measured search objectives and reproducible report export | A second contributor repeats a complete design study; results retain geometry/settings/engine identity and measurement definitions. |
| Later physics tracks | Thermal/scalar transport, free surfaces, force-driven motion and additional models | Each track gets a physical scope, reference cases, supported engines and maintenance owner before entering a release. |

Stages A and B establish value with the existing engine. Short feasibility work
for D and E can inform C, but broad UI or schema generalization should follow
actual adapter needs. Neither an unsuccessful particle experiment nor delayed
finite-volume work should prevent improving the LBM product.

<a id="nested-city--neighbourhood--pond-studies"></a>

### Parent/child flow studies

Use an outer parent → local child → finer child hierarchy to describe separate
flow studies, with explicit source identity, resolution and physical time.
The [user guide](parent-child-domains.md) separates existing offline transfer,
restricted coupled refinement and composed views. City → neighbourhood → pond is
one atmospheric application; the terminology does not qualify other physics.

Add [boundary-field transfer and atmospheric study capabilities](nested-flow-roadmap.md)
to the future LBM/shared-case workstreams. Prioritize result-quality diagnostics
and space/time-varying vector inlet import for separate uniform-grid cases.
Atmospheric-model qualification and supported child-boundary geometry are gates
for useful urban results. Multi-level wall-contact refinement and larger/block
storage follow separately. Arbitrary graded volume-mesh import remains distinct.
The linked plan defines reusable nodes, data contracts, sequencing and examples.
A [bounded development implementation](boundary-transfer.md) now provides sampled
quality diagnostics and offline inlet transfer; see its gate record for tested
combinations and remaining limitations.

### User-defined local refinement regions

Requested November 8, 2026. Add spatial resolution controls to the future LBM
workstream, building on example 15's experimental single fixed 2:1 patch.
This is proposed work; support for multiple regions and levels remains to be
implemented and verified. Keep surface tessellation settings separate from the
volume grid used by the solver.

The user starts with one physical simulation domain and a coarse base cell size.
They add refinement regions and assign each a subdivision multiplier relative to
that base: `requested local cell size = base cell size / multiplier`. A multiplier
of 1 retains the base resolution. A multiplier of 10 requests cells one tenth as
wide. Regions control resolution inside the same fluid domain; they do not create
walls or independent simulations.

Proposed reusable Grasshopper workflow (component names are provisional):

1. **Domain** supplies the physical extent and base cell size.
2. **Refinement Region** pairs a box or supported closed volume with a positive
   subdivision multiplier. Start with boxes; qualify other closed volumes later.
3. **Refinement Plan** combines regions. The finest requested resolution wins in
   overlaps. Preserve region IDs, units and geometry snapshots; reject invalid
   factors and report regions outside the domain or too small to resolve.
4. **Generate Grid** prepares the supported hierarchy and reports actual cell
   sizes, level boundaries, cell counts, estimated memory and any unsupported
   settings before starting a solve. Preview the base domain, regions and grid
   levels in Rhino. Preparation must support cancellation and resource limits.

Native controls and public agent operations must use the same saved plan as GH.
Keep requested resolution in the physical-case schema and generated hierarchy in
solver preparation metadata. Editing either geometry or refinement invalidates
old preparation and results through the existing revision/generation contract.
Save/reopen must preserve intent without starting a job.

The target includes roughly 10:1 coarse-to-fine cell widths. Select supported
ratios, nesting, transition buffers, time stepping and interface coupling during
numerical design. For example, if the implementation supports only nested 2:1
levels, offer an explicit 8:1 or 16:1 alternative; never silently change a 10:1
request. Arbitrary imported cell connectivity and automatic solution-driven
adaptation require separate scope. This feature generates a solver-compatible
grid from user regions.

Before release, extend B08 with disjoint, nested, overlapping and boundary-touching
regions; exercise supported wall/refinement combinations and reject unsupported
ones. Compare conservation, interface errors, pressure and velocity against a
uniform fine reference at equal physical time. Set tolerances before execution.
Measure runtime and memory on each tested device. Check cancellation, failed
preparation, stale completions, save/reopen and region edits through GH and native
controls. A detailed grid preview alone does not verify solver coupling.

The architectural example is **A19: building entrance pressure and vortices** in
[the example backlog](example-roadmap.md). Use coarse cells across the site, a
fine entrance region, and optional intermediate regions around the building and
wake. The region tools also apply to drone gaps, wing tips and underwater parts.
Keep the building and door geometry in an ordinary GH example assembly.

### Scope the first additional solvers narrowly

For the particle experiment, [Sebastian Lague's Fluid-Sim](https://github.com/SebLague/Fluid-Sim)
is an inspiration for simulation techniques independently of graphics. Select one
reference experiment and agree particle count, physical duration, memory budget,
interaction target and numerical criteria before coding. A visually convincing
liquid demo does not establish an airflow or force-analysis capability. Python
3.9 and pinned PyTorch compatibility remain requirements for production Python.

For finite volume, evaluate integrating an established open-source engine such
as [OpenFOAM](https://openfoam.org/) before writing a new general-purpose solver.
Pick a distribution/version, supported execution platforms, packaging approach
and licence obligations explicitly. Start with a stationary incompressible
isothermal case; stage turbulence and boundary-layer requirements as subsequent
capabilities. The conventional solver direction is consistent with
[Fluent's finite-volume approach](https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/flu_th/flu_th_SolveOverview.html),
without implying feature parity with Fluent.

External workers or containers may be appropriate for that engine. Preserve a
common nonblocking job interface and cooperative controls where supported; expose
any differences such as unavailable resume/checkpoint support. Do not impose
embedded PyTorch as a requirement on every numerical engine.

## Examples as a maintained product

Use the [catalogue](example-roadmap.md) as a backlog, not a promise to implement
every application. Prioritize setup and benchmark coverage before specialist
showcases. Each shipped example should provide:

- A physical question, reproducible geometry, units, boundary conditions and
  supported method/device combinations.
- A small installation run and a separate analysis run, with physical duration,
  settling/averaging periods and expected resource use where measured.
- Expected observables, reference provenance, acceptance criteria chosen before
  execution, and explicit numerical/physical limits.
- Editable `.3dm`/`.gh` assets where relevant, instructions for public agent
  operations, and run metadata sufficient to repeat the result.
- Automated checks appropriate to the claim, native lifecycle checks when
  relevant, and a named contributor responsible for updates.

Track evidence separately: **demo** shows a workflow; **verification** checks the
numerical implementation; **validation** compares a physical prediction with an
appropriate experiment. Validation applies within stated conditions. Do not
promote all variants of an example because one configuration passed.

## Open source development and collaboration

Build on Lettuce and other upstream projects, preserve licences and attribution,
and propose generally useful fixes upstream when practical. Original Hawa code
remains GPL-3.0-only; inspect each proposed dependency and distribution separately.
Open development also includes publishing failed experiments, regression cases
and unsupported combinations.

Use issues for scoped tasks and public design proposals for changes to the case
schema, solver contract or numerical models. A proposal should state its user
question, reference method, alternatives including existing integrations,
acceptance data, maintenance burden and release impact. Record the decision in
the repository. This roadmap does not create issues or contact maintainers.

Useful contribution areas include geometry/setup UX, numerical benchmarks,
Windows/CUDA hardware checks, adapter development, GH archive compatibility,
example writing and documentation. Encourage contributors to reproduce an
existing example before adding a new physics feature. Evaluate interoperability
with Butterfly/Eddy3D workflows when useful rather than duplicating their entire
building-environment toolchains.

## Measures that decide whether to continue

Record baselines before assigning performance promises. Measure time to a valid
first case, manual steps required, first useful field, edit-to-result latency,
peak memory, cancellation response and independent reproduction rate. Record
hardware, device, grid/particle count, physical duration, solver settings and
whether preparation and visualization costs are included.

For numerical evidence, measure conservation and benchmark errors alongside
grid/time/domain sensitivity. For comparisons, require matching physical cases
and observables, not equal iteration counts or identical-looking colour maps.
For solver handoff, count what the user had to re-enter and what changed in the
physical model.

The next planning action after 0.5 is to select one native geometry workflow and
one benchmark family, publish their acceptance criteria and invite reproduction.
Use an unpowered drone canopy or frame part for the first application workflow,
followed by an explicitly submerged boat rudder or fin. Keep powered rotor and
surface-running boat work behind their own physics and validation gates.
Only expand into another solver when it answers a specific user question better
and the project can maintain the integration.

## General boundary and atmospheric capability scope

The [next-stage assessment](general-boundaries-atmosphere-scope.md) separates patch
topology, open/wall boundary numerics, physical field transfer, high-Re closure
and grid refinement. It records a reproduced mapped-inlet/curved-wall composition
defect and defines the gates before enabling general nested-domain studies.

Boundary foundation implementation: [guide](general-boundaries.md) and
[gate record](general-boundaries-review.md). The physical patch contract and bounded
NEE adapter are separate from future multi-patch datasets, atmospheric wall/SGS
qualification, full cut-face validation and wall-contact refinement. Do not count
the shared contract as completion of SPH or finite-volume adapters.
