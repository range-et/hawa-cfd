# Boundary tick legibility follow-up (#108)

Date: November 24, 2026. Author/operator: Codex primary agent.
Additional read-only source/contract review: Codex scheduler_cli agent; no
source blocker found, projected tick length remains a live acceptance concern.
Scope: shared native/GH display only; no solver, units, boundary assignment,
archive identity or public node changes.

## Reproduction and change

On Rhino 8.37.26307.15002/macOS, the installed build rendered every example 08
label and the inlet arrow at domain-fit framing, but the single-pixel dotted
outlet marker was effectively invisible against the viewport. Example 22's
computed speed field retained all six foreground labels and its inlet arrow;
its outlet marker was visible but faint. The prior native foreground repair is
retained, not reopened as a current occlusion defect.

The shared renderer now draws four separated coloured strokes with a white halo
at the same inward-normal tick endpoints. Thickness is in pixels; geometry stays
inside the original domain. Open/outlet markers remain broken and distinct from
solid pressure-reference markers and directional velocity arrows. Periodic pair
lines are unchanged.

Recording display contracts check dash endpoints, gaps, ordering, colours and
pixel widths in metre/millimetre and rotated frames. They do not establish visual
legibility. Existing foreground, label, stale-result and visibility checks remain.

## Evidence so far

- Before-change native 22: CPU, 30 steps, cell 0.05 m, speed 1.3 m/s,
  physical time 0.026646935501059656 s; completed/current speed field with no
  solver or view error. All six labels above the field, visible inlet arrow,
  faint outlet marker.
- Before-change GH 08: CPU, 33 x 17 x 17, 30 steps,
  physical time 0.43301270189221935 s; valid 1,144-face slice. All six labels
  visible with Case selected; inlet arrow visible; outlet marker not legible.
  Sticky quality warning retained: density deviation 5.19691% at step 5 exceeds
  the existing 5% threshold. This is display evidence, not physical qualification.
- Before-change installed SHA-256: native
  `948dda2e4b4e8ec763821eea13e291fe4860b3b257ffc26aa4523d4fc8cafa5d`, shared
  `5eef4a56a175a04c2f110eb3ff9492b9f2c8213397a103b9564c1cbfef420bae`.
- Local artifacts: `results/mvp-acceptance-20261124/` (owned copies, native state,
  GH monitor, before screenshots). Source templates were not modified.
- Revised code at `a16d4b0`: 155 C# StateContracts pass. Full Python 3.9 measured
  suite: 2,846 passed, 87 skipped, 215 warnings; strict headless coverage:
  1,201 covered functions, zero failures, 299 host functions still unmeasured.
  Available-device tests ran while another coverage suite/mutation workers were
  active; this is not exclusive-device performance evidence. CUDA is unavailable.
- Development package builds with existing platform/nullability warnings and no
  errors. ZIP integrity passes and legacy example 09 is absent. Revised shared
  assembly SHA-256:
  `ffced5de47d052ff050a0b93df30574d9d7a6d30441a3c54c4353253dc4dde9c`.
  This assembly has not yet been installed or visually accepted.
- Reproduction: `tools/function_coverage.py run --base-ref origin/main --strict
  --coverage-scope headless --output results/function-coverage-annotation-20261124`
  using `.venv/bin/python`, .NET 10.0.404 and one CPU thread; followed by matrix
  render/check. Development build uses `scripts/build_plugin.py` with unique
  `dist/Hawa-annotation-review` staging and archive paths. Local Markdown links pass.

## Gate disposition

| Gate | Decision | Evidence and limits |
| --- | --- | --- |
| G0 research | PASS (bounded display) | Preserve broken inward-normal marker semantics; no new API/dependency. |
| G1 architecture | PASS | Accepted assignments, physical endpoints, archive identities and foreground ownership unchanged; source review by primary and scheduler_cli agents. |
| G2 reliability | PASS (headless) | Full measured suite, contracts, matrix and build above. |
| G3 numerical physics | NOT APPLICABLE (solver verification) | Display-only stroke change; units/labels/normal direction unchanged. CPU30 is not convergence; example08 quality warning retained. |
| G4 UI/UX | BLOCKED | Revised live08/22/25 captures await normal Rhino restart/install. Normal Exit did not complete; no process killed or loaded assembly replaced. Windows unverified. |
| G5 release | NOT APPLICABLE | Development package only; no release or installed-candidate claim. |
| G6 compatibility/examples | BLOCKED (host acceptance) | No new node/format/physics combination. Revised examples and full gallery not run. |

Issue #108 remains open until revised-build live acceptance completes.
