# Hawa issues and future work

Open bugs, verification gaps, improvements and ideas. Maintainers and agents keep
this list current; the user can edit it too. Built capabilities and completed
work live in [features.md](features.md). Detailed sequencing lives in the
[roadmap](docs/roadmap.md), with individual tutorials in the
[example backlog](docs/example-roadmap.md).

Initial triage: November 9, 2026. Status is based on linked repository records,
not a fresh runtime audit. Newer scoped evidence can supersede an older report;
check the follow-ups before reopening a repaired finding.

## How to use this list

Use stable `HAWA-NNN` IDs, never renumber or reuse them. Types are **bug**
(observed defect), **verification gap**, **improvement** and **idea**. Statuses are
**open**, **in progress**, **blocked**, **planned** and **idea**. A suspected bug
must be labelled a hypothesis until reproduced. Priority is relative to the
affected scope; a numerical limitation does not automatically block unrelated UI
work. Owners remain unassigned until someone takes responsibility.

Each entry records the problem or question, evidence, next action and acceptance
condition. Update it in place. When completed, move its outcome and evidence to
[feature history](features.md#history), preserving the ID, and remove the active
entry here. For rejected/deferred decisions that close an item, record the reason
in that history without calling it an implemented feature. Keep unresolved parts
open. Do not paste session transcripts or duplicate detailed benchmark logs.

## Execution surface and review plan

Every active issue has an execution surface below. **Headless work is not the
same as full issue closure**: device parity, UI, document persistence and GH
scheduling may still require hardware or a live host. The
[per-issue execution plan](docs/issue-execution-plan.md) specifies isolated work,
remaining gates, shared resources, dependencies and proposed batches for review.
These are source-based routing assessments, not fresh runtime passes or assigned
agent tasks. Keep the surface and plan row current when an issue’s scope changes.

The [next-ten Python proposal](docs/issue-execution-plan.md#next-ten-python-issues--proposed-scope-for-review) ranks HAWA-001/021/022/004/028/035/038/033/007/026 and defines the integrated base, separate PR boundaries and three-agent queue. These are proposed increments; existing issue statuses and host/device gaps remain unchanged.

## November 9 notes intake

The user’s November 9, 2026 notes are summarized below; this is issue intake,
not implementation approval or a fresh runtime audit. New HAWA-027–043 entries
are dated **November 9, 2026**, owned by **unassigned**, and cover the current
experimental native/GH development workflow unless narrowed in the row. Reports
of missing cells and unwanted defaults lack an exact build/file and remain
unreproduced. Existing IDs retain their ownership and evidence.

Provisional triage for discussion (effort and priority are not yet estimated):

- **Check first:** HAWA-027 missing boundary cells, HAWA-028 domain intersections,
  HAWA-029 panel startup, HAWA-030 visualization/GH handoff. These have small
  first verification steps, not necessarily small fixes. Check current installed
  versus development builds and existing capabilities before scheduling work.
- **User workflow candidates:** HAWA-031–039 cover cell inspection, preservation,
  export, general nesting language, solver guidance, boundary helpers, repeatable
  host tests, probes/loads and user docs. Discuss their value and scope next.
- **Research or separate scope:** HAWA-040–043, plus existing HAWA-009/010/012/013,
  need bounded feasibility/physics decisions before implementation. No promised
  millisecond particle results or blanket accuracy ranking between methods.
- **Existing work remains visible:** HAWA-001 parity; HAWA-002/006 platform/setup;
  HAWA-003/004/011/021/022 atmospheric qualification; HAWA-005 load validation;
  HAWA-007/008 views/application examples; HAWA-014 performance research;
  HAWA-015 propulsion/free surfaces; HAWA-026 measured coverage debt. Their
  inclusion here neither raises nor lowers priority automatically.

The notes’ atmospheric failure table belongs to HAWA-021/022/011, not six new
bugs. The [transfer follow-up](docs/neutral-transfer-review.md) records 1:1 RMS
error 14.60% (10% limit), reference stationarity 13.26% (5%), and 2:1 mean/RMS
errors 13.34%/127.57% (5%/10%). A longer 1:1 window also fails. The 6-cells/H
mean-flow case passes its bounded criteria but has 95.26% TKE error; 4-cells/H
hits 64.84% against 66%. Separate transfer error from settling and missing
sustained turbulent inflow; longer runtime alone is not an established fix.
HAWA-001 also includes upstream/backported CPU disagreement, so MPS alone is
not an established cause. These are historical results, not newly run tests.

## Bugs and verification gaps

**HAWA-026 — Function coverage debt (open; owner: Codex).**
Execution surface: Python, headless C# contracts and host-only C#; split by file
and measured coverage gap as described in the [execution plan](docs/issue-execution-plan.md). The
[function matrix](docs/function-test-matrix.md) records uncovered first-party
Python and unmeasured host-only C# methods. The new gate prevents new or changed
functions from adding debt, but existing unchanged gaps remain. Close individual
gaps with asserting tests and measured execution, update the baseline to preserve
the improvement, and retain separate live Rhino and numerical validation. Full
closure requires resolving all executable gaps in the declared inventory; a node's
presence in an example or a passing suite name is not function-level evidence.

| ID | Type and status | Scope and evidence | Next action and acceptance | Execution surface |
| --- | --- | --- | --- | --- |
| HAWA-021 | Bug · in progress (owner: Codex, November 9 2026) | The imported-data rejection is repaired in development and the three-stage CPU/MPS GH workflow runs. Nested statistical and atmospheric qualification still prevent completion. [Completion contract](docs/atmospheric-nesting-implementation.md). | [PR #5](https://github.com/range-et/hawa-cfd/pull/5) adds frozen-reference replay with explicit failure/device provenance and fine-reference regressions; it does not repair numerical failures. Retain passing v2/manufactured/host gates; fix nested mean/RMS and stationary-turbulence comparisons. Current 6-cells/H AIJ mean-flow checks pass, but TKE and grid sensitivity remain open. Do not close with a short workflow demo. | Python + CPU/MPS; GH regression |
| HAWA-022 | Bug · in progress (owner: Codex, November 9 2026) | Long AIJ cube runs and a mapped nested child reveal kinetic instability at open faces, including ground/open intersections. Short finite-step gates missed it. Failed runs retained under `results/atmosphere-nesting/`. | Constrained stress reconstruction now passes wall/pulse checks and a 60k-step MPS reference run stays healthy. Nested long-window mean/RMS and reference stationarity still fail; qualify sustained turbulence and resolution sensitivity without changing viscosity or thresholds. | Python + CPU/MPS; GH regression |
| HAWA-001 | Bug · open | PorousMedium CPU/MPS pointwise disagreement remains open. [PR #2](https://github.com/range-et/hawa-cfd/pull/2) records a CPU/CUDA KBC precision repair, retaining the MPS FP32 path; it does not close CPU/MPS parity. [Historical evidence](docs/hardening-v0.4.md). | The combined review candidate still fails original 50-step CPU/MPS criteria for populations, velocity and pressure ([fresh review](docs/review-cuda-pr2.md)). Review the precision tradeoff and fix remaining differences without widening tolerances. Diagnose only remaining differences rather than duplicate the CPU/CUDA repair. Close only with scoped comparison evidence; finite fields alone do not close it. | Python + CPU/MPS |
| HAWA-002 | Verification gap · in progress (headless evidence in PR #2; host owner unassigned) | Windows native behavior and clean-machine dependency installation remain unverified. [PR #2](https://github.com/range-et/hawa-cfd/pull/2) records bounded headless CPU/CUDA passes on RTX 5070 Ti; the PR has merged into remote main, but its bounded evidence predates this checkout’s newer gates. [Integration plan](docs/issue-execution-plan.md#existing-windows-cuda-pr). | Local candidate repairs HAWA-044/045/046 and passes the function gate with all 17 coverage blockers resolved ([repair review](docs/review-cuda-blocker-fixes.md)). Run the [exact Windows acceptance checks](docs/windows-cuda-merge-checks.md) on that candidate before integration. Retain its bounded CUDA evidence separately from pending clean Windows Rhino installation, lifecycle and wider CUDA coverage. Track each platform/scope independently. | Platform + Rhino/GH + CUDA |
| HAWA-003 | Verification gap · in progress (owner: Codex) | Legacy coarse-grid molecular-air scaling remains restricted; the experimental shifted-population precursor now runs the tested CPU/MPS cases. General qualification remains open. [Measured blocker](docs/atmosphere-delivery.md#reproduced-numerical-blocker). | Select and verify an appropriate collision/precision/model strategy at physical viscosity. Preserve guards; do not increase viscosity or relax tolerances to claim qualification. | Python + CPU/MPS; host integration |
| HAWA-004 | Verification gap · in progress (owner: Codex) | Shifted external mode now verifies halo-classified cropped buildings, side/top inflow, reversal, corner mass budget and a smooth outgoing pulse. General vortex/acoustic reflection and arbitrary separated cut-face accuracy remain open. [Boundary gate record](docs/general-boundaries-review.md). | Add enlarged-domain/reference comparisons, reversal and edge/corner tests with criteria fixed before runs. Keep supported combinations explicit. | Python + CPU/MPS; host integration |
| HAWA-005 | Verification gap · open | Engineering loads for real RC wings, drone parts and hulls are not established by coarse demonstrations. [Limits](docs/release-notes-v0.4.0.md) and [RC example track](docs/example-roadmap.md#priority-rc-drone-and-small-boat-examples). | Pick a regime and observable, obtain suitable reference data, and measure grid/domain/time sensitivity. Qualify individual cases rather than the whole engine. | Python + numerical references; Rhino demo |
| HAWA-027 | Verification gap · open; trim-regression hypothesis | User reports missing cells at the yellow domain box in a “prebaked” example, and around the obstacle after native Solve. Exact file/build/view is unknown. Current-source audit: native [SliceDisplay](plugin/Hawa.Shared/SliceDisplay.cs) calls wall-link-only [SliceCutCells](plugin/Hawa.Shared/SliceCutCells.cs); snapshot [field collection](src/hawa/field_collection.py) has separate halfway-mask clipping. This is a candidate explanation for the obstacle band, not a fresh host reproduction. HAWA-024 remains closed for its scoped snapshot repair: [follow-up](docs/neutral-transfer-review.md). | Identify the file/build and reproduce outer-domain versus solid-wall gaps separately in native, legacy and snapshot views. Check other supported examples on copies; preserve example 09. Compare retained fluid area, cell/sample extents, raw validity and rendered geometry. Close with reproducible evidence of correct behavior, or a scoped repair/regression; do not reopen HAWA-024 wholesale. | Python + headless C# + Rhino/GH |
| HAWA-028 | Verification gap · in progress (Codex domain agent) | Python contract audit distinguishes independent Sessions, fixed 2:1 coupling and view-only composition. HAWA-052 reproduces late refinement topology rejection; supported view intersections remain accepted. [Scoped review](docs/review-domain-relationships.md). | Complete scoped checks/PR for early solver-allocation rejection. Host/C# object identification, pre-Job validation and actual Rhino/GH workflow remain open; do not impose a blanket overlap ban or close the umbrella issue. | Python contracts + C# preflight + Rhino/GH |
| HAWA-030 | Verification gap · open | User sees only colour meshes in the native panel and asks where other views went and whether the UI generates a hidden GH graph. [Native guide](docs/native-v0.5.md) documents a shared case and Linked Case binding; [feature inventory](features.md) records broader GH views. | Audit actual native/GH view availability and the command/state path, then document it. Assess an explicit “Open in Grasshopper” handoff using existing bindings; specify new versus existing definitions and preservation of user graphs. Close the audit with an observed capability map and a decision on the handoff; any implementation must preserve case identity and avoid duplicate ownership. | Docs/C# audit + Rhino/GH |
| HAWA-044 | Bug · in progress (Codex; November 9, 2026) | Filtered/incomplete CUDA suite acceptance repaired in the isolated integration candidate: independent IDs, completed outcomes, strict JUnit and explicit partial scope. Adverse tests and full local measured gate pass. [Repair review](docs/review-cuda-blocker-fixes.md). | Run exact-candidate Windows CUDA acceptance, then integrate. No hardware pass is inferred from mocked orchestration tests. | Python harness + CPU mocks; CUDA acceptance |
| HAWA-045 | Bug · in progress (Codex; November 9, 2026) | Candidate now hashes complete tracked/nonignored inputs and Git index, records staged/combined diffs, and rejects source drift. Mutation tests and local measured gate pass. [Repair review](docs/review-cuda-blocker-fixes.md). | Qualify unchanged candidate on Windows and integrate; preserve source/test/config/lock and index provenance. | Python harness + CPU mocks; CUDA acceptance |
| HAWA-046 | Bug · in progress (Codex; November 9, 2026) | Candidate compares actual before/after devices, accepting MPS alias normalization. The same narrow assertion repair at a92dbb1 merged through PR #2 into remote main: fresh old-branch suite 202 passed/79 skips; combined candidate historical evidence is 700 passed/82 skips. No numerical tolerance change. [Repair review](docs/review-cuda-blocker-fixes.md). | Verify CUDA cases on Windows and integrate the accepted candidate; source remains separate from main export work. | Python tests + MPS/CUDA |
| HAWA-048 | Bug · in progress (owner: export agent / Codex; November 9, 2026) | Python immutable-frame save in `fields.py` truncates the destination before compression. Fault injection turns an existing valid 887-byte NPZ into 7 bytes and leaves a partial new file. Distinct from repaired session export HAWA-047. [Study](docs/python-sandbox-launch-plan.md#initial-study-results--completed). | [PR #3](https://github.com/range-et/hawa-cfd/pull/3) implements atomic save; review follow-up HAWA-051 repairs long destination filenames in both NPZ writers. Revised local/hosted gates pass and the PR merged into the study base; main-development integration remains. Preserve the old file or absent destination on capture/write/flush/replace failure; clean temporary output and verify exact array/metadata round trips. Scope ownership: fields.py and dedicated field-export tests. Host UI remains separate. | Python filesystem/immutable frames |
| HAWA-049 | Bug · in progress (owner: domain agent / Codex; November 9, 2026) | Python refinement origin preflight uses default relative tolerance: a 1 m fine-grid misalignment is rejected near zero but accepted at parent x=1,000,000 m, and the solver advances. Valid translated controls pass. [Study](docs/python-sandbox-launch-plan.md#initial-study-results--completed). | [PR #4](https://github.com/range-et/hawa-cfd/pull/4) merged into the study base with translation-independent alignment and early rejection. Native function and Linux CPU G6 checks passed; main-checkout/device/release integration remains separate. This does not reproduce the native trimming symptom or close all overlap policy. | Python refinement validation; devices for runtime |
| HAWA-052 | Bug · in progress (Codex domain agent; November 9, 2026) | Unsupported refinement patch bounds/resolution reached parent Session allocation before existing stepper validation; malformed corners lacked domain diagnostics. Eighteen pre-repair regression failures at origin zero/1,000,000. [Review](docs/review-domain-relationships.md). | Shared bounds validation now rejects before Session/Simulation construction and identifies fine/parent indices; focused CPU checks pass. Complete full gates and PR integration; preserve direct-stepper defenses and HAWA-049. Async Job creation/host checks stay under HAWA-028. | Python refinement preflight |

**HAWA-051 — Long valid NPZ destination filenames (in progress; owner: Codex export agent; November 9, 2026).**
Execution surface: Python filesystem, immutable-frame and session export writers.
PR #3 review exposed temporary filenames constructed from the full destination
basename. Both writers fail with `ENAMETOOLONG` for a valid 250-byte ASCII target.
New/overwrite regressions reproduce the defect in both paths. Fixed bounded
prefixes pass 35 focused tests in the isolated branch; the full 671-pass/32-CUDA-skip gate, 33 contracts and 35 Docker tests pass.
Fix merged through [PR #3](https://github.com/range-et/hawa-cfd/pull/3) into the study base; main-development integration remains pending.
Completion: preserve round trips, prior output and temporary cleanup for valid
long destinations in both writers. No host export UI claim.

## Improvements and delivery work

| ID | Type and status | Desired outcome | Next action and acceptance | Execution surface |
| --- | --- | --- | --- | --- |
| HAWA-006 | Improvement · planned | Seamless macOS/Windows setup around embedded Python/PyTorch. [Runtime decision](docs/roadmap.md#runtime-foundation-and-installation). | PR #2 reports that plain torch==2.8.0 installed a CPU-only Windows wheel; embedded bootstrap CUDA selection remains open. Define clean-install, first-run, update and interrupted-download recovery checks; show progress and actionable errors. Link platform evidence to HAWA-002. | Bootstrap/build + clean OS + Rhino |
| HAWA-007 | Improvement · planned | GH_Wind-inspired movable vector slices shared by native/GH/agent workflows. Existing vector nodes are not the complete integrated workflow. [Design direction](docs/roadmap.md#the-proposed-distinction). | Extend the shared-snapshot views with arrow density/scale, scalar overlay, explicit projection mode, masking and fixed legends; moving the view must not restart the solver. | Python + C# + Rhino/GH |
| HAWA-008 | Improvement · planned | Drone and small-boat examples lead onboarding. [Example priorities](docs/example-roadmap.md#first-additions-to-prioritize). | Build a stationary drone-part workflow and submerged rudder/fin workflow with honest demo limits, reproducible settings and useful vector views. Geometry stays in ordinary GH assemblies. | Docs + GH archives + Rhino |
| HAWA-009 | Improvement · planned | User-defined local refinement regions. [Refinement plan](docs/roadmap.md#user-defined-local-refinement-regions). | Specify supported ratios and coupling; verify conservation, error, memory, lifecycle and wall combinations against a uniform fine reference before advertising multiple regions/levels. | Python + C# + Rhino/GH |
| HAWA-010 | Improvement · planned | Reuse one physical case across numerical methods. [Shared-case direction](docs/roadmap.md#one-physical-case-with-a-choice-of-solvers). | Prove one overlapping case with two actual methods, preserve physical intent and measurements, and explicitly reject unsupported physics. The shared boundary schema alone is not a second solver. | Python/adapter + C# + Rhino/GH |
| HAWA-011 | Improvement · in progress (owner: Codex) | Neutral atmosphere now includes the experimental shifted solver, planar rough wall and GH examples 28–29; full delivery remains incomplete. [Delivery checklist](docs/atmosphere-delivery.md). | Continue its explicit numerical, wall, turbulence, nesting and host gates. The shifted candidate removes the tested representation blocker; broader atmospheric accuracy, turbulence statistics, transitions and nesting remain required. Status must follow that checklist, not the existence of utility functions. | Umbrella: Python + devices + Rhino/GH |
| HAWA-029 | Improvement · in progress (Codex; November 9, 2026) | User dislikes a domain being prepopulated when opening the Hawa tab. Fresh [installed-host audit](docs/review-native-intake.md) confirms opening Hawa in an empty Rhino 8.36 document creates the idle 8 × 6 × 4 m block case and preview without a solver job. The [native guide](docs/native-v0.5.md) retains an explicit Block preset. | Check clean-document, saved-case and panel-reopen behavior. The clean-document behavior is reproduced; make the demo preset an explicit opt-in, preserving saved/legacy setup; opening the panel should not create an unwanted case/domain or overwrite restored setup. Verify save/reopen and existing bindings. Missing cells remain HAWA-027. | C# state + Rhino panel |
| HAWA-031 | Improvement · open | Inspect computational cell boundaries on a section plane and optionally bake the whole grid. User’s assumption that the domain is already a collection of Rhino meshes is unverified. [Native scope](docs/native-v0.5.md). | Specify lattice sites versus cell volumes, solid/fluid masks, physical walls and nested ownership; prototype a bounded cell-edge section and whole-grid export with size estimates/cancellation. Accept only correctly located, labelled geometry with declared limits; ordinary scalar display samples must not masquerade as solver cells. | Python/grid data + C# geometry + Rhino/GH |
| HAWA-032 | Improvement · open | Preserve a completed result as a Rhino artifact on a separate layer, beyond a transient viewport. Existing recording/playback is listed in [features](features.md); a saved case is not saved solver tensors. | Audit current baking, then define an explicit snapshot bake with units, case/revision/run, field/time, raw values and colour range. Verify it survives save/reopen and subsequent simulations without overwriting previous results. RGB alone is not a lossless numerical field; define metadata/sidecar storage and partial-write handling. | C# document writes + Python metadata + Rhino |
| HAWA-033 | Improvement · in progress (Codex; November 9, 2026) | Export usable numerical results, e.g. CSV, separately from Rhino baking. Existing field/recording paths may cover part of the need; [node catalogue](docs/node-catalog-v0.5.md). | Audited existing raw NPZ export and repaired atomic replacement (HAWA-047, [evidence](docs/review-export-atomicity.md)); CSV/baking and host UX remain open. Specify fields/probes/loads, positions, units, validity, time, reference quantities and provenance. Export a bounded result, read it back and compare raw values under declared precision; test cancellation and incomplete files. Coordinate artifact identity with HAWA-032. | Python export core + GH/Rhino integration |
| HAWA-034 | Improvement · in progress (Codex; November 9, 2026) | Added the [parent/child guide](docs/parent-child-domains.md), neutral role/resolution map, and navigation from the GH guide, example 33 README and roadmap. It distinguishes offline transfer, coupled refinement and composed views; numerical failures remain explicit. [Review](docs/review-parent-child-guide.md). | Documentation increment complete. Make roles visible on a copy of example 33 in Rhino, preserving IDs/wires/values and updating name-dependent harness lookups if needed; verify the actual canvas workflow before closing. No solver qualification claim. | Docs complete; GH presentation requires Rhino |
| HAWA-035 | Improvement · open | Solver/collision choices need understandable help and compatible options; speed/accuracy labels need evidence. [Compatibility guide](docs/compatibility-matrix.md), HAWA-010. | Map supported combinations to UI options and explain model, cost, limits and device selection. Verify invalid combinations are rejected with reasons and archived settings remain readable. Avoid universal “fast/accurate” rankings; benchmark any comparative label and expose unsupported physics rather than silently ignoring it. | Python capabilities + C# UI + Rhino/GH |
| HAWA-036 | Improvement · open | Styled viewport arrows/labels for inlet, outlet, slip and wall boundaries. Existing domain wireframe is insufficient for the requested explanation. [Boundary guide](docs/general-boundaries.md). | Define normals, inflow/outflow direction, patch identity and a readable legend; test corners, overlapping labels, units and view changes. Acceptance: displayed assignments match accepted solver settings, remain legible and do not restart physics. Keep field-vector work in HAWA-007. | C# display + Rhino/GH |
| HAWA-037 | Improvement · open | Run scoped Rhino integration checks sequentially in one session, resetting between cases. Repeated restarts/crashes are a user concern, not a newly reproduced causal finding. [Host coverage](examples/grasshopper/VERIFICATION.md). | Inventory supported nonblocking harnesses; compose a poll-driven runner with fresh evidence IDs, timeouts, cooperative cancellation and document isolation. Verify two successive runs plus failure recovery, zero owned jobs/sessions after teardown and preserved user geometry. Never reuse the obsolete blocking harness or kill Rhino; loaded-assembly updates may still require normal Quit. | C# harness + Rhino/GH + build coordination |
| HAWA-038 | Improvement · open | Pressure sensors/history, net forces, lift/drag coefficients and angle-of-attack/airspeed plots, eventually for multipart lofted wings. Existing probes, loads and local-polar/LLT tools need an availability audit: [catalogue](docs/node-catalog-v0.5.md), [RC example track](docs/example-roadmap.md#priority-rc-drone-and-small-boat-examples). | Inventory operations and define a bounded probe/load/sweep workflow with pressure reference, axes/signs, reference area/speed/density, averaging and completed-candidate IDs. Verify formulas and provenance, then link physical qualification to HAWA-005. Keep supplied polars/LLT distinct from CFD loads; geometry remains ordinary GH and a new public node needs a reusable contract. | Python probes/loads + C# + Rhino/GH |
| HAWA-039 | Improvement · open | Searchable human- and agent-readable user documentation/site, beyond agent instructions. Existing [native](docs/native-v0.5.md) and [GH](docs/plugin.md) guides provide source content. | Inventory setup, model selection, examples, results and troubleshooting gaps; select a maintainable publishing format with versioned source and working links. Acceptance: a new user can follow one end-to-end workflow, find supported physics/platform limits and distinguish installed release docs from development docs. No hosting or publication choice yet. | Docs/site; host evidence for tutorials |

## Research ideas

| ID | Type and status | Question | Next action and acceptance | Execution surface |
| --- | --- | --- | --- | --- |
| HAWA-012 | Idea · idea | Would a fast particle method improve an RC-relevant liquid exploration workflow? [Solver research](docs/roadmap.md#scope-the-first-additional-solvers-narrowly). | Scope one physics experiment with conservation, stability, cost and interaction criteria; measure a PyTorch candidate before adopting it, including preparation and extraction rather than promising millisecond results. A splash render is not hull-resistance evidence. | Research → Python + devices |
| HAWA-013 | Idea · idea | Add conventional finite-volume engineering CFD without rebuilding physical setup. [Integration direction](docs/roadmap.md#scope-the-first-additional-solvers-narrowly). | Evaluate an established engine and its distribution terms; include the user-suggested FluidDyn/fluidsim repository as an unreviewed research lead, not an assumed finite-volume adapter; reproduce a bounded benchmark through the shared job/result contract. No general solver rewrite commitment. | Research → external engine/adapter |
| HAWA-014 | Idea · idea | Accelerate a demonstrated bottleneck with Rust if worthwhile. [Runtime decision](docs/roadmap.md#runtime-foundation-and-installation). | Profile a representative complete workflow first; compare simpler optimizations and one small native prototype. Require measured end-to-end benefit, numerical parity and manageable packaging; no Rust rewrite scheduled. | Profiling → Python/native + target device |
| HAWA-015 | Idea · idea | Surface-running RC boats and powered propulsion. [RC track](docs/example-roadmap.md#priority-rc-drone-and-small-boat-examples). | Scope free surface, flotation/trim and rotor/propeller interactions separately, with suitable reference experiments. Current submerged hull and prescribed-paddle demos do not implement the complete applications. | Research → physics + devices + Rhino |

| HAWA-040 | Idea · idea | Non-destructive union/classification of multipart geometry using voxel/SDF/VDB-style methods, potentially GPU accelerated, instead of requiring a CAD boolean union. Points/trees and particle reuse are proposals, not proven architecture. [Native geometry scope](docs/native-v0.5.md). | First verify what existing multi-body input already supports. Compare one bounded implicit-union prototype against current classification for overlaps, thin walls, gaps and open meshes; measure wall-location error, memory and end-to-end cost. Accept or reject feasibility with evidence; do not assume scattered points preserve watertight geometry. | Research → Python geometry + C# + Rhino |
| HAWA-041 | Idea · idea | Multiple inflow streams and user-drawn vector forcing with spatial masks. These are distinct boundary and volume-force operations. [Boundary foundation](docs/general-boundaries.md). | Audit existing multi-face inflow, then scope inlet patches separately from masked body forcing. Define units, interpolation, temporal behavior and overlap rules; verify mass/momentum balance and a reference flow before exposing controls. No unmasked global force substitution for the requested local action. | Research → Python physics + C# + Rhino/GH |
| HAWA-042 | Idea · idea | Thermal transport, surface heating/cooling, buoyancy and selectable physical assumptions. Current model is isothermal/neutral: [scope](docs/atmosphere-delivery.md). | Scope temperature transport separately from buoyancy/stratification and solid heat transfer; evaluate a validated coupling approach with thermal properties and boundary conditions. Define energy-balance and reference benchmarks before implementation. Settings must advertise actual capabilities and reject unsupported requests; pressure/incompressibility/temperature are not interchangeable flags. | Research → Python thermal physics + host integration |
| HAWA-043 | Idea · idea | Stronger verification beyond function execution coverage: static typing/linting, runtime contracts, property/fuzz tests, mutation tests and deterministic/differential snapshots. The pasted tool list, commands, timing estimates and 80% mutation threshold are unvalidated suggestions. [Current function gate](docs/function-testing.md), HAWA-026. | Audit existing checks and pilot one risky boundary/state/parser or numerical invariant. Assess Python 3.9/pinned-dependency compatibility, licensing, false positives and CI cost before selecting tools or thresholds. Require tests to detect seeded faults; distinguish deterministic metadata snapshots from tolerance-based numerical comparisons. Passing automation does not mathematically prove correctness or replace review, host checks or physics validation. | Python/.NET tooling + CI; host gate retained |

The “spaghetti vortex” tutorial suggestion belongs to the
[example backlog](docs/example-roadmap.md), under HAWA-008’s example intake:
identify the intended vortex phenomenon/reference first, compare existing vortex
examples, and choose a reproducible visualization with explicit demo limits.
Do not create a new numerical capability or public node from that phrase alone.

## Hosted CI environment

**HAWA-050 — Python 3.9 hosted CI provisioning (in progress; owner: Codex; November 9, 2026).**
Execution surface: CI configuration. `ubuntu-latest` selected Ubuntu 26.04,
which lacked the required Python 3.9 binary; a follow-up exposed pip metadata and
specialized-index dependency resolution failures. The shared study base pins
Ubuntu 24.04/Python 3.9.25/pip 25.3 and separates the CPU torch wheel from normal
PyPI resolution. Initial PR #3/#4/#5 hosted gates passed. [Evidence](docs/review-python-ci-runner.md).
Next action/completion: preserve passing checks on revised heads and integrate
the shared-base fix into the main development branch. No runtime dependency or
numerical threshold change.

## Adding an item

Use the next unused ID. Include type/status, date, owner or “unassigned,” affected
version/scope, repro or hypothesis, evidence link, and the smallest next action
with a completion criterion. The seed entries above are dated November 9, 2026
and unassigned. Being listed is not authorization to expand a release scope.
