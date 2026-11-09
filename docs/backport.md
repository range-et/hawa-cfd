# Python 3.9 compatibility verification

The Mac results below are historical. See the [November 9 Windows CUDA record](verification-windows-cuda-2026-11-09.md) for current hardware tests, repeatable commands, exact exclusions and the unresolved PorousMedium CPU/CUDA parity failure.

The complete vendored Lettuce source tree is pinned to upstream commit `88a6559def2a49fd7f425fd05954ec1e3db2cdb6`. The separate reference environment runs unmodified upstream in Python 3.12. Production Hawa targets Python 3.9; Rhino users do not need the reference environment.

`scripts/audit_backport.py` checks the original source and test hashes: 16 changed source modules, 62 unchanged source modules, and all 61 original test files unchanged. Compatibility and upstream defect repairs are documented in `vendor/lettuce/PORTING.md`. Additional Hawa tests exercise the exposed flow/collision families, backend selection, and plugin service.

The last complete vendored upstream test run passed 419 tests with 884 skips. Skips include native/CUDA hardware configurations unavailable here and upstream exclusions. The current Hawa suite passes 77 with 29 skips. CPU FP32/FP64 core-case arrays match the unmodified oracle bitwise; MPS passes declared tolerances. Cavity is reported as a repaired upstream case rather than a comparison against a constructor that fails.

All 16 original executable example entrypoints complete the bounded CPU and MPS harness. The default limits are 50 simulation steps, or 250 for the intentional numerical-failure example. This verifies execution and bounded behavior, not the original full-duration convergence. The CPU/MPS PorousMedium trajectory has a localized strict pointwise difference after 50 FP32 KBC steps; geometry masks agree, and aggregate differences are small, but strict universal example parity is not established. The comparison script deliberately retains this failure rather than silently widening its tolerance.

The native Grasshopper gallery now contains eight editable definitions: seven verification cases plus a 3D block workflow. Reopening the actual `.gh` graphs and stepping each on MPS passed with valid field meshes. UI checks additionally completed 200 vortex iterations and 300 block-case iterations in Rhino's CPython 3.9.10 with PyTorch 2.8.0 and NumPy 2.0.2. See `docs/plugin.md` for installation, units and current scope, and `docs/captures` for computer-use screenshots.

Windows Rhino installation, full-duration example convergence, and complete Grasshopper wrappers for the remaining upstream examples remain open. NVIDIA CUDA headless execution is now measured in the linked record; universal example parity is not established. The current geometric workflow is a dense voxel LBM prototype and needs problem-specific CFD validation before engineering use.
