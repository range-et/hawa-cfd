# Hawa Lettuce compatibility fork

Based on lettucecfd/lettuce commit
`88a6559def2a49fd7f425fd05954ec1e3db2cdb6`. Original authors and MIT license are
preserved in AUTHORS.rst and LICENSE. README.md and UPSTREAM-pyproject.toml are
unaltered upstream reference files; they do not describe this fork's installation.

Distribution: `hawa-lettuce`; Python import: `lettuce`. Never install this alongside
the upstream `lettucecfd` distribution in the same environment, because they own
the same import namespace. The comparison tools use separate processes and verify
the loaded source paths and hashes.

Initial changes covered packaging, metadata identity, Python 3.9 type-annotation
compatibility, and MPS device selection/synchronization. The packaging metadata
accepts Python 3.9 to 3.12 only so that Hawa's Python 3.12 developer environment
can install the fork editable; production and engine parity runs stay on 3.9.
Subsequent repairs also modify the explicitly audited numerical modules; this is
not an unchanged solver.
`upstream.json` records SHA256 digests of all original source modules.
`scripts/audit_backport.py` reports and enforces the expected changed-file list.

The Windows CUDA repair computes FP32 KBC collisions with FP64 intermediates on
the same CPU/CUDA device, then rounds the result to FP32. Storage and streaming
remain FP32, and the existing near-zero stabilizer guard still uses storage
precision. This avoids amplification of moment cancellation in PorousMedium;
it costs additional temporary memory and execution time. FP64 input retains its
existing path. MPS has no FP64 and no CPU fallback: for FP32 storage with Lettuce's quadratic
equilibrium it evaluates the same KBC decomposition with FP32 hi/lo
(TwoSum/TwoProduct) intermediates, an exact raw-moment split and one final
rounding. On identical inputs this reproduces the rounded CPU result; see the
[HAWA-001 repair record](../../docs/review-porous-kbc-repair.md). See the
[repair verification record](../../docs/verification-windows-cuda-fixes-2026-11-09.md)
for measurements, regressions and limits. Original upstream tests and examples
are unchanged.

The CUDA generator is retained but is not required for the portable tensor path.
Parity checks explicitly use `use_native=False` on both engines. Native CUDA
compilation/execution requires a separate NVIDIA hardware validation run.

The upstream test suite is copied unchanged. Run it in a separate pytest invocation
from Hawa's tests (both have a top-level `tests` package).
