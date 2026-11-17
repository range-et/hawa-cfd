#!/usr/bin/env bash
# Issue #35: explicit CSV interchange and cooperative publication.
source "$(dirname "$0")/lib.sh"
base=21bd205
mutate=(src/hawa/exports.py src/hawa/plugin.py src/hawa/jobs.py)
tests=(tests/conftest.py tests/test_csv_export.py tests/test_export.py)
reviewed=("${mutate[@]}" "${tests[@]}")
test_args=(tests/test_csv_export.py tests/test_export.py)
changed_lines() { git diff --no-prefix "$base" -- "${mutate[@]}"; }
run_study "$@"
