# Refinement roadmap review

- Date: November 8, 2026.
- Author/reviewer: Codex, self-review across the gates below.
- Scope: proposed user-defined resolution regions in [the roadmap](roadmap.md#user-defined-local-refinement-regions) and [example backlog](example-roadmap.md#a19--building-entrance-pressure-and-vortices).
- Intended claim: the requested feature and urban entrance example are recorded for future work. No implementation, numerical result or release claim.
- Source: user request; existing example 15 scope recorded in the example catalogue. No new dependency or copied code.
- Acceptance: specify region composition, requested versus actual resolution, shared-case ownership, verification criteria and example deliverables without advertising current support.
- Environment: local documentation review only; no solver/device configuration or binary changed.

| Gate | Reviewer | Decision | Evidence and reason |
| --- | --- | --- | --- |
| G0 research | Codex | PASS | Backlog scope and acceptance criteria recorded. Selection of numerical coupling methods and primary-source research remain prerequisites to implementation. |
| G1 architecture | Codex | PASS | Proposed plan separates physical intent from generated grid; states overlap policy, capability rejection, revision invalidation and shared GH/native ownership. Implementation contracts remain future work. |
| G2 software/reliability | Codex | PASS | Documentation diff and local links checked; no production code changed. Runtime tests are not applicable to this diff. |
| G3 numerical physics | Codex | PASS | Documentation limits checked: current fixed 2:1 scope retained; 10:1 is a target; interface/conservation and uniform-fine comparisons required before claims. No numerical tests run. |
| G4 UI/UX and examples | Codex | PASS | Proposed workflow includes units, requested/actual resolution, preview, budgets and cancellation. A19 is explicitly proposed; no definition or video claimed complete. Live Rhino checks are not applicable. |
| G5 release/integration | Codex | NOT APPLICABLE | No release, package or website update requested. |

## Results and follow-up

`git diff --check` and a local Markdown link check passed. No Rhino session,
unit suite, numerical run, screenshot or video was needed for this documentation
change. No existing definitions were modified. Combination coverage is specified
in B08 and A19 for future execution; it has not been measured. The implementation
owner is unassigned; numerical design and supported ratios must be resolved before
scheduling delivery. This record approves only the backlog documentation.
