# 0.5 legacy Grasshopper cleanup follow-up

November 8, 2026. Author/reviewer: Codex, separate architecture, reliability,
physics-scope and UX self-review passes. No independent specialist review.
This resolves the older-GH cleanup finding in [the full review](review-full-v0.5.md).
That report remains a historical record of the earlier build.

## Change and acceptance criteria

Solve, Evaluate, Record, Refined Solve, Motion Evaluate and the shared query base
previously discarded their handles after a failed bridge close. They now detach
local handles before transferring IDs to the shared process cleanup service.
The service deduplicates pending requests, prevents recursive bridge calls,
retains failed requests after document disposal, and retries fairly on Rhino
Idle. Retry batches are bounded to eight requests, with a two-second interval.
The idle subscription is removed when no requests remain. No numerical code,
new dependency, geometry recipe or public node was added.

Acceptance: inject close failures, dispose the owning GH document, retain the
pending IDs, restore the bridge, and reach zero pending requests, jobs, sessions
and workers without the native panel's polling timer. Also verify duplicate and
lost-acknowledgement closes, bounded/fair retry, and reentrant callbacks. A close
acknowledgement alone does not establish worker exit.

## Reproduction

Run `dotnet run --project tests/dotnet/StateContracts`,
`.venv/bin/python -m pytest tests -q`, and `scripts/build_plugin.py` with the
repository Python. Quit Rhino normally before installing changed assemblies.
The tested host is Apple arm64, macOS 27.0.1, Rhino 8.36.26296.17002, with the
embedded Python 3.9 runtime. This run used a dedicated Rhino session; no forced
quit or process kill was used.

Through Rhino MCP, run `scripts/verify_legacy_cleanup.cs` in an isolated session.
It opens saved examples 01, 10, 13, 15 and 20, starts their real jobs, injects
cleanup transport failures, closes each definition, and verifies automatic
recovery. Example 01 uses a 100000-step target so teardown interrupts a running
solver. A real query-job fixture attached to a Plane Field component exercises
the query base lifecycle; this fixture is not a numerical field test. Recording
uses a new output directory. The native polling timer is stopped during the
fault test and restored afterward. The bridge delegate is restored on success
or failure. The harness uses private reflection for maintainer fault injection;
it is not an end-user control API.

Evidence is under `results/v05/cleanup-20261108`; the final machine-readable
summary is [verification-cleanup-v0.5.json](verification-cleanup-v0.5.json).
The first recording test required expiring its changed path panel. The harness
was corrected and the entire fault test rerun successfully without intervention.

## Remaining boundaries

Cleanup retries persist within the running Rhino process. A permanently broken
bridge leaves work pending and logs failures in Rhino's command output. Cleanup
does not survive process termination. Acknowledged cancellation remains
cooperative. First runtime initialization and native Brep meshing retain their
previous responsiveness limits.

PorousMedium CPU/MPS parity remains unresolved. CUDA, Windows and clean-profile
dependency installation remain unverified. This lifecycle fix does not change
those release exclusions or establish numerical convergence. Existing upstream
numerical/parity results remain historical evidence because solver code did not
change; they were not rerun for this cleanup-only patch.

## Gate decisions

| Gate | Result | Scope and evidence |
| --- | --- | --- |
| G0 research | PASS | Existing Rhino Idle/embedded bridge contracts; no new numerical method, dependency or copied reference code. Acceptance criteria above. |
| G1 architecture | PASS | Detached owners transfer IDs before bridge entry; retained, idempotent, fair and reentrancy-safe cleanup. Six ownership paths exercised in Rhino with native polling disabled. |
| G2 software | PASS | 33 state contracts; 148 Python tests passed, 29 CUDA skips, four existing MRT warnings. Both plugin projects built with zero errors; existing platform-analyzer warnings remain. Live failure recovery and normal lifecycle regressions passed. |
| G3 physics | NOT APPLICABLE | No numerical implementation or numerical claim changed. The Python regression suite passed; historical PorousMedium parity failure is still open. |
| G4 workflow | PASS | Change-scoped automated live GH controls, valid output meshes, playback and lifecycle checks; native/GH sync and callback checks. No new visual design or video claim. |
| G5 integration | BLOCKED for unrestricted release | Local installed/tested/package verification recorded separately. Windows, CUDA and clean-profile installation remain unverified; no publication. |

The cleanup finding is closed for the tested macOS/Rhino build. This is a bounded
lifecycle verification, not an unrestricted platform or physics approval.

## Observed results

- Fault injection: all five saved workflows plus the query-base fixture passed;
  final run recovery took 3.51–4.48 seconds including three seconds of deliberate
  bridge failure. Every teardown reached zero jobs, sessions and workers.
- Normal gallery: 11 definitions passed; simulation examples used 25 steps,
  with valid field meshes. The airfoil example checked local data and closed wing
  geometry. These are smoke tests, not convergence studies.
- Full recording/refinement: examples 13, 15 and 16 passed, including final-frame
  playback where present; the wake run took 74.94 seconds.
- Hull search: five completed candidates, pause/resume/cancel/restart, input edit
  and document close passed. Motion search: two completed cycle candidates and
  the same control/cleanup sequence passed. Invalid solver input released all
  runtime resources.
- Shared state: all 13 CPU/MPS lifecycle/sync checks and three duplicate-owner /
  replacement callback checks passed. Final process audit: zero pending cleanup,
  zero jobs, zero sessions, zero Hawa workers and zero GH documents.
- Local package: ZIP integrity, installed/tested/bundled binary equality,
  corresponding source, 21 supported GH definitions, notices and root-guide
  links passed. Legacy 09 is excluded. The frozen 0.4 archive is unchanged.
  Binary hashes are in the verification JSON; the archive hash is in
  `dist/Hawa-0.5.0-rh8.zip.sha256` to avoid a self-referential bundle hash.
