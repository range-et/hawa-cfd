# Project tracking documentation review

- Date: November 9, 2026. Author/reviewer: Codex primary agent, self-review only.
- Request: establish `issues.md` and `features.md` following beta-bot's open-work
  versus built/history split, and add ongoing document hygiene to `AGENTS.md`.
- Scope: two root registers, entry-document links and maintenance instructions.
  No code, dependencies, examples, numerical settings or package changes.
- Sources: beta-bot's root feature/issue introductions and AGENTS workflow rules;
  Hawa's quality gates, review template, example matrix, roadmap, native guide,
  node catalogue, release/cleanup and boundary/atmosphere records.
- Acceptance criteria fixed before editing: seed open work and built capabilities
  from existing evidence; preserve stable IDs; do not reopen documented repairs;
  separate ideas, verified defects and missing qualification; preserve unrelated
  work and check documentation links/IDs/whitespace.
- Environment: repository documentation only; no device, solver steps, Rhino
  operations, benchmark or installed/package build under review.

| Gate | Actual reviewer | Decision | Evidence and reason |
| --- | --- | --- | --- |
| G0 research | Codex, self-review | PASS for documentation | Reference pattern inspected and existing Hawa reports linked; no new implementation or performance claim. |
| G1 architecture | Codex, self-review | PASS for records | Open work, inventory, roadmap and example coverage have explicit responsibilities; detailed evidence remains in scoped records. No runtime contract changed. |
| G2 reliability | Codex, self-review | NOT APPLICABLE | No executable changes; documentation links, IDs and whitespace checked separately. Python/.NET suites not run. |
| G3 numerical physics | Codex, self-review | NOT APPLICABLE | No solver change or new validation claim; unresolved parity and qualification limits retained. Numerical runs not repeated. |
| G4 UI/UX | Codex, self-review | NOT APPLICABLE | No product interface/example changed. Register readability reviewed as prose; no Rhino/GH run. |
| G5 release | Codex, self-review | NOT APPLICABLE | No release/package change. Existing platform gaps remain open; no installation or hardware test run. |

## Reproduction and results

Read both root registers against their linked reports and the maintenance rules.
Use the repository Python to check relative file/anchor links in changed docs,
unique active IDs and register targets. Run `git diff --check` scoped to the
changed tracked entry files; inspect new files for trailing whitespace too.

Documentation checks passed. No numerical, native-host, state-contract, installer
or packaging checks were run for this prose-only change. Seeded records summarize
historical evidence and current documented limits; they are not a fresh audit of
the concurrently modified working tree.
