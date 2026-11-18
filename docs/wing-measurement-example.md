# Blended-wing measurement example — headless recipe

Status: geometry and candidate preparation only, November 17, 2026. This is the
example lane of [#40](https://github.com/range-et/hawa-cfd/issues/40), built against
the [frozen measurement contract](measurement-contract-v1.md). No CFD results,
GH archive, host execution or aerodynamic qualification are supplied here.

## Reproducible geometry

The example-only [recipe](../scripts/wing_measurement_recipe.py) calls Hawa's
existing offline NACA generator with two four-digit section strings. Its default
is root 2412, tip 0012, full span 1.2 m, root chord 0.3 m and tip chord 0.2 m.
It matches the cosine-index upper/lower section samples, interpolates shape and
chord linearly with distance from the centerline, and aligns quarter-chords.
Nine full-span sections include the root. The output is an indexed triangular
mesh with welded trailing/leading edges and chordwise-triangulated square tips.
The topology tests establish a closed consistently oriented two-manifold; they
do not certify arbitrary NACA inputs against CAD self-intersection or thin-cell
resolution. Use the existing Geometry Check and grid inspection before solving.

`wing_mesh(...)` returns vertices/sections in metres, triangle indices, volume,
SHA-256 mesh identity and transform provenance. It allows odd section counts
21–401 and odd span-station counts 3–65, and dimensions 1e-6–1e6 m. These are
recipe bounds, not a claim those scales are numerically resolvable. No twist,
sweep or dihedral is implemented in this first recipe.

The fixed planform reference area is `span*(root_chord+tip_chord)/2`; the reference
chord is the analytic mean aerodynamic chord of that trapezoid. Rotating the
wing does not change either reference. Wind is +X, span +Y, up +Z. Positive
angle uses right-handed +Y rotation about the root quarter-chord by default:
leading edge rises relative to trailing edge. A user pivot may be supplied.

```python
from scripts.wing_measurement_recipe import sweep_recipe
study = sweep_recipe(
    {'root': '2412', 'tip': '0012'},
    [{'angle_deg': a, 'speed_m_s': 3.0} for a in [-2., 0., 2., 4.]],
    {'density': 1.225, 'viscosity': 1.5e-5,
     'purpose': 'geometry preparation only; domain/grid not yet admitted'})
```

Run from the repository root with its `.venv/bin/python`; no solver is called.
The example air properties do not establish a viable grid. `sweep_recipe` accepts
an ordered list of 1–64 angle/speed pairs and returns distinct candidate IDs,
actual meshes, immutable copied settings and `run=False`. Repeated conditions
retain separate IDs. Geometry hashes change when rotated vertices change; speed
or settings change the candidate's preflight case hash. This hash is explicitly
**not the final solver case hash**: the production adapter must voxelize each
transformed mesh, assemble the exact case and replace `case_hash` with that
case's authoritative hash before measurement. Nothing here should be submitted
as a completed run or used to synthesize a CL/CD point.

## Ordinary Grasshopper assembly to implement after host handoff

1. Use existing Airfoil components for root/tip profiles and the same point count.
2. Scale profile coordinates to chord, align their quarter-chords, place mirrored
   tip stations, and interpolate ordinary section curves between them.
3. Loft the sections, cap the tips, mesh, then use Geometry Check and Grid Preview.
   Inspect topology, outward normals and resolved thickness. The headless indexed
   recipe provides a correspondence/reference, not a guarantee Rhino's mesher
   produces the identical discretization.
4. Rotate a fresh wing about the declared spanwise pivot for each sweep angle.
   Keep the domain/inlet orientation fixed and validate clearance at every angle.
5. Connect the future #40 measurement/sweep adapters, using one body ID for the
   whole wing, explicit reference area/chord and pressure-probe positions.
6. Plot only accepted, completed measurements. A click must retain candidate ID
   and field identity; failed, rejected and incomplete points leave visible gaps.
   Use #35's eventual interchange adapter for export; this recipe writes no CSV.
7. Save disabled, reopen idle, then test pause/cancel/failure and document teardown
   after the debugging chat releases Rhino. No archive or public node is added
   in this headless increment. Existing examples, including legacy 09, are intact.

## Numerical reference assessment and next gate

The primary source [NACA RM L52G18, Jones, 1952](https://ntrs.nasa.gov/api/citations/19930087204/downloads/19930087204.pdf)
was inspected on November 17, 2026. Pages 2–4 describe NACA0012 rectangular wings
with square tips, AR 1/2/3, and Reynolds numbers 0.4–3 million. The AR2/3 spans
are 20 inches; AR1 span is 14 inches. Lift/moment include support interference,
while tunnel-wall corrections were applied. The published curves are lift and
pitching moment, not a drag polar. At Re 0.4 million, the reported Mach numbers
are 0.20, 0.28 and 0.21 respectively. Thus this is a candidate for a matched
lift/moment study, **not the current CL/CD acceptance reference**. The scan has
not been digitized. No figure or table is redistributed; retain NACA attribution
and confirm NTRS reuse terms before packaging digitized data.

A higher-Re row has lower Mach, but that does not solve the unresolved boundary-
layer/transition and full-way-wall grid requirements. Raising viscosity to fit
the original 150000-cell limit (now 500000 after a bounded CPU resource pilot) would change the experiment. A bare blended wing
also differs from these supported rectangular test models. The wing numerical
gate is BLOCKED pending selection of a matched lift/drag dataset and a budgeted
resolution/transition method. No comparison thresholds or experimental accuracy
are manufactured from these geometry tests. Before a reference run: freeze the
actual geometry/support treatment, Re/Mach and transition assumptions, digitized
source/error bounds, grid/domain/time variants and observable-specific tolerances.
If infeasible, retain the numerical blocker under #15 rather than silently
qualifying the software demonstration.

For an independent simple load reference, [Cambridge's Stokes-flow derivation](https://www.damtp.cam.ac.uk/user/examples/D23Ld.pdf)
gives the isolated creeping-flow sphere drag `6*pi*mu*R*U`. This is a candidate
force check, not a finite-box exact answer. A sphere at Re_D=0.01 with radii
resolved by 4/6/8 cells and outer distances 10/20/40 radii would separate grid and
boundary effects, but the largest uniform box at R/dx=8 requires roughly 640³
cells, far above both the original 150000-cell cap and current 500000-cell cap. Therefore the unbounded Stokes
qualification is also BLOCKED for this restricted collector; do not relax that
cap or accept a small-box result as an unbounded reference. A later scoped study
may select an independently solved finite-domain reference or a separately
approved collector/resource extension and fix criteria before measurement.

What is feasible now is the bounded manufactured load/transform suite in the
measurement contract: exact coefficient algebra, moment translation, independent
link sums and signed force symmetry. Those establish implementation properties;
they do not replace a matched 3D wing drag experiment.
