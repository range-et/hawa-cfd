#!/usr/bin/env bash
# Native data v1 archive validation, publication and paused-state restoration.
source "$(dirname "$0")/lib.sh"
mutate=(src/hawa/native_data.py)
tests=(tests/conftest.py tests/test_native_data.py tests/test_native_data_mutation.py)
copy=(tools/mutation/cpu_only.py)
import_roots=(tools/mutation)
reviewed=("${mutate[@]}" src/hawa/stationary_study.py src/hawa/mesh_voxel.py src/hawa/sweep_executor.py src/hawa/stationary_loads.py src/hawa/measurements.py src/hawa/sweeps.py src/hawa/plugin.py src/hawa/jobs.py src/hawa/exports.py "${tests[@]}" "${copy[@]}")
test_args=(-p cpu_only tests/test_native_data.py tests/test_native_data_mutation.py)
run_study "$@"
