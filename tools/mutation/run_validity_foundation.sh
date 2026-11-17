#!/usr/bin/env bash
# Correctness package items 2, 5 and 6 (#80, #81, #82): mutate only the lines
# changed since the base in the boundary-node export (session and refined
# frames), the shared halfway sampling rule, the half-cell isosurface, the plane
# partition (single frame and composed), streamline tracing and the recording
# query dispatch, against the focused CPU tests. Pathlines were removed by owner
# decision, so src/hawa/recording.py is no longer mutated.
source "$(dirname "$0")/lib.sh"
# PR base: origin/main after #88.
base=56b0728da222d60c3928193c74c8ab72788dd014
mutate=(src/hawa/plugin.py src/hawa/fields.py src/hawa/field_collection.py src/hawa/refinement.py)
tests=(tests/conftest.py tests/test_fields.py tests/test_field_collection.py tests/test_plugin_service.py tests/test_recording.py tests/test_refinement.py tests/test_quality_provenance.py tests/test_mutation_cpu.py tests/test_refinement_preflight.py tests/test_csv_export.py tests/test_export.py tests/test_native_data.py)
copy=(tools/mutation/cpu_only.py tools/mutation/lib.sh)
import_roots=(tools/mutation)
reviewed=("${mutate[@]}" src/hawa/exports.py src/hawa/native_data.py src/hawa/jobs.py "${tests[@]}" tools/mutation/cpu_only.py tools/mutation/lib.sh)
test_args=(-p cpu_only tests/test_fields.py tests/test_field_collection.py tests/test_plugin_service.py tests/test_recording.py tests/test_refinement.py tests/test_quality_provenance.py tests/test_mutation_cpu.py tests/test_refinement_preflight.py tests/test_csv_export.py tests/test_export.py tests/test_native_data.py -k 'not cuda and not mps')
changed_lines() {
  git cat-file -e "$base^{commit}" || { echo "Missing $base: run git fetch origin first" >&2; return 65; }
  git diff --no-prefix "$base" -- "${mutate[@]}"
}
run_study "$@"
