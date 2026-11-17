# CPU headless wing sweeps (#40)

This development path runs the real stationary BGK solver through the measurement
and sweep contracts. It remains experimental: completing a coarse sweep does not
validate wing lift or drag. Export, Rhino/GH adapters and public nodes are outside
this increment.

## Run the example

From the repository's Python 3.9 environment:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m scripts.run_wing_sweep
```

The example uses two different root/tip airfoils (NACA 2418/0018), a full-span
closed loft and explicit −3°/+3° rotations. Each transformed mesh is voxelized
independently. The default domain is 33 × 41 × 25 at 0.025 m spacing, with
synthetic kinematic viscosity 0.01 m²/s, density 1 kg/m³ and speed 1 m/s.
These settings demonstrate the software workflow; they do not represent a
qualified real-air test. The coarse full-way wall remains a lattice staircase.

The command prints a compact internal JSON console report with ordered terminal
records, identified CL–angle/CD–angle/CL–CD plot segments and cleanup counts. It
returns nonzero if any candidate fails, rejects or cancels. Failed quality or
stationarity is preserved as a gap; the driver does not relax criteria to draw
a curve. This is not a new CSV or shared export format.

Controls are `--settling-steps`, `--sample-steps` (at least four),
`--stationarity-tolerance` (absolute coefficient change) and `--timeout` seconds.
Defaults are 1000 settling steps, 64 samples and tolerance 0.05. Both demo
candidates passed this diagnostic in the recorded CPU run; this is not a
grid/domain/time convergence study. The initial 10/8 and 200/32 attempts
retained rejected stationarity results; no criterion was relaxed. A timeout requests
cooperative cancellation and waits for resource cleanup; it cannot kill a
numerical step or guarantee a hard wall-clock exit deadline.

## Python composition

This example driver is not a public node. The source is
[run_wing_sweep.py](../scripts/run_wing_sweep.py):

```python
from scripts.wing_solver_recipe import demo_sweep
from scripts.run_wing_sweep import prepare_entries, run_prepared

recipe = demo_sweep()
entries = prepare_entries(
    recipe, settling_steps=1000, sample_steps=64, tolerance=0.05,
    case_id='my-wing-study', generation=1,
    probes=[{'probe_id': 'upstream', 'position_world_m': [-0.1, 0., 0.1]}])
report = run_prepared(entries, timeout_s=120.)
```

`report['details']` retains load and pressure histories, window summaries,
source quality, the last captured field and the actual session ID for each
started candidate. It is a detached Python result, including NumPy field arrays;
the console report omits these large details. An unstarted candidate has no
fabricated detail result. Pressure probes retain invalid/outside/solid states.
Surface taps require an explicit world surface point, normal and offset; the
caller must transform body-attached inputs with the candidate geometry.

For custom wings, `prepare_sweep(wing_parameters, operating_points, domain, fluid)`
in [wing_solver_recipe.py](../scripts/wing_solver_recipe.py) prepares the cases.
Operating points are explicit angle/speed pairs. The domain uses world-aligned
axes; the executor separately supports a declared orthonormal world basis.
Case hashes cover the final solid indices and domain frame, geometry hashes
cover actual transformed vertices/triangles, and reference area/MAC remain fixed
through angle changes. `prepare_entries` converts declared settling/sample step
counts into exact physical source-time window endpoints for each speed.

## Execution and capture semantics

The executor constructs each fresh private CPU float32 `Session` in one owned
worker. It never registers a global session and never calls the solver's
blocking pause method. Polling/control methods signal or inspect the worker;
pause acknowledges at a step boundary. Cancellation wakes paused workers and
prevents new candidates. Close returns pending until the worker has exited;
results remain readable after confirmed close. Controller descriptors reopen
idle. A replacement live owner must allocate a fresh generation.

Both pressure and load observations occur **after collision, before obstacle
reflection and streaming**. The result records this phase, source step, elapsed
physical time and actual session ID. It must not be relabelled as a later
post-step field snapshot. Solver quality is checked at capture and after each
step, including sticky warnings/rejections. Accepted quality is an implementation
envelope check, not evidence of convergence or physical accuracy.

The collector's solver/body restrictions still apply; the per-case grid cap is
now 500000 cells after the [fine-report resource pilot](wing-fine-report-protocol.md). Across a sweep,
admission additionally caps retained body/probe rows at 100000, total field
cells at 1500000, and geometry at 200000 vertices/400000 triangles before
copying inputs. Prepared mappings are an internal trusted adapter boundary:
hashes bind both mesh and final case, but arbitrary mesh-to-mask equivalence
is not independently recomputed by the executor. The wing producer performs
that voxelization. The executor rejects
non-float32 storage rather than rebuilding a different solver silently. It uses
only explicit `cpu`; there is no backend auto-selection or accelerator fallback.
Preparation and this blocking command-line driver belong off a UI thread.

[Measurement contract](measurement-contract-v1.md) ·
[Foundation evidence](review-measurement-foundation.md)

## Sensitivity limit

The November 17 CPU study passed its stationarity checks but failed its
predeclared grid/domain screen: medium-to-fine CL changed 0.023672, and the
larger domain changed CL 0.075670 and CD 8.21%. These curves remain workflow
demonstrations, with resolution/domain qualification open. See the
[protocol](wing-cpu-sensitivity-protocol.md) and
[review and raw evidence](review-cpu-sweep-validation.md).

The [controlled follow-up](review-worker-and-wing-diagnosis.md) identifies strong
vertical-boundary and coarse body-sampling sensitivity. Longer settling does not
remove the domain gap. No physical qualification or tolerance relaxation follows.

## Saved, clickable example report

Run `scripts.wing_sweep_report` to produce the self-contained HTML viewing
artifact described in [the saved example](../examples/headless-wing/README.md).
A real two-case CPU report is included. Its three coefficient plots link to exact
candidate mesh, raw histories, retained field and provenance. It does not resume
sessions or create a second CSV format; the shared exporter/host integration and
failed numerical qualification remain open in #40.
