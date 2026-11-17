# Saved CPU wing-sweep example

Open [the finer report](report.html): **81×101×61 = 499041 cells, 0.010 m spacing**.
It contains two actual CPU runs from November 17, 2026. The report is a
self-contained viewing artifact: no server, JavaScript, network, Rhino license
or solver is needed to open it. Orange points and case IDs link to the actual
candidate mesh, force/probe histories, retained pressure slice and source
identity. Expand each case's metadata for the grid, references, physical
averaging window and quality diagnostics.

**Finer does not mean qualified.** The fixed geometry and physical domain now
have 2.5 times finer spacing than the original demonstration, but the measured
lift remains sensitive to grid resolution. Synthetic viscosity, full-way
staircase walls and confined boundaries do not represent qualified real-air wing
performance. Lines only connect requested cases; they are not a validated polar.
Histories include settling; coefficients use only the declared averaging window.
Pressure is gauge pressure; solid/boundary nodes are blank, with per-case colour
limits. Loads are whole-body fluid force, not per-face pressure forces.

## Matched-time coarse comparison

[Fresh coarse report](report-coarse.html) uses 33×41×25 cells at 0.025 m.
Both grids measure **0.5196152423…0.5542562584 s**: coarse source steps
1200…1280 and fine steps 3000…3200. Geometry, fluid, domain extents, reference
area/chord and the 0.05 stationarity criterion are unchanged. All four candidates
completed with usable windows and zero owned resources after cleanup.

| Angle | Coarse CL | Fine CL | Absolute CL change | Relative CD change |
| --- | --- | --- | --- | --- |
| −3° | 0.11884614 | −0.00895032 | **0.12779646 — fails 0.02** | 1.2603% — within 5% |
| +3° | 0.16107180 | 0.27610434 | **0.11503255 — fails 0.02** | 0.1046% — within 5% |

Relative CD uses the fine-grid magnitude as denominator. These are bounded
screening criteria, not engineering error bars. This two-grid comparison also
does not establish the original three-grid monotonicity or domain-independence
gates. The [original shorter coarse report](report-coarse-1000.html) is retained
for history; its 1000…1063 window is **not** used for this comparison.

## Generate a fresh report

From a developer checkout with its Python 3.9 `.venv` installed:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m scripts.wing_sweep_report --output /absolute/new-wing-report.html
```

The default selects the fine grid, 3000 settling steps and 201 samples. This
recorded two-case fine run took about **20.3 minutes** on a 48 GiB Mac; the full
fine/coarse study took 21.1 minutes, with at most 769 MiB sampled process RSS.
Runtime is machine-dependent. To explicitly select the quick coarse comparison:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m scripts.wing_sweep_report --coarse --output /absolute/new-coarse-report.html
```

Choose a new path in an existing folder; existing files are never overwritten.
There is no silent coarse fallback. Each fresh CPU float32 session is sequential
and workers drain before writing. The one-hour default timeout requests
cooperative cancellation; it cannot forcibly interrupt a numerical step.
A nonzero exit retains rejected/failed/cancelled cases and coefficient gaps.
This is a blocking developer command, not code for Rhino's UI or a Grasshopper
solution thread.

Both grids use NACA 2418 root / 0018 tip, full span 0.6 m, chords 0.3/0.2 m,
angles −3°/+3°, speed 1 m/s, density 1 kg/m³ and kinematic viscosity 0.01 m²/s.
Each mesh is independently voxelized. Captures occur after collision and before
obstacle reflection/streaming, not at step end. Exact case/session identities
are embedded in each saved report. This example supports explicit CPU only.

## Scope still open

The HTML cannot resume a solver and is not numerical CSV interchange. Native
saved-data viewing/resume is a separate workflow. Stationary pre-reflection
load/probe histories cannot be relabelled as the current moving-body step-end
CSV: their phases, frames, moment references and sample validity differ. A
reviewed shared exporter adapter and physical qualification remain in
[#40](https://github.com/range-et/hawa-cfd/issues/40); no parallel CSV is added.
The saved developer report alone does not establish GH/Rhino host acceptance.

[Run contract](../../docs/headless-wing-sweeps.md) ·
[Fixed fine-grid protocol](../../docs/wing-fine-report-protocol.md) ·
[Fine-run evidence](../../docs/verification-wing-fine-report.json) ·
[Review](../../docs/review-wing-report-example.md)
