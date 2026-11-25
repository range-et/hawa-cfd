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

Python 3.9 focused suites: 149 passed, 14 device deselections. Python 3.12 admission
suite before estimator extraction: twelve passed. Current Python 3.9 admission
suite: 17 passed, including cheap-estimate/full-check agreement and worker
validation-before-read regressions. Ruff passed. Full measured coverage and bound mutation policy
refresh remain pending; focused tests alone do not establish merge readiness.

G0/G1: check-order/path repair; budgets, physical models and public nodes unchanged.
G2: focused checks pass; full gates pending. G3: no numerical algorithm change.
G4: BLOCKED pending example 33 live Rhino admission/message acceptance.
G5: no package or release claim. G6: combined compatibility review separate.
