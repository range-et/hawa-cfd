#!/usr/bin/env bash
# The whole of the runtime admission modules, against tests/test_runtime_admission.py.
source "$(dirname "$0")/lib.sh"
mutate=(src/hawa/backends.py src/hawa/cases.py src/hawa/boundary_contracts.py)
tests=(tests/test_runtime_admission.py)
reviewed=("${mutate[@]}" tests/test_runtime_admission.py)
test_args=(tests/test_runtime_admission.py)
run_study "$@"
