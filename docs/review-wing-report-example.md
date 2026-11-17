# Saved wing report example review

November 17, 2026. Author/operator/reviewer: Codex `wing_wrapup` agent (self-review).
Base: PR #118 `f606446`. Root integrator owns combined suites, measured matrix,
CI and merge decision. This change adds an example presentation only: solver,
collector, tolerances, exporters and host APIs are unchanged.

## Evidence and scope

The runnable [example](../examples/headless-wing/README.md) saves a standalone
HTML with standard Matplotlib SVG figures. It includes the three identified
coefficient plots, clickable candidate anchors, raw world-force/probe histories,
actual candidate mesh and masked captured pressure slice. All text metadata is
escaped; the artifact uses no scripts/CDN/network resources. Retained records,
prepared inputs, sample identities and field session/phase must agree. Rejected
candidates remain listed and split plots according to the existing sweep rule.
Exclusive creation preserves existing files.

A real CPU float32 run on macOS arm64/Python 3.9.25/PyTorch 2.8.0 completed both
shipped candidates. Each ran 1064 steps (1000 settling, 64 samples); the captured
field was source step 1063 / 0.4602925021114292 s. CL was 0.13120227473943177 and
0.17370137599452087; CD was 1.3315546400715705 and 1.3287346632245722. Both windows
met their existing 0.05 stationarity criterion; zero owned handles/workers/sessions
remained. A second fresh run after adding explicit probe legends reproduces these coefficients exactly.
The saved report contains that run's exact source/session identities. These values
are workflow evidence, not a numerical reference. No threshold changed.

Focused automated checks: **19 passed on each Python 3.9.25 and 3.12.4**, no skips.
Owned renderer: **112/112 statements, 42/42 branches** measured in coverage.py.
Tests use actual four-step CPU controls to check plotted raw numbers, masked
field arrays, invalid probe gaps, rejection splitting, candidate anchors,
identity mismatch rejection, escaped HTML, missing/unstarted captures, CLI
failure status and preservation of existing output. Ruff passes. Existing
Matplotlib/pyparsing and test runpy warnings remain; no test failure.

All three actual SVG panels were rasterized with `rsvg-convert` at 1200 px and
visually inspected: axes/labels fit, mesh/load/probe curves and masked pressure
slice are visible. HTML navigation targets and SVG links are asserted; a full
interactive browser inspection was not performed in this lane.

| Gate | Disposition |
| --- | --- |
| G0 | PASS for bounded presentation; no new physical claim or external dataset |
| G1 | PASS self-review: saved artifact, no service/solver ownership change or new public node |
| G2 | Focused PASS; root owns combined suites/matrix and exact-head CI |
| G3 | Workflow-only PASS; existing grid/domain gate FAIL and physical qualification remain open in #40 |
| G4 | Figure visual checks PASS; browser navigation tested structurally; no GH/Rhino example acceptance claimed |
| G5 | Source/example artifact only; no package, installation or release claim |
| G6 | No solver dimensions or public-node inventory changes; headless example only, no new GH coverage claim |

## Important omissions

No Rhino, MPS, CUDA, full-gallery host review, package or release operation was
performed. Production is CPU-only guarded. No parallel numerical CSV is added:
shared export captures live sessions and its load table describes moving-body
step-end histories; the stationary collector's pre-reflection world-frame data
requires an explicit reviewed adapter. #40 remains open for that integration,
public GH workflow, matched references and numerical qualification.
