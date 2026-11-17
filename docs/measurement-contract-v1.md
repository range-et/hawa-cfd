# Measurement contract v1 — frozen CPU/headless foundation

Frozen November 17, 2026 for issue #40 on base `12dc774` by Codex (self-review).
Schema tag: `hawa-measurement-1`. This is an internal producer/analysis contract,
not an export format, public node, engineering-accuracy claim or new case schema.
Changes to these semantics require an explicit version/compatibility review.
The canonical manufactured fixture is
[measurement-v1.json](../tests/fixtures/measurements/measurement-v1.json).

## Audit and isolation

`optimization.MeasuredBounceBack` measures aggregate full-way obstacle force,
using `2*f_i*e_i` on solid/fluid links before streaming. It has no per-body
attribution or torque. `walls.install_interpolated_walls` has a different force
path. Moving-body loads include moving-boundary transition accounting and must
not be repurposed as stationary force data. Existing paths stay unchanged.
`Sample` and `sample_arrays` supply field samples; display reconstruction is not
wall traction. `Wing Analysis` is LLT, not CFD.

The active #35 branch owns exports.py, export schemas, native panel and shared
export adapters. Read-only audit on November 17 finds its draft probe table uses
lattice coordinates and its draft load table uses moving-body histories with
domain-axis forces/torques and world pivots. Those interfaces are unmerged and
not frozen here. #40 neither changes them nor invents a CSV writer. A later
adapter must explicitly transform units/coordinates and preserve identity;
never pass stationary data into the moving-body export path. Reconcile after
#35 lands. This boundary permits independent implementation now without claiming
that exporter integration is complete.

## Supported foundation and resource limits

The first stationary collector accepts only explicit CPU, a physical 3D uniform
D3Q19 BGK case, full-way bounce-back obstacles, and legacy inlet/outlet plus
paired periodic/slip/wall faces. Reject examples/normalized units, curved wall
links, moving bodies, boundary sets, neutral flow, mapped boundaries and refinement.
No fallback from another backend or wall model. Validate before constructing a
session. Force calculations use the solver's dtype, reduction/analysis float64;
report both. CPU float32/float64 are implementation checks, not device parity.

At most 4 named bodies, 500000 grid cells, 256 probes, 100000 retained samples
per body/probe, 64 sweep candidates, 100000 solver steps per candidate. Body
solid-index sets must be nonempty, unique, disjoint, and their union must equal
the case obstacle set. Reject differently named bodies touching along any
D3Q19 link; each obstacle must have at least one lattice-node layer of clear
padding at every domain face. Group mesh inputs into one ID before voxelization
when one physical body is desired. This module does not implement CAD union.
Bounds are development limits, not performance promises. The per-case grid cap
was increased from 150000 to 500000 for the finer CPU example after the
[resource/lifecycle pilot](wing-fine-report-protocol.md); aggregate retained-sweep
budgets and all other guards remain unchanged.

## Request shape (all keys required unless explicitly optional)

`schema`; `identity` with nonempty `case_id`, `candidate_id`, `case_hash`,
`geometry_hash`, and nonnegative integer `revision`, `generation`; `references`
with positive finite `density_kg_m3`, `speed_m_s`, `area_m2`, `chord_m`, finite
`pressure_pa`, and unit vectors `drag_axis_world`, `lift_axis_world`; `bodies`
with unique nonempty `body_id`, `moment_origin_world_m` vector; `window` with
nonnegative `start_s`, positive `end_s > start_s`, integer `minimum_samples >= 4`
and finite nonnegative `stationarity_absolute_coefficient_tolerance`.
`load_axis_world` is an optional unit vector (default drag axis).
Reject unknown keys, coercive numeric strings/booleans, NaN/Inf, nonorthogonal
or nonunit axes and ambiguous identity. Request collections follow the bounds
above. Validate Python payloads with pinned pydantic BaseModel, extra=forbid;
no JSON-mode model validation or dumping defaults into existing case specs.

All vectors in this contract are world-coordinate SI vectors. Domain basis rows
are orthonormal, right handed: world vector = domain vector @ basis;
world point = origin_world_m + domain_point_m @ basis. Body orientation/pivot
is recorded by the candidate geometry producer; a point attached to a body is
transformed once with that same rigid transform. Positive drag follows fluid
inlet velocity; positive lift follows the user-specified perpendicular axis.
side_axis = cross(lift_axis, drag_axis). Do not take absolute values of loads.
Positive angle in the wing recipe raises the leading edge relative to trailing
edge for flow +X, span +Y, up +Z (right-hand +Y rotation of LE→TE chord).

## Sample shape and reductions

Each sample has `schema`, exact matching `identity`, `body_id`, nonnegative
integer `step`, finite `time_s >= 0`, `force_world_n` and
`torque_world_nm` about the request body's stated moment origin, `valid` bool,
`reason` (empty iff valid), and `quality` = `accepted`, `warning` or `rejected`.
Valid vectors are finite triples. Invalid vectors must be null (not zeros).
Rejected-quality samples cannot produce usable coefficients. No synthetic
session identity is invented: future live collector adds its actual session ID
and capture identity in a versioned result envelope, separate from these inputs.
`time_s` and window endpoints are elapsed physical seconds since this candidate's
initial state. They are not wall-clock or absolute source time; a future export
adapter must preserve any case time origin separately rather than add it twice.

Samples per body strictly increase in step and time. The measurement window is
inclusive [start_s, end_s]; require endpoint coverage within relative 1e-9 and
absolute 1e-12 seconds, at least minimum_samples, and uniform time spacing within
those tolerances. No interpolation, silently dropped invalid samples, truncated
history or invented averaging. For this fixed-dt foundation, equal-weight mean
and population standard deviation (ddof=0) are declared; a varying-dt series
rejects. Each half-window must contain at least two samples. Stationarity is
max absolute difference of first/last-half mean [CD,CY,CL] against the explicit
absolute coefficient tolerance, splitting samples at n//2. It is a diagnostic,
not a turbulence/convergence certificate. Warning samples remain labelled;
rejected/invalid samples or inadequate windows reject usable results.

q = 0.5*rho*U^2; [D,Y,L] = dot(F,[drag,side,lift]);
[CD,CY,CL] = [D,Y,L]/(q*S); Cm = dot(M,side)/(q*S*chord).
Moment translation: M(new) = M(old) + (old_origin-new_origin) cross F.
The signed load-cell value is dot(F,load_axis). Fluctuation standard deviation
is not a confidence interval. Return window/count/references/identity with means,
standard deviations and stationarity pass/fail; do not call unsteady data steady.

Full-way stationary link transfer is 2*f_i*e_i at the solid node, excluding
solid-solid and domain-boundary links. Physical force scale is
rho_pu/rho_lu * dx^4/dt^2. Use halfway fluid/solid link locations for torque:
x_wall = x_solid - e_i*dx/2. Sum cross(x_wall-origin, link_force).
Do not infer shear/pressure decomposition from this total momentum transfer.

## Pressure probes

Probe descriptor: unique `probe_id`, `position_world_m`; optional `body_id`,
`surface_point_world_m`, `outward_normal_world`, positive `offset_m` together.
A surface tap's actual position must equal surface_point + offset*normal.
Use an injected sampler in headless tests; never silently shift invalid probes.
Return actual position, valid/reason, pressure_pa and Cp (null if invalid),
identity and capture time. Pressure is solver gauge Pa; reference pressure is
in the same gauge. Cp = (p-pressure_pa_reference)/q. No absolute atmospheric
pressure implied. Surface samples remain explicitly approximate.

## Sweep contract and module boundary

`hawa.sweeps.SweepController` owns an ordered list of <=64 candidate descriptors:
`candidate_id`, `angle_deg`, positive `speed_m_s`, `geometry_hash`, `case_hash`.
Each candidate ID is unique; hashes are opaque nonempty provenance identifiers
in unit fixtures and SHA-256 in production. Actual geometry/config hashes must
be recomputed after each transform, never copied from another angle/speed.
Controller receives an injected executor with start(candidate, generation),
poll(handle), pause(handle), resume(handle), cancel(handle), close(handle).
Polling returns state, candidate_id, generation, optional result/reason.
States: queued/running/paused/completed/failed/cancelled/rejected. No blocking
loops, threads or solver sessions inside the controller. One active handle,
start only on explicit run, at most one start/poll action per tick. Pause blocks
new starts; cancel marks pending candidates cancelled and cooperatively drains
active cleanup. Close failure retains ownership for retry; next candidate cannot
start until prior handle closes. Exceptions become failed records and cleanup
requests. Stale candidate/generation results never publish. Duplicate ticks
cannot double-publish/start. Configuration edits create a new controller;
saved descriptors reopen idle, never restore live handles.

An executor completion is not automatically a valid aerodynamic result. Usable
plot values require matching candidate identity, accepted quality and a passing
measurement window/stationarity assessment. Rejected/failed/cancelled points
retain explicit terminal records and null plotted ordinates. Plot helpers emit
ordered segments split at gaps (CL-alpha, CD-alpha, CL-CD), never connect over
failures. Selection retains candidate identity for later field lookup.
A/B may add ergonomic methods, but cannot change these transition semantics.

## Independent fixtures and validation boundary

The manufactured force fixture has rho=2, U=3, S=4, chord=2, F=[36,0,72],
M=[0,18,0]: q=9, CD=1, CL=2, Cm=0.25. Constant 4-sample data has zero
fluctuation/stationarity drift. A pressure sample of 118 Pa against reference
100 Pa gives Cp=2. A moment reference moved +X by 1 m changes My from 18 to
90 N m. These are algebra assertions, not simulated aerodynamic results.

Numerical follow-up: creeping-flow sphere force (Stokes 6*pi*mu*R*U) is a
candidate analytic load gate requiring finite-domain/grid corrections and a
predeclared protocol. Candidate wing reference: NACA RM L52G18, rectangular
NACA0012 wings AR 1/2/3 and Re 0.4–3 million, NASA NTRS 19930087204.
The wing/reference lane must inspect geometry, tunnel corrections, digitization
and computational feasibility before freezing numerical tolerances. Its high Re
must not be imitated by increasing viscosity. No reference solve, wing drag
accuracy or G3 physical qualification is authorized/claimed by the schema freeze.
This research prerequisite remains open; pure software lanes may proceed against
manufactured fixtures without waiting for expensive physical studies.

## Lane ownership and this round

A: new measurements.py, stationary_loads.py and dedicated tests/schema snapshots.
B: new sweeps.py and dedicated tests. C: example-only recipe/data/guide and tests;
no public geometry service, no generated GH archive without live verification.
Integrator: this contract, combined fixtures/review, CPU runner and measurement
matrix. Do not modify plugin.py, jobs.py, exports.py, fields.py, existing host
adapters or their tests. No Rhino/MCP, MPS/CUDA, plugin install, heavy parallel
suite or mutation runs. Each worktree has local envs/import paths; OMP/MKL threads
limited to 1. Focused CPU checks first; full CPU-only suites and measured gate
run serially at integration. The CPU-only pytest availability shim means device
checks are skipped, not qualified. User's CPU/headless restriction overrides live
host execution for this round; record G4/device omissions, keep #40 open.

## Implementation clarifications from cross-review (November 17)

A clear padding node means fluid, not a wall/slip domain boundary node. The
collector rejects obstacle links whose source is such a boundary node, even
when the obstacle index itself is inside the domain. Actual flow specification,
mask, stencil and physical units must match the declared collector inputs.
The existing full-way callback observes pre-stream populations; raw collector
records therefore expose `source_step`/`source_time_s`. A later adapter must
retain that phase and cannot relabel those loads with a later field capture.

The sweep executor's `close(handle)` returns False while cleanup is pending and
True/None only when resources are released. Exceptions retain ownership for
retry. `start` must either return its handle synchronously or fail without
leaving resources; asynchronous submission requires a future ownership adapter.
Minimal callback identity is validated before discarding old generations, so a
malformed obsolete result cannot cancel the current job.
The future runtime owner must allocate a fresh generation when replacing a
controller and scope executor handles to that generation. Reusing the default
standalone generation across live replacements cannot establish stale-result
isolation and is not a supported production adapter strategy.

The NASA wing-reference audit and finite-domain limitations of the initial
Stokes candidate are recorded in the [wing example guide](wing-measurement-example.md).
Neither supplies a completed physical-qualification protocol for this round.

## Real CPU executor increment (November 17)

The opt-in `hawa.sweep_executor.CpuSweepExecutor` now implements this controller
interface with fresh private CPU float32 Sessions. It accepts fully prepared
candidates with final mesh/case hashes, frame, ownership, request, probe and
step-budget inputs. The scalar measurement/sweep payloads above are unchanged.
Detailed results use `hawa-cpu-sweep-result-1`, including actual session identity
and explicit `after-collision-before-obstacle-reflection-and-stream` capture
phase. Pressure and loads share that phase; later post-step quality is retained
separately. Results survive confirmed handle close.

Admission binds the external world frame to the hashed case's physical frame.
It limits the whole sweep to 100000 retained load/probe rows, 1500000 field
cells and 200000 geometry vertices/400000 triangles. Float64 is rejected by
this adapter because the unchanged Session constructor uses float32. These
are private CPU implementation limits, not new public solver capability claims.
The wing recipe voxelizes meshes; the executor trusts that internal preparation
boundary and does not recompute arbitrary mesh-to-mask equivalence.

[Operation and limitations](headless-wing-sweeps.md) ·
[Fresh integration evidence](review-real-headless-sweeps.md). Export and host
adapters remain independently owned and are not wired by this increment.
