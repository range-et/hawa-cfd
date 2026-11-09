# Hawa 0.5 release review

Scope expanded at the user's request on November 8, 2026: selected closed Rhino
geometry, editable axis-aligned domains and fluid/boundary controls, native field
controls and icons, with the existing shared GH/native case. The older prototype
and roadmap limits are historical; this delivery supersedes their native-setup
boundary. Multiple cases per document and native editors for motion, refinement,
optimization or recording remain outside this release. Those GH workflows remain.

Reviewer: Codex, performing separate research, architecture, developer, numerical
and UI passes. No independent specialist sign-off is claimed. The prior architecture
critic's findings remain covered by the binding/state regressions.

## Acceptance criteria fixed for this change

- Existing schema-1 settings load into the block preset and stay idle. Schema 2
  stores physical setup/view values and Rhino object IDs; no workers/tensors.
- Closed meshes and solid Breps produce a finite selected-body simulation through
  embedded CPU and MPS paths. Missing/open/unresolved geometry fails explicitly.
- Geometry preparation returns control before completion, supports cancellation,
  and cannot publish after an edit/cancel/replacement. No wait loops on the UI thread.
- Domain values are physical metres. Display-unit conversion preserves field
  placement. Unit changes invalidate referenced geometry conservatively for review.
- Object deletion/replacement invalidates owned runs. Reopen retains references
  and stays idle. A second document cannot change the first document's state.
- Display-axis, position and palette/range edits preserve a healthy solver session.
  Fields show their capture step/time/units. Fixed limits survive save/reopen.
- Existing block live-sync, stale-owner/callback, normal undo/redo and cleanup
  regressions continue to pass. Selected-body GH binding uses two physical inputs.
- Native panel/tab/actions and the GH Linked Case node have visible icons, text
  labels and usable control guidance. Native operation does not require GH to run.
- Supported example workflows pass the declared smoke/control checks. Full
  numerical accuracy and convergence are separate claims.

## Review findings addressed

The selected geometry adapter captures detached Rhino geometry on the UI thread,
then meshes and classifies it on a background task. Cancellation always enters
cleanup, including when requested before the task starts. It reuses the existing
GH solid-containment algorithm through `Hawa.Shared.MeshContainment`; no new
collision or force equations are introduced.

Geometry invalidation can arrive while the case service is publishing a change.
It is queued and drained, as document close already is, so it cannot be lost to
reentrancy. Settings/view JSON returned to adapters remains detached. Physical
setup edits use the existing version/undo/generation contract.

A Rhino units change can reinterpret an unscaled selected body. Selected cases
are invalidated rather than silently treating the old field as current. The block
preset retains its prior display-only unit behavior. The native viewport caches
field geometry and colour limits by result version and units; redraw does not
rebuild the voxel mask.

Setup/display forms keep in-progress text while progress notifications arrive.
Physical settings and display changes have separate Apply buttons. Run controls
expose preparation/pausing/completion and disable inappropriate actions. Default
fluid settings are labelled as demonstration values.

## Gate record

Final statuses and measured evidence are in `verification-v0.5.json`. Required
local gates must be completed before packaging the verified build. Windows/CUDA
and clean-install gaps remain explicit exclusions, not passes.

- G0 research: reuse established LBM/voxel behavior and existing Rhino/Eto APIs;
  API signatures checked against the installed Rhino SDK. No new numerical engine,
  dependency, external service or third-party icon asset is introduced.
- G1 architecture: schema migration, identity/ownership, late results, cancellation,
  geometry events and units are covered by contract and native tests.
- G2 development: compile both plugins; run focused state contracts and the Hawa
  suite; verify matching installed/packaged assemblies and corresponding source.
- G3 numerical: existing equations/tolerances unchanged; software/geometry checks
  and existing numerical suite support the implementation scope. Selected-body
  visual examples remain demonstrations, not experimentally validated RC designs.
- G4 UI/UX: inspect native Setup/Solve/View, panel/action/node icons, example 22,
  live state/capture output and existing workflow examples in actual Rhino.
- G5 distribution: preserve frozen 0.4, include GPL source/notices/assets/examples,
  exclude legacy 09 and temporary files, verify ZIP and binary hashes. No public
  publishing or YouTube upload is part of this change.

## Adapter and data path

`Rhino object IDs + SI setup → detached geometry capture → background voxel task →
existing embedded job service → session → tagged field snapshot → native/GH views`.
Settings schema 2 is serializable. The runtime state owns the task cancellation
source, session and query handles separately. A settings version protects writes;
a physics revision and run generation reject obsolete work; result identity
includes case/session/field/step/time. Object IDs are document-local references.
No live mesh, task or tensor is serialized into the settings archive.

A geometry change invalidates the owning case and releases its work. The user
reviews the updated geometry and starts again. It does not silently restart an
optimization or change a bound GH document. Selected geometry retains the same
single-writer lease and scheduled slider-pull contract as the block workflow.

The motion smoke harness assumed saved Run toggles were off. Example 18 opened
with Run on, correctly invoking the saved-toggle guard and remaining ready at
zero steps. The harness now sets Run off on its in-memory copy before the first
solution, then starts after preparation. Shipped definitions remain unchanged.

The final GH visual pass found guide panels using a tiny inherited default font.
Examples 21 and 22 now set explicit readable fonts, wrapping, alignment and colour.
Their object IDs and input wires remain intact; both distributed templates remain
unbound. The new canopy has native Setup/Solve/View and GH screenshots under
`captures/v05/native-selected-*.png`.

## Core-node audit and hull migration

The public parametric hull component was a product-boundary error. It is now a
hidden archive reader only. Example 10 uses standard Grasshopper expressions,
points, mesh construction, volume and transforms. Three parameter sets matched
the former mesh vertices exactly and volume within 4e-15. The migrated graph
completed five search candidates, pause/resume/cancel, input change and close
cleanup on the final installed assembly. Fresh archive checks found 46 public
components and no legacy hull instance in any of the 21 supported definitions.
The modified user legacy example 09 was preserved and excluded. See
[node-catalog-v0.5.md](node-catalog-v0.5.md) for the API audit and remaining limits.

Final canvas inspection confirmed native expressions, controls and Hawa toolbar
icons. At the full-graph overview, Grasshopper suppresses node text; working zoom
shows the labels. The native Setup/Solve/View captures predate this catalogue-only
change and remain evidence for the unchanged native adapter.
