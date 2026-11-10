# General boundaries, nested cases and high-Reynolds-number flow

Scope review, November 8, 2026. Requested before implementation. This builds on
[the current transfer feature](boundary-transfer.md) and [nested-study roadmap](nested-flow-roadmap.md).
No production solver change is included in this review.

## Decision

Treat this as three connected workstreams: general boundary conditions, physically
consistent case transfer, and qualified high-Reynolds-number flow modelling. Grid
subdivision is a fourth workstream that controls spatial cost and resolution.
It cannot supply missing wall stress, turbulence or open-boundary behaviour.

The reusable target is a stationary single-fluid case with named boundary patches,
closed bodies that may extend outside the computation window, and external fields
that can drive supported patches in physical space/time. City, pond, drone, duct
and building entrance workflows should assemble the same operations.

The first atmospheric target should be neutral, isothermal, mechanically driven
flow over prescribed stationary terrain/roughness. Water can be a prescribed
surface with an explicit stress model. Wind-driven water currents, waves and
thermal atmospheric stratification are separate physics. Excluding temperature
limits the atmospheric regime; it does not make thermal stability irrelevant.

## What the code actually lacks

| Layer | Current limitation | Required change |
| --- | --- | --- |
| Boundary topology | Six strings, one X- inlet/X+ outlet; boundary masks overlap at edges | Named patches with normals, fluid/solid classification, edge/corner rules and ownership of incoming lattice links |
| Boundary numerics | Equilibrium inlet resets populations; mapped hook overwrites the full inlet plane after streaming; outlet copies the adjacent plane | Verified velocity/pressure/open-boundary reconstruction; preserve the required non-equilibrium information; explicit compatible pressure reference |
| Geometry preparation | Native geometry requires a two-cell interior margin on every face; Python rejects solids at inlet/outlet | Classify the original closed world geometry through a cropped computation window and stencil halo; identify mixed solid/open patches |
| Field transfer | A child-grid-bound X- velocity array, positive streamwise velocity, no masked samples | Patch-indexed physical datasets, coverage/mask provenance, vector/tensor transforms, incoming/outgoing use, pressure/stress/turbulence compatibility and time semantics |
| High-Re model | FP32 relaxation guard, selectable collision models and basic Smagorinsky; no qualified rough-wall/atmospheric closure | Joint scaling/collision/SGS/wall/inflow design with reference cases and measured device envelope |
| Evidence | Sampled Mach/density checks and approximate nodal flux | Discrete mass budget, reflection and wall-leakage tests, profile preservation, turbulence statistics, settling and application validity |
| Grid/capacity | Dense cells and one interior fixed 2:1 BGK patch | Later wall-compatible hierarchy, level coupling, block storage and actual resource budgets |

### A reproduced composition defect must be addressed first

`plugin.py` installs a mapped `_collide_and_stream` wrapper, then `walls.py`
replaces that method for interpolated walls. Preflight currently accepts this
combination. CPU reproduction using the existing curved-wall fixture and a linear
inlet time profile, 10 steps: expected inlet ux=1.02886751346 m/s; maximum error
0.14681312494 m/s, versus the existing prescribed-profile tolerance 5e-6 m/s.
The active handler is `install_interpolated_walls.<locals>.step`.
Evidence: `results/atmospheric-scope/composition-audit.json`.

This is a failed combination, not evidence against the previously tested child
without curved walls. Immediately gate the combination or fix composition in the
implementation stage. Do not remove periodic/solid restrictions as a shortcut.
Replace competing wrappers with a single solver step coordinator and explicit
pre-collision, post-collision, streaming and boundary-reconstruction phases.

## Proposed common data contracts

- **PhysicalCase** retains units, fluid properties, coordinate frame, geometry
  identities, domain and requested observations. Refinement intent stays separate.
- **BoundaryPatch** names a domain-face subset or body-surface group and carries
  orientation, geometric identity and physical intent. The solver compiles cell/link
  masks; users do not edit flattened population indices.
- **BoundaryCondition** specifies the supported operation: prescribed velocity,
  pressure/open exterior, periodic, symmetry/slip, resolved wall or modelled wall
  stress. Scalar values, analytic profiles and file series are interchangeable
  data sources where their units/fields satisfy the condition's contract.
- **BoundarySeries v2** separates world-space sample data from a child-grid map.
  It records time origin, basis, normals/areas, fluid/solid/unknown masks, source
  geometry/model identity, pressure convention, instantaneous/mean/statistical
  semantics, interpolation/filter policy and quality provenance. Optional stress
  or turbulence fields must name their model; no automatic RANS-to-LES equivalence.
- **CompiledBoundaryPlan** owns every affected lattice link once, resolves corners,
  checks missing/contradictory constraints and produces preview and compatibility
  reports. Wall priority alone is insufficient at an inlet/ground corner: the
  prescribed fluid profile and wall reconstruction must also be compatible.
- **FlowModel / WallTreatment** separate molecular viscosity, collision numerics,
  SGS or mean-flow closure, roughness and wall stress. Numerical stabilisation must
  not silently change the user's physical viscosity.
- **QualityReport** separates numerical health, boundary/transfer consistency,
  resolution/statistical sufficiency and physical-model applicability. A passed
  Mach check cannot imply approval of all four.

Preserve old GH component IDs and schema readers. Keep legacy equilibrium runs
explicitly identified; do not silently reinterpret archived cases with a different
boundary algorithm. Version compiled plans, datasets and numerical method IDs.
Hash source geometry and boundary data. Edits invalidate mapping and child results
through the existing case/revision/generation ownership. Preparation, mapping and
solving remain cancellable workers; GH/native adapters only submit and poll.

## Ground, cropped bodies and open faces

Retain full closed source bodies. Compute occupancy and wall intersections inside
the selected domain plus the halo required by each numerical stencil. Do not
geometrically trim a building into an open mesh and then rely on a closed-solid
containment test. Do not cap an entire child face as a wall when only part of it
cuts a building. The remaining face area remains fluid and gets its own boundary.

Distinguish three mapping outcomes: valid source fluid; source/target solid with
consistent geometry; unresolved or inconsistent coverage. Solid samples are not
zero-velocity inflow. Missing fluid coverage is an error. Coarse parent versus
fine child geometry needs an explicit discrepancy report and a supported policy,
rather than silently opening a blocked passage. Use an enlarged child/buffer where
needed; crossing permission cannot make every cropped domain physically suitable.

Allow any of the six oriented faces to carry prescribed or open conditions.
Incoming/outgoing classification uses the outward normal and an appropriate
boundary-state estimate, not the global X velocity or the immutable word “inlet”.
For reversing flow, define what exterior velocity/turbulence enters the domain and
how pressure/outflow is treated. Compare switching/mixed and characteristic or
convective candidates under reversal tests; do not promise nonreflection from a
sign switch. Avoid prescribing independent velocity and pressure constraints on
the same patch without a formulation that supports them.

## Why viscosity is a separate blocker

For the current conversion, `tau - 0.5 = 3 nu dt / dx²` and
`dt = Ma_ref dx / (sqrt(3) U_ref)`. For illustration, molecular air
nu=1.5e-5 m²/s, U_ref=5 m/s and Ma_ref=0.05 give:

| Cell width | tau − 0.5 |
| --- | --- |
| 0.1 m | 2.598e-6 |
| 1 m | 2.598e-7 |
| 10 m | 2.598e-8 |

The current guard rejects margins ≤1e-6. This is a calculation from Hawa's actual
scaling, not a measured stability boundary. Smaller cells help this margin but
increase cost; lower reference Mach also reduces the margin. Enabling SGS does
not guarantee a nonzero eddy viscosity everywhere, especially at initialisation
and weak strain. FP64 may aid diagnosis on supported devices but does not supply
missing wall or turbulence physics. Do not relax the guard or replace molecular
viscosity with a convenient constant to claim real-air results.

Before selecting a model, audit the current Smagorinsky implementation independently
of upstream parity. It contracts the strain tensor with itself and uses that value
in eddy viscosity. The computational-physics agent independently confirmed that
`Flow.shear_tensor` is a linear second moment: the code computes `Cs²(S:S)` while
the standard unit-lattice expression is `Cs² sqrt(2 S:S)`. For small strain
amplitude epsilon, these scale quadratically and linearly respectively; the
relaxation fixed-point iterations do not remove that difference. This is a
constitutive-formulation discrepancy. A manufactured-strain test must quantify
it and define any correction and compatibility policy before atmospheric work.
Its whole-flow consequences have not been measured in this scope. Agreement with
upstream proves reproduction, not physical correctness.

Evaluate a narrow high-Re LBM configuration combining collision stability, precision,
SGS closure, rough-wall stress and consistent inflow. Do not add a catalogue of
untested models. Select the successful combination from evidence, then expose it.
If the embedded implementation cannot meet the benchmark and memory envelope,
retain the shared case/boundary contracts and evaluate an established solver
adapter as an explicit deployment decision. External execution is not introduced
by this scope, and is not a prerequisite for the basic boundary work.

## Familiar CFD workflows to support

1. **Boundary-value problem:** prepared geometry → patches → compatible velocity,
   pressure and wall conditions → numerical scaling/model check → solve → mass,
   reflection and wall diagnostics. Verify laminar channels before atmosphere.
2. **One-way nested computation:** qualified parent/precursor → boundary sampling
   on the child envelope → conservative mapping assessment and model compatibility
   → child initialisation/spin-up → comparison in overlap regions. Finer grids do
   not invent the unresolved turbulent content of a coarse or mean parent.
3. **Neutral atmospheric LES:** compatible mean profile and resolved/synthetic or
   precursor turbulence → matched rough-wall stress → stable collision/SGS → empty
   domain profile/statistics preservation → obstacle validation. A log-law velocity
   profile alone is incomplete. Steady RANS is a separate mean-flow route; it does
   not produce resolved gust/wake time histories merely by writing timed files.

PALM explicitly treats turbulence adjustment regions as part of nesting and warns
against large parent/child spacing jumps (its guidance recommends avoiding ratios
above 5). That is PALM-specific guidance, not a new universal Hawa limit. Our
requested roughly 10× local resolution target must therefore be evaluated with
intermediate stages and sufficient adjustment distance, separately from whether
a grid generator can create the cells. See the PALM source below.

## Nodes and example assemblies

| Public operation | Proposed organization | Contract |
| --- | --- | --- |
| Boundary Patch | Domain / Boundaries | Select face/subregion or body group; report normals and coverage |
| Boundary Condition | Physics / Boundaries | Assign velocity, supported open/pressure, periodic or wall behaviour and data |
| Boundary Set | Extend Boundaries | Combine patches; validate conflicts, coverage, edges and pressure reference |
| Boundary Data / Capture / Map | Extend Flow Transfer | Load/capture world-space series and compile maps for selected patches; retain v1 reader |
| Flow Model | Extend Physics | Choose a qualified collision/closure configuration and declared applicability |
| Wall Treatment | Physics | Resolved no-slip, symmetry/slip or qualified modelled stress with physical parameters |
| Inflow Profile | Physics, after qualification | Uniform, measured or neutral atmospheric profile; associated turbulence requirements remain explicit |
| Geometry Check / Grid Preview | Extend existing nodes | Show cropped-solid classification, open area, wall links, conflicts and stencil clearance |
| Check Case / Result Quality | Extend existing nodes | Scaling feasibility, resource budget and separate numerical/physical quality dimensions |

Keep domain subdivision in the existing refinement roadmap. Avoid public “city”,
“building entrance” or “pond” nodes. These are annotated example assemblies using
ordinary geometry and the reusable services above. Native panel and public agent
operations use the same schema; they should not get independent boundary engines.

## Build sequence and gates

| Milestone | Deliverable | Required evidence |
| --- | --- | --- |
| A Composition and topology | Gate/fix the known combination, audit SGS strain scaling, one boundary coordinator, patch schema and compiler | Existing examples remain readable; mapped+curved wall regression passes or rejects; unique link ownership; conflicting assignments fail; cancel/edit/dispose and stale callback tests |
| B Walls plus prescribed inflow | One verified velocity reconstruction with wall-compatible edges and arbitrary face orientation | Uniform/profile regressions, Poiseuille/Couette, 90-degree rotation equivalence, wall leakage and discrete mass budget; comparisons at equal physical time |
| C General open/cropped boundaries | Mixed fluid/solid patches, side/top input, pressure reference and reversal handling | Cropped-body versus larger-domain reference; oblique flow; two open faces at corners; vortex exiting and re-entering; reflection and mass-storage residuals; curved/narrow-gap cases rejected unless qualified |
| D High-Re feasibility and neutral model | Audit SGS; select collision/precision/wall/inflow combination | Analytic closure scaling, controlled shear/channel references, empty-domain neutral profile/stress preservation, turbulence spectra/statistics where claimed, measured physical-duration/device cost |
| E Qualified nested study | Multi-patch BoundarySeries v2, transfer assessment, initialisation/spin-up and examples | Known analytic transforms and flux mapping; source/target geometry mismatch; overlap comparisons; grid/time/domain sensitivity; turbulence/pressure evidence against suitable external references |
| F Local hierarchy and capacity | Wall-contact multi-level grids and block allocation | Separate coupling/conservation/interface tests, memory/runtime measurement and comparison with uniform-grid references |

A small D feasibility study should run before committing to a broad atmospheric
UI or deadline. B/C use affordable laminar problems while D investigates the model.
Several independent uniform grids can support E; F need not block that pilot.
No milestone gets an atmospheric label solely because its scene contains buildings.

For each implementation milestone, use G0 research, G1 architecture, G2 reliability,
G3 numerical physics, G4 live GH/native examples and G5 packaging/device gates.
Fix tolerances before measurement and retain rejected combinations explicitly.
Measure conservation with discrete streaming/boundary accounting and fluid-mass
storage; the current nodal face quadrature is an informational estimate only.
Add channel with ground, cropped block, reversing cross-flow, neutral empty domain
and nested obstacle examples before the city-to-pond showcase. Require annotated
files, public MCP recipes, pause/cancel/reopen checks and physical-time animations.

## Sources and assessment status

Primary sources checked November 8, 2026:

- [Zou and He, pressure/velocity LBM boundaries](https://arxiv.org/abs/comp-gas/9611001): non-equilibrium reconstruction and channel/duct verification; a candidate starting point, not proof of high-Re reversing-boundary suitability.
- [OpenFOAM boundary guide](https://doc.cfd.direct/openfoam/user-guide-v6/boundaries): separation of patches and field boundary conditions, including mixed/open workflows. Physical concepts transfer; finite-volume formulas are not drop-in LBM updates.
- [OpenFOAM atmospheric boundary-layer model](https://cpp.openfoam.org/v12/classFoam_1_1atmBoundaryLayer.html): linked velocity and turbulence profiles parameterised by roughness and reference height. Its k/epsilon fields belong to the model it defines, not every LES model.

- [Guo–Zheng–Shi non-equilibrium extrapolation](https://cpb.iphy.ac.cn/en/article/doi/10.1088/1009-1963/11/4/310): a second velocity/pressure reconstruction candidate for comparison before selection.
- [OpenFOAM Smagorinsky source](https://cpp.openfoam.org/dev/Smagorinsky_8C_source.html): official reference for strain-dependent eddy-viscosity scaling, used with the local code derivation above.
- [PALM nested LES workflow](https://docs.palm-model.org/25.10.1/Guide/LES_Model/Modules/Nesting/self_nesting/): established nested-domain architecture; a workflow reference, not a Hawa implementation or performance claim.

Reviewers: main Codex agent (code/architecture audit and CPU composition
reproduction) and the explicitly requested computational-physics sub-agent
(independent source/code assessment; findings incorporated with attribution).
G0/G1 planning review: PASS for scoped claims and contracts. G2/G3 implementation
release gates: BLOCKED by the reproduced composition defect and unqualified
boundary/model combinations. G4/G5: NOT APPLICABLE to this documentation-only
scope. No Rhino session or new release was run for this assessment. Model choices,
quantitative acceptance tolerances and implementation estimates remain to be
finalised at the start of the corresponding milestone.
