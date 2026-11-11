#!/usr/bin/env bash
# HAWA-004 PR study: mutate only the lines PR #66 changed in the shifted
# open-face operator, plus the reflection harness lines changed by its review
# fixes, with the focused tests that exercise them. Local study, not in CI.
# PR #66 also changed tools/mutation/check_results.py; #67 rewrote that file, so
# run_mutation_tooling.sh covers it now.
source "$(dirname "$0")/lib.sh"
# PR base: origin/main at the last merge into the PR #66 branch.
base=f29fe0184325b33b68014935f4f6d013d00071f3
# Review base for the harness: PR #66 head before the review fixes. The harness
# is new in that PR; only its review-fix lines are in scope.
harness_base=d0b54e271d6b57d8d7fa07e8f357b68265b273b5
mutate=(src/hawa/neutral_external.py scripts/verify_boundary_reflection.py)
tests=(tests/conftest.py tests/test_neutral.py tests/test_neutral_external.py tests/test_boundary_reflection.py)
reviewed=("${mutate[@]}" "${tests[@]}")
import_roots=(scripts)
# The CPU/MPS comparison is device qualification (#53); it cannot run on CPU-only hosts.
test_args=(tests/test_neutral_external.py tests/test_boundary_reflection.py
  --deselect tests/test_neutral_external.py::test_external_cpu_mps)
changed_lines() {
  local commit
  for commit in "$base" "$harness_base"; do
    git cat-file -e "$commit^{commit}" || { echo "Missing $commit: run git fetch origin refs/pull/66/head first" >&2; return 65; }
  done
  git diff --no-prefix "$base" -- src/hawa/neutral_external.py
  git diff --no-prefix "$harness_base" -- scripts/verify_boundary_reflection.py
}
run_study "$@"
