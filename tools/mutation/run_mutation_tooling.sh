#!/usr/bin/env bash
# Issue #67 PR study: the lines this PR changes in the mutation launcher and the
# policy checker, against their unit tests. The real-mutmut integration test
# starts its own mutmut and the committed-policy test needs the whole checkout,
# so both stay out of this study; the full suite runs them.
source "$(dirname "$0")/lib.sh"
# PR base: origin/main when the PR branched.
base=5f2c89902d29090fb7da61d5e7ba4b2fe3292e0b
mutate=(tools/mutation/check_results.py tools/mutation/mutmut3.py)
tests=(tests/test_mutation_policy.py)
reviewed=("${mutate[@]}" tests/test_mutation_policy.py)
import_roots=(tools/mutation)
test_args=(tests/test_mutation_policy.py
  --deselect tests/test_mutation_policy.py::test_real_mutmut_never_mutates_a_line_outside_the_patch
  -k 'not test_committed_policies_are_complete_and_reviewed')
changed_lines() { git diff --no-prefix "$base" -- "${mutate[@]}"; }
run_study "$@"
