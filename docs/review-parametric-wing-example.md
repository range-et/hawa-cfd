# Parametric wing example — geometry and integration review

November 17, 2026. Geometry/example author and source reviewer:
Codex `examples_review` agent. Live geometry operator: Codex root via Rhino MCP.
Root owns the installed Study adapter, final archive, UI/solver acceptance,
coverage matrices, combined tests, CI and merge decisions.

## Product boundary

The example uses existing Airfoil nodes for distinct root/tip NACA sections and
ordinary Grasshopper expressions, vectors, Move, Loft, Cap Holes Ex, Mesh Brep,
Mesh Join, Weld and Mesh Unify Normals. No new Hawa wing-geometry component is
introduced. The capped solid and resulting closed mesh are actual graph data;
there is no precomputed replacement wing hidden in the study.

Quarter-chords align at root chord/4. Planform area and MAC are analytic,
angle-independent expression outputs. The separate Stationary Study receives
the mesh, fixed empty-solid domain/fluid case, references, explicit angle/speed
lists and controls. Field display uses the returned selected rotated mesh and
matching snapshot, not the upstream unrotated construction. Surface Field is
offset pressure sampling with invalid samples black. Lift/drag are total
selected-body window means from the study, not local pressure-derived forces.

Three stock-GH scatter plots use returned angle/coefficient lists rather than
the shorter input angle list, preserving cross-product indexing. They do not
join points across rejected candidates. Display-coordinate scaling is separate
from the reported coefficients; axes and units are labelled.

## Fresh geometry evidence

Root executed the generator with `geometryOnly=true` in one transient owned GH
document. Existing Rhino/GH files were not written. All three variants produced
a valid solid Brep and valid closed outward mesh, positive volume and the exact
requested span. The graph changed root/tip codes, chords and span between solves.
The prior GH canvas was restored and the owned document removed/disposed.

| Root / tip | Chords (m) | Span (m) | Mesh vertices / faces | Volume (m³) |
| --- | --- | --- | --- | --- |
| 2418 / 0018 | 0.3 / 0.2 | 0.6 | 3485 / 4694 | 0.005283826501279579 |
| 0012 / 2412 | 0.35 / 0.18 | 0.7 | 5610 / 6724 | 0.005062144002764061 |
| 2418 / 0018 | 0.25 / 0.15 | 0.5 | 4475 / 5499 | 0.002926430487420114 |

Evidence is `results/parametric-wing-geometry/preflight.json` in the example
worktree. This is Rhino geometry execution, not a solver, surface-pressure,
plot, archive or installed Study acceptance pass. The first compile attempt
rejected a local-variable name collision before execution; it was corrected
and the three-variant run above passed. No numerical tolerance was changed.

## Integration checklist still owned by root

- Generate the complete archive after installing the verified Study assembly.
- Check idle opening, closed-solid/mesh outputs and all named port wires.
- Run the scoped annotation/connection check on example 35 only; preserve 09
  and every existing supported archive.
- Inspect actual canvas, selected pressure surface, legend, lift/drag readouts,
  scatter axes and candidate selection. Confirm invalid coefficients remain gaps.
- Exercise geometry edit/re-arm, pause/cancel, selected-case changes, disposal
  and save/reopen, with zero owned workers/sessions/refresh callbacks after cleanup.
- Record package/source identity and update public-node/example G6 mapping.

The existing grid/domain screen fails and the matched physical reference remains
open. Finer sampling and a solid CAD loft are not engineering qualification.
This review does not close #40 or claim CUDA/MPS/Windows host verification.
