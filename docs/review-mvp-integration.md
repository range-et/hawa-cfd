# Combined MVP follow-up acceptance

Date: November 24, 2026. Integrator/operator: Codex primary agent (self-review).
Implementation and scoped reviews: Codex openfoam_walls, scheduler_cli and
lifecycle_admission agents, as identified in the linked records. This is a local
integration branch, not a merge into main or a release.

An earlier bounded source review of cleanup/admission at `bd415bd` by openfoam_walls
found no new actionable regression in job ownership/retries, close reply ordering,
worker validation, budget arithmetic or validated output-path use. That review
ran no tests and does not establish exhaustive concurrency or host acceptance.

## Scope and component evidence

The branch combines PRs #128–#133 and draft #134. It preserves the existing public
nodes, solver budgets, comparison tolerances and archive identities. It does not
claim that every open GitHub issue or the full product roadmap is complete.

- [OpenFOAM controls](review-openfoam-pr128-followup.md): PR #128 `8f0b10f`.
- [Concave wall fields](review-concave-wall-fields.md): PR #129 `b558e9a`.
- [Scheduler retry](review-poll-retry.md): PR #130 `844564b`.
- Coverage CLI percent escape: PR #131 `fcac445`.
- [Session cleanup](review-mps-cleanup-followup.md): PR #132 `efab9ec`.
- [Admission and paths](review-admission-followup.md): PR #133 `f411d69`, stacked
  on #132.
- [Boundary markers](review-boundary-tick-legibility.md): draft #134 `8030a33`.

The generated function matrices are refreshed from the final combined measurement.
No conflicting feature history was
discarded. Production files merged without manual conflict resolution; the
mutation runner conflict retained #133's superset of fixtures and CPU selection.

## Combined checks completed

- C# StateContracts: 159 pass after final OpenFOAM/wall/scheduler/annotation
  integration. The subsequent cleanup/admission changes affect Python only.
- CPU diagnostic at `1aa2d94`: 2,733 pass, 251 deselected, one tooling failure
  because the operator omitted the private .NET 10 runtime environment. With
  PATH/DOTNET_ROOT corrected, all 15 coverage-tool controls pass. Device tests
  and mutation-policy tests were excluded; this is not the final full gate.
- Fixed-policy device smoke at `1aa2d94`: CPU 5 pass and MPS 5 pass, zero failures
  and zero unsupported-guarded cases. Both manifests confirm unchanged source
  and modules loaded from this checkout. Existing tolerances were retained.
  CPU mutation studies ran concurrently in separate worktrees; Rhino was idle
  with the old installed build. These are not performance or convergence claims.
  Local evidence: `results/device-smoke-{cpu,mps}-combined-20261124/manifest.json`.
- Development package from `4e546ac` builds with existing warnings and no errors.
  ZIP integrity passes; the legacy example 09 definition is absent. Hashes are
  in `results/integration-build-hashes.json`. This package has not been installed.
- Pre-lock-order-repair measured gate at `4993264`: 2,984 Python tests pass,
  87 skip, 159 C# contracts pass; 1,240 functions covered, zero strict headless
  failures, 299 host functions unmeasured. Subsequent PR review identified a
  synchronous/asynchronous close lock inversion that this suite did not detect.
  This passing run does not establish merge readiness. A public-path two-thread
  regression reproduces the inversion before repair and passes on Python 3.9/3.12
  after enforcing device-lock-before-release-lock order. It unwinds and joins its
  workers on the failing path. The repair is integrated at `ca5ed03`. Retain the
  original run under
  `results/function-coverage-combined-final-20261124/` as pre-repair evidence.
- Final repaired gate at `5a1e182`: 2,985 Python tests pass, 87 skip, 215 warnings;
  159 C# StateContracts pass; 1,240 functions covered and zero strict headless
  failures. The 299 unmeasured host functions remain explicit debt. Output:
  `results/function-coverage-combined-lockorder-20261124/`. The final component
  merge at `aa248cd` changes only records: source, tests, tools, scripts, plugin
  and vendor files are byte-identical to the measured version. The rendered
  committed matrix passes its baseline check against `origin/main` (`0b81dae`).
  Separate CPU coverage runs overlapped; no other standalone MPS measurement ran
  concurrently. This is not performance evidence.
- All four cleanup/admission mutation policies pass fresh post-repair studies.
  The status runner now pins its changed `plugin.py` dependency. Policies pin
  selected files, not the complete transitive import graph; their review records
  retain that provenance limit and the explicitly unresolved assertion debt.

The diagnostic and smoke runs use macOS/Apple M3 Max, Python 3.9 and pinned
PyTorch 2.8.0. C# checks/build use the private .NET 10 toolchain; the plugin target
remains .NET 7. CUDA and Windows are unverified. The later cleanup lock-order
repair does not change the numerical modules exercised by device smoke; it needs
separate lifecycle evidence. The repaired source passes the standalone MPS
teardown test (64 x 48 x 32, ten steps): current allocation within 1 MiB of
baseline, driver allocation below the existing 25%-of-peak limit. This is not a
Rhino paused-RSS measurement.

## Gate disposition and remaining work

| Gate | Decision | Evidence and limits |
| --- | --- | --- |
| G0 research | PASS (bounded integration) | Component records retain sources, criteria and exclusions; no new dependency or physics claim. |
| G1 architecture | PASS (headless scope) | Scoped source reviews and deterministic ownership/scheduling tests; actual host behavior remains under G4/G6. |
| G2 reliability | PASS (headless scope) | Reproducing close-lock regression, fresh mutation policies, complete measured suite and current matrix pass. Live host behavior remains under G4/G6. |
| G3 numerical physics | PASS (smoke scope only) | CPU/MPS five-case policy above; component numerical evidence retains its own exact source scope. Long-window qualification and PorousMedium parity remain open. |
| G4 UI/UX | BLOCKED | Revised 08/22/25 markers, Stationary Study publication, example 33 refusals and embedded cleanup/paused RSS await live acceptance. |
| G5 release/integration | BLOCKED | Repaired candidate packaging and installed acceptance remain pending. No release. |
| G6 compatibility/examples | BLOCKED | Full gallery, Windows/CUDA and measured host coverage not completed. Existing compatibility/example matrices retain their stated limits. |

Rhino's normal Exit did not complete in the owned test session. No process was
killed and no loaded assembly replaced. Before-change owned-copy screenshots and
state are preserved in the annotation worktree. A normal shutdown is required
before installing the combined candidate.

Issue #76 still requires timed paused-RSS and embedded teardown measurements;
standalone tensor/cache reclamation does not close that host investigation.
Python job-ID retry tests do not prove that Rhino retains ownership of a late
asynchronous cleanup failure. Issue #122 still requires the multi-candidate host
workflow without forced refresh. Issue #75 requires live example 33 messages.
Issue #108 requires revised-build screenshots of 22, 25 and 08 at default framing.
