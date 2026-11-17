# CPU validation follow-up — #40 / PR118

November 17, 2026. Reviewer/operator: Codex root. CPU/headless only. The user
requested CI follow-through and further headless validation, then explicitly
authorized coordination with the debugging/export chat.

## Coordination and CI

All six GitHub checks passed on `734969e`: measured functions, full Python 3.12,
syntax/Rhino-requirements check, CPU smoke, CLI mutations and runtime-admission
mutations. These existing mutation checks do not cover the new measurement code.
The other chat retained Rhino/export ownership. New numerical work waited until
its #35 Python 3.12 and MPS checks finished. Numerical sensitivity runs were serial; mutation studies used one child and
OMP/MKL=1 at reduced priority. Once the other chat was idle, the combined CPU
suite overlapped the worker mutation study (which spends substantial time in
bounded lifecycle waits); this overlap is not device-smoke evidence. No plugin was installed or replaced.

## Worker-exit ordering

A new deterministic regression keeps a worker alive after it has published a
completed result. `close` must return pending, retain its handle, refuse a new
candidate, and preserve the completed data. Only actual thread exit permits
release. This exercises the previously unforced terminal-but-alive cleanup branch.

## Numerical sensitivity: FAIL against the frozen screen

[Predeclared protocol](wing-cpu-sensitivity-protocol.md), committed at `3842a33`
before running; [complete evidence](verification-wing-cpu-sensitivity.json).
The +3° synthetic-viscosity wing was run on three grids, a larger domain, a later
measurement window and a longer averaging window. Grid comparisons used equal
physical source windows. All six actual CPU runs completed, retained accepted
quality and stationarity, and drained every owned handle/worker/session. Source
hashes stayed unchanged during the study; total solve time 216.69 s.

| Variant | Solid nodes | Mean CL | Mean CD | Stationarity drift |
| --- | ---: | ---: | ---: | ---: |
| Grid coarse |249|0.161072|1.310993|0.003088|
| Grid medium |558|0.157450|1.334101|0.002695|
| Grid fine |1070|0.181122|1.350977|0.002581|
| Larger domain |249|0.085401|1.203412|0.003969|
| Later window |249|0.141158|1.297008|0.000079|
| Longer averaging |249|0.158879|1.309035|0.004360|

The grid screen fails: medium→fine CL changes 0.023672 (>0.02), and the lift
changes do not shrink across refinement. Medium→fine CD changes 1.25% (<5%),
which does not repair the failed lift condition. The domain screen also fails:
CL changes 0.075670 and CD 8.21% against coarse (>0.02/5%). The later-window and
longer-averaging comparisons pass their declared screen; the later CL difference
is 0.019914, close to the 0.02 limit, and is not a convergence proof.

No tolerance, resource limit, grid or reference was changed after seeing results.
Stationarity alone demonstrably does not establish resolution/domain independence.
Stepped geometry and finite-domain effects are plausible contributors, not isolated
implementation defects established by this study. The existing #40/#15 physical
qualification gap remains open; these results cannot qualify wing performance.

## Mutation testing

The measurement/sweep analysis study completed with **1,108 mutants, 1,008
assertion kills and 100 reviewed survivors**, 163 passing controls and zero
errors/timeouts/unchecked mutants. Each exact survivor diff is pinned in
[the policy](../tools/mutation/measurement-core-policy.json). Survivors are
falsey/sentinel or endpoint/dtype equivalents, locally swallowed diagnostics,
and message-case/padding changes. Diagnostic spelling is not fully asserted.
Decorated Pydantic validators and the worker/collector/recipes are outside this
inventory. Stronger controls check nonzero side force, source time zero,
probe/candidate boundaries, full result provenance, retained cleanup, generations,
error causes and plot gaps. No production-code defect was inferred from a
surviving mutation alone.

The first core attempt lacked copied schemas and failed its controls; it is not
a pass. Intermediate studies exposed assertion gaps and were superseded by the
fresh final study. The first worker/collector study was intentionally interrupted
at 688/1,736 after identifying test-harness waits and is not accepted. The updated
harness releases gates in `finally` and detects an exited worker promptly; all
50 executor tests pass. The fresh worker/collector study remains exploratory:
its 92 controls pass, but surviving mutations include result-provenance and
admission-boundary assertion gaps. No worker mutation policy pass is claimed.
These gaps remain #40 reliability verification work, not established failures
of the unmutated implementation.

The fresh worker/collector run completed all **1,736 mutants: 1,277 assertion
kills and 459 survivors**, with no raw error/timeout/unchecked outcomes and an
unchanged source snapshot. It is **not an accepted mutation gate**: the remaining
diffs still need review and stronger controls. Owner: #40 integrator; next action:
cover retained result provenance, geometry/generation admission boundaries and
capture-quality/time checks, then rerun the study and pin each remaining diff.

## Final checks and disposition

Fresh standalone Python 3.9: **2,239 passed / 176 skipped**, 127 linked C#
contracts; strict headless/trusted-base gate passes with 1,086 covered functions,
299 unchanged host gaps and no failures. Executor coverage is 280/280 statements
and now 96/96 branches. The refreshed committed matrix passes its baseline check.
Ruff and whitespace checks pass. Dependency deprecation warnings remain visible.

A separate integration-only checkout combines #40 `bbba4e8` and #35 `6eb8a5c`
at executable/test source `40f9a14`. No production merge conflicts or export fixes
were needed. Combined Python 3.9: **2,517 passed / 176 skipped**; Python 3.12:
**2,507 passed / 186 skipped**; **146** linked C# contracts. Strict headless gate:
**1,161 covered functions**, 299 existing host gaps, no failures. Its own matrix
was refreshed at `366f79c`. Skips include intentionally disabled accelerator and
host/platform/tool cases; they are not passes. Neither branch was merged into
main or into the other chat's branch. [Machine summary](verification-cpu-sweep-validation.json).

The earlier frozen standalone CPU smoke remains relevant to unchanged numerical
production source; fresh exact-head CPU smoke and Python 3.12 also run in PR CI.
The combined CPU smoke and updated-head CI outcomes are recorded in the PR/issue
follow-up after completion.

G1 ownership evidence is strengthened. G2 remains bounded by the exact reviewed
mutation scope and automated checks below; it is not exhaustive concurrency proof.
G3 physical/numerical qualification remains blocked: the bounded grid/domain
screen failed, and no matched experimental drag reference is established. G4/G5
host, packaging and release work remain omitted under the user's scope. No public
node, archive or existing solver combination was changed. No Rhino or export
ownership handoff occurred; combined branch checks belong in a separate worktree.
