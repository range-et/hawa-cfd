#!/usr/bin/env bash
# #39: control-plane state transitions, acknowledgement identity and cleanup.
source "$(dirname "$0")/lib.sh"
mutate=(scripts/host_acceptance.py)
source_paths=(scripts/host_acceptance.py)
copy=(scripts/host_acceptance.cs scripts/host_acceptance_audit.py)
tests=(tests/test_host_acceptance.py)
reviewed=("${mutate[@]}" "${copy[@]}" "${tests[@]}")
import_roots=(scripts)
test_args=(tests/test_host_acceptance.py)
run_study "$@"
