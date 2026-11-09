# CUDA PR #2 blocker repairs

November 9, 2026. Author/reviewer: Codex primary agent, self-review. Candidate
combines PR head `864a2652eed371ab8c16e65d9ab1228d09a00e79` with current committed
base `0822db93cccb31bdf4dff04cf36ea62522ebc6f6`. The original main checkout's
uncommitted export feature is deliberately outside this candidate. No remote
merge, push, plugin installation or release is performed.

Local candidate commit: `46fe0a6419cc2653062c1e4ea91448d8d5d17825` on
`codex/cuda-review-integration`; the Windows handoff bundle pins this revision.

## Repairs and contract

- **HAWA-044:** clear inherited pytest selectors/plugin injection and override
  configured `addopts`; collect expected node IDs in a separate process before
  each complete run. An explicit plugin records collected IDs and setup/call/
  teardown outcomes. Require exact collected IDs, one completed outcome per ID,
  successful process exits, complete nonduplicate JUnit and matching skip counts.
  Fail on test/teardown errors, malformed/missing artifacts or any missing/skipped
  Hawa CUDA case. Preserve the declared upstream native exclusions. Record
  `requested_stages`, `full_scope` and `full_passed`; a targeted pass cannot claim
  full qualification.
- **HAWA-045:** snapshot every tracked/nonignored repository file, plus HEAD and
  the Git index. Hashes include engine/vendor sources, tests, configuration,
  requirements and lockfiles; deleted paths are represented explicitly. Compare
  after every child stage and at the end of the supplemental benchmarks. Record
  combined HEAD diff and staged diff. Any observed source/index drift fails the
  run. This detects boundary-observed changes; it is not a filesystem monitor or
  protection against deliberately changing and restoring files between snapshots.
  Use an idle, immutable checkout throughout qualification.
- **HAWA-046:** compare the KBC tensor's actual device before/after collision;
  this accepts the valid `mps:0` representation without weakening dtype or
  population checks. No numerical tolerance changed.
- **HAWA-026 scoped debt:** add asserting, measured tests for the PR's runner,
  Windows diagnostic, portable upstream adapter, parity/example orchestration,
  real CPU worker/checkpoint capture and rotating-sphere observable. Keep broader
  pre-existing uncovered functions visible; no baseline exemption or ratchet
  relaxation.

New tests use mock GPU metadata only to exercise orchestration/failure paths.
They are explicitly **not CUDA hardware passes**. A real small pytest subprocess
checks that configured selectors cannot narrow the independently collected run.
The CPU parity/example/rotation tests execute actual solver code. Numerical
CUDA acceptance still requires the Windows run below.

## Local evidence

Environment: macOS arm64, Python 3.9.25, torch 2.8.0, NumPy 2.0.2, MPS available,
CUDA unavailable; .NET 10 state-contract host. Evidence paths are relative to the
candidate checkout's ignored `results/` directory.

- Focused tests: **38 passed, 4 CUDA skips**, 14 matplotlib/pyparsing deprecation
  warnings; `pr2-fixes-focused2.xml`.
- Full function gate: **700 passed, 82 skipped** (81 unavailable CUDA, one
  unsupported MPS FP64), 18 warnings (four existing MRT and 14 matplotlib/pyparsing
  deprecations); **33 state contracts passed**. All 17 original PR coverage
  blockers resolved; zero ratchet failures against `0822db9`. Fresh inventory:
  318 covered, 136 uncovered, 630 unmeasured, 58 declarations. Existing debt stays
  explicit. Both committed matrices refreshed and freshness-checked.
  Evidence: `pr2-fixes-function-gate/` and `pr2-fixes-function-gate.log`.
  The suite took 541 seconds; a slow MPS moving-body test continued and passed.
  No timeout, skip or tolerance was changed to obtain this result.
- Combined evidence checker: **local pass**, 700 tests / 33 contracts / complete
  source-matched G6 inventory; `pr2-fixes-g6-checked.json`. CUDA/release remains
  blocked. [Compact machine record](verification-cuda-blocker-fixes.json).
- Development build: both assemblies and `dist/Hawa-cuda-blocker-fixes.zip`
  succeed with zero warnings/errors in this incremental build; no installation.
- G6 source inventory is unchanged from the complete prior review run
  (`pr2-review/g6`): the repair changes harness/tests only, not the solver,
  compatibility runner or matrix products. Current source/environment revalidation passes, with all 54 public nodes,
  31 examples and 191 unique graph edges accounted for
  (`pr2-fixes-g6-source-check.json`). Combine with the fresh full suite and state
  evidence; this is not a new execution of all rows. Prior result: 100,010 passed, zero failed, 2,449 CUDA
  blocked; all 102,459 expected rows recorded.
- Original review's CPU/MPS PorousMedium failure remains HAWA-001. No new physical
  validation, Windows runtime or live Rhino/GH behavior claim is made.

## Merge disposition

Follow [the exact Windows handoff](windows-cuda-merge-checks.md). Fresh complete
CUDA suites, upstream/oracle/example comparisons, 13 benchmark configurations,
function coverage, G6 and development build are required for the final candidate.
Do not merge from the historical CUDA reports. Installing/releasing remains a
separate host/clean-install decision.

| Gate | Actual reviewer | Decision | Evidence/limits |
| --- | --- | --- | --- |
| G0 | Codex self-review | PASS for bounded repair | Reproduced review failures; criteria fixed before implementation; no new dependency or physics method |
| G1 | Codex self-review | PASS for harness contract | Explicit complete-scope evidence, source/index ownership, fresh output paths; no shared-case or host change |
| G2 | Codex self-review | PASS locally | 700 tests, 33 contracts, zero coverage failures and fresh committed matrix; Windows/CUDA unverified |
| G3 | Codex self-review | BLOCKED for integrated CUDA claim | Hardware rerun outstanding; no physics change in this repair; prior MPS disagreement retained |
| G4 | Codex self-review | NOT APPLICABLE | Headless tooling/test change; no UI/archive/adapter behavior modified |
| G5 | Codex self-review | BLOCKED for release | Development build only; no clean-host install or release |
| G6 | Codex self-review | PASS locally; CUDA BLOCKED | Existing complete matrix source/environment revalidated and combined with fresh suite/contract inventory; no new full matrix execution |
