# GitHub issue migration crosswalk

Migration date: November 10, 2026. This fixed audit maps the **38 active entries**
from [the retired register snapshot](https://github.com/range-et/hawa-cfd/blob/723117501d3787692d5364fca5854b0a584181f5/issues.md)
to GitHub. It is not an active status list; use the linked issues for current
scope, ownership, dependencies and closure. Closed legacy IDs were not reopened.
No GitHub assignees, priorities or milestones were inferred.

| Legacy ID | GitHub issue |
| --- | --- |
| HAWA-001 | [#11 — Resolve PorousMedium CPU/MPS numerical disagreement](https://github.com/range-et/hawa-cfd/issues/11) |
| HAWA-002 | [#12 — Qualify Windows CUDA and clean Rhino installation](https://github.com/range-et/hawa-cfd/issues/12) |
| HAWA-003 | [#13 — Qualify physical-viscosity atmospheric scaling](https://github.com/range-et/hawa-cfd/issues/13) |
| HAWA-004 | [#14 — Qualify general external-boundary accuracy and reflection](https://github.com/range-et/hawa-cfd/issues/14) |
| HAWA-005 | [#15 — Validate engineering loads against reference cases](https://github.com/range-et/hawa-cfd/issues/15) |
| HAWA-006 | [#16 — Improve embedded Python/PyTorch installation and recovery](https://github.com/range-et/hawa-cfd/issues/16) |
| HAWA-007 | [#17 — Add movable vector slices across native and Grasshopper views](https://github.com/range-et/hawa-cfd/issues/17) |
| HAWA-008 | [#18 — Build drone and small-boat onboarding examples](https://github.com/range-et/hawa-cfd/issues/18) |
| HAWA-009 | [#19 — Support user-defined local refinement regions](https://github.com/range-et/hawa-cfd/issues/19) |
| HAWA-010 | [#20 — Reuse physical cases across numerical methods](https://github.com/range-et/hawa-cfd/issues/20) |
| HAWA-011 | [#21 — Complete neutral-atmosphere delivery and qualification](https://github.com/range-et/hawa-cfd/issues/21) |
| HAWA-012 | [#22 — Evaluate a bounded particle-method liquid workflow](https://github.com/range-et/hawa-cfd/issues/22) |
| HAWA-013 | [#23 — Evaluate an external finite-volume CFD adapter](https://github.com/range-et/hawa-cfd/issues/23) |
| HAWA-014 | [#24 — Profile bottlenecks before considering native acceleration](https://github.com/range-et/hawa-cfd/issues/24) |
| HAWA-015 | [#25 — Scope free-surface boats and powered propulsion](https://github.com/range-et/hawa-cfd/issues/25) |
| HAWA-021 | [#26 — Qualify nested atmospheric transfer statistics](https://github.com/range-et/hawa-cfd/issues/26) |
| HAWA-022 | [#27 — Qualify long-window boundary stability and turbulence](https://github.com/range-et/hawa-cfd/issues/27) |
| HAWA-026 | [#28 — Retire measured Python and C# function coverage debt](https://github.com/range-et/hawa-cfd/issues/28) |
| HAWA-027 | [#29 — Reproduce missing cells at domain and obstacle boundaries](https://github.com/range-et/hawa-cfd/issues/29) |
| HAWA-028 | [#30 — Complete domain relationship and pre-job host validation](https://github.com/range-et/hawa-cfd/issues/30) |
| HAWA-029 | [#31 — Make native startup domain creation opt-in](https://github.com/range-et/hawa-cfd/issues/31) |
| HAWA-030 | [#32 — Audit native views and define Grasshopper handoff](https://github.com/range-et/hawa-cfd/issues/32) |
| HAWA-031 | [#33 — Inspect and export computational cell geometry](https://github.com/range-et/hawa-cfd/issues/33) |
| HAWA-032 | [#34 — Preserve completed results as durable Rhino artifacts](https://github.com/range-et/hawa-cfd/issues/34) |
| HAWA-033 | [#35 — Export usable numerical results with units and provenance](https://github.com/range-et/hawa-cfd/issues/35) |
| HAWA-034 | [#36 — Clarify parent/child domain roles in Grasshopper](https://github.com/range-et/hawa-cfd/issues/36) |
| HAWA-035 | [#37 — Explain solver choices and enforce compatible options](https://github.com/range-et/hawa-cfd/issues/37) |
| HAWA-036 | [#38 — Visualize boundary assignments with arrows and labels](https://github.com/range-et/hawa-cfd/issues/38) |
| HAWA-037 | [#39 — Run sequential nonblocking Rhino integration checks](https://github.com/range-et/hawa-cfd/issues/39) |
| HAWA-038 | [#40 — Define pressure, load and coefficient analysis workflows](https://github.com/range-et/hawa-cfd/issues/40) |
| HAWA-039 | [#41 — Publish searchable versioned user documentation](https://github.com/range-et/hawa-cfd/issues/41) |
| HAWA-040 | [#42 — Evaluate non-destructive multipart geometry classification](https://github.com/range-et/hawa-cfd/issues/42) |
| HAWA-041 | [#43 — Scope multiple inflows and masked vector forcing](https://github.com/range-et/hawa-cfd/issues/43) |
| HAWA-042 | [#44 — Scope thermal transport, buoyancy and heat transfer](https://github.com/range-et/hawa-cfd/issues/44) |
| HAWA-043 | [#45 — Pilot stronger automated verification beyond coverage](https://github.com/range-et/hawa-cfd/issues/45) |
| HAWA-044 | [#46 — Qualify strict CUDA suite acceptance on Windows](https://github.com/range-et/hawa-cfd/issues/46) |
| HAWA-045 | [#47 — Qualify CUDA evidence source provenance on Windows](https://github.com/range-et/hawa-cfd/issues/47) |
| HAWA-046 | [#48 — Verify actual-device assertions on Windows CUDA](https://github.com/range-et/hawa-cfd/issues/48) |

Each issue preserves type/status, scope/evidence, next action/acceptance and the
per-issue execution/dependency assessment. Relative evidence links were converted
to commit-pinned repository links and their file paths verified. HAWA-001/026
include the later PR #9/#8 increments from the integration branch; neither is
closed by those partial increments. Historical routing text is labelled as such.

Migration verification compares all 38 published titles, bodies and labels with
the prepared payloads and checks a one-to-one legacy-ID mapping with no duplicates.
The repository change is documentation/templates only; no fresh solver, hardware,
host or numerical pass is claimed. G0/G1/G2 are scoped document/provenance checks;
G3/G4/G5/G6 runtime, physical, release and compatibility gates are not applicable.
Reviewer: Codex primary agent, self-review; no independent reviewer claimed.
