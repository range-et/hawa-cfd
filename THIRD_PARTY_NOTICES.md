# Third-party notices

Hawa original code is licensed under GNU GPL version 3 (`GPL-3.0-only`).
Copyright (c) 2026 Hawa contributors. See `LICENSE`. Third-party code and assets
retain the licenses listed below. Earlier MIT releases retain their original terms.

## Lettuce — numerical engine (MIT)

Hawa includes a modified Python 3.9 compatibility fork of Lettuce:
https://github.com/lettucecfd/lettuce
Upstream commit: `88a6559def2a49fd7f425fd05954ec1e3db2cdb6`.

Original copyright: **Copyright (c) 2019, Andreas Kraemer**.
Original authors: Andreas Kraemer, Mario Bedrunka, Philipp Spelten, Dominik Wilde,
Robert Fritsch, Maximilian Bille, and Martin Kliemank.

The original MIT notice is preserved verbatim in `vendor/lettuce/LICENSE`, and is
included as `licenses/lettuce/LICENSE` in the plugin distribution. Author credits,
upstream revision, provenance hashes and a description of modifications accompany
it. The original package, tests and examples retain their upstream notices.

For academic use, upstream requests citation of:
Bedrunka et al. (2021), **Lettuce: PyTorch-Based Lattice Boltzmann Framework**,
High Performance Computing: ISC High Performance 2021 International Workshops.
Preprint: https://arxiv.org/abs/2106.12929

## Butterfly — workflow and API reference (GPL-3.0-or-later)

https://github.com/ladybug-tools/butterfly
Reference revision: `c8fc0bbe317bb41bfe5f28305782a82347b8c776`.

Butterfly is developed by Ladybug Tools and its contributors. Its repository
declares **GPL-3.0+**, not MIT. Hawa acknowledges its case/domain/geometry/boundary/
solution/sampling workflow as a design reference. Hawa does not include Butterfly
source code, icons or other assets in its Python package or plugin distribution.
The local reference checkout is ignored by Git and excluded from packages.

## Runtime dependencies

PyTorch, NumPy, Matplotlib, h5py, and other Python dependencies retain their own
licenses; they are not all MIT. Rhino installs their original distributions,
including their license files, using the pinned requirements. Hawa's plugin zip
contains Hawa/Lettuce Python source, not redistributed third-party binary wheels.
`requirements/rhino-py39.txt` records the locked dependency versions.

Rhino and Grasshopper are McNeel products. Their proprietary assemblies are
referenced from the user's Rhino installation and are not bundled with Hawa.
The plugin uses the System.Drawing.Common reference package for compilation;
runtime graphics assemblies are supplied by Rhino, not bundled in the zip.

Hawa is an independent project. These credits do not imply endorsement by the
upstream projects or their authors. Future inclusion of third-party source/assets
must preserve the applicable license and attribution rather than assuming MIT.

## Monad System

The website uses the generated Monad CSS. The website assets and video renderer use its palette.

- Source: https://github.com/range-et/monad_system
- Commit: `358d0559da407897957a5817b24f9ebd8774b791`
- License: MIT
- Copyright (c) 2025 Indrajeet Haldar

The full license is in `vendor/monad_system/LICENSE`. The static website also includes it at `assets/monad/LICENSE.txt`.
The Hawa layouts and video renderer use the supplied tokens. The original Rhino screenshots retain their captured interface colors.

## Additional design and numerical references

Autodesk Flow Design documentation, the OpenFOAM Foundation development repository, and the linked XFLR5 repository inform the expanded visualization, geometry and aircraft-analysis scope. No code, icons or assets from those projects are included in this development change. Their availability does not imply an MIT license.

The stationary wall-link method follows the linear interpolated bounce-back method of Bouzidi, Firdaouss and Lallemand (2001), Physical Review E 64, 046301. Hawa implements the formulas independently; validation limits are recorded in the 0.4 development notes.

The fixed 2:1 refinement implementation uses cubic reconstruction and filtered nonequilibrium restriction described by Lagrava, Malaspinas, Latt and Chopard (2012), Journal of Computational Physics 231, DOI 10.1016/j.jcp.2012.03.015. The formulas are independently implemented. The method is experimental and does not provide exact finite-volume refluxing.
