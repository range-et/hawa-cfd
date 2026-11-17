#!/usr/bin/env bash
# #40: per-body collector and private CPU worker ownership; no exports/host wiring.
source "$(dirname "$0")/lib.sh"
mutate=(src/hawa/stationary_loads.py src/hawa/sweep_executor.py)
tests=(tests/conftest.py tests/test_stationary_loads.py tests/test_sweep_executor.py tests/test_real_sweep_pipeline.py)
reviewed=("${mutate[@]}" "${tests[@]}" src/hawa/measurements.py src/hawa/sweeps.py
  scripts/wing_solver_recipe.py scripts/wing_measurement_recipe.py tools/mutation/cpu_only.py)
copy=(scripts/wing_solver_recipe.py scripts/wing_measurement_recipe.py tools/mutation/cpu_only.py)
import_roots=(. tools/mutation)
export PYTEST_PLUGINS=cpu_only
test_args=(tests/test_stationary_loads.py tests/test_sweep_executor.py tests/test_real_sweep_pipeline.py)
run_study "$@"
