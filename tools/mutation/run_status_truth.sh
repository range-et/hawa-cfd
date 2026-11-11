#!/usr/bin/env bash
# Correctness package item 4 (#74): mutate only the lines this PR changes in
# src/hawa/jobs.py (a job waiting for the device slot reports 'queued'),
# against the deterministic job-contract tests.
source "$(dirname "$0")/lib.sh"
# PR base: origin/main after #89.
base=6b0744abb4ef132936dac310dff023852b0eade6
mutate=(src/hawa/jobs.py)
tests=(tests/conftest.py tests/test_runtime_job_contracts.py)
reviewed=("${mutate[@]}" "${tests[@]}")
test_args=(tests/test_runtime_job_contracts.py -k 'not cuda and not mps')
changed_lines() {
  git cat-file -e "$base^{commit}" || { echo "Missing $base: run git fetch origin first" >&2; return 65; }
  git diff --no-prefix "$base" -- "${mutate[@]}"
}
run_study "$@"
