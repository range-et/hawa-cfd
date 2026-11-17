# 35 — Editable wing and live CFD study

This example is a Grasshopper workflow in Rhino, not the saved HTML report.
It constructs its geometry with ordinary Grasshopper operations and feeds the
resulting mesh to a separate Hawa study. The airfoil coordinates are generated
offline by the existing Airfoil components; no external polar is substituted
for CFD.

## Build the wing

Use a Rhino document in **metres**. Read the graph left to right:

1. Edit the two NACA text panels. Defaults are **2418 at the root** and
   **0018 at the tips**. Both existing Airfoil nodes return section curves in
   the XZ plane.
2. The **Root chord**, **Tip chord** and **Full span** sliders control the wing
   dimensions; defaults are **0.3 m**, **0.2 m** and **0.6 m**. Tip sections
   move to Y = ±span/2 and X = (root chord − tip chord)/4, aligning their
   quarter-chords with the root.
3. An ordered tip/root/tip curve list feeds **Loft**, **Cap Holes**, **Mesh Brep**,
   **Mesh Join**, **Weld** and **Unify Normals**. These are stock Grasshopper
   components. Their output is the actual body passed to the solver. You can
   inspect the sections, replace the loft, or connect your own closed mesh.
4. **Geometry Check** must report accepted, closed geometry before a study.
   Its cells-across-bounds report is a coarse resolution aid; it cannot certify
   a resolved boundary layer or internal thin features.

Planform area is span × (root chord + tip chord)/2. The mean aerodynamic chord
is 2 × (root² + root × tip + tip²)/(3 × (root + tip)). These ordinary expression
nodes keep references fixed while the study rotates the same wing about the
root quarter-chord at (root chord/4, 0, 0). Do not replace planform area with
angle-dependent projected frontal area.

## Run and inspect

The file starts with run controls off. Initialize the Hawa runtime when needed,
wait for geometry admission, then explicitly start the study. Each angle/speed
entry owns a fresh simulation. Pause/cancel must acknowledge cooperatively;
changing geometry or physical settings invalidates the prior study rather than
silently attaching its results to the new wing.

The shipped grid uses **0.01 m cells** in a fixed **0.8 × 1 × 0.6 m** tunnel:
**81 × 101 × 61 = 499,041 nodes**. The study cap is 500,000 per case. Smaller
cells or a larger domain can exceed it and must reject before solver allocation.
The default **−3° and +3°** cases run sequentially at **1 m/s**, with 3,000
settling steps and 201 samples each. This is substantial CPU work, not an
instant preview. Use Pause or Cancel rather than closing Rhino forcibly.
The stationarity criterion remains 0.05 absolute coefficient change; do not
increase it just to obtain a plotted result.

Use **Selected case index** to inspect the matching rotated mesh and captured
field; changing the selection does not rerun the cases. The **Cases** panel
keeps the ordered identity and status of every requested case. If you add
angles or speeds, expand the selection slider's upper bound to the last case
index. Speeds and angles form a cross product; returned Angles and Speeds stay
aligned with the coefficients.

The three ordinary GH scatter plots show **CL versus angle**, **CD versus angle**
and **CL versus CD** in the Rhino viewport below the tunnel. Their axes are
labelled; display scaling does not alter the reported numbers. Points are not
joined into an interpolated curve. Failed/rejected candidates retain their case
records and empty coefficient slots, rather than invented zeros.

The **Total lift** and **Total drag** panels show the selected accepted window's
whole-body fluid force in **newtons**: +Z is lift and +X is drag. The moment
vector is in N m about the supplied root quarter-chord pivot. These integrated
loads come from the solver's momentum exchange; they are not summed pressure
colours. Coefficients use the fixed area/chord and the declared physical window.

**Surface Field** samples pressure outside the selected rotated wing along its
normals, initially at **1.5 cells** offset. Its colours and the fixed **−2 to +2
Pa** legend are approximate sampled pressure. **Black means an invalid sample**;
the validity panel makes this explicit. Change the pressure-colour sliders to
inspect the display without changing the solver. This is not a local surface
force/load-cell result. Turn off preview of the upstream **Actual closed wing
mesh** parameter after running if its unrotated construction preview overlaps
the selected pressure surface.

Solver progress and captured field time are different quantities. Reopening
the definition stays idle. Set Run off and explicitly re-arm after edits or a
reopen; never interpret old selected-case outputs as a new wing's result.

## Scope and interpretation

This is an experimental stationary uniform-grid CPU workflow with synthetic
viscosity. The geometry has a coarse full-way wall representation. Finer cells
improve geometry sampling but do not, by themselves, establish domain
independence, convergence or agreement with physical loads. The existing
grid/domain sensitivity failure and matched-reference gap remain tracked in
[#40](https://github.com/range-et/hawa-cfd/issues/40).

The two section codes genuinely differ. This graph is an example construction,
not a new public Hawa wing geometry operation. Existing Wing Analysis results
remain a separate lifting-line method and are not used here. General stall,
viscous boundary-layer and engineering-load qualification are not claimed.

Save changes as a new `.gh` file. Existing examples and user-owned example 09
are not regenerated by the example creator. Maintainer reproduction uses
`scripts/create_parametric_wing_example.cs` through Rhino MCP, followed by the
scoped annotation, connection, save/reopen and live verification checks.

[Measurement contract](../../docs/measurement-contract-v1.md) ·
[Verification matrix](VERIFICATION.md) ·
[Numerical diagnosis](../../docs/review-worker-and-wing-diagnosis.md)
