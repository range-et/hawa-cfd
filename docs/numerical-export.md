# Numerical field exports

The existing Hawa Checkpoint component supports `export csv` as well as `save`,
`load` and `export`. Give it a local `.csv` path and toggle Execute from false to
true. It captures instantaneous fields through the background query service;
cooperative cancellation leaves the previous complete destination intact when
observed before publication. Cancellation after atomic publication cannot undo a
completed write. The component's GUID, ports and saved-definition layout do not
change. Native-panel export controls are not part of this increment.

Python callers use `{"op":"export","session":"…","path":"…","format":"csv"}`.
The path extension never selects the format. Omitted `format`, or `format="npz"`,
keeps the existing raw NPZ contract even if the path ends in `.csv`. CSV requires
explicit selection. CSV rejects unknown options, including mean/probe/load
requests; `request_id` and `revision` are accepted transport identifiers but do
not assert solver revision identity. The captured case hash is authoritative.

## Version 1 table contract

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
before replacement. Failed captures, writes and replacements remove the temporary
and preserve an existing destination. It does not promise crash durability of
the parent directory or rollback after a successful replacement.

## Readback

Use a CSV parser, not line splitting: metadata may contain embedded newlines.
This is an interchange table, not a solver checkpoint or a Hawa load format.

```python
import csv, json
with open(path, encoding="utf-8", newline="") as source:
    reader = csv.reader(source)
    marker, payload = next(reader)
    assert marker == "hawa-field-csv-1"
    metadata = json.loads(payload)
    header = next(reader)
    assert header == metadata["columns"]
    rows = list(reader)
    assert len(rows) == metadata["rows"]  # reject truncated tables
    assert all(len(row) == len(header) for row in rows)
```

Reimport should also reject malformed numeric cells or flags, and never evaluate
metadata strings as spreadsheet formulas. Table cells are numeric or empty;
user-provided strings occur only inside the quoted JSON metadata cell.

Issue [#35 / HAWA-033](https://github.com/range-et/hawa-cfd/issues/35) remains open
for probe/load exports, native export UX and wider installed-host acceptance.
Baking is separate [#34](https://github.com/range-et/hawa-cfd/issues/34).
[Review and verification](review-numerical-export.md).
