# Native panel startup — issue #31 / HAWA-029

November 16, 2026. Author and reviewer: Codex (self-review, no independent reviewer).
Base: `cc48d62`. Development candidate; not merged or released.

## Contract and repair

Opening Hawa or reopening its panel reads `CaseHub.Find` and leaves a fresh
document without a case, domain/body preview, dirty flag or solver job. Setup
controls stay hidden and run controls disabled until explicit creation or restore.
Saved cases keep their identity, settings and live binding. Archive schemas and
shared-state ownership are unchanged.

Both PR review findings were reproduced and repaired:

- [First preset skipped the save prompt](https://github.com/range-et/hawa-cfd/pull/110#discussion_r4589479248): first explicit Block preset creation writes a namespaced native document record (`Hawa/last-created-case`). This marks a clean saved document changed on Mac as well as Windows. Settings remain in the plugin archive; the marker is not used to restore or create cases. Reapplying identical defaults leaves a saved case clean.
- [Rejected selection created a block](https://github.com/range-et/hawa-cfd/pull/110#discussion_r4589479269): validate object count/existence, mesh/Brep closure and complete fitted settings before publishing a first case. Invalid selections retain an existing case, binding and dirty flag. Fit domain rejects an absent case without creating one.

The first candidate used `RhinoDoc.Modified = true`. Live testing found that
setter had no effect on Mac; the native-record repair then passed the same clean
saved-document test. This agrees with [McNeel's documented Mac behavior](https://discourse.mcneel.com/t/still-prompted-to-save-after-doc-modified-flag-set-to-false/179427/4).
Selection admission moved to `NativeSelection.cs`, a partial of the existing
service, so production admission and fitting run in StateContracts against
geometry/bounds doubles. Background preparation remains host-only.

## Automated evidence

macOS 27.2.1 arm64; Python 3.9.25 / 3.12, PyTorch 2.8.0; MPS available,
CUDA unavailable. .NET 10 contract host, .NET 7 plugin target.

- Separate temporary builds using each prior implementation failed the new
  intended regression assertion (save prompt and unwanted first case).
- 105 C# contracts passed, including a Mac-like ignored Modified setter,
  rejected geometry/domain admission, UI-thread checks, metre conversion,
  deduplication, control events, schema restoration and binding preservation.
- Python 3.9 measured run: 1,821 passed, 87 skipped, 213 warnings.
- Python 3.12: 1,811 passed, 86 skipped, 11 deselected, 215 warnings.
- Ruff and changed-document local links passed.
- All 42 panel/command/selection functions measured covered. Base ratchet and
  strict headless function/line gates pass. Matrix refreshed from
  `results/issue31-mac-final`; 361 other host functions remain unmeasured debt.
- Plugin build passed with two existing CA1416 icon warnings and no errors.
  No new solver, dependency or archive format was introduced.

## Live Rhino evidence

Rhino 8.37.26307.15002 on macOS, via Rhino MCP. Initial connection attempts
failed; reconnect succeeded. The original installed bundle was backed up, Rhino
quit normally before installation, and no loaded assembly was replaced. Only
owned test documents were used. Legacy example 09 and source examples were not
written. The tested candidate remains installed for inspection.

Native assembly SHA256:
`830F2E5171DEBA13CEA436704778BFD2F54181DE58F652062CB97B756A508F9B`.
Shared assembly SHA256:
`47730850F333D47B13491E554A5BC3FB47A0C8CA45504B287560BBC2D0E6BB0F`.

- Phased `verify_panel_startup.cs`: command and repeated panel creation stay
  empty/clean; real open mesh and non-solid Brep rejection leaves no case; first
  preset changes a clean saved document and stays idle; saved identical preset
  and panel reopen stay clean; schema 1/2 public restores keep settings/binding.
  Native Save/SaveAs commands establish clean checkpoints between MCP calls.
  Nested script saves and API exports did not establish a clean Mac UI checkpoint;
  those earlier fixture attempts are not counted as passes.
- `verify_binding_callbacks.cs`: all three phases passed, including duplicate
  owner isolation and queued callback invalidation on case replacement.
- `verify_state_hardening.cs`: all 13 phases passed; live GH sync, invalid inputs,
  ownership, version conflicts, CPU pause/resume, unit scaling, stale-field
  withholding, MPS 25-step result, reset/disposal and zero pending cleanup.
- `verify_native_geometry.cs`: all eight phases passed. Mixed closed mesh/solid
  Brep selection, CPU 30 steps, MPS 30 steps, display edits, deletion/replacement,
  cancellation/retry, CPU 20 steps, selected schema-2 `.3dm` save/reopen and unit
  invalidation. The reopen assertion used `Find`, not `Get`, to avoid masking a
  missing archive restore.
- `verify_native_prototype.cs` did not complete its Undo/Redo sequence. Direct
  MCP Undo/Redo commands did not change the case. A deferred `RhinoDoc.Undo()`
  restored speed and the linked slider, but a later Redo returned false after
  intervening MCP scripts. A second timer-driven attempt did not advance past
  Undo. These attempts are **not passes**; the cause is unresolved between host
  command/undo integration and harness behavior. Keep this acceptance gap in #31.
  The state/binding and geometry harness passes above are independent.
- Shipped native-block, selected-canopy and curved-solid `.3dm` fixtures all
  restored an existing idle case without auto-running.
- Read-only archive audit loaded 31 supported GH definitions, with no archive
  errors and all 53 public nodes represented. This is archive coverage, not
  execution/numerical acceptance of every example.

Raw reports are under `results/issue31-host` and `results/v05`; the compact
[committed evidence](verification-panel-startup.json) preserves outcomes.
Windows/CUDA, all-example execution, picker cancellation by a human, and broad
G6/device qualification are not claimed. Solver runs are lifecycle smoke tests,
not convergence or engineering-accuracy evidence.

## Gate decisions

| Gate | Reviewer | Decision and scope |
| --- | --- | --- |
| G0 evidence | Codex self-review | PASS: both review reproductions and fresh regression checks |
| G1 architecture | Codex self-review | PASS bounded: read-only startup, validated creation, unchanged ownership/archive contracts |
| G2 reliability | Codex self-review | PASS for declared automated and live checks; omitted surfaces remain explicit |
| G3 numerical physics | Codex self-review | NOT APPLICABLE: no physics change or accuracy claim |
| G4 UI/UX | Codex self-review | Bounded host acceptance; no Windows or human picker acceptance |
| G5 distribution | Codex self-review | Development build installed on Mac; not a release gate pass |
| G6 compatibility | Codex self-review | Bounded saved-case, binding and archive checks; no broad matrix rerun |

Keep #31 open until its remaining declared acceptance is reviewed. This PR must
not automatically close the issue.
