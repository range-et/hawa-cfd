# Prescribed moving surfaces in Hawa 0.4

Status: implemented, experimental. Hawa now supports prescribed rigid translation, rotation and oscillation in a fixed, uniform fluid domain. The implementation uses Hawa code and the existing Lettuce tensor engine. No additional upstream engine or repository was imported.

## Workflow

1. Build a physical Case with uniform BGK. Keep the moving mesh out of stationary Geometry.
2. Define Translation, Rotation or Oscillation. Use a nonzero model-space axis. Translation speed is m/s; rotation speed is RPM. Oscillation amplitude is metres or radians, frequency is Hz, phase is radians, and startup ramp is seconds.
3. Connect the Case, closed reference mesh, motion, pivot and unique ID to Moving Body. Preparation runs in the background.
4. Connect one to four Moving Body outputs to Motion Case. Use the existing Check, Solve or Record components.
5. Connect a shared Field Snapshot to Plane Field and Body Loads. Body Preview combines the reference mesh with Body Loads' motion-state output. A shared snapshot keeps body pose and field time synchronized.
6. For cycle-based search, use Motion Evaluate. Connect its completed fitness and candidate ID to Search. Choose a common period, discarded settling cycles and measured cycles. The ramp must finish during settling.

`input_power`, the default motion objective, is the negative of fluid work on the body. Force and torque objectives are signed components in domain axes. Body Loads displays force and torque vectors in model axes, and signed fluid power in watts. Coefficients require explicit reference quantities; they are not inferred. Full bounded load histories are available through the Python service's `body_loads` request and in the returned live motion-state data.

### Editable definitions

- **17 — Oscillating cylinder:** mesh preparation, prescribed transverse motion, field plane, synchronized body preview, recording and playback.
- **18 — Pitching NACA foil:** offline NACA 0024, parametric wing, native Grasshopper Move, pitching motion and loads. The thick profile helps expose the geometry/grid workflow; this coarse demonstration does not resolve realistic RC boundary layers.
- **19 — Rotating paddle:** finite closed paddle rotating in one fluid, with torque and power. It is not a validated propeller performance model.
- **20 — Motion cycle search:** vary oscillation amplitude, settle for a complete cycle and evaluate the next. Three candidates demonstrate completion-driven search. Compare longer settling and more cycles before ranking designs.

## Solver implementation

Motion is evaluated from physical solver time inside the background worker. It does not depend on Grasshopper UI timers. The body geometry is rigid and supplied by the user; the resulting fluid forces do not change its prescribed motion.

The Python implementation supports analytic spheres/cylinders and imported signed-distance grids. Grasshopper prepares a signed-distance grid once from a closed mesh, sampled at half the fluid-cell spacing. Every step transforms physical grid queries into the reference body frame, updates occupancy and wall links, and applies interpolated moving bounce-back. Newly exposed cells use neighbouring density and nonequilibrium stress with local wall velocity. Force evaluation uses relative boundary velocities and covered/uncovered-cell momentum accounting. Torque is about the specified moving pivot. Boundary poses and velocities are evaluated at the step endpoint.

The stationary path remains unchanged. Moving-body updates, masks, field arrays and interpolation run on the selected PyTorch device. Current geometry queries span the bounded domain; the implementation does not yet restrict every update to a swept bounding box or batch all directional kernels.

Recordings contain body poses and current loads with each field frame. Checkpoints restore populations, iteration, motion phase reconstructed from time, transition diagnostics and bounded load history. Reset restores the initial pose. Mean-field capture is disabled for moving bodies; use instantaneous fields and explicit cycle-averaged loads.

The motion, moving-body and Motion Evaluate payloads are validated by pydantic
models; see [the payload schemas](payload-schemas.md) for the field reference and
error format.

## Limits and operating checks

- Uniform BGK only; no moving-body/refinement combination or stationary curved-link combination.
- At most four bodies, 150,000 domain cells and 200,000 signed-distance samples per body.
- Keep bodies two cells from every domain face. Runtime checks stop motion that approaches a face, overlaps another solid, or encounters an unresolved narrow gap. The complete future trajectory is not prevalidated.
- The speed check includes inlet speed and a conservative maximum wall speed, including rotation. Lower lattice Mach or slow the motion if the combined bound exceeds 0.15. The time step follows the case scaling.
- Rigid motions are constant translation/rotation or sinusoidal translation/rotation with a cosine startup ramp. Arbitrary keyframe schedules and independent per-body stop times are not implemented; run duration is set by the solver target.
- No deforming surfaces, contact, fluid-driven rigid-body dynamics, thermal transport, free surfaces, waves, buoyancy or cavitation.
- Instantaneous loads can contain substantial startup and cell-transition transients. A uniform co-moving equilibrium test passes, but general transient-force continuity and arbitrary moving-obstacle convergence are not established. Use completed cycle averages and compare grids, time steps and settling durations. No engineering-accuracy claim is made.
- Changing voxel occupancy changes the volume represented by solid sites. `transition_mass_lu` records the fluid-mass change introduced at cell transitions. It is not a conservative cut-cell volume correction or a proof of exact mass conservation.

## Verification

The full Python suite passes **140 tests**, with **29 skipped** on this machine. The existing CPU FP32, CPU FP64 and MPS engine comparison suite passes. Moving-specific checks include:

- Analytical Couette velocity profile using the production moving-wall reflection rule.
- Short CPU/MPS moving-body population comparison at the stated test tolerances.
- Co-moving body/fluid equilibrium preservation through cell changes, with near-zero loads.
- Exact checkpoint/restart equivalence on CPU and reset to the initial pose.
- Imported signed-distance geometry, independent body IDs, collision/clearance rejection and maximum-speed rejection.
- Recorded frame/pose time agreement and completed-cycle objective windows.
- Background moving recording pause/cancel and worker cleanup.

A rotating-sphere test compares mean torque against the creeping-flow value `-8*pi*mu*R^3*Omega`. With a finite periodic box and cell sizes 0.5, 1/3 and 0.25, relative error decreases approximately **13.6%, 6.6%, 3.0%**. This is a useful grid trend; the finite-domain test is not an unbounded-domain validation. See `scripts/benchmark_rotating_sphere.py` and the recorded evidence.

The cylinder media uses 1,000 actual MPS steps and 101 saved fields, covering about 5.77 seconds. The video contains no generated flow footage or voiceover. Raw force transients remain visible; a symmetric-log force axis preserves the startup peak.

Native checks passed the three moving definitions at 80 MPS steps each, with valid field meshes and closed moved-body previews. A two-candidate motion search passed pause, resume, cancellation and close cleanup; the embedded runtime then held zero jobs, sessions or Hawa worker threads. Eleven existing native graphs also passed their regression checks. Exact evidence is in [verification-motion-v0.4.json](verification-motion-v0.4.json). CUDA hardware and Windows installation remain unverified. The separate PorousMedium CPU/MPS mismatch remains open and is documented in the release notes.

## Performance

On a 26,691-cell imported-mesh case, a local 20-step timing measured about **0.46 seconds on CPU** and **5.64 seconds on MPS**. Other work was active, so this is indicative rather than a controlled throughput benchmark. Many small geometry/boundary kernels make the small moving case CPU-favourable. `auto` chooses an available accelerator, not the fastest benchmarked backend. Select `cpu` for small interactive moving cases and compare devices on the intended grid.

Next optimization work is directional kernel batching, bounded-region geometry updates and reducing host/device synchronization. These can use the existing backend abstraction.

## Numerical references

- [Boundary forces in lattice Boltzmann: Analysis of Momentum Exchange algorithm](https://www.wias-berlin.de/people/caiazzo/PAPERS/MEA_analysis_reviewed_elsart.pdf): force evaluation and newly uncovered nodes.
- [Analysis on force evaluation and localized refilling](https://www.sciencedirect.com/science/article/pii/S0898122125000343): moving boundaries and reconstruction.
- [Hydrodynamic Force Evaluation by Momentum Exchange Method](https://www.mdpi.com/1099-4300/17/12/7876): relative-velocity force formulations and covered/uncovered-node accounting.

These references inform Hawa's independent implementation. They do not imply that all validation cases in those publications have been reproduced here.
