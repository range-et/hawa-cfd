# CPU measurement foundation review — issue #40, lane A

November 17, 2026. Author/reviewer: Codex measurement agent, self-review; root and
sweep agent supplied targeted source-review findings. Base: contract `895975b`.
This is isolated source, not a public dispatcher, GH node, installed plugin,
export schema, released package or physically validated wing experiment.

## Implemented contract

[Measurement contract v1](measurement-contract-v1.md) is implemented by new
`hawa.measurements` validators and analysis plus the isolated
`hawa.stationary_loads.StationaryLoads` boundary. Existing solver, runtime,
export and host sources are unchanged.

- `validate_request(payload)` returns a validated Request. Mutated model objects
  are revalidated; references, axes, identity, validity, sample ordering and
  averaging windows reject ambiguous input. No caller case is overwritten.
- `coefficients(request, force_world_n, torque_world_nm)` returns q, signed
  D/Y/L, CD/CY/CL/Cm and a signed load-cell force. `translate_moment` implements
  reference-point translation; arithmetic overflow rejects, never returns Inf.
- `summarize(request, samples)` returns identity/references/window and one body
  result with mean loads/coefficients, population standard deviations, sample
  count and stationarity diagnostic. Rejected/invalid/incomplete windows raise
  ValueError. Nonstationary or warning-quality windows retain labelled statistics
  but `usable=false`. A display adapter must respect that flag.
- `sample_probes(request, probes, time_s, sampler)` consumes an injected sampler
  returning finite pressure Pa or None. It preserves invalid positions, null
  pressure/Cp, attachment offsets, references, identity and capture time.
- `validate_case(spec, body_indices, device='cpu')` checks ownership/support
  before a Session is allocated. `StationaryLoads(flow, spec, body_indices,
  bodies, origin_world_m, basis, capacity)` then binds the actual flow/spec/units.
  Replace only the matching full-way obstacle boundary explicitly; this module
  does not register global sessions or modify existing service routes.
- The collector returns the original full-way reflection result and stores raw
  per-body force/torque in `.history`. Each entry includes `source_step` and
  `source_time_s` for the **pre-stream state** that supplied the populations,
  plus solver/reduction dtypes. It must not be relabelled as a later field.
  History overflow fails instead of discarding samples. Native code generation
  is disabled because it would bypass Python measurement.

Supported: CPU, physical uniform D3Q19 BGK, explicit legacy boundary set and
full-way stationary obstacles; at most four body IDs and 150000 cells. An
obstacle adjacent along a D3Q19 link to a wall/slip domain-face node is rejected:
that node is not the required **fluid** padding. This prevents domain-boundary
populations being counted as obstacle-fluid links. Independently named bodies
cannot overlap or touch. Per-body ownership must exactly cover the solid mask.

## Fresh checks

Commands used local per-worktree environments and `OMP_NUM_THREADS=1` /
`MKL_NUM_THREADS=1`. Imports resolved into this checkout and its own vendor tree.

- Python 3.9.25 / torch 2.8.0 / NumPy 2.0.2, macOS arm64, explicit CPU:
  **84 focused tests passed**. Measured coverage: measurements.py 192/192 and
  stationary_loads.py 146/146 executable statements, **338/338 (100%)**.
  Report: `results/measurements-lane/coverage.json` (local evidence, not committed).
- Python 3.12.4 focused suite: **84 passed**. Two existing Lettuce package-metadata
  deprecation warnings; no test skips. Python 3.12 is tooling evidence only.
- Ruff Python 3.9 syntax guard passes for the four added source/test files.
- Frozen JSON schema snapshots for request, sample and probe are checked against
  live pydantic schema generation in the focused tests.
- Existing `test_payload_schemas.py`: six checks passed; its hardcoded snapshot
  inventory needs the new three snapshots registered. Integration owner notified;
  this lane deliberately did not edit that shared test. This is an integration
  requirement, not a waived failure.

Independent controls include manufactured coefficient/pressure values; strict
inputs and mutated models; overflow/underflow; missing, rejected and irregular
windows; flipped/rotated axes; halfway-link torque; reference translation;
world transforms; nonoverlapping per-body force sums against the existing
aggregate collector; zero equilibrium; reversal at fixed source density; density
scaling; and exact original reflection. Two fresh CPU sessions advanced five
BGK steps with/without the collector have **bitwise-identical populations**.
CPU float64 collection also runs; no CUDA/MPS operations or Rhino operations ran.
These are small implementation controls, not physical convergence benchmarks.

An initial reversal test inadvertently recomputed density from the already
rounded forward equilibrium before constructing the reverse equilibrium.
Retaining the same input density for both controls fixes the test setup; its
comparison tolerance was not widened. Three intentional arithmetic-overflow
warnings are asserted by their rejection tests and do not escape the final suite.

## Gate disposition and remaining work

| Gate | Disposition for this lane |
| --- | --- |
| G0 | Bounded contract/audit implemented; physical benchmark protocol remains pending |
| G1 | Isolated API, explicit world units, per-body ownership and pre-stream provenance reviewed; runtime adapter not built |
| G2 | Focused CPU checks and new-module line coverage pass; combined full suites, authoritative function matrix and mutation review remain integrator work |
| G3 | Manufactured/link/regression checks pass; Stokes/wing physical qualification not run |
| G4 | BLOCKED for live integration by this round's CPU/headless restriction; no host claim |
| G5 | Not packaged or released; no installed assembly changes |
| G6 | Support/rejection unit cases covered; combined compatibility inventory/public-node mapping remains integration work |

#35 exporter adaptation, a real sweep executor, public service/host adapters,
full-suite/measured-function gate, device qualification, reference aerodynamic
studies and live example acceptance remain open. No CSV writer or GH archive was
introduced. Keep #40 open; partial integration uses `Refs #40`.

## Integration-review follow-up — scaled reference products

Root reproduced an arithmetic mismatch: reference validation used the scaled
product `0.5*rho*U*U`, while coefficients and probes used `0.5*rho*(U**2)`.
For rho=1e-200 and U=1e200, the valid q=5e199 failed on the intermediate square;
for rho=1e200 and U=1e-200, valid q=5e-201 was recomputed as zero. Both new
regressions failed before the repair. Both consumers now use the exact validated
multiplication order. The tests assert finite nonzero q with a scaled ratio and
zero absolute tolerance, and check CD/CL/Cm, Cp and summary usability at both
extremes. No physical/numerical acceptance tolerance changed.

Reviewed the remaining reference denominator calculations: q*S and q*S*chord
use the same multiplication order as validation. Stationary force scaling uses
one expression checked at construction, with explicit overflow/underflow refusal,
so it does not have this validate/consume mismatch.

Fresh focused CPU results after this follow-up: **86 passed** on Python 3.9.25
and **86 passed** on Python 3.12.4 (the same two Lettuce metadata deprecation
warnings). Full suites, measured matrix and mutation evidence are refreshed by
the integration owner; the earlier 338-statement report above predates this fix.
