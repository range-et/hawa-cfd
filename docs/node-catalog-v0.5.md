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
| Recording | Record, Playback, Particles, Body Preview | Keep: time-indexed data and consistent field/body display. |
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
