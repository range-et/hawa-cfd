# Sweep controller foundation — issue #40

November 17, 2026. Author/reviewer: Codex sweep-lane agent, self-review only.
Base: frozen [measurement contract v1](measurement-contract-v1.md), commit
`895975b`, on `codex/40-sweeps`. This is an internal headless implementation;
no public component, live solver adapter, export format or completed CFD study.

## Implemented contract

`hawa.sweeps.validate_candidates(list)` validates and copies 1–64 descriptors,
rejecting duplicates, missing/unknown fields, blank identifiers, nonfinite
numbers, numeric strings and boolean numbers. It never changes case specs.
`SweepController(candidates, executor, generation=0)` starts idle. Public methods
are `run`, `tick`, `pause`, `resume`, `cancel`, `dispose`, and `save`; `records`
and `state` expose detached result snapshots and controller state. `save` stores
only candidate descriptors; constructing a new controller reopens idle.

The injected executor owns all asynchronous solver work. Every method must
return promptly. `start(candidate, generation)` transfers one non-null handle;
a raised start must leave no unreturned resources. `poll(handle)` returns the
contract state/identity. `pause`, `resume` and `cancel` request controls.
`close(handle)` returns False while cleanup is pending and True/None only when
resources have been released. Exceptions retain ownership for retry. The adapter
must enforce this cleanup contract; merely dropping a handle is not sufficient.
No thread, sleep, wait or background process exists in this controller.

One tick performs at most one start or poll. Cleanup occupies a separate tick
and completes before another candidate starts. Cancel/dispose cancel queued
candidates, request active cancellation, and retain active ownership through
retryable cancellation/close failures. Poll/control exceptions create failed
records and cleanup requests. Stale callback identity/generation is ignored;
completion identity mismatch is failed and cleaned. Duplicate ticks cannot
publish the same completion or start the same candidate twice. Sweep state
`completed` means every candidate has a terminal record, not that every
candidate succeeded. Inspect individual record states.

## Result adapter envelope

A completed poll has this result (all named keys required except case_id/revision):

```json
{
  "identity": {
    "candidate_id": "alpha-0", "generation": 7,
    "case_hash": "actual-case-hash", "geometry_hash": "actual-geometry-hash",
    "case_id": "optional-case-id", "revision": 2
  },
  "quality": "accepted",
  "window_valid": true,
  "stationarity_passed": true,
  "coefficients": {"CL": 0.4, "CD": 0.05}
}
```

This small adapter envelope is not the full measurement history or exporter
payload. The integrator maps the measurement module's verified summary into it.
Unknown/coercive/nonfinite values reject. Candidate ID, generation and both
hashes must match the active candidate. Optional case ID/revision survive
unchanged. Quality warning/rejected, invalid window or failed stationarity
become explicit rejected records, retaining data/reason but supplying no usable
plotted point. An executor already reporting failed/cancelled/rejected needs no
coefficient payload.

Each record stores candidate metadata, generation, terminal/live state, reason
and a copied result. `plot_segments(records, kind)` accepts `cl_alpha`,
`cd_alpha` and `cl_cd`. It returns ordered identified point segments split at
all failed, missing or unusable points; no line bridges a rejected point.
Each point retains full candidate metadata and result identity for later field
selection. It revalidates result identity including the record's generation.
No plot-rendering dependency, CSV writer or existing export/host file changed.

## Checks and disposition

Environment: macOS arm64, isolated uv.lock environments, CPython 3.9.25 and
3.12.4, PyTorch 2.8.0 installed but no solver/device work. OMP/MKL threads 1.
Imports verified in this worktree for Hawa and vendored Lettuce.

- Focused Python 3.9 tests: **69 passed**, no skips.
- Coverage.py 7.10.7 focused measurement: **216/216 executable statements** in
  sweeps.py, 100%; intended results and adverse paths asserted. This is local
  module line evidence, not a replacement for the repository function matrix.
- Focused Python 3.12 tests: **69 passed**, no skips; ruff Python 3.9 syntax guard passed.
- Repository payload-model safety scan: passed on the new models.
- Tests cover serial start/poll ordering, pause/resume, cancel/disposal, failed
  start/poll/control, stale IDs/generations, result/reference identity, quality
  rejection, cleanup pending/failure/retry, duplicate ticks, immutable snapshots,
  idle reopen, all three plot mappings and gaps.

| Gate | Disposition | Scope |
| --- | --- | --- |
| G0 | PASS, bounded | Frozen internal software contract; no new method/dependency. |
| G1 | PASS, headless | Injected executor ownership/state invariants tested; real adapter still required. |
| G2 | BLOCKED for integration | Focused tests and line coverage pass; root owns serial full suites, measured function gate and mutation/integration checks. |
| G3 | NOT APPLICABLE to numerical methods | No physics or coefficient algebra introduced; result acceptance gates tested. Physical qualification remains open. |
| G4 | BLOCKED for this round | User requires CPU/headless; no Rhino/GH scheduling, archives or plots inspected live. |
| G5 | NOT APPLICABLE | No package, install, merge or release performed by this lane. |
| G6 | BLOCKED for integration | Finite controller states tested; combined compatibility/example coverage remains integrator work. |

Existing runtime, export and native UI files are untouched. CPU-only checks do
not qualify MPS/CUDA or live Rhino. #40 stays open for measurement integration,
real executor, host workflow, export handoff and numerical reference acceptance.
