# Capture admission review follow-up (#75, PR #133)

Date: November 24, 2026. Reviewer: Codex lifecycle/admission agent (self-review).
Scope: bounded submit-time budget checks and exact validated output paths.

Capture budget admission now calls `check_case(..., compile_boundaries=False)`.
It retains case/budget validation and conservative preparation estimates without
constructing the full external-link or NEE boundary plan on the Grasshopper
submission thread. Full checks remain the default; capture workers validate full boundaries before
reading any parent frames, with attachment/solver checks retained. This is not a full geometry-free case
validator: input metadata and supplied solid indices are still inspected.

Both capture formats use the expanded path returned by output validation for
writing and attachment. Existing dangling symbolic links are rejected before
manifest reads. Tests forbid boundary compilation during admission, verify early
reserve refusal, exercise real v1/v2 capture to `~/capture.npz`, and reject a
symlink before reading an absent manifest.

Python 3.9 focused suites: 149 passed, 14 device deselections. Python 3.12 admission
suite: twelve passed, including both worker validation-before-read regressions. Ruff passed. Full measured coverage and bound mutation policy
refresh remain pending; focused tests alone do not establish merge readiness.

G0/G1: check-order/path repair; budgets, physical models and public nodes unchanged.
G2: focused checks pass; full gates pending. G3: no numerical algorithm change.
G4: BLOCKED pending example 33 live Rhino admission/message acceptance.
G5: no package or release claim. G6: combined compatibility review separate.
