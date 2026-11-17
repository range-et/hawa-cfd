# Windows verification portability — 2026-11-17

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

Final Windows rerun, mutation-tooling study and fresh measured coverage
remain pending. Original failed evidence is retained separately from reruns;
none of these failures or unavailable-device skips count as passes.
