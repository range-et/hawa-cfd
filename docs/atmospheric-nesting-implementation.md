# Atmospheric nesting completion contract

November 9, 2026. Owner/reviewer: Codex (self-review). The earlier neutral coupling
work did **not** complete the requested city → neighbourhood → pond workflow:
neutral validation rejected `boundary_field`, v1 was X− only, and neutral quality
disabled transfer. The development v2 path now accepts neutral external data;
physical qualification remains open. HAWA-021 tracks the complete workflow. This record
supersedes the earlier implication that passing separate operators completed nesting.

## Implementation and acceptance fixed before measurement

- BoundarySeries v2: immutable local file, SI world mapping, velocity **and pressure**
  on every active exterior face, strictly increasing time, full child initial field,
  explicit parent time origin and source/frame/geometry/model provenance. Keep v1.
- Ground samples below the first parent centre use its declared wall law and
  impermeability. Fluid interpolation excludes solid donors, reports reduced
  support and rejects uncovered fluid; child solid/halo ownership remains local.
  No arbitrary extrapolation or copying values through a building.
- Mapped exterior faces prescribe parent velocity, pressure and kinetic strain,
  including side/top entry and reversal. A constrained reconstruction retains
  protected wall/body links and matches the available moments. This supersedes
  the initially proposed convective-velocity/mapped-pressure split, which did not
  reproduce the supplied boundary state. Unmapped pressure-open faces retain the
  child normal flow and apply prescribed tangential backflow. Record mass exchange.
- Numerical health permits experimental transfer only with the existing explicit
  neutral-model opt-in. Model qualification and statistical adequacy stay separate;
  a safe import does not certify a wind estimate.
- Measured/time-window statistics must report means, covariance, spectra and
  uncertainty; roughness transitions require separate spatial surface properties.
- Manufactured transform/time/pressure/mask/ground/reversal tests: interpolation
  error <= 1e-5 in SI; CPU/MPS velocity agreement atol 5e-5 m/s, rtol 5e-4.
- Nested vs monolithic: <=5% relative mean-velocity L2 and <=10% fluctuation RMS
  difference at declared fluid probes, with sampling/initialisation/grid/cadence
  variations recorded. Cp RMSE <=0.1. Do not move thresholds after failures.
- Neutral empty-flow: retain <=5% profile and wall-budget targets; test three
  spacings, averaging windows and sample-height sensitivity.
- External experimental check: AIJ Case I cube, measured inflow and U/W observations,
  no concentration claim. Use the hit-rate definition (25% relative OR 0.05 U_H
  absolute error), target >=0.66 for streamwise velocity; report vertical velocity,
  TKE, all exclusions and grid/time sensitivity separately. A coarse qualitative
  picture or finite state does not pass the measured-velocity gate.
- Live GH: annotated three-stage definition, source saved idle, automatic dependency
  scheduling, matching absolute times, non-null fields/statistics, cancellation,
  invalid-data withholding, recovery, file reload and no owned-worker leaks.
- Run G0–G6, extend matrix acceptance and archive migration for every appended port,
  and package the exact source. Retain failed runs and update features/issues.

Reference data: AIJ Case I, Kondo/Mutou/Hori, edited by Tominaga/Kikumoto/Okaze,
Zenodo DOI 10.5281/zenodo.15430018 (resolved record 15430019), CC BY 4.0. Download
explicit published files, retain checksums and attribution; do not scrape a site.
The PALM nesting paper (Hellsten et al., GMD 14, 3185–3205, 2021) distinguishes
interpolated boundary data, mass consistency and turbulence adjustment. Those are
separate checks here; no PALM or OpenFOAM implementation is copied.

## Development contract details

Wall-filter history is transferred only when ground planes, wall sample height
and filter duration match. Other cases explicitly reset the filter and need child
spin-up. Files have compressed/expanded size checks; capture has an allocation
budget and cooperative cancellation. v1 remains readable. A 2% mapped-pressure
density limit is stricter than the general 5% health check: a numerically healthy
startup frame may still be ineligible for import. Do not remove that guard.

Plane Field, Flow Display, Isosurface and Surface Field accept up to 16 immutable
frames at the same absolute time. The finest containing domain owns each sample,
including its solid mask. Equal cell widths use input order. Pressure references
must agree; mean and instantaneous fields cannot be mixed. This combines display
data only. It does not couple lattices or implement multilevel refinement.

Plane triangles are clipped to the domain union and, for halfway voxel walls,
to the represented solid boundary. Fluid portions survive partial intersection.
Boundary colours use fluid-normalized interpolation and stationary wall speed
zero; raw samples retain their original validity. Curved-link fields and gradient
fields keep conservative validity until their own reconstruction is verified.

The legacy GH poll schedule can be erased by another solution. The development
adapter retains job/generation requests in an owned UI timer, batches one solution
per document and cancels requests on disposal. Host lifecycle checks are required;
unit tests alone cannot qualify this behavior.
