# MPS teardown review follow-up (#76, PR #132)

Date: November 24, 2026. Reviewer: Codex lifecycle/admission agent (self-review).
Scope: completed evaluation-job disposal and asynchronous close reply ordering.

The completed-job control path removed its session without running tensor release.
It now schedules `Job.cleanup`; the worker finalizer uses the same operation.
The public job ID and session registry stay owned until cleanup succeeds. A failed
cleanup records failed/error status on both objects and can be retried through the
original job ID, including cancellation during preparation before a session ID was
published. Successful cleanup removes disposed jobs. No caller joins a worker.

Queued/adversarial regressions cover duplicate close, failed pause/release,
thread-start failure, and a close during preparation through `dispatch_job`.
Session teardown intent permanently rejects stale starts; pending async closes
share one worker. Status uses saved scalars after tensors are cleared. Memory
cleanup has a separate lock that status/async submission never acquire; a
blocked-cleanup test proves duplicate close/status return independently.

The asynchronous control path previously read status after starting cleanup;
an immediate close could clear `flow` first. It now captures the reply before
starting the worker. A synchronous thread double forces that adverse ordering.

Environment: macOS 27.2.1 arm64, Python 3.9.25, PyTorch 2.8.0. The expanded
CPU job/session/native-data suites pass: 129 passed, 28 device deselections.
The earlier live MPS memory test passed before the final retry-ownership changes;
it must be rerun before claiming current live-device acceptance. Ruff passed.
Full measured gate and fresh mutation refresh remain pending; earlier runs are
historical and the failed asynchronous-expectation control run is not a pass.

G0/G1: bounded lifecycle repair; no physical model or public node change.
G2: focused checks pass; complete coverage/mutation evidence pending.
G3: no numerical algorithm change; MPS teardown checks do not establish parity.
G4: BLOCKED pending live Rhino teardown and paused-RSS acceptance.
G5: no package/release claim. G6: combined compatibility review remains separate.
