# Saved CPU wing-sweep example

Open [report.html](report.html) in a browser. It is a self-contained saved result
from two actual CPU runs on November 17, 2026; no server, JavaScript, network,
Rhino license or solver is needed to view it. Orange points and case IDs link to
the corresponding geometry, force/probe histories, retained pressure slice and
source identity. Expand the metadata beneath each case for references, the
measurement window and quality diagnostics.

**This is an experimental software demonstration, not qualified aerodynamics.**
The predeclared grid/domain sensitivity gate fails. The synthetic viscosity,
coarse staircase wing and confined boundaries do not represent real-air wing
performance. Lines only connect the two requested cases; they are not a validated
polar or interpolation model. Histories include the initial transient, while
coefficients use the declared final 64-sample window. Pressure is gauge pressure;
solid and boundary nodes are blank. Field panels use per-case colour limits.

## Generate a fresh report

From a developer checkout with its Python 3.9 `.venv` installed:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m scripts.wing_sweep_report --output /absolute/new-wing-report.html
```

Choose a new path in an existing folder. Existing files are never overwritten.
The command runs two fresh CPU float32 sessions sequentially and drains their
workers before writing. It is a blocking developer command, **not** code to run
on Rhino's UI or Grasshopper's solution thread. A timeout cooperatively cancels;
it cannot forcibly interrupt a numerical step. A nonzero exit retains the report
with rejected/failed/cancelled cases visible and gaps in the coefficient plots.

The frozen demo uses NACA 2418 at the root and 0018 at the tip, full span 0.6 m,
chords 0.3/0.2 m, angles −3°/+3°, speed 1 m/s, density 1 kg/m³ and kinematic
viscosity 0.01 m²/s. Each mesh is independently voxelized on a 33×41×25 grid
with 0.025 m spacing. Each case takes 1000 settling steps then 64 measured steps.
The final retained field is at source step 1063 / 0.4602925021 s, after collision
and before obstacle reflection/streaming; it is not a step-end capture.

The stored report's CL values are 0.1312022747 and 0.1737013760; CD values are
1.3315546401 and 1.3287346632. These are provenance checks, **not acceptance
thresholds or engineering predictions**. Exact case/session identities and
quality outcomes are embedded in the report. Other machines may differ within
an independently reviewed device policy; this example supports explicit CPU only.

## Scope still open

The HTML is a viewing artifact, not a checkpoint; it cannot resume a simulation.
Native checkpoint viewing/resume belongs to the separate native saved-data
workflow. This example does not add a public GH node or archive.

Stationary load/probe histories cannot be relabelled as the current shared
moving-body CSV: they have different capture phase, body/frame/moment semantics
and per-sample validity/quality. A reviewed producer adapter to the existing
interchange service remains in [#40](https://github.com/range-et/hawa-cfd/issues/40),
along with the GH workflow and numerical qualification. No parallel CSV format
is created here.

[Run contract](../../docs/headless-wing-sweeps.md) ·
[Measurement contract](../../docs/measurement-contract-v1.md) ·
[Review](../../docs/review-wing-report-example.md)
