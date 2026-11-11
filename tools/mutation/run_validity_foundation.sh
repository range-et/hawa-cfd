#!/usr/bin/env bash
# Correctness package items 2 and 5 (#80, #81): mutate only the lines changed
# since the base in the boundary-node export (session and refined frames), the
# shared halfway sampling rule, the half-cell isosurface and the plane partition
# (single frame and composed), against the focused CPU tests.
source "$(dirname "$0")/lib.sh"
# PR base: origin/main after #88.
base=56b0728da222d60c3928193c74c8ab72788dd014
mutate=(src/hawa/plugin.py src/hawa/fields.py src/hawa/field_collection.py src/hawa/refinement.py)
tests=(tests/conftest.py tests/test_fields.py tests/test_field_collection.py tests/test_plugin_service.py tests/test_recording.py tests/test_refinement.py)
reviewed=("${mutate[@]}" "${tests[@]}")
test_args=(tests/test_fields.py tests/test_field_collection.py tests/test_plugin_service.py tests/test_recording.py tests/test_refinement.py -k 'not cuda and not mps')
changed_lines() {
  git cat-file -e "$base^{commit}" || { echo "Missing $base: run git fetch origin first" >&2; return 65; }
  git diff --no-prefix "$base" -- "${mutate[@]}"
}
run_study "$@"
