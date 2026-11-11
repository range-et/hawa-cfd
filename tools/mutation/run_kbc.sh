#!/usr/bin/env bash
# HAWA-001 KBC mutation studies:
#   collision:  only the lines of vendored kbc_collision.py the PR changed
#               relative to its base, against tests/test_kbc_precision.py
#   diagnostic: the whole of scripts/diagnose_kbc_parity.py (new to main with
#               that PR), against tests/test_kbc_parity_diagnostic.py
# CUDA/MPS hardware cases are deselected by name for this CPU study; actual
# accelerator runs are separate device evidence, never mutation kills.
source "$(dirname "$0")/lib.sh"
# PR base: the integration commit the branch started from.
base=f9a3a139baea226e2211ff213321c218378716c7
study="${1:?Usage: bash tools/mutation/run_kbc.sh collision|diagnostic NEW_OUTPUT_DIRECTORY}"
# The diagnostic hashes and validates the vendored package beside its own checkout.
copy=(vendor/lettuce/examples/advanced_flows/PorousMedium.ipynb pyproject.toml uv.lock)
case "$study" in
  collision)
    mutate=(vendor/lettuce/lettuce/ext/_collision/kbc_collision.py)
    tests=(tests/conftest.py tests/test_kbc_precision.py)
    source_paths=(src vendor/lettuce/lettuce)
    changed_lines() {
      git cat-file -e "$base^{commit}" || { echo "Full history with $base is required" >&2; return 65; }
      git diff --no-prefix "$base" -- "${mutate[@]}"
    } ;;
  diagnostic)
    mutate=(scripts/diagnose_kbc_parity.py)
    tests=(tests/conftest.py tests/test_kbc_parity_diagnostic.py)
    copy+=(vendor/lettuce/lettuce)
    import_roots=(scripts) ;;
  *) echo "Unknown study: $study" >&2; exit 64 ;;
esac
reviewed=("${mutate[@]}" "${tests[1]}")
test_args=("${tests[1]}" -k 'not cuda and not mps')
run_study "${2:?Usage: bash tools/mutation/run_kbc.sh collision|diagnostic NEW_OUTPUT_DIRECTORY}"
