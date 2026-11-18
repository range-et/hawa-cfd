# CPU wing sensitivity diagnosis — #40

Declared November 17, 2026 before diagnostic solves. Follow-up to the failed
[original screen](wing-cpu-sensitivity-protocol.md); its criteria and evidence
remain unchanged. Operator: Codex root. This diagnoses the synthetic coarse
workflow; it does not qualify physical loads or replace a convergence study.

## Questions and controls

1. Is the domain difference mainly an early-time effect? Run the base and enlarged
   domains through source step 4880; compare identical 81-sample windows starting
   at 1200, 2400 and 4800. Do not compare unequal physical times.
2. Which face placement matters? Move inlet, outlet, lateral faces and vertical
   faces separately, with the same world mesh, fluid, references, lattice spacing
   and source windows. Verify each aligned-domain variant has exactly the same
   world solid-node set before solving. A discrepancy stops that comparison.
3. Does coarse geometry sampling materially change loads? Shift the vertical
   lattice origin by plus/minus half a cell while holding the world mesh fixed.
   The two phase variants sample the same world solid-node set but place vertical
   domain faces 0.025 m apart. Their difference estimates that small boundary
   placement confound; comparison with base includes both sampling and placement.
   These are diagnostic perturbations, not grid refinement or a repaired recipe.

The initial geometry-only audit found voxel-volume errors of -16.13%, -3.77%
and +6.78% for the existing coarse/medium/fine grids. Coarse solid nodes occupy
only two Z planes. Volume here means solid-node count times dx cubed; it is a
sampling proxy, not the exact hydrodynamic bounce-back body volume. Quantify
mesh tetrahedral volume/centroid, voxel proxy volume/centroid, bounding boxes,
node counts and world-mask identities; do not infer force error directly from
volume error. Mesh geometry remains identical across variants.

## Frozen diagnostic cases

Use the original NACA2418/0018 mesh, angle +3 degrees, speed/density 1, viscosity
0.01 m2/s, Mach 0.03, dx 0.025 m, BGK full-way CPU float32. Same area/chord/axes,
probe [-0.1,0,0.1] m, 0.05 coefficient stationarity diagnostic and fresh private
Sessions. Use one OMP/MKL thread at reduced priority; runs are serial. Per-run
cooperative timeout 600 s. Retain all 4881 source observations, source identities,
quality, raw histories and final zero-resource audits. No geometry or physics
production changes during this study.

| Variant | Shape | Origin (m) | Purpose |
| --- | --- | --- | --- |
| base |33,41,25|-.2,-.5,-.2|Extended baseline |
| all-faces |49,49,33|-.4,-.6,-.3|Extended original larger domain |
| inlet |41,41,25|-.4,-.5,-.2|Move inlet only by -.2 m |
| outlet |41,41,25|-.2,-.5,-.2|Move outlet only by +.2 m |
| lateral |33,49,25|-.2,-.6,-.2|Move both Y faces outward .1 m |
| vertical |33,41,33|-.2,-.5,-.3|Move both Z faces outward .1 m |
| phase-plus |33,41,25|-.2,-.5,-.1875|Half-cell Z sampling offset |
| phase-minus |33,41,25|-.2,-.5,-.2125|Same offset sampling, shifted faces |

Re-summarize each retained history at 1200..1280, 2400..2480 and 4800..4880 using
the production measurement contract, preserving raw quality and invalid/rejected
states. All windows use dt=0.03*0.025/sqrt(3) seconds. Compare means, variability,
drift and source provenance. A completed final window does not make earlier
rejected windows usable. Confirm original prefix-window reproduction against the
previous evidence before attributing differences.

Use the original absolute CL change 0.02 and relative CD change 5% as fixed
reporting screens; do not select new acceptance limits after seeing results.
Report each controlled delta, not additive percentages of an assumed linear
response. Even if late-time or individual-face differences shrink, the original
screen stays failed and the reference/continuum qualification remains open.
Unexpected exceptions, quality rejection, changed source, mask mismatch or
unreleased resources invalidate the affected diagnostic comparison.
