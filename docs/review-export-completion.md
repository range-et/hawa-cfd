# Numerical export completion — #35 / HAWA-033

Date: November 17, 2026. Base: merged main `12dc774`.
Status: implementation and local verification complete; PR/CI/Greptile and Windows CUDA gates pending. No merge or release claim.

## Fixed scope and acceptance contract

Complete probe/load CSV interchange and the supported native export workflow.
Reuse the existing solver samples and prescribed-motion loads; do not change
numerical methods, tolerances, force models or native case ownership. Baking is
separate (#34). Native cases are stationary block/selected-geometry cases;
native field/probe export and Grasshopper moving-load export are the supported
surfaces. Native moving-case creation is not introduced by this work.

The existing explicit `op=export, format=csv` request gains `table=probes` and
`table=loads`; omitted table retains fields. NPZ default routing and the field
CSV marker/header remain compatible. Each new table has a versioned marker and
one JSON preamble declaring columns, row count, units and provenance. Publication
remains one atomic UTF-8 file. All CSV writers reserve the canonical destination
while capturing/writing so native and GH callers cannot publish competing files
to the same path. Failure/cancellation before replacement preserves the old file;
cancellation after publication cannot undo a completed replacement.

Probe requests contain 1–10,000 lattice points. Preserve input order and duplicate
points; retain invalid/outside samples as rows with explicit validity and blank
flow quantities. Include lattice coordinates and reconstructed physical world
positions, domain-axis velocity, pressure and density. Reuse the existing bounded
sampling rule and declare it; interpolation is not a new physical-accuracy claim.
GH converts model points with its existing coordinate adapter. Native point
selection freezes document units and the accepted case mapping before submission.

Loads export the retained prescribed-body history, up to its existing 10,000-step
capacity and four bodies. Empty history is rejected instead of inventing loads.
Each row identifies its body, local/absolute time, dimensional domain-axis force,
torque, signed fluid-work power and the instantaneous torque pivot. Reconstruct
historical pivots at each row's time, not from the latest pose. State retained
time coverage and possible truncation; capture-time quality is not historical
sample qualification. Density/speed/pressure references are recorded, while
coefficient area/length and nondimensional coefficients are not invented. Body
IDs use a declared lossless JSON-string encoding in their CSV cells.

Capture arrays/history, case, quality and source identity under the session lock.
Return an artifact ID and actual session/case hash/iteration/local and absolute
times with the output path. Optional expected case hash, iteration and state
must match under that lock before writing. Native document/case/revision/
generation/version attribution is frozen caller context, not a replacement for
the backend's actual capture identity.

Native export accepts a healthy paused or completed case, has separate service-owned job,
status, error and result state, and does not reuse the preview query. Export/Cancel
controls, destination selection and selected probe count must be usable without
blocking Rhino. Cancel/reset/physical edits/disposal invalidate ownership before
bridge cleanup; panel closure retains the service-owned task. Malformed or stale
completion cannot be shown as a successful current export. Export failures do
not turn a healthy solver or preview into a fault.

Grasshopper keeps Checkpoint's GUID, first four inputs and Report output. Append
one optional Points input and explicitly migrate old archives. Add `export probes
csv` and `export loads csv` operations. A changed/missing source or request cancels
the retained operation and requires re-arming; Execute=false cancels pending work.
Completed reports retain the identity of the actual capture.

## Evidence required before closure

- Exact CSV readback against frozen raw data; rotated/scaled/2D probes, invalid
  samples, arbitrary body IDs, load signs and historical pivots/time coverage.
- Failed, incomplete, cancelled and contending publication; expected-identity
  mismatch must preserve prior bytes and leave no temporary/reservation leak.
- Native/GH state contracts: stale/malformed completion, replacement/disposal,
  separate preview/export jobs, input re-arm, old archives and non-metre mapping.
- Fresh measured Python/.NET function and line coverage, applicable mutation
  policies, full suites, bounded compatibility product and package checks.
- Sequential live Mac Rhino workflows, including successful native field/probe
  and GH moving-load readback, cancellation/failure/recovery and zero owned work
  after cleanup. Preserve user documents and legacy example 09.
- Frozen-source headless CUDA suite/smoke/G6 via Hawa c110p. Windows Rhino stays
  closed while Mac holds the only license. Device evidence is separate from host
  behavior and full-duration physical qualification.
- Ready PR, all final-head CI gates, explicit Greptile 5/5, then merge and #35
  closure. No skipped check or named reviewer alone counts as a pass.

## Review ownership

Root coordinates contracts, integration, evidence and live Rhino work.
The numerical_exports agent owns Python interchange, domain_validation owns
native/shared lifecycle and UI, and atmosphere_qualification owns Checkpoint and
archive compatibility. Their initial audits were read-only design reviews, not
test execution. Final gate results and omissions will be recorded here.

## User-requested native workflow completion

Before the final freeze, the user requested dynamic native Setup/View controls
and Save data / Import data for both saved-result viewing and checkpoint resume.
Existing Solve controls already commit directly. Remaining display changes apply
without a separate Apply click; physical setup edits invalidate prior results but
never start a simulation. Paired periodic boundaries change atomically. Invalid
manual colour-range drafts must remain editable with a visible error while the
last accepted display stays intact; external state/version changes cannot silently
commit a stale draft.

Native Save data uses a single versioned, self-contained checkpoint artifact.
Import validates it before replacing the current case and restores a new owned
session paused, with zero advances. Existing field preview then displays saved
results; Run/Resume is explicit. This deliberately avoids adding a separate frame
registry lifetime or pretending CSV contains resumable populations. Imported
physical setup is read-only authoritative archived geometry. Missing original
Rhino object references cannot silently regenerate a different case. A saved
`.3dm` must retain the imported-source distinction and reopen idle, requiring data
import again before resume; solver tensors are not embedded in `.3dm`.

Additional acceptance: atomic/cancelled checkpoint save, bounded safe archive
validation, exact populations/fields/iteration/time/quality restoration, continued
run versus uninterrupted reference, failed/cancelled import preserving existing
case, stale completion/disposal cleanup, unit conversion, dynamic controls and
visible imported-state attribution. The final G6, full measured suite, CUDA and
host checks must include this extension. Earlier export-only passes are bounded
intermediate evidence, not the final-head gate.

## Final installed Mac host evidence

On production freeze `5ac088b`, root installed the official build after saving
and normally quitting Rhino. Rhino 8.37 / embedded Python 3.9.10 / torch 2.8.0
ran the native data, native export and GH export harnesses sequentially on CPU.
All passed; each cleanup audit found zero jobs, sessions and workers.
[Machine evidence and artifact hashes](verification-export-completion-host.json).

Native data exercised actual Eto events, dynamic fluid/periodic/view controls,
invalid range recovery, save, invalid/cancelled import preservation, paused import
with no advances, unit conversion, explicit resume and real `.3dm` reopen.
Independent readback matched all populations, mean arrays, quality and time at
6 and 12 steps against an uninterrupted CPU reference. Native export checked
1,989 field rows and three probes, cancellation, failed destinations and recovery.
GH examples31/17 retained original IDs/wires: 5,376 field rows (4,677 valid,
699 blank invalid), three probes and six load rows matched raw NPZ/history and
the independently calculated historical torque pivot.

Visual inspection confirmed the Export and Save/Import controls fit the dock;
the latter tab title truncates at this width, with readable page actions and
scrollable lower text. Native file pickers, Windows Rhino UI and a fresh full
31-example run/render gallery remain unverified. The read-only archive audit
covered all31 supported archives and53 public nodes; legacy09 was excluded.
Original Rhino/GH documents were restored from preserved copies.

The first complete expanded G6 run retained20 failures from a test-harness
relative-path assertion: the documented save response is an absolute path.
`2c43c74` fixes the oracle and adds all14 native-data cases with relative
fixture directories. No production behavior or tolerance changed; a fresh full
G6 rerun is required. Full measured coverage, final mutation review, CUDA, CI
and Greptile remain separate merge gates.

## Gate disposition

Review roles are actual agents, not independent human sign-off. Root performed
integration self-review and the live checks; domain_validation and
atmosphere_qualification cross-reviewed the native ownership changes.

| Gate | Reviewer | Status | Bounded evidence / remaining work |
| --- | --- | --- | --- |
| G0 research | root, numerical_exports | PASS | Contract fixed before measurement; existing sampler/load semantics, NPZ arrays and public Rhino/Eto operations reused; no new numerical method or dependency. |
| G1 architecture | domain_validation, atmosphere_qualification, root | PASS | Transactional import, separate operation ownership, paused/no-advance restore, stale completion and disposal contracts;146 linked state contracts plus live ownership/cleanup/reopen checks. |
| G2 reliability | numerical_exports, domain_validation, root | PASS |2256 tests passed87 explicit skips;146 C# contracts. Strict headless function/line gate and trusted-base ratchet pass:511 Python and582 C# covered functions;299 host functions remain unmeasured. Python3.12:2246 passed97 skips. All four applicable mutation policies pass. |
| G3 numerical implementation | numerical_exports, atmosphere_qualification, root | PASS, bounded CPU/MPS implementation | Exact raw CSV/NPZ and independent continuation checks; CPU/MPS compatibility and both5-case smoke gates pass. No physical validation or unrestricted hardware claim; CUDA still required for merge. |
| G4 UI/UX | root | PASS, focused Mac workflow | Actual dynamic events and dock inspection; file dialogs, Windows UI and full-gallery run/render omitted as listed above. |
| G5 integration | root | BLOCKED | Official package built/installed; ready PR, final CI/Greptile5/5 and CUDA pending. Not released. |
| G6 compatibility | atmosphere_qualification, root | PASS locally; CUDA BLOCKED |102,582 rows recorded:100,092 CPU/MPS/structural passes,0 failures,2,490 CUDA rows blocked; source hashes stable.53 public nodes/31 archives audited. [Machine evidence](verification-compatibility.json). |

Fresh full G6 rerun `results/compatibility-export-complete-v4` passed every available
row, including54 CSV and28 native-data CPU/MPS rows. CUDA is explicitly blocked
on this machine. The CPU device smoke also passed all5 comparisons; final MPS
smoke is queued after the measured suites.

Measured production-parity run: `results/function-coverage-export-complete`,
Python3.9.25,2256 passed/87 skipped,146 C# contracts. Skips:85 unavailable CUDA,
one unsupported MPS float64 and one mutmut requiring the3.12 developer environment.
Warnings include dependency deprecations, the deliberate duplicate-ZIP fixture
and existing experimental upstream MRT notices; none is silently counted as a pass.
The strict headless check includes executable lines and used trusted base
`12dc774`; the refreshed committed matrix preserves299 unmeasured host functions.

Developer Python3.12.4 suite:2246 passed/97 explicit skips (production-Python
entrypoints remain3.9-only; accelerator availability remains explicit),216
warnings. The3.9 run above is authoritative. Both suites completed successfully.

The first final MPS smoke executed all5 cases successfully, but its overall gate
failed because this review record changed during its whole-tree source audit.
That run is retained as invalid evidence. A fresh run with the entire checkout
frozen is required; no numerical tolerance or production change is involved.

The frozen-checkout MPS rerun `results/device-smoke-export-complete-mps-v2`
passed all5 cases with identical before/after source audit and no module-path
errors. CPU smoke likewise passed5/5. [Final headless evidence](verification-export-completion-headless.json).
All local required checks are complete. PR#119 is ready/non-draft. Merge remains
blocked until final CI, explicit Greptile5/5 and Windows CUDA are verified.

## Frozen PR #119 Windows CUDA handoff — 2026-11-17

The Windows operator received the [exact-head handoff on #35](https://github.com/range-et/hawa-cfd/issues/35#issuecomment-6941958822)
and tested `6eb8a5c0950f4148e39e11bcbbbccf206a4f7858` in a fresh isolated LF worktree.
Direct chat delivery was unavailable; the agreed GitHub issue channel carried
acknowledgement, progress and results. Original Windows checkouts, environments
and previous evidence were preserved. No implementation, test, policy or
tolerance changes were made during this round.

Environment: Windows build 26300, NVIDIA RTX 5070 Ti, driver 621.14,
Python 3.9.25, torch 2.8.0+cu128, CUDA runtime 12.8, NumPy 2.0.2 and
pydantic 2.13.5. A real backend operation selected `cuda:0`; loaded Hawa/Lettuce
modules came from the tested checkout. GPU jobs ran sequentially.

| Fresh Windows check | Result |
| --- | --- |
| Complete Hawa suite | **2,251 passed, 92 skipped, zero failed**; 214 warnings, 262.15 seconds |
| Explicit CUDA suite cases | **91 passed**, zero failed/skipped |
| Device smoke vs CPU FP64 | **5/5 passed**, zero guarded; unchanged sources and no foreign modules |
| Finite G6 | **100,092 passed, zero failed**, 2,490 unavailable MPS rows blocked; 312.52 seconds |
| CUDA G6 rows | **2,490 passed**, zero failed/blocked |
| New CUDA export product | **27/27 pass**: seven raw readback successes, 20 expected rejections/cancellations |
| New CUDA native-data product | **14/14 pass**: two exact continuation successes, 12 expected rejection/cancellation checks |
| G6 evidence and archive inventory | PASS: 102,582 rows, 53 public nodes, 31 examples, 188 observed port combinations |

The suite's independent collection and outcome/JUnit verifier cover all 2,343
tests. Skips are 90 unavailable MPS cases, one CPU-default check inapplicable when
CUDA exists, and one real-mutmut integration requiring developer Python. They
remain explicit omissions. All 110 mutation-policy source entries match their
exact raw-byte hashes; no line-ending normalization was applied to evidence.

Export rows compare literal schemas, captured raw fields, ordered/duplicate
probes, load histories, historical pivots, units, time, validity and provenance
using the independent matrix oracle. Stationary load export, stale identity and
pre-publication cancellation preserve the previous destination and reject as
declared; those are passing rejection contracts, not successful simulations.

Native-data rows cover voxel and curved walls. Valid cases save at step six,
restore paused with zero advancement, preserve exact populations/fields/means,
quality and mass baseline, and continue to step twelve matching uninterrupted
same-backend CUDA state exactly. Other rows verify stale source, save/import
cancellation, truncated ZIP, unsupported schema and corrupt populations. These
are headless Python service checks, not Windows native-panel or GH observations.

The [machine record](verification-pr119-windows-cuda-2026-11-17.json) retains exact
commands, source/index digest, environment, smoke comparisons, all 41 new CUDA
row outcomes, skip reasons and artifact hashes. Raw manifests, logs, independent
collection, JUnit, CPU/reference arrays, complete G6 rows and fixtures are under
`results/pr119-windows-cuda-2026-11-17/` in the isolated Windows worktree
`C:/Users/range/Desktop/hawa-cfd-pr119-cuda`; the record includes the complete ZIP
path, size and SHA256. Source/index snapshots stayed unchanged until all checks
and the final independent verifier completed. The subsequent commit adds only
documentation/evidence.

Reviewer/operator: Codex Windows agent, independently executing the Mac author's
frozen source. G2 passes the complete requested Windows suite; G3 passes the
existing bounded smoke and exact interchange/continuation contracts; G6 passes
the available CPU/CUDA product with MPS blocked. Existing G0/G1 and Mac measured,
mutation, C# and host records remain separately attributed above. This evidence
increment changes no executable functions and does not claim fresh Windows
coverage instrumentation, mutation execution or C# host qualification.

**Windows Rhino was never launched, attached to, initialized or run.** Mac retains
the sole license; any Windows host handoff requires explicit Mac-closed
confirmation. No plugin build, installation, release, merge, generated native
CUDA extension, long-duration physical qualification or expanded upstream
example run is claimed. `verify_cuda.py --stages suite --repeats 1` correctly
records its broader four-stage `full_scope` as false. These results clear the
requested Windows CUDA hold for this PR candidate; final CI, Greptile review,
merge and #35 closure remain with the Mac coordinator. Baking #34 is separate.
