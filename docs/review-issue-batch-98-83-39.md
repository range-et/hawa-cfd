# Parallel issue batch integration review

Date: November 16, 2026. Integrator/reviewer: Codex root agent. Implementation
agents: `issue98`, `issue83`, and `issue39`; these are actual task participants,
not independent human or physical-validation reviewers.

The three issue worktrees start at main `1b4e6c7`. The original development
checkout and its 26 pre-existing modified/untracked files are preserved.
Integration occurs only on `codex/issue-batch-98-83-39`, not main. No issue closure,
GitHub publication or release is established by this record.

## Candidate and checks

Final measured integration source `02d51d9` contains #98 production fixes through `99e4197` and its
mutation CPU guard `7e3e659`, #83 through `c533d5e`, and #39 through the reviewed
cancellation repair `17046e5`. Final mutation policies through #98 `cf2e7fe` and #39 evidence `e5a92a8`
are integrated. Final combined Python 3.9/3.12 checks, coverage and compatibility evidence pass
within the declared local scope.

Fresh root checks on macOS, Python 3.9.25:

- Focused quality provenance, host controller and mutation CPU guard: 76 passed.
- Final measured Python 3.9: **1,899 passed, 87 skipped**, 213 warnings,
  299.97 seconds; all expected test IDs matched fresh collection.
- Final Python 3.12.4 developer suite: **1,889 passed, 97 skipped**,
  215 warnings, 239.41 seconds. Production-only checks remain on Python 3.9.
- Final instrumented StateContracts: **121 passed**. Linked production sources
  use host/transport doubles, not a Rhino kernel.
- Strict headless coverage and baseline ratchet against `1b4e6c7`: passed;
  **1,001 covered functions, 308 unmeasured host functions, 58 declarations**.
  Committed matrix refreshed and its baseline check passes. Strict line evidence
  is checked against the raw results directory; it is not duplicated in docs.
- Ruff on the integrated checkout: passed.
- Combined G6 `results/g6-issue-batch-final`: all 102,459 declared rows present;
  100,010 passed, zero failed, 2,449 CUDA rows blocked, 331.23 seconds.
  Runner verified exact row inventory, unchanged source hashes and archives.
  CPU/MPS local pass; release pass false.
- Example archive inventory validation: 53 public nodes, 31 definitions,
  188 distinct observed port combinations. This is not a live gallery run.
- Build/package succeeded with zero compiler errors and platform warnings;
  ZIP integrity and exclusion of legacy example 09 definitions were checked.

Installed development candidate `6ed101244ff0345e962664630efddf1516d17c1f`
contains the same plugin production sources as `085d4a3`. Later changes concern
the runner scripts, tests, mutation harness and records. Rhino was quit normally
after saving the initially empty document, the previous installed bundle was
backed up, and the candidate was installed while Rhino was closed. No loaded
assembly was replaced. Preservation files are under
`results/host-preservation-20261116/` in the integration worktree. This is a local
development installation, not a release or clean-machine qualification.

## Sequential host evidence

Only one agent operated Rhino at a time. See the scoped records for exact
fixtures, devices, numerical values and omissions:

- [Obstacle preflight](review-obstacle-preflight.md): kernel, Geometry and
  GeometryCheck fixtures; CPU native solid, hollow and touching bodies;
  transverse self-intersection refused before a job starts. Native selection
  of malformed fixtures rejected by Rhino itself is not credited to Hawa.
- [Host runner](review-host-acceptance-pilot.md): two CPU 31/32 pilot sequences,
  record/playback, inspected captures, active cancellation and cleanup. Root
  requested independent review by `issue83`, which found an uncertain-open
  cancellation race. `issue39` repaired it; `issue83` re-reviewed it. The final
  adapter passed a live cancellation with omitted ownership response, recovering
  its owned GH reference and reaching zero jobs/sessions/workers/cleanup/refresh.
- [Quality provenance](review-quality-provenance.md): targeted CPU GH08 and native 300-step warning checks retain the step-5
  density trigger after current density recovers; checkpoint reload preserves
  it. Root inspected the actual native panel through desktop accessibility and
  screenshot: completion 300/300, warning, quantity/value/limit/step and wrapped
  time are readable without clipping or overlap at the observed panel width.
  The screenshot is retained in the chat tool output; no local image artifact or
  viewport framing/convergence claim is made.

The original development checkout was not used for edits or installations.
Tests use owned geometry/documents and preserve blank existing GH documents.
Native live-object count, case ownership and pending cleanup were checked after
host tests. The native document's dirty flag was retained, not cleared to conceal
operations. A disclosed possible idle auto-backend initialization overlap is
recorded in the #83/#98 reports; subsequent runs selected CPU before execution.

## Review and gate disposition

Root reviewed trigger/checkpoint admission, threshold formatting, obstacle
validation/cancellation, geometry scheduling and runner retry/cleanup behavior.
`issue83` additionally reviewed combined interactions at `085d4a3` and found no
further actionable defect; all local file links in the eight then-changed
Markdown records resolved. Review does not substitute for measured execution.

| Gate | State at this checkpoint | Evidence / remaining work |
| --- | --- | --- |
| G0 | PASS for bounded scope | Existing issues/contracts; no new numerical method or dependency. |
| G1 | PASS for bounded scope | Reviewed contracts, ownership and cancellation repair; scoped live recovery. |
| G2 | PASS for automated local scope | Complete 3.9/3.12 suites, strict headless/base ratchet, reviewed mutations and build pass. |
| G3 | No new physics qualification | No tolerance relaxed. Sampled warnings and finite runs are not accuracy or convergence evidence. |
| G4 | PASS for targeted workflows; broader gate incomplete | Sequential scoped Rhino checks pass; full supported gallery, all native layouts and lifecycle combinations not rerun. |
| G5 | Local development package/install only | Backup and normal restart; no release, clean-machine or merged-main claim. |
| G6 | PASS on CPU/MPS; CUDA BLOCKED | Combined matrix passes locally: 100,010 rows passed, zero failed, 2,449 unavailable CUDA rows blocked; Python 3.9 exact test inventory and 121 state contracts reconciled. |

The legacy aggregate compatibility checker hardcodes 67 state contracts although
the current suite has 121. Do not claim that checker passed. Direct matrix/archive verification, exact full-test collection comparison and the
actual 121-contract result passed; no repository checker change was made.
The compact local record is `results/issue-batch-final-evidence.json`.

Final package checks: ZIP integrity, matching 29 runtime/source Python files,
legacy 09 definition exclusion and local Markdown link checks pass. Final original
checkout preservation audit matches all 26 starting file hashes. Issue branches
remain separate and clean; this integration is local, with no push or main merge.

## PR #112 review follow-up

Greptile's first review (4/5, comment 4595057470) found that corrupt ownership
JSON prevented cancellation before the host could recover its retained document.
Integration `6872f1b` fixes atomic ownership publication and CLI recovery, with
foreign-run rejection and canonical UUID parsing retained. `issue83` independently
reviewed the repair; `issue39` verified actual corrupt-file cancellation in Rhino
(run j), zero resources and preservation of both blank GH documents/native model.
No plugin assembly or numerical source changed; prior G6 source evidence remains
valid. See the [runner follow-up](review-host-acceptance-pilot.md#pr-112-corrupt-ownership-follow-up).

Fresh combined Python 3.9 measurement after this repair:
**1919 passed, 87 skipped**, 213 warnings, 280.10 seconds; **121 state contracts**.
Strict headless and `1b4e6c7` baseline checks pass; refreshed committed matrix:
1001 covered, 308 unmeasured host functions, 58 declarations. Evidence directory:
`results/function-coverage-pr112-owner-repair`. Both Python versions pass the
46 focused controller tests; host-controller mutation policy accepts 600 assertion
kills and 42 explicitly reviewed survivors from 642 mutants. The preceding full
Python 3.12 result remains tied to its prior source; PR CI reruns the full suite
on this repair. Merge additionally requires all repository checks and Greptile
5/5 approval on the final head; no earlier green check is substituted.
