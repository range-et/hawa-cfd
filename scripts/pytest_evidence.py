"""Explicit pytest plugin: machine-readable node IDs and completed outcomes."""
import json
from pathlib import Path


def pytest_addoption(parser):
    parser.addoption('--verification-evidence', required=True)


def pytest_configure(config):
    config._verification_collected = []
    config._verification_reports = {}


def pytest_collection_finish(session):
    session.config._verification_collected = [item.nodeid for item in session.items]


def pytest_runtest_logreport(report):
    # Set by sessionstart; the plugin runs in its own isolated pytest process.
    reports = _config._verification_reports
    reports.setdefault(report.nodeid, []).append((report.when, report.outcome))


def pytest_sessionstart(session):
    global _config
    _config = session.config


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    outcomes = []
    for nodeid, phases in config._verification_reports.items():
        phase_names = [phase for phase, outcome in phases]
        if (len(set(phase_names)) != len(phase_names) or 'setup' not in phase_names
                or 'teardown' not in phase_names or any(outcome == 'failed' for phase, outcome in phases)):
            outcome = 'failed'
        elif any(outcome == 'skipped' for phase, outcome in phases):
            outcome = 'skipped'
        elif ('call', 'passed') in phases:
            outcome = 'passed'
        else:
            outcome = 'failed'
        outcomes.append(dict(nodeid=nodeid, outcome=outcome))
    Path(config.getoption('--verification-evidence')).write_text(json.dumps(dict(
        collected=config._verification_collected, outcomes=outcomes, exit_code=int(exitstatus)), indent=2), encoding='utf-8')
