# Python-first parallel debugging launch

November 9, 2026. Coordinator: Codex primary agent. This supersedes the host-first
order in the earlier execution plan. C# implementation, Rhino/GH operation,
canvas changes and plugin installation are deferred. Existing headless .NET
contract tests still belong to the required code-verification gate.

## Checkpoint and isolation actually prepared

All three agents start at local checkpoint
`a26924caa9ef5da070c0a82f2f8a8bf3ddf5782d`, ref
`codex/python-study-base-20261109`, whose parent is `0822db9`.
A temporary Git index captured the current tracked/untracked work, including the
atomic session-export repair and issue records. The main checkout's HEAD, index
and working files were not replaced. This checkpoint is not a claim that all
captured work is merged or released.

The separate CUDA candidate `46fe0a6` is excluded. Collision/vendor CUDA repairs
must not be recreated in these branches. Integrating that candidate later requires
rebasing/reviewing affected branches and testing the combined source.

| Agent | Independent checkout | Branch | Initial study |
| --- | --- | --- | --- |
| `export_study` | `/Users/r2d2/Desktop/hawa-python-sandboxes/export-033` | `codex/python-export-033` | HAWA-033 and immutable-frame save failure handling |
| `domains_study` | `/Users/r2d2/Desktop/hawa-python-sandboxes/domains-028` | `codex/python-domains-028` | HAWA-028 domain contracts and refinement preflight |
| `transfer_study` | `/Users/r2d2/Desktop/hawa-python-sandboxes/transfer-021` | `codex/python-transfer-021` | HAWA-021/022 stationary reference versus transfer error |

These are independent Git clones and Python virtual environments, not linked
working directories sharing an index. Each environment uses Python 3.9.25,
PyTorch 2.8.0, NumPy 2.0.2 and the editable vendored engine from **its own checkout**.
The coordinator checks actual import paths before accepting results.

Docker Desktop is now available. The coordinator built and smoke-tested the
Linux CPU image `hawa-python-study:20261109` (image ID
`sha256:6b367745131c89cf349cd005532efe5ac708f871b1758105669406e468e18e93`).
All three focused suites ran with one CPU / 2 GiB limits, network disabled,
read-only root/source and dedicated writable results/tmp. Python 3.9.25, torch
2.8.0+cpu and NumPy 2.0.2 were verified. The image excludes .NET: complete
function/state-contract gates run natively. Initial and container environment
records remain under the sandbox directory and `results/python-docker-runtime/`.

## Phase 1 — reproduce and establish PR contracts

Already launched: three bounded study agents. They can read production code,
run focused CPU tests, and write diagnostics under their own `results/study/`.
They do not edit shared production files, issue registers or tracked tests during
this initial study. Each reports a passing control and a failing reproduction
when proposing a bug fix. A test passing against existing behavior is not proof
of a suspected defect or of complete issue closure.

The coordinator records confirmed defects under stable IDs and turns each
result into a branch-specific coding assignment. No PR should combine unrelated
repairs merely because they share a Python language/runtime.

## Initial study results — completed

All three agents finished their bounded study with clean tracked checkouts.
These are targeted CPU baselines, not full-suite or GPU qualification.

| Agent | Fresh checks | Finding / first PR |
| --- | --- | --- |
| Export | 10 CPU tests pass | **HAWA-048 confirmed:** immutable-frame save truncates before compression. Injected failure replaces an existing 887-byte NPZ with 7 bytes; a new path also retains 7 partial bytes. First PR: “Preserve immutable field exports on failed writes.” |
| Domains | 28 CPU tests pass; 4 device cases deliberately deselected | **HAWA-049 confirmed:** a one-metre fine-grid offset is rejected near zero but accepted at parent x=1,000,000 m; the malformed case advances. Aligned controls pass at both origins. First PR: “Reject refinement misalignment independently of world origin.” |
| Transfer | 36 CPU tests pass; 4 device cases deliberately deselected | No new solver defect claimed. Existing harness combines settling, transfer and optional resolution comparison; first PR: “Make neutral transfer studies replayable against a frozen reference.” |

[Compact study record](verification-python-launch.json). Raw tests, scripts,
reproduction JSON and detailed agent recommendations are copied under
`results/python-launch-20261109/`. This is historical study evidence; implementation and full gates subsequently
completed as recorded below. The third package is diagnostic tooling, not a
solver repair.

## Phase 2 — independent coding assignments

| Work package | Allowed production ownership | Tests and completion criteria | PR boundary |
| --- | --- | --- | --- |
| A: HAWA-048 immutable-frame export safety, supporting 033 | `src/hawa/fields.py` save path; extract a dedicated writer only if justified | Reproduce old-file truncation or partial-new-file publication; then round-trip and capture/write/flush/replace failure tests. Preserve raw arrays/metadata, clean owned temporaries, and keep prior output intact. | One Python safety repair. No CSV, UI, session-export rewrite or baking. |
| B: HAWA-049 refinement alignment/preflight, supporting 028 | `src/hawa/refinement.py` validation; dedicated preflight tests | Use a valid translated grid as control and an invalid offset case at a large world origin. Accept/reject must reflect physical alignment, not world-coordinate magnitude. Keep supported nesting usable. | One preflight repair if reproduced. No new refinement ratios, view-overlap policy or boundary solver rewrite. |
| C: transfer diagnostic harness, under 021/022 | `scripts/verify_neutral_nesting.py`, new `tests/test_neutral_nesting_verification.py`, dedicated report; solver and recording APIs read-only | Separate parent stationarity, same-grid transfer and resolution changes. Record source hashes, fixture geometry, absolute times, averaging windows, probes and fixed criteria. Missing/partial/stale evidence fails. Preserve mean ≤5%, RMS ≤10%, Cp RMSE ≤0.1 and reference stationarity ≤5%; report child stationarity as an additional diagnostic. | First PR establishes reproducible diagnosis. A later, separately reviewed solver fix must follow a demonstrated cause. A failed study is a valid result. |

Each agent owns a dedicated test/report file as well as its allowed production
surface. No concurrent edits to `plugin.py`, `jobs.py`, `boundary_series.py`,
`neutral*.py`, collision code, `vendor/`, dependency pins or shared gate tooling.
If a required fix crosses that boundary, the coordinator serializes the related
work; an agent must not silently expand its patch.

Agent C can develop its small harness while A/B code. Long simulations wait for
the numerical slot. Agent A's `fields.py` ownership also delays any second worker
adding CSV/view behavior there. HAWA-026 coverage work is attached to the functions
changed by these PRs, rather than a competing broad rewrite.

## Compute and verification queue

Observed host: 48 GiB memory, 16 logical CPUs. Initial policy:

- At most three study/coding agents, one per checkout; set
  `OMP_NUM_THREADS=1` and `MKL_NUM_THREADS=1` for focused CPU commands.
- Initial focused tests/diagnostic probes should fit a five-minute run. Record
  wall time, dimensions, steps and output sizes. This is a scheduling budget,
  not an OS-enforced cap or an accuracy criterion.
- Run at most **one full function gate, MPS job or long numerical study at once**.
  Native full-suite tests can discover and use MPS; they are not automatically
  CPU-only just because the assigned feature is Python.
- Numerical progression: fast manufactured/operator controls → bounded diagnostic
  run → stationary-reference study → same-grid transfer → changed-resolution
  transfer. Estimate memory/time from a pilot before long windows. Never shorten
  the accepted statistical window or widen tolerances to obtain a pass.
- CUDA remains a separate Windows queue. CPU/MPS evidence does not qualify CUDA.

The constrained Docker image above supplies independent Linux CPU checks. MPS
stays on native macOS; CUDA stays on the Windows acceptance queue. Container
results do not establish GPU correctness or native Rhino behavior.

## PR preparation and integration

For each code PR:

1. Commit the failing regression and smallest repair on its own branch; retain
   before/after evidence. Keep exploratory scripts/logs in `results/` and summarize
   only useful conclusions in a dedicated review record.
2. Run focused tests, then queue the complete function gate. Use the actual PR
   base commit's baseline; for this initial branch checkpoint, use `a26924c`.
   Refresh and check the committed function matrix. Do not exempt new functions
   or discard historical coverage debt.
3. Run applicable numerical/compatibility checks. Domain-contract/solver/format
   changes require G6; prior G6 evidence is stale when its source inventory changes.
   A narrow same-format serialization repair can justify a narrower gate with
   explicit round-trip/failure evidence. Record all unavailable devices.
4. Review source/test/provenance evidence and allowed-file scope. Require a
   concrete contract, meaningful assertions, unchanged numerical tolerances,
   and explicit remaining host/device work. Self-review is labelled as such.
5. Prepare separate PR-ready commits/diffs against a common published base when
   that base is ready. Do not target old remote `main` with all checkpoint changes
   repeated in each issue PR. The user subsequently authorized publication: all three PRs below are ready
   for review, not drafts.
6. Integrate sequentially in a separate integration checkout. Regenerate shared
   coverage matrices from combined source rather than resolving their conflicts
   by concatenation. Rerun the affected combined gates before merge.

The coordinator owns shared issue/feature registers and integration records.
Each PR reports what its Python scope establishes and what remains for C#/Rhino;
partial core fixes do not close a whole mixed-surface issue.

## Following waves and deferred work

| Queue | Issues | Direction |
| --- | --- | --- |
| Next Python features/contracts | 007, 028, 031, 033, 035, 038, 043 | Vector/sample and grid contracts, bounded CSV/probe export, observable formulas/provenance, capability rejection and a focused stronger-testing pilot. Scope after first safety/preflight results; avoid overlapping `fields.py` edits. |
| Numerical/device studies | 001, 003, 004, 005, 009, 011, 014, 040 | Remaining parity, physical-viscosity/boundary/load studies, refinement, profiling and multipart-geometry feasibility. One owner per solver area; actual device/reference evidence required. 001 follows CUDA candidate integration. |
| Research only until separately bounded | 010, 012, 013, 015, 041, 042 | Additional engines, particle/free-surface/propulsion, masked forcing and thermal physics. Do not turn these into broad implementation assignments. |
| C#/Rhino later | 002, 006, 008, 027, 029, 030, 032, 034, 036, 037 | Install/host checks, examples, actual trimming reproduction, opt-in startup, views, baking, canvas presentation and host orchestration. Headless Python cannot close these host claims. |
| Documentation later | 039 | Broader documentation/site work after this Python-first batch. |
| Separate CUDA acceptance | 044, 045, 046 | Already repaired in candidate `46fe0a6`; Windows acceptance/integration remains. No duplicate implementation here. |

HAWA-021/022 own the first numerical study; HAWA-026 applies across all code PRs.
The initial studies do not assume that the remaining list is entirely defective
or that every idea should become a feature.

## Published batch and review follow-up

All PRs target `codex/python-study-base-20261109`, not `main`. The original
snapshot is `a26924c`; subsequent shared commits repair hosted CI provisioning.
On November 9, PR #4 was merged into this study base (`a00223f9`). This does not
mean the main working checkout, installed plugin or released package contains it.
PR #3 subsequently merged into the same base (`74eae0d`); PR #5 incorporated
that combined source and refreshed coverage again.

| Package | Published result | Initial implementation evidence | Current follow-up |
| --- | --- | --- | --- |
| HAWA-048 | [PR #3](https://github.com/range-et/hawa-cfd/pull/3), merged into study base | 637 native tests, 32 CUDA skips, 33 contracts; 31 Docker tests | Review fix now covers both NPZ writers (HAWA-051); 35 focused native/Docker tests, 671 full tests and 33 contracts pass; pushed 94aed35, hosted function/review checks pass |
| HAWA-049 | [PR #4](https://github.com/range-et/hawa-cfd/pull/4), merged into study base | 654 native tests, 32 CUDA skips, 33 contracts; 58 Docker tests; 97,561 G6 rows pass, 4,898 unavailable-device rows blocked | Preserve scoped alignment repair; broader HAWA-028 and main/release integration remain separate |
| HAWA-021/022 harness | [PR #5](https://github.com/range-et/hawa-cfd/pull/5), merged into study base | 656 native tests, 32 CUDA skips, 33 contracts; 32 Docker tests | Review fixes implemented: malformed descriptor reports, selected-device provenance and actual ratio-2 replay; 45 focused native/Docker tests / 699 full tests and 33 contracts pass; Final follow-up handles rehashed corrupt NPZ reports and integrates merged #3: 49 focused native/Docker tests and 720 full tests pass; pushed 6bf7875; hosted function/review checks pass; merged as d9cc3a7 |

The evidence column describes initial implementation; the follow-up column records revised tests.
Both revised branches incorporate the merged domain repair and regenerate
combined measured coverage. The transfer smoke/replay reproduced RMS error
32.6437% against the unchanged 10% limit; HAWA-021/022 remain open. C# and Rhino
implementation remain deferred. This review batch and its checks are complete. Preserve the remaining numerical,
Windows and host qualification gaps when sequencing the next batch.

The older [CUDA PR #2](https://github.com/range-et/hawa-cfd/pull/2) received only
its review-requested MPS device comparison repair (`a92dbb1`, directly on the old
PR head). Both original MPS failures reproduced; the fixed KBC tests pass 6 cases
with 4 CUDA skips, and its old-branch full suite passes 202 with 79 skips (78 CUDA,
1 MPS float64). No newer study checkpoint was imported. The broader CUDA runner
repairs and exact Windows acceptance remain separate.

Final observed GitHub status: PRs #3/#4/#5 are merged into the study base, whose
head is `d9cc3a7`. PR #2 merged into remote `main` as `65e220e`. These merges were
performed outside this agent's actions while checks were running. The working
checkout remains unchanged in production source; combining the shared study base
with remote main and the separate CUDA acceptance-runner repairs is still an
integration task. No new review findings appeared on the final PR #5 head.
