# Hawa built features and history

This is the running inventory of implemented capabilities and completed work.
Open bugs, remaining work and ideas live in [GitHub Issues](https://github.com/range-et/hawa-cfd/issues); future
direction lives in the [roadmap](docs/roadmap.md). Maintainers, agents and the user
can edit this file. Add evidence and limits when updating a capability.

Inventory established November 9, 2026 from existing repository documentation.
“Built” means an implementation exists within the linked scope. It does not mean
released, physically validated or verified on every platform. Linked reports
record historical checks on particular builds; this inventory is not a fresh
test run. Review and verification records cited below without a link were moved
to a private maintainer archive on 2026-11-11; they remain in this repository's
git history at commit cc407cc. See the release review for distribution
claims and the [coverage matrix](examples/grasshopper/VERIFICATION.md) for required
example checks.

## Implemented capabilities

| Capability | Current scope and important limits | Guide and evidence |
| --- | --- | --- |
| Function inventory and coverage ratchet | Syntax inventory of first-party Python and plugin C#, actual Python function-entry evidence, and instrumented .NET state contracts. Rejects new/changed untested functions, lost coverage and stale reports. Historical and host-only gaps remain HAWA-026; execution does not establish assertion quality. | [Function policy](docs/function-testing.md), [matrix](docs/function-test-matrix.md) |
| Embedded Python/PyTorch LBM | Runs inside Rhino's Python 3.9 environment with pinned dependencies. CPU/MPS evidence exists. Headless Windows CUDA acceptance passes on merged main (#46/#47/#12); clean Windows Rhino installation and lifecycle with CUDA remain open in #61. | [Native guide](docs/native-v0.5.md), backport |
| Native geometry and case setup | Selected closed meshes/solid Breps, editable physical domain/fluid settings and one shared case per document. | [Native guide](docs/native-v0.5.md), [full review](docs/review-full-v0.5.md) |
| Native panel and GH live binding | Shared settings, direct/computed input ownership, revisions, stale-result handling, undo and saved idle cases. Public operations support agent workflows. | [Architecture](docs/architecture-v0.5.md), [agent operations](docs/agents/native-prototype.md), [state coverage](examples/grasshopper/VERIFICATION.md) |
| Background work and cooperative lifecycle | Preparation, solve/query jobs, pause/resume/cancel and cleanup; legacy failed-close retry has a scoped follow-up record. | [Cleanup review](docs/review-cleanup-v0.5.md), [architecture](docs/architecture-v0.5.md) |
| Field visualization | Scalar slices, vectors, streamlines, snapshot planes/contours/isosurfaces, surface sampling and legends. Native/GH capabilities differ; integrated movable vector slices remain HAWA-007. | [Plugin guide](docs/plugin.md), [node catalogue](docs/node-catalog-v0.5.md) |
| Record and playback | Field snapshots, physical-time metadata and playback within documented formats and limits. Particles and time-dependent pathlines were removed (see history, November 12, 2026). | [GH examples](examples/grasshopper/README.md), [0.4 report](docs/release-notes-v0.4.0.md) |
| Asynchronous design search | Completed-candidate objectives, best-result history and cooperative controls. Hull geometry is an example recipe, not a public hull-construction service. | [GH examples (example 10)](examples/grasshopper/README.md), [node boundary](docs/node-catalog-v0.5.md) |
| Local airfoil and wing tools | Offline coordinates/NACA generation, supplied local polars and attached-flow lifting line. Bundled polar is synthetic format data; no viscous/stall CFD claim. | [Plugin guide](docs/plugin.md), [release limits](docs/release-notes-v0.4.0.md) |
| Curved stationary walls and fixed refinement | Experimental curved links and one fixed 2:1 BGK patch with explicit unsupported combinations. Multiple-region refinement remains HAWA-009. | [0.4 numerical evidence](docs/release-notes-v0.4.0.md), [coverage](examples/grasshopper/VERIFICATION.md) |
| Prescribed rigid motion and cycle objectives | Translation/rotation/oscillation, raw loads and complete-cycle search. No force-driven body response, free surface, buoyancy or validated propeller prediction. | [Motion guide](docs/moving-surfaces-v0.4.md), [motion evidence](docs/verification-motion-v0.4.json) |
| Result quality and offline inlet transfer | Bounded Mach/density/finite-state quality policy and v1 mapped X− velocity series, with source identity and coverage checks. Not convergence or atmospheric validation. | [Transfer guide](docs/boundary-transfer.md), [gate record](docs/boundary-transfer-review.md) |
| Shared boundary foundation | Physical patch schema plus bounded LBM NEE wall/slip/velocity/open reconstruction; corrected closure is explicitly versioned. Full reversing/cropped/atmospheric capability is not established. | [Boundary guide](docs/general-boundaries.md), [gate record](docs/general-boundaries-review.md) |
| Experimental neutral flow | Shifted-population regularized SGS with molecular-air input viscosity (FP32 storage does not represent molecular dissipation at 0.1–10 m; runtime `dissipation_storage` diagnostic, [#13](https://github.com/range-et/hawa-cfd/issues/13)), sampled/filtered planar rough-floor stress and restart state. External mode adds halo-classified cropped buildings, side/top velocity or open faces, pressure reference and measured link mass budget. Pressure-backflow open faces now pass a pressure-driven reversal test; open faces of both boundary methods reflect acoustic pulses and fail the declared vortex-exit criterion ([HAWA-004 record](docs/boundary-reflection-review.md)). Analytic wall, convected-disturbance, stationary-channel and scoped CPU/MPS/Rhino checks pass. Full atmospheric accuracy and nesting qualification remain open. | [Coupling review](docs/neutral-coupling-review.md), [verification](docs/verification-neutral-coupling.json); HAWA-003/004/011 in [GitHub Issues](https://github.com/range-et/hawa-cfd/issues) |
| Device smoke gate | Five short existing cases (compatibility engine, KBC collision, neutral precursor, moving sphere, curved-wall channel) compared with a CPU FP64 reference under a committed bitwise/bounded policy, with a per-run manifest. The CPU mode runs in CI. CUDA (RTX 5070 Ti) and MPS (M3 Max) each passed 5/5 on merged main `71625aa`, so #57 is complete; other devices are not qualified. | [Gate guide](docs/device-smoke.md), [#57](https://github.com/range-et/hawa-cfd/issues/57) |
| Compatibility and example coverage gate | G6 enumerates 102,459 finite contract rows, detects incomplete/stale evidence and audits all public nodes against annotated GH workflows. CPU/MPS local checks pass; on Windows CUDA (merged main `285d961`) all `cuda:0` rows pass with MPS rows blocked. Arbitrary graphs and continuous inputs are not exhaustively enumerated. | [G6 guide](docs/compatibility-matrix.md), [machine report](docs/verification-compatibility.json) |

## Headless testing expansion (November 9, 2026)

First-party Python now has measured 365/365 functions and 6,164/6,164 executable
lines covered; linked C# contracts cover 152/152 functions and 1,618/1,618 lines.
The fresh native suite passed 1,419 Python tests (82 skipped) and 67 C# contracts.
CI adds strict headless coverage and four-module mutation checks (358/398 killed,
40 explicitly reviewed survivors). Stationarity failure reporting, failed-resume history preservation and source
palette packaging were repaired. [Review and limits](docs/review-headless-quality.md).

GitHub #28 and #45 remain open: 590 host-dependent C# functions are unmeasured,
mutation scope is bounded, and no fresh Rhino acceptance or physical qualification
is claimed. The [local example review](docs/local-rhino-acceptance.md) records all
supported workflows, numbers and images for maintainer acceptance.

## Atmospheric transfer development (November 9, 2026)

BoundarySeries v2 now carries timed multi-face velocity, gauge pressure, kinetic
strain, initial fields, geometry hashes and absolute source time. Neutral
recordings include the stress data required for LBM reconstruction. Spatial
roughness and Flow Statistics operations have GH components. Boundary Patch adds
an explicit pressure-derived backflow option; old archives retain velocity mode.
These changes are **built and under verification**, not a completed release.

The first 12,000-step AIJ Case I comparison (4 cells/H, CPU, measured mean inlet)
passed its bounded checks, but later runs fail qualification: the current 40,000-step
4-cells/H run has 64.84% streamwise hit rate (66% required). The older 8-cells/H
run has 75.82% hit rate but 5.44% stationarity change (5% maximum). Resolved TKE is
poorly reproduced. The current 60,000-step 6-cells/H MPS run passes its bounded mean-velocity/stationarity checks (72.53% hits, 1.83% change), but TKE relative L2 error is 95.26%. Longer same-grid nesting also misses mean/RMS and stationarity
limits; the 2:1 comparison misses mean/RMS limits. These are retained failures, not
validated atmospheric results. [Contract and evidence scope](docs/atmospheric-nesting-implementation.md).

The development views accept several same-time frames, use the finest containing
domain and trim slice faces at halfway solid boundaries. Reconstructed display
colours remain separate from raw samples. Example 33 demonstrates three imported
uniform grids and a shared height-controlled slice. Host and lifecycle checks pass within the recorded scope. These changes are
not released.

## Transfer/display repairs verified locally

- **HAWA-023 closed:** disjoint bodies in a shared building list are excluded
  conservatively; cropped/intersecting bodies retain local and halo classification.
  The three-stage CPU/MPS workflow and archive checks pass.
- **HAWA-024 closed for the declared snapshot views:** same-time multi-frame
  sampling, finest ownership, disjoint-gap clipping and halfway-wall plane trimming
  pass the field matrix and live GH checks. Legacy live views retain their contracts;
  curved-link/derivative reconstruction remains explicitly outside this repair.
- **HAWA-025 closed:** retained UI polling reaches completion through intervening
  solutions and pause/resume. Saved enabled graphs reopen idle. Disposal and failed
  cleanup recovery leave zero jobs/sessions/workers/refreshes across five legacy
  component families with the native timer disabled.

Evidence: [transfer review](docs/neutral-transfer-review.md),
[machine record](docs/verification-neutral-transfer.json). The atmospheric
qualification failures remain open in HAWA-021/022; these repairs do not close them.

## History

### November 12, 2026 — Particles and pathlines removed (owner decision)

The owner descoped particles. Removed: Python `recording.pathlines` and its
100,000-point budget, the `recording`/`particles` query, and the GH Particles
tool. Old definitions still open, because a hidden Particles stub keeps the
original GUID and parameters, and it reports only that the tool was removed.
Example 32 is a translation-and-recording example now; its Particles node is
removed during the live acceptance re-save. The particle work recorded in #82,
#93 and #96 below was never verified and is no longer a capability.
Particle-method solver research (#22) is closed as descoped on the same
decision. Static streamlines, Flow Display, field planes and isosurfaces are kept.

### November 12, 2026 — GH field views draw what was not simulated (#81, #82, partial)

Built, not released. These views moved into `FieldViewComponents.cs`, which the
GH host harness measures in full:
- GH Plane Field draws the merged plane classes. Fluid faces are coloured.
  Solid, invalid and no-data pieces are black ("not simulated", as on Slice) on
  their own vertex copies, for single and composed frames.
- GH Surface Field keeps every face and draws faces with an invalid sample black.
  Its label counts those faces.
- GH Flow Display skips seeds with fewer than two traced points. Each remaining
  path keeps its per-seed colours, and points with no valid colour sample are black.
- GH Particles outputs final positions only for particles whose `alive` flag is true.

Not done: a live Rhino check.

### November 11, 2026 — GH Slice key and GH Vectors alignment (#29, #81, partial)

Built, not released, measured in the GH host harness:
- GH Slice adds a remark on every result: "Black = not simulated (solid or
  no-data nodes)". The remark names the actual wall mode (interpolated at link
  crossings, or voxel halfway between nodes) and the cell size. It warns that
  colours within about one cell of a surface depend on that wall mode and
  resolution. The mesh output description carries the same key.
- GH Vectors keeps one entry per input point, with null where the sample is not
  simulated, so Lines stays index-aligned with Points, Pressure and Valid.

Not done: the native panel caveat, the #81 Plane Field and Surface Field
classes, and a live Rhino check.

### November 11, 2026 — Grasshopper host harness and GH status truth (#74, partial)

Built, not released. StateContracts now links five GH source files (`Runtime.cs`,
the new `FieldTools.cs`, `ResultsComponents.cs`, `SolveComponents.cs`,
`AnimationComponents.cs`) against GH/Rhino doubles. Every function and line in
those files is measured with asserting tests ([policy](docs/function-testing.md)).
The GH side of #74:
- A component whose required input disappears replaces its old status with
  "waiting for input". A failure shows "failed".
- After a document switch the label reads "cancelled: document inactive", with
  the reason as a remark.
- Record names the inputs that changed when it restarts. After a document
  switch it says how to resume.
- Solve shows "queued: waiting for the device" before its session exists.
- Plane Field, Isosurface, Flow Display and Surface Field warn when a wired
  child delivered no frame or a frame is wired twice.

Not done: CaseHub's queued state and the native panel (they must change
together) and a live Rhino check of these transitions.

### November 11, 2026 — batched CUDA and MPS round on merged main `71625aa`

One CUDA host (Windows 11, RTX 5070 Ti, driver 621.14, torch 2.8.0+cu128) and one
MPS host (M3 Max, macOS 27.0.1, torch 2.8.0) ran the #52/#53 commands on merge
commit `71625aa`, which contains #63 (#11), #65 (#13), #64 (#57) and #66 (#14).
Fresh checkouts, no tolerance or policy edits; binaries stay on the hosts by SHA-256.
- Device smoke gate (#57): 5/5 on CUDA and on MPS; the MPS KBC case is now bitwise.
  #57 is complete.
- HAWA-001 KBC repair (#11): the original 50-step PorousMedium criteria pass on CUDA
  and MPS (MPS f 3.3e-7, u 1.3e-5, p 1.4e-4), with 16/16 examples on both. #11 is complete.
- HAWA-046 actual-device assertions (#48): MPS cases pass on `71625aa`; the CUDA part
  passed on merged `239d644`. #48 is complete.
- HAWA-003 precision diagnostic (#13): no false "resolved" result on either device;
  device rows report indeterminate arithmetic, as designed. #13 is closed as
  re-scoped: FP32 molecular-viscosity neutral flow is not qualified, and
  double-float storage moved to #51.
- HAWA-004 boundary reflection (#14): CUDA matches every CPU FP64 decision within
  bounds. On MPS all 9 decisions match, but the C1-S FP32 mass budget residual is
  3.35e-6 lu against its declared 1e-6 lu bound (CPU FP32 6.3e-7), so C1-S is not
  qualified on MPS. #14 is closed under its approved re-scope; the failing rows and
  this MPS residual are in #60.
[CUDA results](https://github.com/range-et/hawa-cfd/issues/57#issuecomment-6786203542),
[MPS results](https://github.com/range-et/hawa-cfd/issues/14#issuecomment-6786793399).

### November 11, 2026 — motion payload schemas with pydantic (#68, first migration)

Built, not released. `motion.py` validates the moving-body, motion and Motion
Evaluate payloads through pydantic 2.13.5 models (unversioned v0, validate only,
so case hashes are unchanged). Unknown keys, and numeric strings and booleans in
float fields, are now rejected, and invalid metric or axis values fail before an
evaluation runs. A guard refuses any other pydantic already loaded in Rhino's
shared interpreter. Behaviour tests cover every declared
constraint through the public entry points; tests enforce the four advisory rules
and a checked-in JSON Schema snapshot ([docs](docs/payload-schemas.md)). Rhino
installation of pydantic on macOS/Windows and the local Rhino acceptance are
recorded separately on the PR; other payloads are not converted.

### November 11, 2026 — mutation studies on mutmut 3.7.0 (#67)

Developer tooling only; no solver or numerical change. All 8 mutation studies
were regenerated on mutmut 3.7.0 with changed-line scope and fail-closed result
checks ([#67](https://github.com/range-et/hawa-cfd/issues/67), PR
[#84](https://github.com/range-et/hawa-cfd/pull/84), merged at `cc407cc`).
The runtime-admission mutation job on GitHub dropped from 11–15 min to about
1m45s, and a full CI run now takes about 7.5 min with `functions` as the critical
path. Accepted limits: the boundary reflection study still takes about 10–13 min
locally on 2 vCPU, `production_python` tests cannot kill mutants on 3.12, and the
39 unresolved survivors are tracked in
[#85](https://github.com/range-et/hawa-cfd/issues/85). Measurements:
[#67 record](https://github.com/range-et/hawa-cfd/issues/67#issuecomment-6789438865).

### November 11, 2026 — Python 3.12 developer environment (Phase 0 for #67/#68)

Production stays Python 3.9. `pyproject.toml` now accepts Python 3.9–3.12 so a
`.venv-dev` (3.12) can install Hawa editable for tooling (ruff, mutmut 3.7.0 in a
`tools` dependency group); `.venv` (3.9) remains the gate environment. uv.lock
covers both, and `requirements/rhino-py39.txt` re-exports byte-identically for 3.9.
A test ties the Rhino `# requirements:` headers to the project pins. New CI jobs
run ruff's 3.9 syntax guard, the Rhino export check and the full headless suite on
3.12 (production-only entry points skipped). Developer tooling only; no solver or
Rhino change, not released.

### November 10, 2026 — HAWA-004 boundary reflection measurements (partial)

Added an enlarged-domain/analytic harness with criteria committed before the
first run: acoustic and vortex reflection, oblique corners, pressure-driven
reversal and a cropped-body cut face, for shifted external and NEE open faces.
Repaired pressure-backflow outgoing faces, which could not pass through zero
normal speed (reversal error 3.07 → 0.0042 m/s). C1 corners, R1 reversal and the
attached K1-S cut face pass on CPU. Acoustic reflection (≈1), vortex exit
(0.22 / 0.53) and backflow vortices fail. The default-face reversal defect is
[#55](https://github.com/range-et/hawa-cfd/issues/55); a vortex leaving through an open/open corner
(C2, 1.24) and the other failing reflection rows are collected in
[#60](https://github.com/range-et/hawa-cfd/issues/60). MPS FP32 rows are queued
in #53; a pre-merge CUDA check on one RTX 5070 Ti was within all declared bounds. The approved re-scope moves the
failing rows to #60; HAWA-004 closes after merge and qualifying device runs.
[Criteria, results and limits](docs/boundary-reflection-review.md).

### November 10, 2026 — headless Windows CUDA acceptance on merged main

[PR #56](https://github.com/range-et/hawa-cfd/pull/56) fixed Windows path separators in
the function gate, the G6 example contract and three test assertions. The full
Windows CUDA acceptance runbook then passed on
merged main `285d961` (Windows 11, RTX 5070 Ti, driver 621.14, torch 2.8.0+cu128,
Python 3.9.25):
- Suite: 1419 passed, 0 failed in each of three runs, with all 86 CUDA cases executed.
- Upstream: 750 passed.
- CPU/CPU64/CUDA core parity passed; examples 16/16; benchmarks 13/13.
- Function gate and 67 state contracts passed.
- G6: 100,010 passed, 0 failed, with 2,449 MPS rows blocked.

This closed HAWA-044/045 (#46/#47). HAWA-002 (#12) was re-scoped and closed, and
clean Windows Rhino installation (including embedded CUDA PyTorch), native UI and
docking, and lifecycle moved to #61. HAWA-001's KBC repair (#11) also passed its
CUDA regression on branch `b66cb59`; its MPS qualification is pending in #53.
This is headless development evidence, not an installed or released claim.
[Manifest and results](https://github.com/range-et/hawa-cfd/issues/46#issuecomment-6780599636).

### November 10, 2026 — HAWA-001 KBC repair candidate (#11)

Devices without FP64 (MPS) now evaluate KBC with FP32 hi/lo intermediates
(TwoSum/TwoProduct, exact moment split, one rounding); CPU/CUDA keep their FP64
path. On identical inputs MPS reproduces the rounded CPU output bitwise. The
original 512-square/50-step PorousMedium CPU/MPS comparison passes on one M3 Max
(f 3.3e-7, u 1.3e-5, p 1.4e-4) and all 16 upstream examples keep CPU/MPS parity.
The MPS collision costs about 7x plain FP32. A CUDA regression run (#52, one
RTX 5070 Ti) passed the same criteria with output unchanged from main.
Merged to main through [PR #63](https://github.com/range-et/hawa-cfd/pull/63) (`8eec667`),
not released; #11 stays open for the batched MPS round (#53) on the merged commit.
[Repair record](docs/review-porous-kbc-repair.md).

### November 10, 2026 — GitHub backlog migration

Migrated all 38 active HAWA entries to GitHub Issues with evidence, acceptance
criteria, execution surfaces and dependencies. Existing IDs are preserved;
new work uses GitHub issue numbers. Retired the Markdown backlog, updated agent
instructions and added intake/PR templates. Published titles, bodies and labels
were checked against the migration payloads with no missing or duplicate entries.
This closes no product issues and adds no solver capability.
[Migration crosswalk and verification](docs/github-issue-migration.md).

### November 9, 2026 — merged Python issue closeout

[PR #6](https://github.com/range-et/hawa-cfd/pull/6) merged into main at
`bd8e624`, including refinement PR #7. The following scoped defects are closed
in development, not claimed installed or released:

- **HAWA-048 / HAWA-051 closed:** atomic immutable-field NPZ writes preserve old
  output on failure; both writers support long valid destination filenames.
  Fault-injection/round-trip controls and 35 focused native/Docker checks passed.
  Export review.
- **HAWA-049 / HAWA-052 closed:** refinement alignment is independent of world
  origin and invalid patch topology fails before solver allocation. Combined
  gate: 852 passed, 82 hardware skips, 33 contracts; CPU G6: 97,561 passed,
  4,898 device-blocked. Host/pre-Job validation remains HAWA-028.
  Domain review.
- **HAWA-050 closed:** pinned Python 3.9 CI provisioning and synchronized test
  dependency lock pass hosted checks and locked-sync verification.
  CI review.
- **HAWA-053 closed:** imported rough-wall filter history survives reset;
  repeated CPU replays match exactly.
- **HAWA-054 closed:** exterior-boundary workspace is included before allocation;
  large-case rejection and valid controls pass. The conservative estimate is not
  an OS memory limit.
- **HAWA-055 closed:** corresponding source includes verification inputs; exact
  package checks pass and packaged source collects 892 tests. Legacy example 09
  remains excluded. The last three repairs share the integration review:
  810 passed, 82 hardware skips, 33 contracts before the refinement merge.

These are recorded checks, not new test runs during this documentation closeout.
HAWA-001 numerical parity, broader HAWA-026 coverage, HAWA-028 host validation,
and Windows CUDA acceptance under HAWA-002/044–046 remain open. PR #8 is still
open; PR #9 merged into the study integration branch after #6 and is not yet in
main. Neither is counted as closing its umbrella issue.

### November 9 2026 HAWA-001 diagnostic increment

Added a bounded repeated-cell KBC diagnostic with exact FP32 inputs, actual
device/stage/stabilizer evidence and unchanged population criteria. Original
512-square/50-step CPU/MPS parity still fails; an improved but still-failing
scratch candidate was rejected. No production or vendor repair is claimed.
Diagnosis and limits. Review follow-up
HAWA-056/057 adds actual loaded-source validation and partial failure evidence.
HAWA-001 remains open.

### November 9 2026 domain relationship contracts (HAWA-028 partial / HAWA-052 candidate)

Independent Python state and intentional view overlap now have explicit relation
controls. A shared refinement bounds check preserves existing topology criteria
while rejecting unsupported patches before solver allocation, with fine/parent
indices in diagnostics. HAWA-049 alignment checks remain unchanged. Focused CPU
checks pass (82 native and Docker CPU tests). Final function gate: 852 passed,
82 skips, 33 state contracts, zero ratchet failures; matrices refreshed. Linux
CPU G6 and its combined checker pass with 4,898 MPS/CUDA rows explicitly blocked;
development packaging passes. HAWA-028 stays open for host/pre-Job workflow and
HAWA-052 remains an integration candidate.
Contract inventory and evidence.

### November 9 2026 airfoil dispatcher coverage (HAWA-026 tranche)

Added 23 public airfoil-dispatch cases with independent routing, invalid-input,
metadata, degree-unit and length-scaling assertions. Native/Linux focused suites
pass 29 cases; seven seeded faults are detected. After rebasing onto integration `588bffd`, the combined gate passes 899 tests,
with 83 hardware skips, 33 state contracts and zero ratchet failures. Promoted only
the freshly measured dispatcher baseline entry; no production behavior changed.
HAWA-026 remains open for other coverage debt; this is not physical validation or
a release. Review and limits.

### November 9 2026 HAWA-021/022 diagnostic harness (C1)

Added frozen-reference preparation/replay, strict source/frame/configuration
identity, explicit analysis windows and partial-scope reporting to the Python
nesting study. Fixed numerical criteria remain unchanged; HAWA-021/022 stay open.
No solver or host behavior changed. Original C1 checks: 32 focused tests, 656 suite
passes, 32 CUDA skips, 33 state contracts and zero function-gate failures. The
real bounded CPU run and replay retain the same RMS failure; see the C1 review.

PR #5 review additionally hardens malformed descriptor failures, records selected
source/child backends and exercises actual ratio-2 fine-reference replay with
nonzero warmup. A later damaged-archive finding is repaired with explicit ZIP,
DEFLATE and EOF failure reporting and refreshed-hash regression cases. Fresh
measurements are recorded in the C1 review.
### November 9 2026 long export filename review repair (HAWA-051 candidate)

Both Python NPZ writers now use bounded temporary prefixes, so valid long
basenames do not fail solely because an atomic-write suffix is appended. Four
new/overwrite regressions reproduced the failure before repair. Final combined
verification after incorporating PR #4: 35 focused tests on native and constrained
Linux CPU, 671 full native passes, 32 CUDA skips, 33 state contracts and zero
coverage failures. Matrices refreshed; no schema, solver or C# change.
HAWA-051 and the enclosing HAWA-048 PR remain pending integration.
Review follow-up.


### November 9 2026 immutable-frame export repair candidate (HAWA-048)

Implemented atomic NPZ publication for immutable-frame saves, complementing the
existing session-export repair. Observed cancellation and failed compression/IO
preserve earlier output and clean temporary files. Focused CPU tests: 31 passed
natively and in constrained Linux Docker. Full native gate: 637 passed, 32 CUDA
skips, 33 state contracts, zero coverage failures; matrices and development ZIP
checked. HAWA-048 remains open pending integration.
No format, solver, C# or installed-plugin change. Review.

### November 9 2026 refinement placement repair candidate (HAWA-049)

The Python refinement preflight now uses its existing absolute origin tolerance
without a translation-dependent relative allowance. Misaligned patches reject
before solver construction and report expected/received origins. Thirty new
regression cases plus the existing focused domain tests pass on CPU (58 passed,
four device cases deliberately deselected). Full measured gate passes with 654
Python tests, 32 CUDA skips and 33 state contracts; matrices are refreshed and
checked. Development build and ZIP integrity pass. Fresh Docker CPU G6 records
97,561 passes, zero failures and 4,898 unavailable MPS/CUDA rows, accounting for
all 102,459 expected rows with unchanged source. The combined checker links this
Linux matrix to the native suite/contract evidence without claiming a full GPU
matrix pass. Integration review remains pending; this is not a completed release
or closed issue. Review.


### November 9 2026 parent/child documentation (HAWA-034 partial)

Added a general [parent/child domain guide](docs/parent-child-domains.md), linked
from the GH user guide, example 33 instructions and roadmap. It distinguishes
separate recorded transfer, restricted coupled refinement and composed views,
with actual sample counts, spacing, time and ownership rules. Historical numerical
failures remain explicit. Example files are unchanged; canvas presentation and
live review remain open under HAWA-034. Documentation review.


### November 9 2026 CUDA blocker repairs in separate candidate

The isolated CUDA integration candidate repairs HAWA-044/045/046 and resolves
all 17 PR coverage blockers. Fresh local evidence: 700 tests passed, 82 device
skips, 33 state contracts, zero function-gate failures; current G6 source/evidence
recheck passes and development assemblies build. This code is not merged into
this checkout or published. See repair review
and Windows acceptance handoff. The original
main-checkout export increment is separate; CUDA and clean-host release remain
unverified.


### November 9 2026 atomic raw-result export

**HAWA-047 closed for Python export failure paths:** capture/compression failures
previously truncated an existing NPZ result. Exports now write a temporary sibling
and replace only after completion, preserving raw arrays and metadata. Ten focused
CPU tests and the full 624-pass/32-CUDA-skip suite pass; 33 state contracts pass,
and the function matrix is refreshed with no ratchet failures. No host install,
Windows check or release. HAWA-033 remains in progress for broader export UX/CSV;
baking is still HAWA-032. Review.

### November 9 2026 CUDA PR integration review

Reviewed PR #2 in an isolated no-commit combination with current source. Found
HAWA-044/045 evidence-validation defects and HAWA-046 MPS test alias failure.
After the local alias fix, 668 tests and 33 state contracts pass; 82 tests skip,
the function gate has 17 untested new/changed functions, and the original bounded
CPU/MPS PorousMedium comparison still fails. Local G6 also passes 100,010 rows with 2,449 unavailable-CUDA rows blocked.
PR remains unmerged, with no CUDA rerun or installed-candidate claim. Review and merge prerequisites.

### November 9 2026 CUDA PR planning follow-up

Linked existing PR #2’s headless CUDA evidence and numerical repairs into
HAWA-001/002/006 and the execution plan. Replaced duplicate CPU/CUDA investigation
with PR review/integration and current-source device checks. The PR is open;
reported branch results are not merged, independently reproduced or installed-host
qualification. Scope and remaining work.

### November 9 2026 issue execution planning

Classified all 35 open issues by isolated Python/C# work, device requirements and
live Rhino/GH acceptance; proposed a bounded worker/PR pilot and serial host
queue for user review. This is a plan, not implemented sandbox infrastructure or
completed verification. Plan and
documentation review.

### November 9 2026 user-notes intake

Reconciled user feedback into HAWA-027–043 and existing open issues, with
provisional verification/workflow/research groupings for later triage. Missing
cells and overlap validation remain unreproduced hypotheses; HAWA-024’s scoped
repair remains closed. No implementation or runtime checks were performed.
Documentation review.

### November 9 2026 function testing gate

Added the source/signature/test matrix, coverage.py call evidence, Roslyn C#
inventory and Coverlet state-contract measurement. The ratchet rejects new or
changed untested functions, lost coverage and stale committed reports; PR CI uses
the base commit's baseline. Local evidence: 614 Python passes, 32 CUDA skips and
33 state-contract passes. Existing debt remains HAWA-026. No solver or host
behavior changed; hosted CI and the long numerical gates were not run for this
increment. [Review](docs/review-function-testing.md).

### November 9 2026 compatibility gate

- **HAWA-019 closed for finite compatibility coverage:** executable G6 products,
  independent accept/reject rules, exact evidence checks and enum/node drift tests.
  97,418 expected results, zero failures, 1,873 CUDA rows blocked. 575 Python tests
  and 33 state contracts pass locally. [Scope and evidence](docs/compatibility-matrix.md).
- Added annotated **31** (tunnel/probes/checkpoints) and **32** (translation/recorded
  particles); both run in Rhino. All 52 public nodes now appear in 30 idle GH
  definitions with no archive errors. This is not a fresh simulation of every old
  example or exhaustive arbitrary-graph coverage.
- **HAWA-020 closed:** matrix-discovered 2D streamline broadcasting failure repaired
  in immutable and legacy field paths; all field product rows and planar-seed
  regressions pass. No numerical tolerance was relaxed.


### November 9 2026 neutral coupling and failed-gate repairs

- **HAWA-016 closed for the startup/settling test:** preserved the failed 24³
  startup result, diagnosed absent initial turbulent stress, added sampled/filtered
  wall reference and verified analytic wall/drive identities. A 200k-step CPU
  rough-channel run passes the unchanged 2%/5%/5% settling criteria; the coarse
  log-law metric has one independent probe. Atmospheric model qualification remains
  HAWA-003/011. [Evidence](docs/neutral-coupling-review.md).
- **HAWA-017 closed:** convective outgoing reconstruction reduces the enlarged-domain
  shear-pulse error from 18.28% to 2.34% (10% limit). Rough/open corner corrections
  preserve mass and applied tangential impulse. Cropped-body halo ownership and
  CPU/MPS regressions pass.
- **HAWA-018 closed:** old precursor archives load six original inputs and append
  three defaults without missing-chunk warnings. Parameter GUIDs and source wires
  survive, and examples 28–30 save/reopen correctly.
- Added annotated **example 30**. Live Rhino: MPS 1000 steps, CPU recovery 400,
  pause, invalid-input withholding/recovery and close during run. Examples 28–29
  still run. Development bundle only; Windows/CUDA and full atmospheric validation
  remain unverified.

### November 9 2026 project tracking established

Added the open-work and implemented-capability registers, linked them from the
entry documentation, and established maintenance rules in `AGENTS.md`. This is a
documentation change, with no solver, runtime, GH archive or release change.
See the documentation review.

### Earlier completed work retained as evidence

These are a concise index of existing records, not newly verified completions:

- 0.4 closeout: frozen experimental feature baseline,
  bundled source/licences and supported examples; numerical limits remain.
- [0.5 native work](docs/review-full-v0.5.md): selected geometry, shared state and
  native/GH workflows; read the later cleanup follow-up before treating its old
  cleanup finding as current.
- [Legacy GH cleanup repair](docs/review-cleanup-v0.5.md): retained retry ownership
  and fault-injection coverage close that finding for the recorded host/build.
- [Boundary foundation repairs](docs/general-boundaries-review.md): mapped/curved
  composition, slip-edge and incoming/wall findings have scoped repairs and
  regressions. Broader boundary qualification remains open as HAWA-004.

## Recording completed work

Keep this inventory concise and update existing rows before adding overlapping
ones. Add dated history for meaningful completions, preserving the `HAWA-NNN` ID
when closing an issue. Include what changed, affected scope/version, actual
checks/device, omissions, remaining limits and a link to the review or report.
Distinguish implemented, locally verified, packaged and publicly released states.
Create newly discovered follow-up work in GitHub Issues and reference its GitHub
number. Preserve legacy HAWA IDs; do not allocate new ones.


### November 9 2026 combined Python / CUDA integration candidate

The merged study branch and remote main now combine with the missing strict CUDA
evidence-runner repairs. Fresh local verification: 806 suite passes, 82 device
skips, 33 contracts, zero coverage failures; 97,561 CPU G6 passes with 4,898 GPU
rows blocked; development package checks pass. This candidate is not an installed
release. Integration review. HAWA-001 and
atmospheric qualification remain unresolved; Windows acceptance stays separate.


### Integration review repairs (November 9, 2026)

HAWA-053 preserves imported wall-filter state on reset; HAWA-054 includes exterior
matrix/link preparation in the conservative preflight budget; HAWA-055 includes
verification tools/configuration/docs/examples in the source bundle. The coverage
test dependency is now in uv.lock. Fresh combined gate: 810 passes/82 skips,
33 contracts, no ratchet failures; actual bundled source collects all 892 tests.
These repairs are merged into main through PR #6; they do not establish Windows/host
qualification. Evidence.
