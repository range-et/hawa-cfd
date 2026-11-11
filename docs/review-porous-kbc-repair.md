# HAWA-001: KBC repair for devices without FP64

November 10, 2026. Author: Amp agent working on issue #11, branch
`codex/issue-011-kbc-conditioning`. Self-reviewed. The native Mac runs were done
by a separate coordinating agent on the user's Mac. This is a candidate repair
for [#11](https://github.com/range-et/hawa-cfd/issues/11), not a release. It
builds on the bounded diagnosis and the
existing CPU/CUDA precision repair, which this change leaves untouched.

## Question, criteria and scope

The question: why does PorousMedium (512×512, 50 steps, FP32 storage) disagree
between CPU and MPS, and can the collision be repaired without widening
tolerances?

The criteria are unchanged and were fixed before measurement. Populations,
density, physical velocity and physical pressure use `rtol=1e-3` and
`atol=1e-5`, with atol scaled by the velocity (34.64) or pressure (400)
conversion factor. In the repeated-cell diagnostic, identical inputs must give
identical outputs at every array shape.

Changed production code: only `vendor/lettuce/lettuce/ext/_collision/kbc_collision.py`.
- FP32 storage on a device without FP64 (MPS) with Lettuce's quadratic
  equilibrium now uses `_collide_compensated`.
- CPU and CUDA keep their FP64-intermediate path.
- FP64 storage and any other equilibrium keep the original kernel.

Excluded: Hawa solver contexts and storage (owned by #13), every other
collision, MLX, and any CPU fallback. Physical validation and convergence over
the full duration are also out of scope.

## Root cause

All CPU tests here ran in a Linux x64 orb with Python 3.9.25, PyTorch
2.8.0+cpu and NumPy 2.0.2. Calling the KBC kernel directly in FP32 on CPU (the
same arithmetic MPS runs) reproduces the original 50-step comparison against
the default CPU path. The result is f 7.73e-4, ρ 6.06e-4, u 0.0272 and p 0.242,
against 7.72e-4, 6.06e-4, 0.0272 and 0.242 on real CPU/MPS. The disagreement
is FP32 collision arithmetic. Streaming and boundaries do not contribute.

KBC computes γ = 1/β − (2 − 1/β)·⟨Δs,Δh⟩/⟨Δh,Δh⟩. With τ = 0.50098 that is
about 1 − r, where the ratio r is close to 1, so γ needs r to about 1e-5. In
plain FP32 three errors exceed that:
- The equilibrium is rounded to ulp(feq) ≈ 1e-8, while the higher-order residual
  Δh is only 1e-5 to 1e-4.
- Δs subtracts two shear estimates of about 0.33 each.
- Δh = fneq − Δs also absorbs FP32 noise in the residual's conserved moments,
  which are zero in exact arithmetic.

In the frozen cell, γ is +0.0016 in FP64 and +0.0053 in plain FP32. On the
step-50 field, plain FP32 differs from the correctly rounded FP64-intermediate
output in 83% of populations, by up to about 150 ulp. It also biases mass by
+1.2e-8 per cell per step. Reduction order on MPS then pushes the frozen cell
below zero at 512×512, where the inherited reset sets γ = 2.

## Candidates and why bit-level agreement is required

This trajectory amplifies tiny differences. Adding unbiased ±1-ulp noise to
the reference collision output gave these results:
- 50% of populations perturbed each step: 3 of 4 seeds failed the original criteria.
- 0.2% of populations: 4 of 6 seeds failed.
- 0.001% of populations: 4 of 4 seeds passed.

Full FP64 storage on CPU also fails against the FP32 CPU reference (u 8.0e-4,
p 0.0124). The failures come from a few cells near γ = 0 whose reset depends on
a 1-ulp input difference.

A conditioning change that only "improves" FP32 therefore still fails. MPS has
to reproduce the CPU's correctly rounded FP32 output in almost every
population. Scratch candidates on the CPU proxy:

| Candidate (scratch) | Populations ≠ FP64-rounded | Proxy f / u / p | Criteria |
| --- | ---: | --- | --- |
| Plain FP32 (current MPS) | 83.4% | 7.73e-4 / 0.0272 / 0.242 | FAIL |
| A: moment-space Δs/Δh from FP32 fneq | 81.8% | 5.24e-4 / 0.0101 / 0.218 | FAIL |
| B: + compensated linear equilibrium | 1.71% | 1.01e-4 / 0.0035 / 0.040 | FAIL |
| C: + compensated quadratic equilibrium | 0.62% | 1.01e-4 / 0.0035 / 0.040 | FAIL |
| D: + double-float Δs/Δh and update | 0.17% | 6.2e-6 / 1.6e-4 / 5.4e-3 | pass (seed-like) |
| **Adopted: D + double-float stabilizer** | **0.0000%** | **1.8e-7 / 6.7e-6 / 9.5e-5** | **PASS** |

## Adopted method

`_collide_compensated` evaluates the same KBC decomposition in unevaluated FP32
pairs (hi + lo). It uses Knuth's TwoSum and Dekker's TwoProduct, with splitter
2¹²+1, and derives div and sum from those.
- ρ and j are compensated sums of the stored FP32 populations.
- feq = w(ρ + e·j/cs² + ((e·j)²/(2cs⁴) − j·j/(2cs²))/ρ) is computed in pairs.
  The weights and the constants derived from cs are pairs of the FP64 values.
- An exact separable raw-moment transform on the 3^d velocity grid splits the
  residual into second-order moments (Δs) and third/fourth-order moments (Δh).
  The inverse uses only ±1 and ½ coefficients.
- The sums, the ratio, γ and the update are computed in pairs and rounded to
  FP32 once.
- The near-zero guard, the non-finite handling and the inherited negative reset
  are unchanged.

Δs and Δh carry no mass or momentum by construction, and no tolerance or
threshold changed. The method needs IEEE-rounded FP32 operations without FMA
contraction. On MPS this was measured, not assumed (see below).

## Verification

Linux CPU (orb):
- On random near-equilibrium D2Q9 32² and D3Q27 8³ fields, the compensated
  kernel is bitwise equal to the rounded FP64-intermediate kernel. Plain FP32
  differs in more than half of the values.
- The frozen cell is bitwise equal at sizes 1, 8 and 64.
- On the step-50 field, 0.0000% of populations differ. The CPU proxy at the
  original criteria passes with f 1.8e-7, u 6.7e-6, p 9.5e-5.
- Vendored upstream KBC tests: 12 passed, 78 skipped (CUDA or unsupported
  stencils), 406 deselected.

Native Mac (agent-run): MacBook Pro Mac15,8, M3 Max, macOS 27.0.1, Python
3.9.25, PyTorch 2.8.0, MPS. Candidate commit `71bb6fc`, fresh worktree and venv.
- Focused tests: 40 passed, 6 CUDA skips. The passes include TwoSum/TwoProduct
  exactness on MPS and MPS == CPU bitwise at 1, 8, 32 and 512.
- Diagnostic: CPU and MPS both `completed=true, passed=true`. At every size the
  MPS public output exactly matches the FP64 reference. The raw FP32 stages
  still show the historical 512² reset in all 262,144 cells.
- **Original PorousMedium CPU/MPS, 50 steps: PASS**, with f 3.28e-7, ρ 3.58e-7,
  u 1.32e-5 and p 1.43e-4.
- All 16 upstream example entrypoints pass on both devices, and parity is
  16/16. The other seven KBC examples are included.

The Mac results above are for `71bb6fc`. Later commits only restructure the
kernel and add tests: the compensated sums are now sequential and bounded,
`torch.where` takes scalars, and the redundant placeholder denominator is gone.
On CPU, final outputs are bitwise identical to `71bb6fc` on the step-50 field
and in the proxy. A batched MPS rerun of the final head is queued in
[#53](https://github.com/range-et/hawa-cfd/issues/53).

Cost: one 512² D2Q9 collision on MPS takes about 49 ms, against 6.8–7.7 ms for
plain FP32 (about 7×). The whole 50-step PorousMedium worker took 4.8 s on MPS
and 5.4 s on CPU. On the 2-core Linux CPU, the CPU FP64-intermediate path costs
86 ms per collision and the compensated kernel (only exercised in tests there)
about 0.9 s. Temporary memory is several pair tensors of size q×grid. Hawa's own
solvers do not use KBC; this affects Lettuce KBC examples on MPS.

## Tests, coverage and mutation

`tests/test_kbc_precision.py` alone gives 100% line and branch coverage of
`kbc_collision.py` (236 statements, 34 branches; coverage.py, CPU). Vendor code
is outside the first-party function gate, so this is a scoped run. The tests
cover:
- bitwise equality with the rounded FP64 kernel (D2Q9 and D3Q27, the frozen
  cell at every shape, the degenerate guard and NaN isolation);
- TwoSum/TwoProduct exactness;
- the dispatch contract for MPS/meta/FP64/CPU/CUDA, using spies and stand-in
  device tensors;
- density scaling of the storage guard in both kernels;
- initialization, unsupported stencils and exact messages.

The diagnostic adds a `compensated_vs_reference` row. It fails independently
when only the double-float kernel disagrees, and its entry point is tested.

Mutation testing used mutmut 2.4.5 through `tools/mutation/run_kbc.sh`, with
CUDA/MPS cases deselected by name. Results:
- `kbc_collision.py`, patch mode over the lines this PR changes relative to base
  `f9a3a13`: **211 mutants, 206 killed, 5 reviewed survivors, 0
  timeouts/errors/suspicious**. The survivors are an equivalent Dekker splitter
  (4098), an equivalent isfinite(low part) check, and three exact-boundary or
  unreachable-window threshold comparisons inherited from Lettuce. Diffs and
  reasons are in `tools/mutation/kbc-collision-policy.json`.
- `scripts/diagnose_kbc_parity.py`, the whole script (it is new to main with
  this PR): **306 mutants, 298 killed, 8 reviewed survivors, 0
  timeouts/suspicious**. Five are equivalent: the Taylor-Green constructor
  arguments that `make_flow` overwrites (4), and `gamma <= 1e-15`, which can
  never equal 1e-15 because a stabilizer near zero is a multiple of 2⁻⁵² (FP64)
  or 2⁻²³ (FP32). One is equivalent content: JSON indentation. Two are
  **collection errors**, not kills and not equivalents: they break the import,
  and mutmut 2.4.5 counts only pytest exit 1 as killed. Diffs and reasons are in
  `tools/mutation/kbc-diagnostic-policy.json`.

The first whole-script run (PR #59's study on main found 82 of 300 surviving)
led to new contract tests. They cover the criterion constants and size bounds,
the exact near-zero guard equality and the reachable reset window
[1e-15, 2e-15) on FP64 cells, unchanged-input checks in the inspection and in the
study, fail-closed evidence and reports, argument parsing and exact messages.
CPU-run tests no longer carry `cuda`/`mps` in their ids, which had made the
mutation selector skip them.

Exploratory collision runs found loop-timeout mutants in a pairwise sum and
equivalent index mutants. The source was restructured to remove them, and the
final runs are fresh. Whole-module mutation of the vendored file is out of scope.


## Gates and evidence

| Gate | Reviewer | Decision | Evidence and limits |
| --- | --- | --- | --- |
| G0 | Amp agent, self-review | PASS | Diagnosis, Lettuce KBC source at 88a6559, standard TwoSum/TwoProduct; criteria unchanged |
| G1 | Amp agent, self-review | PASS | Dispatch contract tested; CPU/CUDA/FP64/non-quadratic paths unchanged; no Hawa state change |
| G2 | Amp agent, self-review | PASS locally | Function gate, strict headless check, scoped 100% kbc_collision.py coverage, targeted mutation policies |
| G3 | Amp agent; Mac run by coordinator | PASS for original CPU/MPS criteria on one Mac | Single machine/OS; a bounded 50-step comparison, not convergence or physical validation |
| G4 | — | NOT APPLICABLE | No UI, node or host change |
| G5 | — | BLOCKED | Not merged, packaged or installed |
| G6 | — | NOT APPLICABLE | No node, field format or shared-state change |

CUDA: the CPU/CUDA FP64-intermediate path is unchanged by this diff. A CUDA
regression run on `b66cb59` (Windows 11, RTX 5070 Ti, PyTorch 2.8.0+cu128,
[#52](https://github.com/range-et/hawa-cfd/issues/52), results on
[#11](https://github.com/range-et/hawa-cfd/issues/11)) passed: focused tests
50 passed with 0 CUDA skips, the diagnostic passed, PorousMedium CPU/CUDA at the
original criteria passed (f 1.79e-7, ρ 4.77e-7, u 1.05e-5, p 1.93e-4), and
16/16 example parity passed. CUDA output for PorousMedium was bitwise equal to
main's. Later commits do not change `vendor/`, `src/` or the diagnostic script;
they add tests, mutation tooling, docs and merges of main.

Remaining before #11 closes: maintainer review and merge, then the batched MPS
round on the merged commit ([#53](https://github.com/range-et/hawa-cfd/issues/53)).
Other Apple GPUs and macOS versions are not covered.
