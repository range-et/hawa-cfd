# Native data: save, inspect and resume

The native **Data** tab saves a complete Hawa checkpoint and imports it as a
paused result. Import does not advance the solver. The same file supports viewing
saved fields and explicitly resuming the simulation; it is not a CSV importer.
This development workflow supports Hawa's stationary, physical, axis-aligned 3D
native cases, including supported interpolated walls. Moving bodies, normalized
benchmarks, neutral-flow state, refinement and external boundary-file dependencies
are outside this format.

1. Pause or complete the accepted run. In Data, choose a new `.npz` destination
   and **Save data**. Wait for the saved artifact identity. Saving runs in the
   background; Cancel data operation cancels before publication when observed.
2. Choose that file and the import backend, then **Import data**. Validation and
   device allocation run in the background. A failed or cancelled replacement
   preserves the existing accepted case. Successful import replaces its owned
   solver session, preserves Rhino geometry and opens paused at the saved step.
3. Inspect the imported result with the dynamic View controls. Export fields or
   probes from the paused result without taking another step. Imported physics is
   read-only: it uses archived solver geometry, not missing original Rhino objects.
   Use Block preset or start a new geometry case for editable physical setup.
4. To continue, set a total target greater than the imported iteration and click
   **Run / Resume**. The target is an absolute iteration count. Importing or changing
   display settings never starts the run.

The data file is the durable solver state. Saving a Rhino `.3dm` stores the
imported source identity and physical bounds, not its populations. Reopening stays
idle and requires importing the data file again before viewing/resuming. Keep the
`.npz` with the Rhino project. No automatic loading of an external path is implied.

## Format and provenance

`hawa-native-data-1` is a compressed NumPy archive loaded with `allow_pickle=False`.
It contains `populations.npy` (FP32 D3Q19), `metadata.npy` (one JSON string), and,
when averaging samples exist, `mean_u.npy`, `mean_p.npy` and `mean_rho.npy`.
Metadata records the authoritative accepted case and hash, artifact ID, source
session/state, iteration, local/origin/absolute time, quality history, population
storage, Hawa version, averaging count and initial mass baseline. Native settings
and caller case/revision/generation/version attribution are separate context;
imported physical geometry comes from the authoritative case. The current local
case/session identity after import differs from the saved source identity.

Physical case quantities use SI units; model coordinates are mapped using the
saved physical spacing/origin and the current Rhino document units. Imported
geometry is not revoxelized. Quality remains the solver's bounded numerical-health
record, not convergence or engineering validation. Same-backend continuation has
its own exact checks; importing onto another device does not establish bitwise
cross-device equality or hardware qualification.

Before allocation, the reader checks member names and duplicates, expanded ZIP
size and NPY-declared shapes/types/byte sizes. The total expanded budget is 256 MiB;
metadata is capped at 16 MiB. It rejects malformed, nonfinite, inconsistent,
unsupported or incomplete archives before publishing a replacement session.
The writer applies the same budgets, reserves its destination against competing
CSV/data writes in this process, writes a sibling temporary, flushes/fsyncs and
atomically replaces the destination. Pre-publication cancellation or failure
preserves existing bytes. Cancellation after publication cannot undo a completed
write; parent-directory crash durability is not promised.

Existing GH Checkpoint `save`/`load`, raw field NPZ and recording formats retain
their own contracts. They are not silently guessed or converted by native Import
data. CSV is described in the [numerical export contract](numerical-export.md).
See the [completion review](review-export-completion.md) for exact test devices,
steps, omissions and release status.
