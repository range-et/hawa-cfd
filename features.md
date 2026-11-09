# Hawa built features and history

This is the running inventory of implemented capabilities and completed work.
Open bugs, remaining work and ideas live in [issues.md](issues.md); future
direction lives in the [roadmap](docs/roadmap.md). Maintainers, agents and the user
can edit this file. Add evidence and limits when updating a capability.

Inventory established November 9, 2026 from existing repository documentation.
“Built” means an implementation exists within the linked scope. It does not mean
released, physically validated or verified on every platform. Linked reports
record historical checks on particular builds; this inventory is not a fresh
test run. See the [release review](docs/release-review-v0.5.md) for distribution
claims and the [coverage matrix](examples/grasshopper/VERIFICATION.md) for required
example checks.

## Implemented capabilities

| Capability | Current scope and important limits | Guide and evidence |
| --- | --- | --- |
| Function inventory and coverage ratchet | Syntax inventory of first-party Python and plugin C#, actual Python function-entry evidence, and instrumented .NET state contracts. Rejects new/changed untested functions, lost coverage and stale reports. Historical and host-only gaps remain HAWA-026; execution does not establish assertion quality. | [Function policy](docs/function-testing.md), [matrix](docs/function-test-matrix.md) |
| Embedded Python/PyTorch LBM | Runs inside Rhino's Python 3.9 environment with pinned dependencies. CPU/MPS evidence exists; CUDA and Windows qualification remain open in HAWA-002. | [Native guide](docs/native-v0.5.md), [backport](docs/backport.md) |
| Native geometry and case setup | Selected closed meshes/solid Breps, editable physical domain/fluid settings and one shared case per document. | [Native guide](docs/native-v0.5.md), [full review](docs/review-full-v0.5.md) |
| Native panel and GH live binding | Shared settings, direct/computed input ownership, revisions, stale-result handling, undo and saved idle cases. Public operations support agent workflows. | [Architecture](docs/architecture-v0.5.md), [agent operations](docs/agents/native-prototype.md), [state coverage](examples/grasshopper/VERIFICATION.md) |
| Background work and cooperative lifecycle | Preparation, solve/query jobs, pause/resume/cancel and cleanup; legacy failed-close retry has a scoped follow-up record. | [Cleanup review](docs/review-cleanup-v0.5.md), [architecture](docs/architecture-v0.5.md) |
| Field visualization | Scalar slices, vectors, streamlines, snapshot planes/contours/isosurfaces, surface sampling and legends. Native/GH capabilities differ; integrated movable vector slices remain HAWA-007. | [Plugin guide](docs/plugin.md), [node catalogue](docs/node-catalog-v0.5.md) |
| Record and playback | Field snapshots, physical-time metadata, playback and particle paths within documented formats and limits. | [GH examples](examples/grasshopper/README.md), [0.4 report](docs/release-notes-v0.4.0.md) |
| Asynchronous design search | Completed-candidate objectives, best-result history and cooperative controls. Hull geometry is an example recipe, not a public hull-construction service. | [Hull workflow](docs/hull-optimization.md), [node boundary](docs/node-catalog-v0.5.md) |
| Local airfoil and wing tools | Offline coordinates/NACA generation, supplied local polars and attached-flow lifting line. Bundled polar is synthetic format data; no viscous/stall CFD claim. | [Plugin guide](docs/plugin.md), [release limits](docs/release-notes-v0.4.0.md) |
| Curved stationary walls and fixed refinement | Experimental curved links and one fixed 2:1 BGK patch with explicit unsupported combinations. Multiple-region refinement remains HAWA-009. | [0.4 numerical evidence](docs/release-notes-v0.4.0.md), [coverage](examples/grasshopper/VERIFICATION.md) |
| Prescribed rigid motion and cycle objectives | Translation/rotation/oscillation, raw loads and complete-cycle search. No force-driven body response, free surface, buoyancy or validated propeller prediction. | [Motion guide](docs/moving-surfaces-v0.4.md), [motion evidence](docs/verification-motion-v0.4.json) |
| Result quality and offline inlet transfer | Bounded Mach/density/finite-state quality policy and v1 mapped X− velocity series, with source identity and coverage checks. Not convergence or atmospheric validation. | [Transfer guide](docs/boundary-transfer.md), [gate record](docs/boundary-transfer-review.md) |
| Shared boundary foundation | Physical patch schema plus bounded LBM NEE wall/slip/velocity/open reconstruction; corrected closure is explicitly versioned. Full reversing/cropped/atmospheric capability is not established. | [Boundary guide](docs/general-boundaries.md), [gate record](docs/general-boundaries-review.md) |
| Experimental neutral flow | Shifted-population regularized SGS, molecular-air scaling, sampled/filtered planar rough-floor stress and restart state. External mode adds halo-classified cropped buildings, side/top velocity or open faces, pressure reference and measured link mass budget. Analytic wall, convected-disturbance, stationary-channel and scoped CPU/MPS/Rhino checks pass. Full atmospheric accuracy and nesting qualification remain open. | [Coupling review](docs/neutral-coupling-review.md), [verification](docs/verification-neutral-coupling.json); HAWA-003/004/011 in [issues](issues.md) |
| Compatibility and example coverage gate | G6 enumerates 102,459 finite contract rows, detects incomplete/stale evidence and audits all public nodes against annotated GH workflows. CPU/MPS local checks pass; CUDA is blocked. Arbitrary graphs and continuous inputs are not exhaustively enumerated. | [G6 guide](docs/compatibility-matrix.md), [machine report](docs/verification-compatibility.json) |

## Atmospheric transfer development (November 9, 2026)

BoundarySeries v2 now carries timed multi-face velocity, gauge pressure, kinetic
strain, initial fields, geometry hashes and absolute source time. Neutral
recordings include the stress data required for LBM reconstruction. Spatial
roughness and Flow Statistics operations have GH components. Boundary Patch adds
an explicit pressure-derived backflow option; old archives retain velocity mode.
These changes are **built and under verification**, not a completed release.

The first 12,000-step AIJ Case I comparison (4 cells/H, CPU, measured mean inlet)
passed its bounded checks, but later runs fail qualification: the current 40,000-step
4-cells/H run has 64.84% streamwise hit rate (66% required). The older 8-cells/H
run has 75.82% hit rate but 5.44% stationarity change (5% maximum). Resolved TKE is
poorly reproduced. The current 60,000-step 6-cells/H MPS run passes its bounded mean-velocity/stationarity checks (72.53% hits, 1.83% change), but TKE relative L2 error is 95.26%. Longer same-grid nesting also misses mean/RMS and stationarity
limits; the 2:1 comparison misses mean/RMS limits. These are retained failures, not
validated atmospheric results. [Contract and evidence scope](docs/atmospheric-nesting-implementation.md).

The development views accept several same-time frames, use the finest containing
domain and trim slice faces at halfway solid boundaries. Reconstructed display
colours remain separate from raw samples. Example 33 demonstrates three imported
uniform grids and a shared height-controlled slice. Host and lifecycle checks pass within the recorded scope. These changes are
not released.

## Transfer/display repairs verified locally

- **HAWA-023 closed:** disjoint bodies in a shared building list are excluded
  conservatively; cropped/intersecting bodies retain local and halo classification.
  The three-stage CPU/MPS workflow and archive checks pass.
- **HAWA-024 closed for the declared snapshot views:** same-time multi-frame
  sampling, finest ownership, disjoint-gap clipping and halfway-wall plane trimming
  pass the field matrix and live GH checks. Legacy live views retain their contracts;
  curved-link/derivative reconstruction remains explicitly outside this repair.
- **HAWA-025 closed:** retained UI polling reaches completion through intervening
  solutions and pause/resume. Saved enabled graphs reopen idle. Disposal and failed
  cleanup recovery leave zero jobs/sessions/workers/refreshes across five legacy
  component families with the native timer disabled.

Evidence: [transfer review](docs/neutral-transfer-review.md),
[machine record](docs/verification-neutral-transfer.json). The atmospheric
qualification failures remain open in HAWA-021/022; these repairs do not close them.

## History

### November 9 2026 function testing gate

Added the source/signature/test matrix, coverage.py call evidence, Roslyn C#
inventory and Coverlet state-contract measurement. The ratchet rejects new or
changed untested functions, lost coverage and stale committed reports; PR CI uses
the base commit's baseline. Local evidence: 614 Python passes, 32 CUDA skips and
33 state-contract passes. Existing debt remains HAWA-026. No solver or host
behavior changed; hosted CI and the long numerical gates were not run for this
increment. [Review](docs/review-function-testing.md).

### November 9 2026 compatibility gate

- **HAWA-019 closed for finite compatibility coverage:** executable G6 products,
  independent accept/reject rules, exact evidence checks and enum/node drift tests.
  97,418 expected results, zero failures, 1,873 CUDA rows blocked. 575 Python tests
  and 33 state contracts pass locally. [Scope and evidence](docs/compatibility-matrix.md).
- Added annotated **31** (tunnel/probes/checkpoints) and **32** (translation/recorded
  particles); both run in Rhino. All 52 public nodes now appear in 30 idle GH
  definitions with no archive errors. This is not a fresh simulation of every old
  example or exhaustive arbitrary-graph coverage.
- **HAWA-020 closed:** matrix-discovered 2D streamline broadcasting failure repaired
  in immutable and legacy field paths; all field product rows and planar-seed
  regressions pass. No numerical tolerance was relaxed.


### November 9 2026 neutral coupling and failed-gate repairs

- **HAWA-016 closed for the startup/settling test:** preserved the failed 24³
  startup result, diagnosed absent initial turbulent stress, added sampled/filtered
  wall reference and verified analytic wall/drive identities. A 200k-step CPU
  rough-channel run passes the unchanged 2%/5%/5% settling criteria; the coarse
  log-law metric has one independent probe. Atmospheric model qualification remains
  HAWA-003/011. [Evidence](docs/neutral-coupling-review.md).
- **HAWA-017 closed:** convective outgoing reconstruction reduces the enlarged-domain
  shear-pulse error from 18.28% to 2.34% (10% limit). Rough/open corner corrections
  preserve mass and applied tangential impulse. Cropped-body halo ownership and
  CPU/MPS regressions pass.
- **HAWA-018 closed:** old precursor archives load six original inputs and append
  three defaults without missing-chunk warnings. Parameter GUIDs and source wires
  survive, and examples 28–30 save/reopen correctly.
- Added annotated **example 30**. Live Rhino: MPS 1000 steps, CPU recovery 400,
  pause, invalid-input withholding/recovery and close during run. Examples 28–29
  still run. Development bundle only; Windows/CUDA and full atmospheric validation
  remain unverified.

### November 9 2026 project tracking established

Added the open-work and implemented-capability registers, linked them from the
entry documentation, and established maintenance rules in `AGENTS.md`. This is a
documentation change, with no solver, runtime, GH archive or release change.
See the [documentation review](docs/review-project-tracking.md).

### Earlier completed work retained as evidence

These are a concise index of existing records, not newly verified completions:

- [0.4 closeout](docs/closeout-v0.4.md): frozen experimental feature baseline,
  bundled source/licences and supported examples; numerical limits remain.
- [0.5 native work](docs/review-full-v0.5.md): selected geometry, shared state and
  native/GH workflows; read the later cleanup follow-up before treating its old
  cleanup finding as current.
- [Legacy GH cleanup repair](docs/review-cleanup-v0.5.md): retained retry ownership
  and fault-injection coverage close that finding for the recorded host/build.
- [Boundary foundation repairs](docs/general-boundaries-review.md): mapped/curved
  composition, slip-edge and incoming/wall findings have scoped repairs and
  regressions. Broader boundary qualification remains open as HAWA-004.

## Recording completed work

Keep this inventory concise and update existing rows before adding overlapping
ones. Add dated history for meaningful completions, preserving the `HAWA-NNN` ID
when closing an issue. Include what changed, affected scope/version, actual
checks/device, omissions, remaining limits and a link to the review or report.
Distinguish implemented, locally verified, packaged and publicly released states.
Use the next unique ID for newly discovered follow-up work in `issues.md`.
