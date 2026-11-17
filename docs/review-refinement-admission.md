# Fixed refinement admission (#30 / HAWA-028)

November 16, 2026. Author and current reviewer: Codex domain-validation agent
(self-review). Codex atmospheric-qualification agent independently reviewed
implementation `0e76b95` read-only and found no actionable production defect;
PR/Greptile review remains pending. Base: `21bd205`.
This is a development reliability increment, not a physical validation or release.

## Scope and acceptance criteria

The remaining reproduced gap was timing: `evaluate_submit` constructed and
registered a `Job` and started its worker before `run_refined` checked the two
cases. Refined Solve also crossed the embedded bridge synchronously during its
Grasshopper solution. The older HAWA-052 fix correctly rejected unsupported patch
topology before constructing either solver; it did not establish pre-job admission.

This change moves the existing coupled-case checks into `check_refinement`, called
before Job construction and retained in `run_refined` for direct callers. It checks
existing case/combined budget and supported physics, integer patch corners,
clearance, resolution, physical cell size, matching physical conditions and basis,
and absolute origin placement. It constructs no Session, solver or tensors.
The existing fixed 2:1 numerical method and tolerances are unchanged.

The GH adapter checks only cheap domain/relationship metadata synchronously.
Rejections identify its instance GUID and coarse/fine source objects. Cold runtime use is refused with an instruction to initialize the existing
Hawa Runtime node on the host first. This records GH-bridge readiness, not a
query of private shared-runtime state: native-only initialization conservatively
still requires the explicit Runtime action. After that initialization, Python
admission runs on an owned task. A changed, missing,
cancelled or removed input detaches the task; a retained UI timer transfers any
late successful job into CaseHub's retryable cleanup. Faults are observed without
publishing results. No unfinished task is waited on in the solution thread.
The node GUID, ports, saved-true guard and frame/report contract are unchanged.

Acceptance criteria fixed for this increment:

- Invalid refinement metadata creates no Job, worker or solver; registry unchanged.
- Valid nested, translated and rotated fixed patches remain accepted, including
  the existing absolute origin tolerance of `1e-7`.
- Invalid wired inputs identify coarse/fine sources and the rejecting component.
- Cold submission refuses before any task/bridge call; existing public Runtime
  initialization permits later asynchronous submission. Submission returns while the bridge is pending; cancellation, replacement and
  removal cannot publish a stale result or lose ownership of a late job.
- Existing pause, failure, completion and saved-definition activation behavior
  remains available; fresh measured function/line evidence covers changed code.

Independent Sessions, intentional composed-view overlaps and v1/v2 offline
transfer contracts are unchanged. There is no blanket overlap prohibition.
Geometry-dependent solid/interface checks still run with the constructed grids;
this is metadata admission, not a promise that every future worker failure is
predictable before a Job exists. The #83 obstacle admission and #75 case/resource
boundaries are reused; aggregate multi-case/display/host-memory budgeting is not
implemented or claimed here. No new public node or dependency is introduced.

## Evidence and gates

Environment: macOS arm64, Python 3.9.25 / PyTorch 2.8.0 for production tests;
Python 3.12.4 / mutmut 3.7.0 for CPU mutation; .NET 10 host doubles and .NET 7 plugin.

| Gate | Reviewer | Decision | Evidence / omissions |
| --- | --- | --- | --- |
| G0 research | Codex (self) | PASS, bounded | Existing fixed-refinement contracts, #30/#83 and parent/child operation distinctions; no new numerical method or dependency. |
| G1 architecture | Codex (self) | BLOCKED | Headless ownership/adverse ordering pass; actual GH scheduling still awaits installed-host verification. |
| G2 reliability | Codex (self) | BLOCKED | Focused tests/build pass; complete fresh matrix and mutation review pending. |
| G3 physics | Codex (self) | NOT APPLICABLE | No method/tolerance changes or new physical claim. Existing short refinement regressions exercised; no convergence/engineering validation. |
| G4 UI/UX | Codex (self) | BLOCKED | Source-identity/activation/output assertions pass in doubles; native workflow pending. |
| G5 integration | Codex (self) | BLOCKED | Development package builds; combined installation, CI and external review pending. |
| G6 compatibility | Codex (self) | BLOCKED | GUID/ports retained and operation distinctions preserved; focused native workflow pending, full example inventory not rerun. |

Focused commands and results:

- `.venv/bin/python -m pytest tests/test_refinement_preflight.py tests/test_refinement.py -q`:
  **96 passed, 4 skipped** (CUDA unavailable); includes CPU and four MPS
  parametrizations. An initial combined-budget regression failed because the
  existing case budget truncates fractional MiB; corrected the fixture to a
  four-MiB budget and reran. No production tolerance was changed.
- `dotnet run --project tests/dotnet/StateContracts`: **127 passed**. Real linked
  Refined Solve replaces its former stand-in. Tests use a bridge barrier to
  prove pending return and late success/fault handling, including invalid input
  replacement, Run=false and document removal. The focused Coverlet pass measured
  every new Refined Solve/RefinementAdmission function and executable source line.
- `scripts/build_plugin.py --output dist/domain-admission --archive dist/domain-admission.zip`:
  development build/package passes. The SDK build exposed a non-generic versus
  generic Eto timer event mismatch; production and its double were corrected.
  Existing platform analyzer warnings remain. Package is not installed/released
  by this record.
- Fresh mutation and complete function matrix: **pending**. Initial status-truth
  runs timed out on a reversed lock-acquire loop; the deterministic lock fixture
  now bounds acquisitions so this mutation fails without spinning to a process
  time limit. No timeout is counted as a kill/pass.

`scripts/verify_refinement_admission.cs` is the focused native harness. It creates
one owned GH document using public APIs and restores the previously active
canvas. It checks invalid placement/source IDs, CPU pause and invalid replacement,
valid two-step recovery, immediate cancel/removal, and public pending-refresh and
cleanup counts. Its timer returns between observations. It does not enumerate
private workers or overwrite user geometry, example 09, or any example archive.
A zero public scheduler/cleanup count after the observation window does not
prove that every detached submission timer has completed or that zero workers
exist; the deterministic headless barriers supply that separate ownership
evidence. Native results and final package/source hashes must be recorded after
execution. The first native candidate exposed a real cold-start crash: RhinoCode
created host progress UI from the background thread. The candidate was rejected;
the explicit Runtime prerequisite and cold-background bridge guard repair that
path. The native harness now asserts cold rejection before using the public
Runtime node, so a prewarmed test cannot hide the original failure. Initial
harness-only C#9/`CastTo(out)`/persistent-device and null-placeholder assertions
were also corrected. Fresh installed verification is required for the repair.

## Disposition

#30 remains open while installed-host execution, complete measured gates and PR
review are pending. The implementation addresses fixed coupled-refinement
metadata admission and host object identification only. No unrelated resource,
physical-qualification, all-device or exhaustive arbitrary-graph claim is made.
