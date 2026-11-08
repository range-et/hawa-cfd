Hawa runs a GPU lattice Boltzmann solver inside Rhino 8 and Grasshopper. This release is an experimental prototype.

## Downloads

- **Hawa-0.2.0-rh8.zip:** the plugin, Python source, eight editable definitions, and license notices.
- **Hawa-walkthrough-captures.zip:** seven original UI captures and a shot list.
- **hawa-first-look.mp4:** the Hawa overview. Duration: 57 seconds.
- **hawa-block-workflow.mp4:** the block-flow example. Duration: 68 seconds.
- **Hawa-YouTube-upload-kit.zip:** both videos, thumbnails, titles, descriptions, and license notices.

The videos use captions and screenshots from verified Rhino runs. They have no audio. The edits use Monad colors and Helvetica titles.
The slides contain no added header bars or title rules.

## Install

1. Copy the complete Hawa folder into Grasshopper's Libraries directory.
2. Restart Rhino 8.
3. Open a supplied example.
4. Allow Rhino to install the pinned dependencies.
5. Select a backend.
6. Toggle Run to start the solver.

## Verification

CPU and MPS checks passed on this Mac. Eight saved Grasshopper graphs reopened and completed 25 MPS steps with valid slice meshes.
The visible vortex run completed 200 iterations. The block run completed 300 iterations.

The embedded session used CPython 3.9.10, PyTorch 2.8.0, and NumPy 2.0.2.

## Open checks

- NVIDIA CUDA hardware.
- Windows installation.
- Full-duration example convergence.
- Problem-specific CFD validation.

The block uses a demonstration viscosity of 0.1 m²/s. Atmospheric validation remains open.
The gallery contains eight definitions. Wrappers for the remaining upstream examples remain open.
PorousMedium has a known pointwise CPU/MPS discrepancy in the bounded run.

Hawa and Lettuce retain their MIT notices. Monad System supplies the visual tokens under the MIT license.
Butterfly informs the workflow under a GPL-3.0+ reference. Hawa contains no Butterfly code or assets.

Project: https://range-et.github.io/hawa-cfd/
Guide: https://github.com/range-et/hawa-cfd/blob/main/docs/plugin.md
Notices: https://github.com/range-et/hawa-cfd/blob/main/THIRD_PARTY_NOTICES.md
