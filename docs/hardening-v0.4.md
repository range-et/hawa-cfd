# Hawa 0.4 local hardening review

Reviewed on 8 November 2026, on macOS Apple Silicon, Python 3.9, PyTorch 2.8 and Rhino 8. Changes are local to the experimental 0.4 branch. This review does not establish engineering accuracy or Windows/CUDA compatibility.

## Patches

- Closing a completed creation job now signals its owned solver to stop before removing the session. Previously, a headless caller could leave that worker running without a registry entry.
- Grasshopper components release their current job when input validation throws. Previously, an invalid input could leave the previous computation active.
- Recorded fields use the same shape, finite-value and positive-density checks as imported snapshots. Playback checks frame metadata against the manifest. Particle advection checks seed coordinates, frame dimensions, increasing finite times, positive spacing and recording-directory boundaries.
- Field archives have an expanded-size check before decompression. Recording manifests are limited to 2 MB and 1,000 frames. Pathlines and contours have output limits of 100,000 points and segments respectively; contours accept at most 100 levels.
- Checkpoint loading rejects negative or fractional iterations and nonpositive density before changing the numerical state. Loading also refreshes mass monitoring, timestamps and error state.
- Built-in examples validate resolution and their estimated allocation before constructing a solver. Zero sizes no longer silently select a default.
- The example runner removes stale reports before starting a worker. A failed rerun cannot reuse an earlier success. CPU/MPS comparison now reports every example and exits with a failure when any comparison fails.

## Review coverage

Reviewed solver advancement and reset/checkpoint paths; backend selection; background evaluation, query and recording jobs; Grasshopper ownership and scheduled callbacks; geometry cancellation and mesh ownership; field sampling and geometry extraction; offline airfoil and polar handling; wall corrections; fixed-grid refinement; and verification/package scripts.

The numerical models retain their existing scope: fixed-duration submerged-body objectives, linear attached-flow lifting-line analysis, and experimental fixed 2:1 refinement. This pass does not change the collision equations or relax comparison tolerances.

## Local verification

- Hawa: **127 passed, 29 skipped**, including 15 added regression cases.
- Vendored upstream suite: **419 passed, 884 skipped**. Skipped cases remain unverified.
- Reference/backport engine comparison: CPU FP32, CPU FP64 and MPS pass the existing field/checkpoint tolerances.
- All 16 upstream example entrypoints execute successfully on CPU and MPS using the bounded profile: up to 50 steps per simulation, with 250 for the intentional failure detector example. These are execution checks, not full-duration convergence studies.
- Native Grasshopper: examples 01–08, 11, 12 and 14 pass graph/geometry checks; flow cases advance 25 steps. Example 10 completes five search candidates and passes pause/resume/cancel/input-change/document-close checks. Example 13 records and loads its final frame; 15 completes 200 coarse and 400 fine steps; 16 completes 8,000 steps and loads its final frame with plane and flow displays.
- Search control timings: submit 46 ms, pause 31 ms, resume 42 ms, cancel 17 ms and close 117 ms on this machine.
- The user-edited legacy Galapagos example 09 opens with 36 objects. It was neither solved nor saved. Hawa Search is the supported asynchronous optimization path.
- The local package contains 15 supported definitions, excludes legacy example 09, and passes ZIP integrity and source-content checks.

Native evidence and the final invalid-input cleanup check are recorded in `hardening-v0.4.json`. Detailed run logs remain under `results/v04` and `results/examples`.

## Open numerical finding

**CPU/MPS example parity passes 15 of 16 entrypoints. PorousMedium fails the existing tolerance after 50 steps.** The CPU and MPS obstacle masks match. Initial populations match exactly; maximum population difference grows from about 1.49e-8 at step 1 to 7.71e-4 at step 50. The case uses KBC with relaxation time 0.5009765625, close to the lower stability limit. This is consistent with numerical sensitivity, but the underlying cause has not been conclusively resolved. The unmodified upstream CPU run also differs from the backported CPU run for this case (maximum population difference about 4.63e-4).

The comparison remains failing and its tolerance is unchanged. Treat this example as a numerical investigation case. It blocks a claim that all example results match across devices; it does not invalidate the separately passing engine comparison suite. CUDA requires hardware verification on a CUDA machine.
