#!/usr/bin/env bash
# #73 PR study: mutate only the open-face mass-budget lines PR #73 changed in
# src/hawa/neutral_external.py (node-first storage sums), against the focused
# CPU tests. The MPS budget test is device qualification (#53) and needs MPS.
source "$(dirname "$0")/lib.sh"
# PR base: origin/main after #67 (PR #84) merged.
base=cc407cc9b4a353fc259f205f9dcb9bee766e76a9
mutate=(src/hawa/neutral_external.py)
tests=(tests/conftest.py tests/test_neutral.py tests/test_neutral_external.py)
reviewed=("${mutate[@]}" "${tests[@]}")
# The CPU/MPS comparison is device qualification (#53); it cannot run on CPU-only hosts.
test_args=(tests/test_neutral_external.py
  --deselect tests/test_neutral_external.py::test_external_cpu_mps)
changed_lines() {
  git cat-file -e "$base^{commit}" || { echo "Missing $base: run git fetch origin first" >&2; return 65; }
  git diff --no-prefix "$base" -- src/hawa/neutral_external.py
}
run_study "$@"
