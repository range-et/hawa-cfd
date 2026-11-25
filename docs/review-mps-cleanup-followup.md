# MPS teardown review follow-up (#76, PR #132)

Date: November 24, 2026. Reviewer: Codex lifecycle/admission agent (self-review).
Scope: completed evaluation-job disposal, retry ownership and asynchronous control ordering.

The completed-job control path removed its session without running tensor release.
It now schedules `Job.release_owned_session`; the worker finalizer uses the same operation.
The public job ID remains registered until cleanup succeeds; already-published
sessions retain their registry entry, while unpublished sessions stay owned by
the known job ID. A failed
cleanup records failed/error status on both objects and can be retried through the
original job ID, including cancellation during preparation before a session ID was
published. Successful cleanup removes disposed jobs. No caller joins a worker.

Queued/adversarial regressions cover duplicate close, failed pause/release,
thread-start failure, close during preparation through `dispatch_job`, concurrent
public close during finalization, and separate stationary-study disposal. Tests
assert daemon cleanup workers and no registry resurrection after independent close.
Session teardown intent permanently rejects stale starts; pending async closes
share one worker. Status uses saved scalars after tensors are cleared. Memory
cleanup has a separate lock that status/async submission never acquire; a
blocked-cleanup test proves duplicate close/status return independently.

The asynchronous control path previously read status after starting cleanup;
an immediate close could clear `flow` first. It now captures the reply before
starting the worker. A synchronous thread double forces that adverse ordering.

Environment: macOS 27.2.1 arm64, Python 3.9.25/3.12.4, PyTorch 2.8.0.
Focused Python 3.9 job/session/stationary controls before the final CPU-selector
rename: 91 passed, 16 device deselections. Final mutation controls include both
CPU fake-cache cases. The full CPU diagnostic before the final assertion additions had
2766 passes, 177 skips and four expected stale-policy failures; that diagnostic
is not a passing full gate. Ruff passed. Final Python 3.9 CPU measured suite: **2777 passed, 177 skipped**; strict
headless coverage: **1203 covered functions, zero failures**, against trusted
base `0b81daee`. The 299 unmeasured host functions remain visible. The .NET
StateContracts run completed through the same gate. CPU mutation/gate processes
overlapped; these are correctness checks, not performance measurements. Fresh CPU mutation studies currently pass:
native-data 1056 mutants (946 killed, 110 reviewed survivors), status-truth 286
(275 killed, 11 reviewed), numerical-export 1626 (1509 killed, 117 reviewed).
Validity-foundation passes 2709 mutants (2476 killed, 233 reviewed); reviewed survivors are exact documented
diffs, not a blanket score threshold.

A fresh M3 Max teardown check on the final production source used a 64×48×32
case and ten MPS steps: current memory returned within 1 MiB of baseline and
driver memory fell below 25% of peak. CPU fake-device tests independently assert
garbage collection → synchronization → cache release and failure recovery.
The old 80×60×40 >95% measurement is historical, not a fresh measurement here.

The scheduler/CLI agent independently reviewed public retry ownership, duplicate
async requests and released status; its adversarial review found and helped
repair public-job removal and registry reinsertion races. Its additional tests
cover queued reset/pause states and overlapping session close. Neither reviewer
used live Rhino. The Python API retains IDs for explicit polling/retry after
failure; whether the Rhino cleanup queue retains an acknowledged async-close
handle and observes a later failure remains unverified.

G0/G1: bounded lifecycle repair; no physical model or public node change.
G2: strict measured headless coverage, CPU suite and all four mutation checks pass.
G3: no numerical algorithm change; MPS teardown checks do not establish parity.
G4: BLOCKED pending live Rhino teardown and paused-RSS acceptance.
G5: no package/release claim. G6: combined compatibility review remains separate.
