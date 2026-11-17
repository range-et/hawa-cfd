# Numerical field exports

Hawa exports instantaneous lattice fields, probe samples and retained moving-body
loads as explicit, versioned CSV tables. These are interchange files, not solver
checkpoints. Export does not establish convergence or engineering accuracy.

In Grasshopper, use the existing **Checkpoint** component with an absolute path,
choose `export csv`, `export probes csv` or `export loads csv`, then toggle Execute
false → true. Probe export requires 1–10,000 model-coordinate points on the new
optional Points input. The component retains its GUID, first four inputs and
Report output; old archives gain the optional input without rewiring. The report
contains the actual captured session, case hash, iteration, time and artifact ID.
Changing or disconnecting inputs cancels the retained action and requires another
false → true edge. Execute=false cancels pending work. Ordinary solver progress
does not replace an in-flight capture.

In Rhino's native **Export** tab, pause or complete a healthy case, choose fields or probes
and a destination, then Export CSV. For probes, select Rhino point objects and
Capture selected probes first; selection changes afterward do not change that
captured list. Probe coordinates and document units are checked against the
accepted stopped case. Cancel export is separate from solver and field-preview controls.
A panel closure leaves the service-owned export running. Physical changes/reset
invalidate export ownership. Native cases are stationary; use a moving-body GH
Solution and `export loads csv` for loads.

Python callers use `{"op":"export","session":"…","path":"…","format":"csv"}`.
`table` defaults to `fields`; use `probes` with `points` (lattice coordinates), or
`loads`. Path extensions never select a format. Omitted `format`, or `format=npz`,
keeps the raw NPZ contract. Unknown CSV options reject. Optional
`expected={case_hash,iteration,state}` must match exactly under the session lock;
native exports use this to require the selected paused/completed result. Optional
`attribution={case_id,revision,generation,version}` is frozen caller-declared
context, not solver-authoritative identity. Legacy `request_id` and `revision`
transport fields do not assert solver identity.

## Field table (`hawa-field-csv-1`)

UTF-8 CSV uses standard quoted records (including commas, quotes and newlines
inside metadata). The first record contains two cells: `hawa-field-csv-1`, then
one JSON metadata object. The next record is the ordinary column header. Every
remaining record is a lattice node in NumPy C order (last index varies fastest).
There are at most 250,000 nodes; use NPZ or a smaller case above that limit.
There is no companion sidecar that can become inconsistent with the data file.

| Columns | Meaning |
| --- | --- |
| `i,j,k` | Zero-based lattice index; k is zero for 2D |
| `x,y,z` | World position in declared physical units: `origin + [i,j,k] @ basis * dx` |
| `solid,boundary_node,valid` | Integer flags; valid iff neither mask is set |
| `u_domain,v_domain,w_domain` | Raw physical velocity in domain axes; w is zero for 2D |
| `pressure,density` | Raw solver gauge pressure and physical density |

Invalid nodes keep their position and flags, with all five flow quantities empty.
Do not read blanks as zeros. NPZ retains all original array values. CSV refuses
nonfinite source fields, nonpositive density and invalid masks/geometry before
publication. It neither interpolates nor averages and does not apply display
clipping or coefficient conversion. Valid numeric values use Python's round-trip
float decimal representation; float32 values promote exactly to float64. Read
with a float64 parser to recover exported raw values exactly. Transform velocity
to world axes as `domain_velocity @ basis` only if needed.

Metadata records schema, column names, expected row count, shape, case and hash,
session, Hawa version, selected backend, captured iteration, `local_time`, `time_origin` and `absolute_time`, sampled quality,
physical origin/basis/dx, units, validity and pressure-reference semantics.
`local_time` is elapsed solver time; `time_origin` is the case
`time_origin_seconds` (zero when absent); `absolute_time = time_origin + local_time`.
Use absolute time to align nested parent/child results. All three use the declared
time units. Case
geometry origin in document coordinates is scaled by physical dx / display
spacing. Ordinary physical wind cases declare metres, seconds, m/s, Pa and kg/m³.
Built-in benchmark examples instead declare normalized length/time/velocity/
pressure/density; their normalization is not an SI engineering specification.
Pressure is the solver's gauge quantity relative to rest density, not a newly
subtracted user coefficient reference. Quality metadata is not convergence or
engineering validation. No coefficient reference area/length is implied.

Metadata and arrays are captured under one session lock and JSON is frozen before
file IO. File output uses a same-directory temporary, flush/fsync and atomic
replacement. The export checks cancellation before capture, every 1024 rows and
before replacement. A process-wide canonical-path reservation rejects competing
CSV publications from native/GH callers. Failed captures, writes and replacements remove the temporary
and preserve an existing destination. It does not promise crash durability of
the parent directory or rollback after a successful replacement.

## Probe table (`hawa-probe-csv-1`)

Columns are `probe_index,i,j,k,x,y,z,valid,u_domain,v_domain,w_domain,pressure,density,speed`.
Input order and duplicates are preserved. `i,j,k` retain requested lattice
coordinates; `x,y,z` are physical sample positions using the captured mapping.
The existing fluid-only trilinear/halfway-wall sampling rule determines validity.
Outside/invalid samples remain rows with `valid=0` and six blank flow quantities.
For 2D, the existing sampler projects k to zero; requested k is retained but the
physical position describes the sampled plane. Sampling is instantaneous and
bounded to 10,000 points; it is not a new interpolation-accuracy claim.

## Load table (`hawa-load-csv-1`)

Columns are `sample_index,body_id,local_time,absolute_time,pivot_x,pivot_y,pivot_z,valid,force_x_domain,force_y_domain,force_z_domain,torque_x_domain,torque_y_domain,torque_z_domain,power`.
Export requires a moving-body session advanced at least one step. It includes
all retained step-end records, up to 10,000 steps and four bodies, in history/body
order. `body_id` cells are JSON strings: decode each with `json.loads`, preserving
arbitrary quotes, newlines and formula-prefix characters without interpreting them.

Force is fluid force on the body (N), torque is about its instantaneous pivot
(N·m), and power is signed fluid work on the body (W), all in domain axes.
Pivot positions are reconstructed from prescribed motion at each row's time and
mapped to physical world coordinates; they are not the latest pose copied into
older rows. Metadata declares first/last retained times, capacity and whether the
retained start is later than the first step. Earlier or reset history is not
reconstructed. `valid=1` means complete finite data, not physical qualification.
Quality is capture-time quality, not a historical quality assessment of each row.

Metadata includes density/speed/pressure context and explicitly absent reference
area/length. Coefficients are not invented or computed. Raw sign conventions and
moving-surface limitations remain those of the solver.

## Readback

Use a CSV parser, not line splitting: metadata may contain embedded newlines.
This is an interchange table, not a solver checkpoint or a Hawa load format.

```python
import csv, json
with open(path, encoding="utf-8", newline="") as source:
    reader = csv.reader(source)
    marker, payload = next(reader)
    assert marker in {"hawa-field-csv-1", "hawa-probe-csv-1", "hawa-load-csv-1"}
    metadata = json.loads(payload)
    header = next(reader)
    assert header == metadata["columns"]
    rows = list(reader)
    assert len(rows) == metadata["rows"]  # reject truncated tables
    assert all(len(row) == len(header) for row in rows)
```

Reimport should also reject malformed numeric cells or flags, and never evaluate
metadata strings as spreadsheet formulas. Field/probe cells are numeric or empty; load body IDs use the declared JSON-string
encoding. Check schema, required columns, finite values, flags, row count and
identity before accepting an artifact. A truncated file is not a complete export.

Publication is atomic within the destination filesystem. Pre-publication failure
or cancellation preserves the prior complete file and removes the temporary;
cancellation after replacement cannot undo publication. This does not promise
parent-directory crash durability or coordinate separate operating-system
processes writing the same destination.

Baking remains separate [#34](https://github.com/range-et/hawa-cfd/issues/34).
[Completion review and exact verification scope](review-export-completion.md);
[historical field increment](review-numerical-export.md).

Native resumable data uses the separate [Save/Import data workflow](native-data.md).
