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
compatibility, and MPS device selection/synchronization. Subsequent repairs also
modify the explicitly audited numerical modules; this is not an unchanged solver.
`upstream.json` records SHA256 digests of all original source modules.
`scripts/audit_backport.py` reports and enforces the expected changed-file list.

The Windows CUDA repair computes FP32 KBC collisions with FP64 intermediates on
the same CPU/CUDA device, then rounds the result to FP32. Storage and streaming
remain FP32, and the existing near-zero stabilizer guard still uses storage
precision. This avoids amplification of moment cancellation in PorousMedium;
it costs additional temporary memory and execution time. FP64 input retains its
existing path. MPS retains its FP32 path, without a CPU fallback; historical
CPU/MPS PorousMedium parity remains unresolved. See the
[repair verification record](../../docs/verification-windows-cuda-fixes-2026-11-09.md)
for measurements, regressions and limits. Original upstream tests and examples
are unchanged.

The CUDA generator is retained but is not required for the portable tensor path.
Parity checks explicitly use `use_native=False` on both engines. Native CUDA
compilation/execution requires a separate NVIDIA hardware validation run.

The upstream test suite is copied unchanged. Run it in a separate pytest invocation
from Hawa's tests (both have a top-level `tests` package).
