# Change / release review record

Copy this template; do not mark checks passed before running them.

- Change, commit and tested binary/package hashes:
- Date, author, reviewers (role and actual person/agent; note self-review):
- User question and intended claim (demo / verification / validation):
- Scope, affected nodes/interfaces and exclusions:
- Reference sources/versions and licence decisions:
- Acceptance criteria fixed before execution (metrics, norms, tolerances):
- Environment: OS/hardware, Rhino, Python, PyTorch, requested/selected device, dtype:
- Example paths and exact input changes; geometry/input hashes or versioned assets:
- Grid, spacing, physical properties, boundaries, motion and physical time:
- Settling/averaging, seed if used, target and resource budget:

| Gate | Reviewer | PASS / FAIL / BLOCKED / NOT APPLICABLE | Evidence and reason |
| --- | --- | --- | --- |
| G0 research | unassigned | BLOCKED | |
| G1 architecture | unassigned | BLOCKED | |
| G2 software/reliability | unassigned | BLOCKED | |
| G3 numerical physics | unassigned | BLOCKED | |
| G4 UI/UX and examples | unassigned | BLOCKED | |
| G5 release/integration | unassigned | BLOCKED | |

## Reproduction and combination coverage

1. Starting file and clean/installed environment:
2. Public UI or MCP operations, in order:
3. Expected completion and observable assertions:
4. Pause/cancel/edit/close sequence and expected recovery:
5. Cleanup and saved artifacts:

| Combination ID | Example and variation | Expected result or rejection | Observed result | Evidence |
| --- | --- | --- | --- | --- |
| | | | NOT RUN | |

List dimensions and relevant pairs/triples covered, unsupported combinations,
missing hardware and budgeted omissions. Do not claim exhaustive coverage.

## Results and disposition

- Test commands/harnesses and terminal status; pass/fail/skip counts and warnings:
- Numerical error, conservation, sensitivity and reference comparison:
- UI timing: submit vs acknowledgement vs completed result; sampling interval:
- Field provenance: case/revision/generation/session/capture step/physical time:
- Screenshots / final rendered video checks / valid geometry checks:
- Jobs, sessions and workers after teardown:
- Saved-definition, package/source/hash and licence checks:
- Failures, linked regressions and remaining limits:
- Required follow-up, owner and acceptance test for each gap:
- Release decision and exact supported claims; anything not verified:
