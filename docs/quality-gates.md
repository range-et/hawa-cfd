# Development and release verification gates

These gates are the review contract for Hawa changes. Use them with the
[architecture review](architecture-v0.5.md), [example verification matrix](../examples/grasshopper/VERIFICATION.md)
and [Rhino MCP operating guide](agents/rhino-mcp.md). A named review role is a
checklist and an evidence responsibility, not proof that a specialist approved
anything. Record who actually reviewed the work. One person or agent may perform
several roles in separate passes; do not fabricate independent reviewers.

## Gate decisions

Record each applicable gate as **PASS**, **FAIL**, **BLOCKED**, or **NOT APPLICABLE**.
PASS requires evidence for the exact change/build and declared scope. BLOCKED
means a required test could not run, such as CUDA without hardware. NOT APPLICABLE
requires a reason based on the diff. A skipped test is unverified, not a pass.
A prior result is historical evidence until its relevance to the current build
has been assessed. Review all gates for every change; scale execution to impact.

A failure blocks the claim it contradicts. For example, PorousMedium parity blocks
“all devices agree”; it does not erase a separately passing UI test. A bounded
prototype may ship with explicit exclusions and tracked limitations. Do not call
that an unrestricted release pass. Record the disposition, owner and next check
for every exception. Never silently waive data loss, stale-result attribution,
uncontrolled workers, broken archives, or an advertised numerical claim.

## G0 — Research and evidence reviewer

Before implementation, state the user question, supported physics, reference
behavior and exclusions. Use primary sources for numerical methods and host APIs.
Record source/version/date, what was observed versus inferred, licence and
attribution obligations, alternatives and acceptance criteria. Recheck changing
APIs when implementing them. The [0.5 interface comparison](architecture-v0.5.md)
records KaroroCAM, Kangaroo and Karamba findings; it is not a speed ranking or an
audit of their private internals.

**Pass evidence:** a scoped decision with traceable references and criteria set
before measurement. No copied assumptions about threading, accuracy or API rights.
A new dependency requires a distribution/licence review; Hawa is GPL-3.0-only and
bundled upstream notices remain intact. Local airfoil/polar files require no web
scraping or database API. Research alone cannot pass an implementation gate.

## G1 — Software architect

Review the data model, ownership and transitions before reviewing appearance.
First check the product boundary: example geometry/recipes stay in ordinary GH
assemblies; a new node needs a reusable operation or a defined numerical service.
Do not use the component count as a progress metric. Check document/case identity, settings version, physics revision, run generation,
field capture provenance, binding leases, undo, persistence/schema migration and
capability rejection. Draw the command/result path for a new workflow. Review
host-thread boundaries, cancellation ownership, stale callbacks, cleanup retries,
resource budgets and extension points. Review old saved definitions as clients.

**Pass evidence:** explicit invariants, failure paths and migration decisions;
production state-contract tests; native ownership/lifecycle tests when adapters
change. Use `tests/dotnet/StateContracts`, `verify_state_hardening.cs`,
`verify_binding_callbacks.cs` and `verify_native_prototype.cs` as applicable.
Host doubles cannot verify actual GH scheduling or window lifetime.

## G2 — Software developer and reliability reviewer

The [function coverage gate](function-testing.md) inventories first-party Python
and plugin C# surfaces. Require a fresh complete run, current committed matrix,
coverage for every new function, and no lost coverage relative to the trusted
baseline. Existing unchanged gaps remain explicit debt; changed gaps require
tests. CI also requires 100% functions and executable lines in the declared
headless scope and runs the reviewed mutation inventories. Unmeasured host code
stays explicit; these checks supplement assertion review and numerical/host gates.

Review the diff for invalid inputs, missing/list data, non-finite values, partial
mutation, exception isolation, idempotence, thread safety, bounded allocations,
file handling and backward compatibility. Add a regression for each repaired
behavior at the cheapest level that can reproduce it. Include adverse ordering,
not only a successful run. Preserve Python 3.9 and the pinned dependencies.

**Pass evidence:** relevant focused tests, then the Hawa suite; applicable builds;
actual host checks for host behavior; reports that fail on missing output and do
not reuse an old success. Check cleanup after cancel, invalid input and document
close. Inspect skips/warnings and record their meaning. No blanket “all tests
passed” when only a subset ran.

Developer commands from the checkout (not requirements for installed users):

```sh
.venv/bin/python -m pytest tests -q
dotnet run --project tests/dotnet/StateContracts
```

The contract test host uses .NET 10; the plugin targets .NET 7. Build with
`scripts/build_plugin.py`. Never install over loaded assemblies. Numerical-engine
changes also need the separate upstream/backport checks under G3.

## G3 — Computational physicist / numerical reviewer

Separate three claims: **workflow demonstration**, **implementation verification**
(analytic/reference-code comparison), and **physical validation** (appropriate
experimental evidence). Approval applies to a stated regime and observable.
Inspect units, reference frames, pressure reference, force/torque/power signs,
Reynolds/Mach scaling, boundary placement, grid/domain/time sensitivity, stability,
conservation, settling and averaging. Compare equal physical time, not merely
iteration count. Define norms, tolerances and reference provenance before running.

**Pass evidence:** relevant numerical tests and benchmark reports with measured
errors, conservation and sensitivity, plus reference/backport comparisons when
engine behavior changes. Existing tools include `audit_backport.py`,
`run_upstream_tests.py` (separate reference and backport runs), `compare_engines.py`,
`run_examples.py`, `compare_examples.py`, and the wall/refinement/motion benchmark
scripts. Inspect arguments and environment requirements before execution. Keep
reference imports isolated from the fork. Distinguish the 16 upstream entrypoints
from the editable GH gallery; a bounded 50-step run is not a full-duration study.

Never widen tolerances to hide disagreement. Keep PorousMedium CPU/MPS parity
explicitly unresolved. Synthetic polar data tests parsing, not aerodynamics.
A submerged hull does not model waves/buoyancy. Prescribed motion is not fluid/body
coupling. A coarse RC example does not resolve its boundary layer. A good render
and a completed run cannot establish convergence or an optimum.

## G4 — UI/UX reviewer and example operator

For code PRs, follow the [local Rhino acceptance review](local-rhino-acceptance.md):
open all supported examples, run/render them, and inspect numbers and images.
The creator records evidence and omissions; the maintainer owns the merge
decision. This important soft gate does not require a self-hosted CI runner and
does not count as measured host code coverage. Preserve modified legacy 09.

Run the annotated definition as a new user would, then repeat through supported
Rhino MCP operations. Do not rely on hidden state or knowledge of the generator.
Inspect the actual canvas and viewport. Verify the Hawa tab, icons, labels, units,
workflow groups, defaults, editable controls, read-only ownership, domain wireframe,
legend and display field. Check preparation, progress, pause acknowledgement,
completion, stale results, errors, recovery and save/reopen behavior. Distinguish
solver progress from the field's capture time. Test viewport/unit changes and
panel/document switching where relevant.

**Pass evidence:** example ID and exact controls, observed states/output geometry,
public-operation steps and screenshots of important UI states. Read errors and
check non-null valid outputs, not only component colour or `VolatileDataCount`.
A numerical reviewer must separately approve any numerical claim.

For tutorial/video changes, inspect the rendered beginning, middle, every title
and the final frames; check for empty slides, clipped labels, unwanted overlays,
wrong field/units and stale footage. Keep narration direct and technical claims
within the recorded evidence. A successful video encode is not visual QA.

## G5 — Release integrator

Combine gate records; do not average away failures. Match the tested source,
installed assemblies and packaged binaries. Verify ZIP integrity, bundled source,
licences, supported examples, annotation/assets and relative links. Exclude user
legacy example 09 and temporary test files. Recheck the unbound native template;
saving after automatic GH activation can accidentally persist a test case ID.
Do not overwrite a frozen release. State the actual OS/Rhino/Python/PyTorch/device
matrix, clean-install status, skipped cases and known issues.

**Pass evidence:** a release record linking the gate decisions, tests, coverage
matrix, package hashes and unresolved issues. Windows docking, CUDA and clean
Rhino dependency installation require actual environments. MPS is PyTorch's Apple
backend; it is not MLX. `auto` selection is not a performance benchmark.

## Recurring failure patterns to check explicitly

| Gotcha / symptom | Required prevention or regression |
| --- | --- |
| Rhino appears frozen during optimization | Never wait/sleep on the UI thread. Poll jobs across turns/timer callbacks. Pass only completed, candidate-tagged fitness to search. Test pause/cancel during preparation and execution. Galapagos is not made asynchronous by an async upstream node. |
| A worker completes but GH still says running | GH ScheduleSolution can be erased by another solution. Retain job/generation polls in an owned UI timer; test idle completion, intervening solutions, pause and document disposal. |
| Slice has a blank band around a body | Clip partially intersecting triangles at the represented boundary; do not discard their fluid portion. Test retained area, nested priority, disjoint gaps and raw validity separately from reconstructed colours. |
| Example produces duplicate legends or geometry | SetPersistentData can append to a default. Clear persistent data before replacing defaults, and inspect output branch/count as well as the screenshot. |
| “Expired during a solution” GH breakpoint | Never set sliders in `SolveInstance`. Pull in a validated pre-solution callback. Test an intervening solution before the pull. |
| Old sliders overwrite a panel edit | Version all settings, remember pulls while locked, reacquire data after scheduled writes; test lock/edit/unlock. |
| Old/duplicate component changes another case | Check document, case ID, owner, lease and callback generation before writes. Test restore to a new ID and duplicate components. Preflight every slider before applying any. |
| View exception stops a healthy run | Isolate observers and field-query faults. Retain last good field; retry views explicitly/boundedly. Test malformed metadata before publication. |
| Old field is labelled as current | Capture fields and time under the same lock; include revision/generation/session/field/step/time. Withhold stale GH output; label retained native fields. |
| Invalid/disconnected/list input leaves work running | Release owned work and binding on input failure; test NaN, empty input and multiple items. Verify worker exit, not just null handles. |
| Close loses resource ownership | Retain failed cleanup requests; make close idempotent. Test close during callbacks/transport and verify jobs, sessions and workers after teardown. |
| Undo or restore revives an obsolete case | End undo records in `finally`; tie undo to case identity; restore once into idle. Test normal Rhino UI Undo/Redo, not timer-driven document Undo calls. |
| Unit changes distort cached output | Store physical spacing and convert at view time; cache by units/result identity. Test metres↔millimetres. The generated block preserves physics; referenced Rhino geometry invalidates conservatively because unscaled unit changes can alter its physical size. |
| Saved Run is on but no steps advance | The reopen guard intentionally stays idle. Set Run off before the first valid solution, then on after preparation. Harnesses must initialize copied toggles, not assume saved defaults. |
| Parity reports pass with absent example outputs | Require the complete declared inventory on both devices before comparing. An empty selection or partial run is an error. |
| Native verification changes a distributable 3dm | Open a uniquely named copy in the evidence directory; compare every template hash before and after the host run. Keep live test documents away from source paths. |
| Empty native test document is rejected after deleting fixtures | Rhino object-table counts can include deleted entries. Enumerate live objects explicitly; verify repeated harness runs. |
| Native MCP target and first GH binding use different documents | Verify the actual active Rhino document before opening an unbound Linked Case. A slot target alone does not activate the document. |
| A report shows a previous run's success | Give each run its own directory/ID; reset terminal status before start; fail on absent cases/files and check the declared inventory. |
| Windows has an NVIDIA GPU but all CUDA tests skip | Verify the installed PyTorch build and execute a CUDA operation before collection; use `--require-cuda`. The plain pinned PyPI wheel was CPU-only in the Windows check. See `windows-cuda.md`. |
| Windows audit/example harness fails before numerical checks | Normalize manifest path separators and Git CRLF conversion only; retain content checks. Resolve worker output paths before changing directories. Require all 16 example reports. |
| CUDA changes a moving sphere's solid mask at surface cells | Check CPU/CUDA mask equality before comparing loads. The radius-1, dx=1/3 regression in `test_motion.py` covers four formerly differing cells. Use ordered geometry reductions and rationalized radial distance consistently for classification and wall links; do not add a mask-only epsilon. |
| Near-equilibrium KBC amplifies FP32 rounding into CPU/CUDA load differences | Keep the local collision precision/conservation regressions in `test_kbc_precision.py` and the original bounded PorousMedium field comparison. CPU/CUDA use FP64 collision intermediates with FP32 storage and the storage-precision degeneracy guard. Report the performance/memory cost; CPU/MPS parity remains unresolved. |
| Interpolated walls still look stepped | Distinguish the grid mask from solver wall positions. Clip supported slice displays at wall links; label reconstructed boundary colours and preserve raw sample validity. Test diagonal masks and endpoint intersections. |
| Smooth CAD body becomes a stepped or misplaced wall | Separate surface tessellation from lattice resolution. Use cell/body-scaled Brep meshing and test fractional link positions, including tangential and seam crossings. A mesh-distance tolerance alone does not bound link-position error. |
| Connected geometry becomes empty while an upstream task runs | Withhold geometry/case output and cancel old preparation; do not substitute an empty obstacle set. Check valid non-null output, not GH data counts (null placeholders count). |
| Playback accepts corrupt/mismatched data | Validate shape, finite values, time, manifest identity, path boundaries and expanded archive size before use. Test missing frames and interrupted recordings. |
| Preview or mesh uses different motion time | Feed views, body pose and loads from the same field snapshot. Compare complete cycles after settling. |
| Updating examples breaks saved graphs | Preserve object IDs, wires and parameter archives. Run annotation connection checks and reopen saved definitions. Use copies for test variations. |
| Finite completed flow is treated as usable wind data | Keep job and quality status separate. Test local Mach exceedance, sticky rejection across checkpoints, source transfer eligibility and time-coverage rejection. |
| “Rhino crashed” actually means missing MCP slot | Readopt with `list_slots` and inspect app/process state first. Save and Quit normally for assembly updates; never kill Rhino. |
| “Saved file” is in the wrong folder | Use explicit save APIs/paths, verify the resulting file. macOS Save As can turn slash-containing names into colon-separated filenames. Keep temporary files out of example/package folders. |
| Empty video slides or misleading screenshots | Inspect final rendered artifacts and captured UI, including final frames. Keep screenshot provenance with the run. |

Historical `scripts/verify_grasshopper_examples.cs` contains blocking polling and
an obsolete runtime lookup. Do not run it as the current verification harness.
Use the scoped nonblocking scripts listed in the example matrix, read each first,
and adapt hardcoded paths in an isolated test session. Script existence does not
prove its coverage or compatibility with a newer build.

## Scope, sequencing and records

For a change: G0 defines claims → G1 defines contracts → G2/G3 implement and check
behavior → G4 reproduces the user workflow → G5 checks distribution and evidence.
Findings can send work back to an earlier gate. A UI-only edit still needs G3 to
confirm that units/labels/legends have not changed the scientific interpretation;
it need not rerun unrelated expensive numerical benchmarks.

Copy [the review record](review-record-template.md) for each change/release. Keep
large logs under `results/<version>/<run-id>/`; commit a concise report with
reproduction steps, claims, exact configuration, gate decisions and linked or
packaged evidence. Assign a maintainer/reviewer explicitly; an unassigned required
gate remains BLOCKED. Add every newly discovered bug to this table, a regression
and a reproducible example variation where the integration matters.

Boundary foundation regressions: a full-node NEE writer must not erase curved-wall
corrections; intersecting slip planes must enforce every normal and shear symmetry;
open incoming data must satisfy the same edge constraints as prescribed velocity.
Keep legacy SGS parity separate from corrected physical closure verification.
The installer must receive the Libraries directory, not Libraries/Hawa; nested
bundles cause duplicate assembly prompts. The build script now rejects that path.

Shifted-population gotchas: checkpoints must declare storage (f versus g=f-w);
density checks must include the reference density. Halfway walls are outside the
first/last sample planes; nodal flux at those planes is not wall leakage. Report
actual population exchange and preserve physical-model qualification separately
from finite/low-Mach status. Neutral precursor transfer remains blocked.

## G6 — Compatibility matrix and example coverage

This is a required gate for new nodes, solver/boundary combinations, field formats,
shared-state changes and release candidates. Its executable inventory is
[tests/matrix](../tests/matrix/cases.py); the current scope and reproduction commands
are in [the compatibility guide](compatibility-matrix.md).

Enumerate the complete product of the **declared finite dimensions**. Maintain an
independent acceptance rule, successful runtime checks, deliberate invalid cases,
and named regression/lifecycle checks. Missing rows, duplicate IDs, stale sources,
changed example archives, unannotated graphs and public nodes without a sample
must fail. Source changes during a run invalidate its evidence. Unavailable
hardware is BLOCKED. A rejection is a passing contract check only when rejection
was the expected result; it is never a successful simulation.

A new public component or enum option must update this inventory and its fixtures.
A changed contract requires reviewing the independent oracle, its tests and the
example instructions together. Do not derive expected support from the same
production validator being tested. Run longer numerical/reference gates separately.
Four finite steps do not demonstrate convergence, conservation or accuracy.

Human examples are a covering library of annotated workflows. The machine matrix
expands variations without producing tens of thousands of nearly identical GH
files. Report node coverage, observed wire coverage, contract coverage and live
host coverage separately. Arbitrary Grasshopper graph sizes, continuous geometry,
parameter values and event orderings are unbounded; never call that whole space
exhaustively tested. Explicitly declare which finite product is exhaustive and
which stress/reference cases remain outside it.
