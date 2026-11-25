# OpenFOAM Slice 1 review follow-up — PR #128

Date: November 24, 2026. Implementation/testing: Codex `openfoam_walls` agent.
Additional read-only review: Codex `scheduler_cli` agent (gradient gate and stale
report findings). This is a reliability/test follow-up, not independent numerical
qualification or a release.

## Repaired contracts

- Hawa-to-OpenFOAM handoff accepts only the represented laminar collision models
  (`bgk`, `trt`, `regularized`); SGS models are rejected before case publication.
- Explicit null boundary velocity/pressure values and out-of-range pressure
  reference cells are rejected before publication. An omitted solver consistently
  means `simpleFoam` in both generation and execution.
- Case execution is single-use. Existing mesh/time/probe output or the exclusive
  run marker refuses reuse, including after a failed invocation. Publish a fresh
  case to retry; existing user output is not deleted by the runner.
- Probe directories are ordered by numeric time, with pressure and velocity read
  from the same directory and required to share sample time. Missing, unmatched
  or non-finite measurements fail closed.
- Comparison rejects invalid vector shapes, non-finite measurements/tolerances,
  overflowed pressure scales and derived non-finite metrics. The declared pressure
  threshold gates both pressure differences and pressure gradients; gradient error
  is multiplied by the probe-pair distance and normalized with the same pressure
  scale. An inconsistent finite gradient cannot pass merely because delta-p agrees.
- Provenance hashes tracked and nonignored untracked file contents, deletions and
  symlink targets, and refuses unavailable Git provenance. Path-only status text
  is no longer the source fingerprint.
- Tool discovery explicitly requires the declared OpenFOAM `v2606`; empty channel
  or cavity inventories fail before work starts.
- The CLI records a unique `RUNNING` run ID before executing the suite and records
  `FAILED` if it raises. A failed rerun cannot leave an old `COMPLETED` report in
  the requested report file.

## Assertion and mutation scope

Generated deterministic interpolation tests exercise 40 shifted, uneven grids in
each of 2D and 3D, five interior probes per grid, against independent affine-field
identities. Additional tests cover translated face ordering, all parabolic vector
components, physical recipe/scaling constants, pressure signs/distances, exact
comparison metrics, default semantics, failure ordering and run metadata.

Two dictionary fixtures were copied from the previously solver-executed November
23 OpenFOAM control artifacts after checking every file against its original
manifest SHA-256. They test the emitted dictionaries against known executed
artifacts; they are not fresh solver runs. Parameter variation has independent
physical-contract tests.

The new `tools/mutation/run_openfoam.sh` studies all added lines in
`src/hawa/openfoam.py` and `scripts/compare_openfoam_controls.py` against the PR
base `0b81daee8b5c00838c1af95b54066b2b5da96079`, using mutmut 3.7.0 on Python 3.12.
Pydantic class fields/decorated validators remain outside mutmut's mutation
capability and have explicit rejecting tests. The previous motion-schema study
never established mutation coverage of OpenFOAM: adding a reviewed hash only
pinned its contents. It was separately rerun after these changes (104 killed,
zero survivors, 133 passing control tests) to refresh its source dependency.

The first exploratory OpenFOAM study completed 3883 mutants: 2586 killed and 1297
survived, zero timeout/error outcomes. Its weak assertions motivated the added
contract tests. A second study was interrupted at 455/3920 when read-only review
found two further correctness defects; it is incomplete and earns no pass. Only
the final-source study below is relevant to the current code. Mutation evidence
is not mathematical correctness or physical validation; unresolved survivors
remain test gaps, never equivalent changes or kills.

## Evidence and gate disposition

Focused Python 3.9 tests: **97 passed** (OpenFOAM/physical contracts/schema).
Ruff passes. Final-source results are recorded below.

- G0/G1: represented physics, accepted/default input behavior, single-run ownership
  and failure provenance are explicit; no new public node or dependency.
- G2: regression and measured gates pass; unresolved mutation assertion debt
  below is tracked under the repository’s explicit unresolved-survivor policy.
- G3: numerical solver implementation and thresholds are unchanged. The extra
  gradient gate closes an evidence false-pass. Fresh final-source Channel 07 CPU comparisons pass at ny20/40 as recorded
  below; Cavity 06 remains historical/diagnostic. No MPS/CUDA or independent
  numerical qualification is claimed here.
- G4: not applicable to this headless increment; no Rhino/GH UI or archive changed.
- G5: not applicable; no package, installation or release produced.
- G6: explicit valid/rejected handoff combinations tested; no claim that the
  existing finite compatibility inventory covers all future OpenFOAM combinations.

Slices 2–4, physical validation and device qualification remain in #126/#127.


## Fresh external execution check

On macOS arm64 with the local `/opt/homebrew/bin/openfoam2606` launcher, generated
a fresh Channel 07 `ny=10` case and ran blockMesh, checkMesh, simpleFoam and probe
post-processing through the repaired runner. OpenFOAM **v2606** reports **Mesh OK**,
400 cells, bounds (0,0,0)–(4,1,0.3) m, and convergence at iteration 148. Both
velocity and pressure report sample time **148**. A second invocation on the same
directory is refused before executing another solver, preserving the old files.
Evidence: `results/openfoam-pr128-execution-20261124/execution-result.json` plus
case manifest and process logs in that fresh directory. This verifies the real
external execution path; Hawa was not rerun for a numerical comparison here.

## Final-source checks and explicit assertion debt

Python 3.9 full measured suite: **2930 passed, 87 skipped**; strict headless
function/line gate **1227 covered, zero failures**, 299 host functions unmeasured.
Linked .NET 10 StateContracts: **155 passed**. Python 3.12 full suite:
**2920 passed, 97 skipped**. Logs: `results/function-openfoam-review-20261124`
and `results/openfoam-review-py312-20261124.log`. Concurrent CPU/device suites
mean these are functional evidence, not performance measurements. Final policy
artifact regression: **80 passed, 1 skipped**.

Final mutation study: **3990 mutants; 3418 killed, 572 survived; zero errors,
timeouts or missing-test outcomes**, with 83 passing control tests. Exact
inventory/source hashes and every survivor diff hash/reason are committed in
[the policy](../tools/mutation/openfoam-policy.json). Of the survivors, 86 are
narrow text/codec equivalents and **486 remain explicitly unresolved assertion
or portability gaps**, never counted as kills. `check_results.py` accepts the
exact reviewed manifest; that integrity check is not a complete-testing pass.

Highest-risk unresolved seeded gaps include default overwrite behavior and
case/manifest payload assertions; backup/cleanup failure paths; permissive
process mocks accepting changed solver commands; unconverged successful-process
fixtures; optional analytic maps and nonzero analytic error scaling; and exact
comparison boundaries. Filesystem case sensitivity also limits local detection.
These are gaps exposed by seeded mutants, not reproduced production defects.
Owner: PR #128; next action is targeted independent assertions and a new exact
study before claiming these gaps closed. Completion requires each surviving
behavior either killed by a relevant assertion or justified narrowly with
reviewed evidence. The exact-inventory policy passes with tracked unresolved survivors as permitted
by `docs/function-testing.md`; there is no repository zero-survivor threshold.
Assertion kills are 85.66% (3418/3990), but that ratio is not the policy gate.
The remaining debt limits assurance, rather than constituting a reproduced
runtime defect or a failed mandatory automated gate. No blanket merge approval
or complete mutation coverage is claimed.

## Fresh final-source Channel 07 comparisons

[Committed machine evidence](verification-openfoam-review-controls.json) includes
exact production SHA-256 hashes, Git content provenance, environment, full case
inputs, probe samples and per-observable comparison rows. Both runs used CPU
FP32 (PyTorch 2.8.0, macOS arm64) and OpenFOAM v2606 through the real launcher;
both Hawa settling and OpenFOAM convergence checks passed. The unchanged limits
are 0.02 normalized velocity and 0.05 normalized pressure difference/gradient.

| Grid | Hawa steps | Velocity Linf | Pressure/gradient Linf | Result |
| --- | ---: | ---: | ---: | --- |
| ny20 | 12000 | 0.0096289852 | 0.0212810434 | PASS |
| ny40 | 22000 | 0.0042923145 | 0.0096396693 | PASS |

These bounded checks supersede no prior cavity result and do not qualify
Slices 2–4, other devices, turbulent models or engineering accuracy.

## November 25 — PR #135 two-dimensional profile repair

Codex `openfoam_walls` reproduced review comment
[4690560057](https://github.com/range-et/hawa-cfd/pull/135#discussion_r4690560057):
a 2D channel bundle with `profile_axis=2` passed validation but its one-cell
empty-Z extrusion emitted six identical `(0.5 0 0)` inlet vectors. This changes
the supplied Z-dependent parabolic inlet into a uniform inlet.

Frozen source `76a33f7` rejects Z-dependent parabolic profiles for `dimensions=2`
with actionable guidance to use `dimensions=3` and a resolved Z mesh. Regressions
exercise direct validation, Hawa handoff, refusal before case publication, and
accepted X/Y-dependent 2D and Z-dependent 3D profiles against analytic face
samples. No 3D capability or valid in-plane 2D profile was removed.

Focused OpenFOAM tests: **87 passed** on Python 3.9 and **87 passed** on Python
3.12; Ruff and diff checks pass. Fresh isolated mutation evidence at
`results/pr135-openfoam-profile-20261125`: **3990 mutants, 3421 killed, 569
survivors, zero error/timeout/no-test outcomes**, with **87 passing controls**.
The exact policy passes; all retained survivors have unchanged status/diff hash
and retain their prior reasons (**86 narrow equivalents, 483 unresolved gaps**).
Three former unresolved mutants are now killed: the minimum channel grid bound
(two mutants) and the omitted-provenance default. The Pydantic model validator
remains outside mutmut's decorated-method scope; its new rejection has direct
regression evidence, not a claimed mutation kill.

The separately refreshed motion-schema dependency study at
`results/pr135-motion-schema-20261125` passes **104/104 mutants killed**, **133
passing controls**, zero survivors, and an exact matching policy. This refresh
pins the changed OpenFOAM source; it does not mutate the OpenFOAM validator.

No new numerical solver study, device qualification or live-host check was run
for this validation-only repair. Earlier Channel 07 comparisons remain historical
numerical evidence for unchanged supported cases. The root integration review
owns the final combined full-suite/function gates and host acceptance.
