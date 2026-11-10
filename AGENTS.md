# Hawa agent entry point

Hawa is an experimental embedded CFD plugin for Rhino 8 and Grasshopper.

## Project records and document hygiene

- Read [features.md](features.md) and the relevant [GitHub issues](https://github.com/range-et/hawa-cfd/issues)
  before planning work, alongside the quality gates below. GitHub Issues is the
  source of truth for bugs, verification gaps, features, build/CI work and research.
  `issues.md` is a retired migration pointer; never add active entries there.
- Keep [the roadmap](docs/roadmap.md) for direction and
  [the example catalogue](docs/example-roadmap.md) for reference candidates.
  Track actionable work, priorities, owners and status in GitHub issues. Link to
  detailed specifications and gate records instead of maintaining duplicate backlogs.
- Create newly found bugs or hypotheses in GitHub with evidence/repro, scope,
  execution surface, owner (or unassigned), next action and completion criteria.
  Search for duplicates first. Preserve existing HAWA IDs on migrated issues;
  new work uses GitHub issue numbers, not newly allocated HAWA IDs.
- Update the linked issue and applicable feature/review records in the same work.
  Close an issue only when its declared acceptance criteria are met. A partial PR
  must use a reference (not an automatic closing keyword) and leave remaining scope
  open. Record the outcome, evidence, device/host omissions and release status;
  link completed capabilities from features history. Record rejected decisions
  without calling them built features. See [the workflow](docs/github-issues.md).
- Keep feature claims bounded by actual implementation and review evidence.
  Separate built, verified, packaged and released; record devices, omissions and
  limits. Historical tests are not fresh passes. Read newer follow-ups before
  reopening an older repaired finding.
- Preserve existing user edits and unrelated active work. Keep these registers
  concise, update entries in place, and check local links after documentation
  changes. Do not copy session transcripts or large logs into the registers.

Before changing or reviewing Hawa, read [docs/quality-gates.md](docs/quality-gates.md).
Assess research, architecture, software reliability, numerical physics and UI/UX
as separate evidence gates. G6 also requires the versioned compatibility matrix and public-node/example coverage; see [docs/compatibility-matrix.md](docs/compatibility-matrix.md). Use [the review record](docs/review-record-template.md)
and [example coverage matrix](examples/grasshopper/VERIFICATION.md). Record actual
reviewers, checks and omissions; a persona name or a skipped check is not a pass.

For operating the installed plugin through **Rhino MCP only**, read
[docs/agents/rhino-mcp.md](docs/agents/rhino-mcp.md), then
[examples/grasshopper/README.md](examples/grasshopper/README.md).
For the 0.5 native panel and public shared-case API, also read
[docs/agents/native-prototype.md](docs/agents/native-prototype.md) and the
[0.5 native guide](docs/native-v0.5.md).
For state ownership, failure handling and GH scheduling rules, read
[docs/architecture-v0.5.md](docs/architecture-v0.5.md).
These workflows use native Hawa components and Rhino's embedded Python runtime.
They do not require a separate Python process, shell access, browser automation,
or direct access to private embedded-runtime fields.

## Repository working rules

- Preserve user geometry, documents and edits. Example 09 is a modified legacy
  Galapagos definition; do not regenerate, overwrite or include it in release
  packages. Use example 10 for supported asynchronous hull search.
- Treat solver output as experimental. Read the release notes and moving-surface
  limits before reporting forces or coefficients. PorousMedium CPU/MPS parity
  remains unresolved. Do not relax comparison tolerances to hide a difference.
- Keep the Python production code compatible with Python 3.9 and the pinned
  PyTorch dependencies. MPS is PyTorch's Apple backend; MLX is not a backend here.
- Use cooperative pause/cancel and document disposal. Never kill Rhino to
  restart it. Quit through Rhino's normal application command when a restart is
  needed. Do not replace a loaded plugin assembly.
- Keep heavy work off the Grasshopper solution thread. Poll background jobs;
  do not wait in a C# loop, sleep on the UI thread, or use `.Wait()` / `.Result`
  on an unfinished task.
- Preserve functional object IDs, wires, parameter values and archive
  compatibility when improving example presentation. The annotation script
  checks connections and keeps local backups. Run it after regenerating examples.
- Original Hawa code is GPL-3.0-only. Preserve bundled upstream license notices.
- Report what was actually run, including device, steps and skipped checks.
  A rendered field is not a convergence or engineering-accuracy result.

## Product boundary

A tutorial request does not authorize a new public node by default. Use ordinary
Grasshopper assemblies for example geometry and recipes. Promote a component only
when it represents a reusable solver/data operation or an explicitly scoped
numerical service, with a defined contract and verification. The hull construction
is example 10, not a Hawa tool. Its hidden archive reader exists only to preserve
older user definitions. See [the node audit](docs/node-catalog-v0.5.md).

## Developer checks

For code changes, run the [function coverage gate](docs/function-testing.md) and
refresh its committed matrix. New functions and changes to uncovered functions
need measured tests; imports and a named test alone do not count. Keep historical
coverage debt visible and use the base-commit baseline for PR checks.

Use the repository's `.venv/bin/python` for local development commands. Test
changes with the relevant tests, then the Hawa suite. Run the native verification
scripts through Rhino MCP for changes to Grasshopper behavior. Paths in C# helper
scripts must be adjusted for a different checkout.

Build with `scripts/build_plugin.py`. It includes source and supported examples.
The installed-user workflow is documented separately from this developer build.

Shared-state changes also require `dotnet run --project tests/dotnet/StateContracts`
(test host: .NET 10; plugin target: .NET 7). These tests link production service
source against host/transport doubles. They do not replace live GH scheduling
checks in `scripts/verify_state_hardening.cs` and `scripts/verify_binding_callbacks.cs`.
