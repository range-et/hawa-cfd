# Per-issue execution plan

**Execution plan — November 9, 2026.** The initial proposal is retained below;
the current execution update records work now started. Ownership/status remains in
[issues](../issues.md). All 46 active IDs are routed below; HAWA-047 is closed in feature history. The mapping is based
on repository source and evidence, with the subsequent startup audit noted above. New
reproductions can change a row’s surface. Broad research items have provisional
surfaces because their designs do not yet exist.

## Current execution update

The [proper PR review](review-cuda-pr2.md) now records fresh local tests, concrete
original merge blockers HAWA-044/045/046 and 17 function-coverage gaps.
The [repair follow-up](review-cuda-blocker-fixes.md) resolves these locally;
[exact Windows candidate acceptance](windows-cuda-merge-checks.md) remains required. The corrected candidate is local commit `46fe0a6` on
`codex/cuda-review-integration` in the separate checkout. No remote PR merge or push.
The first feature increment is [atomic raw-result export](review-export-atomicity.md)
under HAWA-033 (HAWA-047 repaired); the broad export and baking features remain open.
Docker Desktop subsequently became available; all three Python packages ran
constrained Linux CPU checks. See the current [sandbox record](python-sandbox-launch-plan.md#published-batch-and-review-follow-up).
Rhino MCP initially reported no running slots. A separate empty session subsequently
confirmed default block creation on panel open ([audit](review-native-intake.md));
no simulation or plugin installation occurred, and the session was quit normally.

## Python-first parallel launch — current priority

The user has superseded the earlier host-first order. Three isolated agent studies
have completed studies and implementations from checkpoint `a26924c`.
PRs #3/#4/#5 merged into the shared study base after review fixes and
combined-source verification. The narrow PR #2 MPS assertion fix merged into
remote main; broader CUDA acceptance-runner repairs remain separate.
HAWA-021/022 numerical qualification remains open. Follow the [sandbox launch plan](python-sandbox-launch-plan.md)
for file ownership, budgets, individual PR boundaries and serialized verification.
C# implementation and Rhino work wait until the Python batch; existing headless
state-contract checks still apply. No production coding or remote PR was launched
in the study phase. The list now has 40 active items because two distinct Python
bugs were reproduced, not because existing issues were split arbitrarily.

## Next ten Python issues — proposed scope for review

November 9, 2026. Coordinator: Codex primary agent. This is a scoped proposal,
not a new implementation launch or a claim that ten broad issues can close in
CPU containers. The previous C#/Rhino deferral remains in force. Priority weighs
incorrect results and unsafe inputs first, then usable output and confidence in
changes. Run order also accounts for dependencies and exclusive file ownership.

### Gate zero: one integrated base before parallel edits

Verified remote heads: `main` at `65e220e` (PR #2) and the study base at `d9cc3a7`
(PRs #3/#4/#5). Prepare a separate integration checkout; preserve the dirty main
working tree. Combine those histories and the still-separate HAWA-044/045 CUDA
runner repairs from candidate `46fe0a6`, reviewing only the missing changes.
Do not replay the already-merged MPS assertion or replace newer code with the old
candidate. Carry forward current issue/feature records deliberately. Regenerate
coverage from the combined source; rerun focused checks, the full measured gate,
applicable G6 and build/package checks. Open one ready-for-review integration PR
to `main`. This prerequisite is not one of the ten issue deliverables.

Windows acceptance remains pending until that exact final source is run on the
Windows CUDA machine; this does not prevent clearly CPU/MPS-scoped Python work.
After the integration PR merges, pin the ten branches to its actual commit.
If it remains open, subsequent PRs may explicitly stack on it, but must not
silently target an obsolete checkpoint. Reconcile HAWA-046/048/049/050/051 by
actual scope and remaining integration/hardware evidence, not by PR count alone.

### Ranked issue contracts

| Priority | Issue / why now | First PR-sized deliverable and likely ownership | Acceptance / stopping boundary |
| --- | --- | --- | --- |
| 1 | **HAWA-001: CPU/MPS PorousMedium disagreement** — backend choice changes results | Reproduce after integration; separate collision precision, forcing and boundary effects with matching initial tensors and staged observables. Own scoped collision code/tests; vendor edits only after upstream comparison. Fix only a demonstrated cause. | Original 50-step population/velocity/pressure criteria, conservation and unaffected CPU controls; actual MPS required. CUDA is separately unverified. If the cause remains unknown, publish a diagnostic-test/evidence PR and keep the defect open. |
| 2 | **HAWA-021: parent-to-child transfer error** — use the replay harness to resolve the existing failure | Freeze a qualifying parent, isolate 1:1 mapping/time/interpolation/stress transfer before 2:1 discretization; own boundary_series and dedicated transfer experiments. Preserve source hashes and equal physical time. | Mean <=5%, RMS <=10%, Cp RMSE <=0.1, reference stationarity <=5%, unchanged health checks. A diagnostic-only or partial-ratio run cannot establish full qualification. No turbulence closure claim from a short smoke. |
| 3 | **HAWA-022: open-face/ground-edge stability** — prevent late failures missed by short tests | Same numerical owner as 021; isolate an actually failing face/edge topology, compare controlled inflow and ground cases, and fix boundary composition only if reproduced. Own neutral_external/neutral boundary implementation after 021 handoff. | Preserve repaired stress reconstruction; check mass budget, finite/positive states, original quality guards and the failure-producing duration. Recheck affected transfer metrics; no viscosity increase or shortened acceptance window. Broader turbulence qualification may stay open. |
| 4 | **HAWA-004: open-boundary accuracy** — finite flow can still contain reflected disturbances | Bounded outgoing-pulse/vortex and enlarged-domain comparison with matching interior samples; then a boundary repair if supported by the measurements. Own boundary benchmark fixtures first, production boundary files only after 021/022. | Declare observable, reference domain, tolerances and grid/time sensitivity before runs; retain reversal/edge/corner cases. Scope qualification to tested topologies; no universal nonreflecting-boundary claim. |
| 5 | **HAWA-028: domain relationship validation** — reject unsupported coupling before computation | Test containment, disjoint, touching, duplicate, rotated, translated and partial overlap for independent cases, coupled refinement and view composition separately. Own refinement preflight/tests; collection/transfer production edits require handoff. | Valid controls stay valid; unsupported coupling fails before Session/job creation with offending inputs identified. Preserve HAWA-049. If current rules are correct, ship contract tests and a documented policy, not invented rejection. Host preflight remains open. |
| 6 | **HAWA-035: compatible solver choices** — avoid silent unsupported configurations | Audit existing check_case, boundary_contracts and G6 oracle; add missing rejection/diagnostic behavior and a machine-readable supported-choice contract only where needed. Own these validators; no panel changes. | Independent expected combinations; invalid requests fail before allocation; legacy inputs retain meaning; no silent fallback or unsupported fast/accurate labels. G6 required for changed support contracts; UI filtering remains deferred. |
| 7 | **HAWA-038: trustworthy probes and load coefficients** — measurements must have defined meaning | Audit existing sampling, optimization/motion loads and polar/LLT paths. Deliver one Python measurement contract for axes/signs, pressure reference, density/speed/area, averaging and result identity; fix or extend missing calculation paths only. | Analytic/manufactured sign, units, translation/rotation and reference-quantity cases; reject invalid references and stale identity. Keep supplied polars distinct from CFD forces. Engineering validation stays HAWA-005; plotting/host UI is deferred. |
| 8 | **HAWA-033: usable numerical export** — make verified results inspectable outside Rhino | Bounded CSV export of explicit probes/selected samples using the 038 identity/units contract. Prefer a dedicated writer module; any fields/plugin dispatch changes owned exclusively. Retain NPZ behavior. | Document columns, units, coordinates, validity, time and reference metadata; round-trip precision, atomic publication, cancellation, long filenames and partial-write tests. Avoid full-grid materialization by default; no bake/UI/new public node. |
| 9 | **HAWA-007: useful vector slices** — improve the existing result workflow | Pure Python sampling contract for full 3D versus in-plane vectors, density/scale, solid/invalid masking and fixed scalar ranges, using immutable snapshots. Reuse existing operations before adding any. Own fields/field_collection only after export handoff. | Manufactured directional/rotated-plane and mask cases, stable output budget, unchanged source snapshot and solver iteration. This completes a Python increment only; movable native/GH controls need the later host phase. |
| 10 | **HAWA-026: measured coverage with meaningful assertions** — make regressions harder to miss | First independent tranche: audit/test airfoils.dispatch_airfoil, listed uncovered in the final PR #5 matrix, covering existing operation routing and invalid inputs with numerical/data assertions. Recheck the integrated matrix before choosing final gaps. Own airfoils tests; do not refactor merely to raise a number. | Tests detect seeded wrong-routing/units failures and execute the claimed functions; promote only measured covered baseline entries. This retires a named tranche, not all Python/C# coverage debt. New-code coverage remains mandatory for every other PR. |

The numerical entries deliberately distinguish an implemented repair, a verified
contract, and an unresolved experiment. Ten issue IDs are not a promise of ten
closed issues or ten arbitrary production patches. Each gets a separate scoped
PR when there is a reviewable contribution; an unreproduced hypothesis gets an
evidence/test outcome rather than a fabricated fix. Split further only when
independent changes genuinely require it.

### Three-agent execution sequence

Use three separate clones/branches and environments, with the coordinator owning
integration and records. Suggested branch names are `codex/issue-001-parity`,
`codex/issue-028-domains`, etc. Do not start ten concurrent agents.

| Stage | Agent A: result/data work | Agent B: contracts | Agent C: numerical work |
| --- | --- | --- | --- |
| First launch | 026: airfoil dispatch coverage | 028: domain relationships | 001: parity reproduction and cause isolation |
| Following handoff | 038: measurement contract | 035: capability validation, after 028 | 021: controlled transfer, after parity baseline |
| Next | 033: bounded CSV, after 038 | 007: design/tests read-only while export owns fields; implementation after 033 | 022: stability isolation after 021, or earlier if 021 localizes that cause |
| Final numerical tranche | Review/combined verification | Review/combined verification | 004: boundary accuracy after boundary ownership is released |

Only one worker edits a production file at a time. The shared plugin dispatcher
and field modules require explicit coordinator handoff; reviewers can inspect
read-only. A proved numerical dependency may change the order, with evidence
recorded before reassignment. Research ideas, general refinement expansion,
thermal/free-surface/second-solver work and new public nodes are excluded.
HAWA-003/011 are affected umbrella qualification work, not extra concurrent owners.
HAWA-027/029 remain important but need the deferred C#/Rhino lane; they are not
being downgraded because CPU work is easier.

### Sandbox, evidence and PR finish line

- Reuse the verified Python 3.9 / torch 2.8.0 / NumPy 2.0.2 Docker CPU image by
  immutable ID from the [launch record](python-sandbox-launch-plan.md); 1 CPU /
  2 GiB, no network or Docker socket, read-only source/root and dedicated output.
  Reassess memory before a larger numerical case rather than pretending it fits.
- Each native environment imports its own checkout. Give each run a unique
  output directory and sandbox-specific TMPDIR; the previous shared pytest tmp
  retention cleanup demonstrated why this matters.
- Parallelize small CPU tests. Serialize native full gates, MPS studies and long
  simulations; CUDA runs use the Windows queue. The Docker image has no .NET;
  native function gates provide state-contract evidence. Record actual devices.
- First collect the reproducer/control and acceptance criteria, then implement,
  test the failure paths, run relevant tests and the complete function gate,
  regenerate matrices against the actual PR base, and run applicable G3/G6 and
  build/package checks. Changed schemas/capabilities need compatibility evidence.
- Publish **ready-for-review PRs, never drafts**, one bounded issue increment per
  PR. Explain unresolved scope and link evidence. Address review findings and
  check the pushed head's CI before proceeding; a green bot status alone is not
  proof that its comments were fixed.
- Integrate serially. Refresh shared matrices from the actual combined source;
  do not resolve generated evidence conflicts by choosing one branch's matrix.
  Close only the verified issue scope and move its outcome to features history.

The user authorized integration followed by agents 026/028/001. The integration
candidate is now locally verified ([review](review-python-integration.md)); issue
workers start from its committed head after its PR is opened. Later stages remain
queued. Prior test counts remain historical evidence for their original source.

## Earlier resumed issue order — superseded by Python-first launch

The CUDA candidate waits for Windows acceptance; it does not block these tasks.
Work proceeds one bounded change at a time. The active entries remain open
until their own completion criteria are satisfied.

| Order | Issue | Next concrete deliverable | Verification surface |
| --- | --- | --- | --- |
| Started | 034 | Parent/child guide and role map delivered; remaining canvas presentation scoped in the [review](review-parent-child-guide.md) | Documentation links and unchanged archive hashes now; Rhino for canvas edits |
| Next implementation | 029 | Make the demonstration block explicitly opt-in; preserve saved/legacy setup and bindings | Headless state regressions, build, then clean/saved/reopened Rhino documents |
| Next host diagnosis | 027 / 030 | Capture the exact trimming symptom and audit native/GH view availability | One isolated Rhino session; derive array/geometry fixtures only after reproduction |
| Next result feature | 032 / 033 | Agree a bounded shared artifact contract, then add the selected export/baking workflow | Python for export; Rhino for document writes and UX; atomic NPZ repair already complete |
| Separate numerical batch | 021 / 022 | Establish stationary reference, then same-grid and refined transfer comparisons | Ordered CPU/MPS experiments with unchanged thresholds |

HAWA-026 coverage checks accompany each code change. HAWA-028 overlap rules and
HAWA-035 capability wording should be audited alongside affected features.
Broader physics/engine ideas keep their scoped research status; they are not
implied implementation commitments for this first batch.

## Existing Windows CUDA PR

*Initial planning snapshot; see the current execution update above.*

[PR #2 — Codex/windows cuda](https://github.com/range-et/hawa-cfd/pull/2)
was inspected November 9, 2026 at head
`864a2652eed371ab8c16e65d9ab1228d09a00e79`, base `d3a5793`.
It is open, not a draft; GitHub reports mergeable against remote main, with no
submitted reviews or attached status checks at inspection. That mergeability
result does not assess this local checkout at `0822db9`: its three newer commits
add roadmap records, atmospheric transfer/shared views and the function gate.
At that initial planning stage, no PR checkout, merge, tests or independent
numerical reproduction had been performed. The current execution update and
linked review supersede that limitation.

Read the [repair follow-up](https://github.com/range-et/hawa-cfd/blob/864a2652eed371ab8c16e65d9ab1228d09a00e79/docs/verification-windows-cuda-fixes-2026-11-09.md)
after the initial failure report. It records Windows 11, RTX 5070 Ti,
Python 3.9.25, PyTorch 2.8.0+cu128 and NumPy 2.0.2:

- Three Hawa runs at 204 passed / 77 skipped each, with 78 named CUDA cases and
  zero CUDA skips; bounded 16/16 examples and 13/13 supplemental configurations.
- Ordered/rationalized moving-body geometry fixes sphere-mask and torque parity.
- KBC uses FP64 collision intermediates on CPU/CUDA with FP32 storage. MPS keeps
  FP32, so HAWA-001 remains open. Reported cost for the bounded PorousMedium case:
  1.77× CPU time, 1.21× CUDA time and roughly twice CUDA tensor allocation.
- State-contract/build/package results are reported, but live Rhino/GH, clean
  embedded CUDA installation, MPS and long-duration engineering validation are
  excluded. The plain bootstrap torch pin remains an installation follow-up.

These are PR-author records, not fresh passes on the integrated source. The PR
adds reusable `verify_cuda.py`, benchmark tooling, explicit CUDA test fixtures,
portable upstream handling and Windows path fixes. Reuse/review that work; do not
commission a second CUDA harness or repeat the already repaired CPU/CUDA diagnosis
from scratch. The current function gate, committed coverage matrix and expanded
G6 inventory still need evidence after integration; the older suite count cannot
stand in for them. Review CPU/MPS behavior and performance before adopting the
precision tradeoff. Keep generated native CUDA extensions outside the portable
PyTorch claim.

**Plan change:** replace the proposed HAWA-001 fresh CPU investigation with a
PR #2 review/integration work item, followed by current-source CPU/CUDA regression
and native Mac CPU/MPS comparison. HAWA-002 now has pending integration evidence
for headless CUDA, alongside separate Windows host/installation gaps. HAWA-006
owns the clean embedded CUDA wheel-selection follow-up. Integration must preserve
this checkout’s newer work and local documentation edits.

## What an issue surface means

Record separately: code/data touched, where a minimal reproduction can run,
where a fix can be tested, hardware/host needed for completion, and conflicting
work. A Python implementation can need MPS evidence; a C# method can be tested
without Rhino. “Can produce a PR in a sandbox” is a weaker claim than “can close
this entire issue in the sandbox.” Split mixed issues into scoped PRs under the
existing ID rather than assigning the whole issue to a supposedly independent
worker. Keep unresolved host/device scope open after a partial PR merges.

| Lane | Environment and eligible work | Boundary |
| --- | --- | --- |
| P: headless Python | Isolated checkout + Python 3.9 environment; CPU solver, service, array geometry, serialization and numerical fixtures | No Rhino imports in `src/hawa`; no CAD capture, viewport or GH scheduling evidence |
| C: headless C# | .NET 10 StateContracts, linked production logic with host/transport doubles | Current links cover CaseHub, CaseState, NativeSettings and SliceCutCells. Other C# files are not automatically headless; plugin target remains .NET 7 |
| D: device runs | Native macOS environment for MPS; actual CUDA-capable runner for CUDA | Same source/fixtures and fixed tolerances; CPU pass cannot replace device evidence |
| H: host verification | One owner of the available Rhino 8/GH session, through Rhino MCP | CAD/document mutation, Eto panel, viewport, binding callbacks, archives and embedded Python lifecycle |
| R: research/docs | Isolated checkout, reference/data/license review, specifications and site content | Research is not an implemented feature; tutorial claims still need actual host evidence |

The current full function gate runs **both Python and headless .NET**, even for a
Python-only change. A practical worker image therefore includes .NET 10 as well
as Python, or delegates the full gate to a matching integration runner before
review. See [function policy](function-testing.md) and the existing
[Ubuntu CPU workflow](../.github/workflows/function-tests.yml).

## Source and verification map

These are starting points for investigation, not confirmed defect locations.

| Surface | Production entry points | Existing evidence/test entry points |
| --- | --- | --- |
| Numerical core and devices | `src/hawa/{lbm,collision,engine,backends,neutral,neutral_external,boundaries,roughness,refinement}.py`; `vendor/lettuce` | `tests/test_{lbm,engine,neutral,neutral_external,general_boundaries,refinement}.py`; `scripts/compare_engines.py`, `compare_examples.py`, `verify_neutral_nesting.py`, `verify_atmospheric_reference.py` |
| Data, fields and service | `src/hawa/{plugin,jobs,fields,field_collection,recording,boundary_series,boundary_data,flow_statistics,motion,optimization}.py` | Corresponding `tests/test_*.py`; `tests/matrix`; field export already exists in `plugin.py` and must be audited before adding another |
| Shared state and display | `plugin/Hawa.Shared/{CaseHub,CaseState,NativeSettings,SliceCutCells,SliceDisplay,CaseGeometry,SurfaceMeshing,WallLinks}.cs` | [StateContracts links](../tests/dotnet/StateContracts/StateContracts.csproj); geometry/display beyond those links needs actual Rhino or deliberate extraction |
| Host adapters | `plugin/Hawa.Rhino/{HawaPanel,NativeGeometry,NativePreview}.cs`; `plugin/Hawa.Grasshopper/*Components.cs`, `LinkedCaseComponent.cs`, `PollScheduler.cs` | `scripts/verify_native_slice_display.cs`, `verify_collection_views.cs`, `verify_state_hardening.cs`, `verify_binding_callbacks.cs`, scoped geometry/archive harnesses |
| Tooling/distribution/docs | `plugin/Bootstrap.py`, `scripts/build_plugin.py`, `tools/function_coverage.py`, `site`, `scripts/build_site.py` | `tests/test_function_coverage.py`; `.github/workflows/function-tests.yml`, `pages.yml`; clean install and package checks |

All host recipes must follow the [MCP guide](agents/rhino-mcp.md),
[example matrix](../examples/grasshopper/VERIFICATION.md) and
[quality gates](quality-gates.md). A harness name here is not a fresh pass.

## Issue surface matrix

“Independent” below means isolated source/output ownership and a declared CPU,
RAM and time budget. It does not mean unlimited workers on one machine.

| Issue | Isolated first deliverable / lane | Completion outside the sandbox | Dependency / scheduling decision |
| --- | --- | --- | --- |
| HAWA-001 | P: review PR #2 KBC precision repair against current source and reproduce CPU regressions; do not duplicate its repaired diagnosis | D: native CPU/MPS comparison at original tolerances; current-source CUDA regression | PR integration first; inspect numerical/resource tradeoff. Reserve collision code against neutral-flow edits; CPU-only closure remains impossible |
| HAWA-002 | P/R: review existing PR #2 CUDA tooling/evidence and integrate with current function/G6 gates | D: fresh CUDA run on integrated source; H: Windows native UI + clean installs | Reuse existing headless work; separate recorded PR passes from pending integration, wider CUDA coverage and host qualification |
| HAWA-003 | P: bounded physical-viscosity/scaling experiment in neutral/collision paths | D: CPU/MPS qualification; H if exposed contracts/adapters change | Same numerical owner/batch as 011/021/022; avoid parallel competing solver edits |
| HAWA-004 | P: enlarged-domain reflection/reversal fixtures and error measurements | D for declared backends; H for changed boundary-node contracts | Coordinate boundary ownership with 021/022. Analytic tests parallelize; production boundary patches serialize |
| HAWA-005 | R/P: choose one load regime/reference and build headless sensitivity study using load/motion/airfoil paths | D for device claims; H for the promised wing/hull workflow | Depends on a scoped observable and reliable load extraction; coordinate 038. Not a quick verification |
| HAWA-006 | P/C: bootstrap/build error-path tests and installation design | H: clean macOS/Windows first use, update and recovery | Coordinate 002; sandbox install alone cannot qualify embedded Rhino dependencies |
| HAWA-007 | P: vector sampling/projection/masking tests; C where view calculations can be isolated | H: movable slice controls, viewport style and no solver restart | Shares fields/views with 027/031/036; agree data contract before parallel adapter edits |
| HAWA-008 | R: select and annotate ordinary-GH example recipes | H: create/open/run/save definitions and verify wires/output | Follows relevant supported features; keep 09 untouched. Vortex suggestion first needs a defined phenomenon |
| HAWA-009 | P: refinement topology/conservation prototype and uniform-fine comparison | D + H: backend qualification, region inputs and lifecycle | Define overlap policy with 028 first; major numerical scope, not first batch |
| HAWA-010 | R/P: common case/capability contract and one two-method experiment | External engine environment, then C/H adapter and case-switch lifecycle | Depends on 013 feasibility; do not assign a broad “second solver” implementation yet |
| HAWA-011 | P/R: maintain atmospheric delivery checklist and explicit failing numerical gates | D/H: full declared atmospheric workflow | Umbrella for 003/004/021/022; no separate worker editing the same solver for this ID |
| HAWA-012 | R/P: one particle-method feasibility experiment with end-to-end cost | D for GPU timing; H only after product integration is chosen | Deferred research; independent prototype can use a separate directory after scope approval |
| HAWA-013 | R: assess existing engines, distribution and a bounded adapter experiment | Chosen external runtime; later C/H integration | Research before 010 implementation. FluidDyn suggestion remains unassessed |
| HAWA-014 | P/D: profile representative complete workflows; compare one small native candidate only if warranted | Target-device/package checks; H if the bottleneck is host-side | Depends on measured bottleneck. No Rust rewrite or performance promise |
| HAWA-015 | R: separate free-surface, flotation and propulsion requirements | Future numerical/device validation and H applications | Deferred; existing submerged/prescribed-motion demos cannot close it |
| HAWA-021 | P: controlled same-grid transfer, stationary reference and then refined transfer tests; boundary_series/statistics/neutral paths | D: CPU/MPS long-window comparisons; H: affected transfer/GH/archive regression | First numerical workstream; ordered experiments, not concurrent fixes to all three causes |
| HAWA-022 | P: isolate boundary stability from remaining statistics/turbulence qualification | D + affected H regression | Same owner as 021; retain repaired stress reconstruction evidence. Do not reimplement repaired boundaries from older reports |
| HAWA-026 | P: one module’s uncovered functions with meaningful assertions; C: one linked state/geometry contract tranche | H/instrumented evidence for remaining host-only methods | Best small sandbox pilot. Split by disjoint files, preserve base-commit ratchet; whole issue remains open |
| HAWA-027 | H first: capture exact build/file/view and outer-domain versus obstacle gap. Then P field/mask fixture and C SliceCutCells area regression where applicable | H: native/legacy/snapshot viewport reproducer plus affected examples | First host slot. Once captured, delegate minimal numeric/geometry fixture; do not guess the defect is Python-only |
| HAWA-028 | P/R: define supported containment/overlap cases; test case/boundary/refinement and collection contracts. C preflight where isolated | H: accepted inputs versus actionable rejection before jobs start | First scope audit; supported view overlap differs from solver coupling. Coordinate 009/034, not blanket overlap rejection |
| HAWA-029 | C: default/restored state tests in settings/hub where applicable; inspect panel startup | H: fresh document, saved case, reopen, undo and existing binding | Small host candidate after reproduction; shared panel/state files conflict with 030/032/035 |
| HAWA-030 | R/C: map panel, shared case and available GH views; propose explicit handoff contract | H: observe current availability and any new binding/graph handoff | Audit early; implementation decision later. No assumption of hidden generated graph |
| HAWA-031 | P/C: cell-versus-site geometry contract, bounded section coordinates and output budgets | H: grid preview and baking in Rhino/GH | Learn from 027 first; align identity/metadata with 032/033; avoid whole-grid allocation by default |
| HAWA-032 | P: snapshot metadata schema; C: isolated naming/identity logic if extracted | H: layer/object writes, persistence, save/reopen and subsequent run isolation | Requires shared artifact contract with 033; single document-write owner |
| HAWA-033 | P: audit existing export; define raw-data schema and round-trip/corruption tests, then writer if needed | H: existing/new export UI, completed-result attribution and cancellation | Strong sandbox implementation candidate after small contract review; coordinate 032. Core-only PR can merge with host follow-up open |
| HAWA-034 | R: generic parent/child terminology and precise transfer/refinement distinctions | H only for modified GH panels/archives and observed tutorial steps | Independent docs draft; no solver dependency for wording. Do not regenerate archives outside host lane |
| HAWA-035 | P: independent capability/invalid-combination tests; R: explanatory copy | C/H: actual option filtering, preserved archives and tooltips | Reuse G6 oracle; serialize HawaPanel edits with 029/030. Benchmark any speed comparison separately |
| HAWA-036 | C/R: boundary glyph/label contract and testable direction transforms | H: display conduit/viewport, legibility and no physics restart | Shares display files with 007/031; integrate after coordinate/normal conventions agreed |
| HAWA-037 | R/C: inventory safe staged harnesses and design orchestration/evidence format | H: repeated sequential runs, failure recovery and cleanup in one session | Start as a small runner pilot around existing harnesses; not a prerequisite to capturing 027 now |
| HAWA-038 | P: audit existing probes/loads/LLT, coefficient/sign formulas and sweep provenance tests | H: sensors/plots/workflow; D/reference studies under 005 | Establish observable contract before UI. Keep physical validation separate from formula checks |
| HAWA-039 | R: extend existing site/docs structure, versioning and navigation; link/build checks | H only to substantiate new tutorial instructions/screenshots; deployment separately reviewed | Independent documentation candidate. `site/` and Pages workflow already exist; no new hosting stack assumed |
| HAWA-040 | P/R: multipart voxel/SDF union experiment using synthetic geometry | C/H: Brep/mesh capture, CAD tolerances and user geometry preservation | Audit current multi-body classification first; coordinate geometry files with 027/031. GPU feasibility not established |
| HAWA-041 | P/R: distinguish existing multi-face inflow from masked volume forcing; conservation prototype | D and C/H boundaries/force UI if pursued | Depends on physics contract; boundary changes conflict with 004/021/022 |
| HAWA-042 | P/R: narrowly scoped thermal transport/energy balance experiment | D + C/H capability/thermal settings integration | Deferred physics extension; no temperature flag in current isothermal model |
| HAWA-043 | P/C: audit tooling and pilot property/mutation testing on a bounded module | CI runtime and dependency review; H requirements remain unchanged | Coordinate 026 and shared coverage tools. Container foundation is infrastructure, not completion of this five-layer idea |
| HAWA-044 | P: fix CUDA runner inventory/selection checks with adversarial subprocess/JUnit tests | D: repeat full CUDA execution after repair | Local repair measured; Windows acceptance then integration; shared owner with 045 |
| HAWA-045 | P: enforce unchanged complete source/config provenance across stages | D: fresh CUDA suite/benchmarks on final revision | Local repair measured; immutable Windows evidence required; coordinate 044 |
| HAWA-046 | P/D: carry local actual-device comparison fix into candidate tests | D: verify MPS and declared CUDA cases | Fresh 700-pass suite and function gate pass; Windows/integration pending |
| HAWA-048 | P: atomic immutable-frame save regression and repair | Host export UX remains separate | First sandbox repair; owns fields.py, no overlap with session-export changes |
| HAWA-049 | P: translation-independent refinement preflight | D/G6 after core repair; host input UX later | Second sandbox repair; owns refinement.py, no blanket view-overlap rejection |

| HAWA-050 | CI: pinned Python 3.9 runner and dependency provisioning repair | Hosted checks on actual PR heads; main integration | Implemented on shared study base; initial three PR gates passed |

| HAWA-051 | P: bounded temporary prefixes in both NPZ writers, long-name regressions | Normal local filesystem checks; Windows unverified | Review repair in PR #3; no host UI change |
| HAWA-052 | P: reject unsupported refinement topology before solver allocation with domain diagnostics | Full native gate + Linux CPU G6; host/pre-Job scope stays under 028 | Shared refinement validator and relationship controls; [review](review-domain-relationships.md); no blanket overlap ban |

| HAWA-053 | P: restore imported wall filter on reset | CPU repeated-reset replay; host/device scope separate | Integration PR #6 review repair |
| HAWA-054 | P: budget exterior projection/workspace before allocation | Large-case rejection sentinel; valid small controls/G6 | Integration PR #6 review repair; conservative estimate |
| HAWA-055 | P: complete corresponding source verification inputs | Package fixture and actual packaged test collection | Integration PR #6 review repair |

## Proposed sandbox and PR contract

Use the existing Ubuntu CPU workflow as the starting specification for a
reproducible worker image: Python **3.9**, PyTorch **2.8.0**, NumPy **2.0.2**,
vendored `hawa-lettuce`, repository test extras and .NET **10**. Pin the selected
image/tool versions and record OS/architecture; prove dependency installation
and the actual tests before calling this environment supported. Do not upgrade
production dependencies to make the image easier to build. There is no checked-in
Docker recipe identified in this audit and no container was built here.

Use a Linux CPU container for lane P/C. Keep MPS as a separate native macOS job:
PyTorch documents MPS as the macOS Metal backend, and Docker Desktop documents
its `--gpus` passthrough for Windows/WSL2, not a macOS MPS worker. This plan does
not treat container CPU results as Mac GPU evidence. Sources checked November 9,
2026: [PyTorch MPS](https://docs.pytorch.org/docs/stable/notes/mps.html),
[Docker GPU support](https://docs.docker.com/desktop/features/gpu).
These platform references do not change Hawa’s pinned PyTorch version.

For the first pilot, an isolated checkout with its own `.venv` is also enough
to debug CPU logic; it is dependency/workspace isolation, not a security boundary.
The reusable container is preferable for repeatable workers once its smoke test
passes. Each worker receives:

1. An immutable base revision, one issue/subscope, allowed files, regression or
   investigation question, acceptance criteria and explicit out-of-scope work.
   Current local documentation edits must be preserved and incorporated into an
   agreed checkpoint before dispatch; do not fork from an unspecified dirty tree.
2. Its own worktree/checkout, `codex/hawa-NNN-description` branch, writable result
   directory and environment. No shared production checkout or installed-plugin
   writes, Rhino connection, Docker socket, personal home mount or publishing
   credentials inside the execution container. Bound CPU/RAM/time and PyTorch
   thread counts so independent tests do not exhaust one host.
3. A failing regression first for reproduced bugs, or a measured experiment for
   hypotheses; focused tests, then the full suite/function gate and refreshed
   committed matrix. Use the PR base baseline. Add applicable G3/G6 evidence;
   record every device skip instead of interpreting it as a pass.
4. A draft PR or ready-to-publish patch with problem, change, exact commands,
   source/environment hashes, retained criteria and unresolved device/host gates.
   Publishing uses an authorized repository integration outside the sandbox;
   sandbox code does not need GitHub credentials. No automatic merge/issue closure.
5. Integration review for overlapping edits and rerun of affected checks on the
   combined revision. Generated function matrices/baselines are a common conflict:
   regenerate from integrated source, never concatenate or hand-wave conflicts.
   Each individual PR still carries its required fresh matrix.

A pure core PR can be merge-ready without Rhino **only when its declared scope
and affected contracts need no host evidence**. If the claim is a repaired
viewport, callback, archive or installed workflow, keep that claim pending until
H verification. Native/GH adapter changes require the plugin build plus relevant
live checks. Tests with doubles cannot waive those gates.

## Proposed sequence for review

### 1. Establish the dispatch boundary

Preserve current edits and agree the base revision. Review PR #2 against this
checkout’s newer source; decide the integration candidate before collecting
authoritative CUDA/MPS evidence. Build/smoke-test the CPU +
.NET environment against the current workflow, record skips and confirm evidence
output. This is a bounded infrastructure PR; it does not introduce the whole
HAWA-043 toolchain. If the base fails, report and isolate the failure before using
it to judge workers. No blanket promise that all Python issues fit the image.

### 2. Pilot two independent headless tasks and one host audit

- **Worker A — HAWA-026:** pick one uncovered, headless, low-overlap module after
  reading the committed matrix; deliver asserting tests and measured improvement.
- **Worker B — PR #2 / HAWA-001/002:** review the CUDA tooling and numerical
  changes, reconcile them with newer local source in an isolated candidate, and
  run the current CPU/function gates. Queue current-source CUDA and MPS checks
  afterward; reserve collision/moving-boundary files. No duplicate CUDA harness
  or fresh diagnosis of the already repaired CPU/CUDA failure.
- **Host owner — HAWA-027, then 029 and 030 audits:** capture builds, small
  reproducible files and observations. No concurrent agent controls the session.
  Hand extracted array/polygon fixtures to a later isolated worker. Classify 028’s
  overlap rules alongside this audit before calling missing validation a defect.

Limit the first pilot to those two CPU tasks; throttle or queue heavy benchmarks.
Review pilot quality, memory/time cost and integration friction before expanding.
Do not start a second neutral/collision editing worker alongside Worker B.

### 3. Deliver the first user-visible slice

Choose the reproduced trimming/default fixes based on stage 2. Pair an isolated
regression/fix with one scheduled host acceptance run. Next, agree the shared
result schema for **032/033**, implement export core in the sandbox, and schedule
baking/export UI as a single coordinated host change. **034/039** can proceed as
independent documentation work, drawing only on verified capabilities.

Pilot **037** with two existing staged harnesses and failure cleanup while doing
this host work. A giant all-examples runner is not needed before useful fixes.

### 4. Run a coordinated numerical workstream

For **021/022**, use one production-code owner and ordered experiments: stable
reference/statistics → controlled same-grid transfer → refined transfer. Related
003/004/011 remain linked, not competing patch assignments. Independent reference
analysis can parallelize, but long CPU/MPS jobs require budgets and the device
queue. Keep the original tolerances. Qualification might remain open even after
an informative diagnostic PR.

Choose **038/005** as the next application workstream if loads are the product
priority. Keep 009/010/012–015/040–042 as separately reviewed research scopes;
they should not consume the initial bug-fix pilot by default.

## Serial host and device queue

One owner controls the available Rhino session at a time. Agents may independently
prepare code/tests/specifications, but cannot mutate that session concurrently.
Queue entries carry issue, candidate source/build hash, named fixture, public
steps, expected outputs, cleanup checks and required device. Use disposable
copies and preserve user documents/example 09. No replacement of a loaded
assembly; batch candidate checks per build and use normal saved Quit for updates.

Host ownership and device ownership are separate resources. A standalone MPS job
needs no Rhino, but it can compete with Rhino on the same Mac GPU/memory. Initially
allow one heavy device job at a time across both lanes. CPU container workers must
leave headroom for the host. Pause/cancel cooperatively; collect fresh evidence and
release owned jobs/documents before advancing the queue.

Future independent Rhino machines could each have a queue; this proposal assumes
one available session and does not rely on extra licenses, hosts or slots.

## Review decisions

Recommended scope to approve first: **environment pilot + 026 tranche + PR #2 review/integration
for 001/002 + serial 027/029/030 audit**. Approve the result-schema and numerical
workstreams separately after those findings. The plan deliberately makes no
calendar estimate until environment setup and first reproductions establish cost.

Acceptance of the pilot means reproducible isolated evidence, preserved host
state, reviewable PRs and an honest list of remaining gates—not that all 35 issues
are fixed or that a passing suite establishes engineering accuracy.
