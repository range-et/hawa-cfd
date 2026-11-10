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

## Re-scope and close

An issue whose declared criteria cannot all be met in the current round can be
closed after an explicit re-scope instead of staying open indefinitely. This needs
maintainer approval, recorded on the issue. The closing comment lists each
acceptance item as passed, failed, or unsupported-guarded, with evidence links.
Failed items move to one linked follow-up issue that copies the failing evidence
and any new items found. `features.md` claims only the passed items. A follow-up
that is itself re-scoped again must either narrow its scope or record an explicit
"accept limitation" decision. Re-scoping never changes a tolerance or criterion
after results are known. That is a separate method change, which needs its own approval.

## Device qualification protocol

1. **Develop on CPU.** One branch and one commit are shared by every device. Build
   a CPU FP64 reference and, where possible, a CPU proxy of each device's precision
   path (e.g. forcing the FP32-only path). Device machines run that commit; they
   only change device-specific code paths, and those changes return through the
   same branch.
2. **Declare the comparison before running.** For each case, state its class:
   `bitwise`, `bounded` (stated error limit) or `statistical` (means, RMS or
   spectra within confidence bounds). Compare every device to the CPU FP64
   reference, not CUDA to MPS. Changing a class or limit after results is a
   criteria change.
3. **Finish CPU work first.** Tests, 100% line coverage, targeted mutation testing
   and the PR come before device runs.
4. **One batched device round per merged commit.** CUDA and MPS run in parallel on
   the same merged `main` commit, tracked in one issue per device per round (e.g.
   #52 and #53). Each run posts a machine-generated manifest (commit, source hash,
   device, driver or macOS, PyTorch, dtype, seeds, wall time, overlapping jobs) with
   raw results. Exploratory device sessions are allowed while debugging, but only
   the merged commit's results count as qualification.
5. **Device smoke gate.** Every PR that touches numerics passes the device smoke
   gate ([#57](https://github.com/range-et/hawa-cfd/issues/57)): CPU mode in CI, and
   CUDA and MPS modes in the batched round. Re-run it after driver, macOS or PyTorch
   upgrades.
6. **One owner reconciles.** The issue owner reads every device result against
   CPU and marks each box passed, failed, or unsupported-guarded. Unsupported-guarded
   means a runtime guard refuses or labels the device for that feature; an unguarded
   known discrepancy is a failure. Then close the issue, or re-scope and close it
   as described above. Close the round's device trackers and open the next round's.

## Completion

On completion, record the outcome and evidence in the issue and applicable feature
history, then close the issue. For rejected work, explain the decision and close
as not planned rather than calling it implemented. Do not duplicate the open backlog
in Markdown. The [migration crosswalk](github-issue-migration.md) is a fixed audit
record, not a status register.
