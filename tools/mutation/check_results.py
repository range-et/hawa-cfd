"""Accept only the exact reviewed mutation inventory, never a score threshold."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(directory, policy, root=ROOT):
    directory, root = Path(directory), Path(root)
    for name, expected in policy['sources'].items():
        if digest(root/name) != expected or digest(directory/name) != expected:
            raise ValueError('Reviewed source/test snapshot changed: '+name)
    if (directory/'working-source-before.sha256').read_bytes() != (directory/'working-source-after.sha256').read_bytes():
        raise ValueError('Working source changed during mutation run')
    control = list(ET.parse(directory/'control.xml').getroot().iter('testcase'))
    control_path = Path(policy.get('control_test_file', 'tests/test_cli.py')).parts
    expected = Counter(line.split('::', 1)[1] for line in (directory/'collected.txt').read_text().splitlines()
                       if '::' in line and Path(line.split('::', 1)[0]).parts[-len(control_path):] == control_path)
    if not expected or Counter(c.get('name') for c in control) != expected:
        raise ValueError('Missing, duplicated or filtered control tests')
    if any(c.find(tag) is not None for c in control for tag in ('failure','error','skipped')):
        raise ValueError('Control suite did not pass completely')
    cases = list(ET.parse(directory/'mutations.xml').getroot().iter('testcase'))
    names = [c.get('name') for c in cases]
    if len(cases) != policy['mutants'] or set(names) != {'Mutant #'+str(n) for n in range(1, policy['mutants']+1)}:
        raise ValueError('Missing or duplicated mutation inventory')
    survivors = {}
    for case in cases:
        if case.find('error') is not None or case.find('skipped') is not None:
            raise ValueError('Mutation execution was incomplete')
        failed = case.find('failure')
        if failed is not None:
            if failed.get('message') != 'bad_survived':
                raise ValueError('Timeout, suspicious or unknown mutation outcome')
            survivors[case.get('name')] = hashlib.sha256((failed.text or '').encode()).hexdigest()
    reviewed = {name: row['diff_sha256'] for name, row in policy['reviewed_survivors'].items()}
    if survivors != reviewed:
        raise ValueError('Survivors changed; review the exact diffs')
    raw_exit = int((directory/'mutation-exit.txt').read_text())
    if raw_exit != (2 if survivors else 0):
        raise ValueError('Unexpected raw mutmut exit status')
    return dict(mutants=len(cases), killed=len(cases)-len(survivors),
                reviewed_survivors=len(survivors), control_tests=len(control),
                raw_mutmut_exit=raw_exit, policy_pass=True,
                scope=policy.get('scope', 'Exact reviewed CLI pilot; not whole-codebase mutation coverage'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--policy', type=Path, default=ROOT/'tools/mutation/cli-policy.json')
    args = parser.parse_args(argv)
    result = verify(args.directory, json.loads(args.policy.read_text()))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
