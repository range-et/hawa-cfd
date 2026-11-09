# HAWA-049 — Refinement origin preflight

November 9, 2026. Author/reviewer: Codex domains agent, self-review; no independent
approval claimed. Base: `a26924caa9ef5da070c0a82f2f8a8bf3ddf5782d`.
Scope: Python refinement placement validation and its regressions. No changes to
collision, transfer, field clipping, public nodes, C#, archives or Rhino state.

## Reproduction and contract

`run_refined` previously used `np.allclose(expected, actual, atol=1e-7)` for the
fine-grid origin. NumPy's default relative tolerance enlarged the permitted
misalignment as absolute coordinates increased.

A CPU case with parent shape 17³, coarse spacing/dx 1 m, fine shape 13³, fine
spacing/dx 0.5 m and coarse-index patch [5,5,5]–[11,11,11] demonstrates it:

| Parent origin | Fine origin | Required | Before repair |
| --- | --- | --- | --- |
| [0,0,0] | [5,5,5] | Accept | Accepted |
| [0,0,0] | [6,5,5] | Reject | Rejected |
| [1000000,0,0] | [1000005,5,5] | Accept | Accepted |
| [1000000,0,0] | [1000006,5,5] | Reject | Accepted and advanced; wrong-origin fine frame returned |

The placement contract is the existing absolute `1e-7` bound in the supplied
world-coordinate units, independent of translation. The repair explicitly sets
`rtol=0`, retains `atol=1e-7`, and includes expected/received origins in the error.
Validation remains before the first checkpoint and Session/solver construction.
Supported aligned, translated and rotated grids remain accepted. This does not
introduce a new unit conversion or change spatial/physical resolution criteria.

## Tests and evidence

Environment: macOS arm64; Python 3.9.25, torch 2.8.0, NumPy 2.0.2. Focused runs use
CPU only with `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`.

- Initial study: 28 existing tests passed, four device cases deliberately
  deselected. The four-case real CPU reproduction ran one coarse/two fine steps.
- New regression before repair: **15 failed, 15 passed**, 4.53 seconds.
- After repair: **58 passed, four device cases deliberately deselected**, 8.10
  seconds. This includes 30 new preflight cases plus existing domain/view,
  refinement, boundary-data and boundary-series CPU tests.
- Invalid-origin tests replace Session with an assertion failure to prove rejection
  happens before construction. They cover both offset signs, all three axes and
  positive/negative million-unit translations. Tests on either side of `1e-7`
  preserve the absolute bound; valid translated/rotated cases execute one coarse
  and two fine steps and check frame placement, physical time and finite fields.
- Full measured gate: **654 passed, 32 unavailable-CUDA skips, four existing MRT
  warnings**, 238.04 seconds; **33 state contracts passed**. Zero ratchet failures
  against `a26924c`. Both committed matrices refreshed and checked: 281 covered,
  149 uncovered, 630 unmeasured and 58 declarations; historical debt remains.
  This full host run includes available MPS cases; it does not provide CUDA evidence.
- Fresh development build: both assemblies and `dist/HAWA-049.zip` succeed.
  Clean-build output contains 105 CA1416 platform warnings in unchanged icon
  sources (103 Grasshopper, two Rhino); zero errors. No C# implementation changed.
  ZIP integrity, legacy-09 exclusion and exact packaged refinement source match
  pass; package SHA-256 is recorded in `package-check.json`. Nothing installed.
- `git diff --check` passes. Fresh G6 is queued separately with the coordinator;
  the source changed, so old matrix evidence is not substituted. No live Rhino,
  clean-install or release qualification in this phase.

Evidence under this checkout's ignored `results/` directory:
`study/refinement-origin-results.json`, `study/domain-baseline.xml`,
`refinement-preflight/before.xml`, `refinement-preflight/before.log`,
`refinement-preflight/focused.xml`, `refinement-preflight/focused.log`,
`refinement-preflight/function-gate/`, `refinement-preflight/function-gate.log`,
`refinement-preflight/committed-matrix-check.json`, `refinement-preflight/build.log`,
`refinement-preflight/package-check.json`.

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python -m pytest tests/test_refinement_preflight.py tests/test_refinement.py tests/test_field_collection.py tests/test_boundary_data.py tests/test_boundary_series.py -q -k 'not mps and not cuda' --junitxml=results/refinement-preflight/focused.xml
```

## Gate disposition

| Gate | Actual reviewer | Decision | Scope |
| --- | --- | --- | --- |
| G0 evidence | Codex domains agent | PASS for scoped repair | Reproduced bad acceptance and valid controls; fixed existing tolerance before repair; no new dependency or numerical method |
| G1 architecture | Codex domains agent | PASS | Validation before solver allocation; no state/ownership or supported topology changes |
| G2 reliability | Codex domains agent | PASS locally | Red/green regressions, 654 suite passes, 33 state contracts, zero coverage failures, refreshed/checked matrices and development build; CUDA unavailable |
| G3 numerical | Codex domains agent | PASS for placement contract only | Real one-step aligned controls plus existing CPU conservation/time tests; no engineering-accuracy or GPU claim |
| G4 UI/UX | Codex domains agent | NOT APPLICABLE to core repair | No adapter/view/archive edit; native trimming remains unverified |
| G5 release | Codex domains agent | BLOCKED | No build/install/release qualification in this phase |
| G6 compatibility | Codex domains agent | PENDING fresh run | Source changed; coordinator will assign serial full matrix run |

HAWA-049 remains in progress until required full evidence is collected. Broader
HAWA-028 policy work, HAWA-031 cell geometry and HAWA-027 native missing-cell
reproduction remain open. Valid view overlap is intentional and is not rejected
by this fix. Numerical transfer work in HAWA-021/022 is unchanged.
