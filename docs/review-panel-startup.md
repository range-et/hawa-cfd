# Native panel startup — issue #31 / HAWA-029

November 16, 2026. Author and reviewer: Codex (self-review, no independent reviewer).
Base: `cc48d62`. Scope: native command/panel startup; no solver or archive schema change.

## Contract and change

Opening `Hawa` or constructing/reopening its panel must leave a fresh document
without a shared case, domain/body preview, dirty flag or solver job. Setup
controls stay hidden and run controls disabled until a case exists. Select bodies
and Block preset are explicit actions. Cancelled selection leaves an empty panel.
Saved cases must retain their settings, case identity and live binding; schema 1
still restores the original block defaults and schema 2 retains selected geometry.

The command no longer calls `CaseHub.Get`; refresh calls `Find` and renders an
empty state. Empty control events cannot create a case. The shared service,
persistence callbacks, archive schemas and GH creation path are unchanged.
`HawaCommand` is in its own source file so the production command can be tested
without substituting the entire plugin lifecycle. Panel lambdas have separate
block bodies to make measured execution unambiguous; the layout expansion is
otherwise formatting, not new behavior.

## Automated evidence

`tests/dotnet/StateContracts/PanelContracts.cs` exercises the production panel and
command against event-capable Eto and Rhino doubles. Assertions cover fresh and
reopened panels, command docking branches, cancelled picking, empty control
events, absent preview calls/bounds, explicit block creation, edits/undo, run,
pause/cancel/reset/refresh, saved schemas before/after panel construction,
selected-body settings, binding identity and unrelated-document notifications.
The doubles do not establish real docking, selection, persistence or GH scheduling.

Environment: macOS 27.2.1 arm64, Python 3.9.25 / 3.12, PyTorch 2.8.0;
MPS available, CUDA unavailable. C# contracts use .NET 10 doubles; plugin targets
.NET 7. No live Rhino simulation or separate device qualification was run.

- `dotnet run --project tests/dotnet/StateContracts`: 102 passed.
- Direct Coverlet check: all 36 panel/command executable functions and 385 lines
  covered. Branch coverage is separate; this is not a complete behavioral proof.
- Python 3.12: 1,811 passed, 86 skipped, 11 production-only tests deselected;
  215 warnings (including dependency deprecations).
- `ruff check .`: passed.
- `scripts/build_plugin.py`: both assemblies built; two existing CA1416 icon
  platform warnings, zero errors. ZIP integrity passed; example 09 excluded.
- Changed documentation links and `git diff --check`: passed.
- Python 3.9 measured gate: 1,821 passed, 87 skipped, 213 warnings; 102 C#
  contracts passed. Base-commit ratchet and strict headless function/line gate
  passed with zero failures. Committed matrix refreshed from
  `results/issue31-gate`; the 36 measured panel/command baseline entries are
  promoted. Other 367 unmeasured host functions remain explicit debt.
- This refresh supersedes two interrupted local measurement attempts during
  callback/test formatting; neither interrupted run is reported as a pass.

## Host acceptance and remaining scope

Rhino MCP returned no slots; one spawn attempt returned `startup_timeout` because
Rhino did not bind its MCP port within 120 seconds. A subsequent slot query was
also empty. No candidate assembly was installed or replaced, and no Rhino process
was killed or user document edited. Live checks are **BLOCKED**, not passed.

`scripts/verify_panel_startup.cs` is an unrun, bounded public-API host check for an
isolated empty document. Remaining host acceptance: visible empty panel and no
viewport preview; explicit preset and cancelled/successful body selection; actual
schema-1/schema-2 `.3dm` save/reopen; panel reopen; native Undo/Redo; live Linked
Case callbacks and supported-example acceptance. Use the existing state/binding
harnesses on copies. Preserve legacy example 09. No broad G6 rerun or physical
validation is claimed for this UI-only change.

| Gate | Reviewer | Decision | Scope |
| --- | --- | --- | --- |
| G0 evidence | Codex self-review | PASS | Existing #31 reproduction and fixed acceptance above; no new dependency/method |
| G1 architecture | Codex self-review | PASS, bounded | Read-only startup; unchanged shared ownership and archive contracts; asserting state restoration tests |
| G2 reliability | Codex self-review | PASS headlessly | Both Python suites, 102 contracts, base ratchet, strict headless coverage and build pass; real host acceptance remains blocked |
| G3 numerical physics | Codex self-review | NOT APPLICABLE | No physics, units or solver changes; no accuracy claim |
| G4 UI/UX | Codex self-review | BLOCKED | MCP unavailable; headless callback tests do not prove native layout or host behavior |
| G5 distribution | Codex self-review | BLOCKED for release | Development build only; no install/release or Windows acceptance |
| G6 compatibility | Codex self-review | PASS for unchanged contracts; host BLOCKED | No public-node, shared-state, schema or numerical-product change; old schemas covered headlessly, live bindings/examples pending |

Keep #31 open until the declared host checks pass. This PR supplies the repair and
headless regressions; it must not automatically close the issue.
