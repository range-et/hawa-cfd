# Native panel startup — issue #31 / HAWA-029

November 16, 2026. Author and reviewer: Codex (self-review, no independent reviewer).
Base: `cc48d62`. Development candidate; not merged or released.

## Contract and repair

Opening Hawa or reopening its panel reads `CaseHub.Find` and leaves a fresh
document without a case, domain/body preview, dirty flag or solver job. Setup
controls stay hidden and run controls disabled until explicit creation or restore.
Saved cases keep their identity, settings and live binding. Archive schema versions and
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

## Requested preview controls follow-up

The user opened a saved block case and requested readily accessible visibility
buttons. **Show preview / Hide preview** now sit above the run controls and toggle
native view flags. They preserve physical settings, case ID,
bindings, session and job, and keep individual controls in the View tab. Saving
the document retains visibility; no schema-version change or new node is required.
Buttons are disabled when no case exists. An unchanged visibility action is a
no-op. A changed action writes a native document marker for Mac save prompting.
Hidden native overlays also stop contributing to automatic viewport extents.

108 contracts pass, including running-session preservation, saved hidden restore,
empty-state/no-op behavior, other display settings and actual conduit draw/bounds
recording doubles. The plugin builds with the same two icon warnings. This is a
new candidate: earlier live hashes/results above do not prove the new buttons.
The user authorized saving and a normal restart. The new candidate was installed
only after Rhino exited; fresh bounded acceptance is recorded below.

Fit domain now explains that bodies must be assigned with **Select bodies**;
adding Rhino geometry alone does not change the case. Its tooltip says it refits
the already assigned bodies. The invalid-selection regression asserts this guidance.

The subsequent native annotation report is related to [#108](https://github.com/range-et/hawa-cfd/issues/108).
Boundary labels were emitted in `PostDrawObjects` before the field mesh despite
depth testing being disabled. Native annotations and the HUD/legend now draw in
`DrawForeground`, after object/field passes. The existing GH foreground conduit is
unchanged. A new optional `view.annotations` Boolean defaults to true for older
documents, and is controlled by **Annotations and legend** in View. Global show/hide
includes it. Disabling annotations leaves the mesh/domain visible. Invalid flag
types are rejected. This is an additive schema-2 field, not a schema-version bump.
Contracts assert foreground ordering around an opaque mesh, visibility independence,
legacy missing-key behavior and persisted false values. Actual field-overlap behavior is checked in the new-build captures below; broader
example-specific legibility is not inferred from the contracts.

Final follow-up measurement (`results/issue31-annotations`): 1,821 Python tests
passed / 87 skipped; 108 C# contracts passed. The base ratchet and strict headless
function/line gate pass: 916 functions covered, 361 host functions unmeasured,
including all 46 panel/command/selection functions. The committed matrix and
changed-function baseline are refreshed. Two intermediate measurements were
discarded when subsequent user requests changed their inputs; they are not passes.

## Installed follow-up acceptance — November 16, 2026

The user model was backed up and saved, Rhino quit normally, and the new build
was installed without replacing loaded assemblies. Rhino 8.37 Mac loaded native
SHA256 `34E8DA7AB5F4986A905F53263E54F31908251AA86F13FA6CE1A74C5618630B3D`
and shared SHA256 `D9D063FBFF40B6A07FFD900A7EA19B6FF30FFBA428609560C733BB430B297044`.

Fresh live passes: empty startup, first-preset save state, unchanged preset,
global preview hide/show, hidden flags surviving actual `.3dm` reopen, schema-1/2
restore with binding preservation, all 3 binding-callback phases and all 13 state
hardening phases (CPU pause/resume, MPS 25 steps and zero pending cleanup).
On a separate CPU 30-step velocity field, toggling annotations retained the field
and solver. The normal domain-framed captures were visually inspected:
[annotations hidden](captures/native-annotations-hidden-8f3d31f.png) and
[annotations above the field](captures/native-annotations-shown-8f3d31f.png).
All six boundary labels and the legend render above the field; the independent
switch removes annotations while retaining the field/domain/body preview.
A first recapture attempt ran during a transient field refresh and failed its
ready-field precondition; the later ready-field capture passed. No failed attempt
is treated as a test pass.

Only owned test documents were modified during verification. The user's model
was reopened afterward; its object ID set and serialized Hawa settings matched
the pre-restart records exactly. It was clean and idle with no session/job and
zero pending cleanup. No simulation was started on that model. The MCP router
readopted its window on port 10501 after the owned test window closed.

G4/G5 now have bounded installed Mac evidence for these controls and field
layering. Windows/CUDA, full 22/25/08 legibility acceptance, full example execution
and the previously recorded native Undo/Redo gap remain outside these passes.
Greptile approved code commit `8f3d31f`; both original review threads are resolved
and all CI checks on that code commit passed.
