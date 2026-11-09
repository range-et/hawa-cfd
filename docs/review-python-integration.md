# Python study / main integration

November 9, 2026. Implementer/reviewer: Codex coordinator, self-review.
Scope: combine remote main `65e220e`, reviewed study base `d9cc3a7` and the
missing HAWA-044/045 repairs from `46fe0a6` in an isolated checkout. No source
from the dirty original working tree is overwritten. Latest planning/issue
records are carried forward deliberately.

## Resolution and contracts

The first merge was source-clean. The candidate merge added only the missing
CUDA evidence helpers, runner checks and their tests; KBC's device comparison was
already repaired in main and is preserved. Generated coverage conflicts are
resolved by fresh measurement, not by selecting an old matrix. Historical CUDA
reports remain historical; the Windows handoff requires a new final-commit bundle.
No new numerical tolerance, public node, C# source behavior or installed assembly
change is introduced by resolving this integration.

Baseline policy: remote main has no function-coverage baseline yet. Local checks
use the stricter pre-existing study baseline `d9cc3a7`; hosted CI's initial-adoption
path uses the included unchanged baseline. New functions must be measured and
existing debt remains visible. Final counts and gate results are recorded below.

## Initial focused verification

Own Python 3.9.25 virtual environment, torch 2.8.0, NumPy 2.0.2; actual editable
imports verified inside this checkout. Focused export/refinement/replay/CUDA-tool
suite: 138 passed, 14 matplotlib/pyparsing warnings, 34.09 s. Full native gate,
fresh Docker CPU G6 and development packaging are running/pending. No CUDA or
Rhino claim. Source/test files are frozen during measured checks.

G0/G1: scoped integration contracts reviewed. G2/G5/G6 pending current checks.
G3: numerical acceptance/CPU-MPS PorousMedium failure remains HAWA-001; no new
physical qualification. G4: no live host verification; no host behavior change
attributable to the merge resolution. Release remains blocked on the stated
platform/numerical/host gaps.

Fresh constrained Linux CPU G6 completed: 97,561 passed, zero failed, 4,898
MPS/CUDA rows blocked; all 102,459 rows recorded, unchanged source, 38.48 s.
Image `sha256:6b367745131c89cf349cd005532efe5ac708f871b1758105669406e468e18e93`,
one CPU / 2 GiB, no network, read-only source/root. This is not an MPS/CUDA
matrix pass. Final combined evidence check follows the native suite.

## Final local verification

- Full native function gate: **806 passed, 82 skipped**, 18 warnings (four MRT
  and 14 matplotlib/pyparsing), 151.18 seconds. CUDA is absent; MPS float64 is
  unsupported. **33 state contracts passed**, zero ratchet failures against
  `d9cc3a7`. Matrices regenerated and checked: 334 covered, 129 uncovered,
  630 unmeasured, 58 declarations; historical debt remains explicit.
- Combined Docker-environment checker passes using the fresh Linux CPU G6 and
  native suite/contracts: 54 public nodes, 31 examples, 191 edges. This is mixed
  environment evidence, not a full native-GPU compatibility pass.
- Both development assemblies build with 105 existing CA1416 icon warnings and
  zero errors. ZIP integrity, exclusion of legacy09 and exact packaged source
  equality pass. Nothing installed. Package hash is in the ignored
  `results/integration/package-check.json`.
- G2 passes locally and G6 passes for the declared CPU matrix; unavailable GPU
  rows remain blocked. G5 development build/package checks pass, release blocked.
  G3/host qualification remains limited as above. Hosted CI must pass the actual
  pushed PR head; a local pass is not a hosted result.

Commands: `.venv/bin/python tools/function_coverage.py run --output
results/integration/function-gate --base-ref
origin/codex/python-study-base-20261109`; render/check via the same coverage tool;
`scripts/build_plugin.py --output dist/Hawa-python-integration --archive
dist/Hawa-python-integration.zip`. Detailed logs are in `results/integration/`
and `results/docker-integration/`.

The diff to old remote main also carries the already-developed atmospheric,
shared-view and function-coverage checkpoint; it is larger than the three narrow
issue PRs. Those existing changes retain their earlier reviews and limits.
No fresh Rhino operation or new C# implementation was performed in this task.
Next issue branches stack on this reviewed integration branch until it merges.
