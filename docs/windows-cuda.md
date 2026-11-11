# Windows CUDA verification

This workflow verifies Hawa's headless PyTorch CUDA implementation on actual
NVIDIA hardware. It covers the same numerical service used by the plugins.
Live Rhino installation, docking, Grasshopper scheduling and viewport behavior
require separate host checks. A successful headless run does not pass those gates.

## Environment setup

Run from the checkout in PowerShell:

```powershell
uv sync --extra test
uv pip install --python .venv/Scripts/python.exe 'torch==2.8.0+cu128' --index-url https://download.pytorch.org/whl/cu128 --no-deps
$env:PYTHONUTF8 = '1'
.venv\Scripts\python.exe scripts/bootstrap_reference.py
```

The plain pinned PyPI installation produced `torch 2.8.0+cpu` on the tested
Windows machine, with `torch.cuda.is_available() == False`. The explicit CUDA
wheel is necessary here. PyTorch documents this distribution at
[previous versions, 2.8.0](https://pytorch.org/get-started/previous-versions/).
The CUDA 12.8 wheel includes `sm_120`, which this RTX 5070 Ti uses.
This is a build variant of the pinned PyTorch version; NumPy remains 2.0.2 and
production Python remains 3.9. The isolated upstream oracle uses Python 3.12.

Use the environment's Python directly after installing the CUDA variant.
Another `uv sync` or syncing `uv run` may restore the CPU wheel from the lockfile;
if so, reinstall the explicit CUDA wheel. No system Python, GPU driver, global
NuGet setting or installed Rhino plugin is changed by this workflow.
The current Rhino bootstrap still requests plain `torch==2.8.0`; automatic CUDA
installation inside a clean Rhino environment remains an open integration task.

## Repeatable commands

```powershell
.venv\Scripts\python.exe scripts/verify_cuda.py --repeats 3
.venv\Scripts\python.exe scripts/verify_cuda_benchmarks.py --output results/windows-cuda/my-fresh-benchmarks.json
```

`verify_cuda.py` creates a unique UTC-stamped evidence directory, or accepts a
fresh `--output` directory. It refuses to reuse a directory. It records the
commit, working tree, source hashes, actual GPU/runtime, commands, exit codes,
JUnit files and numerical comparison reports. Its stages are:

1. Repeat the complete Hawa suite, requiring a successful CUDA operation before
   collection and checking for actual CUDA test cases with no CUDA skips.
2. Run the vendored upstream tests for the portable implementation on CPU and
   CUDA, in FP32 and FP64 where parametrized.
3. Compare the compatibility engine's CPU FP32/FP64 and CUDA FP32 fields with
   the isolated, pinned upstream oracle at iterations 0, 1, 10 and 50.
4. Execute all 16 upstream entrypoints on CPU and CUDA with the existing bounded
   profile, then compare every saved field using the original tolerances.

Use `--stages suite`, `--stages upstream`, `--stages parity` or `--stages examples`
for a targeted rerun. The default runs all four. A subset is not a full pass.

The benchmark command runs the existing comoving-body check, three refinement
grids, six fractional-wall channel configurations and three rotating-sphere
grids on both CPU and CUDA. It retains motion invariance thresholds, checks
refinement improvement/mass drift, and compares scalar observables at
`rtol=3e-4, atol=2e-6`. It reports analytic errors; these runs are implementation
checks, not experimental physical validation.

## Upstream native-extension boundary

Hawa always requests `use_native=False`: PyTorch executes the CUDA tensor work.
Lettuce also has a separate generated CUDA extension that needs a compiler
toolkit. That extension is outside Hawa's production execution path.

The portable upstream run excludes the native test directory and `Native`
parameter cases. It loads `scripts.pytest_portable`, which changes only an
omitted `Context(use_native=...)` default to `False`. Explicit devices, dtypes,
native arguments, test assertions and tolerances remain unchanged. This matters
because four otherwise relevant upstream tests use `Context()` and implicitly
enable code generation when a GPU is present. Their unadapted run fails on this
machine because `CUDA_HOME`/the compiler toolkit is unavailable.

The upstream suite's own skips remain visible in JUnit and logs. They include
unsupported stencil/model combinations and upstream TODO tests. They do not
count as passing tests. Original upstream test files are unchanged.

## Windows verification repairs

- The source audit normalizes CRLF to LF and uses POSIX manifest paths. It still
  detects substantive source edits, changed upstream tests and extra modules.
- Nested example names use POSIX separators, and worker output paths are
  absolute before the worker changes its current directory.
- The efficient-bounce-back cylinder script and its notebook launcher import
  Unix `resource` for a peak-memory diagnostic. On Windows, the isolated worker
  supplies that diagnostic from `psutil`'s actual peak working-set counter,
  converted to KiB. This adaptation is recorded in each affected report; original
  example files and numerical calculations remain unchanged.
- Example comparison accepts explicit CPU/GPU evidence directories, verifies
  complete inventories and matching source hashes, and retains all tolerances.
- Solver tests now explicitly cover CPU/CUDA/MPS for lifecycle, checkpoints,
  recording, optimization, moving bodies, refinement and outlet stability.
  Device-parity loops also include CUDA. Missing hardware remains a visible skip.

The initial November 9 verification report
preserves the original PorousMedium and rotating-sphere failures. The subsequent
[repair record](verification-windows-cuda-fixes-2026-11-09.md) documents the fixes
and fresh verification on `codex/windows-cuda`. KBC now uses FP64 collision
intermediates on CPU/CUDA with FP32 storage; see that record for the cost and
scope. MPS parity and clean Rhino CUDA dependency installation remain open.
