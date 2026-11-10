# Runtime Python test and mutation evidence

This study adds deterministic CPU tests of runtime contracts, error paths,
physical/numerical invariants, immutable data validation, transfer cleanup,
job cancellation and legacy boundary-series initialization. No production
source, coverage exclusion or comparison tolerance was changed.

## Line coverage

The 2026-11-09 runtime-focused run passed 221 cases on Python 3.9.25 and CPU.
The final integrated gate (`resume-review-gate/python.json`) measures **3,356/3,356
executable lines** across `src/hawa`, including the invalid-step rejection guard
and its no-mutation assertions. All 1,415 Python cases passed, with 82 explicit
skips. This fresh complete run supersedes the earlier focused unions; see the
[combined review](review-headless-quality.md) for scope and limitations.

An earlier union audit overstated the denominator as 3,391 by counting
`executed_lines | missing_lines`. Coverage.py's raw `executed_lines` includes
35 module/class docstring locations that are not executable statements in its
line-coverage denominator. Comparing those locations with `Coverage.analysis2`
confirmed 28 module and seven class docstrings, not source edits or coverage
exclusions. Use coverage.py's statement totals and missing statements for line
claims. Earlier non-plugin line totals derived by that union method are retired.
Line coverage is also not complete branch coverage.

New tests include a real one-voxel exterior pore which cannot satisfy independent
mass/momentum constraints; this verifies rejection of a singular boundary
projection without mocking the linear algebra. A legacy v2 transfer archive
with optional strain arrays removed exercises gradient reconstruction, preserves
mapped velocity/pressure and advances one finite CPU step. Fault injection is
limited to write/attachment failures and job-route/control boundaries.

CUDA/MPS execution, live Rhino/Grasshopper scheduling and numerical engineering
qualification are not established by these CPU-focused tests. One intentional
extreme relaxation input emits a NumPy overflow warning before its expected
ValueError; the test passes and no runtime behavior was changed.

## Mutation scope

`tools/mutation/run_runtime_admission.sh NEW_DIRECTORY` runs pinned mutmut 2.4.5
against `backends.py`, `cases.py` and `boundary_contracts.py`, using only
`tests/test_runtime_admission.py` in an isolated copied source tree. It records
independent collection, a passing unmutated control, exact imported source
paths, XML outcomes and diffs. Before/after working hashes must match; the raw
mutmut exit is preserved. This is a bounded three-module mutation study, not
whole-runtime mutation coverage or proof that every defect is detectable.

Exploratory mutation findings led to tests for all six face identities and
normal/profile axes, deep metadata ownership, threshold boundaries, pressure
backflow, neutral profile admission, exact published case collision metadata,
case Reynolds/Mach controls and backend routing/probing. The exploratory run
was not treated as final evidence because tests were strengthened during it.
The final isolated control contains 91 tests.

The final fresh run (`admission-mutations-final91`) completed **356 mutants:
320 killed, 36 survived**, zero skipped/error/timeout outcomes. All 91 control
tests passed; working source hashes were unchanged. Raw mutmut exit was 2,
which is preserved rather than presented as a clean raw score. The exact
survivor diff and source hashes are pinned in
[`runtime-admission-policy.json`](../tools/mutation/runtime-admission-policy.json).
The 36 survivors comprise 28 diagnostic-string decorations and 8 reviewed
algebra/probe equivalents; their individual reasons are recorded in that policy.
The probe equivalents preserve its fixed-array reduction and operation-family
contract, not a stronger elementwise device qualification it does not implement.

The final policy is intended for the shared mutation result validator; changes
to sources, tests, mutant inventory or survivor diffs require a fresh review.
The 320/356 raw score is 89.89%; reviewed survivors are not counted as killed.
Local environment: Python 3.9.25, PyTorch 2.8.0, NumPy 2.0.2, mutmut 2.4.5.
