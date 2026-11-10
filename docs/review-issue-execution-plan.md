# Issue execution-surface planning review

- Date: November 9, 2026. Author/reviewer: Codex primary agent; self-review only.
- Request: classify each issue by execution environment and propose isolated
  agent/PR work versus serial Rhino work for user review.
- Scope: all 35 active issues, source-based routing and proposed work batches.
  No implementation, delegation, container build, host operation or PR publication.
- Evidence inspected: registers, quality/function/G6 gates, Python dependency
  pins, existing Ubuntu CI, StateContracts production links, plugin project SDK
  references, core/service exports, source/test/harness inventory, MCP guide and
  existing site/Pages workflow. External platform references are linked in plan.
- Criteria: exactly one matrix row per active issue; distinguish development
  location from closure evidence; preserve IDs/status/owners and existing edits;
  identify dependencies/resource conflicts; check documentation links/whitespace.

| Gate | Reviewer | Decision | Scope/reason |
| --- | --- | --- | --- |
| G0 research | Codex, self-review | PASS for planning | Source and official platform references support environment split; proposed image remains unbuilt/unverified. |
| G1 architecture | Codex, self-review | PASS for planning | Explicit P/C/D/H/R boundaries, partial PR scope, immutable base, separate evidence and host/device ownership. No runtime design changed. |
| G2 reliability | Codex, self-review | NOT APPLICABLE | Documentation only; link/ID/table/whitespace checks performed. No Python/.NET suite or function matrix regeneration. |
| G3 numerical physics | Codex, self-review | NOT APPLICABLE | No physics change or new numerical pass; device and reference gates retained. |
| G4 UI/UX | Codex, self-review | NOT APPLICABLE | Host audits are proposed, not performed. |
| G5 release | Codex, self-review | NOT APPLICABLE | No build/install/package/PR or release. |
| G6 compatibility | Codex, self-review | NOT APPLICABLE | No nodes, contracts or example archives changed. |

Documentation checks: all 35 active IDs have unique execution-plan rows and
per-issue surfaces; relative file/anchor links resolve; issue-table column counts
are consistent; changed files pass whitespace checks. Existing intake edits are
preserved, including the untracked notes-intake review. Planning decisions await
user review and no issue is closed by this classification.

## Existing CUDA PR follow-up

Inspected PR #2 metadata, changed-file list, repair follow-up, CUDA setup/runner
and device fixture at head `864a2652eed371ab8c16e65d9ab1228d09a00e79` via GitHub
CLI. Compared its base with local commit history. This was scope/evidence triage,
not a full code review or independent reproduction. Found no submitted reviews
or attached CI checks; PR remains open. Updated HAWA-001/002/006 and pilot scope
to reuse its work, while requiring integration evidence against newer local
source and retaining MPS/Windows host/clean-install gaps. No source or PR changes.
Rechecked documentation links, unique issue mapping and whitespace.
