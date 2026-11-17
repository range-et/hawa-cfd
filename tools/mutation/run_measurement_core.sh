#!/usr/bin/env bash
# #40: SI analysis and sweep state machine; CPU only, no host/export paths.
source "$(dirname "$0")/lib.sh"
mutate=(src/hawa/measurements.py src/hawa/sweeps.py)
tests=(tests/conftest.py tests/test_measurements.py tests/test_sweeps.py)
reviewed=("${mutate[@]}" "${tests[@]}" tests/fixtures/measurements/measurement-v1.json tools/mutation/cpu_only.py)
copy=(tests/fixtures/measurements tools/mutation/cpu_only.py)
import_roots=(tools/mutation)
export PYTEST_PLUGINS=cpu_only
test_args=(tests/test_measurements.py tests/test_sweeps.py)
run_study "$@"
