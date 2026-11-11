#!/usr/bin/env bash
# HAWA-003: mutate only the lines in atmospheric-precision.patch (storage_resolution,
# the dissipation_storage quality field and the precision harness).
source "$(dirname "$0")/lib.sh"
mutate=(src/hawa/neutral.py src/hawa/quality.py scripts/verify_atmospheric_precision.py)
tests=(tests/test_atmospheric_precision.py)
reviewed=("${mutate[@]}" tests/test_atmospheric_precision.py tools/mutation/atmospheric-precision.patch)
import_roots=(scripts)
copy=(tools/mutation/atmospheric-precision.patch)
test_args=(tests/test_atmospheric_precision.py)
# The committed patch has Git's a/ and b/ prefixes; the scope uses repository paths.
changed_lines() { sed -e 's#^+++ b/#+++ #' tools/mutation/atmospheric-precision.patch; }
run_study "$@"
