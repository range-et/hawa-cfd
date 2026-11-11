#!/usr/bin/env bash
# Mutate only the lines the device smoke gate PR adds, in a disposable, cache-free copy.
# Commit first: the patch is `git diff BASE` of the committed working tree.
set -euo pipefail
repo_dir="$(cd "$(dirname "$0")/../.." && pwd)"
python_bin="$repo_dir/.venv/bin/python"
mutmut_bin="$repo_dir/.venv/bin/mutmut"
output_dir="${1:?Usage: bash tools/mutation/run_device_smoke.sh NEW_OUTPUT_DIRECTORY BASE_REVISION}"
base="${2:?Usage: bash tools/mutation/run_device_smoke.sh NEW_OUTPUT_DIRECTORY BASE_REVISION}"
"$python_bin" -c 'import importlib.metadata as m; assert m.version("mutmut") == "2.4.5" and m.version("whatthepatch") == "1.0.7", "Install tools/mutation/requirements.txt"'
sources=(scripts/device_smoke.py scripts/benchmark_curved_walls.py scripts/parity_worker.py)
reviewed=("${sources[@]}" scripts/device_smoke_policy.json tests/test_device_smoke.py
          tests/test_neutral.py tests/test_motion.py tests/test_kbc_precision.py)
mkdir "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
cp -R "$repo_dir/src" "$output_dir/src"
cp -R "$repo_dir/scripts" "$output_dir/scripts"
find "$output_dir/src" "$output_dir/scripts" -type d -name __pycache__ -prune -exec rm -rf {} +
mkdir "$output_dir/tests"
cp "$repo_dir"/tests/{test_device_smoke,test_neutral,test_motion,test_kbc_precision}.py "$output_dir/tests/"
# parity_worker reads the vendored engine manifest; nothing under vendor is mutated.
ln -s "$repo_dir/vendor" "$output_dir/vendor"
cd "$repo_dir"
git rev-parse --verify "$base^{commit}" > "$output_dir/base-revision.txt"
git diff "$base" -- "${sources[@]}" > "$output_dir/changed-lines.patch"
shasum -a 256 "${reviewed[@]}" > "$output_dir/working-source-before.sha256"
cd "$output_dir"
printf '[pytest]\n' > pytest.ini
export PYTHONPATH="$output_dir/src:$repo_dir/vendor/lettuce"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
unset PYTEST_ADDOPTS
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
"$python_bin" -c 'import sys; sys.path.insert(0, "scripts"); import device_smoke, benchmark_curved_walls, parity_worker, hawa; from pathlib import Path; modules=(device_smoke, benchmark_curved_walls, parity_worker, hawa); assert all(Path(m.__file__).resolve().is_relative_to(Path(".").resolve()) for m in modules); print("\n".join(m.__file__ for m in modules))' > imported-source.txt
"$python_bin" -m pytest tests/test_device_smoke.py --collect-only -q > collected.txt 2>&1
"$python_bin" -m pytest tests/test_device_smoke.py -q --junitxml=control.xml > control.log 2>&1
set +e
"$mutmut_bin" run --paths-to-mutate "$(IFS=,; echo "${sources[*]}")" --use-patch-file changed-lines.patch --tests-dir tests/ --runner "\"$python_bin\" -m pytest tests/test_device_smoke.py -q -x" --no-progress > mutation.log 2>&1
mutation_exit=$?
set -e
printf '%s\n' "$mutation_exit" > mutation-exit.txt
"$mutmut_bin" results > results.txt
"$mutmut_bin" junitxml > mutations.xml
"$mutmut_bin" show all > mutations.diff
cd "$repo_dir"
shasum -a 256 "${reviewed[@]}" > "$output_dir/working-source-after.sha256"
cmp "$output_dir/working-source-before.sha256" "$output_dir/working-source-after.sha256"
# Preserve mutmut's survivor/timeout exit status; never use --CI masking.
exit "$mutation_exit"
