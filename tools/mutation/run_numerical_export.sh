#!/usr/bin/env bash
# Issue #35 CSV interchange and export/native-data routing changed lines.
source "$(dirname "$0")/lib.sh"
base=0e76b95
mutate=(src/hawa/exports.py src/hawa/plugin.py src/hawa/jobs.py)
tests=(tests/conftest.py tests/test_csv_export.py tests/test_csv_tables.py tests/test_export.py tests/test_native_data.py tests/test_runtime_job_contracts.py tests/test_native_data_status.py)
copy=(tools/mutation/cpu_only.py)
import_roots=(tools/mutation)
reviewed=("${mutate[@]}" src/hawa/native_data.py "${tests[@]}" "${copy[@]}")
test_args=(-p cpu_only tests/test_csv_export.py tests/test_csv_tables.py tests/test_export.py tests/test_native_data.py tests/test_runtime_job_contracts.py tests/test_native_data_status.py)
changed_lines() { git diff --no-prefix "$base" -- "${mutate[@]}"; }
run_study "$@"
