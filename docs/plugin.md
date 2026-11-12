# Hawa for Rhino 8 / Grasshopper

Hawa runs its Python 3.9 Lettuce engine inside Rhino. PyTorch uses MPS on Apple Silicon or CPU. The default installer installs the standard PyTorch wheel, which on Windows is CPU-only, so `cuda:0` is normally unavailable inside Rhino. Installing CUDA PyTorch into Rhino's embedded environment is unverified; [the Windows CUDA guide](windows-cuda.md) covers headless CUDA verification only. Select `auto`, `mps`, `cuda:0`, or `cpu`. An unavailable explicit selection reports an error.

## Install

Unzip the Hawa package (for example `Hawa-0.5.0-rh8.zip`). Copy the complete `Hawa` folder to Grasshopper's Libraries directory. Keep `python`, `Bootstrap.py`, licenses and source beside the `.gha`. Quit Rhino normally and reopen it. Select the **Hawa** tab.

Open `examples/01-tgv3d-bgk.gh`. Rhino downloads pinned dependencies on first use. This needs internet access and can take time. Subsequent solves run in Rhino's process. No separate Python or OpenFOAM install is required. Quit and restart Rhino if another script loaded conflicting dependencies.

## Controls

- **Solve:** Run starts or resumes; false pauses. Target is the total iteration count. Reset clears the state. Changing the case creates a new idle session.
- **Search:** connect slider genes and an Evaluate component as in example 10. Run advances one candidate after the previous result completes. Pause holds the search; Run false cancels. History includes candidate IDs. Restore Best writes the best recorded genes to the sliders.
- **Record / Refined Solve:** Run starts a fresh job; false cancels. Pause holds at a step boundary. Recording requires a new absolute directory.
- Saved Run=true values open idle. Toggle off and on to start. Closing a definition requests cancellation and releases its job registrations.
- Use one item per input for stateful components. Lists or trees of cases are rejected. Geometry meshes and seed points use their documented list inputs.

Geometry classification, solver creation, numerical work and field extraction use background workers. Grasshopper schedules short progress updates. Initial dependency loading still runs through Rhino's Python initialization. Cancellation takes effect at a checkpoint; it does not interrupt a GPU instruction midway.

Galapagos waits synchronously for fitness and cannot directly consume this asynchronous protocol. Use **Hawa Search** for responsive repeated CFD runs. Example 09 is retained in the source repository as a historical file and is excluded from the 0.4 distribution.

## Editable definitions

| File | Workflow |
| --- | --- |
| 01–05 | 2D/3D Taylor–Green vortices; BGK, TRT and Smagorinsky |
| 06 | Driven cavity |
| 07 | Poiseuille channel with Guo forcing |
| 08 | Basic block flow |
| 10 | Responsive parametric hull search |
| 11 | Domain wireframe, 3D tubes, plane contours and isosurface |
| 12 | Local airfoil coordinates, local polars, tapered RC wing and LLT |
| 13 | Record and play back timed fields |
| 14 | Experimental interpolated sphere walls and offset Cp sampling |
| 15 | Experimental fixed 2:1 refinement around a sphere |
| 16 | Record a cylinder wake and inspect the saved frames |

Keep the supplied `data` folder next to the airfoil example. Relative paths resolve beside the definition. `polar-format.csv` contains synthetic format data; replace it before making aerodynamic decisions. The wake video uses an analytical cylinder mask and a small initial perturbation; the mesh-based definition is a separate editable simulation.

## Components

| Ribbon group | Components |
| --- | --- |
| 00 Setup | Runtime |
| 01 Domain | Domain, Wind Tunnel, Domain Preview, Refinement Patch |
| 02 Geometry | Geometry, Geometry Check, Grid Preview |
| 03 Physics | Physics, Boundaries |
| 04 Case | Case, Example, Check Case |
| 05 Solve | Solve, Evaluate, Search, Refined Solve |
| 06 Results | Sample, Field Snapshot |
| 07 Visualize | Slice, Vectors, Streamlines, Seed Points, Color Map, Plane Field, Isosurface, Flow Display, Surface Field, Legend |
| 08 Files | Checkpoint |
| 09 Airfoils | Airfoil, Polar Data |
| 10 Aircraft | Wing, Wing Analysis |
| 11 Animation | Record, Playback |

Hover over each input for units and limits. Domain supports `model`, `meters`, and `millimeters`. Wind Tunnel follows the document units and aligns X with the wind. Closed obstacle meshes must clear the inlet and outlet. Geometry Check reports closure, naked edges and bounding dimensions. Grid Preview shows occupied cells.

## Fields and animation

Capture one **Field Snapshot** and connect it to several views. All views then use the same field and time. Select speed, pressure, density, velocity components, Cp, vorticity magnitude or Q. Derivative fields mask samples that touch solids. Blue-green, spectrum and diverging palettes have explicit limits. Share a Color Map between views and a Legend.

Plane Field supports an arbitrary rectangle and contour levels. Isosurface extracts a scalar level in 3D. Flow Display traces snapshot streamlines and builds tubes. Surface Field samples at an outward offset from a mesh; those values are approximate surface values. Hide Domain's own box preview when using Domain Preview's wireframe.

Recording stores velocity, pressure, density, solid masks, iteration and physical time in local NPZ files. Playback selects a frame. Limits are 1,000 frames and 2 GiB per recording. Partial recordings retain their completion state; do not treat a cancelled run as completed.

## Parent and child domains

A parent can supply recorded boundary data to a separately run child. That
**offline one-way transfer**, **coupled refinement**, and **composed field views**
are different operations. The [parent/child guide](parent-child-domains.md)
explains resolution, time and data ownership, and maps example 33's existing
city/neighbourhood/pond labels to outer/local/finer domains. Atmospheric and
nested statistical qualification remain open.

## Refinement and numerical scope

Refinement Patch snaps a rectangular region to the parent grid. Voxelize the original geometry on both domains. Use the same physical settings and BGK collision in both cases. Refined Solve advances the fine grid twice per coarse step and returns separate frames. The coarse frame masks the covered interior.

This release supports one fixed 2:1 patch. It uses cubic population reconstruction and filtered nonequilibrium restriction. It has no dynamic patch motion, automatic geometry-driven patch creation or exact conservative refluxing. Curved-wall links cannot be combined with refinement. Keep interfaces two coarse cells from solids and outer faces. Compare a uniform fine-grid result for each new case.

Stationary interpolated walls use measured fluid-to-wall link fractions on a uniform D3Q19 grid. Moving walls and free surfaces are outside this implementation. The hull model excludes waves, buoyancy and body motion.

Wind cases use X- equilibrium inlet, X+ zero-gradient population outflow, and paired periodic, wall or slip transverse faces. The outflow assumes outgoing flow and can reflect disturbances; keep it away from wakes and compare larger domains. The previous outlet developed negative density in a long cylinder run. Version 0.4 replaces it in Hawa; the vendored Lettuce implementation is unchanged.

Airfoil uses offline four-digit NACA generation or local Selig/Lednicer files. Polar Data reads local CSV/XFOIL data and interpolates Cl, Cd, Cm and L/D within its supplied range. LLT models attached flow on an unswept tapered wing. Optional matching polar data adds approximate profile drag. It does not calculate viscous polars, stall, VLM/panel solutions or aircraft stability derivatives. No airfoil websites are queried.

## Verification and license

See [release notes](release-notes-v0.4.0.md) for measured checks and remaining limits. MPS and CPU were exercised here. CUDA hardware and Windows installation remain unverified. Numerical and UI checks do not establish engineering accuracy.

Hawa source is `GPL-3.0-only`. Lettuce and Monad retain their MIT notices. Butterfly, OpenFOAM, Autodesk Flow Design and XFLR5 are references; their source is not bundled. The package includes corresponding Hawa source and build scripts. See `THIRD_PARTY_NOTICES.md` and `licenses/lettuce`.


## Prescribed moving bodies (experimental)

Use **Translation**, **Rotation** or **Oscillation** to define motion. **Moving Body** prepares a closed mesh against a base physical Case in the background. Its pivot and axis use model coordinates; speed is m/s, RPM is rev/min, and angular oscillation amplitude is radians. Connect one to four prepared bodies to **Motion Case**, then use the existing Solve or Record component. Do not also place those meshes in stationary Geometry.

Use uniform BGK. Keep every moving body at least two cells from every domain face and clear of other bodies. Thin parts need enough cells across their thickness. The check includes wall speed, including rotational tip speed. The experimental limits are 150,000 domain cells, four bodies and 200,000 signed-distance samples per body.

Connect one Field Snapshot to both Plane Field and **Body Loads**. Connect Body Loads' motion-state output and the reference mesh to **Body Preview**. This displays the body at the same time as the field. Recorded frames carry the same pose/load metadata.

**Motion Evaluate** publishes a fitness and candidate ID after complete cycles. Set a common period for all motions, settling cycles and measured cycles. The startup ramp must finish during settling. Connect its completed fitness and ID to Search. The default objective, `input_power`, is negative fluid work on the body; minimizing it minimizes mean mechanical input power under the prescribed motion. Force and torque objectives are signed domain-axis components. No rigid-body response, thrust target or design constraint is inferred.

Example 20 demonstrates this wiring. Its short candidate count and settling interval demonstrate the workflow; they do not establish an optimum. Instantaneous loads can contain startup and cell-transition transients. Compare cycle averages, grid sizes, time steps and longer settling periods.

CPU and MPS work through the same tensor implementation. On the tested small imported-mesh case, CPU was substantially faster than MPS because of many small geometry and boundary tensor operations. `auto` selects an available accelerator, not the fastest measured backend. Select `cpu` when responsiveness matters for a small grid. CUDA moving-body hardware tests remain outstanding.
