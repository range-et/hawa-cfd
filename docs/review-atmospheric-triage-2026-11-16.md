# Atmospheric qualification triage — November 16, 2026

**#21, #26 and #27 remain open.** Four fresh bounded CPU experiments reproduce
the qualification gap and narrow the next investigation. No solver, tolerance,
viscosity, node, archive or qualification geometry changed. This is diagnostic
evidence, not a new implemented feature or atmospheric validation.

Author/reviewer: Codex `atmosphere_qualification` agent (self-review).
Tested source: `21bd2056824f84bf4d26dcb559f122a6bed58833`.
Environment: Apple M3 Max, macOS 27.2.1 arm64, Python 3.9.25, Torch 2.8.0,
NumPy 2.0.2, requested/selected CPU, FP32 populations, one OMP/MKL thread.
No installed plugin or package was tested.

The [fixed completion contract](atmospheric-nesting-implementation.md) requires
mean-velocity relative L2 <=5%, fluctuation RMS relative L2 <=10%, Cp RMSE <=0.1
and reference stationarity <=5%. These criteria were retained before execution.
The [machine record](verification-atmospheric-triage-2026-11-16.json) contains
source hashes, exact metrics, per-probe RMS, configuration and artifact hashes.
Full recordings and raw comparison arrays remain in the named local `results/`
directories; those large artifacts are not committed or remotely archived here.
Hashes identify retained artifacts; they do not substitute for their availability.

## Results

All runs use the existing shifted SGS cropped-building harness, U=5 m/s,
nu=1.5e-5 m²/s, density=1.225 kg/m³, Mach=0.05, dx=1 m, seven unchanged probes,
and the existing rough-floor/filter/initial-state transfer. The parent is
32×24×16 cells. The standard child is 20×16×12 at (4.5,4.5,0.5) m. Each analysis
uses the latter half of its recorded window. No ratio-2 or fine-reference run
was performed.

| CPU experiment | Mean error | RMS error | Cp RMSE | Reference stationarity | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| 1000 warmup + 1000 recorded, interval 10 | 0.6868% | 14.0243% | 0.03656 | 2.1416% | FAIL: RMS |
| Same run, interval 2 | 0.6874% | 14.0230% | 0.03624 | 2.1156% | FAIL: RMS |
| 5000 warmup + 5000 recorded, interval 10 | 0.9969% | 3.2889% | 0.00942 | 27.6517% | FAIL: reference stationarity |
| Baseline frozen parent, child outlet +4 cells | 0.6865% | 10.1730% | 0.03676 | 2.1416% | FAIL: RMS; diagnostic geometry only |

The short analysis covers 8.660254–11.547005 s; the longer analysis covers
43.301270–57.735027 s. Runtime was respectively 20.74, 43.45, 100.85 and 7.61 s.
The first three harness commands exited 1 for their recorded numerical failures,
without an execution error. The custom outlet control completed normally and
reported `passed=false`, `full_nesting_passed=false`.

At identical common timestamps, the interval-2 parent velocity **and pressure**
are bitwise equal to interval 10. Comparing the child on those same 51 samples
gives RMS error 14.01975%, versus 14.02430%. Five-times denser capture therefore
does not repair this short-window discrepancy. This does not establish cadence
independence in other flows or windows.

In the baseline, lateral RMS at (22.5,10.5,2.5) m contributes 59.37% of squared
RMS discrepancy, and vertical RMS at (18.5,10.5,2.5) m contributes 18.85%.
The first probe is one cell from the standard child outlet. Moving that outlet
four cells downstream reduces total RMS error to 10.1730%, still above 10%.
This demonstrates domain-placement sensitivity in this case. It does not prove
a particular boundary implementation defect, nor authorize substituting the
larger child into the fixed qualification test.

The longer run illustrates an independent blocker: good child/parent agreement
can coexist with a strongly changing reference. Its low RMS error is not a
qualification pass. The explicit diagnostic flag permitted comparison only;
the reference gate still failed.

## Reproduction

From the tested source, provision `.venv` with
`uv sync --frozen --python 3.9 --extra test`. Use fresh output directories:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/verify_neutral_nesting.py --output results/nesting-cpu-baseline-21bd205 --device cpu --warmup 1000 --steps 1000 --interval 10 --ratios 1 --diagnostic-nonstationary-reference
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/verify_neutral_nesting.py --output results/nesting-cpu-cadence2-21bd205 --device cpu --warmup 1000 --steps 1000 --interval 2 --ratios 1 --diagnostic-nonstationary-reference
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python scripts/verify_neutral_nesting.py --output results/nesting-cpu-window5000-21bd205 --device cpu --warmup 5000 --steps 5000 --interval 10 --ratios 1 --diagnostic-nonstationary-reference
```

The outlet control reused the baseline `reference.json` through `load_reference`,
checking its source/frame identities before and after. It used the same `case`,
`capture`, `create_recording`, `series` and `metrics` functions, with only child
shape changed to `[24,16,12]`; dx=1 and origin `[4.5,4.5,0.5]` were unchanged.
Child warmup=0, steps=1000, interval=10, CPU. Both source and child quality were
`within-tested-envelope`; their absolute clocks matched to 1e-10 s. The
temporary driver initially rejected a relative module path before running any
solver; the corrected driver used the resolved harness path and a fresh
`results/nesting-cpu-outlet-plus4-v2-21bd205` directory.

`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m pytest
tests/test_neutral_nesting_verification.py -q`: **49 passed in 21.65 s**.
No production/test function changed; no fresh full-suite, function-coverage,
mutation, build, Rhino, MPS or CUDA pass is claimed.

## Gate disposition and next work

| Gate | Reviewer | Status | Evidence / scope |
| --- | --- | --- | --- |
| G0 research | Codex, self-review | PASS | Existing completion criteria retained; no new numerical method or external reference imported. |
| G1 architecture | Codex, self-review | NOT APPLICABLE | Evidence-only change; no interface/state ownership change. |
| G2 reliability | Codex, self-review | PASS | Scoped harness regression suite: 49 tests; frozen source/frame identity checked. No code change or full-suite claim. |
| G3 numerical physics | Codex, self-review | FAIL | Short-window RMS and longer-window reference stationarity fail; no atmospheric qualification. |
| G4 UI/UX | Codex, self-review | NOT APPLICABLE | No host/example/UI change or fresh live-host claim. |
| G5 release/integration | unassigned | BLOCKED | No release or package tested; ready PR, CI and Greptile review remain separate. |
| G6 compatibility | Codex, self-review | NOT APPLICABLE | No changed contract, public node or example inventory. |

Owner for next investigation: atmospheric work lane / maintainer. First hold a
stationary frozen parent and common timestamps fixed while varying downstream
clearance and examining boundary-adjacent velocity/strain and mass-budget errors.
Distinguish domain sensitivity from a reproduced reconstruction defect before
changing solver code. A justified repair then needs the unchanged standard-child
test, longer stationary windows, ratio-2/fine-reference and device comparisons.
The broader #27 stationarity/TKE/grid criteria and #21 delivery contract remain
independent; none can be closed by these four CPU diagnostics.
