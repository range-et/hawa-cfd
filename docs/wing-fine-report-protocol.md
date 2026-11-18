# Finer wing report protocol — November 17, 2026

Declared before fine-grid solves by Codex wing-wrapup, coordinated with root.
User requested a finer wing simulation; native block example remains quick.
This extends CPU resource admission, not physical qualification. The original
[sensitivity protocol](wing-cpu-sensitivity-protocol.md) and failures remain intact.

## Fixed configurations and comparisons

Keep the NACA2418/0018 mesh, origin, physical domain extents, fluid, Mach, reference
area/chord, two angles −3°/+3°, probe and full-way BGK method unchanged.

| Configuration | Spacing | Shape / cells | Settling | Samples | Source window |
| --- | --- | --- | --- | --- | --- |
| Retained original report | 0.025 m | 33×41×25 / 33825 | 1000 | 64 | 1000…1063 coarse dt |
| Fresh coarse comparison | 0.025 m | 33×41×25 / 33825 | 1200 | 81 | 1200…1280 coarse dt |
| New fine report | 0.010 m | 81×101×61 / 499041 | 3000 | 201 | 3000…3200 fine dt |

`fine_dt = 0.4 * coarse_dt`, so comparison starts and ends at equal physical
source times. Both comparison windows retain the same 0.05 absolute coefficient
stationarity criterion. A source capture at index N requires N+1 advances.
The original report is preserved as historical evidence, not used as an
unequal-time comparison. Report default becomes fine; explicit `--coarse`
selects the quick comparison. No silent fallback.

Record actual raw results, status/quality, session/case/geometry identities,
solid-node counts, timing and cleanup. Compare absolute CL change with 0.02 and
relative CD change with 5% (fine magnitude denominator), matching the earlier
screen's bounded refinement thresholds. A two-grid result is not the original
three-grid monotonic-refinement criterion, domain independence or a physical
reference pass. Keep all rejected cases/failed thresholds visible; never adjust
criteria to improve curves.

## Resource admission and pilot

One explicit CPU float32 worker at a time; one OMP/MKL thread. Raise only the
per-case grid cap from 150000 to 500000 and share the constant with the recipe.
Retain aggregate limits: 1.5 million retained field cells, 100000 load/probe rows,
200000 vertices, 400000 triangles, 64 candidates, 100000 steps per case.
The requested sweep retains 998082 field cells and 12804 load/probe rows.

At 499041 cells, one D3Q19 float32 population is 37927116 bytes; two retained
field snapshots (velocity, pressure, density, two masks) are about 22 MiB before
Python metadata. Temporaries dominate peak memory: allow a conservative 2 GiB
working estimate and stop after the pilot if observed process peak exceeds
3 GiB. Require at least 8 GiB available memory before starting. These are pilot
admission criteria, not a proof that arbitrary admitted inputs consume this much.
The observed machine has 48 GiB physical memory; no Rhino/GPU work is requested.

First run one ten-step fine candidate, record elapsed time/peak RSS, then run a
separate fine candidate for cooperative pause acknowledgement, resume, cancel
and drain. No long solve starts until root reviews pilot results. Cancellation
occurs at a step boundary; never kill a worker. A long solve timeout requests
cooperative cancellation, followed by confirmed zero workers/handles/sessions.
Tests assert exact 500000 admission and 500002 rejection before allocations;
500001 cannot factor into three integer dimensions >=4.
