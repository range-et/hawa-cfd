# Worker mutation and wing sensitivity diagnosis — #40

November 17, 2026. CPU/headless follow-up to
[the failed sensitivity screen](review-cpu-sweep-validation.md). Operator and
integrator: Codex root. Actual test/review contributors: agents `/root/sweeps`
(worker controls) and `/root/wing_example` (collector controls and independent
geometry/scaling review), each in an isolated worktree. The other chat confirmed
no heavy local checks were running and retained Rhino/export ownership.

## Software evidence

The worker controls now assert retained schemas and provenance after success,
pre-allocation failure and cancellation; actual capture/source/final quality;
matching-step but mismatched-time rejection; generation zero/one and coercive
lookalikes; physical frame tolerances with nonzero coordinates; geometry
validation even when its digest matches; and resource rejection before deepcopy.
The collector controls independently derive force/torque from prescribed impulses,
vary physical spacing/timestep/reference density, exclude internal body links,
and exercise per-body attribution, boundary padding and admission limits. The
force oracle no longer obtains its expected dimensional factor from collector.scale.
These mutation-driven controls close assertion gaps; a separately reproduced CPU allocation defect is described below.

Independent geometry tests compare signed-X-ray classification with triangle
solid-angle winding for all off-plane lattice nodes in the original three mesh
bounding boxes. They exercise both inside and outside classifications; all
triangle-plane ties are conservatively excluded. Separate tests verify equality
of world solid-node sets across the five aligned domain expansions. This does
not qualify arbitrary CAD, surface ties, hydrodynamic accuracy or a continuum mesh.

The final frozen study on merged main (`71cae35`, upstream `7cd7024`) has
**1,757 mutants, 1,564 assertion kills, 193 individually reviewed survivors and
233 passing controls**, with zero errors, timeouts or unchecked outcomes. The
exact [policy](../tools/mutation/stationary-executor-policy.json) passes against
`results/stationary-executor-mutation-main`; reviewed source hashes stayed unchanged.
Survivors cover diagnostic wording/labels, redundant guards/default inference,
unused private normalization fields and equivalent arithmetic. The torque-arm
shift along the impulse direction preserves its cross product, without a claim
about extreme floating-point rounding. One malformed non-dict budget input can
change exception class but still rejects before allocation; identical diagnostic
classes for unsupported inputs are not claimed. Completed/rejected/failed
publication races are now asserted before the worker's finally block.

An earlier strengthened study had 1,736 mutants, 1,474 kills, 260 survivors and
two timeouts: it was not accepted. Paused-worker test cleanup was corrected to
resume/cancel and drain the worker after a bounded control deadline; the clean
study above replaced it. Timeout limits and numerical tolerances were not relaxed.
Geometry algorithms, decorated validators, public adapters and physical accuracy
are outside this worker inventory. This is bounded assertion evidence, not an
exhaustive concurrency proof.

## CPU allocation defect (#120)

Mutation review prompted a direct CPU-collector regression under a non-computing
`torch.device('meta')` allocation trap. Before the repair, construction placed
link masks/arms/vectors on meta, or collection allocated force/torque accumulators
there and failed before publishing a load. Two new regressions failed while the
other 97 collector controls passed. The repair binds all these allocations to CPU.
The trap never executes an accelerator kernel. A thread control showed this
context did not propagate to a new worker, so failure of the current private
worker under that caller context is not claimed.

[#120](https://github.com/range-et/hawa-cfd/issues/120) tracks this reproduced defect
through merge. It is separate from the sensitivity failure: all original runs
already used CPU tensors. After the repair, a fresh 4881-step baseline replay has
**exactly equal complete load history, probe values and summary**, a fresh session,
accepted completion and zero owned resources (62.20 s). The machine evidence
binds this parity result to the repaired source and retains the earlier study's
original source hashes. No numerical tolerance changed.

## Controlled numerical investigation

[Protocol](wing-cpu-diagnostic-protocol.md) was committed at `d66d531` before
solves. Eight serial cases retain 4,881 pre-stream source observations each;
identical 81-sample windows start at source steps 1,200, 2,400 and 4,800. Numerical
production code, fluid properties, geometry, references and tolerances stayed
unchanged. Test-only commits were integrated during the study. One reduced-priority
mutation child and short focused tests overlapped some runs; run durations are
operational records, not performance benchmarks. Each numerical solve used one
OMP/MKL thread and a fresh CPU float32 Session. No Rhino/device/export operation.

All eight cases completed with accepted quality and stationarity, zero owned
resources and unchanged numerical source. Total solve time was 618.79 s. The
original coarse, later-baseline and larger-domain prefix means reproduce exactly.
[Machine evidence](verification-wing-cpu-diagnosis.json) retains all three window
summaries, geometry metrics, source/session/hash provenance and raw-history hashes.

Latest common window: source 4800..4880, physical time 2.07846..2.11310 s.

| Domain / sampling variant | Solid nodes | CL | CD |
| --- | ---: | ---: | ---: |
| Baseline |249|0.140976|1.296746|
| All faces farther away |249|0.068526|1.143816|
| Inlet farther away |249|0.141372|1.208854|
| Outlet farther away |249|0.143463|1.334417|
| Lateral faces farther away |249|0.135266|1.295416|
| Vertical faces farther away |249|0.068717|1.238439|
| Half-cell Z phase, upper placement |356|0.319065|1.469551|
| Same phase, lower placement |356|0.267248|1.419738|

**Domain mechanism:** moving only the top/bottom slip faces almost reproduces the
full-enlargement lift result (CL difference 0.000191). Moving inlet/outlet/lateral
faces individually changes lift much less in this case. Drag has a different
sensitivity: moving the inlet alone changes CD by -6.78%, failing the original
5% screen. These are controlled comparisons, not a linear/additive decomposition
of the full response or an infinite-domain result.

**Time mechanism:** baseline CL at the three windows is 0.161072, 0.141158 and
0.140976; larger-domain CL is 0.085401, 0.070694 and 0.068526. Thus extending
settling does not remove the domain discrepancy. The latest baseline differs
from its original window by 0.020096 CL, narrowly exceeding the original 0.02
reporting screen; the previously tested 2400-step comparison still has its original
passing result. Neither value is substituted for the other. Small within-window
drift does not establish long-time or domain independence.

**Grid mechanism and limits:** the mesh volume is 0.00463910 m3, while node-count
volume proxies differ by -16.13%, -3.77% and +6.78% across the original grids.
The coarse body occupies only two Z planes; its centroid is about 3.50 mm above
the mesh centroid. A half-cell phase change gives 356 rather than 249 solid nodes
and substantially different loads without changing the world mesh or references.
The phase pair itself differs by 0.051817 CL from the small vertical-face shift,
so boundary placement is a material confound. These results demonstrate strong
sampling/placement sensitivity; they do not uniquely partition the original
refinement difference between geometry, boundary and bulk discretization errors.
The independent winding tests found no off-plane classification mismatch for
these fixtures; surface-tie and general-CAD correctness are not established.

## Interpretation and limits

The original grid/domain screen remains **failed**. Its values and thresholds
were not replaced by later or more favorable observations. These experiments
separate sensitivity mechanisms; they do not provide a matched experimental
reference, establish asymptotic convergence or qualify engineering loads.

A read-only unit/capture audit found no domain-length conversion error: the
WindFlow length scale cancels from physical dt, leaving Ma*dx/(sqrt(3)*U), and
collector force conversion uses mass*velocity/time = rho/rho_lu*dx^4/dt^2.
The original grid comparisons have equal physical windows. Domain variants have
identical world meshes, references and solid-node sets. No production solver,
voxelizer or measurement code was changed to obtain these results.

Fresh checks on the merged source (`71cae35`, base `7cd7024`), macOS arm64:

- Python 3.9 CPU-only full suite: **2,667 passed / 176 skipped**; Python 3.12:
  **2,657 passed / 186 skipped**. Skipped accelerator/host/platform checks are
  not passes.
- **146** linked C# state contracts; strict measured headless gate passes with
  **1,161 covered functions**, 299 existing host gaps and 72 declarations.
  The committed matrix is refreshed against the merged-main baseline.
- Frozen CPU float32-versus-CPU float64 smoke: **five cases pass**, source
  unchanged, OMP/MKL=1 and no overlapping jobs. This remains a short smoke check.
- Motion schema policy refreshed after the allocation source change: **104
  assertion kills / 104 mutants**, 132 controls, no survivors/errors/timeouts.
  Initial full runs failed only its stale source hash; these fresh suites pass
  with the refreshed policy. Motion production code was unchanged.

[Software evidence](verification-worker-diagnosis.json) binds the local outcomes.
No Rhino/GH operation, accelerator solve, export edit, installation or release
was performed. Exact pushed-head CI outcomes are recorded in PR #118.

## Gate disposition

- G0: PASS for the predeclared diagnostic questions and fixed reporting criteria;
  physical-reference selection/qualification remains open in #40/#15.
- G1: PASS within the private CPU ownership and retained-result contract exercised
  here; no public runtime or document-lifecycle adapter is introduced.
- G2: PASS for the bounded CPU software checks and exact reviewed mutation inventory above; existing host gaps and omitted scopes remain open.
- G3: FAIL for the original grid/domain independence screen. This follow-up is
  diagnosis, not a waiver or physical validation pass.
- G4: deferred under the user's CPU/headless scope; live Rhino/GH acceptance is
  not performed or claimed.
- G5: not applicable to this test/evidence increment; no package/install/release.
- G6: no public node, supported backend or combination changed. Existing host
  coverage omissions remain explicit; no new live-node acceptance is claimed.

#40 remains open and PR #118 remains draft. The next numerical work must address
body resolution and domain independence within an explicitly reviewed resource
budget, then repeat a fixed protocol and matched reference. Merely increasing
settling or relaxing stationarity does not close the failed numerical gate.
