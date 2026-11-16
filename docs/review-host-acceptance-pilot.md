# #39 sequential acceptance pilot review

November 16, 2026. Author/reviewer: Codex issue39 agent (self-review); root agent
reviewed ownership/lost-response hazards. Base `1b4e6c7`. Scope is tooling for
examples 31/32, with no runtime dependency, public node, physics or tolerance change.

Criteria fixed before execution: two successive CPU pilot runs, valid numerical
and mesh outputs, fresh provenance, cooperative failure/cancel recovery,
owned-only disposal, zero jobs/sessions/Hawa workers/cleanup/refreshes and
preserved user content.

| Gate | Reviewer | Decision | Evidence |
| --- | --- | --- | --- |
| G0 | Codex issue39 | PASS | Existing MCP workflow and official GH API; bounded [guide](host-acceptance-pilot.md). |
| G1 | Codex issue39, root review | PASS for controller | Run/sequence identities, deadlines, explicit scratch serial, durable ownership, no host waits; actual window behavior remains separate. |
| G2 | Codex issue39 | Pending final gates | Focused asserting tests and actual SDK compile; final measured/mutation evidence below. |
| G3 | Codex issue39 | NOT APPLICABLE | Tooling only; intended runs are workflow smoke checks. |
| G4 | Codex issue39 | BLOCKED | Live preflight/failure cleanup exercised, but two successful workflows and visual acceptance are not established. |
| G5 | Codex issue39 | NOT APPLICABLE | No release/install; existing build includes tool source. |
| G6 | Codex issue39 | NOT APPLICABLE | No node, archive, field format, shared state or supported-combination change. |

## Live evidence and retained failures

Rhino 8.37.26307.15002, macOS, process17334, MCP `aardvark` port10502.
Initial discovery returned no slots; one spawn attempt timed out on10500. User
routing guidance enabled readoption of the existing host. No process was killed
or assembly replaced. Installed `plugin.py` and `jobs.py` hashes match base source.
Initially there was an unnamed empty millimetre native model and an empty GH
definition, with no jobs/sessions/workers.

- `results/host-pilot-20261116-b`: preflight refused the native dirty flag after
  manual unit setup. Script history can mark it dirty. Final runner requires
  explicit scratch serial and records/preserves the flag; it never clears it.
- `...-c`: initial adapter assumed a device panel; the example uses persistent
  input instead. Failure was retained and owned cleanup reached zero resources.
  Final adapter sets only unconnected device inputs on copied definitions to CPU.
- `...-d/e`: filtered GH enumeration hid registered copies. GH's active-document
  filter excluded every graph despite reported matching native associations.
  Geometry remained `voxelizing`, not a successful run. Temporary native
  creation/activation during manual setup is a candidate cause, not a reproduced
  Hawa defect. Original empty GH definition remained in `AllDocuments`; owned
  diagnostic copies were removed using that inventory. Final adapter checks
  registration before a solution and retains its own teardown reference.

Normal Open of an owned empty `.3dm` activated a new native serial while MCP
continued targeting the original. A subsequent normal Close call did not return;
initial desktop inspection found no modal dialog in the active scratch window.
Its awaiting orchestration was terminated without signalling Rhino. Root then
selected the original Untitled tab, found a pending inline File path prompt and
clicked Cancel. No save, close or discard occurred; original window became active.
The command had targeted the injected original rather than the visible scratch.
This is a harness/window-targeting blocker, not a reason to override GH's filter
or bypass injected-document identity. The two-run criterion remains unverified.

Original millimetre units were restored; a backup is
`results/pilot-original-empty-backup.3dm`. Original native serial268435460 and
empty GH `f0ff2856-9daa-4829-b909-082f21a0fcb3` were preserved. Manual setup and
recovery are separate from the runner's read-only native contract. No completed
example, physical accuracy, full gallery or successful visual pass is claimed.

## Automated evidence

Final commands/counts are recorded after source freeze below. An initial full
measurement was intentionally interrupted to improve mutation-discovered tests;
it is not a pass. Python3.9 remains authoritative; Python3.12 is developer evidence.
Adapter compilation targets.NET7 with installed Rhino/GH references: zero errors,
two System.Drawing platform warnings requiring live capture verification.
C# maintainer script execution is not credited as product function coverage.

Remaining #39: two successful runs and cancellation recovery on a correctly
targeted host, numerical/image inspection, full-gallery composition and native
lifecycle/Undo/Redo harnesses. Keep #39 open.
