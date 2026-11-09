# HAWA-050 — Hosted Python 3.9 runner pin

November 9, 2026. Reviewer/implementer: Codex primary agent, self-review.

The first Python issue PR's hosted function gate failed at environment setup,
before tests ran: [failed job](https://github.com/range-et/hawa-cfd/actions/runs/42710638393/job/129478914639).
`ubuntu-latest` resolved to Ubuntu 26.04; `actions/setup-python@v6` could not find
Python 3.9 for that runner.

The official [Python versions manifest](https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json)
was inspected on November 9. Python 3.9.25 lists Linux x64 builds for Ubuntu 22.04
and 24.04, not 26.04. Pin the existing function-test job to `ubuntu-24.04` and
`3.9.25`, matching the development interpreter. No production dependency version,
function baseline, threshold, solver or test exclusion changes.

The fix lives once on the shared Python-study base so all three issue PRs inherit
it without mixing CI repair into their implementation diffs. Their previously
measured source/test inventories are unchanged; committed matrix freshness is
checked again after updating the base. Hosted evidence must still pass on each
actual PR head. HAWA-050 remains in progress until hosted checks and integration;
no local-only claim that GitHub succeeded.

G0/G1: PASS for scoped provisioning fix, based on actual failure and official
runtime inventory. G2: local YAML change inspected; hosted recheck required.
G3/G4/G6: not applicable to the runner-label/interpreter patch pin; no numerical,
UI or compatibility-contract change. G5: no plugin install or release.

The runner pin reached dependency installation on the next attempt, exposing a
second provisioning failure: [dependency job](https://github.com/range-et/hawa-cfd/actions/runs/42711444283/job/129481723122).
The bundled pip rejected normalized metadata names for dependencies and attempted
to build typing-extensions using only the PyTorch CPU index, where `flit_core`
was absent. Pin pip 25.3 (supports Python >=3.9), install the explicit
`torch==2.8.0+cpu` wheel from that index with `--no-deps`, then resolve the existing
project/test dependencies through normal PyPI. This keeps the CPU variant while
avoiding use of a specialized wheel index as the general dependency source.
Production dependency pins and test thresholds remain unchanged. Both failed
attempts are retained; the next hosted run must reach and pass the actual tests.

## Hosted follow-up

The initial implementation heads of PRs #3, #4 and #5 all passed their hosted
function gates after this repair. [PR #3 passing run](https://github.com/range-et/hawa-cfd/actions/runs/42711875100)
and [PR #5 passing run](https://github.com/range-et/hawa-cfd/actions/runs/42712962650)
provide executed evidence. G2 passes for that scoped provisioning check. The fix
is on the shared study base; integration into the main development branch remains
separate. Revised PR heads require their own CI checks.
