# Hawa for Rhino 8 / Grasshopper

Hawa runs a Python 3.9 Lettuce compatibility engine inside Rhino. PyTorch selects CUDA on NVIDIA, MPS on Apple Silicon, or CPU. Apple acceleration uses PyTorch MPS, not MLX.

## Install

Unzip `Hawa-0.2.0-rh8.zip`. Copy the entire `Hawa` folder (including `python`, `Bootstrap.py`, and notices) into Grasshopper's Libraries directory. Restart Rhino, open Grasshopper, and select the **Hawa** tab. Do not move the `.gha` out of its folder.

Open `examples/01-tgv3d-bgk.gh`. Rhino downloads the pinned Python dependencies on first use; allow time and internet access for that first initialization. No separate Python installation, OpenFOAM installation, or external solver process is required. If another script has already loaded a conflicting NumPy version, restart Rhino before initializing Hawa.

## Try the examples

The eight native `.gh` files include seven numerical verification cases and a physical 3D block case. They are editable definitions with wired Hawa components, dropdowns, sliders, Run/Reset toggles, instructions, and result previews. Geometry is internalized in the block definition; it needs no separate Rhino model.

1. Choose **auto**, **mps**, **cuda:0**, or **cpu** in Backend. Auto probes available devices; an explicit unavailable device produces an error.
2. Double-click **Run / Pause** to set it true. The target is the absolute total iteration count. The monitor shows the selected backend, grid, progress, mass change, and simulation time.
3. Keep Grasshopper open while inspecting its Rhino preview. Change the display field or slice index. `-1` selects the middle slice. Blue is low and red is high; the displayed range updates automatically.
4. Set Run false to pause. Toggle it false → true to resume toward a larger target. Toggle Reset true → false to clear the simulation. Set Run false before changing grid, geometry, or backend; changing these creates a new idle session.
5. Save a copy to experiment. Opening a file does not automatically start a saved Run=true value. Initializing an idle solver still allocates the initial field.

The block example uses explicit **meters** in Domain and a deliberately viscous demonstration fluid (`nu = 0.1 m²/s`). It demonstrates the workflow; it is not a validated atmospheric wind analysis. Its horizontal slice index is editable and snapshot streamlines are wired. The seven numerical examples use Lettuce reference units.

## Components

| Ribbon group | Components | Purpose |
| --- | --- | --- |
| 00 Setup | Runtime | Embedded dependency setup and runtime information |
| 01 Domain | Domain, Wind Tunnel | Uniform oriented lattice or a geometry-relative tunnel |
| 02 Geometry | Geometry | Closed-mesh obstacle voxelization |
| 03 Physics | Physics, Boundaries | Physical speed, viscosity, density, collision and six faces |
| 04 Case | Case, Example, Check Case | Assemble, select and validate a case |
| 05 Solve | Solve | Background iteration, pause/resume, reset and monitoring |
| 06 Results | Sample | Interpolate velocity and pressure at Rhino points |
| 07 Visualize | Slice, Vectors, Streamlines | Colored fields and snapshot flow visualization |
| 08 Files | Checkpoint | Save/load solver populations or export NPZ fields |

The toolbar uses original Hawa artwork. Hover over a component or input for its description and units. The example canvases have numbered, colored workflow groups. Grasshopper can show component names or icons according to its normal Display settings.

Domain accepts `model`, `meters`, or `millimeters`. With `model`, the current Rhino document sets the SI conversion. Wind Tunnel uses document units and aligns local X with the wind vector. Wind cases currently use local X- inlet, X+ outlet, paired periodic faces, solid walls or slip faces. Solids must be closed meshes and must not intersect inlet/outlet.

## Verification and current limits

The clean Rhino 8 Mac session loaded CPython 3.9.10, PyTorch 2.8.0, and NumPy 2.0.2 with no diagnostic override. The vortex was started through its visible Run toggle and reached 200 steps on MPS. Automated native-definition verification reopens the saved files, runs their actual component graphs, checks solver completion and valid slice meshes. See the repository's `results/plugin` reports when running the developer checks.

MPS and CPU have been exercised on this machine. CUDA selection and code paths exist, but NVIDIA hardware validation remains outstanding. Windows installation has not been exercised here. The `.gh` gallery covers eight workflows, not all sixteen original upstream Python/notebook entrypoints. The latter have a separate bounded execution harness; full-duration convergence and production CFD validation remain separate work.

Dense grids are limited to two million cells and an estimated memory budget. Results include instantaneous pressure/density and optional sampled mean velocity. Streamlines follow one field snapshot; they are not time-resolved particle trajectories. Geometry is voxelized, not body-fitted. Checkpoint files are local NPZ files.

Hawa and the vendored Lettuce code retain MIT notices. Butterfly is GPL-3.0+ and is a workflow reference only; its code and assets are not distributed. See `THIRD_PARTY_NOTICES.md` and `licenses/lettuce`.
