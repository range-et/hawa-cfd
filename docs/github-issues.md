# GitHub issue workflow

[Open issues](https://github.com/range-et/hawa-cfd/issues) are the development
backlog for bugs, verification, features, build/CI, documentation and research.
There is no Markdown backlog. Specifications, review evidence, feature history and
roadmap direction remain versioned in the repository; task status lives on GitHub.

## Intake and planning

Search open and closed issues before creating one. Use the scoped-work template
and include the problem or hypothesis, source/build/repro, execution surface,
remaining work, completion criteria, dependencies and owner (or unassigned).
Preserve HAWA IDs on the 38 migrated issues so old references still resolve.
New work uses the GitHub issue number; do not allocate new HAWA IDs.

Use type labels (`bug`, `verification`, `enhancement`, `research`, or
`documentation`) and applicable `surface:` labels. Keep `status:` labels current;
GitHub's open/closed state is authoritative. Historical Codex ownership is prose,
not an assignment to a GitHub user. Set assignees only to actual agreed owners.
Do not invent priority, milestones or delivery dates from an untriaged suggestion.
Split large work into linked issues with distinct acceptance criteria when useful.

## Implementation and closure

Reference the issue in its PR. Use `Refs #NUMBER` for partial work. Use
`Closes #NUMBER` only when the complete declared scope is met and the merge target
supports the intended closure. A merge to a study branch does not establish main,
installed or released status. Update the issue with remaining work after partial
merges; do not treat a green suite as numerical or host qualification.

Follow the repository quality gates. Record actual tests, devices, skipped checks,
known limits and evidence paths. Keep numerical tolerances fixed unless a separately
justified method/contract change is approved. Shared hardware and Rhino work need
explicit coordination; headless tests cannot substitute for live host gates.

On completion, record the outcome and evidence in the issue and applicable feature
history, then close the issue. For rejected work, explain the decision and close
as not planned rather than calling it implemented. Do not duplicate the open backlog
in Markdown. The [migration crosswalk](github-issue-migration.md) is a fixed audit
record, not a status register.
