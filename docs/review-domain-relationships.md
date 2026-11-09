# HAWA-028 Python domain contracts / HAWA-052 allocation preflight

November 9, 2026. Author/reviewer: Codex domain agent, self-review. Base `abe7545`.
This is implementation verification of Python contracts, not physical validation,
host acceptance, or release qualification. Original code licence is unchanged.

## Policy and acceptance criteria

The reference contracts are the existing `RefinedStepper` checks and
[domain guide](parent-child-domains.md), not an inferred ban on intersections.

| Operation | Existing contract | Added assertions |
| --- | --- | --- |
| Independent Python Sessions | Each case allocates separate state; spatial intersection with another case is not a coupling operation. | Contained, disjoint, touching, duplicate and partial-overlap extents retain independent tensor storage; mutating one leaves the other unchanged. No time advancement is claimed. |
| Coupled refinement | One aligned 2:1 BGK fine patch, integer corners, at least four coarse intervals per axis and cubic-stencil clearance inside its parent; fine resolution exactly `2*(upper-lower)+1`. | Disjoint, touching, partially outside, coincident extent, insufficient halo, undersized, wrong-resolution and malformed-corner requests reject before Session/Simulation allocation. Parent/fine roles and offending indices are reported. Minimum size and both clearance limits run successfully. |
| Composed immutable views | Same-time frames; finest containing domain owns each sample, equal spacing follows input order, no fallback through fine solids; no numerical coupling. | Touching and partial overlap remain accepted; duplicate extents reverse owner with reversed input order; containment and disjoint-gap values/owners are checked at origin zero and translation 1,000,000. Existing rotated-vector and finer-solid assertions remain in the focused suite. |
| Offline transfer | Coverage, world mapping, time, source quality and identity are separate transfer contracts. | Inventory only; existing transfer tests and full-suite evidence apply. No transfer validation or atmospheric qualification is changed. |

HAWA-049's absolute origin tolerance remains `rtol=0, atol=1e-7` and its 30
placement tests remain unchanged. Aligned translated and rotated runtime controls
are retained, and relative rotation between grids still rejects. No blanket
overlap rejection, numerical tolerance change, new node or schema is introduced.

## Reproduced defect and repair

HAWA-052: valid individual case specifications with unsupported patch topology
reached parent Session allocation before the existing `RefinedStepper` rejection.
Eighteen pre-repair cases failed the new early-rejection/diagnostic assertions.
These include nine invalid cases at translations zero and 1,000,000; malformed
2D corners previously failed NumPy broadcasting instead of a domain diagnostic.
Evidence is retained locally in `results/issue-028/before.log` and `before.xml`.

A shared `_validate_patch_bounds` now applies the existing index/resolution
criteria before the first checkpoint, Session or fine Simulation. The direct
stepper calls the same validator so its defenses remain. Missing/scalar corner
inputs additionally produce a domain-specific ValueError. Valid cases keep the
same solver and exchange calculations. No fields/transfer production code changed.

This does **not** add pre-submit validation to the asynchronous Job constructor:
`Job.work` still starts and acquires its device slot before calling `run_refined`.
HAWA-028 remains open for C#/Rhino preflight, offending host-object identification,
job-creation timing and user workflow checks. Geometry-dependent interface-solid
checks still require the constructed masks; their placement is unchanged.

## Fresh evidence

Native focused CPU: **82 passed, six device cases deliberately deselected**.
Command: `.venv/bin/python -m pytest tests/test_refinement_preflight.py
 tests/test_domain_relationships.py tests/test_refinement.py
 tests/test_field_collection.py -k 'not mps and not cuda' -q`.
Native uses its own virtualenv/TMPDIR, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`.
Focused logs/JUnit: `results/issue-028/focused-final-corrected.*`.

Docker focused CPU: **82 passed, six device cases deselected** on the same final
fixtures (`results/docker/focused-final.*`). Image
`sha256:6b367745131c89cf349cd005532efe5ac708f871b1758105669406e468e18e93`,
Python 3.9.25 / torch 2.8.0+cpu / NumPy 2.0.2, Linux aarch64; one CPU/2 GiB,
network disabled, read-only root/source with dedicated writable results and tmp.

Scoped Docker G6 completed: **97,561 passed, zero failed, 4,898 blocked**
(MPS/CUDA unavailable), all **102,459** expected rows, source unchanged,
33.98 seconds; 54 public nodes, 31 examples, 191 observed edges. Raw evidence:
`results/docker/g6/{summary.json,rows.jsonl}`. This is not a GPU/release pass.
The combined full-suite evidence checker has not yet run.

The full native gate was deliberately interrupted for integration-base review
repairs; neither interrupted attempt is a pass. Final full function gate,
committed matrices, G6 revalidation against the updated integration base and
development build checks are pending. Publication is held until those checks.

| Gate | Reviewer | Current disposition |
| --- | --- | --- |
| G0 research | Codex, self-review | PASS for preserving the existing scoped topology contract; no new numerical method or dependency |
| G1 architecture | Codex, self-review | PASS for allocation ordering and independent/view ownership; async/host preflight remains open |
| G2 reliability | Codex, self-review | Focused CPU passes; full function gate and committed matrices pending |
| G3 numerical physics | Codex, self-review | Existing bounded refinement controls pass on CPU; no new convergence/conservation claim or engine changes |
| G4 host/UI | Unassigned host reviewer | BLOCKED: no Rhino/GH work in this sandbox |
| G5 release/integration | Codex, self-review | Pending development build; installed-host qualification excluded |
| G6 finite compatibility | Codex, self-review | Scoped Linux CPU matrix passes; final-base combined checker pending, MPS/CUDA blocked |
