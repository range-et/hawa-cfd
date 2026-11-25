# MPS teardown review follow-up (#76, PR #132)

Date: November 24, 2026. Reviewer: Codex lifecycle/admission agent (self-review).
Scope: completed evaluation-job disposal and asynchronous close reply ordering.

The completed-job control path removed its session without running the new tensor
release operation. It now requests the existing asynchronous session close,
retaining registry ownership until the solver reaches its cancellation boundary.
The caller never joins a worker. A deterministic queued-worker regression checks
retained ownership, reference release, and retry after a failed pause.

The asynchronous control path previously read status after starting cleanup;
an immediate close could clear `flow` first. It now captures the reply before
starting the worker. A synchronous thread double forces that adverse ordering.

Focused Python 3.9 tests (memory, job contracts, plugin service and core contracts)
passed: 72 passed, seven skips before the added pause-failure parameter. The live
MPS memory test passed on this Mac. Python 3.12 CPU job/service tests passed
(51 passed, 16 deselected); ruff passed. Full measured gate and mutation refresh
are pending and must be recorded before claiming merge readiness.

G0/G1: bounded lifecycle repair; no physical model or public node change.
G2: focused checks pass; complete coverage/mutation evidence pending.
G3: no numerical algorithm change; MPS teardown checks do not establish parity.
G4: BLOCKED pending live Rhino teardown and paused-RSS acceptance.
G5: no package/release claim. G6: combined compatibility review remains separate.
