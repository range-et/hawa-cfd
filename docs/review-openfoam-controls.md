# OpenFOAM Slice 1 Control Verification Review (#126, #127)

- **Date:** November 23, 2026
- **Author / reviewer:** Antigravity primary agent (self-review only; independent numerical reviewer still pending before release-gate enforcement)
- **Scope:** Slice 1 headless physical-case handoff (`src/hawa/openfoam.py`), versioned pydantic schema (`hawa-openfoam-case-1`), atomic OpenFOAM v2606 case generator, `checkMesh`/probe parsers, and Channel (`07`) + Cavity (`06`) cross-solver verification harness (`scripts/compare_openfoam_controls.py`).
- **Environment:** macOS arm64, Python 3.9.25 (`.venv`) and Python 3.12.4 (`.venv-dev`), externally installed **OpenFOAM v2606** (`darwin64ClangDPInt32Opt`, `/opt/homebrew/bin/openfoam2606`), Hawa CPU (`torch.float32` for `WindFlow` channel, `torch.float64` for `Cavity2D`).
- **Evidence JSON:** [verification-openfoam-controls.json](verification-openfoam-controls.json)
- **Raw OpenFOAM cases:** `results/openfoam/controls/` (gitignored local run artifacts)

## Measured Cross-Solver Results

### 1. Control 07 — Laminar 2D Poiseuille Channel (`WindFlow` + `hawa-nee-v1` vs OpenFOAM `simpleFoam`)

Physical case: $L_x = 4.0\text{ m}$, $L_y = 1.0\text{ m}$, $U_{\max} = 0.5\text{ m/s}$, $\nu = 0.025\text{ m}^2/\text{s}$, $\rho = 1.225\text{ kg/m}^3$ ($\text{Re} = 20$), parabolic inlet on `x-`, pressure outlet $p = 0\text{ Pa}$ on `x+`, fixed no-slip walls on `y-`/`y+`, periodic/empty in `z`.
Analytic solution: $u_x(y) = 4 U_{\max}(y/L_y)(1 - y/L_y)$, $dp/dx = -0.12250\text{ Pa/m}$, $\Delta p(x=1\to 3) = 0.24500\text{ Pa}$.

| Grid (`ny`) | Role | OF `simpleFoam` | Hawa CPU (`WindFlow`) | `ux(2, 0.5)` Hawa / OF / Analytic (m/s) | `dp/dx` Hawa / OF / Analytic (Pa/m) | Hawa vs OF `u_L2` | Hawa vs OF `u_Linf` | Hawa vs OF `dp_Linf` | Gate |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| `10` | Coarse baseline | Converged (`148` it, 400 cells, `Mesh OK`) | Settled (`7000` steps, `40.41 s`, $\tau = 0.5433$) | `0.50772` / `0.49265` / `0.50000` | `-0.12968` / `-0.12069` / `-0.12250` | `2.348%` | `3.125%` | `7.446%` | Baseline |
| `20` | Resolved gate | Converged (`143` it, 1600 cells, `Mesh OK`) | Settled (`12000` steps, `34.64 s`, $\tau = 0.5866$) | `0.50243` / `0.49813` / `0.50000` | `-0.12464` / `-0.12204` / `-0.12250` | `0.694%` | `0.963%` | `2.128%` | **PASS** (<2% / <5%) |
| `40` | Resolved gate | Converged (`268` it, 6400 cells, `Mesh OK`) | Settled (`22000` steps, `31.75 s`, $\tau = 0.6732$) | `0.50116` / `0.49953` / `0.50000` | `-0.12356` / `-0.12238` / `-0.12250` | `0.283%` | `0.429%` | `0.964%` | **PASS** (<2% / <5%) |

- Both solvers converge monotonically toward the analytic solution as the grid refines (`u_L2`: `2.348% -> 0.694% -> 0.283%`; `dp_Linf`: `7.446% -> 2.128% -> 0.964%`).
- OpenFOAM's `ny=40` case also demonstrated why kinematic-pressure conversion ($\rho \cdot p_{\text{kin}}$) and residual control (`1e-7`) matter: at `1e-9` the zero cross-stream velocity component $U_y \approx 10^{-13}$ caused `simpleFoam` to stall on `Uy` normalized residual despite `Ux` (`1.3e-13`) and `p` (`1.4e-12`) reaching machine precision.

### 2. Control 06 — Lid-Driven 2D Cavity (`Cavity2D` vs OpenFOAM `simpleFoam`, $\text{Re} = 10$)

Physical case: unit square $[0, 1] \times [0, 1]\text{ m}$, $U_{\text{lid}} = 1.0\text{ m/s}$, $\nu = 0.1\text{ m}^2/\text{s}$, $\rho = 1.0\text{ kg/m}^3$, sampled at 7 fixed interior SI probes and 2 horizontal pressure pairs.

| Config | OF `simpleFoam` | Hawa CPU (`Cavity2D`, FP64) | `ux(0.5, 0.5)` Hawa / OF | `ux(0.5, 0.75)` Hawa / OF | `dp_upper_lr` Hawa / OF (Pa) | `u_L2` | `u_Linf` |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| `n=32, Ma=0.05` | Converged (`120` it) | `3880` steps, $\tau = 0.7771$ | `-0.17732` / `-0.20287` | `+0.06567` / `-0.02921` | `+0.82110` / `+0.68539` | `5.532%` | `9.653%` |
| `n=64, Ma=0.05` | Converged (`403` it) | `7760` steps, $\tau = 1.0543$ | `-0.17927` / `-0.20459` | `+0.02266` / `-0.03121` | `+0.71517` / `+0.69308` | `3.959%` | `5.798%` |
| `n=64, Ma=0.015` | Converged (`403` it) | `25865` steps, $\tau = 0.6663$ | `-0.19490` / `-0.20459` | `+0.01408` / `-0.03121` | `+0.76591` / `+0.69308` | `2.511%` | `4.621%` |

**Diagnostic findings (kept visible, not hidden by relaxed limits):**
1. At fixed acoustic scaling (`Ma = 0.05`, shipped `cases.py` default), refining `n=32 -> 64` pushes BGK relaxation time $\tau$ from `0.777` to `1.054`, holding centerline `ux(0.5, 0.5)` ~12.4% below OpenFOAM. Switching to diffusive scaling (`Ma = 0.015`, $\tau = 0.666$) cuts the centerline discrepancy from 12.4% to 4.7% and `u_L2` from `3.96%` to `2.51%`.
2. `lt.Cavity2D` places bounce-back walls at $x \in [0.5/n, 1-1.5/n]$, $y_{\min} = 0.5/n$ and an `EquilibriumBoundaryPU` lid at $y_{\max} = 1 - 1/n$, shifting the effective lid downward by $1/n$ right near the $u_x = 0$ sign reversal around $y \approx 0.75$. Cavity (`06`) therefore remains diagnostic evidence rather than a tight pass gate until `Cavity2D` wall alignment or a full-node lid condition is addressed.

## Gate Summary

| Gate | Reviewer | Decision | Evidence / Omissions |
| --- | --- | --- | --- |
| G0 research | Agent self-review | PASS (Slice 1) | OpenFOAM v2606 tutorials verified locally; deprecation-free `nonuniform List<vector>` parabolic inlet; cross-solver verification distinguished from experimental validation. |
| G1 architecture | Agent self-review | PASS (Slice 1) | Versioned `hawa-openfoam-case-1` pydantic schema (`extra="forbid"`, pinned 2.13.5, JSON Schema snapshot); explicit rejection of unsupported features; atomic publish with rollback; no new public GH node. |
| G2 reliability | Agent self-review | PASS | 100% measured line/function coverage on `src/hawa/openfoam.py` and `scripts/compare_openfoam_controls.py`; `tests/test_openfoam.py` + `tests/test_payload_schemas.py` pass on Python 3.9 and 3.12; `ruff check .` passes; strict headless function coverage gate verified. |
| G3 numerical physics | Agent self-review | PASS (Channel 07 CPU) / DIAGNOSTIC (Cavity 06) | Channel `ny=20, 40` pass <2% velocity and <5% pressure-drop gates with monotonic 3-grid convergence to analytic solution; Cavity 06 diagnoses `tau` scaling and `1/n` lid-offset effects. Omissions: MPS/CUDA runs, Sphere (14), Cylinder (16), Complex body (22/10), independent numerical reviewer sign-off. |
| G4 UI/UX | Agent self-review | NOT APPLICABLE | Headless Python handoff/comparison slice only; no Rhino/GH UI or `.gh` archive changes. |
| G5 release | Agent self-review | NOT APPLICABLE | No CI release blocker or Yak package change; OpenFOAM remains externally installed. |
| G6 compatibility | Agent self-review | PASS (Slice 1 contract) | Supported vs rejected boundary/feature combinations tested explicitly in `tests/test_openfoam.py`. |
