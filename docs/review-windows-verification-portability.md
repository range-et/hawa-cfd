# Windows verification portability — 2026-11-17

Tracked in [#117](https://github.com/range-et/hawa-cfd/issues/117).

Implementation: Codex atmosphere_qualification and numerical_exports agents,
with root coordinating LF attributes and integration. Independent read-only
review by domain_validation found no actionable defects in commits `6af5e4e`,
`50dbc14`, `dee9b9c` and `3dcca31`: raw-byte hashing and unknown-scope rejection
remain intact, Windows path cases exercise the repaired behavior, and GH/3dm
archives receive no new text/eol attributes. This review does not replace the
required Windows rerun or measured gate.

PR #116's first Windows headless run used production commit
`1cc3a80ccdd233bef24d2cd8213710c36d60cf97`, Python 3.9.25,
PyTorch 2.8.0+cu128 and an NVIDIA GeForce RTX 5070 Ti (driver 621.14).
The Hawa c110p chat operated Windows; the Mac coordinator retained the sole
Rhino license. Windows Rhino was not part of this verification.

The suite reported 1,951 passed, 92 skipped and 20 failed. All 91 explicitly
named CUDA cases passed. The separate device smoke gate passed all five
comparisons against CPU FP64, including bitwise KBC agreement, with unchanged
source snapshots and no foreign imported modules. These are headless PR
results, not installed-host or merged-main device qualification. The original
Windows G6 run also passed 100,010 rows with zero failures; 2,449 unavailable
MPS rows were blocked and all CUDA rows passed, with unchanged source hashes.

The failures exposed verification portability defects:

- Fifteen policy checks correctly rejected raw-byte hashes after Windows Git
  converted LF sources to CRLF. All 89 policy source entries matched after
  diagnostic normalization; the checker must continue hashing exact bytes.
- Two foreign-module fixtures compared unresolved Unix paths with resolved
  Windows paths.
- A mutation draft fixture wrote platform-translated newlines but expected
  an LF byte hash.
- Mutation export test doubles keyed files by POSIX paths but received native
  Windows strings; the launcher also compared native source paths against
  Git's POSIX changed-line scope.

The correction requires LF checkout attributes for policy-pinned text,
portable fixtures and canonical Git path identities in mutation tooling.
All 541 tracked files matching the new attribute extensions already contain
LF in the committed blobs; no source-byte renormalization is required.
Binary Grasshopper archives are outside these attributes.

The portable device-smoke fixtures pass all 44 focused Python 3.9 tests.
The fresh Python 3.12 mutation study (`results/device-smoke-mutation-portable-final-20261117`)
contains 1,207 mutants: 998 assertion kills and 209 reviewed survivors/no-tests
(95 survived, 114 had no selected tests), with 43 passing controls and zero
errors. Its runner now uses the existing CPU-only plugin: preliminary forked
Metal crashes were errors, not kills, and that study was discarded.
Exact artifact-name assertions kill uppercase manifest/directory mutations
even on case-insensitive filesystems. The `GIT` executable-case mutation remains
an explicitly bounded macOS filesystem equivalence, not cross-platform proof.

The final mutation-tooling study
(`results/mutation-tooling-windows-paths-final-20261117`) contains 576 mutants:
520 assertion kills and 56 reviewed survivors, with 61 passing controls and
zero errors/timeouts. All six uppercase artifact filename mutants are killed;
temporary evidence fixtures explicitly enforce case-sensitive lookup and
directory entry spelling. The complete test file passes 76 tests on Python 3.9
with its real-mutmut integration skipped, and 77 on Python 3.12 including that
integration. The exact source/test policy is refreshed without hash normalization.

The fresh Mac measured gate at `3dcca319` passes: 1,978 Python tests,
87 skips (85 unavailable CUDA, one unsupported MPS float64, one Python 3.12-only
mutmut integration), 213 warnings and 127 instrumented .NET contracts.
Both strict headless function/line coverage and trusted-base `d12fd069` checks
pass; the committed matrices are refreshed from
`results/function-coverage-portable-final-20261117`. The 299 host-only C# functions
remain unmeasured and 60 declarations remain explicit, not credited as passes.

## Final Windows rerun

The Windows operator used the Mac coordinator's final-candidate handoff on
[PR #116](https://github.com/range-et/hawa-cfd/pull/116#issuecomment-6939585504):
`0e219a9a4dd92c412bc17fe30b2dd3c54e1c917b`. Direct cross-chat delivery was
unavailable from Windows; the operator acknowledged the agreed source on the PR
before proceeding. No competing source edits were made. A new isolated worktree
preserved the earlier failed checkout, evidence and original development setup.

On Windows build 26300, RTX 5070 Ti, driver 621.14, Python 3.9.25,
torch 2.8.0+cu128, CUDA 12.8, NumPy 2.0.2 and pydantic 2.13.5:

| Fresh check | Result |
| --- | --- |
| LF checkout / exact policy hashes | All 541 attribute-covered text files use LF; all 91 policy source entries match raw bytes |
| Focused smoke/mutation tests | 120 passed, one Python 3.12-only integration skipped |
| Complete Hawa suite | **1,973 passed, 92 skipped, zero failed**, 213 warnings; 273.75 seconds |
| Named CUDA suite cases | **91 passed**, zero failed/skipped |
| CUDA smoke against CPU FP64 | **5/5 passed**, zero guarded; 53.39 seconds |
| G6 finite matrix | **100,010 passed, zero failed**, 2,449 unavailable MPS rows blocked; 175.41 seconds |
| CUDA G6 rows | **2,449 passed**, zero failed/blocked |
| G6 source/row/archive verification | PASS; 102,459 rows, 53 public nodes, 31 examples, 188 observed port combinations |

The complete suite uses an independent collection and exact outcome/JUnit
inventory through `verify_cuda.py --stages suite --repeats 1`; it includes all
2,065 tests, not a filtered subset. Its 92 skips are 90 unavailable MPS cases,
one CPU-default check inapplicable on CUDA hardware and one real-mutmut test
requiring the developer Python environment. Warning categories include upstream
MRT/plotting deprecations and intentional invalid-input numeric warnings; the
complete log is retained. No skipped case counts as a pass.

GPU jobs ran sequentially: focused tests, complete suite, smoke, then G6. Actual
selected backend was `cuda:0`; imports came from the isolated worktree. Source
and index snapshots stayed unchanged through all checks and final verification.
No production Python blob differs from the original failed candidate `1cc3a80`.
The mutation tooling and test repairs are the already reviewed Mac commits above.
No numerical tolerance, provenance guard or assertion was relaxed.

[Machine record](verification-pr116-windows-cuda-2026-11-17.json) includes commands,
versions, fixed smoke policy, each comparison, source/index hashes, skips,
artifact hashes and the integrity-checked raw evidence ZIP location/SHA256.
Raw logs, JUnit, independent inventory, reference/candidate arrays, G6 rows and
fixtures remain in `results/pr116-cuda-final-2026-11-17/` in the Windows worktree
`C:/Users/range/Desktop/hawa-cfd-pr116-cuda-final`.

Reviewer: Codex Windows operator, executing these checks independently from the
Mac implementation. G0/G1 retain the scoped method/contracts already reviewed;
G2 now passes this Windows full-suite check, G3 passes the bounded smoke policy,
and G6 passes the available CPU/CUDA finite product with MPS explicitly blocked.
The separate Mac measured/mutation records above remain Mac evidence; they were
not rerun as Windows instrumentation. This evidence-only increment changes no
executable function and does not refresh their matrices as if Windows measured
them. G4 Windows host and G5 installed/release qualification are **not run**.

Windows Rhino was never launched, attached to, initialized or run. Mac retains
the sole license; a future Windows host handoff requires explicit Mac-closed
confirmation. No plugin build/install, release, merge, full-duration physical
qualification or generated native CUDA extension claim follows from this round.
The old upstream-suite/example/benchmark stages were not part of this requested
rerun; `verify_cuda.py` correctly records its broader `full_scope` as false.

The #117 Windows acceptance criteria now pass on this exact PR candidate.
Merge remains the coordinating maintainer's decision. These are pre-merge
headless results, not merged-main or installed-host CUDA qualification.

Original failed evidence is retained separately from reruns;
none of these failures or unavailable-device skips count as passes.
