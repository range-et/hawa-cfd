# Retained poll retry review — PR #130 / #122

- Date: November 24, 2026. Reviewer: Codex scheduler agent (self-review).
- Scope: Grasshopper poll ownership and deterministic deadline tests. No solver,
  archive, public ports, numerical tolerance or example changes.
- Environment: macOS arm64; .NET SDK 10.0.404, net10 StateContracts with
  Rhino/Grasshopper/Eto doubles; plugin target remains net7.
- Claim: a skipped Hawa component retains an active retry timer when a sibling
  completes during the same drain. This does not establish the trigger of the
  original installed-host publication interruption.

## Reproduction and repair

Queue two components in one document at t=0 with 100 ms deadlines. At t=100,
let the solution cancel the first completed component and skip the second.
Before the repair, cancellation sees an empty pending dictionary and disposes
its timer; the skipped request is then restored without a timer. The new
regression fails with “Completed component disposed the skipped component's
retry timer” on that implementation.

Defer empty-registry timer disposal until Drain's finally block. The retry
remains armed and runs at t=200; no solution runs at t=99 or t=199. Completing
the retry leaves zero requests and zero active timers. The existing Stationary
Study contract verifies final output publication without duplicate submission
and document-close cleanup after a skipped solution. It now advances an internal
monotonic clock provider instead of sleeping. Each fixture restores the clock.

## Gate decisions

| Gate | Decision | Evidence / limits |
| --- | --- | --- |
| G0 research | PASS, scoped | Existing retained-poll contract and reproducible timer ownership failure; no new API or method. |
| G1 architecture | PASS, headless | Due entries temporarily live outside pending; timer lifetime now spans their disposition. Cancellation identities and failed-solution handling remain intact. |
| G2 reliability | PASS, headless | 158 StateContracts; Python 3.9 measured suite 2,846 passed / 87 skipped; strict headless function/line gate zero failures. Committed matrix refreshed. |
| G3 numerical physics | NOT APPLICABLE | Scheduling only; no solver or physical quantity changes. |
| G4 UI/UX | BLOCKED | Fresh Rhino multi-candidate, intervening-solution, pause/cancel and close acceptance remains with the integration owner. |
| G5 release | BLOCKED | Not integrated, installed or packaged by this review. |
| G6 compatibility | BLOCKED for host acceptance | Headless scheduler transitions tested; no new node/schema/enum. Full installed-example acceptance has not run. |

Local logs: `results/scheduler-review-20261124/` (not committed). A first test
attempt could not start because only .NET 11 was installed; the private .NET 10
SDK fixed the environment without changing project targets. Issue #122 stays
open until the live multi-candidate workflow satisfies its acceptance criteria.

## Fresh checks

- `dotnet run --project tests/dotnet/StateContracts`: 158 passed.
- `.venv/bin/python tools/function_coverage.py run --output
  results/function-coverage-scheduler-review-20261124 --base-ref origin/main
  --strict --coverage-scope headless`: PASS; 2,846 Python tests passed,
  87 skipped, 215 warnings, 158 instrumented state contracts. The 299 unmeasured
  host functions remain explicit. Accelerator/host omissions are not passes.
- Full Python 3.12 rerun and live Rhino acceptance are not included in this
  record; no Python implementation changed in this follow-up.
- Logs and the uncommitted coverage run retain exact tool output. No numerical
  convergence, engineering accuracy, installed build or release claim.
