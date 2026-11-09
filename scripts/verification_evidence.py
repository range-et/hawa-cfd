"""Shared provenance and complete pytest evidence checks for CUDA qualification."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def snapshot(root):
    """Hash every tracked/nonignored file, plus HEAD and the index (including deletions)."""
    names = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root).decode().split('\0')
    files = {}
    for name in sorted(set(names) - {''}):
        path = root / name
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return dict(files=files,
                commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip(),
                index_sha256=hashlib.sha256(subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=root)).hexdigest())


def clean_environment():
    """Prevent caller selectors/plugins from silently changing the declared pytest scope."""
    env = dict(os.environ, PYTHONUTF8='1', MPLBACKEND='Agg', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    for name in ('PYTEST_ADDOPTS', 'PYTEST_PLUGINS'):
        env.pop(name, None)
    return env


def validate_pytest(expected_path, actual_path, xml, require_cuda=False):
    """Require an independent collection, exactly one outcome per ID and intact JUnit."""
    expected = json.loads(expected_path.read_text())
    actual = json.loads(actual_path.read_text())
    ids = expected['collected']
    if (not ids or len(set(ids)) != len(ids) or expected['exit_code'] != 0
            or actual['exit_code'] != 0 or actual['collected'] != ids):
        raise ValueError('Incomplete, duplicate or failed collection')
    outcomes = actual['outcomes']
    if Counter(row['nodeid'] for row in outcomes) != Counter(ids):
        raise ValueError('Missing or duplicate test outcomes')
    if any(row['outcome'] not in ('passed', 'skipped') for row in outcomes):
        raise ValueError('Failed test outcome')
    cases = list(ET.parse(xml).iter('testcase'))
    keys = [(c.get('classname'), c.get('name')) for c in cases]
    if len(cases) != len(ids) or len(set(keys)) != len(keys):
        raise ValueError('Incomplete or duplicate JUnit evidence')
    if any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise ValueError('Failed JUnit evidence')
    skipped = sum(row['outcome'] == 'skipped' for row in outcomes)
    if skipped != sum(c.find('skipped') is not None for c in cases):
        raise ValueError('JUnit/outcome skip mismatch')
    cuda = [row for row in outcomes if 'cuda' in row['nodeid'].partition('[')[2].lower()]
    if require_cuda and (not cuda or any(row['outcome'] != 'passed' for row in cuda)):
        raise ValueError('Missing or skipped CUDA cases')
    return dict(total=len(ids), skipped=skipped, failures=0, cuda_named=len(cuda),
                cuda_skipped=sum(row['outcome'] == 'skipped' for row in cuda))
