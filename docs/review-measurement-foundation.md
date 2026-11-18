# Measurement foundation integration — #40 partial

Date: November 17, 2026. Integrator/reviewer: Codex root. Implementation agents:
measurements, sweeps and wing_example. Independent cross-review: sweeps reviewed
stationary measurement guards; wing_example reviewed sweep lifecycle. Root
reviewed interfaces, numerical signs/units, failure behavior and combined tests.
No independent physical-validation reviewer is claimed.

Base main: `12dc774495871e9821c6481f27f84b80c0bd2fe2`. Contract freeze: `895975b`.
Integrated executable/test source: `4ab95ab`; refreshed mutation tooling/policy
head: `b940c83`. Subsequent evidence/documentation commits must not be described
as a different tested implementation.

## Scope and ownership

[Contract](measurement-contract-v1.md), [measurement lane](review-measurement-core.md),
[sweep lane](review-sweep-core.md), [recipe lane](review-wing-measurement-recipe.md).
Three isolated branches and local environments were created after the contract
commit. No prior worktree was modified. The implementation adds standalone
measurement/collector/sweep modules and one example-only script; it does not
change existing solver, job, dispatcher, exporter, host, view or geometry code.
The only existing test changed is the schema snapshot registry, extended to
validate the new payloads by class identity (not ambiguous model names).

The work is deliberately not wired into the live service: the active #35 chat
owns exporter/native UI interfaces and Rhino. Frozen sample data and injected
executors permit independent code development without editing those paths.
The wing recipe returns explicitly preflight hashes, which a future adapter
must replace with the final assembled/voxelized solver-case hash. There is no
real CFD sweep executor, new GH node/archive, UI plot or exporter in this change.

## Review findings and repairs

- An obsolete malformed callback previously failed full schema validation before
  its identity was discarded. The sweep now validates minimal callback identity
  first; stale payloads cannot fail/cancel the current candidate.
- Collector metadata must match the actual flow spec, mask, stencil and physical
  units. A same-mask/different-dx payload cannot change load scaling silently.
- A wall/slip domain node is not fluid padding. Obstacle links adjacent to such
  nodes reject, preventing those populations contributing to measured loads.
- Strict numeric inputs, reference-product overflow/underflow, result overflow,
  and mutable validated models receive rejecting regressions.
- Final source review found that coefficient/probe code squared speed before
  density scaling, unlike validation. Both now use the same ordered product;
  two extreme-reference regressions verify nonzero finite q and coefficients
  without absolute-tolerance masking.
- The original callback samples pre-stream populations. Histories retain source
  step/time rather than inheriting a later field's timestamp.

These findings were repaired before combined measurement; no acceptance
threshold or numerical tolerance was widened.

## Checks and evidence

Environment: macOS arm64; local `.venv` Python 3.9.25 and `.venv-dev` Python 3.12.4,
PyTorch 2.8.0, NumPy 2.0.2; CPU only, OMP/MKL threads limited to one. Full-suite
runs use the existing `tools.mutation.cpu_only` pytest availability shim; this
intentionally disables accelerator checks and is not device qualification.
Heavy checks run serially at reduced process priority. No Rhino/MCP/GPU access,
plugin replacement, restart, external export or accelerator qualification was run.

Pre-arithmetic-fix combined focused check: **214 passed** on Python 3.9, including all three
lanes, all payload schema snapshots and two cross-lane pipeline tests. The
manufactured pipeline proves case identity, gap preservation, speed/reference
coefficient scaling and idle reopen. Its constant loads are manufactured, not
a wing polar or CFD prediction. Per-lane fresh results are linked above.
Ruff's configured Python3.9 syntax guard and `git diff --check` pass.

The first measured attempt (`results/measurement-foundation-gate`) retained
2 failures, 2094 passes and 176 skips: the CPU-only pytest plugin could not be
imported by a temporary fixture process, and the changed schema registry
invalidated its motion mutation-policy hash. No product tests failed. The nested
fixture now passes with PYTHONPATH pointing only at tools/mutation and
PYTEST_PLUGINS=cpu_only (adding the entire repo would shadow its src namespace).
The motion study was rerun, not rehashed blindly: 104/104 assertion kills, zero
survivors/errors, 132 passing controls, unchanged mutant inventory. Its refreshed
policy explicitly includes the newly read models/snapshots. This does not claim
mutation coverage for new measurement/sweep code. Raw results remain in
`results/motion-schema-measurement-refresh`; the arithmetic correction was
followed by a second identical-inventory pass in
`results/motion-schema-scaled-reference-refresh`.

Final corrected-source evidence in `results/measurement-foundation-gate-corrected`:
**2098 passed, 176 skipped** on Python 3.9 (190.10 s). The strict headless
measurement and base-commit ratchet pass: **1059 covered functions, 299 unmeasured
host functions, 60 declarations, zero failures**. All 659 executable statements
in the four new modules/script were measured. The committed matrix is refreshed.
The linked C# host-double suite passed **127 contracts**; it does not establish
live Rhino behavior. Python 3.12 independently passed **2088 tests, 186 skipped**
(129.97 s), recorded in `results/measurement-foundation-py312.xml`.
Accelerator availability was deliberately disabled; skips are not hardware
qualification. Python-version-dependent tooling skips remain explicit. Warnings
include existing plotting dependency deprecations. The earlier 2096-test run
predates the arithmetic regressions and is not final-source evidence.

The existing explicit CPU smoke gate passed **5/5 cases** against its CPU FP64
reference (`results/measurement-foundation-cpu-smoke/manifest.json`). This is
regression evidence for the existing cases, not wing/force qualification.

## Gate disposition for this increment

| Gate | Decision | Evidence / limits |
| --- | --- | --- |
| G0 | PASS for software contract; physical reference BLOCKED | Frozen SI/identity/ownership semantics and reviewed primary-source audit; NASA candidate has no drag polar and unmatched conditions |
| G1 | PASS for internal headless scope | One active executor handle, delayed terminal publication until cleanup, immutable copies, strict provenance; production submission adapter remains open |
| G2 | Automated suite/coverage PASS; new-module mutation study OPEN | Both Python suites, 127 C# contracts, strict measured gate and refreshed existing motion mutation policy pass. Targeted mutation of the new modules remains outstanding; no merge-ready claim |
| G3 | PASS for manufactured/link invariants; physical qualification BLOCKED | Independent coefficient algebra, moment translation, signed force/density controls and five-step bitwise preservation; no aerodynamic benchmark |
| G4 | BLOCKED by user's CPU/headless constraint | No live GH/native/gallery run or visual acceptance; fake executor tests do not establish scheduling in Rhino |
| G5 | NOT APPLICABLE | Development source only, no package/install/release or merge claim |
| G6 | PASS for bounded internal support/rejection tests; host extension BLOCKED | No new public nodes/enums/archive formats or changed existing combinations. No new public example mapping or full G6/device run claimed |

## Follow-up

The [real CPU headless sweep increment](review-real-headless-sweeps.md) implements
the previously pending private executor and voxelized case path. Its fresh
evidence supersedes that portion of the remaining-scope list below; public
runtime/GH, export, host and physical qualification remain open.

## Remaining scope (at this foundation checkpoint)

#40 remains open: real runtime/sweep executor, final case/body/probe geometry
mapping, #35 export integration, public GH adapters/plots/archives, live lifecycle
and gallery acceptance, targeted mutation study, device comparison and a feasible
predeclared force/wing reference protocol. A finite field or rendered plot will
not close the numerical gate. General engineering qualification remains #15.
No data from the legacy user example 09 was changed or included in a package.
