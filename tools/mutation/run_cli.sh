#!/usr/bin/env bash
# Run from any directory. The argument must name a new evidence directory.
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../.." && pwd)"
python_bin="$repo_dir/.venv/bin/python"
mutmut_bin="$repo_dir/.venv/bin/mutmut"
output_dir="${1:?Usage: bash tools/mutation/run_cli.sh NEW_OUTPUT_DIRECTORY}"
"$python_bin" -c 'import importlib.metadata as m; assert m.version("mutmut") == "2.4.5", "Install tools/mutation/requirements.txt"'
# Never reuse a cache or mutate working source. mkdir deliberately rejects reuse.
mkdir "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
cp -R "$repo_dir/src" "$output_dir/src"
find "$output_dir/src" -type d -name __pycache__ -prune -exec rm -rf {} +
mkdir "$output_dir/tests"
cp "$repo_dir/tests/test_cli.py" "$output_dir/tests/"
cd "$repo_dir"
shasum -a 256 src/hawa/cli.py tests/test_cli.py > "$output_dir/working-source-before.sha256"
cd "$output_dir"
export PYTHONPATH="$output_dir/src:$repo_dir/vendor/lettuce"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
unset PYTEST_ADDOPTS
"$python_bin" -c 'import hawa.cli; from pathlib import Path; assert Path(hawa.cli.__file__).resolve() == Path("src/hawa/cli.py").resolve(); print(hawa.cli.__file__)' > imported-source.txt
"$python_bin" -m pytest tests/test_cli.py --collect-only -q > collected.txt
"$python_bin" -m pytest tests/test_cli.py -q --junitxml=control.xml > control.log 2>&1
set +e
"$mutmut_bin" run --paths-to-mutate src/hawa/cli.py --tests-dir tests/ --runner "\"$python_bin\" -m pytest tests/test_cli.py -q -x" --no-progress > mutation.log 2>&1
mutation_exit=$?
set -e
printf '%s\n' "$mutation_exit" > mutation-exit.txt
"$mutmut_bin" results > results.txt
"$mutmut_bin" junitxml > mutations.xml
"$mutmut_bin" show all > mutations.diff
cd "$repo_dir"
shasum -a 256 src/hawa/cli.py tests/test_cli.py > "$output_dir/working-source-after.sha256"
cmp "$output_dir/working-source-before.sha256" "$output_dir/working-source-after.sha256"
# Preserve mutmut's failure/survivor/timeout exit status; never use --CI masking.
exit "$mutation_exit"
