#!/usr/bin/env bash
# PR #128 added handoff and control runner lines, including review repairs.
# Pydantic decorated validators/class fields are not mutated by mutmut 3;
# rejecting schema tests cover them separately.
source "$(dirname "$0")/lib.sh"
base=0b81daee8b5c00838c1af95b54066b2b5da96079
mutate=(src/hawa/openfoam.py scripts/compare_openfoam_controls.py)
tests=(tests/conftest.py tests/test_openfoam.py tests/test_openfoam_contracts.py)
reviewed=("${mutate[@]}" "${tests[@]}" tools/mutation/cpu_only.py tests/fixtures/openfoam/channel_poiseuille_ny10.json tests/fixtures/openfoam/cavity_re10_n32.json)
copy=(tools/mutation/cpu_only.py tests/fixtures/openfoam)
import_roots=(scripts tools/mutation)
export PYTEST_PLUGINS=cpu_only
test_args=(tests/test_openfoam.py tests/test_openfoam_contracts.py)
changed_lines() {
  git cat-file -e "$base^{commit}" || return 65
  git diff --no-prefix "$base" -- "${mutate[@]}"
}
run_study "$@"
