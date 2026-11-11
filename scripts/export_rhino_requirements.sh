#!/usr/bin/env bash
# Re-export requirements/rhino-py39.txt from uv.lock for Python 3.9 only.
#
# uv.lock covers Python 3.9 (production, Rhino 8) and 3.12 (developer tooling),
# so a plain `uv export` adds python_full_version markers. Rhino only runs 3.9:
# lock a temporary copy narrowed to 3.9, preferring the versions in uv.lock, and
# export it with the command recorded in the file's header.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

mkdir -p "$work/vendor/lettuce" "$work/requirements"
cp "$root/pyproject.toml" "$root/uv.lock" "$work/"
cp "$root/vendor/lettuce/pyproject.toml" "$work/vendor/lettuce/"
sed -i.bak 's/^requires-python = .*/requires-python = ">=3.9,<3.10"/' "$work/pyproject.toml"

cd "$work"
uv lock --quiet
uv export --quiet --no-dev --no-hashes --no-emit-project --no-emit-package hawa-lettuce --output-file requirements/rhino-py39.txt >/dev/null
cp requirements/rhino-py39.txt "$root/requirements/rhino-py39.txt"
