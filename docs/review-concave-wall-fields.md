# Concave-wall full-field review follow-up — PR #129

Date: November 24, 2026. Reviewer: Codex `openfoam_walls` agent (self-review).
This follow-up changes tests and evidence only; it does not change wall physics.

The earlier CPU/MPS test compared mean speed, which loses direction and local
variation. The revised test retains that original `rtol=5e-4` scalar check and
additionally compares every fluid velocity component and pressure, with identical
fluid masks. CPU-only hosts explicitly skip only the named MPS comparison.
The original q=0.29 CPU 40-step fallback-count, finite-field and mass-drift
checks remain unconditional in the midpoint/stability test. A follow-up review
identified that the initial split accidentally made those checks MPS-dependent;
this final revision restores them. CPU-only focused run: **2 passed, 1 skipped**.

The added field criterion is the existing CPU/accelerator criterion in
`scripts/compare_examples.py`: `rtol=1e-3`, `atol=1e-5` times the field's physical
unit-conversion scale from `scripts/example_worker.py`. It is reused unchanged,
not calibrated from this test's errors. Pressure uses
`convert_density_lu_to_pressure_pu(2) - convert_density_lu_to_pressure_pu(1)`;
velocity uses `convert_velocity_to_pu(1)`.

## Fresh bounded evidence

Python 3.9, PyTorch 2.8.0, macOS Apple Silicon, CPU and MPS FP32; deterministic
14×10×8 L-shaped solid, dx=0.1 m, speed=1 m/s, viscosity=0.05 m²/s,
density=1.225 kg/m³, Mach=0.05, BGK, q=0.29, 40 steps. This is a short
implementation regression, not settled or grid-converged flow.

| Field | Compared values | Maximum absolute difference | rtol | Physical atol | Violations |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fluid velocity components | 3216 | 1.7404556e-5 m/s | 1e-3 | 3.4641016e-4 m/s | 0 |
| Fluid pressure | 1072 | 4.0888786e-4 Pa | 1e-3 | 0.0049 Pa | 0 |

`.venv/bin/python -m pytest tests/test_concave_walls.py -q`: 3 passed,
including the unchanged rest-equilibrium and midpoint-rounding checks.
Ruff on the changed test passes.

A preliminary diagnostic applied pure `rtol=5e-4, atol=0` to every velocity
component. It failed at 210/3216 values, with maximum violating absolute error
8.520059e-6 m/s, primarily at nearly zero components. That was a trial extension
of the previous scalar criterion, not the pre-existing full-field policy. The
failure remains disclosed; neither bitwise parity nor pure-relative field parity
is claimed. No established tolerance was widened.

## Gates and remaining limits

- G0/G1: not applicable to this test-only follow-up; no method or ownership change.
- G2: focused tests pass; full-suite/function-gate results recorded below when run.
- G3: PASS only for the declared bounded full-field comparison. No accuracy,
  long-window stability or universal CPU/MPS parity claim.
- G4: BLOCKED — no live Rhino check; parent integration owns host acceptance.
- G5: not applicable — no package or release produced.
- G6: existing finite matrix not rerun; this adds a bounded device regression
  without changing supported combinations or public nodes.

## Complete headless checks on the follow-up

- Python 3.9 measured full suite: **2849 passed, 87 skipped**; strict headless
  function/line gate **1201 covered functions, zero failures**. The 299
  uninstrumented host functions remain unmeasured. Committed matrix regenerated.
- Linked .NET 10 StateContracts: **156 passed** (Rhino/transport doubles).
- Python 3.12 full suite: **2839 passed, 97 skipped**. Extra skips are the
  production-Python entrypoints; CUDA is unavailable. Existing upstream,
  matplotlib and runpy warnings remain visible in the local logs.
- Evidence directories: `results/function-concave-review-cpu-retained-20261124` and
  `results/concave-review-cpu-retained-py312-20261124.log`. These full suites overlapped other
  CPU mutation/coverage work and available-device tests; no timing/performance
  claim is made. The focused CPU/MPS comparison above ran in a separately
  coordinated short device window.
- No new production lines were changed in this follow-up, so it introduces no
  additional production mutation scope. The original numerical implementation
  and its remaining live-host gate retain their stated scope.
