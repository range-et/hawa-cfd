# Numerical export completion — #35 / HAWA-033

Date: November 17, 2026. Base: merged main `12dc774`.
Status: implementation and verification in progress; no completion or release claim.

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
