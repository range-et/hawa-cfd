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

## Bugs and verification gaps

**HAWA-026 — Function coverage debt (open; owner: Codex).** The
[function matrix](docs/function-test-matrix.md) records uncovered first-party
Python and unmeasured host-only C# methods. The new gate prevents new or changed
functions from adding debt, but existing unchanged gaps remain. Close individual
gaps with asserting tests and measured execution, update the baseline to preserve
the improvement, and retain separate live Rhino and numerical validation. Full
closure requires resolving all executable gaps in the declared inventory; a node's
presence in an example or a passing suite name is not function-level evidence.

| ID | Type and status | Scope and evidence | Next action and acceptance |
| --- | --- | --- | --- |
| HAWA-021 | Bug · in progress (owner: Codex, November 9 2026) | The imported-data rejection is repaired in development and the three-stage CPU/MPS GH workflow runs. Nested statistical and atmospheric qualification still prevent completion. [Completion contract](docs/atmospheric-nesting-implementation.md). | Retain passing v2/manufactured/host gates; fix nested mean/RMS and stationary-turbulence comparisons. Current 6-cells/H AIJ mean-flow checks pass, but TKE and grid sensitivity remain open. Do not close with a short workflow demo. |
| HAWA-022 | Bug · in progress (owner: Codex, November 9 2026) | Long AIJ cube runs and a mapped nested child reveal kinetic instability at open faces, including ground/open intersections. Short finite-step gates missed it. Failed runs retained under `results/atmosphere-nesting/`. | Constrained stress reconstruction now passes wall/pulse checks and a 60k-step MPS reference run stays healthy. Nested long-window mean/RMS and reference stationarity still fail; qualify sustained turbulence and resolution sensitivity without changing viscosity or thresholds. |
| HAWA-001 | Bug · open | PorousMedium CPU/MPS pointwise disagreement exceeds the existing tolerance. [Hardening evidence](docs/hardening-v0.4.md). | Reproduce on declared versions, isolate the cause and retain the original comparison criteria. Close only with a justified repair and comparison evidence; finite fields alone do not close it. |
| HAWA-002 | Verification gap · open | Windows native behavior, CUDA hardware and clean-machine dependency installation remain unverified in the [release review](docs/release-review-v0.5.md). | Run the applicable installation, native lifecycle and numerical checks on actual environments. Track each platform separately; a CPU/MPS pass cannot close CUDA. |
| HAWA-003 | Verification gap · in progress (owner: Codex) | Legacy coarse-grid molecular-air scaling remains restricted; the experimental shifted-population precursor now runs the tested CPU/MPS cases. General qualification remains open. [Measured blocker](docs/atmosphere-delivery.md#reproduced-numerical-blocker). | Select and verify an appropriate collision/precision/model strategy at physical viscosity. Preserve guards; do not increase viscosity or relax tolerances to claim qualification. |
| HAWA-004 | Verification gap · in progress (owner: Codex) | Shifted external mode now verifies halo-classified cropped buildings, side/top inflow, reversal, corner mass budget and a smooth outgoing pulse. General vortex/acoustic reflection and arbitrary separated cut-face accuracy remain open. [Boundary gate record](docs/general-boundaries-review.md). | Add enlarged-domain/reference comparisons, reversal and edge/corner tests with criteria fixed before runs. Keep supported combinations explicit. |
| HAWA-005 | Verification gap · open | Engineering loads for real RC wings, drone parts and hulls are not established by coarse demonstrations. [Limits](docs/release-notes-v0.4.0.md) and [RC example track](docs/example-roadmap.md#priority-rc-drone-and-small-boat-examples). | Pick a regime and observable, obtain suitable reference data, and measure grid/domain/time sensitivity. Qualify individual cases rather than the whole engine. |



## Improvements and delivery work

| ID | Type and status | Desired outcome | Next action and acceptance |
| --- | --- | --- | --- |
| HAWA-006 | Improvement · planned | Seamless macOS/Windows setup around embedded Python/PyTorch. [Runtime decision](docs/roadmap.md#runtime-foundation-and-installation). | Define clean-install, first-run, update and interrupted-download recovery checks; show progress and actionable errors. Link platform evidence to HAWA-002. |
| HAWA-007 | Improvement · planned | GH_Wind-inspired movable vector slices shared by native/GH/agent workflows. Existing vector nodes are not the complete integrated workflow. [Design direction](docs/roadmap.md#the-proposed-distinction). | Extend the shared-snapshot views with arrow density/scale, scalar overlay, explicit projection mode, masking and fixed legends; moving the view must not restart the solver. |
| HAWA-008 | Improvement · planned | Drone and small-boat examples lead onboarding. [Example priorities](docs/example-roadmap.md#first-additions-to-prioritize). | Build a stationary drone-part workflow and submerged rudder/fin workflow with honest demo limits, reproducible settings and useful vector views. Geometry stays in ordinary GH assemblies. |
| HAWA-009 | Improvement · planned | User-defined local refinement regions. [Refinement plan](docs/roadmap.md#user-defined-local-refinement-regions). | Specify supported ratios and coupling; verify conservation, error, memory, lifecycle and wall combinations against a uniform fine reference before advertising multiple regions/levels. |
| HAWA-010 | Improvement · planned | Reuse one physical case across numerical methods. [Shared-case direction](docs/roadmap.md#one-physical-case-with-a-choice-of-solvers). | Prove one overlapping case with two actual methods, preserve physical intent and measurements, and explicitly reject unsupported physics. The shared boundary schema alone is not a second solver. |
| HAWA-011 | Improvement · in progress (owner: Codex) | Neutral atmosphere now includes the experimental shifted solver, planar rough wall and GH examples 28–29; full delivery remains incomplete. [Delivery checklist](docs/atmosphere-delivery.md). | Continue its explicit numerical, wall, turbulence, nesting and host gates. The shifted candidate removes the tested representation blocker; broader atmospheric accuracy, turbulence statistics, transitions and nesting remain required. Status must follow that checklist, not the existence of utility functions. |


## Research ideas

| ID | Type and status | Question | Next action and acceptance |
| --- | --- | --- | --- |
| HAWA-012 | Idea · idea | Would a fast particle method improve an RC-relevant liquid exploration workflow? [Solver research](docs/roadmap.md#scope-the-first-additional-solvers-narrowly). | Scope one physics experiment with conservation, stability, cost and interaction criteria; measure a PyTorch candidate before adopting it. A splash render is not hull-resistance evidence. |
| HAWA-013 | Idea · idea | Add conventional finite-volume engineering CFD without rebuilding physical setup. [Integration direction](docs/roadmap.md#scope-the-first-additional-solvers-narrowly). | Evaluate an established engine and its distribution terms; reproduce a bounded benchmark through the shared job/result contract. No general solver rewrite commitment. |
| HAWA-014 | Idea · idea | Accelerate a demonstrated bottleneck with Rust if worthwhile. [Runtime decision](docs/roadmap.md#runtime-foundation-and-installation). | Profile a representative complete workflow first; compare simpler optimizations and one small native prototype. Require measured end-to-end benefit, numerical parity and manageable packaging; no Rust rewrite scheduled. |
| HAWA-015 | Idea · idea | Surface-running RC boats and powered propulsion. [RC track](docs/example-roadmap.md#priority-rc-drone-and-small-boat-examples). | Scope free surface, flotation/trim and rotor/propeller interactions separately, with suitable reference experiments. Current submerged hull and prescribed-paddle demos do not implement the complete applications. |

## Adding an item

Use the next unused ID. Include type/status, date, owner or “unassigned,” affected
version/scope, repro or hypothesis, evidence link, and the smallest next action
with a completion criterion. The seed entries above are dated November 9, 2026
and unassigned. Being listed is not authorization to expand a release scope.
