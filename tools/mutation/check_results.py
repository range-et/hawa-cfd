"""Accept only the exact reviewed mutation inventory, never a score threshold."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
# mutmut 3.7.0 stores each mutant's raw exit code. Only pytest's "tests failed"
# exit (1) is a kill. 0 is a survivor and 33 means no selected test reached the
# mutated function; both need a reviewed diff. Anything else (timeouts, signals,
# pytest internal or usage errors, interrupted or unchecked) fails the check,
# even where mutmut itself would report "killed".
KILLED = 1
REVIEWABLE = {0: 'survived', 33: 'no tests'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def inventory_digest(names):
    """Hash the sorted mutant names, so the policy pins exactly which mutants exist."""
    return text_digest('\n'.join(sorted(names)))


def outcomes(directory):
    """Return (mutant rows, unreviewed outcome map) from a study's exported mutants.json."""
    rows = json.loads((Path(directory)/'mutants.json').read_text())
    survivors = {}
    for name, row in rows.items():
        if row['exit_code'] == KILLED:
            continue
        if row['exit_code'] not in REVIEWABLE:
            raise ValueError('Timeout, error, suspicious or unchecked mutant: '+name)
        survivors[name] = dict(status=REVIEWABLE[row['exit_code']], diff_sha256=text_digest(row['diff']))
    return rows, survivors


def verify(directory, policy, root=ROOT):
    directory, root = Path(directory), Path(root)
    for name, expected in policy['sources'].items():
        if digest(root/name) != expected or digest(directory/name) != expected:
            raise ValueError('Reviewed source/test snapshot changed: '+name)
    if (directory/'working-source-before.sha256').read_bytes() != (directory/'working-source-after.sha256').read_bytes():
        raise ValueError('Working source changed during mutation run')
    if (directory/'tool.txt').read_text().strip() != policy['tool']:
        raise ValueError('Mutation tool differs from the reviewed policy')
    control = list(ET.parse(directory/'control.xml').getroot().iter('testcase'))
    control_paths = [Path(name).parts for name in policy['control_test_files']]
    collected = [line.split('::', 1) for line in (directory/'collected.txt').read_text().splitlines() if '::' in line]
    owners = [[path for path in control_paths if Path(name).parts[-len(path):] == path] for name, _ in collected]
    expected = Counter(test for (_, test), owner in zip(collected, owners) if owner)
    if (not expected or Counter(c.get('name') for c in control) != expected
            or any(not any(path in owner for owner in owners) for path in control_paths)):
        raise ValueError('Missing, duplicated or filtered control tests')
    if any(c.find(tag) is not None for c in control for tag in ('failure', 'error', 'skipped')):
        raise ValueError('Control suite did not pass completely')
    if int((directory/'mutation-exit.txt').read_text()) != 0:
        raise ValueError('mutmut run did not complete')
    rows, survivors = outcomes(directory)
    if len(rows) != policy['mutants'] or inventory_digest(rows) != policy['inventory_sha256']:
        raise ValueError('Mutation inventory changed; review the new mutants')
    reviewed = {}
    for name, row in policy['reviewed_survivors'].items():
        if not row['reason'].strip():
            raise ValueError('Reviewed survivor has no reason: '+name)
        reviewed[name] = dict(status=row['status'], diff_sha256=row['diff_sha256'])
    if survivors != reviewed:
        raise ValueError('Survivors changed; review the exact diffs')
    return dict(mutants=len(rows), killed=len(rows)-len(survivors),
                reviewed_survivors=len(survivors), control_tests=len(control),
                policy_pass=True, scope=policy['scope'])


def draft(directory, policy):
    """Return the policy a fresh run implies, keeping reasons only for unchanged diffs.

    New or changed survivors get an empty reason, which `verify` rejects until
    someone reviews the diff in mutations.diff and writes one.
    """
    directory = Path(directory)
    rows, survivors = outcomes(directory)
    old = policy['reviewed_survivors']
    for name, row in survivors.items():
        same = old.get(name, {})
        keep = same.get('status') == row['status'] and same.get('diff_sha256') == row['diff_sha256']
        row['reason'] = same['reason'] if keep else ''
    sources = {name: digest(directory/name) for name in policy['sources']}
    return dict(policy, tool=(directory/'tool.txt').read_text().strip(), mutants=len(rows),
                inventory_sha256=inventory_digest(rows), sources=sources,
                reviewed_survivors=dict(sorted(survivors.items())))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--policy', type=Path, default=ROOT/'tools/mutation/cli-policy.json')
    parser.add_argument('--draft', action='store_true',
                        help='print the policy this run implies instead of checking it')
    args = parser.parse_args(argv)
    policy = json.loads(args.policy.read_text())
    result = draft(args.directory, policy) if args.draft else verify(args.directory, policy)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
