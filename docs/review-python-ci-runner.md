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
