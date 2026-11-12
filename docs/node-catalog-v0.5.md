# Hawa 0.5 product-boundary audit

The parametric hull was an example recipe incorrectly promoted to public API.
It is removed from the Hawa toolbar. Example 10 now contains ordinary Grasshopper
expressions, point/mesh construction, volume measurement, nonuniform scaling and
translation. Users can replace that geometry without changing the CFD workflow.
Three shape variations are compared with the archived construction before migration.

A hidden archive reader retains the old component GUID so existing user files,
including legacy 09, can open without losing their object data. It emits a migration
warning. It is not a new-node option or a dependency of a supported example. No
user-owned legacy file is regenerated. The old Galapagos generator now refuses to
run. The maintained inventory is 46 public components plus one archive reader.

## Catalogue decisions

| Family | Components | Decision and boundary |
| --- | --- | --- |
| Setup and coupling | Runtime, Linked Case | Keep: runtime capability and shared-case ownership. Linked Case supports block and selected geometry; its old block-only description is corrected. |
| Domain and geometry | Domain, Wind Tunnel, Domain Preview, Geometry, Geometry Check, Grid Preview | Keep: reusable discretization, validation and inspection of user geometry. No design-specific shape generation. |
| Physical case | Physics, Boundaries, Case, Check Case | Keep: explicit physical settings and supported combinations. |
| Verification | Example | Keep as a clearly labelled numerical verification-case factory: analytic/reference cases, not design recipes. |
| Motion | Translation, Rotation, Oscillation, Moving Body, Motion Case | Keep: prescribed rigid-body kinematics and solver preparation. They do not solve body dynamics. |
| Execution | Solve, Refined Solve, Evaluate, Motion Evaluate, Search | Keep with explicit contracts. Evaluate computes a specific stationary X-resistance objective normalized by V^(2/3); its description now states this. It is not a generic objective or an area-based Cd. Motion Evaluate measures complete cycles. Search consumes completed candidate IDs. |
| Results and files | Field Snapshot, Body Loads, Sample, Checkpoint | Keep: shared field/time, physical loads, sampling and persistence. |
| Display | Slice, Vectors, Streamlines, Seed Points, Color Map, Plane Field, Isosurface, Flow Display, Surface Field, Legend | Keep for compatibility; the simple slice/streamline nodes overlap the richer snapshot-based views. Prefer shared snapshots for multi-view comparison. Consolidation needs explicit migration, not silent removal. |
| Recording | Record, Playback, Body Preview | Keep: time-indexed data and consistent field/body display. Particles was removed by owner decision (November 2026); a hidden stub only opens old definitions. |
| Requested aerodynamic service | Airfoil, Polar Data, Wing, Wing Analysis | Keep within the explicitly requested offline airfoil/polar and lifting-line workflow. Wing is its constrained unswept/tapered geometry input, not a general aircraft modeller. No live database calls or implied viscous drag prediction. |
| Example recipe | Parametric Hull | Remove from public catalogue; replace its supported-example use with native GH construction. Preserve hidden archive loading only. |

## What the previous checks did and did not establish

The earlier smoke tests established that existing graphs ran. They did not decide
whether every component belonged in the product. The product-boundary gate now
precedes API promotion. The live UI pass also found tiny inherited guide fonts;
native examples now set their typography explicitly and preserve their IDs/wires.

The current native panel is a stationary, single-fluid setup editor with scalar
slices. Motion, search, recording and richer visualization remain GH workflows.
It is not a universal native replacement for the GH toolset. First dependency
initialization is synchronous. The existing selected-case slider contract requires
covering the supported parameter range; narrow slider capability negotiation is
not implemented. These limits must remain visible in the user guide.

The numerical suite, host lifecycle checks and workflow runs are evidence for
specific claims. They are not experimental validation, convergence studies, all
possible GH combinations, or proof that an arbitrary optimization is meaningful.
Windows, CUDA and clean-install gates require their own environments. Known
PorousMedium parity remains unresolved.

## Promotion rule

Before adding a public node, state its reusable operation, input/output contract,
units, supported physics, lifecycle and independent verification. First try an
ordinary GH assembly for example-specific geometry or orchestration. Preserve
existing archives through explicit migration and compatibility readers. Verify
both the catalogue and the actual shipped definitions; hiding an icon alone does
not remove an example's dependency on a component.

## Post-0.5 development additions

Boundary Capture and Boundary Data are reusable offline data-transfer operations;
Result Quality exposes the worker's numerical-envelope report. All three have
dedicated icons. See [scope and contracts](boundary-transfer.md). Their example
uses ordinary GH block/domain geometry. These additions are not part of the frozen
0.5 package or an atmospheric capability claim.

## Boundary foundation development additions

`Boundary Patch` describes a reusable physical face condition. `Boundary Set`
compiles six patches onto a case in a worker. Both have toolbar icons. They are
solver/data operations, not application-specific geometry generators. Existing
`Boundaries` keeps its legacy archive contract. Physics accepts the explicit
`smagorinsky-v1` model; `smagorinsky` retains upstream behavior.
See [the boundary guide](general-boundaries.md) for exact supported combinations.

### Experimental neutral precursor (development only)

Hawa Neutral Precursor is a reusable periodic-channel numerical service under
Physics. It accepts a physical Case, reference height, aerodynamic roughness, Cs
and initial disturbance. It requires explicit experimental opt-in and excludes
obstacles/open boundaries/refinement. Quality blocks transfer until atmospheric
qualification. Examples 28–29 assemble existing Domain, Physics, Case, Solve and
visualisation nodes. See [verification and limits](neutral-precursor-review.md).

Neutral development update: **Hawa Neutral Flow** retains the Neutral Precursor
GUID and old ports. New optional inputs specify a wall sampling plane, filter time
and six external patches. Empty patches retain precursor mode. External mode
accepts halo-classified stationary buildings and uniform/neutral face profiles.
See [the coupling contract](neutral-coupling-review.md). This is a reusable model
operation; example 30's buildings are ordinary Grasshopper geometry.


### Atmospheric transfer and shared views (development)

The current public inventory is 54 reusable operations. Wall Roughness attaches
bounded spatial roughness regions to a physical case. Flow Statistics evaluates
recorded probe histories with means, covariance, spectra and sampling diagnostics.
They are used in annotated example 33; city, neighbourhood and pond are tutorial
stages, not public component types.

Boundary Capture appends start/end physical-time inputs. Boundary Patch appends
an explicit backflow mode; old archives keep velocity mode. BoundarySeries v2
carries velocity, pressure, strain and initial state on all active exterior faces.
Neutral external mode can consume it with explicit experimental opt-in. Precursor
mode and unsupported compositions still reject. Numerical qualification remains open.

Plane Field, Flow Display, Isosurface and Surface Field retain their GUIDs and
change Frame to a list input. Existing single-frame wires remain valid. They use
same-time immutable frames, finest-domain priority and physical transforms. Slice
triangles are clipped at halfway solid boundaries; derivative fields and curved
links retain conservative validity. The legacy live Slice/Streamlines components
retain their session contracts. No case-combiner recipe node was introduced.
