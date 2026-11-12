# Hawa

**A CFD sketchpad for Rhino 8 and Grasshopper.**

Hawa runs a lattice Boltzmann flow solver inside Rhino. You select geometry, set a domain and fluid properties, run on the GPU (Apple MPS or NVIDIA CUDA) or the CPU, and inspect pressure, speed and flow lines in the viewport. Results are quick and approximate. Hawa is experimental: a completed run or a clean-looking field does not establish convergence or engineering accuracy.

[User guide](docs/user/README.md) · [Plugin guide](docs/plugin.md) · [Example definitions](examples/grasshopper/README.md) · [Project page](https://range-et.github.io/hawa-cfd/) · [License](LICENSE)

## What it does

- **Native panel (Rhino):** set up a case from selected closed meshes or solid Breps, edit the domain, fluid and face boundaries, then run, pause and inspect a slice. See the [0.5 native guide](docs/native-v0.5.md).
- **Grasshopper components:** cases, solving, sampling and display. The views are slices, vectors, streamlines, flow tubes, field planes, contours, isosurfaces and offset surface sampling. Parts of a view that were not simulated (solids, gaps between domains, missing derivatives) are drawn black.
- **Recording and playback** of timed field frames.
- **Responsive design search** over completed candidates (example 10).
- **Experimental options:** prescribed moving bodies with body loads, a fixed 2:1 refinement patch, stationary curved-wall links, nested parent/child domains, and local airfoil and lifting-line analysis.

Particles and time-dependent pathlines were removed in November 2026. Saved definitions that use the old Particles component still open; the component reports that it was removed.

## Install

Requirements: Rhino 8 on macOS (Apple silicon, MPS or CPU) or Windows (CUDA or CPU), and internet access on first use.

1. Build the package with `scripts/build_plugin.py`, or use a provided Hawa ZIP.
2. Copy the complete `Hawa` folder to Grasshopper's Libraries directory. Keep `python`, `Bootstrap.py`, the licenses and the source beside the `.gha`.
3. Quit Rhino normally and reopen it.
4. Open `01-tgv3d-bgk.gh` from the package examples (`examples/grasshopper/` in the source). On first use Rhino installs the pinned Python dependencies (PyTorch 2.8.0, NumPy 2.0.2, pydantic 2.13.5) into its embedded Python 3.9. No separate Python or OpenFOAM installation is needed.

Details and troubleshooting: [plugin guide](docs/plugin.md#install).

## First run

1. In example 01, choose a backend and set **Run** to true. The solver runs in a background worker; Grasshopper stays responsive.
2. Open example 11 for the 3D views on one shared snapshot: planes, tubes, contours and isosurfaces.
3. Examples 12–20 cover airfoils, recording, sphere pressure, refinement, cylinder flow and moving bodies. Examples 21–23 use the native panel. The [example catalogue](examples/grasshopper/README.md) lists every workflow and its limits.

Saved definitions open idle. Toggle Run off and on to start a job.

## Limits

- Single-phase, low-Mach flow on a uniform lattice, with one optional refinement patch. Cell size limits how well thin features and near-wall flow are represented.
- Quality labels report the run's numerical envelope only. They are not validation.
- Moving bodies follow prescribed motion. There is no free-body dynamics. Read the [moving-surface guide](docs/moving-surfaces-v0.4.md) before using body loads.
- Airfoil analysis assumes attached flow. Stall, XFOIL viscous polars and stability derivatives are not included.
- Solver work on Apple's MPS backend from several threads is now serialised by one shared lock ([#99](https://github.com/range-et/hawa-cfd/issues/99)); the sequence that aborted Rhino now completes in a live check. A quality warning still does not report its trigger ([#98](https://github.com/range-et/hawa-cfd/issues/98)). See [open issues](https://github.com/range-et/hawa-cfd/issues).
- A clean Windows Rhino installation has not been verified end to end.

## Documentation

- [User guide](docs/user/README.md), [plugin guide](docs/plugin.md) and [native guide](docs/native-v0.5.md)
- [Built features and history](features.md) and the [build log](https://range-et.github.io/hawa-cfd/build-log/)
- [Roadmap](docs/roadmap.md) and [example catalogue](docs/example-roadmap.md)
- [Quality gates](docs/quality-gates.md) and [compatibility matrix](docs/compatibility-matrix.md)
- [Windows CUDA setup](docs/windows-cuda.md)

## Development

Production code targets Python 3.9, because Rhino 8 embeds CPython 3.9. Two environments come from `uv.lock`:

```sh
# .venv, Python 3.9: tests, gates and scripts
uv sync --extra test
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/build_plugin.py
# .venv-dev, Python 3.12: ruff and mutation studies
UV_PROJECT_ENVIRONMENT=.venv-dev uv sync --python 3.12 --extra test --group tools
.venv-dev/bin/ruff check .
```

Pull requests run the headless suite on Python 3.9 and 3.12, the function and line coverage gate, mutation checks and a CPU device smoke test. Grasshopper behaviour is also checked in a live Rhino session. Example definitions are generated in Rhino with `scripts/create_grasshopper_examples.cs` and annotated with `scripts/annotate_grasshopper_examples.cs`; keep the user-modified example 09 out of regeneration and packages ([verification matrix](examples/grasshopper/VERIFICATION.md)). Read [CONTRIBUTING](CONTRIBUTING.md), [AGENTS.md](AGENTS.md) and the [function testing guide](docs/function-testing.md) before changing code. Work is tracked in [GitHub issues](https://github.com/range-et/hawa-cfd/issues).

## Attribution

- **Hawa:** GNU GPL version 3 (`GPL-3.0-only`). Copyright (c) 2026 Hawa contributors. See [LICENSE](LICENSE).
- **Lettuce:** MIT license. The vendored source keeps its original copyright and author notices.
- **Butterfly:** GPL-3.0+ workflow reference. Hawa contains no Butterfly code or assets.
- **Monad System:** MIT license. The website and videos use its pinned colours and styles.

See the [third-party notices](THIRD_PARTY_NOTICES.md) and the [Monad license](vendor/monad_system/LICENSE).
