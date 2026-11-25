# OpenFOAM case handoff and shared-observable verification

Tracking issues: [#126](https://github.com/range-et/hawa-cfd/issues/126) (physical-case
handoff and mesh preparation) and [#127](https://github.com/range-et/hawa-cfd/issues/127)
(cross-solver shared-probe verification and gate).

User intent: run the same SI physical case in Hawa and externally installed
OpenFOAM, then compare velocity at fixed world-space probes, pressure differences
$\Delta p = p(A) - p(B)$ in Pa, and segment-average pressure gradients in Pa/m.
Different discretizations are expected; matching meshes is not the objective.
Agreement with OpenFOAM is **cross-solver verification**, not physical validation.

## Physical-case handoff (#126)

Hawa's `WindFlow.grid` is a regular lattice of sample sites, not an existing
OpenFOAM volume mesh. The handoff bundle (`schema: "hawa-openfoam-case-1"`,
`src/hawa/openfoam.py`, [JSON Schema](schemas/openfoam-case-bundle.schema.json))
captures SI domain bounds, fluid properties, 6-face physical boundary intent
(validated against `boundary_contracts.py`), fixed world-space probe coordinates,
pressure pairs, and meshing/solver controls.

Initial supported scope (Slice 1):
- Stationary, single-fluid, incompressible, isothermal laminar cases in Cartesian
  domains (`velocity`, `pressure`, `wall`, `slip`, `periodic`, plus 2D XY extrusion).
- Parabolic velocity inlets are rendered as exact `nonuniform List<vector>` values
  at `blockMesh` face centers (avoiding deprecated OpenFOAM expression BCs and
  on-the-fly C++ compilation).
- Unsupported features (`moving_bodies`, `refinement_lower`, `neutral_precursor`,
  `boundary_field`, `wall_links`, `solid`, `roughness`, `porous`, `free_surface`,
  `open` faces, `mapped`/`neutral` profiles) fail explicitly before publishing.
- Atomic directory publishing protects existing user output on failure and writes
  SHA-256 digests in `bundle/manifest.json`.

## Cross-solver comparison (#127)

Staged case roadmap:
1. **Slice 1 (Controls — implemented):** Laminar 2D Poiseuille channel (`07`,
   `WindFlow` + `hawa-nee-v1` vs OpenFOAM `simpleFoam`) and lid-driven 2D cavity
   (`06`, `Cavity2D` vs OpenFOAM `simpleFoam`).
2. **Slice 2 (Curved body — planned):** Laminar sphere (`14`) with watertight STL
   export, `snappyHexMesh`, and upstream/side/wake probes.
3. **Slice 3 (Transient separated — planned):** Cylinder wake (`16`) over matched
   physical windows (mean/RMS velocity, pressure drop, shedding frequency).
4. **Slice 4 (Complex geometry — planned):** Native canopy (`22`) or one fixed
   submerged hull candidate (`10`).

Measurement contract:
- Every required probe is defined once in SI world coordinates and interpolated on
  both solvers (OpenFOAM `postProcess -func probes` with `cellPoint`; Hawa exact
  bilinear/trilinear interpolation). Missing, solid, out-of-domain, or non-finite
  probes fail immediately.
- OpenFOAM kinematic pressure $p/\rho$ is multiplied by $\rho$ to obtain Pa before
  computing $\Delta p = p(A) - p(B)$ and segment gradient $(p(B) - p(A)) / \|B - A\|$.
- Steady Hawa channel runs check actual observable settling (velocity + pressure
  drop drift over a trailing check window) rather than assuming a short fixed step
  count.
- Per-probe and per-pair limits are evaluated individually; no average may hide a
  failed required probe.

See [review-openfoam-controls.md](review-openfoam-controls.md) and
[verification-openfoam-controls.json](verification-openfoam-controls.json) for
measured Slice 1 evidence on local OpenFOAM v2606.
