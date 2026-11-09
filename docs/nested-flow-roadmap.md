# Nested flow studies: city → neighbourhood → pond

Implementation tracking: [neutral atmosphere and rough-wall delivery record](atmosphere-delivery.md).
The complete feature set is authorised; the record distinguishes implemented
utilities from the remaining solver, validation and host-delivery gates.

Proposed scope, November 8, 2026. No implementation or release date is claimed.
This extends the [roadmap](roadmap.md) and its user-defined refinement regions.
The first delivery uses separate uniform grids with offline, one-way boundary
transfer. Multi-level grids follow as a separate numerical workstream.

## Current evidence and study boundary

Local inspection of `src/hawa/plugin.py` confirms a uniform X- inlet/X+ outlet,
FP32 physical solver, two-million-cell limit plus memory preflight, a relaxation
margin check, and rejection of solids touching inlet/outlet. `refinement.py`
requires one 2:1 BGK patch and excludes curved-wall links and moving bodies; its
interface stencil must stay away from solids. `recording.py` provides bounded
field recordings, but no imported boundary-condition contract.

Smagorinsky is already selectable. Its presence does not establish atmospheric
validation or a suitable wall model. The production session checks finite
populations and positive density and tracks mass change; its completion flag is
not a numerical-quality assessment. The user's reported pilot maximum lattice
Mach of about 0.46 has not been independently reproduced here. It exceeds the
current input Mach limit of 0.15, which does not constrain local accelerated flow.

For this first study, interpret “pond” as airflow over a prescribed stationary
water-surface boundary. Choose and document that boundary treatment. Resolving
water currents, waves, wind-driven water motion or air/water stress coupling needs
additional physics and separate validation. Neutral atmospheric flow is the first
candidate regime; stable/unstable thermal stratification stays outside it.

## Proposed node contracts

Names are provisional. Reuse existing nodes where an added input or output gives
a clear contract. Buildings, neighbourhoods and ponds remain example geometry.

| Family / operation | Inputs → outputs | Scope |
| --- | --- | --- |
| Results: Boundary Capture | Parent recording or active recorder, target boundary planes, time window and cadence → immutable boundary dataset | Sample vector velocity in physical units; include coverage and fluid/solid validity. Extend Record to write boundary-only data during runs. |
| Files: Boundary Data | Dataset path → validated boundary-series handle and metadata | Versioned local format first; bounded lazy reads, checksums, units, times and incomplete-file rejection. External formats get explicit adapters later. |
| Coupling: Map Boundary | Boundary series, child domain/faces, coordinate transform, time offset and mapping policy → mapped boundary specification plus report | Rotate vectors as well as points; quantify coverage, flux error, resolution and time sampling. |
| Setup: Boundaries (extend) | Mapped boundary specification plus supported outlet/wall settings → boundary set | Begin with planar X- spatial/time-varying velocity and X+ outlet. Reject unsupported backflow, other incoming faces and solid intersections explicitly. |
| Verification: Result Quality | Case/run or recording, versioned quality policy and intended use → time history, status and reasons | Shared engine assessment also shown directly in Solve, native panel, exports and transfer validation. Optional node exposes the report; safety must not depend on wiring it. |
| Setup: Atmosphere | Reference wind vector/height, roughness, ground datum and supported neutral-flow model → physical profile/model specification | Include compatible turbulence quantities and wall treatment; release only after model qualification. Do not make it a cosmetic speed-profile node. |
| Geometry: Geometry Check / Grid Preview (extend) | Bodies and child domain → boundary intersections, open-area masks, cell classifications and preview | First flag unsupported cuts; later support mixed solid/fluid boundary faces with tested wall precedence. |
| Grid: Refinement Region / Refinement Plan / Generate Grid | Base grid and regional factors → supported hierarchy and preparation report | Follow the refinement roadmap; qualify ground/water/building contacts separately. |
| Setup: Check Case / Runtime (extend) | Case and device capabilities → estimated peak memory, cell budget and supported combinations | Account for all levels, halo/storage, mapping cache, recording and display copies. Raising a cap requires measured capacity. |

No separate city, pond or nesting-solver node is needed. Existing Case, Solve,
Record, Sample, field views and public case operations assemble these services.

## Transfer data and ownership

A BoundarySeries manifest records schema version, content hash, source case and
physics revision, run generation, engine/model/device/precision, physical units,
world origin/basis, face normals, sample layout/areas, monotonic physical times,
vector velocity, validity/solid masks, sampling method and source quality report.
Tag data as instantaneous, averaged or statistical; averaging cannot preserve an
unsteady wake. Store optional pressure with its reference and turbulence fields
with their model definitions. Do not prescribe velocity and pressure together on
the same patch without a boundary formulation that supports those constraints.

Map in physical coordinates and seconds, then convert to the child's lattice
units. Equal iteration numbers are not equal physical times. Interpolate only
valid fluid samples; do not bridge buildings or fill missing coverage with zeros.
Report normal flux before and after mapping. Any conservative correction must be
explicit, bounded, measured and justified; arbitrary vector rescaling is unsafe.
Use anti-alias filtering when reducing resolution and verify its effect on wakes.
Reject spatial extrapolation and out-of-range time by default. Holding or looping
frames requires an explicit, labelled policy and compatible endpoint behavior.

First support offline, immutable datasets. A completed dataset feeds a child;
parent and child need not run concurrently. A changed parent invalidates derived
mapping and dependent child results. Use an acyclic dependency graph, content
hashes and existing case/revision/generation ownership. Background workers own
mapping and IO; bounded caches, cancellation and existing poll callbacks keep GH
and Rhino responsive. Save/reopen retains paths/hashes and reports missing data;
it does not auto-run or silently rebind to another file. Native, GH and agent
operations share these contracts. No live bidirectional coupling is implied.

## Example workflow

1. Prepare a city case with a qualified neutral atmospheric model, boundaries and
   resource budget. Start with quality diagnostics active.
2. Place the neighbourhood domain inside parent coverage, with sufficient upstream
   and lateral margins. Capture data on the child's intended boundary location,
   which need not be the parent's outlet. Inspect masks and incoming normal flow.
3. Read and map the series to the neighbourhood's independent uniform grid. Check
   physical-time coverage, flux, source quality and geometry consistency. Run after
   parent settling; allow the child its own spin-up and exclude it from statistics.
4. Repeat neighbourhood → whole-pond. Use the same world geometry and datum while
   resolving more detail locally. Fine grids cannot recover fluctuations absent
   from the parent data; qualify missing-scale turbulence treatment separately.
5. Compare overlapping probes, mean/profile and time-history measures, pressure
   reference, conservation and resolution sensitivity at matching physical times.
   Animate all stages on the same physical clock and show quality status.

The first inlet-only implementation supports aligned, predominantly one-way flow
with clear inlet/outlet faces. A child with significant side/top inflow, reversing
flow or buildings crossing its boundary must be rejected until the broader open
boundary formulation is verified. Simply adding a mapped inlet does not make every
urban crop valid. Keep parent buffers and perform boundary-placement studies.

## Result quality comes first

Keep job status (`running`, `completed`, `cancelled`, `failed`) separate from
quality (`unchecked`, `within-tested-envelope`, `warning`, `rejected`). Passing
numerical diagnostics does not establish physical validation. Preserve both
states in recordings and mapped data. Block rejected/unchecked source datasets
from normal production chaining; allow explicit diagnostic inspection without
presenting those results as qualified wind predictions.

Track fluid-cell maximum and percentile lattice Mach, exceedance count/location,
density deviation, finite/positive state, relaxation margin, boundary flux and
mass-storage balance, boundary backflow, probe settling and statistical duration.
For open domains, total mass change alone is not a conservation residual: include
net boundary flux. Declare diagnostic cadence and do not imply that sampled
maxima bound unsampled steps. Preflight imported maximum velocity; monitor actual
flow acceleration during runs. A versioned policy sets thresholds for the tested
model, with explicit stop or pause on hard failures and recoverable UI state.

Treat the reported 0.46 pilot as outside the current low-Mach operating envelope,
retaining its fields for diagnosis. Lower reference lattice Mach may help local
Mach but also reduces the relaxation margin at fixed physical viscosity and grid;
check both together. Do not bypass the margin check, inflate molecular viscosity
without changing the declared physical case, or assume FP64 alone supplies missing
turbulence/wall physics. Device precision support must be tested.

## Delivery order and acceptance

| Stage | Work | Gate before claiming support |
| --- | --- | --- |
| 0 Quality | Shared quality report, transfer eligibility and diagnostic UI | Reproduce a finite but over-limit case; completed/rejected shown together; reports survive export/reload; cancellation and stale results checked. |
| 1 Boundary transfer MVP | Versioned BoundarySeries, planar mapped vector inlet, steady then unsteady input | Uniform regression; analytic spatial/time profiles; rotated vectors; physical-unit/time conversion; flux/error tolerances set before runs; no missing/masked interpolation; CPU/MPS and available CUDA comparisons. |
| 2 Atmospheric qualification | Choose collision/SGS and compatible rough-wall model; neutral inflow and timestep scaling | Empty-domain profile preservation, wall/roughness checks, relevant building/wake references and resolution/time/domain studies at stated Reynolds regimes. Compare an established engine if the embedded path cannot meet the envelope. |
| 3 General child boundaries | Mixed solid/open masks, side/top inflow and backflow-capable boundaries | Building cut and corner tests, zero solid leakage, flux balance, no duplicate boundary assignment, parent/child geometry consistency and boundary-placement studies. Keep unsupported shapes rejected. |
| 4 Multi-level and capacity | Wall-contact refinement, block storage and measured budgets | Interface conservation and error versus uniform reference; ground/water/building contacts; per-device memory/performance and cancellation. Evaluate larger dense budgets separately from sparse storage. |
| 5 Study examples | City → neighbourhood → pond; entrance and water-adjacent refinement comparisons | Annotated GH files and public agent recipes, matching-time animation, quality overlays, reproducible reports and explicit study limitations. |

Stages 0–1 enable a bounded transfer demonstration. Useful urban results additionally
require stage 2 and whichever stage-3 capabilities the geometry demands. Multi-level
refinement is not a prerequisite for the three-uniform-grid pilot. One-way transfer
has no feedback from child to parent; study overlap and boundary placement.

Block-structured storage and multi-level stepping are related but separate tasks.
Sparse storage alone does not remove unresolved flow physics or guarantee speedup.
Custom graded volume-mesh import remains a separate capability: require a supported
structured/block schema for LBM, or route arbitrary unstructured connectivity to a
future compatible solver adapter. Do not interpret an imported surface mesh as a
volume simulation grid.

## References and review

Read November 8, 2026: OpenFOAM documents
[timeVaryingMappedFixedValue](https://doc.openfoam.com/2306/tools/processing/boundary-conditions/rtm/derived/inlet/timeVaryingMappedFixedValue/)
for space/time interpolation of supplied boundary values. This is a useful format
and behavior reference; the Hawa LBM boundary reconstruction still needs its own
verification. The [atmospheric boundary-layer API](https://cpp.openfoam.org/v12/classFoam_1_1atmBoundaryLayer.html)
connects velocity and turbulence profiles. The
[neutral atmospheric omega boundary](https://doc.openfoam.com/2306/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmBoundaryLayerInletOmega/)
states its equilibrium, neutral-flow scope. These references support scoped design;
they do not validate Hawa. No external code or dependency is added.

Documentation self-review by Codex: G0 PASS for traceable scope/references; G1 PASS
for proposed contracts and lifecycle; G2 PASS for documentation links/diff checks;
G3 PASS for explicit numerical gates and limits, with no new physics claim; G4 PASS
for proposed workflow/error states, with no executed UI claim; G5 NOT APPLICABLE
because no release is being made. These decisions cover planning only. Numerical,
unit, device and Rhino tests were not run for this documentation change. The pilot
Mach value is user-supplied evidence. Implementation ownership and dates remain
unassigned; each stage requires execution of its gates before release.
