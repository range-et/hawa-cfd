# HAWA-026 — Airfoil dispatcher coverage tranche

November 9, 2026. Author/reviewer: Codex airfoil coverage agent (self-review).
Initial audit base `abe7545`; final integration base `977bb78`; branch `codex/issue-026-coverage`. This is implementation
verification of existing behavior, not a new solver feature or physical validation.

## Scope and acceptance

The integrated function matrix listed `airfoils.dispatch_airfoil` as uncovered;
all seven other inventoried airfoil functions/lambdas already had measured tests.
Existing airfoil tests called helpers directly. New tests enter through public
`plugin.dispatch(op='airfoil')` and exercise all five existing action routes.
No production source, public API, dependency, tolerance, C# code or example changes.
Only the dispatcher's freshly measured baseline entry is eligible for promotion;
HAWA-026 remains open for the rest of the Python/C# inventory.

Assertions fixed before measurement cover default/explicit NACA count and trailing
edge, finite symmetric unit-chord coordinates, known translated/scaled import
coordinates and provenance, polar sorting/Re/Mach, interpolation in degrees,
wing angle units and length-scaling invariants, area/aspect ratio, sign symmetry,
zero-lift offset, forwarded twist/stations/polar, constant profile drag and total
drag composition. Invalid NACA, coordinate, polar, operating angle and wing inputs
must reach their existing validators. Unknown action and missing required field
retain their existing errors. Synthetic polar values are parsing/interpolation
controls, not experimental aerodynamic data. Wing controls check linear attached,
unswept, incompressible implementation behavior; no stall or convergence claim.

Reference behavior is the unchanged source at the base, its documented degree
conversion and dimensional definitions, and independent hand-computed fixture
values/invariants. No dependency or external data/licence change is introduced.
Length similarity uses a factor of ten with area scaling by one hundred; angle
control bounds finite-wing lift by the existing section slope `2*pi/radian`.
Existing tolerances were not relaxed. These are selected controls, not exhaustive
continuous parameter coverage.

## Evidence

Native environment: macOS 27.0.1 arm64, Python 3.9.25, PyTorch 2.8.0, NumPy 2.0.2.
Focused work is CPU NumPy; `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1` and sandbox-local
`TMPDIR=results/issue-026/tmp` bound worker resources and temporary files.

- Focused: `.venv/bin/python -m pytest tests/test_airfoils.py tests/test_airfoil_dispatch.py -q --junitxml=results/issue-026/focused.xml`:
  **29 passed**, no skips/warnings, 0.11 seconds (23 new cases, six existing).
  After merging `977bb78`, repeat `focused-updated-base.xml`: **29 passed**,
  no skips/warnings, 0.23 seconds.
- Seeded fault controls: `results/issue-026/seeded_faults.py` loads modified source
  into fresh subprocess module memory; production files remain unchanged.
  Unmodified control: **23 passed**. Seven targeted mutants each produced exactly
  one test failure and zero collection/test errors: lost count override, lost open
  trailing-edge option, import routed to polar, lost Re/Mach metadata, degrees
  interpreted as radians, lost wing twist, and unknown action accepted. Logs/XML
  and `seeded-fault-results.json` retain exact outcomes. This is a bounded assertion
  sensitivity check, not a general mutation score or proof of correctness.

- Linux CPU focused rerun: **29 passed**, no skips/warnings, 0.09 seconds;
  `results/docker-026/focused.xml` and `.log`. After merging `977bb78`, repeat
  `updated-base.xml`: **29 passed**, no skips/warnings, 0.13 seconds. Python 3.9.25, torch 2.8.0+cpu,
  NumPy 2.0.2 on Linux aarch64; immutable image
  `sha256:6b367745131c89cf349cd005532efe5ac708f871b1758105669406e468e18e93`.
  Docker limits: one CPU, 2 GiB, 256 PIDs, no network, all capabilities dropped,
  no new privileges, read-only root/source, dedicated writable result mount and
  512 MiB temporary filesystem. Ran the same two test files with cache disabled.

- Full native CPU/MPS function gate against `977bb78`:
  `.venv/bin/python tools/function_coverage.py run --output results/issue-026/full-gate --base-ref 977bb78`:
  **833 passed, 82 skipped, 18 warnings**, 157.85 seconds; **33 .NET state
  contracts passed** with Rhino/transport doubles. Skips: 81 CUDA unavailable,
  one unsupported MPS float64 case. Warnings: 14 existing matplotlib/pyparsing
  deprecations and four existing MRT experimental/inefficiency warnings.
  These hardware omissions are not passes; live Rhino was not started.
- Ratchet failures: **zero**. Dispatcher measured **7/7 executable lines,
  10/10 branches**, attributed to all 23 new cases. Its unchanged fingerprint was
  promoted from uncovered to covered only after this report. No other baseline
  entry changed. Current inventory: 337 covered, 126 uncovered, 630 unmeasured,
  58 declarations; remaining debt stays explicit.
- Both committed matrices refreshed from this exact measurement. Checks against
  trusted base `977bb78` and the newly promoted local baseline both pass:
  `results/issue-026/matrix-base-check.log` and `matrix-local-check.log`.
  Baseline JSON is intentionally outside the tool's source/test snapshot; the
  freshness checks still verify all snapshotted inputs without an exemption.

The review-only seed harness is retained under ignored results, with exact
substitutions and fresh subprocess logs. No modified module was written to disk
or used during the full gate. The seed controls predate the integration merge;
`airfoils.py` was unchanged by that merge. Focused native/Linux and the full gate
above are fresh for the final integrated source.

## Gate disposition and limitations

| Gate | Decision | Evidence/reason (same self-reviewer throughout) |
| --- | --- | --- |
| G0 research | PASS | Existing contract, selected invariants, fixture values and exclusions above; no numerical method or dependency added. |
| G1 architecture | PASS | Public dispatch exercised without changing ownership, state, schema or API; no new node. |
| G2 reliability | PASS | Focused native/Linux controls, seven seeded faults, full gate, 33 state contracts and both baseline/matrix checks pass; hardware skips retained. |
| G3 numerical | PASS, scoped | Degree units, dimensions and symmetry controls verify existing linear implementation behavior; no physical validation or engine change. |
| G4 UI/UX | NOT APPLICABLE | Tests only; no host/UI/example change, no live Rhino claim. |
| G5 release | NOT APPLICABLE | No distributable production change or release/package requested; no installation/build claim. |
| G6 compatibility | NOT APPLICABLE | No new combinations, field formats, nodes, shared state or release candidate. Historical G6 evidence is separate; no fresh full G6 run. |

No Windows/CUDA execution, live Rhino scheduling, wind-tunnel reference, long
numerical study or whole-issue closure is claimed. Full-suite hardware skips must
remain explicit. Merge/release decisions remain with the maintainer.

## Rebase onto the merged diagnostic branch

November 9, 2026: rebased onto integration `588bffd`, preserving the domain
and CPU/MPS diagnostic work and both sets of feature/issue records. Regenerated
both matrices from the combined source; no production code or numerical limits
changed. Full native gate: **899 passed, 83 hardware skips, 18 warnings**,
167.78 seconds, **33 state contracts**, zero ratchet failures. Hardware skips
are 82 CUDA-unavailable cases and one unsupported MPS FP64 case.
Inventory: 347 covered, 126 uncovered, 630 unmeasured, 58 declarations.
Trusted-base and local-baseline matrix checks both pass. Evidence:
`results/rebase-588/gate/`. Prior counts above describe earlier branch snapshots.
HAWA-026 remains open beyond the dispatcher; no new host or release claim.
