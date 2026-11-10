#!/usr/bin/env bash
# HAWA-003: mutate only the lines in atmospheric-precision.patch (storage_resolution,
# the dissipation_storage quality field and the precision harness) in a disposable copy.
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../.." && pwd)"
python_bin="$repo_dir/.venv/bin/python"
mutmut_bin="$repo_dir/.venv/bin/mutmut"
output_dir="${1:?Usage: bash tools/mutation/run_atmospheric_precision.sh NEW_OUTPUT_DIRECTORY}"
sources=(src/hawa/neutral.py src/hawa/quality.py scripts/verify_atmospheric_precision.py tests/test_atmospheric_precision.py tools/mutation/atmospheric-precision.patch)
"$python_bin" -c 'import importlib.metadata as m; assert m.version("mutmut") == "2.4.5", "Install tools/mutation/requirements.txt"; import whatthepatch'
mkdir "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
cp -R "$repo_dir/src" "$output_dir/src"
find "$output_dir/src" -type d -name __pycache__ -prune -exec rm -rf {} +
mkdir "$output_dir/tests" "$output_dir/scripts" "$output_dir/tools" "$output_dir/tools/mutation"
cp "$repo_dir/tests/test_atmospheric_precision.py" "$output_dir/tests/"
cp "$repo_dir/scripts/verify_atmospheric_precision.py" "$output_dir/scripts/"
cp "$repo_dir/tools/mutation/atmospheric-precision.patch" "$output_dir/tools/mutation/"
cd "$repo_dir"
shasum -a 256 "${sources[@]}" > "$output_dir/working-source-before.sha256"
cd "$output_dir"
printf '[pytest]\n' > pytest.ini
export PYTHONPATH="$output_dir/src:$repo_dir/vendor/lettuce"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
unset PYTEST_ADDOPTS
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
"$python_bin" -c 'import sys; sys.path.insert(0, "scripts"); import hawa.neutral, hawa.quality, verify_atmospheric_precision as v; from pathlib import Path; root=Path(".").resolve(); modules=(hawa.neutral, hawa.quality, v); assert all(Path(m.__file__).resolve().is_relative_to(root) for m in modules); print("\n".join(m.__file__ for m in modules))' > imported-source.txt
"$python_bin" -m pytest tests/test_atmospheric_precision.py --collect-only -q > collected.txt 2>&1
"$python_bin" -m pytest tests/test_atmospheric_precision.py -q --junitxml=control.xml > control.log 2>&1
set +e
"$mutmut_bin" run --paths-to-mutate src/hawa/neutral.py,src/hawa/quality.py,scripts/verify_atmospheric_precision.py --use-patch-file tools/mutation/atmospheric-precision.patch --tests-dir tests/ --runner "\"$python_bin\" -m pytest tests/test_atmospheric_precision.py -q -x" --no-progress > mutation.log 2>&1
mutation_exit=$?
set -e
printf '%s\n' "$mutation_exit" > mutation-exit.txt
"$mutmut_bin" results > results.txt
"$mutmut_bin" junitxml > mutations.xml
"$mutmut_bin" show all > mutations.diff
cd "$repo_dir"
shasum -a 256 "${sources[@]}" > "$output_dir/working-source-after.sha256"
cmp "$output_dir/working-source-before.sha256" "$output_dir/working-source-after.sha256"
exit "$mutation_exit"
