# Boundary foundation gate record

Development scope, November 9, 2026. Maintainer: main Codex agent. Independent
numerical reviewer: `/root/computational_physics_review`, explicitly requested by
the user in the preceding scope investigation. This is a bounded experimental
implementation, not a general atmospheric release.

## Gate decisions

| Gate | Decision and evidence |
| --- | --- |
| G0 Research | PASS for stated scope. Guo–Zheng–Shi NEE and official OpenFOAM SGS formulation checked. Full-node NEE selected; no claimed published convergence rate for our corners. Original code; no dependency/source licensing change. |
| G1 Architecture | PASS for bounded adapter. Physical schema separate from Torch adapter. Explicit method/version in case identity, disjoint node writers, immutable donors, early unsupported-combination checks. Existing worker/ownership paths reused; Check Case moved off solution thread. SPH/FV adapters, world-space series and native patch editor remain future work. |
| G2 Reliability | PASS for tested platform. Full Hawa suite: 175 passed, 31 skipped, 4 existing MRT warnings. StateContracts: 33 passed. Build succeeds. Live invalid-input, pause/recovery and document cleanup checks recorded below. |
| G3 Numerical | PASS for operator verification and bounded laminar/reference claims. Independent reviewer reran focused suite (17 passed, 1 CUDA skip at that revision) and closed both detected conflicts. CPU/MPS operator comparisons, composition, mapping with walls, SGS manufactured stress, rotation, frozen-donor stress, slip shear, positive/negative open branches and cropped interior comparison run. Analytic Couette/Poiseuille reports included. General reversing flow, reflection, arbitrary cropped boundaries, turbulence and physical-flux conservation remain BLOCKED/unqualified. |
| G4 Examples/UI | PASS for bounded macOS workflows: 25/26/27 each completed 400 MPS steps, zero component errors, valid field mesh. Annotated saved idle files, wireframe, blue-green legends and captures inspected. Pause, invalid-edge failure and repair exercised on 25. Final label-only assembly revision is separately smoke-checked; full numerical host runs used the identical boundary implementation. |
| G5 Integration | PASS for local development package checks; BLOCKED for unrestricted release. CUDA, Windows and clean dependency installation unavailable/unrun. No public release, commit, push or website publication in this task. |

G0/G1/G2/G4/G5 reviews were performed by the main agent as separate checks, not by
invented independent reviewers. The physics reviewer inspected implementation and
reports and ran the focused suite; they did not run the full suite or host checks.

## Findings and disposition

- **Mapped/curved-wall wrapper replacement — fixed.** Ordered coordinator retains
  both corrections. The 10-step prescribed-inlet regression meets 5e-6 m/s and
  records ten wall impulses. Direct overlapping writers reject.
- **Upstream SGS strain dependence — audited and corrected explicitly.** Vendor
  `smagorinsky` remains archived behavior. Hawa `smagorinsky-v1` implements the
  standard magnitude with an analytic effective-relaxation solution. The base
  viscosity guard remains unchanged.
- **Slip/slip edge penetration — fixed after independent review.** Every incident
  normal is constrained and odd reflected stress removed. Regression includes
  manufactured shear; arbitrary curved slip surfaces are not supported.
- **Open incoming/wall mismatch — fixed after independent review.** Incoming
  exterior values use the same shared-edge compatibility checks as velocity data.
- **FP32 NEE moment drift — reduced.** A strict 80-step uniform-direction test
  exposed small accumulated conserved-moment residuals. Projecting residuals and
  correcting reconstructed moments made the unchanged 2e-5 m/s test pass. Reversal
  is explicitly a manufactured reset to a uniform reversed state, not forcing
  from a transient external pressure history.
- **Unsupported refined coarse case — rejected.** Refined Solve now rejects either
  case carrying the general boundary set, including a general coarse case with
  a legacy fine case.
- **Stale transient boundary diagnostics on reset/load — fixed.** Clear report
  to compiled-plan metadata when populations/time are restored.
- **Duplicate install directory — fixed guard.** An initial install targeted
  Libraries/Hawa instead of Libraries and produced Hawa/Hawa. The prompt was
  closed, Rhino quit normally, duplicate bundle moved to the evidence folder,
  and the correct directory installed. The build now rejects that mistake.
- **Duplicate example legend planes — fixed.** Clear the default plane before
  assigning the example plane. Original functional IDs and wires retained.
- **Misleading generic face labels — fixed.** Domain Preview now labels X-/X+
  without hard-coded inlet/outlet roles, which can be Y-oriented in new cases.
- **Empty native preview overlay — removed from captures.** The fresh empty
  native case had no result/binding and showed field 0. It was closed through
  public CaseHub.Close before capturing GH output.

## Numerical evidence

`docs/general-boundaries-numerical.json` contains final six analytic runs with
13,17,25 wall-normal nodes, fixed physical dimensions and about 20 physical seconds.
Fields were initialized at analytic macroscopic profiles. Criteria, set before
measurement: relative profile L2 <4%; wall error <5e-6 m/s; mass change <2%.

Final Poiseuille errors: **3.13%, 1.64%, 0.634%**. Final Couette errors:
**0.0810%, 0.0329%, 0.2165%** (not monotonically convergent; FP32/scaling remains part
of the measured behavior). All six meet those criteria. The earlier coarse n=9
Poiseuille failure, **7.36%**, is retained in the report. No tolerance was widened.

Upstream reference and backport suites each: **419 passed, 884 skipped, 40 warnings**.
`compare_engines.py`: CPU, CPU64 and MPS fields/checkpoints passed. Those tests
check the retained vendor path; the corrected SGS model is checked independently.
Known PorousMedium CPU/MPS discrepancy remains unresolved. No CUDA pass is inferred.

Source logs: `results/general-boundaries/`. Final host reports include source
example path, state, quality outputs and mesh validity. The local evidence folder
also retains intermediate failures rather than relabelling them as final passes.

## Remaining work before linked atmospheric use

World-space multi-patch datasets; source/target solid reconciliation; adjacent open
corners; physically forced reversal and measured reflection; crop-face leakage and
extended-domain comparisons after settling; physical flux accounting; neutral-ABL
collision/SGS/rough-wall/inflow qualification; wall-compatible multi-level grids.
These remain separate research/implementation gates, not hidden behind completion.
