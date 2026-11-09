# Boundary transfer development gate record

- Date: November 8, 2026. Author/reviewer: Codex, self-review across all roles.
- Scope: sampled quality diagnostics, offline mapped vector inlet, three GH nodes,
  example 24, icons, native quality status, and development packaging paths.
- Claims: bounded implementation verification and workflow demonstration. No
  atmospheric, conservative coupling, convergence or engineering validation claim.
- Runtime: macOS ARM64, Rhino 8.36, embedded Python 3.9 and pinned PyTorch;
  numerical tests use FP32 CPU/MPS. CUDA and Windows were unavailable.
- References: existing pinned Lettuce equilibrium boundary and simulation ordering;
  [mapped boundary reference](https://doc.openfoam.com/2306/tools/processing/boundary-conditions/rtm/derived/inlet/timeVaryingMappedFixedValue/)
  from the design research. Direct refetch returned 403 during implementation;
  no external source was copied. No dependency/licence change.
- Numerical acceptance fixed in tests: uniform regression atol=2e-7/rtol=2e-6;
  prescribed vector profile atol=5e-6; CPU/MPS velocity atol=2e-5/rtol=3e-4.
- Example: parent 17×9×9, dx=0.2 m; child 13×13×13, dx=0.1 m;
  U=1 m/s, nu=0.1 m²/s, rho=1.225 kg/m³, reference lattice Mach=0.03;
  60/120 steps at equal physical time 0.2078460969 s. Parent frames every 5 steps.
  Startup is included; there is no settled-flow claim or random input.

| Gate | Actual reviewer | Decision | Evidence / scope |
| --- | --- | --- | --- |
| G0 research | Codex | PASS, bounded | Scope and limitations in boundary-transfer.md and nested-flow-roadmap.md. Existing equilibrium reconstruction retained, with explicit upstream limitations. Atmospheric work deferred. |
| G1 architecture | Codex | PASS, bounded | Immutable file hash and physical grid binding; per-case inlet ownership; worker query/cancel path; no blocking GH mapping; unsupported combinations rejected. 33 shared-state contracts pass. |
| G2 reliability | Codex | PASS on tested host | 157 Hawa tests pass, 30 skip, 4 existing warnings. Plugin assemblies build. Corrupt/mismatched files, time coverage, unit transforms, cancellation and checkpoint quality history have regressions. |
| G3 numerics | Codex | PASS for stated verification | Uniform/time-varying inlet tests; source/mask rejection; CPU/MPS comparison. Full 60/120-step transfer max velocity difference 1.2636184692e-5 m/s. Upstream and backport suites each: 419 pass, 884 skip, 40 warnings. Engine field/checkpoint comparison passes CPU, CPU64, MPS. |
| G4 GH workflow | Codex | PASS on Rhino/macOS MPS | Record → Capture → Read → Solve completed at matching physical time. Valid field meshes; duration rejection and recovery; idle reopen; annotation wire preservation; canvas and viewport inspected. Final installed-source rerun completed with zero errors; native CPU 20-step smoke completed and docked quality label was visually inspected. |
| G5 release | Codex | BLOCKED for general release | Development bundle only. CUDA, Windows and clean installation unverified. No frozen release, website or public package replaced. |

## Regression findings and resolutions

1. Streaming modifies pre-stream equilibrium inlet values. Mapped inlet now
   reapplies its velocity plane after streaming. The completed-step profile test
   passes its original tolerance. This is a defined experimental boundary, not a
   claim of a universally accurate open boundary.
2. Checkpoint restore could erase earlier rejected quality. Quality history is
   saved/restored, with validation before population mutation. Legacy history is
   labelled warning and excluded from normal transfer.
3. Periodic faces do not represent net external flow. Diagnostics report their
   individual estimates but exclude periodic pairs from the external-flux total.
   This nodal estimate remains distinct from a discrete conservation residual.
4. View comparisons used auto-ranged legacy slices. The example now includes
   shared 0–1.5 m/s colour settings and a legend. Legacy slice nodes are hidden;
   existing object IDs and wires were preserved during annotation.

## Reproduction and coverage

Run `.venv/bin/python -m pytest tests -q`,
`dotnet run --project tests/dotnet/StateContracts`, and
`.venv/bin/python scripts/verify_boundary_transfer.py --output <new-directory>`.
The latter requires a fresh directory. Isolated reference checks use
`scripts/run_upstream_tests.py` with and without `--reference`, and
`scripts/compare_engines.py`. Full logs are under `results/boundary-transfer/`.
The upstream skips reflect unavailable CUDA/native configurations and the suite's
existing exclusions; they are not passes. PorousMedium parity remains unresolved.

For Rhino, follow [the example instructions](boundary-transfer.md) using a copy.
Set new paths, enable Record, wait, enable Capture, wait, then enable Solve. Inspect
actual outputs and physical times. Set Run false; change target from 120 to 121;
enable Run and expect `Target exceeds boundary time coverage`. Restore target 120,
set Run false then true and require completion. Close only the owned definition.
Reopen the shipped file and require all controls off. The annotation check retains
functional wires. Native/GH binding behavior was not changed; its contract suite
was rerun, but unrelated full native lifecycle harnesses were not repeated.

Evidence: [verification summary and hashes](verification-boundary-transfer.json),
[numerical report](boundary-transfer-numerical.json),
[canvas](captures/boundary-transfer/canvas.png),
[viewport](captures/boundary-transfer/viewport.png). These are a short demonstration,
not an animation or a publication video. No video was requested in this step.

## Remaining limits

The quality policy covers sampled Mach/density/finite state and reports estimated
flux/backflow. It does not measure convergence, statistical confidence, full
mass-storage residuals, turbulence fidelity or unsampled extrema. Rejected finite
runs may finish for diagnosis; transfer is blocked. Only periodic transverse child
faces are supported. Conservative boundary reconstruction, wall/open-edge
intersections, coarsening filters and multi-face backflow need further numerical
work. Boundary-only recording during the solve and arbitrary external file-format
adapters remain future work; this version captures from full parent recordings.
The native panel exposes quality but boundary import is currently a GH/API feature.

## Subsequent composition finding

The next-stage scope audit reproduced a mapped-inlet plus curved-wall failure
that the initial bounded tests did not cover. This combination is accepted by
preflight but does not preserve the specified inlet profile. It blocks extending
the verification claim to curved-wall child cases. See
[the scope assessment](general-boundaries-atmosphere-scope.md) for evidence and
the required regression/gating work. The original example uses no curved child
walls. No production code was changed during this later assessment.
