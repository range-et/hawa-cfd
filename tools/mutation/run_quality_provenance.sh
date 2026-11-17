#!/usr/bin/env bash
# Issue #98: sampled sticky-warning provenance, not solver dynamics.
source "$(dirname "$0")/lib.sh"
base=1b4e6c759cb86a677be992c5e1c65def3006866a
mutate=(src/hawa/quality.py)
tests=(tests/conftest.py tests/test_quality_provenance.py)
reviewed=("${mutate[@]}" "${tests[@]}")
test_args=(tests/test_quality_provenance.py)
changed_lines() { git diff --no-prefix "$base" -- "${mutate[@]}"; }
run_study "$@"
