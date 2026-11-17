# Wing measurement recipe review — #40 partial

- Date: November 17, 2026.
- Author/reviewer: Codex `wing_example` agent, self-review; parent integration
  review remains separate. No independent numerical specialist approval claimed.
- Base: `895975b`, contract frozen on main `12dc774`.
- Scope: new example-only Python geometry/candidate recipe and headless tests.
  No existing solver, component, exporter, shared runtime, archive or node changed.
- Claims: closed oriented example mesh, deterministic provenance, reference area
  and angle conventions. No simulated flow or experimental accuracy.
- Source/reference decisions and limitations: [example guide](wing-measurement-example.md).

| Gate | Decision in this lane | Evidence / limits |
| --- | --- | --- |
| G0 research | PASS for reference audit; physical-reference selection BLOCKED | NASA PDF inspected; lacks drag polar and retains support interference. No copied dataset. Stokes finite-domain/resource limitation recorded. |
| G1 architecture | PASS, bounded self-review | Recipe remains under scripts, no public shape API. New candidate ID per run, copied settings, explicit preflight hash scope, disabled initial state. |
| G2 reliability | PASS for focused checks | 44 tests on each Python 3.9/3.12, 100% measured owned-file line and branch coverage; broader integration gates pending. |
| G3 physics | BLOCKED for aerodynamic qualification | No solver or reference run. Algebraic geometry invariants only; no CL/CD values produced. |
| G4 UI/UX | BLOCKED by requested headless scope | No Rhino/MCP, GH archive, viewport or graph test. Ordinary GH assembly guide only. |
| G5 integration/release | NOT APPLICABLE to standalone lane | No package/install/release. Parent combines code and required evidence. |
| G6 compatibility/examples | Pending integration | No new public node/enum or existing case contract. Host example coverage not claimed. |

## Actual checks

Own `.venv`: Python 3.9.25, NumPy 2.0.2; own `.venv-dev`: Python 3.12.4.
`hawa` and `lettuce` imports resolve into `/Users/r2d2/Desktop/hawa-40-wing-example`
and its `vendor/lettuce`, respectively. All checks used `OMP_NUM_THREADS=1` and
`MKL_NUM_THREADS=1`; no solver/backend is selected by this recipe.

```
.venv/bin/python -m coverage run --branch --include='*/scripts/wing_measurement_recipe.py' -m pytest tests/test_wing_measurement_recipe.py -q
.venv/bin/python -m coverage report -m
.venv-dev/bin/python -m pytest tests/test_wing_measurement_recipe.py -q
.venv-dev/bin/ruff check scripts/wing_measurement_recipe.py tests/test_wing_measurement_recipe.py
```

Result: 44 passed on each interpreter, no skips; 101 executable statements and
48 branches measured, zero misses/partial branches. Ruff's configured Python3.9
syntax guard passes. These are focused results, not the committed repository
function matrix or a full-suite pass. Parent owns serial full-suite/function gate.

Assertions independently check paired opposite directed edges, all undirected
edges having two incident faces, Euler characteristic 2, no duplicate/unreferenced
vertices, nonzero triangle area, positive volume, section blending, fixed analytic
area/chord, scale law, positive-angle convention and inverse rotation, repeatable
hashes, angle/speed/config identity differences, repeated candidate IDs, immutable
settings and rejected malformed/overflow/degenerate inputs. Deliberately collapsed
and reversed upstream sections are rejected. This is not a general CAD
self-intersection proof.

No full suite, mutation study, C# tests, G6 runtime, numerical smoke, device
qualification, Rhino, package build, install or release was run in this lane.
No shared coverage matrix was edited. Issue #40 remains open.
