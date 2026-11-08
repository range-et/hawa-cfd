# Parametric hull and Galapagos

Open `09-parametric-hull-galapagos.gh` in Rhino 8 with Hawa v0.3.0 installed. The definition contains the complete assembly. It needs no Rhino model, external Python installation, or external CFD process.

This example demonstrates a shape search for a fully submerged, stationary canoe hull. The fluid moves in +X. The hull has a closed flat deck and curved underwater sections. There is no free surface, wave resistance, buoyancy, trim, or boat motion.

## Use the example

1. Change **Bow fullness**, **Stern fullness**, and **Beam / draft** to inspect the shape. The length and closed mesh volume stay fixed.
2. Select **auto**, **mps**, **cuda:0**, or **cpu**. The saved definition starts with **Enable evaluation** false.
3. Set **Enable evaluation** true. Wait for the completed result. The Grasshopper solution waits while the candidate runs.
4. Double-click **Minimize hull resistance** to open Galapagos. Its Genome links to the three shape sliders. Its Fitness links to Hawa Evaluate. The saved goal is **Minimize**.
5. Open **Solvers** and select **Start Solver**. The supplied settings use population 10, initial boost 1, and a two-minute limit. A slower device may need a longer limit to complete a population.
6. When the search stops, select a genome and press **Reinstate**. Hawa evaluates the selected hull again and displays its field.
7. Set Enable false before editing the tank, fluid, duration, or resolution. Save a copy for another study.

Opening a saved enabled definition requires Enable false, then true. A disabled evaluator emits no fitness or solution. A failed run reports an error and emits no candidate score. Close Galapagos and fix the case before restarting the search.

## Assembly

```text
Shape sliders → Parametric Hull → Geometry ─┐
Fixed tank → Domain ──────────────────────┼→ Case → Evaluate → Fitness → Galapagos
Fluid controls → Physics ─────────────────┤              └→ Slice / Streamlines
Face conditions → Boundaries ─────────────┘
Galapagos Genome → the three shape sliders
```

Hawa Parametric Hull creates 40 longitudinal intervals and 25 points around each section. It rescales the transverse coordinates to retain the requested mesh volume. Bow controls the upstream taper exponent. Stern controls the downstream exponent. Beam / draft changes the section aspect ratio. The Genome excludes the reference length and volume controls.

The fixed tank measures 24 × 12 × 10 m. The example uses 0.4 m cells, a 1 m/s inlet, density 1000 kg/m³, and kinematic viscosity 0.1 m²/s. Side, top, and bottom faces use slip conditions. This deliberately viscous fluid keeps the small demonstration stable. It does not represent water at normal temperature.

## Fitness

Each changed candidate creates a fresh D3Q19 regularized LBM run. It completes 200 iterations and averages the last 20 obstacle-force samples. Hawa caches the last unchanged candidate. Hawa releases previous candidate sessions.

A full-way bounce-back boundary measures momentum exchange on links between fluid and solid sites. For an incoming population at a solid site, reflection transfers `2 f_i e_i`. The measurement excludes links between solid sites. The physical force conversion is `rho_scale × dx⁴ / dt²`. The measurement excludes domain-face forces.

Galapagos minimizes:

```text
mean X force / (0.5 × density × speed² × reference volume^(2/3))
```

The reference volume stays fixed during a search. The result is dimensionless. The report gives mean X force, its standard deviation, and voxel volume. Hawa emits fitness only after the whole evaluation completes. A background Solve node would return intermediate values while Galapagos changes the genes. Use Evaluate for this assembly.

## Verification and interpretation

The embedded Mac MPS demonstration completed a population of ten genomes. Reinstating the best recorded genome reproduced its fitness. The starting score was 3.964145. The best recorded score was 3.895586. See [the recorded candidates](media/hull-search.json).

These scores demonstrate the search connection and repeatable evaluations. They do not establish a resistance improvement for a real boat. The coarse voxelized hull volume differed from the 6 m³ mesh volume: 5.056 m³ for the starting shape and 4.864 m³ for the selected shape. The score difference is small relative to grid effects and force fluctuations. The two-minute search completed one population. It did not establish an optimum or convergence.

Before drawing physical conclusions, refine the grid and extend the run and averaging window. Check domain clearance and Reynolds number. Compare with an established submerged-body benchmark. A surface boat study also needs a free-surface solver and separate validation.

The selected hull also passed a 200-iteration CPU/MPS comparison. The fitness values differed by about 0.0014%. See [the verification report](media/hull-verification.json).

The tests check zero force for a resting equilibrium, force sign under flow reversal, repeatability, CPU/MPS agreement, density scaling, invalid settings, and session cleanup. The saved definition is also checked inside Rhino for closed geometry, fixed volume, Galapagos links, completed evaluation, result meshes, disabled outputs, and reopening.
