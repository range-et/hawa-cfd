# Bounded CPU wing sensitivity protocol — #40

Frozen before measurements on November 17, 2026, by Codex root. This is a
sensitivity screen for the existing synthetic-viscosity workflow, not a physical
wing benchmark. It does not replace the blocked matched experimental reference
in [the wing guide](wing-measurement-example.md). No Rhino, export, MPS or CUDA.

Use the same NACA2418/0018 closed mesh as the headless demo: full span 0.6 m,
root/tip chords 0.3/0.2 m, 41 section points, 5 span stations, angle +3°, speed 1 m/s,
rho 1 kg/m³, kinematic viscosity 0.01 m²/s, lattice Mach 0.03. Reference area and
MAC stay fixed. Full-way BGK, CPU float32, one OMP/MKL thread. Probe at
[-0.1,0,0.1] m. All cases must use fresh Sessions and final voxelized case hashes.

The base timestep is `dt0 = 0.03*0.025/sqrt(3)` seconds. Source indices are
pre-stream: a run ending at source index N requires N+1 advances. Compare
**equal physical windows**, not equal step counts, across grids.

| Variant | dx (m) | Shape | Origin (m) | Settling steps | Samples | Source window / dt0 |
| --- | --- | --- | --- | --- | --- | --- |
| grid-coarse |0.025|33×41×25|[-0.2,-0.5,-0.2]|1200|81|1200…1280|
| grid-medium |0.02|41×51×31|same|1500|101|1200…1280|
| grid-fine |1/60|49×61×37|same|1800|121|1200…1280|
| domain-large |0.025|49×49×33|[-0.4,-0.6,-0.3]|1200|81|1200…1280|
| settling-long |0.025|33×41×25|base|2400|81|2400…2480|
| averaging-long |0.025|33×41×25|base|1200|161|1200…1360|

The first three have identical physical extents; only lattice spacing changes.
The larger domain moves all six faces away from the same world geometry. Its
body/probe positions remain unchanged. Long-settling and long-averaging variants
change only their stated window. Each grid stays below the frozen 150000-cell
collector cap. These six runs are serial and require a coordinated quiet CPU
window; per-run timeout 600 s requests cooperative cancellation rather than killing
a worker. Keep failure/rejection data and cleanup audits.

## Criteria fixed before execution

1. Every requested case has exactly one attributable terminal record; every
   completed window has accepted solver quality, at least its declared sample
   count, complete equal-time endpoints and the unchanged 0.05 absolute
   coefficient stationarity criterion. All owned workers/handles/sessions drain.
2. Record mean CL/CD, coefficient fluctuations, drift, actual source times,
   session identity, solid-node counts, grid/domain metadata and all hashes.
   Invalid quality/windows are not plotted as successful points or discarded.
3. For the grid screen, both medium→fine changes must be no larger than
   coarse→medium changes (separately for CL/CD). Medium→fine absolute CL change
   must be ≤0.02 and relative CD change ≤5% of |fine CD|. Zero fine CD yields an
   undefined relative comparison, not a pass.
4. For domain, settling and averaging comparisons against coarse, require
   absolute CL change ≤0.02 and relative CD change ≤5% of |coarse CD|. These are
   explicit screening thresholds, not experimental error bars or qualified
   engineering tolerances. A failing screen keeps the numerical gate open;
   do not change thresholds or silently substitute a longer/bigger run.

Passing only means insensitivity to these bounded variants. It is not an
asymptotic convergence proof, accuracy against experiment, real-air Reynolds
number support or a device comparison. A failure is evidence about the coarse
workflow, not automatically a solver implementation defect. Record hypotheses
separately from reproduced defects; no new issue is needed for the already
tracked physical-qualification gap unless a distinct implementation bug appears.

Reproduction uses `scripts.wing_solver_recipe.prepare_sweep`,
`scripts.run_wing_sweep.prepare_entries` and `run_prepared` with the table's
parameters. Keep geometry, fluid, tolerances and physical windows as written;
serialize runs and retain the original observations before deriving differences.
