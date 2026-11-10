# November 9 user-notes issue intake

- Date: November 9, 2026. Author/reviewer: Codex primary agent, self-review only.
- Request: convert the pasted Hawa notes into actionable issues, reconcile existing
  entries and prepare for later triage. Source: user attachment “Pasted text.txt”;
  durable summaries are in the issue rows, not a copied transcript.
- Scope: documentation only. Added HAWA-027–043; retained existing ownership,
  closed repair scopes and historical numerical failures. Added provisional
  verification/workflow/research groupings without committing implementation order.
- References: features/issues registers, quality gates and review template,
  roadmap/example backlog, native guide, node catalogue and neutral-transfer
  follow-up. External tool/repository suggestions were not researched or endorsed.
- Acceptance: distinct stable IDs; observations versus hypotheses labelled;
  date/owner/scope/evidence/next action/completion criteria; no duplicate atmospheric
  bugs or reopened HAWA-024; local links, IDs and whitespace checked.
- Environment: repository documentation only. No device, solver steps, Rhino
  operations, binaries, GH archives or numerical settings changed.

| Gate | Actual reviewer | Decision | Evidence and reason |
| --- | --- | --- | --- |
| G0 research | Codex, self-review | PASS for intake | User requests mapped to existing records; research proposals explicitly unvalidated. No method/dependency adoption. |
| G1 architecture | Codex, self-review | PASS for intake | Existing IDs retained; new scope distinguishes shared-state handoff, geometry, views and physics. Runtime contracts unchanged. |
| G2 reliability | Codex, self-review | NOT APPLICABLE | Prose only; documentation checks below. Function matrix and Python/.NET suites not rerun. |
| G3 numerical physics | Codex, self-review | NOT APPLICABLE | No solver change or fresh validation; recorded failures and unchanged tolerances retained. |
| G4 UI/UX | Codex, self-review | NOT APPLICABLE | Reported symptoms await reproduction; no host/UI/example edits or checks. |
| G5 release | Codex, self-review | NOT APPLICABLE | No packaging, installation or release changes. |
| G6 compatibility | Codex, self-review | NOT APPLICABLE | No public node, combination, format, state or example changes; inventory not rerun. |

## Checks and disposition

Repository Python checked relative Markdown file/anchor targets in changed docs,
unique active issue definitions and new IDs against the prior registers.
`git diff --check` checked whitespace. No implementation issue was closed and no
feature capability was added. Triage remains provisional for discussion with the
user; the first verification actions are not promises of small fixes.
