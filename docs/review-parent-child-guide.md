# HAWA-034 — Parent/child terminology documentation increment

November 9, 2026. Author/reviewer: Codex primary agent (self-review).
Scope: user guide, Grasshopper README navigation and roadmap terminology.
No solver, public node, parameter, generator, archive or installed plugin changes.

## Evidence and outcome

The existing example 33 generator and host verification script still use
`A / city`, `B / neighbourhood`, `C / pond`, including control lookups. Replacing
strings globally could break the harness or recreate the archive. This increment
instead gives readers an explicit role/spacing map and leaves archive presentation
for an isolated Rhino edit with identity/wire checks.

The new [guide](parent-child-domains.md) distinguishes:

- Offline one-way transfer: separate parent and child solves, source files,
  coverage/quality and physical-time requirements; no child feedback to parent.
- Coupled refinement: the existing single fixed 2:1 patch and its exclusions.
- Composed views: no stepping or solver coupling; finest-containing ownership,
  equal-spacing input order, retained masks and matched absolute times.

Source/evidence reviewed: `src/hawa/field_collection.py`,
`scripts/create_neutral_transfer_example.cs`,
`scripts/verify_neutral_transfer_example.cs`, the existing refinement/transfer
user guides, [transfer review](neutral-transfer-review.md), and
[acceptance contract](atmospheric-nesting-implementation.md). The documented
numerical failures are historical; no new physics result is claimed.

The role map retains the actual three sample counts and spacings and distinguishes
sample centres from physical walls. The generic terminology does not claim a
new supported model or arbitrary transfer/refinement combination. Existing
control names, filenames and supplied step/time instructions remain usable.

## Verification and gates

- Local Markdown file and heading/explicit-anchor targets checked for edited docs.
- All `.gh` and `.3dm` archives under `examples/` hash-identical before/after;
  evidence in `results/issue-034-docs/` (including legacy example 09).
- `git diff --check` passes. No code tests, new full function/G6 run, plugin build
  or Rhino session: this increment edits documentation only.
- G0/G1: PASS for terminology and ownership, checked against source/contracts.
- G2: PASS for documentation integrity; no runtime reliability claim.
- G3: PASS for bounded wording; numerical qualification remains failed/open.
- G4: documentation review only; live canvas relabelling and user walkthrough
  remain NOT RUN, so the complete issue stays open.
- G5/G6: NOT APPLICABLE to this documentation increment; no release, new node,
  field format, supported solver combination or archive change.

HAWA-034 remains in progress for the canvas/presentation portion. Next: in a copy
of example 33, make parent/child roles visible without changing functional object
IDs, wires, values or archive compatibility; update name-dependent verification
lookups only as needed and verify the copied graph through Rhino MCP. Keep the
original archive filename stable. Do not close HAWA-021/022 or broader refinement
on the strength of these documentation changes.
