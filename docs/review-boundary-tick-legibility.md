# Boundary tick legibility follow-up (#108)

Date: November 24, 2026. Reviewer/operator: Codex primary agent.
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
- Revised code: 155 C# StateContracts pass; development package builds with
  existing platform/nullability warnings and no errors.

## Gate disposition

G0/G1: bounded display decision; accepted assignment and physical geometry unchanged.
G2: focused contracts pass; full measured gate pending.
G3: no solver change; numerical interpretation unchanged. Short CPU runs are not
convergence or physical validation; the example 08 quality warning stays visible.
G4: revised live 08/22/25 captures pending normal Rhino restart/install. The
normal Exit request did not complete; no process was killed and no loaded
assembly was replaced. Windows remains unverified.
G5: development build only, not a released package.
G6: no new node, format or supported physics combination; full gallery not run.

Issue #108 remains open until revised-build live acceptance completes.
