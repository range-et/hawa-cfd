# CUDA PR #2 integration review

November 9, 2026. Reviewer: Codex primary agent, source review and local execution;
no independent human approval. **Do not merge the PR as submitted.** Its numerical
repairs have useful bounded evidence, but its new verification tooling can report
incomplete or mixed-source evidence as passed, its MPS tests fail, and integration
with our function gate requires additional measured tests.

## Repair follow-up

The original findings below are retained as historical review evidence. The
[corrected candidate](review-cuda-blocker-fixes.md) now passes local checks and
resolves the 17 function-coverage blockers. Its Windows CUDA rerun is still
required; the original PR branch has not been pushed or merged. Use the
[exact-candidate handoff](windows-cuda-merge-checks.md), not the old PR head.

## Exact scope

Reviewed [PR #2](https://github.com/range-et/hawa-cfd/pull/2), head
`864a2652eed371ab8c16e65d9ab1228d09a00e79`, base `d3a5793`, against local
`0822db9`. GitHub had no submitted reviews/status checks at inspection. The PR’s
33 changed files include Windows harness portability, device parametrization,
KBC collision precision and moving-body geometry—not just CUDA tests.

An uncommitted integration candidate is at `/Users/r2d2/Desktop/hawa-cuda-review`,
branch `codex/cuda-review-integration`. A no-commit merge applied cleanly; the
primary checkout and prior documentation edits were preserved. Only the MPS
assertion fix below was added to that candidate. No GitHub merge, push, posted
review, installed assembly replacement or release occurred.

## Findings to fix before merge

### HAWA-044 — P1: CUDA runner accepts a filtered suite as complete

At PR `scripts/verify_cuda.py:60,78–83,94`, the runner inherits `PYTEST_ADDOPTS`
and configured pytest selections, then accepts any nonempty set of CUDA cases
without comparing collected/executed IDs to the intended suite. For example,
`PYTEST_ADDOPTS='-k test_kbc_equilibrium'` selects only a small subset on CUDA;
all can pass while the runner's suite stage succeeds. This defeats the stated
complete-suite guarantee and can hide an unrelated regression.

Reproduced with controlled child-process/JUnit injection: one passing testcase
named `test_one[cuda:0]`, inherited `-k test_one`, exit 0 → runner exit 0 and
`passed: true`. CUDA was mocked only to test orchestration; this is not hardware
evidence. Reproducer: `results/pr2-review/probe_runner.py` in the review checkout.

Required repair: explicitly neutralize external selection for full verification,
collect the independent intended test inventory under the same device environment,
and compare exact IDs/counts with execution. Reject missing/duplicate cases and
JUnit failures/errors even if a subprocess reports success. Keep intentional
upstream native exclusions explicit. Regression tests must prove that filtered
or incomplete execution cannot satisfy the full-suite gate. Partial `--stages`
runs should declare selected scope, not appear to be full qualification.

### HAWA-045 — P2: source drift does not invalidate CUDA evidence

At PR `scripts/verify_cuda.py:55–58,109`, source hashes are captured only before
execution. A file changed between suite, parity and example stages can yield
`passed: true` attributed to the original source. The new benchmark runner also
hashes benchmark scripts rather than the complete engine inputs. This conflicts
with the existing unchanged-source evidence requirement.

The same controlled probe rewrote a hashed Python input during a child stage;
the runner still returned exit 0 / `passed: true`. Required repair: compare the
complete relevant source/test/config/lock inventory before and after all stages,
reject additions/deletions/changes, and record staged as well as unstaged changes.
Apply consistent provenance to supplemental benchmarks. Add mutation/fault tests;
do not silently bless evidence produced while an agent edits the checkout.

### HAWA-046 — P2: new device assertion fails on working MPS

PR `tests/test_kbc_precision.py:47` compares `str(flow.f.device)` with the fixture
string `mps`. PyTorch reports `mps:0`. Both D2Q9 and D3Q27 MPS cases fail here,
before the numerical assertion. The original focused run produced **2 failed,
36 passed, 21 skipped**. The skips include absent CUDA and the deliberate MPS
FP64 exclusion.

A local candidate fix compares `flow.f.device == before.device`, retaining the
FP32 assertion. This tests actual device preservation without conflating aliases.
The corrected complete suite passes below. Incorporate this fix into the reviewed
PR revision before closing the item; it is not posted or merged.

### HAWA-026 / integration gate: 17 new or changed functions lack measured tests

The current function gate ran on the combined source and failed with **17**
new/changed untested functions. These include CUDA orchestration, the portable
upstream adapter, Windows resource adaptation, rotating-sphere benchmark and
modified example/parity runner entry points. The candidate’s old committed matrix
also fails the freshness check. The original PR predates this gate; that explains
the gap but does not satisfy today’s acceptance rules.

Add behavioral tests for the changed harness paths (including the false-pass
cases above), measure execution, regenerate both committed matrices and check
against `0822db9` as the trusted integration baseline. Do not reset the baseline
or weaken numerical tolerances. Headless mocks can test orchestration contracts;
real CUDA execution still requires the device runner.

## Numerical and architectural assessment

KBC’s wider CPU/CUDA intermediates retain FP32 storage/streaming and the
storage-precision stabilizer guard; MPS deliberately keeps FP32. The shallow
working flow/context leaves original inputs intact in the supplied tests. The
local near-equilibrium/conservation/equilibrium tests pass after the alias fix.
The recorded Windows improvement and resource cost are plausible bounded evidence,
not an independently reproduced CUDA pass on this Mac. Review the measured
CPU/CUDA time and temporary-memory costs before adopting the policy.

Ordered transforms and rationalized radial distance use the same signed distance
for classification and wall links. New surface-neighbour and off-pivot
sphere/cylinder tests pass locally on available devices. No tolerance was relaxed.
Neither a finite sphere benchmark nor the broader unit suite establishes physical
validation, arbitrary-geometry accuracy or atmospheric qualification.

Fresh CPU/MPS PorousMedium evidence on the combined candidate retains the original
512×512, 50-step case and field tolerances:

| Field | Maximum absolute difference | Comparison |
| --- | --- | --- |
| Populations | 0.0007722378 | FAIL |
| Density | 0.0006060004 | PASS under combined relative/absolute tolerance |
| Physical velocity | 0.02718640 | FAIL |
| Physical pressure | 0.24240017 | FAIL |

HAWA-001 remains open. This is one bounded example, not a fresh run of the entire
16-example inventory. The PR can only make a CPU/CUDA repair claim; CPU/MPS
qualification cannot be inferred. Unmodified-upstream parity and the full
supplemental benchmark set were not rerun in this review.

[Compact machine summary](verification-cuda-pr2-review.json).

## Checks actually run

Environment: macOS arm64, Python 3.9.25, PyTorch 2.8.0, native MPS available,
CUDA unavailable, .NET 10.0.403. Raw evidence is in the review checkout under
`results/pr2-review/`.

| Check | Result / evidence |
| --- | --- |
| No-commit integration | Applied cleanly against `0822db9`; not a merge approval |
| Original focused regression run | 2 failed / 36 passed / 21 skipped; `focused.xml` |
| Corrected full Python suite | 668 passed / 82 skipped (81 CUDA unavailable, 1 MPS FP64 exclusion) / 4 existing MRT warnings; `function-gate/pytest.xml` |
| Vendored upstream KBC subset | 12 passed / 78 skipped (60 CUDA unavailable, 18 unsupported stencils), 406 deselected; portable tensor adapter, CPU. Not a full upstream/oracle run; `upstream-kbc.xml` |
| State contracts | 33 passed using production-linked host/transport doubles; `function-gate/state-contracts.log` |
| Function gate against current base | FAIL: 17 new/changed untested functions; `function-gate-command.log` |
| Committed matrix freshness | FAIL: old matrix does not describe combined source |
| CUDA runner fault injection | Incorrect success for incomplete suite and changed source; mocked orchestration only |
| PorousMedium CPU/MPS | Both executions complete; field comparison fails as above; `porous/cpu-mps-comparison.json` |
| Full local G6 | 100,010 passed / 0 failed / 2,449 CUDA blocked; 102,459 expected/recorded rows, no source drift; `g6/summary.json` |
| Combined evidence checker | PASS locally: matrix, full declared test modules, 33 contracts and example/public-node inventory; release remains blocked; `g6-checked.json` |
| Plugin build | Both assemblies and development ZIP built; existing CA1416 icon warnings. Not installed |
| CUDA and Windows host | NOT RUN: no CUDA device here; existing PR records are historical branch evidence |
| Rhino/GH runtime for PR | NOT RUN. Separate existing-install startup audit ran afterward without simulation or installing candidate binaries; [record](review-native-intake.md) |

## Merge path

1. Fix 044/045 and incorporate 046; add measured harness tests and current
   function-matrix evidence against our integration baseline.
2. Rerun current CPU/MPS suite, state contracts, applicable G6 and build on the
   exact proposed integration revision. Preserve all newer atmospheric work.
3. Run updated CUDA harness and the declared CUDA/G6/benchmark scope on the RTX
   machine (or another declared CUDA environment); retain source hashes, hardware,
   full inventory and failures. Existing older CUDA counts do not cover new code.
4. Explicitly retain HAWA-001 and Windows embedded installation/host limits. A
   bounded headless merge is distinct from installed/release qualification. No
   universal backend parity claim is supportable from the present evidence.
5. After required evidence and review, merge the bounded change; package/install
   only through the existing normal-quit/build workflow. No automatic release.

## Gate disposition

| Gate | Reviewer | Decision | Scope |
| --- | --- | --- | --- |
| G0 research/evidence | Codex self-review | PASS for review | Scope, references in PR, fixed tolerances and omissions inspected; no new numerical method adopted |
| G1 architecture | Codex self-review | FAIL for evidence lifecycle | Mixed-source evidence accepted; no host/state-schema changes in PR |
| G2 reliability | Codex self-review | FAIL | Findings 044–046 and function gate; corrected candidate suite passes but does not erase gaps |
| G3 numerical | Codex self-review | BLOCKED for integrated CPU/CUDA claim | CUDA unavailable; fresh CPU/MPS comparison fails its separate existing claim |
| G4 UI/UX | Codex self-review | NOT APPLICABLE to headless review | No adapter change; installed host acceptance remains unverified |
| G5 release | Codex self-review | BLOCKED | Development build only; no clean-host test or release |
| G6 compatibility | Codex self-review | PASS locally; CUDA BLOCKED | 100,010 passed / 0 failed / 2,449 CUDA blocked; all 102,459 expected rows, unchanged source. No release pass |
