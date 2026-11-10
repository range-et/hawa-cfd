# Device smoke gate

[Script](../scripts/device_smoke.py) · [Committed policy](../scripts/device_smoke_policy.json) ·
[CI workflow](../.github/workflows/device-smoke.yml) · Issue [#57](https://github.com/range-et/hawa-cfd/issues/57)

The device smoke gate runs the same short, fixed set of existing solver checks on
Linux CPU (GitHub CI), Windows CUDA and Apple MPS. It takes about 20 seconds on
one CPU thread. Each case runs twice in one process:

- **Reference:** CPU, FP64.
- **Candidate:** the requested device with Hawa's FP32 production storage. On the
  CPU this is the CPU proxy of the device precision path.

Devices are never compared with each other. The committed policy declares every
check's class and tolerance before any device run. The tolerances are copied from
the named existing criteria and are not widened. Changing a class, tolerance or
case after device results are known is a criteria change; see the device
qualification protocol in [the issue workflow](github-issues.md).

This is a smoke gate. It does not establish convergence, physical accuracy,
long-window stability or performance.

## Cases

| Case | Path covered | Class and tolerance | Criterion source |
| --- | --- | --- | --- |
| `engine-2d` | Compatibility engine: BGK, TRT, Smagorinsky TGV, BGK cavity, Guo Poiseuille; iterations 0, 1, 10, 50 | bounded: rtol 3e-4, atol 2e-6 (pressure atol × pressure conversion scale) | `compare_engines.py` accelerator tolerance |
| `kbc-near-equilibrium` | One KBC collision of the stored HAWA-001 PorousMedium cell, 1×1 and 8×8 | bitwise: FP32 output equals the FP64 collision rounded to FP32 | `test_kbc_precision.py` |
| `neutral-shifted-regularized` | Neutral precursor, shifted regularized SGS, rough floor; 12³, 100 steps | bounded: velocity rtol 3e-4, atol 3e-5; relative mass change atol 1e-6 | `test_neutral.py::test_cpu_mps_reference` |
| `moving-sphere` | Oscillating sphere, interpolated moving bounce-back; 12 steps | bitwise solid mask; bounded populations rtol 3e-4, atol 3e-6 | `test_motion.py` device parity and mask equality |
| `curved-wall-channel` | Guo-forced BGK channel with interpolated wall links, q 0.25 and 0.75 | bounded: max speed rtol 3e-4, atol 2e-6 | `verify_cuda_benchmarks.py` wall rows |

Bitwise means identical bits after rounding the reference to the candidate dtype,
so it also distinguishes −0 from +0. Bounded means
`|candidate − reference| ≤ atol × scale + rtol × |reference|` for every element.
No case is statistical: confidence-bounded statistics need long windows that do
not fit a smoke run. Scalar results (mass change, maximum speed) are compared as
FP64 numbers computed from the FP32 candidate state.

### Excluded candidates

These existing checks were measured on the CPU proxy first (Linux, torch 2.8.0+cpu,
`f29fe01`). Against a CPU FP64 reference, CPU FP32 itself misses their criteria, so
they cannot separate device error from storage precision. Their criteria compare
FP32 runs with each other and remain in their own harnesses.

- `tgv3d-bgk` and `tgv3d-smagorinsky`: iteration-50 pressure exceeds the limit by
  3.8e-5 and 1.6e-4.
- PorousMedium 50-step fields: max |u| difference 8.0e-4 against a limit of about
  3.5e-4; the 99.9th percentile is 2.5e-5. The KBC path is covered by
  `kbc-near-equilibrium`.
- Sphere masks at dx 1/3: multiples of 1/3 round differently in FP32 and FP64, so
  24 on-surface cells classify differently.

## Outcomes

Each case is `pass`, `fail` or `unsupported-guarded`.

- `unsupported-guarded` requires a policy entry naming the device, the exception
  type and a message pattern, and the runtime guard must actually raise it. A device
  that is declared unsupported but runs is a failure. An undeclared exception is a
  failure. The current policy declares no unsupported devices, because no runtime
  guard refuses any of these cases.
- The run passes only when no case fails, the source snapshot is unchanged and every
  loaded `hawa`/`lettuce` module comes from this checkout.
  Guarded cases are counted separately, never as passes.

Before #11 (PR #63), MPS ran the plain FP32 KBC collision. A CPU emulation of that
path gave 9/9 and 576/576 mismatched populations in `kbc-near-equilibrium`, so the
case detects it. Since #63, MPS uses compensated FP32 hi/lo intermediates. A CPU
emulation of that path gives 0 mismatches, but only an MPS run is MPS evidence.

## Manifest

Every run writes `manifest.json` in a new output directory and refuses to reuse one.
It records:

- the commit, dirty flag and `git status`, and a SHA-256 over every tracked or
  nonignored file, taken before and after the run with the provenance helper
  from `scripts/verification_evidence.py`;
- the file of every loaded `hawa` and `lettuce` module, before the first case and
  after the last. Each must be a file under this checkout's `src/hawa` or
  `vendor/lettuce/lettuce`. A module from an installed copy or another checkout
  fails the run (`module_errors`), and a mismatch before the cases skips them, so a
  pass always names the source that was tested;
- the device, backend probe, OS, Python, PyTorch, NumPy and thread settings. On CUDA
  it also records the GPU, capability, CUDA runtime and driver. On MPS it records the
  Mac model, chip and macOS version;
- the reference and candidate dtypes, seeds (torch and NumPy 0, reset before every
  run), the policy SHA-256 and the operator's overlapping-jobs statement;
- for each case: reference and candidate wall time, status, any error or guard
  message, and each array's dtype, shape, violations or mismatches and maximum error.

Raw arrays are saved as `cases/<case>/reference.npz` and `candidate.npz`.

## Commands

Use a fresh checkout of the exact commit with the production Python 3.9
environment. Keep the output under the ignored `results/` directory, so that the
run does not change the source snapshot.

Linux or macOS CPU (the same command CI runs):

```sh
.venv/bin/python scripts/device_smoke.py --device cpu --output results/device-smoke-cpu-NEW --overlapping-jobs none
```

Windows CUDA, after installing the CUDA wheel as described in
[the Windows CUDA guide](windows-cuda.md):

```powershell
.venv\Scripts\python.exe scripts/device_smoke.py --device cuda --output results/device-smoke-cuda-NEW --overlapping-jobs "none"
```

Apple MPS (do not set `PYTORCH_ENABLE_MPS_FALLBACK=1`; the script refuses it):

```sh
.venv/bin/python scripts/device_smoke.py --device mps --output results/device-smoke-mps-NEW --overlapping-jobs "none"
```

Replace `none` with a description of any other work running on the machine. The
exit code is 0 only when the manifest `result` is `pass`. Attach the whole output
directory to the round's device issue.

## Verification of the gate itself

`tests/test_device_smoke.py` checks the comparison classes at their boundaries,
guard handling, manifest fields, provenance, and reduced real runs of every builder
on the CPU. `scripts/device_smoke.py` has 100% line and branch coverage.

Targeted mutmut 2.4.5 covered only the lines this gate added, from
`git diff 8eec667` passed to `--use-patch-file`:

```sh
bash tools/mutation/run_device_smoke.sh results/device-smoke-mutation-NEW 8eec667
.venv/bin/python tools/mutation/check_results.py results/device-smoke-mutation-NEW --policy tools/mutation/device-smoke-policy.json
```

Of 453 mutants, 445 were killed. The remaining 8 are reviewed in
[the policy](../tools/mutation/device-smoke-policy.json): 3 equivalent placeholder or
role arguments, 1 timeout constant, 1 already-sorted key order and 3 console flush
flags. This is a PR-scoped record, not whole-module or CI mutation coverage. CPU
runs are not CUDA or MPS evidence.
