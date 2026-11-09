# Native startup audit — HAWA-029

November 9, 2026. Operator/reviewer: Codex primary agent via Rhino MCP; self-review.
This audits the existing installed build, not the CUDA integration candidate or
the new export build. No simulation, geometry creation, file overwrite or assembly
installation was performed.

## Observed workflow

1. `list_slots` returned no running slots. Spawned one Rhino 8 session (`aardvark`).
2. `get_context` reported an empty document: zero objects, six template layers,
   no selection and no open GH canvas. Document path was null, `Modified=false`.
3. Ran Rhino's `Hawa` command. Public `CaseHub.Get` / `Describe` reported an idle
   block case, dimensions 8 × 6 × 4 m, cell size 0.5 m, artificial demonstration
   viscosity 0.1 m²/s, target 200, selected backend setting CPU. Session and job
   were null, steps zero. Domain/body/field view switches were enabled.
4. Inspected the viewport capture: the Hawa preview/zero-step field label was
   present. A second context snapshot still showed no GH canvas or objects.
   This demonstrates no canvas opened; it is not an exhaustive audit of all GH
   integration or panel controls.
5. Recorded installed assembly paths/hashes and public case state in
   [the machine record](verification-native-intake.json). Rhino version:
   8.36.26296.17002; Hawa assembly versions 0.5.0.0.
6. Issued normal `_Quit` for this agent-created, unmodified, empty session. The
   MCP response disconnected during shutdown; subsequent `list_slots` was empty.
   No force quit or process signal was used; no user document existed in the session.

Raw captures: `results/native-intake-2026-11-09/startup.json` and `startup.png`.
Installed hashes identify the tested binaries; version 0.5 alone does not prove
they equal either current source checkout.

## Disposition

HAWA-029’s clean-document startup behavior is now reproduced. Implement an
explicit opt-in block preset and test saved-case restoration, old archives,
bindings, reopen and undo before closing it. No UI repair is claimed here.

HAWA-027 remains unverified in the host: no solve or partially missing cells were
reproduced. A source trace found separate native wall-link and snapshot halfway
clipping paths; that is a hypothesis to guide the next minimal reproducer.
HAWA-030 still needs an actual panel/view capability and handoff design audit.

| Gate | Reviewer | Decision | Scope |
| --- | --- | --- | --- |
| G0 evidence | Codex self-review | PASS for audit | Exact installed hashes, public operations and expected startup recorded |
| G1 architecture | Codex self-review | NOT APPLICABLE | No code/state-contract change; default public state observed |
| G2 reliability | Codex self-review | NOT APPLICABLE | No code edit or solver run; this is not a suite pass |
| G3 numerical | Codex self-review | NOT APPLICABLE | Zero solver steps; no numerical claim |
| G4 UI/UX | Codex self-review | PASS for reproducing startup only | Default case/preview observed in an empty document; saved/reopened/bound cases not tested |
| G5 release | Codex self-review | NOT APPLICABLE | Existing install only, no package/install verification |
| G6 compatibility | Codex self-review | NOT APPLICABLE | No combinations, components, formats or archives changed |
