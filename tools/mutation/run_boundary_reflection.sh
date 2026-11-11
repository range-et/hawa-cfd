#!/usr/bin/env bash
# HAWA-004 PR study: mutate only the lines this PR changes in the shifted
# open-face operator and the mutation policy checker, plus the reflection
# harness lines changed by the PR #66 review fixes, in a disposable copy, with
# the focused tests that exercise them. Local study (about 30 minutes on one CPU); not in CI.
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../.." && pwd)"
python_bin="$repo_dir/.venv/bin/python"
mutmut_bin="$repo_dir/.venv/bin/mutmut"
output_dir="${1:?Usage: bash tools/mutation/run_boundary_reflection.sh NEW_OUTPUT_DIRECTORY}"
# PR base: origin/main at the last merge into this branch.
base=f29fe0184325b33b68014935f4f6d013d00071f3
sources=(src/hawa/neutral_external.py tools/mutation/check_results.py)
# Review base for the harness: PR #66 head before the review fixes. The harness
# is new in this PR; only its review-fix lines are in scope.
harness_base=d0b54e271d6b57d8d7fa07e8f357b68265b273b5
harness=scripts/verify_boundary_reflection.py
tests=(tests/test_neutral_external.py tests/test_mutation_policy.py tests/test_neutral.py tests/test_boundary_reflection.py tests/conftest.py)
"$python_bin" -c 'import importlib.metadata as m; assert m.version("mutmut") == "2.4.5" and m.version("whatthepatch") == "1.0.7", "Install tools/mutation/requirements.txt"'
mkdir "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
cp -R "$repo_dir/src" "$output_dir/src"
find "$output_dir/src" -type d -name __pycache__ -prune -exec rm -rf {} +
mkdir -p "$output_dir/tests" "$output_dir/tools/mutation" "$output_dir/scripts"
cp "$repo_dir/tools/mutation/check_results.py" "$output_dir/tools/mutation/"
cp "$repo_dir/$harness" "$output_dir/scripts/"
for name in "${tests[@]}"; do cp "$repo_dir/$name" "$output_dir/tests/"; done
cd "$repo_dir"
shasum -a 256 "${sources[@]}" "$harness" "${tests[@]}" > "$output_dir/working-source-before.sha256"
git diff --no-prefix "$base" -- "${sources[@]}" > "$output_dir/changed-lines.patch"
git diff --no-prefix "$harness_base" -- "$harness" >> "$output_dir/changed-lines.patch"
cd "$output_dir"
printf '[pytest]\n' > pytest.ini
export PYTHONPATH="$output_dir/src:$repo_dir/vendor/lettuce"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
unset PYTEST_ADDOPTS
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
"$python_bin" -c 'import hawa.neutral_external as m; from pathlib import Path; assert Path(m.__file__).resolve() == Path("src/hawa/neutral_external.py").resolve(); print(m.__file__)' > imported-source.txt
# The CPU/MPS comparison is device qualification (#53); it cannot run on CPU-only hosts.
run_tests="tests/test_mutation_policy.py tests/test_neutral_external.py tests/test_boundary_reflection.py --deselect tests/test_neutral_external.py::test_external_cpu_mps"
"$python_bin" -m pytest $run_tests --collect-only -q > collected.txt 2>&1
"$python_bin" -m pytest $run_tests -q --junitxml=control.xml > control.log 2>&1
set +e
"$mutmut_bin" run --paths-to-mutate src/hawa/neutral_external.py,tools/mutation/check_results.py,$harness --use-patch-file changed-lines.patch --tests-dir tests/ --runner "\"$python_bin\" -m pytest $run_tests -q -x -p no:cacheprovider" --no-progress > mutation.log 2>&1
mutation_exit=$?
set -e
printf '%s\n' "$mutation_exit" > mutation-exit.txt
"$mutmut_bin" results > results.txt
"$mutmut_bin" junitxml > mutations.xml
"$mutmut_bin" show all > mutations.diff
cd "$repo_dir"
shasum -a 256 "${sources[@]}" "$harness" "${tests[@]}" > "$output_dir/working-source-after.sha256"
cmp "$output_dir/working-source-before.sha256" "$output_dir/working-source-after.sha256"
exit "$mutation_exit"
