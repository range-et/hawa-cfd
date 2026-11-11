#!/usr/bin/env bash
# The whole of the CLI module, against tests/test_cli.py.
source "$(dirname "$0")/lib.sh"
mutate=(src/hawa/cli.py)
tests=(tests/test_cli.py)
reviewed=(src/hawa/cli.py tests/test_cli.py)
test_args=(tests/test_cli.py)
run_study "$@"
