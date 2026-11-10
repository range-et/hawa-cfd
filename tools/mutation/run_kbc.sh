#!/usr/bin/env bash
# HAWA-001 KBC mutation studies in a disposable, cache-free source copy:
#   collision:  only the lines of vendored kbc_collision.py this PR changes
#               relative to its base (patch mode), against tests/test_kbc_precision.py
#   diagnostic: the whole of scripts/diagnose_kbc_parity.py (new to main with
#               this PR), against tests/test_kbc_parity_diagnostic.py
# CUDA/MPS hardware cases are deselected by name for this CPU study; actual
# accelerator runs are separate device evidence, never mutation kills.
set -euo pipefail
selection='not cuda and not mps'
# PR base: the integration commit the branch started from. Its kbc_collision.py
# is identical to main's; the diagnostic script exists only from that base on.
base=f9a3a139baea226e2211ff213321c218378716c7
repo_dir="$(cd "$(dirname "$0")/../.." && pwd)"
python_bin="$repo_dir/.venv/bin/python"
mutmut_bin="$repo_dir/.venv/bin/mutmut"
study="${1:?Usage: bash tools/mutation/run_kbc.sh collision|diagnostic NEW_OUTPUT_DIRECTORY}"
output_dir="${2:?Usage: bash tools/mutation/run_kbc.sh collision|diagnostic NEW_OUTPUT_DIRECTORY}"
case "$study" in
  collision) target=vendor/lettuce/lettuce/ext/_collision/kbc_collision.py; tests=tests/test_kbc_precision.py
             scope=(--use-patch-file changed-lines.patch) ;;
  diagnostic) target=scripts/diagnose_kbc_parity.py; tests=tests/test_kbc_parity_diagnostic.py; scope=() ;;
  *) echo "Unknown study: $study" >&2; exit 64 ;;
esac
"$python_bin" -c 'import importlib.metadata as m; assert m.version("mutmut") == "2.4.5", "Install tools/mutation/requirements.txt"'
mkdir "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
# The diagnostic hashes and validates the vendored package beside its own checkout.
mkdir -p "$output_dir/vendor/lettuce/examples/advanced_flows" "$output_dir/scripts" "$output_dir/tests"
cp -R "$repo_dir/vendor/lettuce/lettuce" "$output_dir/vendor/lettuce/lettuce"
cp "$repo_dir/vendor/lettuce/examples/advanced_flows/PorousMedium.ipynb" "$output_dir/vendor/lettuce/examples/advanced_flows/"
cp "$repo_dir/pyproject.toml" "$repo_dir/uv.lock" "$output_dir/"
cp "$repo_dir/scripts/diagnose_kbc_parity.py" "$output_dir/scripts/"
cp "$repo_dir/tests/conftest.py" "$repo_dir/$tests" "$output_dir/tests/"
find "$output_dir/vendor" -type d -name __pycache__ -prune -exec rm -rf {} +
cd "$repo_dir"
shasum -a 256 "$target" "$tests" > "$output_dir/working-source-before.sha256"
git cat-file -e "$base^{commit}" || { echo "Full history with $base is required" >&2; exit 65; }
git diff --unified=0 "$base" -- "$target" > "$output_dir/changed-lines.patch"
cd "$output_dir"
printf '[pytest]\n' > pytest.ini
export PYTHONPATH="$output_dir/vendor/lettuce:$repo_dir/src"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
unset PYTEST_ADDOPTS
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
"$python_bin" -c 'import lettuce.ext._collision.kbc_collision as k; from pathlib import Path; assert Path(k.__file__).resolve().is_relative_to(Path("vendor/lettuce/lettuce").resolve()); print(k.__file__)' > imported-source.txt
"$python_bin" -m pytest "$tests" -k "$selection" --collect-only -q > collected.txt 2>&1
"$python_bin" -m pytest "$tests" -k "$selection" -q --junitxml=control.xml > control.log 2>&1
set +e
"$mutmut_bin" run --paths-to-mutate "$target" --tests-dir tests/ --runner "\"$python_bin\" -m pytest $tests -q -x -k '$selection'" --no-progress ${scope[@]+"${scope[@]}"} > mutation.log 2>&1
mutation_exit=$?
set -e
printf '%s\n' "$mutation_exit" > mutation-exit.txt
"$mutmut_bin" results > results.txt
"$mutmut_bin" junitxml > mutations.xml
"$mutmut_bin" show all > mutations.diff
cd "$repo_dir"
shasum -a 256 "$target" "$tests" > "$output_dir/working-source-after.sha256"
cmp "$output_dir/working-source-before.sha256" "$output_dir/working-source-after.sha256"
exit "$mutation_exit"
