# Capture admission review follow-up (#75, PR #133)

Date: November 24, 2026. Reviewer: Codex lifecycle/admission agent (self-review).
Scope: bounded submit-time budget checks and exact validated output paths.

Capture budget admission now uses the same `estimate_case_budget` arithmetic as
full validation, inspecting only grid shape and the six external face contracts.
It does not inspect solid/halo arrays, construct a roughness grid, hash the whole
case, or compile boundary links. Tests explicitly forbid those expensive helpers.
Full validation remains in capture workers before any parent reads, and in the
existing attachment/solver paths. The shape cap and memory budgets are unchanged.

Both capture formats use the expanded path returned by output validation for
writing and attachment. Existing dangling symbolic links are rejected before
manifest reads. Tests forbid boundary compilation during admission, verify early
reserve refusal, exercise real v1/v2 capture to `~/capture.npz`, and reject a
symlink before reading an absent manifest.

This PR is stacked on the final PR #132 lifecycle repair, including the later
query-close/async-cleanup lock-order correction and its bounded regression. The scheduler/CLI
agent independently reviewed the estimate/full-validation split and identified
the missing worker validation and roughness allocation in the original cheap
path; both were repaired and re-reviewed. Admission itself only reads scalars
and six face contracts. The existing job constructor still deep-copies and hashes
the request, so this is not a constant-time or allocation-free whole-submit claim.

Python 3.9 admission regressions: 28 passed; combined focused controls after
stacking: 473 passed, 32 device deselections (before the final inherited lifecycle
assertions). Ruff passed. Final Python 3.9 CPU measured suite: **2806 passed, 177 skipped**, with
155 .NET StateContracts. Strict headless coverage passes **1211 covered functions,
zero failures** against the trusted PR #132 base `e151698`; 299 host functions
remain unmeasured. The committed matrix validates. CPU gate/mutation processes
overlapped, with no performance claim. All four exact mutation policies pass. Validity-foundation passes 2747
mutants (2513 killed, 234 reviewed), with 366 CPU controls. Fresh CPU
mutation studies pass: native-data 1056 mutants (946 killed, 110 reviewed),
status-truth 287 (276 killed, 11 reviewed), numerical-export 2012 (1875 killed,
137 reviewed), including whole admission.py. Remaining new admission survivors
are error prose decoration/case changes and an equivalent one-cell cap increase:
2000001 = 3 × prime 666667 cannot form three resolutions each at least four.
One explicit assertion debt remains under #75 (owner: unassigned): the
combined refinement fallback default changing from 1024 to 1025 MiB is not
distinguished when memory_limit_mb is absent. It is not claimed equivalent;
completion requires a missing-key combined-budget boundary regression and fresh
validity mutation evidence. Explicit combined thresholds and per-case defaults
are asserted. Policy dependency pinning remains bounded; unchanged boundary_contracts imports
are not a whole-import-graph provenance claim. Exact budget thresholds, attached
reserve, asymmetric faces, route selection and
output-path identity are asserted. Focused tests alone do not establish merge readiness.

G0/G1: check-order/path repair; budgets, physical models and public nodes unchanged.
G2: CPU suite, strict measured headless coverage and all four mutation policies pass. G3: no numerical algorithm change.
G4: BLOCKED pending example 33 live Rhino admission/message acceptance.
G5: no package or release claim. G6: combined compatibility review separate.
