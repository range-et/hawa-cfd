# OpenFOAM control dictionary references

These snapshots preserve the input bundle and nine generated OpenFOAM files from
`results/openfoam/controls/channel_poiseuille_ny10` and `cavity_re10_n32`, the
November 23, 2026 macOS OpenFOAM v2606 runs reported in
`docs/verification-openfoam-controls.json`. Each file was checked against its
original `bundle/manifest.json` SHA-256 before copying. Both cases passed
`checkMesh` and converged in `simpleFoam`. Cavity's Hawa/OpenFOAM comparison
remains diagnostic, not an accuracy pass.

The test checks the emitted dictionaries against these previously executed
artifacts so that token/value changes in the generator cannot pass merely because
some substrings still exist. Review intentional dictionary changes against a
fresh OpenFOAM run before refreshing these references. The independent physical
recipe and translated-face tests cover parameter variation separately.
