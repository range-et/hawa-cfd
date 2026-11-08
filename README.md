# Hawa

**GPU lattice Boltzmann simulation for Rhino 8 and Grasshopper.**

Hawa runs its Python 3.9 engine inside Rhino. Define geometry and physics in Grasshopper. Use MPS, CUDA or CPU through PyTorch. Inspect pressure, speed and flow paths in the viewport.

This branch contains the experimental **0.4** update. The published **0.3** package and videos remain available on the [project page](https://range-et.github.io/hawa-cfd/). Read the [0.4 checks and limits](docs/release-notes-v0.4.0.md) before using the new package.

[Plugin guide](docs/plugin.md) · [Editable definitions](examples/grasshopper) · [License](LICENSE)

## New workflows

- Responsive hull search with completed-candidate IDs, pause, cancel and best-result history.
- 3D stream tubes, domain wireframes, field planes, contours, isosurfaces and offset surface sampling.
- Shared blue-green, spectrum and diverging color maps with fixed ranges.
- Timed field recording, playback and particle paths.
- Local airfoil coordinates and polars, offline NACA four-digit generation, tapered wings and attached-flow lifting-line analysis.
- Mesh checks, voxel inspection, experimental stationary curved-wall links and one fixed 2:1 refinement patch.

The package has 38 Hawa components and 15 editable definitions. Example 09 is historical and excluded from the new package. Use example 10 for asynchronous optimization.

## Install and run

Build the current package with `scripts/build_plugin.py`, or use the provided development ZIP. Copy the complete Hawa folder to Grasshopper's Libraries directory. Quit Rhino normally, reopen it, and open `01-tgv3d-bgk.gh`.

Rhino installs the pinned dependencies on first use. This needs internet access. Select a backend and set Run true. The solver then runs inside Rhino. No separate Python or OpenFOAM installation is required.

For new visualization tools, open example 11. Examples 12–16 cover local airfoils, recording, sphere pressure, refinement and cylinder flow. See the [plugin guide](docs/plugin.md) for controls and input limits.

## Videos

The new local renders are `dist/videos-v04/hawa-flow-tools.mp4` and `dist/videos-v04/hawa-cylinder-wake.mp4`. They use actual recorded fields, native Rhino captures, Monad colors and captions. They have no audio. Watch the published [Tools video](https://youtu.be/GN6Ou3yOF_I) and [Wake video](https://youtu.be/zpRlRn9Qbf4).

Earlier published walkthroughs: [overview](https://youtu.be/Ji_9iOYXSXg), [block](https://youtu.be/PVBanKHGhC4), [historical Galapagos hull](https://youtu.be/0kVTmHttA78).

## Development

The production target is Python 3.9 with PyTorch 2.8.0 and NumPy 2.0.2. A separate Python 3.12 environment runs unmodified upstream Lettuce for reference comparisons.

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

The Grasshopper build needs the installed Rhino SDK. Run `scripts/create_grasshopper_examples.cs` inside Rhino to create the `.gh` files. Run `scripts/verify_grasshopper_examples.cs` to reopen and check those graphs. Run `scripts/create_hull_example.cs` and `scripts/verify_hull_example.cs` for the hull assembly.

The C# helper scripts contain this checkout's paths. Change the paths before you run the scripts on another machine.

### Website and videos

The website and video renderer use the pinned Monad palette in `vendor/monad_system/colors.json`.

```sh
.venv/bin/python scripts/sync_design_tokens.py
.venv/bin/python scripts/build_site.py
.venv/bin/python scripts/make_walkthroughs.py
```

The video renderer needs macOS Helvetica Neue and Menlo, Pillow, ffmpeg, and ffprobe. It writes the MP4 files to ignored `dist/videos-monad/`.

## Verification

The current Hawa suite passes **112 tests**, with 29 skipped and four inherited warnings. The earlier vendored upstream run passed 419 tests with 884 skipped. The Lettuce compatibility engine remains unchanged by the new Hawa outlet and refinement modules.

The core CPU comparison matched the upstream oracle bitwise; MPS passed declared tolerances. All 16 upstream executable entrypoints completed bounded runs. These are separate from the Grasshopper gallery. PorousMedium retains a known pointwise CPU/MPS discrepancy.

Native MPS checks exercise saved definitions, valid field meshes, recording, a repeated hull search, and the fixed refinement patch. See the [release notes](docs/release-notes-v0.4.0.md) for exact evidence and limits.

CUDA hardware, Windows installation, full-duration upstream convergence and engineering-case validation remain open. Refinement is experimental. Aircraft analysis does not include XFOIL viscous calculations, VLM, stall or stability derivatives.

## Attribution

- **Hawa:** GNU GPL version 3 (`GPL-3.0-only`). Copyright (c) 2026 Hawa contributors. See [LICENSE](LICENSE).
- **Lettuce:** MIT license. The vendored source retains its original copyright and author notices.
- **Butterfly:** GPL-3.0+ workflow reference. Hawa contains no Butterfly code or assets.
- **Monad System:** MIT license. The website and videos use its pinned colors and styles.

See [the third-party notices](THIRD_PARTY_NOTICES.md) and [the Monad license](vendor/monad_system/LICENSE).
