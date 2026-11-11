#!/usr/bin/env bash
# Mutate only the lines the device smoke gate PR added (against its base 8daf810).
# parity_worker.py refuses Python other than 3.9, so its tests skip on 3.12 and
# its mutants have no tests here; see the reviewed policy.
source "$(dirname "$0")/lib.sh"
base=8daf810e0abd75cd417e16bab19fa59a330985e4
mutate=(scripts/device_smoke.py scripts/benchmark_curved_walls.py scripts/parity_worker.py)
tests=(tests/test_device_smoke.py tests/test_neutral.py tests/test_motion.py tests/test_kbc_precision.py)
reviewed=("${mutate[@]}" scripts/device_smoke_policy.json "${tests[@]}")
source_paths=(src scripts)
# parity_worker reads the vendored engine manifest; nothing under vendor is mutated.
copy=(vendor)
import_roots=(scripts)
test_args=(tests/test_device_smoke.py -m 'not production_python')
changed_lines() {
  git cat-file -e "$base^{commit}" || { echo "Full history with $base is required" >&2; return 65; }
  git diff --no-prefix "$base" -- "${mutate[@]}"
}
run_study "$@"
