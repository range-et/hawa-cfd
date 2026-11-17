# Stationary mesh study bridge

This CPU-only asynchronous service accepts an arbitrary closed triangular mesh
from Rhino/Grasshopper in world metres. Geometry construction stays in ordinary
Grasshopper components. It reuses the existing stationary full-way BGK collector,
measurement contract and sequential sweep executor. A pressure-coloured surface
is a sampled field visualization; integrated force/torque comes from momentum
exchange. Surface pressure colours are not local traction or per-face force.

This is experimental workflow infrastructure. It does not repair the failed
wing grid/domain qualification or close [#40](https://github.com/range-et/hawa-cfd/issues/40).
See the [measurement contract](measurement-contract-v1.md).

## Wire contract

Submit through the existing `evaluate_submit` operation. All these top-level
keys are required; unknown keys fail admission:

```json
{
  "op": "evaluate_submit",
  "kind": "stationary_study",
  "device": "cpu",
  "case": {"shape": [81,101,61], "dx": 0.01, "speed": 1.0,
    "viscosity": 0.01, "density": 1.0, "mach": 0.03,
    "collision": "bgk", "solid": [], "origin": [-0.2,-0.5,-0.2],
    "basis": [[1,0,0],[0,1,0],[0,0,1]],
    "boundaries": ["inlet","outlet","slip","slip","slip","slip"]},
  "geometry": {"vertices_m": [], "triangles": []},
  "operating_points": [{"angle_deg": -3.0, "speed_m_s": 1.0},
                       {"angle_deg": 3.0, "speed_m_s": 1.0}],
  "references": {"area_m2": 0.15, "chord_m": 0.25333333333333335,
                 "pressure_pa": 0.0},
  "pivot_world_m": [0.075,0,0],
  "probes": [{"probe_id": "upstream", "position_world_m": [-0.1,0,0.1]}],
  "settling_steps": 3000,
  "sample_steps": 201,
  "stationarity_tolerance": 0.05,
  "case_id": "caller-owned-stable-case-id",
  "generation": 0
}
```

The empty geometry arrays above are placeholders, not an executable example.
Supply a consistently oriented closed manifold with positive signed volume,
nondegenerate triangles, and two lattice spacings of clearance at every domain
face. Rotation is right-handed about world +Y and the supplied pivot; positive
angle raises the leading edge relative to trailing edge in +X flow. Reference
area/chord stay fixed across points. Each speed gets its own physical timestep;
source windows use exactly settling through settling+samples−1 inclusively.
Probes are fixed world-space fluid probes; attached surface taps are excluded.

Base cases must have no solids, identity basis and physical uniform BGK physics.
Case origin is in world metres; spacing, when present, must equal dx. Host
adapters normalize a Rhino-unit case origin by dx/spacing before submission.
The only accepted case keys are shape, dx, spacing, speed, viscosity, density,
mach, collision, boundaries, solid, origin, basis, initial_velocity,
memory_limit_mb and reference_pressure. The service rejects accelerator requests,
curved boundaries, moving bodies, mapped inflow, neutral flow and refinement.
No implicit backend fallback occurs.

Admission bounds are 500,000 cells/case, 26,000 input vertices, 52,000 input
triangles, 64 candidates, 256 probes and 100,000 solver steps/candidate. Across
all cases retain at most 1,500,000 field cells, 100,000 total body/probe rows,
200,000 vertices and 400,000 triangles. Minimum sample count is four. These are
allocation bounds, not runtime promises.

## Polling, selection and ownership

`evaluate_control` uses existing `job` and `action` pause/resume/cancel/close.
Pause during preparation uses cooperative checkpoints; a solve pause reports
`pausing` until the candidate worker observes it. Cancellation drains before
releasing results and never publishes partial selected fields.

`evaluate_poll` accepts `job`, and optionally `selected_candidate` (zero-based
index). Without selection it returns only bounded records/plot segments and
progress. The ordinary job envelope retains job/key/state/steps/target/error;
steps/target count terminal/total candidates, not solver timesteps. Progress is
available while running. A completed job result contains `records`, `plots`
(`cl_alpha`, `cd_alpha`, `cl_cd`); requesting selection adds `selected`:

- candidate, identity, geometry (rotated world-metre mesh), device and dtype;
- complete `load_samples` and `probe_samples`, summary and quality;
- actual session, capture phase and provenance;
- `frame`, an existing immutable Field Snapshot descriptor, or null if no field
  was produced; no raw field arrays cross the poll bridge.

Records keep rejected/failed cases and reasons; plots split at unusable cases.
Each record has CM (pitching moment coefficient) only for a completed usable
case; its value is null while running or for a rejected/failed/cancelled case.
Selected histories are bounded but larger than progress: adapters should request
selection when needed, not on every running poll. Selected geometry, loads and
field share the candidate and generation identity. Field iteration/time are the
last captured pre-reflection source state (steps−1), not the final post-step
solver state. Frame case metadata adds physical_dx and the declared pressure
reference for existing field views; identity.case_hash names the original exact
solver case, before view metadata enrichment.

Field arrays are registered on the background worker in the existing 256 MiB,
16-frame cache. Normal cache eviction can expire a view; close removes every
still-resident frame owned by the study. A study creates no global solver
session and retains no filesystem artifacts. Worker exceptions drain active
solver handles; close/cancel never blocks the UI while waiting for a thread.

## Verification scope

`tests/test_stationary_study.py` exercises a real CPU cube study, exact
field/load/probe source attribution, standard field-query compatibility,
rotation and physical timestep changes, input budgets, cancellation during
preparation and solving, pause acknowledgement, control/serialization races,
fault draining and frame cleanup. The existing voxelizer recipe tests exercise
the moved production helper unchanged in algorithm. Live GH scheduling and
Rhino mesh/loft behavior remain separate host verification gates.

The G6 finite inventory adds 33 stationary-study rows: the Cartesian product of
±10° angles, 0.5/1 m/s speeds, valid/invalid selection and CPU/MPS/CUDA requests,
plus open-mesh, rotated-domain and cancellation rows on each requested backend.
Unsupported MPS/CUDA rows execute CPU-independent admission checks even without
that hardware; they are rejection evidence, not device numerical verification.
