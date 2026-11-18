#!/usr/bin/env bash
# Issue #68 PR study: the lines this PR changes in src/hawa/motion.py, against the
# motion, payload-schema and motion-rejection tests. mutmut 3 does not mutate
# class bodies or decorated methods, so the pydantic field constraints and model
# validators are covered by one rejecting behaviour test each, not by this study.
source "$(dirname "$0")/lib.sh"
# PR base: origin/main when the PR branched (#67 merged).
base=cc407cc9b4a353fc259f205f9dcb9bee766e76a9
mutate=(src/hawa/motion.py)
tests=(tests/conftest.py tests/test_motion.py tests/test_payload_schemas.py tests/test_runtime_rejection_edges.py
  # test_runtime_rejection_edges imports fixtures from these at module level.
  tests/test_general_boundaries.py tests/test_neutral.py tests/test_boundary_data.py tests/test_walls.py
  tests/test_optimization.py)
reviewed=("${mutate[@]}" "${tests[@]}" docs/schemas/moving-body.schema.json docs/schemas/motion-evaluation.schema.json
  src/hawa/measurements.py src/hawa/stationary_loads.py src/hawa/sweeps.py
  docs/schemas/measurement-request.schema.json docs/schemas/measurement-sample.schema.json
  docs/schemas/measurement-probe.schema.json docs/schemas/sweep-candidate.schema.json
  docs/schemas/sweep-callback.schema.json docs/schemas/sweep-poll.schema.json
  tools/mutation/cpu_only.py)
# test_motion imports scripts/benchmark_motion.py; the snapshot test reads docs/schemas.
copy=(scripts/benchmark_motion.py docs/schemas tools/mutation/cpu_only.py)
import_roots=(tools/mutation)
export PYTEST_PLUGINS=cpu_only
test_args=(tests/test_motion.py tests/test_payload_schemas.py
  tests/test_runtime_rejection_edges.py::test_fixed_motion_and_unsupported_geometry
  tests/test_runtime_rejection_edges.py::test_motion_evaluation_rejects_invalid_requests_before_advancing
  -k 'not cuda and not mps')
changed_lines() {
  git cat-file -e "$base^{commit}" || { echo "Full history with $base is required" >&2; return 65; }
  git diff --no-prefix "$base" -- "${mutate[@]}"
}
run_study "$@"
