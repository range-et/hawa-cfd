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
| G2 | Codex issue39 | PASS | 1848 Python 3.9 tests, strict headless/base ratchet, actual SDK compile and reviewed mutation study; limits below. |
| G3 | Codex issue39 | NOT APPLICABLE | Tooling only; intended runs are workflow smoke checks. |
| G4 | Codex issue39 | PASS for declared pilot | Two fresh CPU 31/32 runs, four inspected captures, active cancellation and zero-resource cleanup. Full gallery/native coverage remains open. |
| G5 | Codex issue39 | NOT APPLICABLE | No release/install; existing build includes tool source. |
| G6 | Codex issue39 | NOT APPLICABLE | No node, archive, field format, shared state or supported-combination change. |

## Live evidence and retained failures

Rhino 8.37.26307.15002, macOS, process 17334, MCP `aardvark` port 10502.
Initial discovery returned no slots; one spawn attempt timed out on 10500. User
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
or bypass injected-document identity. Root subsequently activated the original native window; its GH filter became correct without overrides. The final pilot then completed the two-run criterion, as recorded below.

Original millimetre units were restored; a backup is
`results/pilot-original-empty-backup.3dm`. Original native serial 268435460 and
empty GH `f0ff2856-9daa-4829-b909-082f21a0fcb3` were preserved. Manual setup and
recovery are separate from the runner's read-only native contract. Those setup attempts did not establish an example or visual pass; the successful
bounded follow-up below supplies that evidence. Physical accuracy and full
gallery coverage remain unverified.

## Automated evidence

Final commands/counts are recorded after source freeze below. An initial full
measurement was intentionally interrupted to improve mutation-discovered tests;
it is not a pass. Python 3.9 remains authoritative; Python 3.12 is developer evidence.
Adapter compilation targets .NET 7 with installed Rhino/GH references: zero errors,
two System.Drawing platform warnings requiring live capture verification.
C# maintainer script execution is not credited as product function coverage.

Remaining #39: full-gallery composition, native lifecycle/Undo/Redo harnesses, and Windows/device coverage. Checkpoint file actions in 31 are not part of this pilot. Keep #39 open.

## Successful bounded host follow-up

After root restored actual native window activation, fresh runs f and g both
completed sequential CPU 31/32 on unchanged final runner source. 31: 60 steps,
21×16×16, t=1.7320508075688776s, three valid velocities/pressures and lines;
32: Record 40/40, Playback t=1.154701s, valid body with 54 vertices/24 faces. Probe values
agreed across the repeats. All four perspective zoom-extents captures were
inspected: domain/body/three vectors in 31; domain/moved body/pivot in 32. These
are workflow observations, not an accuracy or field-convergence assessment.

Run h changed only its copied 31 target to 1,000,000, observed running 37 steps,
then requested controller cancellation without an observe reply. It disposed
only the owned graph and ended failed/Cancelled by operator as intended. Fresh
audits after every example and cancellation found zero jobs, sessions, Hawa
workers, cleanup requests and refreshes. Original archive hashes stayed equal.
Original native model returned to millimetres with 0 objects; its dirty flag was
retained. Original GH graph returned active, empty and unmodified.

[Compact machine evidence](verification-host-acceptance-pilot.json) retains exact
run IDs, hashes, cleanup counts, screenshot paths/hashes and scope. Setup recovery
was external to the runner; no claim that the pilot automatically repairs native
window targeting. 26 focused tests pass on both Python 3.9 and 3.12; controller/audit
line coverage 147/147 and branch coverage 62/62. Mutmut 3.7.0: 590 mutants, 552 assertion
kills, 38 reviewed survivors, zero timeout/error outcomes. The policy explicitly
retains case-sensitive-filesystem and diagnostic/help gaps; it is not all-killed.

## Ownership publication race follow-up

Independent review by the issue83 agent identified cancellation before ownership
publication as a possible orphan path. Commit `17046e5` routes every uncertain
open through close and cleanup. The adapter recovers its per-run host reference
even when the request has no owned ID, and checks supersession before registering
the graph. Rhino MCP callbacks execute serially on the UI thread; a close queued
after an in-flight open sees its reference, while a stale open queued after close
fails its sequence check. A regression test covers late ownership and prohibits
terminal completion until a clean audit. Independent re-review found no remaining
concrete finding. Fresh SDK compilation passed; the final mutation study has 590
mutants, 552 assertion kills and the same 38 reviewed survivor diffs. Earlier live
runs f/g/h retain their original source hashes and are not relabeled as this fix.

Post-repair live run i on the combined candidate (PID 34800) opened an owned
CPU graph, then deliberately cancelled without consuming its reply or ownership
record. The close request carried no owned ID. The adapter recovered and disposed
the host reference; the fresh audit found zero jobs, sessions, workers, cleanup
requests and refreshes. Terminal failed/Cancelled by operator was expected.
No Run toggle was enabled. Original native serial 268435457 returned to millimetres
with zero live objects and its dirty flag retained; both original blank GH graphs
were preserved unmodified and the original canvas restored. This validates late
ownership reconciliation, not a deterministic concurrent UI scheduling race.

Final measured Python 3.9 suite: 1848 passed, 87 skipped, 213 warnings; linked
.NET state contracts passed. New controller/audit execute 147/147 lines and 62/62
branches. The committed matrix records all source rows, including 361 unmeasured
host functions. Strict headless and base-commit ratchet checks use the fresh c
measurement. MPS access was exclusively leased; concurrent other-agent CPU
mutation/host checks mean these timings are not performance evidence. The full
Python 3.12 suite is delegated to the combined integration gate; 26 focused
3.12 controls passed here. Final developer ZIP built successfully without install.

The [final integration review](review-issue-batch-98-83-39.md) records the delegated
full Python 3.12 pass and combined coverage; the branch measurements above retain
their original scope and counts.

## PR 112 corrupt ownership follow-up

Greptile comment 4595057470 identified direct ownership publication as a
cancellation blocker if its JSON was interrupted. The adapter now writes a
same-directory temporary file and atomically renames it. The CLI treats unreadable
or malformed same-run ownership as uncertain, stops normal work through close,
and lets close/cleanup finish using the retained host reference. Foreign run IDs
still reject without changing state. Recovered UUIDs are validated and normalized
for the .NET parser. Independent issue83 review caught malformed GUID and URN
format cases, both repaired; final re-review found no remaining concrete finding.

46 focused tests passed on Python 3.9 and 3.12, including actual CLI cancellation
and normal polling, malformed files/IDs, foreign identity, and cleanup completion.
Targeted coverage is 162/162 lines and 70/70 branches. Actual SDK compilation
passed with the same two drawing-platform warnings. Fresh mutation f: 642 total,
600 assertion kills, 42 reviewed survivors, no errors/timeouts. The discarded e
run detected a changed source hash during review and is not counted. The full
measured suite and committed matrix will be refreshed on the integrated branch.

Live run j (`869bb748daf342b9baf4a51786043764`) verified valid atomic ownership
publication, then deliberately truncated that file before actual CLI `poll
--cancel`. The close request had no owned ID, recovered the per-run host reference,
and disposed its copied CPU graph. Subsequent CLI polling completed while the
file remained corrupt; the fresh audit found zero jobs, sessions, Hawa workers,
cleanup requests and refreshes. Terminal failed/Cancelled by operator was expected.
No Run toggle was enabled. Native serial 268435457 returned to millimetres with
its dirty flag retained and zero live objects. Both original blank GH documents
remained unmodified and the original canvas was restored. No installation changed.
