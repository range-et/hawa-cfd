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
| 1 | Molecular-air numerical treatment on coarse grids | Collision/precision strategy, weak-strain and zero-SGS cases, decay/stress tests, CPU64 reference and CPU/MPS comparison at equal physical times. Keep molecular viscosity unchanged. | Experimental shifted solver preserves small relaxation increments; CPU64/CPU/MPS checks pass. General high-Re accuracy envelope remains open. |
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
