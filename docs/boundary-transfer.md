# Boundary transfer and result quality — development build

This adds a time-varying vector inlet to the existing LBM engine. It changes
solver boundary behavior; it is more than mesh generation. No new numerical
solver, turbulence model, adaptive mesh or atmospheric qualification is included.

## Supported workflow

Open `examples/grasshopper/24-boundary-flow-transfer.gh`. Save a copy. Supply a
new absolute parent recording directory and a new absolute `.npz` boundary path.
Enable **Record parent**, wait for completion, enable **Capture inlet**, wait for
preparation, then enable **Run child**. Existing files are preserved. Reopening
stays idle. Record/Capture false cancels; Solve false pauses and Reset clears.

The parent runs 60 steps at 0.2 m cells and the child runs 120 steps at 0.1 m
cells. Both use U=1 m/s, viscosity=0.1 m²/s and reference lattice Mach=0.03,
covering approximately 0.207846 s. This is a short developing-wake demonstration,
with startup included. It is not a converged wind prediction or an air-viscosity
case. The child inlet lies at X=1.2 m in parent coordinates. The block is upstream
of it; the child has no solids. Change the demonstration geometry using ordinary
GH components, and inspect diagnostics before transfer.

Three reusable components have dedicated icons:

- **Boundary Capture**: completed Record manifest + child Case + new file path
  → saved boundary file, mapped Case and source report. Work runs asynchronously.
- **Boundary Data**: saved file + matching child Case → mapped Case. Increment
  Reload after replacing a file. A SHA-256 hash prevents silently solving a
  changed file through an old case reference.
- **Result Quality**: Solution → numerical-envelope status, transfer eligibility
  and diagnostic report. Solve's monitor and the native panel also show quality;
  wiring this component is optional.

Use the mapped Case with Solve or Record. Native panel quality is supported;
editing/importing boundary datasets in the native panel is not yet exposed.

## Inlet contract and limits

The first format is an offline, mapped X- plane: float32 velocity `[time,3,y,z]`
in child-axis m/s, increasing physical times starting at zero, and JSON metadata
in an NPZ archive. It stores physical grid geometry, source case and file hashes,
source time offset, interpolation method and numerical quality. It requires
2–1000 frames; compressed and expanded archives are limited to 64 MiB, and
capture velocity storage to 32 MiB. Solver memory preflight reserves another
64 MiB for boundary preparation. Full parent recordings retain existing budgets.

Mapping uses physical world coordinates, trilinear interpolation in space and
linear interpolation in time. Vectors rotate between parent and child bases.
Every interpolation sample must be fluid and covered. Nothing is extrapolated,
looped, averaged or silently zero-filled. Child scaling is independent; match
physical time rather than iteration count. Parent and child origin coordinates
are converted using each case's model-unit spacing and physical spacing.

Only stationary, uniform 3D child grids with **periodic Y/Z face pairs** are
supported. No inlet backflow, solid inlet/outlet intersections, moving child,
refinement combination or wall/open-edge intersections. Both parent and child
remain ordinary independent cases; there is no two-way feedback. Use sufficient
parent coverage and investigate domain-placement effects before applications.
Fine cells cannot recover fluctuations missing from the parent recording.

The inlet extends Lettuce's existing equilibrium velocity boundary. Its upstream
source explicitly documents limitations as a Navier–Stokes boundary condition:
`vendor/lettuce/lettuce/ext/_boundary/equilibrium_boundary_pu.py`. Mapped velocity
is also imposed after streaming so completed-step inlet velocity matches the
specified plane. Pressure is not an additional imported input. Verification
covers prescribed values and bounded runs, not universal accuracy or conservative
coupling. Atmospheric inflow, ground roughness and broader open boundaries remain
separate work.

## Quality interpretation

Job completion and result quality are separate. Policy `hawa-low-mach-v1` checks
initial state and at most five-step intervals, including the last partial chunk.
It reports sampled maximum/peak lattice Mach, cells above 0.15, maximum lattice
density deviation from 1, finite/positive state, approximate boundary mass flux
and inlet/outlet backflow counts. Periodic pairs are excluded from net external flux. Flux uses nodal quadrature and is not an exact
discrete conservation proof. These checks do not establish settling, turbulence
accuracy or statistical convergence.

- **within-tested-envelope**: sampled Mach ≤0.10 and density deviation ≤5%.
- **warning**: sampled Mach >0.10 or density deviation >5%.
- **rejected**: sampled Mach >0.15, density deviation >10%, nonfinite populations,
  nonpositive density or no fluid cells.

The worst sampled status remains until reset and survives checkpoint save/load. Legacy checkpoints without quality history receive a warning and cannot feed normal transfer. Nonfinite/nonpositive states stop
the solver; finite out-of-envelope runs can finish for diagnosis but cannot feed
Boundary Capture. Normal transfer requires the source to pass the bounded policy.
The reported Mach=0.46 pilot belongs in rejected status. The labels describe this
numerical policy only; they do not certify a useful atmospheric result. Unsampled
steps may exceed sampled maxima. Quality is included in recorded frames, field
snapshots and exports. Older recordings without quality must be recreated.

## Verification

See [the gate record](boundary-transfer-review.md). CUDA and Windows require
actual hardware; CPU/MPS comparisons cannot establish their support in practice.
The known PorousMedium CPU/MPS discrepancy remains open.

## Subsequent scope audit: curved-wall combination

A CPU reproduction found that a mapped inlet combined with `wall_links` is
accepted but loses its post-stream inlet update when the curved-wall handler is
installed. Do not use that combination. Example 24 has no curved child walls and
its recorded verification remains applicable. See [the next-stage scope](general-boundaries-atmosphere-scope.md)
for the failed case and required composition gate. No production patch was made
during this scope-only assessment.

The composition failure above is repaired in the boundary-foundation development
build by the ordered step coordinator. A regression verifies the prescribed
10-step inlet profile and retained wall history. Direct writer overlap rejects.
For the new NEE route and wall-compatible mapped fields, see
[the boundary guide](general-boundaries.md). Legacy periodic restrictions remain.
