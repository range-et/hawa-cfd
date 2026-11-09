# PR #2 — Windows CUDA checks before merge

Run these checks on the **final combined integration candidate** identified by
its generated `candidate-commit.txt`, not historical `46fe0a6` or PR #2's old
head. The new branch combines merged PRs #2–#5 and the HAWA-044/045 evidence-runner
repairs. [Integration review](review-python-integration.md) records local checks;
none is Windows CUDA qualification. Re-export the bundle and commit file whenever
source changes; do not reuse the old handoff files.

## Transfer and identify the candidate

The handoff contains `hawa-cuda-candidate.bundle` and `candidate-commit.txt`.
A Git bundle carries the complete candidate history without publishing or merging
on GitHub. Copy both files to the Windows machine. From their directory, use a
new checkout; the commands below never modify an installed Rhino plugin.

Prerequisites: Git, uv, the .NET 10 SDK (test host; plugin targets .NET 7), working
NVIDIA driver/CUDA-capable GPU, network access for pinned dependencies and the
reference oracle. Use PowerShell. Each native command is checked explicitly.

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
$candidate = (Get-Content .\candidate-commit.txt -Raw).Trim()
Invoke-Checked git @('bundle', 'verify', '.\hawa-cuda-candidate.bundle')
Invoke-Checked git @('clone', '-c', 'core.autocrlf=false', '-b', 'codex/python-integration-20261109', '.\hawa-cuda-candidate.bundle', 'hawa-cuda-acceptance')
Set-Location .\hawa-cuda-acceptance
$actual = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actual -ne $candidate) { throw 'Wrong candidate commit' }
if (git status --porcelain) { throw 'Start with a clean candidate checkout' }

Invoke-Checked uv @('sync', '--locked', '--extra', 'test')
$py = (Resolve-Path .\.venv\Scripts\python.exe).Path
Invoke-Checked uv @('pip', 'install', '--python', $py, 'torch==2.8.0+cu128', '--index-url', 'https://download.pytorch.org/whl/cu128', '--no-deps')
$env:PYTHONUTF8 = '1'
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
Remove-Item Env:PYTEST_PLUGINS -ErrorAction SilentlyContinue
Invoke-Checked $py @('scripts/bootstrap_reference.py')

$run = 'results/windows-cuda-merge-' + (Get-Date -Format 'yyyyMMddTHHmmss')
New-Item -ItemType Directory $run | Out-Null
Start-Transcript -Path "$run/transcript.txt"
Invoke-Checked nvidia-smi @()
Invoke-Checked dotnet @('--info')
Invoke-Checked $py @('-c', "import sys,numpy,torch; from hawa.backends import select_backend; assert sys.version_info[:2]==(3,9); assert numpy.__version__=='2.0.2'; assert torch.__version__=='2.8.0+cu128'; b=select_backend('cuda:0'); print(sys.version, numpy.__version__, torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0), b.info())")
Invoke-Checked $py @('-m', 'pip', 'freeze')
```

Do not run another syncing `uv run`/`uv sync` after installing the CUDA wheel: it
can restore the CPU variant. Use `$py` directly. Do not edit, stage, regenerate
reports in tracked directories, switch branches or run another agent in this
checkout during verification. Evidence outputs below are ignored by Git.

## Required headless merge gates

Continue in the same PowerShell session:

```powershell
# Three independent full Hawa runs, portable upstream tests, isolated reference
# parity and all 16 bounded upstream examples on CPU and CUDA.
Invoke-Checked $py @('scripts/verify_cuda.py', '--output', "$run/headless", '--repeats', '3')

# 13 CPU/CUDA pairs: motion invariance, refinement, wall and rotation grids.
Invoke-Checked $py @('scripts/verify_cuda_benchmarks.py', '--output', "$run/benchmarks.json")

# Full measured Python suite + 33 instrumented production-linked state contracts.
Invoke-Checked $py @('tools/function_coverage.py', 'check', '--output', 'docs/function-tests', '--base-ref', 'd9cc3a72d5096b35f0fca920fe9a4357594c315c')
Invoke-Checked $py @('tools/function_coverage.py', 'run', '--output', "$run/function-gate", '--base-ref', 'd9cc3a72d5096b35f0fca920fe9a4357594c315c')

# Complete current compatibility inventory, including all available CUDA rows.
Invoke-Checked $py @('scripts/run_compatibility_matrix.py', '--output', "$run/g6")
Invoke-Checked $py @('scripts/check_compatibility_evidence.py', '--matrix', "$run/g6", '--junit', "$run/function-gate/pytest.xml", '--state-log', "$run/function-gate/state-contracts.log")

# Build both assemblies and a new development ZIP; DO NOT pass --install.
Invoke-Checked $py @('scripts/build_plugin.py', '--output', "$run/package", '--archive', "$run/Hawa-cuda-candidate.zip")

$headless = Get-Content "$run/headless/report.json" -Raw | ConvertFrom-Json
if (-not $headless.full_passed -or -not $headless.full_scope) { throw 'Full headless scope did not pass' }
$hawaRuns = @($headless.stages | Where-Object { $_.name -match '^hawa-[123]$' })
if ($hawaRuns.Count -ne 3) { throw 'Missing full suite repeats' }
foreach ($stage in $hawaRuns) {
    if (-not $stage.passed -or -not $stage.source_unchanged -or $stage.counts.cuda_named -le 0 -or $stage.counts.cuda_skipped -ne 0) {
        throw 'Incomplete or skipped CUDA suite'
    }
}
$benchmarks = Get-Content "$run/benchmarks.json" -Raw | ConvertFrom-Json
if (-not $benchmarks.passed -or -not $benchmarks.source_unchanged -or $benchmarks.results.Count -ne 13) { throw 'Benchmark gate failed' }
$matrix = Get-Content "$run/g6/summary.json" -Raw | ConvertFrom-Json
if (-not $matrix.local_pass -or $matrix.counts.failed -ne 0 -or $matrix.expected_rows -ne $matrix.recorded_rows -or $matrix.sources_changed_during_run) { throw 'G6 failed' }
$blocked = @(Get-Content "$run/g6/rows.jsonl" | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object { $_.status -eq 'blocked' })
if (@($blocked | Where-Object { $_.id -notmatch '/mps$' }).Count -gt 0) { throw 'A non-MPS compatibility row is blocked' }
Invoke-Checked $py @('-c', "import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; assert not any('09-parametric-hull-galapagos.gh' in n for n in z.namelist()); print('ZIP integrity and legacy-09 exclusion passed')", "$run/Hawa-cuda-candidate.zip")
if ((git rev-parse HEAD).Trim() -ne $candidate -or (git status --porcelain)) { throw 'Candidate changed; discard the run' }
Get-FileHash "$run/Hawa-cuda-candidate.zip" -Algorithm SHA256
Stop-Transcript
```

## Acceptance and evidence to return

All commands must exit zero and produce their complete fresh artifacts. Inspect
JUnit/log skip reasons as well as the summaries:

- Each Hawa repeat must exactly match its independently collected IDs, with zero
  failures/errors and zero CUDA skips. Windows MPS skips are expected and remain
  unverified. Do not use the old PR's 204/78 counts as the new inventory.
- Portable upstream scope keeps the explicit native-extension exclusions; inspect
  any remaining skips (unsupported stencil/model and upstream TODO cases). CUDA
  unavailable/device skips are unacceptable on this machine. This run does not
  qualify generated native CUDA extensions.
- Core reference comparisons must include `cpu`, `cpu64` and `cuda:0`; all
  compared checkpoints/fields pass their existing tolerances. No MPS claim.
- Both bounded example inventories contain all 16 entrypoints and their field
  comparisons pass. Keep the original intentional failing-TGV example semantics;
  a 50-step profile is not long-run convergence evidence.
- All 13 benchmark configurations pass without changing thresholds. Retain
  analytic error, performance and memory data even when scalar parity passes.
- Function gate has no new/changed uncovered functions or lost coverage against
  the stated base; 33 state contracts pass. Save its fresh matrix without replacing
  the committed local matrix during these checks.
- G6 has complete expected/recorded rows, zero failures, unchanged sources, and
  no blocked CUDA/CPU rows. MPS-only blocks are expected on Windows, so do not use
  `--release` to disguise that separate hardware limitation.
- Both assemblies build and the ZIP passes integrity. Review any new warning.
  Build success does not qualify installation, Rhino/GH scheduling or UI behavior.

Return the entire `$run` directory (including JUnit, collection/result JSON,
provenance/diffs, comparison arrays, function matrix, G6 rows and logs), candidate
commit and package SHA-256. Keep failed evidence and use a fresh output directory
for each rerun. A later fix requires new evidence for the resulting candidate.

HAWA-001 CPU/MPS PorousMedium disagreement and HAWA-002/006 clean Windows Rhino
installation remain explicit limitations. They are separate from this bounded
headless merge decision. Installing/releasing still requires normal Rhino Quit,
clean embedded CUDA setup and live host lifecycle checks; this runbook does not
approve or perform those actions.
