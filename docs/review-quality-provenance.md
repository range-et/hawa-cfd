# Sampled quality warning provenance (#98)

November 16, 2026. Author/reviewer: Codex issue98 agent, separate self-review
passes. Root coordinating agent additionally reviewed trigger history, checkpoint
trust boundaries and native UI changes; visual review participation is recorded below. Base: `1b4e6c7`. This increment explains
sticky numerical-envelope status; it does not change the solver, tolerances,
assessment cadence, transfer eligibility, or physical qualification.

## Contract and implementation

The report preserves the first sampled assessment that established its worst
severity. A warning-to-rejection escalation replaces that trigger. Later samples
may recover or raise the peak without erasing the trigger. The `trigger` stores
severity, iteration, physical time, and a list of offending quantities, actual
values and policy limits. Human reasons name Mach or density deviation in percent
and include the same step and time. Both Mach and density deviation expose
`peak_sampled_*` and the first iteration achieving that peak. These are sampled
extrema, not claims about unobserved steps between assessments.

Invalid populations/density/no-fluid assessments carry a JSON-safe boolean trigger;
nonfinite numeric values are not written into trigger provenance. Old checkpoint
records without the new fields remain readable: unknown trigger/peak iterations
stay null. New checkpoint fields are checked before population/state mutation.
The native panel displays the retained reasons; GH Solve and Quality already
expose the report JSON. Native text skips malformed legacy reason entries.

No new dependency, node, numerical method or archive rewrite is introduced.
The existing `hawa-low-mach-v1` policy and its strict > thresholds remain intact.

## Reproduced cause

[Machine record](verification-quality-provenance.json) contains each five-step
assessment on CPU and MPS. Reconstructed the case from
`scripts/create_grasshopper_examples.cs` example 08: 33×17×17, 0.5 m spacing,
block [4,6]×[3,5]×[0,4] with surface-inclusive solid nodes, speed 1 m/s,
viscosity 0.1 m²/s, density 1.225 kg/m³, Mach scaling 0.05, regularized collision,
X inlet/outlet, periodic Y, wall/slip Z. Advanced 300 steps, 4.330127 s physical
time, by `Session.advance(5)` and captured `session.quality` after each call.
This is a headless reconstruction, not a live GH archive acceptance.

| Device | Trigger | Final density deviation | Final Mach | Sampled peak Mach |
| --- | --- | --- | --- | --- |
| CPU FP32 | step 5: density deviation 5.196905% > 5% | 0.658202% | 0.07753038 | 0.08438580 |
| MPS FP32 | step 5: density deviation 5.196965% > 5% | 0.658154% | 0.07753030 | 0.08438585 |

These reproduce the contradictory final numbers in #98 and establish a startup
density transient as the cause for these runs. The report now keeps that evidence
after recovery. No timing/performance claim: other agents may run CPU work while
this agent holds the exclusive MPS test lease.

## Gate record

| Gate | Reviewer | Decision | Evidence / limitation |
| --- | --- | --- | --- |
| G0 | Codex self-review | PASS | Existing policy and issue reproduction define the reporting contract; no new method claim. |
| G1 | Codex self-review | PASS | Additive report data; legacy load tests; reject malformed new persisted fields before mutation; no ownership changes. |
| G2 | Codex issue98 and root | PASS for local automated scope | Combined source `02d51d9`: 1899 Python 3.9 / 1889 Python 3.12 tests pass; 121 C# contracts; strict headless/base checks and fresh reviewed mutation policies pass. |
| G3 | Codex self-review | PASS for reporting scope | CPU/MPS reproduction above; thresholds and dynamics unchanged. No physical validation claim. |
| G4 | Issue98 agent live MCP; root visual review | PASS for targeted issue scope | CPU GH08 and native warning after recovery; root inspected full reason wrapping and progress. Broad supported-example sweep not run. |
| G5 | Codex issue98 and root | Development package only | Final integrated build/ZIP checks pass; combined6ed1012 installed for targeted CPU host checks. Not released or clean-machine qualified. |
| G6 | Codex root | PASS on CPU/MPS; CUDA BLOCKED | Final integrated source: 102,459 rows, 100,010 passes, zero failures, 2,449 CUDA-unavailable rows. Exact matrix/archive and full-test inventories verified. |

## Verification and omissions

Final combined evidence is in the [integration review](review-issue-batch-98-83-39.md):
Python 3.9 has 1899 passes/87 skips, Python 3.12 has 1889 passes/97 skips,
121 state contracts pass and the committed matrix is refreshed. These are
combined-source results, not a relabeling of earlier branch failures. The earlier branch measured run had 1,856 passes, 87 skips and two stale
mutation-policy hash failures (atmospheric precision and validity foundation);
no matrix was generated from that failed run. The parent refreshed the committed function matrix from final combined measurements.

- Focused CPU provenance tests: 49 passed after mutation-driven additions.
- Scoped #98 mutation: 312 mutants, 309 assertion kills, three reviewed equivalents.
- Atmospheric precision rerun: unchanged 760 inventory, 716 kills and 44 reviewed
  survivors; existing unresolved #85 gaps retained. The static patch hunk for
  `dissipation_storage` was reanchored after the new reporting lines; its scope
  did not change. Two survivor diff hashes changed only with the line number
  and were re-reviewed.
- StateContracts: 109 passed; existing nullable warning in FieldTools.cs remains.
- Python 3.9 production and separate 3.12 tooling environments use `uv.lock`.
- G6 `results/g6-issue98`: full declared products completed, CPU/MPS available,
  CUDA blocked. Runner-level `verify_evidence` / `verify_examples` passed; the aggregate
  `check_compatibility_evidence.py` checker was not run. CPU mutation work
  overlapped; the coordinator also reported a
  briefly started then interrupted #83 test process. No timing claim.
- CUDA unavailable/unrun. A headless MPS result does not establish Rhino workflow.
- Tool limitation observed: `tools/function_coverage.py run --help` raises
  argparse `TypeError: must be real number, not dict`; the documented run command
  is used directly. This unrelated help-format defect is not repaired here.

## Targeted live acceptance

Installed combined candidate `6ed1012` (including production change `99e4197`),
Rhino 8.37.26307.15002, embedded torch 2.8.0. CPU only for these runs.
An owned in-memory copy of shipped example 08 completed 300 steps: trigger step 5,
density 5.196905%, current density 0.658202%, current Mach 0.07753038. No component
errors; Slice valid, 681 vertices / 1,144 faces. Public `EmbeddedRuntime.Call`
checkpoint save/load preserved the exact historical trigger. The copy was stopped
and disposed; the original archive was never saved. The canvas image at its
existing zoom was cropped, so this is not a full example-layout sign-off.

The native selected-body case used block [4,6]×[3,5]×[1,5] m, domain
[0,16]×[0,8]×[0,8] m, 0.5 m cells, and the same fluid/boundaries as above.
The first attempt correctly rejected a box entered without converting the blank
Rhino document's millimetres; replacing only the owned box with metre-correct
model coordinates resolved it. No document unit change. The accepted case
completed 300 steps with result_steps=300, outdated=false, no solver/view/geometry
error. Its actual trigger was density 5.219793% at step 5; current density
0.661170%, current Mach 0.08207298, matching the separate headless prediction.
No private runtime state was modified.

Raw host artifacts are in `results/issue98/host/`; the compact machine record
below pins the installed source and outcomes. Initial GH idle preparation briefly
used the shipped `auto` backend before the input was changed to CPU; possible
idle MPS initialization overlapped another agent's suite. Run itself was CPU.
No timing claim. Future copies must set CPU before the first solution.
Root inspected the visible native panel through a read-only desktop screenshot: full
COMPLETED 300/300 and warning reason, with time wrapping onto the next line,
no clipping or overlap, and full progress bar. The screenshot remains in the
conversation tool output, not a repository artifact. No viewport framing claim.
The owned case was cooperatively cancelled/closed and body deleted. Final checks:
zero live Rhino objects, no case, zero pending cleanup, zero GH poll work; two
blank GH documents preserved. The broader supported
example sweep remains outside this targeted check; no broad sweep pass is claimed.

## Mutation-host failure and repair

The first validity-foundation run was interrupted after the near-threshold
formatting review. Its log also contains four forked-worker segmentation faults
in `backends._probe`: mutations removing an explicit CPU argument reached the
`auto` MPS probe after fork. `-k 'not mps'` and hiding CUDA do not prevent this.
That run is invalid and supplies no kills/policy pass. It may have overlapped
the earlier G6 MPS run; no timing claim is made.

The validity runner now explicitly loads the mutation-only `cpu_only` pytest
plugin, which reports CUDA and MPS unavailable in that process. A regression
asserts default/auto select CPU and explicit accelerator requests fail before
probing. Production backend code and qualification runs do not load this plugin.
The shared runner exposes declared import roots to both controls and mutant
processes. Docker was considered, but the local daemon was unavailable.
The fresh guarded run `results/validity-foundation-issue98-final` completed with
2,526 mutants: 2,307 assertion kills, 219 reviewed survivors, zero errors,
timeouts or signals; all 154 CPU controls passed (24 device cases deselected).
All 219 survivor names/statuses/diff hashes exactly match prior reviewed entries;
one previous seam-splitting survivor was killed in this run. The five added
checkpoint validation-call mutants were all killed. Scope and source hashes now
include the new provenance controls and CPU guard; policy verification passes.
Two workers were retained throughout; final combined G6 overlapped CPU work.
No performance claim. The interrupted run supplies no acceptance evidence.
