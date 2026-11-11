# Shared mutmut 3.7.0 study driver, sourced by tools/mutation/run_*.sh.
#
# A runner sets these arrays, then calls `run_study NEW_OUTPUT_DIRECTORY`:
#   mutate        files to mutate (whole files, or only patch lines with `base`)
#   reviewed      every file whose hash the policy pins (sources, tests, data)
#   tests         test files (and tests/conftest.py when needed) copied into the study
#   test_args     pytest selection: the control suite and mutmut's test universe
# and optionally:
#   source_paths  trees copied for mutmut, which mutates only `mutate` in them
#                 (default: src plus each mutated file outside src); a tree
#                 must hold whole packages
#   copy          other repository paths the tests read, outside source_paths
#   import_roots  directories tests put on sys.path, such as scripts (a copied
#                 vendor/lettuce is always one)
#   changed_lines a function that prints a `git diff --no-prefix` patch; only
#                 the lines it adds are mutated
# The study runs in a fresh copy with no cache. mutmut forks one child per
# mutant from a parent that has imported torch, so the study pins one CPU thread
# per process and must not touch an accelerator.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_bin="$repo_dir/.venv-dev/bin/python"
launcher="$repo_dir/tools/mutation/mutmut3.py"

run_study() {
  local output_dir="${1:?Usage: bash tools/mutation/run_STUDY.sh NEW_OUTPUT_DIRECTORY}"
  local workers="${MUTMUT_MAX_CHILDREN:-$(getconf _NPROCESSORS_ONLN)}"
  local path control_pid mutation_exit
  local -a roots=() scope=() paths=()
  "$python_bin" -c 'import importlib.metadata as m; assert m.version("mutmut") == "3.7.0", "Install the tools group into .venv-dev"'
  # mkdir deliberately rejects reuse: never reuse a cache or mutate working source.
  mkdir "$output_dir"
  output_dir="$(cd "$output_dir" && pwd)"
  if [[ -n "${source_paths+x}" ]]; then
    paths=("${source_paths[@]}")
  else
    paths=(src)
    for path in "${mutate[@]}"; do [[ "$path" == src/* ]] || paths+=("$path"); done
  fi
  mkdir -p "$output_dir/tests"
  for path in "${paths[@]}" ${copy[@]+"${copy[@]}"}; do
    mkdir -p "$(dirname "$output_dir/$path")"
    cp -R "$repo_dir/$path" "$output_dir/$path"
  done
  cp "${tests[@]/#/$repo_dir/}" "$output_dir/tests/"
  find "$output_dir" -type d -name __pycache__ -prune -exec rm -rf {} +
  cd "$repo_dir"
  shasum -a 256 "${reviewed[@]}" > "$output_dir/working-source-before.sha256"
  if declare -F changed_lines > /dev/null; then
    changed_lines > "$output_dir/changed-lines.patch"
    "$python_bin" "$launcher" changed-lines "$output_dir/changed-lines.patch" "$output_dir/scope.json"
    scope=(--scope scope.json)
  fi
  for path in ${import_roots[@]+"${import_roots[@]}"}; do roots+=(--import-root "$path"); done
  # A study that copies the vendored engine imports it from its own copy.
  local lettuce="$repo_dir/vendor/lettuce"
  if [[ -d "$output_dir/vendor/lettuce/lettuce" ]]; then
    lettuce="$output_dir/vendor/lettuce"
    roots+=(--import-root vendor/lettuce)
  fi
  cd "$output_dir"
  # mutmut copies also_copy files into mutants/ but does not create their parents.
  for path in ${copy[@]+"${copy[@]}"}; do mkdir -p "mutants/$(dirname "$path")"; done
  printf '[pytest]\n' > pytest.ini
  {
    printf '[mutmut]\nsource_paths =\n'; printf '    %s\n' "${paths[@]}"
    printf 'only_mutate =\n'; printf '    %s\n' "${mutate[@]}"
    printf 'pytest_add_cli_args_test_selection =\n'; printf '    %s\n' "${test_args[@]}"
    printf 'pytest_add_cli_args =\n    -p\n    no:cacheprovider\n'
    printf 'also_copy =\n    pytest.ini\n'
    for path in ${copy[@]+"${copy[@]}"}; do printf '    %s\n' "$path"; done
    printf 'use_git_change_detection = false\n'
  } > setup.cfg
  export PYTHONPATH="$output_dir/src:$lettuce"
  export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
  export CUDA_VISIBLE_DEVICES='' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
  unset PYTEST_ADDOPTS
  "$python_bin" -c 'import importlib.metadata as m; print("mutmut=="+m.version("mutmut"))' > tool.txt
  "$python_bin" -m pytest "${test_args[@]}" -p no:cacheprovider --collect-only -q > collected.txt 2>&1
  # The control suite reads the unmutated copy, so it runs beside mutmut's serial
  # stats and clean-test phases instead of before them.
  "$python_bin" -m pytest "${test_args[@]}" -p no:cacheprovider -q --junitxml=control.xml > control.log 2>&1 &
  control_pid=$!
  set +e
  "$python_bin" "$launcher" run --max-children "$workers" ${roots[@]+"${roots[@]}"} ${scope[@]+"${scope[@]}"} > mutation.log 2>&1
  mutation_exit=$?
  # control.xml carries the control verdict for check_results.py.
  wait "$control_pid"
  set -e
  printf '%s\n' "$mutation_exit" > mutation-exit.txt
  "$python_bin" "$launcher" export > export.log 2>&1
  cd "$repo_dir"
  shasum -a 256 "${reviewed[@]}" > "$output_dir/working-source-after.sha256"
  cmp "$output_dir/working-source-before.sha256" "$output_dir/working-source-after.sha256"
  # Preserve mutmut's exit status; the policy checker judges every mutant.
  return "$mutation_exit"
}
