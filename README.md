<p align="center"><img src="site/assets/hawa.svg" width="76" alt="Hawa"></p>

# Hawa — Flow, inside Rhino.

**An open-source GPU lattice Boltzmann prototype for Rhino 8 and Grasshopper.** Create a domain, voxelize closed geometry, set the physics, and inspect the resulting flow fields without launching an external solver.

[Project page](https://range-et.github.io/hawa-cfd/) · [Download v0.2.0](https://github.com/range-et/hawa-cfd/releases/download/v0.2.0/Hawa-0.2.0-rh8.zip) · [Installation guide](docs/plugin.md) · [Editable examples](examples/grasshopper)

![The Hawa Grasshopper workflow, with a completed 300-step MPS run](docs/captures/06-block-mps-completed.jpg)

## What is here

- **15 Grasshopper components** with original icons, input descriptions, and numbered workflow groups.
- **8 editable `.gh` definitions**, including Taylor–Green vortices, cavity flow, forced channel flow, and a self-contained 3D block case.
- **Embedded Python 3.9 + PyTorch** with explicit `auto`, `cpu`, `mps`, and `cuda:0` selection.
- **Native results**: colored field slices, point sampling, velocity vectors, snapshot streamlines, and local NPZ checkpoints/exports.
- A complete vendored Lettuce source tree, original upstream tests, additional compatibility checks, and a separate unmodified reference environment.

Apple GPU acceleration uses **PyTorch MPS**, not MLX. CPU and MPS have been exercised on this Mac. NVIDIA CUDA and Windows installation verification remain outstanding.

## Start in Grasshopper

1. [Download the plugin ZIP](https://github.com/range-et/hawa-cfd/releases/download/v0.2.0/Hawa-0.2.0-rh8.zip) and copy its **entire `Hawa` folder** into Grasshopper's Libraries directory. Restart Rhino 8.
2. Open `Hawa/examples/01-tgv3d-bgk.gh`. Rhino downloads the pinned dependencies on first initialization; allow time and internet access for this setup.
3. Choose **auto** in Backend and double-click **Run / Pause**. Keep Grasshopper open while viewing its Rhino preview.
4. Change the displayed field or slice. Run false pauses; Reset true → false clears state; Run false → true resumes toward the absolute target iteration count.

No separate Python installation or OpenFOAM installation is required. If another script already loaded a conflicting NumPy version, restart Rhino before initializing Hawa. See [the full plugin guide](docs/plugin.md) for units, controls and troubleshooting.

## Watch the walkthroughs

The launch videos use captioned screenshots from the actual verified Rhino sessions. They are screenshot-based walkthroughs, not continuous screen recordings. Public YouTube links are listed here once published.

<!-- HAWA_VIDEO_LINKS -->

## A physical case you can edit

![Block obstacle, computed speed slice and instantaneous streamlines in Rhino](docs/captures/07-block-rhino-preview.jpg)

Open `08-wind-around-block.gh` to follow Domain → Geometry / Physics / Boundaries → Case → Solve → Slice / Streamlines. Its geometry is internalized and its length units are explicitly meters. It uses a viscous demonstration fluid (`nu = 0.1 m²/s`); it is not a validated atmospheric wind analysis.

## Development

The production target is CPython 3.9 with PyTorch 2.8.0 and NumPy 2.0.2. Python 3.12 is a separate unmodified upstream oracle, not a user dependency.

```sh
uv sync --extra test
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/audit_backport.py
.venv/bin/python scripts/run_upstream_tests.py
.venv/bin/python scripts/bootstrap_reference.py
.venv/bin/python scripts/run_upstream_tests.py --reference
.venv/bin/python scripts/compare_engines.py
.venv/bin/python scripts/run_examples.py --device cpu
.venv/bin/python scripts/run_examples.py --device mps
.venv/bin/python scripts/build_plugin.py
```

The Rhino SDK must be installed to build the Grasshopper assembly. Run `scripts/create_grasshopper_examples.cs` inside Rhino to regenerate the native examples; `scripts/verify_grasshopper_examples.cs` reopens their saved graphs and verifies MPS stepping and meshes. These developer scripts currently use this checkout's absolute path; adjust `root`/paths on another machine.

## Verification status

- Hawa tests: **77 passed, 29 skipped** on this Mac.
- Vendored upstream suite: **419 passed, 884 skipped** in the last complete run. Skips include unavailable native/CUDA combinations and upstream exclusions; they are not additional passing tests.
- Six comparable core cases: CPU FP32/FP64 field arrays bitwise match the upstream oracle; MPS comparisons pass declared tolerances. The repaired cavity is checked separately because the upstream constructor fails.
- All **16 original executable example entrypoints** complete bounded CPU and MPS runs. Default stepping caps are 50 iterations (250 for the intentional-failure example); this does not establish original full-duration convergence.
- PorousMedium has a localized CPU/MPS FP32 KBC difference after the bounded run. Its strict pointwise comparison remains a known discrepancy, despite small aggregate relative errors. Do not claim universal pointwise example parity.
- All **8 native Grasshopper definitions** reopen and run their actual graphs to 25 MPS steps with valid slice meshes. UI verification additionally ran the vortex to 200 and block case to 300 steps in embedded CPython 3.9.10, PyTorch 2.8.0, NumPy 2.0.2, without diagnostic overrides.

The `.gh` gallery covers seven numerical cases plus a physical block workflow; it does not yet wrap all sixteen upstream entrypoints. The block uses a viscous demonstration fluid and is not a validated atmospheric analysis. Production CFD validation, complete upstream-example GH wrappers, and NVIDIA/Windows verification remain work to do.

See [the editable example gallery](examples/grasshopper/README.md), [screenshots and video shot list](docs/captures/README.md), [backport notes](vendor/lettuce/PORTING.md), and [third-party notices](THIRD_PARTY_NOTICES.md).

Hawa and vendored Lettuce retain MIT notices. Butterfly is **GPL-3.0+**, used only as an API/workflow reference; no Butterfly code or assets are bundled.
