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
cancelled or removed input detaches the task; a process-rooted UI timer transfers any
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
| G1 architecture | Codex root + independent agents | PASS | Headless adverse ordering and fresh cold/warm GH lifecycle pass; retained timer ownership and actual zero-worker cleanup verified. |
| G2 reliability | Codex root + agents | PASS | Exact mutation policies; full Python 3.9 suite 1,978 passed/87 skipped; 127 instrumented state contracts; strict headless function/line and trusted-base checks pass. |
| G3 physics | Codex (self) | NOT APPLICABLE | No method/tolerance changes or new physical claim. Existing short refinement regressions exercised; no convergence/engineering validation. |
| G4 UI/UX | Codex root | PASS | Cold prerequisite and actionable source IDs observed in Rhino; pause/replacement/recovery/cancel/removal pass. |
| G5 integration | Codex root | BLOCKED | Combined package and installed runtime checks pass; ready PR #116 awaits final CI and external review. |
| G6 compatibility | Codex root | PASS, local | 100,010 rows passed, zero failed, 2,449 CUDA rows blocked; 53-node/31-example archive inventory passes. No arbitrary-graph or all-device qualification. |

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
  Existing platform analyzer warnings remain. Final combined package was installed and tested as recorded below; no released
  distribution claim.
- Fresh combined validity mutation: **2,562 mutants, 2,343 assertion kills,
  219 reviewed equivalents; 279 controls passed**. The new omitted-step test
  detects default removal, None and 201-step variants. [Exact evidence](verification-working-validity-mutation.json).
  Complete measured function matrix now passes on the combined source (below). Initial status-truth
  runs timed out on a reversed lock-acquire loop; the deterministic lock fixture
  now bounds acquisitions so this mutation fails without spinning to a process
  time limit. No timeout is counted as a kill/pass.

`scripts/verify_refinement_admission.cs` is the focused native harness. It creates
one owned GH document using public APIs and restores the previously active
canvas. It checks invalid placement/source IDs, CPU pause and invalid replacement,
valid two-step recovery, immediate cancel/removal, and public pending-refresh and
cleanup counts. Its timer returns between observations. It does not enumerate
private workers or overwrite user geometry, example 09, or any example archive.
The public pending-submission count now covers retained detached-task timers
as well as scheduler/cleanup counts. These are ownership diagnostics, not a
private worker enumeration. An earlier native candidate passed the superficial
UI assertions but leaked a refinement worker after removal: the local Eto timer
had no guaranteed managed GC root, unlike the headless double's global timer
list. That result is a failed lifecycle gate, not a pass. A process-owned static
timer set now roots each detached submission until drained, and the harness
requires its pending count to reach zero. Deterministic headless barriers and
fresh live removal/worker follow-up remain separate evidence. Native results and final package/source hashes must be recorded after
execution. The first native candidate exposed a real cold-start crash: RhinoCode
created host progress UI from the background thread. The candidate was rejected;
the explicit Runtime prerequisite and cold-background bridge guard repair that
path. The native harness now asserts cold rejection before using the public
Runtime node, so a prewarmed test cannot hide the original failure. Initial
harness-only C#9/`CastTo(out)`/persistent-device and null-placeholder assertions
were also corrected. Fresh installed verification of both repairs now passes; see the next section.

## Fresh installed acceptance

Root ran the revised harness in a new Rhino 8.37 Mac process on Apple M3 Max,
with GH readiness initially false. Final production candidate `ae95b7d` passes
all nine observations: invalid source identity, cold rejection, explicit public
Runtime initialization, asynchronous submit, paused invalid replacement,
valid recovery, both two-step frames, immediate cancellation and removal.
Invalid and valid submission returned in 4.68 ms and 2.92 ms respectively;
these are individual observations, not a performance guarantee.

The final [host record](verification-refinement-admission-host.json) includes
zero pending submissions, refreshes and cleanup. A separate same-process,
read-only runtime registry/thread audit after disposal found **zero jobs,
sessions and Hawa workers**. Original two empty GH documents were restored;
no user geometry or source archive was changed. Cold crash and retained-worker
failures remain in local `results/refinement-admission-host/` as rejected evidence.

Loaded binary SHA256 values:

- Grasshopper: `bf99fd985183443fe4a9181d671a06a9e2c8661635acb8423df355a4e8f08993`
- Shared: `0fac588984d9ccd10ce061f9d746692245044338f604b5bbf08f1e16a2f2e41f`
- Rhino: `b8eb2587caa088835770dadd6dbade53d1b2ea4eb8888611e1618d63f94b0a63`

Codex numerical-exports agent independently reviewed the cold guard and retained
ownership fixes, found no blocking findings, and reran all 127 state contracts.
This review does not substitute for the separate installed observations above.

The fresh combined [G6 record](verification-working-30-35-g6.json) covers all
102,459 declared rows in 378 seconds on available CPU/MPS devices: 100,010 pass,
zero fail, 2,449 CUDA rows blocked by unavailable hardware. Source hashes did not
change during the run; `verify_evidence` and the 53-node/31-example/188-edge
archive checker pass. Raw row evidence remains in `results/working-g6-final/`.
These are finite contract checks, not a new numerical qualification.

Final measured run: `results/function-coverage-portable-final-20261117`, Python
3.9.25, **1,978 passed / 87 skipped**, 127 instrumented .NET contracts passed.
Skips: 85 unavailable CUDA, one unsupported MPS float64 case, one mutmut-only
Python 3.12 test. Strict headless 100% functions/lines and trusted base `d12fd069`
checks pass with no failures. Both committed coverage matrices are refreshed:
497 Python and 521 C# functions covered; 299 host-only C# functions remain
unmeasured and 60 declarations have no explicit body. Those exclusions are not
host acceptance passes. The final Python 3.12 complete suite also passes in CI;
all final-head CI and Greptile review gates still apply before merge.

## Disposition

#30's remaining acceptance criteria are satisfied; closure is tied to
[PR #116](https://github.com/range-et/hawa-cfd/pull/116) passing its final gates
and merging. The Windows rerun on source-equivalent candidate `0e219a9` passes
1,973 tests (92 explicit skips), all 91 CUDA cases, five CPU-FP64 smoke cases
and all 2,449 CUDA G6 rows. [Windows evidence](review-windows-verification-portability.md)
is headless PR evidence, not installed Windows Rhino or merged-main qualification.
The declared installed-host and local measured checks are complete. The implementation addresses fixed coupled-refinement
metadata admission and host object identification only. No unrelated resource,
physical-qualification, all-device or exhaustive arbitrary-graph claim is made.
