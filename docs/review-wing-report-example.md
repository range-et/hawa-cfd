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
remained. Fresh runs after adding explicit probe legends and correcting SVG marker links reproduce these coefficients exactly.
The saved report contains that run's exact source/session identities. These values
are workflow evidence, not a numerical reference. No threshold changed.

Focused automated checks: **19 passed on each Python 3.9.25 and 3.12.4**, no skips.
Owned renderer: **115/115 statements, 42/42 branches** measured in coverage.py.
Tests use actual four-step CPU controls to check plotted raw numbers, masked
field arrays, invalid probe gaps, rejection splitting, candidate anchors,
identity mismatch rejection, escaped HTML, missing/unstarted captures, CLI
failure status and preservation of existing output. Ruff passes. Existing
Matplotlib/pyparsing and test runpy warnings remain; no test failure.

All three actual SVG panels were rasterized with `rsvg-convert` at 1200 px and
visually inspected: axes/labels fit, mesh/load/probe curves and masked pressure
slice are visible. Root browser review then found the initial orange points did not navigate:
Matplotlib marker-only Line2D (and its single-point scatter optimization) dropped
URL attributes from rendered SVG. Fixed-size Circle patches now emit actual
SVG anchors. The regression parses the final SVG and requires all six links to
wrap rendered markers, including singleton segments separated by a rejected
case; merely checking artist URL properties is insufficient. Root owns the
post-fix browser click acceptance.

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
matched references and numerical qualification. The later public GH workflow
is delivered in example35; see [its completed host review](review-parametric-wing-example.md).

## Integrator browser acceptance

Codex root opened the saved report in the desktop in-app browser on November17.
Case-table links, Back to all cases and expanded identity details worked.
The initial orange markers failed actual navigation despite stored Matplotlib
artist URLs; the renderer was repaired and its test now parses real SVG anchors.
The regenerated artifact was reloaded: all six marker links are exposed, and
clicking the first orange marker navigated to the matching wing-000 section.
Both candidate panels and the overview were visually inspected without clipping.
The pressure legend identifies the upstream probe. No physical claim is added.
## Requested finer grid and matched-time comparison

The later [fixed protocol](wing-fine-report-protocol.md) raises the CPU per-case
resource cap to 500000 and ships the 499041-cell, 10 mm report by default, with
an explicit 25 mm `--coarse` option. The original shorter report is preserved.
No geometry, fluid, physical-domain extent or acceptance threshold was changed.

All four fresh fine/coarse candidates completed with usable windows. Fine source
steps 3000…3200 and coarse 1200…1280 measure the same physical endpoints. Fine
runs took 593.9/625.5 s; the complete four-run study took 1268.3 s. Observed peak
RSS was 806617088 bytes (769 MiB), below the predeclared 3 GiB pilot stop limit.
All owned resources drained; tracked Python source, dependency pins and protocol
hashes remained unchanged. [Committed concise evidence](verification-wing-fine-report.json)
links the retained local raw observations and field arrays (verification artifacts,
not a new public interchange/checkpoint format).

The refinement screen **still fails**: absolute CL changes are 0.12779646 and
0.11503255 (limit 0.02). Relative CD changes are 1.2603% and 0.1046% (limit 5%).
A sign change in the negative-angle lift is retained, not hidden. These results
show why the original coarse curves were not qualified; they do not qualify the
new grid either. The pressure history also remains a raw diagnostic, not a
pressure-stationarity assertion.

Fresh focused checks for the cap/recipe/report update: **157 passed on each
Python 3.9/3.12**, 386/386 statements and 174/174 branches across the three changed
files. Exact 500000-cell acceptance and 500002-cell rejection before allocation
are asserted; 500001 cannot factor into three dimensions of at least four.
All three final fine SVG panels were rendered at 1200 px and inspected, with
unclipped axes, visible probe legends and finer masked pressure cells. Both
fresh reports contain all six actual SVG candidate anchors. Root owns any live
GH/Rhino adapter acceptance and final combined gates separately.

## Monad presentation correction (Greptile review)

The report now embeds the shared Monad dark/light colors and Helvetica/monospace
font stacks without importing network fonts. Dark is the default; a native
Light theme checkbox changes HTML and SVG presentation through CSS. Markers
are described as highlighted points, not by the old orange palette. The
scientific coolwarm pressure raster and normalization are unchanged.

All three saved reports were migrated as viewing artifacts, without rerunning
CFD: scientific SVG geometry, embedded rasters, candidate anchors, label text,
metadata and tables were checked against their original bytes. Historical run
records remain unchanged. The focused suite passes 22 tests on Python 3.9 and
3.12; the renderer measures 139/139 statements and 46/46 branches. All nine
figures were rasterized and inspected in both themes. Codex root subsequently verified the fine report in the CUA in-app browser:
dark default, light/dark checkbox changes including SVG chrome, an actual gold
marker navigating to candidate 1, expanded source identity/step 3200, return
to overview, candidate 0 selection, and readable/unclipped probe/pressure axes
and Pa units. Coarse HTML interactions were not run; those retain static
figure evidence only. Browser screenshots were observed inline, not saved.
See [presentation proof and artifact hashes](verification-wing-report-themes.json).
