# MPS teardown review follow-up (#76, PR #132)

## November 25, 2026 — capture exclusion (PR #135)

Reviewer: Codex lifecycle/admission agent; source/test freeze `76a33f7`.
Greptile identified that CPU/CUDA sessions use a capture lock separate from the
shared device lock. An active frame capture could therefore lose `flow` between
array copying and metadata capture even while holding its session lock.

A deterministic CPU regression reproduced the defect before the fix: cleanup
cleared tensors while the capture held its lock (0.14 seconds, all workers joined).
Release now acquires `MPS_LOCK`, then the session capture lock, then `release_lock`.
The prior query-close/async-close order is preserved. The production lock-site
audit found no current session-lock-to-global-lock acquisition path: job device
admission precedes session operations, while capture/export/native-save checkpoints
run outside their capture blocks. MPS sessions reuse the same reentrant device lock.

The regression pauses the real field capture between arrays and metadata, starts
public async close, checks that status remains accessible and tensors remain owned,
then resumes the capture and verifies coherent step/time metadata and complete
cleanup. Separate-session and shared-device lock topologies use CPU tensors; the
shared topology uses the production `DeviceLock`. These are not CUDA or live Rhino
checks. Both new variants plus the previous lock-order regression passed on Python
3.9 and 3.12 (three tests each). Broader CPU controls passed 221 tests on 3.9 before
the shared-lock variant was added, and 222 on 3.12 with it (14 device deselections).
Ruff and whitespace checks passed.

Fresh isolated mutation controls passed 317 export tests and 368 validity tests,
with 14/24 device deselections and no skips. Fresh exact policies pass:
numerical-export 2012 mutants (1875 killed, 137 reviewed survivors), and
validity-foundation 2747 (2513 killed, 234 reviewed). All survivor diff hashes
match their prior explicit reviews; no new survivor exemptions, mutation errors
or timeouts. Runs used two/four CPU workers respectively and overlapped other
CPU studies; these are correctness results, not performance measurements.
Evidence directories: `results/pr135-capture-export-20261125` and
`results/pr135-capture-validity-20261125`.
The current measured suite/package and remaining host omissions belong to the
[integration review](review-mvp-integration.md). The November 24 results below
remain historical evidence for their recorded revisions.

## November 24, 2026 — completed-job and async-close repairs

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

A later Greptile P1 exposed a lock inversion: a query-wrapped close already owned
`MPS_LOCK` and waited for `release_lock`, while async cleanup held `release_lock`
and waited for `MPS_LOCK`. Cleanup now acquires the shared reentrant device lock
before the per-session release lock. Neither lock is acquired by status or async
submission. The scheduler/CLI agent's real query/public-close_async regression
failed pre-fix in 2.14 seconds with both workers joined, then passed on Python
3.9 and 3.12. The bounded release-lock probe prevents the regression test from
stranding threads; it is CPU/fake-device evidence, not live Rhino scheduling.
The post-fix broad CPU controls passed 94 tests (14 device deselections), and the
M3 Max teardown test passed again in 0.49 seconds on this source.

The asynchronous control path previously read status after starting cleanup;
an immediate close could clear `flow` first. It now captures the reply before
starting the worker. A synchronous thread double forces that adverse ordering.

Environment: macOS 27.2.1 arm64, Python 3.9.25/3.12.4, PyTorch 2.8.0.
Focused Python 3.9 job/session/stationary controls before the final CPU-selector
rename: 91 passed, 16 device deselections. Final mutation controls include both
CPU fake-cache cases. The full CPU diagnostic before the final assertion additions had
2766 passes, 177 skips and four expected stale-policy failures; that diagnostic
is not a passing full gate. Ruff passed. Final Python 3.9 CPU measured suite: **2778 passed, 177 skipped**; strict
headless coverage: **1203 covered functions, zero failures**, against trusted
base `0b81daee`. The 299 unmeasured host functions remain visible. All 155 .NET
StateContracts passed through the same post-lock-order gate. CPU mutation/gate processes
overlapped; these are correctness checks, not performance measurements. Fresh CPU mutation studies currently pass:
native-data 1056 mutants (946 killed, 110 reviewed survivors), status-truth 286
(275 killed, 11 reviewed), numerical-export 1626 (1509 killed, 117 reviewed).
Validity-foundation passes 2709 mutants (2476 killed, 233 reviewed); reviewed survivors are exact documented
diffs, not a blanket score threshold. The status-truth runner now pins plugin.py
and was genuinely rerun after the lock-order change. Policies bind selected
execution dependencies, not the whole import graph; unchanged optimization
imports retain historical bounded provenance limits.

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
