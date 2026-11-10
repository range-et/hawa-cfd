#!/usr/bin/env bash
# Mutate only the admission modules in a disposable, cache-free source copy.
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../.." && pwd)"
python_bin="$repo_dir/.venv/bin/python"
mutmut_bin="$repo_dir/.venv/bin/mutmut"
output_dir="${1:?Usage: bash tools/mutation/run_runtime_admission.sh NEW_OUTPUT_DIRECTORY}"
"$python_bin" -c 'import importlib.metadata as m; assert m.version("mutmut") == "2.4.5", "Install tools/mutation/requirements.txt"'
mkdir "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
cp -R "$repo_dir/src" "$output_dir/src"
find "$output_dir/src" -type d -name __pycache__ -prune -exec rm -rf {} +
mkdir "$output_dir/tests"
cp "$repo_dir/tests/test_runtime_admission.py" "$output_dir/tests/"
cd "$repo_dir"
shasum -a 256 src/hawa/backends.py src/hawa/cases.py src/hawa/boundary_contracts.py tests/test_runtime_admission.py > "$output_dir/working-source-before.sha256"
cd "$output_dir"
printf '[pytest]\n' > pytest.ini
export PYTHONPATH="$output_dir/src:$repo_dir/vendor/lettuce"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
unset PYTEST_ADDOPTS
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
"$python_bin" -c 'from hawa import backends,cases,boundary_contracts; from pathlib import Path; modules=(backends,cases,boundary_contracts); assert all(Path(m.__file__).resolve().is_relative_to(Path("src/hawa").resolve()) for m in modules); print("\n".join(m.__file__ for m in modules))' > imported-source.txt
"$python_bin" -m pytest tests/test_runtime_admission.py --collect-only -q > collected.txt 2>&1
"$python_bin" -m pytest tests/test_runtime_admission.py -q --junitxml=control.xml > control.log 2>&1
set +e
"$mutmut_bin" run --paths-to-mutate src/hawa/backends.py,src/hawa/cases.py,src/hawa/boundary_contracts.py --tests-dir tests/ --runner "\"$python_bin\" -m pytest tests/test_runtime_admission.py -q -x" --no-progress > mutation.log 2>&1
mutation_exit=$?
set -e
printf '%s\n' "$mutation_exit" > mutation-exit.txt
"$mutmut_bin" results > results.txt
"$mutmut_bin" junitxml > mutations.xml
"$mutmut_bin" show all > mutations.diff
cd "$repo_dir"
shasum -a 256 src/hawa/backends.py src/hawa/cases.py src/hawa/boundary_contracts.py tests/test_runtime_admission.py > "$output_dir/working-source-after.sha256"
cmp "$output_dir/working-source-before.sha256" "$output_dir/working-source-after.sha256"
exit "$mutation_exit"
