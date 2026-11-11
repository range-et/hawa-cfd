# HAWA-004 boundary reflection, reversal and cut-face qualification

Tracking: [range-et/hawa-cfd#14](https://github.com/range-et/hawa-cfd/issues/14).
Branch `codex/hawa-004-boundary-qualification`, from
`origin/codex/python-integration-20261109` at `f9a3a13`, with `origin/main`
merged in. Development verification only: Linux x64 orb, CPU only. **No MPS
device ran here.** The FP32 harness rows still have to run on a Mac in the
batched MPS session ([#53](https://github.com/range-et/hawa-cfd/issues/53)).
CUDA ran an early pre-merge check on `1ead04d` (RTX 5070 Ti): all FP32 rows
were within the declared bounds, with the same decisions as CPU FP64
([results](https://github.com/range-et/hawa-cfd/issues/14#issuecomment-6781110349)). The qualifying CUDA run on the merge commit is
[#52](https://github.com/range-et/hawa-cfd/issues/52). Author and every review
pass: Amp agent (self-review). No independent reviewer.

## Protocol and acceptance criteria (fixed before measurement)

These were written and committed before the measurement harness first ran. Changing a
criterion after a run would need a new, dated entry that keeps the original
result. Systems:

- **S**: neutral external mode, `shifted-links-v1`, shifted storage,
  `shifted-regularized-sgs-v1`. Rough floor impulse set to zero (specular
  halfway floor) unless stated otherwise, so the open faces are isolated.
- **N**: general boundaries, `hawa-nee-v1`, full-node NEE.

Precision: CPU64 (`torch.float64`) is the primary measurement. Rows marked FP32
repeat the case at production storage precision on CPU with the same criterion.
Reference: an enlarged domain with the same upstream faces and geometry, extended
downstream (and laterally for corner cases) far enough that its own exit
disturbances cannot reach the compared region during the window. The harness
computes and asserts this causality bound for acoustic cases. Convective cases
cannot exclude every reference-exit acoustic return; this is recorded as a limit.
Comparisons use every fluid node of the small domain, including boundary nodes,
at equal step counts (equal physical time). Metrics are maxima over samples taken
every 10 steps through the window unless stated.

| ID | Case | Metric | Criterion |
| --- | --- | --- | --- |
| A1-S / A1-N | Right-running planar Gaussian acoustic pulse (density amplitude ε=1e-3, σ=4 cells; matching u'=c_s δρ) normally incident on the open X+ face; uniform mean flow; transverse periodic/specular faces; Ls=64; window until the reflected wave has crossed back to the inlet region | R = max \|δρ_small − δρ_ref\| / ε | R ≤ 0.10 |
| A1-S FP32 | As A1-S, FP32 storage | same | R ≤ 0.10 |
| A1-S fine | As A1-S at 2× resolution (σ=8, Ls=128) | same | R ≤ 0.10 |
| A2-S / A2-N | Left-running pulse into the velocity inflow face | same | Reported only. Velocity Dirichlet faces are expected to reflect acoustics (\|R\|≈1); no nonreflection claim for inflow faces |
| V1-S / V1-N | Taylor vortex (axis Z, R=5 cells, peak V=0.5U, consistent incompressible pressure) convected by U through the open X+ face; Y periodic; Ls=64; window until the centre is 6R past the face | E = max \|u_small − u_ref\| / V | E ≤ 0.10 |
| V1-S FP32 | As V1-S, FP32 | same | E ≤ 0.10 |
| V1-S fine | As V1-S at 2× resolution (R=10, Ls=128) | same | E ≤ 0.10 |
| V2-S | Strong vortex V=1.5U: local backflow through the open face | same | Backflow-vortex exit is claimed only if E ≤ 0.10; otherwise listed unsupported |
| C1-S | Uniform oblique flow (0.6, 0.8)·5 m/s; X−/Y− velocity, X+/Y+ open, corners shared; 200 steps | max \|u − U\|; CPU64 per-step mass budget residual | ≤ 3e-5 m/s (CPU64 and FP32); residual < 1e-10 lattice units |
| C2-S | Taylor vortex (V=0.5U) convected diagonally into the X+/Y+ open corner; reference extended in +X and +Y | E as V1 | E ≤ 0.10 |
| R1-S | Physically forced reversal: both X faces open with `backflow_mode: pressure`, Δp=20 Pa (X− high), initial uniform −1 m/s with the consistent linear pressure; run to 2T, T = 2ρL/Δp (−1 → +3 m/s). Analytic plug flow u(t)=−1+Δp t/(ρL), L=(Nx−1)dx | mean-u error / 1 m/s; node max error / 1 m/s; both faces must report incoming links during the run; CPU64 mass residual | ≤ 0.02; ≤ 0.05; incoming observed on X+ early and X− late; < 1e-10 |
| R1-S fine / FP32 | R1 at dx/2; R1 in FP32 (mass residual not applied in FP32) | same | same |
| K1-S | Cut-face accuracy: laminar Re_W=100 (W=6 m, U=5 m/s, ν=0.3 m²/s, Cs=0) long block, 6 m high in a 12 m domain, leading edge 2W upstream of the open X+ face it crosses; reference domain continues the block to Nx=80. Equal physical time ≈4 reference flow-throughs | relative L2 and Linf/U of velocity: interior (x ≤ Ls−7) and near-face band (last 6 planes); settledness = relative change over the last 1000 steps; backflow = incoming open links at the end | interior L2 ≤ 0.02, Linf ≤ 0.05; band L2 ≤ 0.05, Linf ≤ 0.10; settledness ≤ 0.01 (else INCONCLUSIVE); backflow > 0 required for a separated-cut claim |
| K1-N | Same block, full height, Z periodic, through the N open X+ face | same | same |

Supported combinations are claimed only for rows that pass. A failure blocks the
claim it contradicts. Repairs are rerun against the unchanged criterion, and the
original failing result stays in this record.

Out of scope here: physical atmospheric validation, turbulence statistics,
inflow-face cut accuracy (needs mapped parent data), curved/narrow-gap cut
bodies, active rough-floor/open-edge accuracy beyond mass budgets, and N adjacent
open faces (rejected by contract).

## Environment and reproduction

Linux x86_64 orb, 2 CPUs. Python 3.9.25, PyTorch 2.8.0+cpu, NumPy 2.0.2. Every
row ran on CPU; CPU64 unless marked FP32. Run 1 is the unrepaired baseline at
`60daf11`. Run 2 has the restructured harness and the first repair at
`54987f5`. Run 3 has the time-consistent pressure face at `4893429`. Local raw
reports: `results/hawa-004/run{1,2,3}-*/`.

```sh
.venv/bin/python scripts/verify_boundary_reflection.py --output results/NEW/cpu.json
.venv/bin/python scripts/verify_boundary_reflection.py --output results/NEW/mps.json --device mps   # FP32 rows only
```

## Results

Run 3 at `4893429` unless stated. Velocity-mode rows are bit-identical to run 2.
Run 4 at `792f0cd` (final production source) repeated R1-S, R1-S-fine,
R1-S-fp32, C1-S, C1-S-fp32 and V2-S pressure backflow; R1 values are identical
to run 3 (mean 0.00418 / 0.00419 / 0.00415, node 0.00704 / 0.00715 / 0.00702 m/s).

| Row | Measured | Criterion | Decision |
| --- | --- | --- | --- |
| A1-S | R = 0.976 (FP32 0.976; 2× resolution 0.955) | ≤ 0.10 | **FAIL** |
| A1-N | R = 1.234 (FP32 1.235) | ≤ 0.10 | **FAIL** |
| A2-S / A2-N | R = 0.895 / 0.963 | reported only | Inflow faces reflect, as expected |
| V1-S | E = 0.221 (FP32 0.221; 2× resolution 0.204, run 5 at `abf2292`) | ≤ 0.10 | **FAIL** |
| V1-N | E = 0.527 (FP32 0.527) | ≤ 0.10 | **FAIL** |
| V2-S | E = 0.869; no incoming link ever recorded | claim only if ≤ 0.10 | **FAIL**, unsupported |
| V2-S pressure backflow | E = 1.422; 160 incoming links (unrepaired 0.869, first repair 1.382) | claim only if ≤ 0.10 | **FAIL**, unsupported |
| C1-S | 2.0e-14 m/s, residual 1.3e-15 (FP32 1.9e-5 m/s) | ≤ 3e-5 m/s; < 1e-10 | **PASS** |
| C2-S | E = 1.243 (FP32 1.243); peak at the corner node (diagnostic below) | ≤ 0.10 | **FAIL** |
| R1-S, declared node reference | mean 0.0042, node 0.0070 m/s; both branches; residual < 1e-15. dx/2: 0.0042 / 0.0072. FP32: 0.0042 / 0.0070 | ≤ 0.02; ≤ 0.05 | **PASS** after both repairs |
| R1-S, run 2 (first repair, snapshot donor speed) | mean 0.066 / 0.036 m/s at dx and dx/2; node 0.071 / 0.039 | ≤ 0.02; ≤ 0.05 | **FAIL**; traced to the solver (below) |
| R1-S, run 1, unrepaired | mean 3.07 m/s; X− never became an inflow face | ≤ 0.02 | **FAIL** |
| K1-S | interior L2 0.0017, Linf 0.018; band L2 0.012, Linf 0.070; settled 3.2e-4; no incoming links at the face (FP32 the same to 4 digits) | see protocol | **PASS** for the attached cut face; no separated-cut claim |
| K1-N | interior L2 0.217; settled change 0.181 (FP32 the same; runs 2 and 3 identical) | settled ≤ 0.01 | **INCONCLUSIVE** (not settled) |

## Device comparison (declared before any device run)

Declared on November 10, 2026, before any MPS or CUDA run, under the device
qualification protocol in [the workflow](github-issues.md). Each device runs
the `-fp32` rows on one shared commit and is compared with the CPU FP64 row
above, not with another device. Class: `bounded`.

| Rows | Bound against CPU FP64 |
| --- | --- |
| All | Same decision (PASS, FAIL or INCONCLUSIVE) |
| A1-S/N (R), V1-S/N and C2-S (E) | absolute difference ≤ 0.01 |
| R1-S mean and node error | absolute difference ≤ 0.001 m/s |
| C1-S | velocity error ≤ 3e-5 m/s (the row criterion); mass residual ≤ 1e-6 lu |
| K1-S/N interior and band L2/Linf, settled change | absolute difference ≤ 0.002 each; K1-N settled change within 0.01 |

CPU FP32 sits inside every bound (largest differences: A1-N R 1.5e-3, other R/E ≤ 3e-5, R1
2.6e-5 m/s, K1 8e-5, C1 mass 4.2e-7 lu).

## Findings and disposition

- **Pressure-backflow faces could not reverse. Fixed.** On `backflow_mode:
  pressure` faces, the outgoing branch convected the normal velocity at the
  node's own speed. That stalls at u_n=0, so the face behaved like a slowly
  relaxing velocity condition. R1 never reversed: 3.07 m/s error, with a
  one-cell pressure jump of 4.2 Pa behind the 20 Pa reference at step 50.
- **Pressure faces sat half a cell outside their nodes. Fixed.** After the
  first repair, R1 still failed against the declared node reference (0.066 m/s),
  and the error halved with dx. The boundary node took the donor's normal speed
  from the one-step-old pre-stream snapshot. In an accelerating flow that lags
  by a, so the FD stress at the node read a one-sided strain
  (−3u₀+4u₁−u₂)/2 = 3a/2. The resulting Π^neq_xx = −τa is half a cell of pressure
  gradient at τ≈½. Measured at step 300: boundary Π^neq_xx = −4.39e−6 against
  ≈1e−7 in the interior; the face-link momentum flux was 4.5e−6 short, against
  half the per-cell flux gradient of 4.35e−6. Pressure faces now take the
  donor's current, post-stream normal speed in both directions. A donor on
  another exterior face, whose missing links are not yet rebuilt, keeps the
  complete snapshot. Tangential components are still convected. Regressions:
  `test_outgoing_open_normal_speed_follows_backflow_mode` (X+ and Y− outlets) and
  `test_pressure_face_corner_donors_use_complete_snapshot` fail without the
  respective change; the harness R1 test fails on both earlier versions.
  Default faces are unchanged.
- **Withdrawn amendment.** A cell-centred R1 reference (L = Nx·dx), adopted
  after run 1, was withdrawn at the user's direction before this record was
  merged. The declared node reference above is unchanged from `a1aa352`, and
  R1 is judged only against it.
- **Default open faces cannot let local outflow reverse. Open:
  [#55](https://github.com/range-et/hawa-cfd/issues/55).** In V2, the face
  minimum stays at +0.27U while the vortex's −0.5U backflow is suppressed before
  it arrives. Applying the donor speed to default faces raised V1-S to 0.55, so
  that repair was rejected for this mode.
- **Acoustic reflection.** Both open methods hold exterior pressure as a
  Dirichlet value, so a normally incident pulse reflects with order-one
  amplitude (S 0.98, N 1.23). No nonreflection claim is made or supported.
- **Vortex exit.** The V1-S error is concentrated in the boundary-node layer
  (0.21 at the face plane, 0.08 one cell in, 0.012 for x < 52). Interior
  results more than about 12 cells from the face are much better, but the
  declared all-node criterion fails, and doubling the resolution only lowers
  it to 0.204. N is worse (0.53).
- **Rejected candidates, CPU64, against unchanged criteria:** face-mean
  transport speed (V1 0.12, V2 0.89, A1 0.98); LODI characteristic outflow
  without transverse terms (A1 0.020, V1 0.91); the same with the incoming
  characteristic convected (A1 0.019, V1 0.18). None passes both acoustic and
  vortex rows; a method change is tracked in #55.
- **Open/open corner amplifies vortex exit. Open:
  [#60](https://github.com/range-et/hawa-cfd/issues/60).** C2-S fails at
  1.24. A diagnostic rerun of the same case (not a criterion row) put the
  peak at the X+/Y+ corner node: at step 1440, 1.22 there, 0.47 / 0.43 on the
  X+ / Y+ faces and 0.14 in the interior away from the last four cells. The
  interior error alone still exceeds 0.10, so a corner-only repair would not
  pass C2. Uniform flow through the same corner (C1) is exact.
- **K1-N did not settle.** A 2D block behind reflecting inflow and outflow
  faces at τ−½ = 0.0052 still changed 18% over the last 1000 steps.
  Undamped acoustic sloshing is a hypothesis; it was not verified here.

All failing and inconclusive reflection rows (A1, V1, V2, C2 and K1-N) are
collected, with their evidence, in
[#60](https://github.com/range-et/hawa-cfd/issues/60). The maintainer
approved the re-scope, as recorded on #14: C1, R1 and K1-S passed; A1, V1,
V2, C2 and K1-N move to #60, the single follow-up; #55 stays separate. #14
closes only after this PR merges and the MPS and CUDA runs on the merged
commit qualify.

## Supported combinations after this work

| Combination | Status |
| --- | --- |
| S uniform oblique flow through velocity/open corners | Verified (C1, CPU64 and FP32) |
| S pressure-driven reversal through two `backflow_mode: pressure` faces | Verified (R1, declared node reference, CPU64 and FP32, dx and dx/2) |
| S attached flow beside a cropped body at an open face | Verified at Re_W=100 (K1-S) |
| S/N acoustic transparency of open faces | Not supported; measured reflection ≈1 |
| S/N vortex exit at the declared 10% all-node accuracy | Not supported (0.22 / 0.53) |
| S local backflow through a default open face | Not supported (#55) |
| S non-uniform (vortex) outflow through an open/open corner | Not supported (1.24; #60) |
| S backflow vortex with pressure backflow | Not supported (1.42) |
| N cut-face accuracy | Inconclusive (not settled) |
| N adjacent open faces | Rejected by contract (unchanged) |

## Tests, coverage and mutation

- New and changed tests: `tests/test_boundary_reflection.py` (harness protocol,
  metrics and small real runs; 100% of harness lines),
  `tests/test_neutral_external.py` (pressure/velocity faces at X+ and Y− outlets;
  corner donors), `tests/test_mutation_policy.py` (several control files), and
  `tests/test_tooling_entrypoints.py` (KBC diagnostic entrypoint, which the
  strict check found uncovered).
- Function gate after merging `origin/main` at `8eec667` (merge `6a09a71`;
  `tools/function_coverage.py run`): 1,439 passed, 170 skipped (all skips are
  MPS or CUDA hardware unavailable); functions 550 covered, 58 declarations,
  590 unmeasured C# host functions. `check --strict --coverage-scope headless`
  on the run directory: exit 0, `failures: []`. `check --base-ref origin/main`:
  exit 0, `failures: []`. The committed matrix was regenerated from that run
  and `check --output docs/function-tests --base-ref origin/main` passes.
  Earlier gates at `792f0cd` and after merging `c6e57ad` also passed.
- Mutation (mutmut 2.4.5, whatthepatch 1.0.7): the PR-scoped study mutates only
  lines changed against `origin/main` (`f29fe01`) in `neutral_external.py` and
  `check_results.py`, with `test_mutation_policy.py` and
  `test_neutral_external.py`. Result: **34 mutants, 33 killed, 1 reviewed
  equivalent, 0 timeouts, 0 errors, 0 skips**; runtime a few minutes. Survivor
  #29 changes `split('::', 1)[0]` to `split('::', 2)[0]`. It is equivalent
  because the first field is identical. An earlier pass also found two
  equivalent survivors (an unused `get` default and `keepdim`); both arguments
  were removed. The policy is `tools/mutation/boundary-reflection-policy.json`.
- Not in mutation scope: the reflection harness (`scripts/verify_boundary_reflection.py`),
  under the minutes budget for this PR. It is line-covered by asserting tests. A
  partial wider discovery pass was stopped and is not counted. The CPU/MPS
  comparison test is deselected in the study; it belongs to #53.

## Gate decisions

All passes by the same Amp agent; no independent reviewer.

| Gate | Decision | Evidence and limits |
| --- | --- | --- |
| G0 research | PASS for the scoped verification | Criteria committed in `a1aa352` before the first run; enlarged-domain and analytic references; one withdrawn amendment, recorded above |
| G1 architecture | PASS | One production change inside the existing open-face writer; no new node, schema, contract or archive change; default faces unchanged |
| G2 reliability | PASS for headless scope | Strict headless and base-ref checks pass; PR-scoped mutation 33 killed, 1 reviewed equivalent. No live Rhino or device run |
| G3 numerical | PASS for C1, R1 and K1-S; FAIL for A1, V1, V2 and C2; INCONCLUSIVE for K1-N | Rows above. No nonreflection, vortex-exit, backflow-vortex or N cut-face claim |
| G4 UI/UX and examples | NOT APPLICABLE / BLOCKED | No GH or UI change. Live Rhino examples were not run here; pressure-backflow behavior changes for GH cases that use it |
| G5 integration | BLOCKED for release | CPU here. CUDA pre-merge check on `1ead04d` within all bounds (max A1-N ΔR 5.1e-4; `--require-cuda` 64 passed); qualifying run on the merge commit in #52. MPS FP32 rows go to #53 |
| G6 compatibility | NOT APPLICABLE | No new node, enum option or accepted combination; open-face contracts unchanged |
