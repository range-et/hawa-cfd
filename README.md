# Hawa

**GPU lattice Boltzmann simulation for Rhino 8 and Grasshopper.**

Hawa runs its Python 3.9 engine inside Rhino. Select geometry and set up a case in the native panel, or build workflows in Grasshopper. Use MPS, CUDA or CPU through PyTorch. Inspect pressure, speed and flow paths in the viewport.

This branch contains **Hawa 0.5**, with selected Rhino geometry, editable domains and fluid settings, a dockable panel with icons, field controls and live GH sync. Read the [0.5 guide](docs/native-v0.5.md). The published **0.3** package and videos remain available on the [project page](https://range-et.github.io/hawa-cfd/). Read the [0.4 checks and limits](docs/release-notes-v0.4.0.md) before using the new package.

[User guide](docs/user/README.md) · [Plugin guide](docs/plugin.md) · [Editable definitions](examples/grasshopper) · [License](LICENSE)

Project records: [built features and history](features.md) · [GitHub issues and planned work](https://github.com/range-et/hawa-cfd/issues) · [project roadmap](docs/roadmap.md) · [existing and proposed examples](docs/example-roadmap.md) · [contributing](CONTRIBUTING.md) · [code of conduct](CODE_OF_CONDUCT.md) · [security policy](SECURITY.md). Future solver work is outside the bounded 0.5 prototype.

## New workflows

- Responsive hull search with completed-candidate IDs, pause, cancel and best-result history.
- 3D stream tubes, domain wireframes, field planes, contours, isosurfaces and offset surface sampling.
- Shared blue-green, spectrum and diverging color maps with fixed ranges.
- Timed field recording, playback and particle paths.
- Experimental prescribed moving meshes: translation, rotation, oscillation, body loads and completed-cycle search.
- Local airfoil coordinates and polars, offline NACA four-digit generation, tapered wings and attached-flow lifting-line analysis.
- Mesh checks, voxel inspection, experimental stationary curved-wall links and one fixed 2:1 refinement patch.

The current package has 54 public Hawa components, 29 GH gallery definitions and two native examples (21: block sync; 22: selected canopy). Example 09 is historical and excluded from the new package. Use example 10 for asynchronous optimization.

## Install and run

Build the current package with `scripts/build_plugin.py`, or use the provided development ZIP. Copy the complete Hawa folder to Grasshopper's Libraries directory. Quit Rhino normally, reopen it, and open `01-tgv3d-bgk.gh`.

Rhino installs the pinned dependencies on first use. This needs internet access. Select a backend and set Run true. The solver then runs inside Rhino. No separate Python or OpenFOAM installation is required.

For new visualization tools, open example 11. Examples 12–16 cover local airfoils, recording, sphere pressure, refinement and cylinder flow. Examples 17–20 add an oscillating cylinder, pitching foil, rotating paddle and completed-cycle search. Read the [moving-surface guide](docs/moving-surfaces-v0.4.md) before using body loads. See the [plugin guide](docs/plugin.md) for controls and input limits.

## Videos

The moving-surface demo is `dist/videos-v04/hawa-moving-surfaces.mp4` (1,000 MPS steps, synchronized body motion and raw loads). The other local renders are `dist/videos-v04/hawa-flow-tools.mp4` and `dist/videos-v04/hawa-cylinder-wake.mp4`. They use actual recorded fields, native Rhino captures, Monad colors and captions. They have no audio. Watch the published [Tools video](https://youtu.be/GN6Ou3yOF_I) and [Wake video](https://youtu.be/zpRlRn9Qbf4).

Earlier published walkthroughs: [overview](https://youtu.be/Ji_9iOYXSXg), [block](https://youtu.be/PVBanKHGhC4), [historical Galapagos hull](https://youtu.be/0kVTmHttA78).

## Development

For NVIDIA hardware on Windows, see the [CUDA setup and repeatable verification workflow](docs/windows-cuda.md).

The production target is Python 3.9 with PyTorch 2.8.0, NumPy 2.0.2 and pydantic 2.13.5, because Rhino 8 embeds CPython 3.9. pydantic 2.13 is the last line for 3.9; [payload models follow four rules](docs/payload-schemas.md) that keep its known advisories unreachable. Every line of production code must import and pass on 3.9. Development uses three separate environments:

- `.venv` (Python 3.9) is the production-parity environment. Use it for the test suite, the function coverage gate, the scripts and everything else these docs run with `.venv/bin/python`. Its CI jobs are authoritative.
- `.venv-dev` (Python 3.12) is for developer tooling that needs newer Python: ruff's Python 3.9 syntax guard and the mutmut 3.7.0 mutation studies ([#67](https://github.com/range-et/hawa-cfd/issues/67)). CI also runs the full headless suite on 3.12, because mutation results on 3.12 are only valid while the tests pass there. Passing on 3.12 is never evidence that code works on 3.9.
- `.venv-reference` (Python 3.12, created by `scripts/bootstrap_reference.py`) runs unmodified upstream Lettuce for reference comparisons.

```sh
# .venv, Python 3.9 (from .python-version)
uv sync --extra test
# .venv-dev, Python 3.12, with the tools dependency group
UV_PROJECT_ENVIRONMENT=.venv-dev uv sync --python 3.12 --extra test --group tools
.venv-dev/bin/ruff check .
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

The Grasshopper build needs the installed Rhino SDK. Run `scripts/create_grasshopper_examples.cs` inside Rhino to create the `.gh` files. Use the nonblocking harnesses listed in [the verification matrix](examples/grasshopper/VERIFICATION.md); the original `verify_grasshopper_examples.cs` is historical and must not be run. Use `scripts/create_responsive_hull_example.cs` for the supported hull search. Preserve the historical user-modified example 09. Run `scripts/annotate_grasshopper_examples.cs` after regenerating supported definitions.

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

The headless Hawa suite runs in CI on every pull request, on Python 3.9 and 3.12; see [CONTRIBUTING](CONTRIBUTING.md) for the gates. The earlier vendored upstream run passed 419 tests with 884 skipped. The Lettuce compatibility engine remains unchanged by the new Hawa outlet and refinement modules.

The core CPU comparison matched the upstream oracle bitwise; MPS passed declared tolerances. All 16 upstream executable entrypoints completed bounded runs. These are separate from the Grasshopper gallery. PorousMedium's pointwise CPU/MPS discrepancy is repaired on main (HAWA-001, [#11](https://github.com/range-et/hawa-cfd/issues/11)) but not yet in a released package; the released 0.4 and 0.5 packages still have it.

Native MPS checks exercise saved definitions, valid field meshes, recording, a repeated hull search, and the fixed refinement patch. See the [release notes](docs/release-notes-v0.4.0.md) for exact evidence and limits.

Windows CUDA headless checks have a [numerical repair record](docs/verification-windows-cuda-fixes-2026-11-09.md) for PorousMedium parity and rotating-sphere surface-mask/torque failures. Clean Windows Rhino installation, full-duration upstream convergence and engineering-case validation remain open. Refinement is experimental. Aircraft analysis does not include XFOIL viscous calculations, VLM, stall or stability derivatives.

## Attribution

- **Hawa:** GNU GPL version 3 (`GPL-3.0-only`). Copyright (c) 2026 Hawa contributors. See [LICENSE](LICENSE).
- **Lettuce:** MIT license. The vendored source retains its original copyright and author notices.
- **Butterfly:** GPL-3.0+ workflow reference. Hawa contains no Butterfly code or assets.
- **Monad System:** MIT license. The website and videos use its pinned colors and styles.

See [the third-party notices](THIRD_PARTY_NOTICES.md) and [the Monad license](vendor/monad_system/LICENSE).

Development verification includes the required [G6 compatibility matrix and example coverage gate](docs/compatibility-matrix.md). Its finite inventory, actual device results and annotated workflow coverage are recorded separately from numerical validation.
