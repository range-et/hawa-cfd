# Neutral atmosphere and rough walls: delivery record

November 9, 2026. Implementation owner and current reviewer: Codex (self-review).
The user has authorised the complete feature set and its tests. Individual rows
below do not require another scope approval. This record is the completion checklist;
**the feature set is not complete or released**.

## Current implementation update

See [the neutral coupling review](neutral-coupling-review.md) for the current
shifted solver, sampled/filtered rough floor, halo-classified buildings, side/top
open faces and convective outlet repair. The earlier startup-profile failure is
retained and diagnosed; stationary-channel checks use separate settling and
averaging. The matrix below now distinguishes implemented operators from remaining
physical qualification. The original preparation results below remain historical.


## Supported target

Neutral, isothermal air above fixed terrain, resolved buildings and an impermeable
water surface. Results must include mean velocity, pressure, resolved fluctuations,
surface air traction and separate numerical/model/statistical quality assessments.
Water roughness is initially prescribed and subject to sensitivity checks. This
scope does not calculate pond circulation, waves, buoyancy or thermal stability.

Use reusable physics, boundary, transfer and statistics operations. Do not add
City or Pond components. Preserve old archives and their numerical methods.

## Completion contract

| Order | Deliverable | Required completion evidence | Current status |
| --- | --- | --- | --- |
| 1 | Molecular-air numerical treatment on coarse grids | Collision/precision strategy, weak-strain and zero-SGS cases, decay/stress tests, CPU64 reference and CPU/MPS comparison at equal physical times. Keep molecular viscosity unchanged. | Strategy selected (November 10): unchanged shifted regularized SGS collision, FP32 storage, SGS-dominated LES with a runtime storage-dissipation diagnostic. FP32 storage does **not** represent molecular air dissipation at 0.1/1/10 m; see the precision experiment below. On MPS the diagnostic cannot claim "resolved" (indeterminate); MPS rerun is batched in [#53](https://github.com/range-et/hawa-cfd/issues/53). Double-float storage is [#51](https://github.com/range-et/hawa-cfd/issues/51). |
| 2 | Neutral mean profile and roughness contract | SI units, tangential vectors, height/roughness conventions, rotation, zero speed, reversal, invalid input and matching friction velocity | Implemented SI profile and matching integrated rough-floor relation; explicit experimental contract. |
| 3 | Planar modelled wall operator | Impermeability, discrete wall impulse and mass balance, shear sign, smooth/rough applicability, sample-height and grid sensitivity. Rough-wall channel reference and total-stress budget. | Sample/filter/checkpoint state, exact impulse/mass tests and analytic channel checks pass. Atmospheric sampling/grid qualification remains open. |
| 4 | Empty-domain neutral turbulent flow | Compatible wall/inflow/top/forcing. Precursor or verified turbulence generation. Mean-profile preservation, Reynolds stresses, spectrum and averaging uncertainty over stated flow-through times. | Open; see the current review for bounded implementation |
| 5 | General boundaries and cropped geometry | Adjacent incoming/outgoing faces, reversal, corner ownership, fluid/solid masks and halo consistency; flux and outgoing-vortex reflection tests against enlarged-domain references. | Implemented shifted incoming-link ownership, halo geometry and side/top open/velocity conditions. Pulse and corner budget checks pass; general vortex/acoustic qualification remains open. |
| 6 | BoundarySeries v2 and nesting | World-space multiple-face time series; source geometry/model provenance, transforms, masks, filtering, coverage, flux residuals, child spin-up and statistics. Retain v1 reader. | Development v2 implemented for neutral external flow: velocity/pressure/strain, initial state, wall history where compatible, masks, time windows and provenance. Manufactured checks pass; nested statistical qualification fails and remains open. |
| 7 | Building and land/water transitions | Appropriate external experimental reference; roughness-transition recovery, domain/grid/wind-direction sensitivity and pressure/wall-stress observables. No assumed applicability of an equilibrium wall law in separation. | NOT VALIDATED |
| 8 | GH/native delivery | Shared contracts, reusable model/wall/profile/statistics operations; annotated empty-domain, obstacle, roughness-transition and nested examples. Worker cancellation, stale output, edit/pause/close/reopen and live CPU/MPS host checks. | GH Neutral Flow, Roughness and Flow Statistics implemented. Annotated 33 adds three-stage transfer and shared views. Automatic scheduling/lifecycle checks remain active; native atmospheric editing remains open. |
| 9 | Distribution | Exact tested-source package, examples, agent recipes, model limits, gate record; CUDA/Windows require actual hardware evidence. | NOT RELEASED |

Stages 1 and 3 must qualify before public atmospheric controls are advertised.
Separate uniform grids remain the first nesting target. Sparse storage, arbitrary
volume-mesh import and wall-contact multilevel refinement are separate workstreams.
No assumption that a 10:1 grid jump preserves turbulence.

## Historical preparation increment

`src/hawa/atmosphere.py` provides a shifted neutral mean profile,
`U(h) = Uref log(1+h/z0)/log(1+href/z0)`, and the matching equilibrium
wall-traction relation `u* = kappa |Ut|/log(1+h/z0)`,
`t_fluid = -rho u*² Ut/|Ut|`. The rest limit uses a division-free expression.
Vectors use a unit surface normal, heights are distances above the aerodynamic
plane, and displacement is zero. Reference/sample heights must exceed z0.
Roughness length is not equivalent sand-grain roughness or terrain elevation.

These are SI preparation/verification functions. They do not impose stress on
populations, generate turbulent fluctuations, certify a logarithmic layer, or
make a wall impermeable. They are deliberately not exposed as a completed GH
atmospheric model.

`check_case` retains the production relaxation limit and now returns a structured
scaling report for accepted physical cases. Its rejection message reports both
the physical and FP32-represented relaxation margin. Cases and hashes are not
mutated. Existing collision operators, population storage and stepping are unchanged.

## Reproduced numerical blocker

At Uref=5 m/s, molecular kinematic viscosity=1.5e-5 m²/s and Ma_ref=0.05:

| Cell width | Physical tau−0.5 | FP32 represented margin | Production preflight |
| --- | --- | --- | --- |
| 0.1 m | 2.5980762e-6 | 2.6226044e-6 | accepts scaling only |
| 1 m | 2.5980762e-7 | 2.3841858e-7 | rejects |
| 10 m | 2.5980762e-8 | 0 | rejects |

The actual tensor representations agree on CPU and MPS. At 10 m, storing tau in
FP32 loses the entire molecular relaxation increment. This is not proof that all
high-Re LBM methods fail: it is evidence that the present representation cannot
simply be relabelled an atmospheric model. A suitable collision/precision/SGS/wall
combination still needs selection and verification. SGS does not guarantee a
positive viscosity increment at every point or time. Increasing physical
viscosity, disabling the check or switching to CPU64 alone does not qualify LES.

Reproduce:

```sh
.venv/bin/python scripts/verify_atmospheric_scaling.py --output results/atmosphere-development/scaling.json
.venv/bin/python -m pytest tests/test_atmosphere.py tests/test_general_boundaries.py -q
.venv/bin/python -m pytest tests -q
```

The scaling harness intentionally exits **2**, with `passed: false`, because the
requested inventory includes unsupported grids. It does not run a flow simulation.
Detailed evidence is in `results/atmosphere-development/` (local development logs).

## Physical-viscosity precision experiment (HAWA-003, November 10, 2026)

Codex, self-review; [#13](https://github.com/range-et/hawa-cfd/issues/13). CPU table: Linux x64
orb, Python 3.9.25, PyTorch 2.8.0+cpu, commit `1d50235`. The final head reproduces these CPU
numbers bit for bit. MPS: M3 Max, macOS 27.0.1,
PyTorch 2.8.0, same commit (below). **CUDA was not tested in this round**; it is
deferred to a separate CUDA environment ([#52](https://github.com/range-et/hawa-cfd/issues/52)).

`scripts/verify_atmospheric_precision.py` runs a periodic D3Q19 transverse shear
wave on a uniform perpendicular mean flow (stored populations then carry a realistic
mean-flow magnitude). It uses the production shifted storage and
`shifted-regularized-sgs-v1` collision at Uref=5 m/s, nu=1.5e-5 m²/s, Ma_ref=0.05.
The effective relaxation increment comes from the decay of the mode over the last
90% of the run. FP32 and CPU FP64 cases run the same steps, so they cover equal
physical times. The criteria are in the script docstring; the 5% tolerance is the
existing atmospheric target.

| Case (N=32 unless stated) | FP64 / molecular | FP32 vs FP64 | Storage diagnostic (model share) |
| --- | --- | --- | --- |
| Cs=0, weak strain, dx 0.1 / 1 / 10 m | 1.0033 / 1.0042 / 1.0135 | −100% / −144% / −603% (wave not damped, or grows) | 0 / 0 / 0, below storage precision |
| Cs=.17, wave 0.1 Uref, dx 0.1 / 1 / 10 m | SGS-dominated | −3.9% / −3.7% / −3.0% | 0.82, resolved |
| Cs=.17, wave 0.01 Uref, dx 0.1 / 1 / 10 m | SGS-dominated | −97% / −99% / −101% | 0, below |
| Synthetic margin 1e-5 / 1e-4 / 1e-3 / 1e-2 (Cs=0, dx 1 m; calibration) | 1.003 | −94% / −24% / +0.17% / −0.03% | 0 / 0 / 0.99 / 1.00 |

Held-out validation was declared before it was measured. Cs=.17 at wave 0.03 Uref,
at N=64, and Cs=.3 at weak strain all fail in FP32 (−57%, −53%, −86%), and the
diagnostic reports each as below storage precision. N=16 at 10 m and wave 0.3 Uref
pass (−0.3%, −1.1%), and the diagnostic reports each as resolved. Margin 3e-3
passes. Margin 3e-4 is within 3.3% of FP64, but the diagnostic reports it as
below: a conservative miss. Criterion 3 (agreement in every case) therefore
**fails on 1 of 20 cases**, and the harness exits 2. The threshold was not
changed. No CPU case was falsely reported as resolved; Apple-silicon CPU FP32 on the
Mac gave the same agreement pattern (same single conservative miss).
[Tracked summary](verification-atmospheric-precision.json).

**MPS defect and fix.** On MPS FP32 at `1d50235`, the collision lost more dissipation
than CPU FP32 in the same cases. Two cases were falsely reported as resolved:
dx=0.1 m (−5.1% on MPS vs −4.2% on CPU) and dx=10 m (−9.7% vs −3.5%), both at Cs=.17
and wave 0.1 Uref. The margin-3e-4 conservative miss also appeared on MPS (−4.8%). The
diagnostic models only storage rounding and was calibrated with CPU FP32 arithmetic,
so it is not evidence of resolved dissipation on MPS. Policy
`hawa-storage-dissipation-v2` therefore reports `device` and `arithmetic_qualified`.
A share below 0.5 still reports `below-storage-precision` on any device, because
storage alone already loses that dissipation. On MPS, a share of 0.5 or more reports
`indeterminate-device-arithmetic` instead of `resolved`. The ratio, the 5% tolerance
and the criteria are unchanged. The harness now counts `false_resolved_cases`
separately from `conservative_misses`. The rule was not tuned to the two failed
cases: every MPS case that would claim resolved becomes indeterminate. The MPS
per-stage cause (which collision operation loses accuracy) is not yet isolated; a
probe is queued in the batched Mac session [#53](https://github.com/range-et/hawa-cfd/issues/53).

Decision for this round:

- **Collision:** keep `shifted-regularized-sgs-v1`. In FP64 it reproduces the molecular
  decay within 0.1–1.4% for increments down to 2.6e-8 (N=16–64).
- **Precision:** keep FP32 storage everywhere (`make_solver` is unchanged). MPS has no
  float64. FP32 storage cannot represent molecular air dissipation at 0.1, 1 or 10 m.
  Shifted storage already removes `w`, but the mean-flow part of the stored population
  still sets the rounding floor. A hi/lo FP32 storage prototype with FP32 collision
  arithmetic recovered only 0.43–8.9× of the molecular decay. Double-float storage
  with double-float collision arithmetic is [#51](https://github.com/range-et/hawa-cfd/issues/51),
  an unassigned follow-up.
- **Model:** at these spacings the solver is an SGS-dominated LES. The input molecular
  viscosity is unchanged, but storage cannot represent it. FP32 represents the SGS
  dissipation only where strain is strong enough. Quality reports now include
  `dissipation_storage`: the dissipation-weighted share of cells whose dissipative
  update is at least 10× the FP32 storage rounding, for the model total and the
  molecular part. The 10× ratio was calibrated on the cases above (error ≈ 0.3–0.7/R).
  The diagnostic does not change populations, status, transfer eligibility or guards.
  In a 48×48×24 CPU precursor it added 3–10% to step time.

Existing guards and tolerances are unchanged. Zero-SGS neutral cases are still accepted,
but they now report `molecular_status: below-storage-precision`. Rejecting them would
be a new contract decision and was not made here. This result does not qualify
atmospheric LES, wall models or turbulence. "Resolved" is qualified on CPU only.

| Gate | Decision | Evidence / limit |
| --- | --- | --- |
| G0 | PASS, bounded | Shear-wave analytic decay; Lehmann et al. and Latt–Chopard references above; no copied code |
| G1 | PASS | Additive quality field; collision numerics, storage, checkpoints and `make_solver` unchanged; shared-file split agreed with #11 |
| G2 | PASS for the declared scope | Strict headless function and line gate on the final head; targeted mutmut of this PR's lines: 440 mutants, 430 killed, 0 timeouts. The 10 survivors are reviewed in `atmospheric-precision-policy.json`: 4 equivalent, 3 decoration, 3 import or collection errors (counted as errors, not kills). |
| G3 | PASS for FP64 collision representation; **FAIL** for FP32 molecular representation and for complete diagnostic agreement (1/20 conservative on CPU) | Tracked summary; the MPS false-resolved defect is fixed by v2 and awaits the batched MPS rerun |
| G4 | NOT APPLICABLE | No GH or native change; the new quality field is not yet shown in the host |
| G5/G6 | BLOCKED | v2 MPS rerun batched in #53; no package. CUDA not tested in this round (deferred, #52) |

```sh
.venv/bin/python scripts/verify_atmospheric_precision.py --output results/hawa-003/precision-cpu.json
.venv/bin/python scripts/verify_atmospheric_precision.py --device cpu --device mps --output results/hawa-003/precision-mac.json   # Mac (#53)
```

## Acceptance definitions for subsequent implementation

Freeze benchmark configurations and numerical thresholds before each solver change.
Use independent reference data and report its uncertainty. Do not turn the following
candidate engineering targets into claims that have already passed:

- Empty-domain mean profile: initial target <=5% relative L2 drift in the declared
  surface-layer sampling interval, after spin-up; compare multiple downstream
  stations and at least three grids. Separately compare total shear and forcing.
- Wall operator: population-level mass and impulse identities to precision-scaled
  tolerance; integrated channel wall stress within 5% of the imposed momentum
  budget on the qualified grids. This does not establish local separated-wall accuracy.
- Inflow: measured mean and Reynolds-stress tensor, spectra, integral scales and
  adjustment fetch. A mean profile or independent random noise does not supply
  resolved building wakes.
- Nesting: compare against a larger monolithic reference using common physical
  times/locations, mean and fluctuation statistics, sampling cadence, boundary
  placement and grid-ratio sensitivity. Declare any flux correction and measure it.
- Model applicability: warn/reject invalid wall samples, inadequate turbulence
  spin-up/averaging and unsuitable atmospheric stability. Retain the existing
  local Mach/density checks. A health pass alone does not establish wind accuracy.

## Research and attribution

Primary sources consulted November 9, 2026:

- [OpenFOAM v12 atmospheric profile](https://cpp.openfoam.org/v12/classFoam_1_1atmBoundaryLayer.html): shifted mean log-law convention and reference-height relationship. Its RANS k/epsilon prescription is not adopted as an LES turbulence inlet.
- [Han, Ooka and Kikumoto: wall-function bounce](https://arxiv.org/abs/2009.04352): wall shear must enter the population update; channel validation is distinct from evaluating a wall-law formula. This paper evaluates a smooth-wall Spalding treatment, not validation of Hawa's proposed rough-ground law.
- [PALM mesoscale nesting](https://docs.palm-model.org/25.10/Guide/LES_Model/Modules/Mesoscale_nesting/): turbulent adjustment and boundary mass-flux consistency are independent requirements for nested LES.

No source code or datasets from these works were copied. New Hawa code retains
GPL-3.0-only; existing third-party notices are unchanged.

## Gates for this increment

All reviews here are by the main Codex agent; there is no independent specialist
approval of the new atmospheric work.

| Gate | Decision | Evidence / claim boundary |
| --- | --- | --- |
| G0 research | PASS for preparation scope | Primary formulas and explicit physical limits above |
| G1 architecture | PASS for preparation scope | Stateless SI utilities; additive preflight report; unchanged case hashes, archives and ownership |
| G2 reliability | PASS for tested increment | Focused and full-suite results recorded below; production guards retained |
| G3 physics | PASS for constitutive identities; FAIL for requested production scaling | Law consistency/rotation/dissipation tests and actual CPU/MPS representation. Rough-wall and atmospheric flow remain unvalidated. |
| G4 UI/UX | NOT APPLICABLE to utilities; BLOCKED for complete delivery | No new public node or example, no Rhino session altered |
| G5 integration | BLOCKED for complete delivery | No package, install or release; CUDA and Windows untested |

Final full-suite run after range-validation hardening: **187 passed, 31 skipped,
4 existing MRT warnings**, 17.09 seconds. Evidence:
`results/atmosphere-development/pytest-final.log`. Skips remain unverified; this
does not qualify atmospheric flow, CUDA or Windows. The scaling experiment exits
2 as expected and remains a failed delivery gate, not a passing physical test.
