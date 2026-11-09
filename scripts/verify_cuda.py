"""Repeatable Windows/CUDA headless verification with fresh, fail-closed evidence.

Prepare .venv with torch==2.8.0+cu128 and bootstrap_reference.py first.
This exercises Hawa's portable PyTorch CUDA backend, not Lettuce's optional
generated native CUDA extension or the live Rhino/Grasshopper UI.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from verification_evidence import snapshot, clean_environment, validate_pytest

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--stages', nargs='+', choices=['suite', 'upstream', 'parity', 'examples'],
                        default=['suite', 'upstream', 'parity', 'examples'])
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    if sys.version_info[:2] != (3, 9):
        parser.error('Use the production Python 3.9 environment')
    import numpy as np
    import torch
    from hawa.backends import select_backend
    from audit_backport import audit

    backend = select_backend('cuda:0')  # A real operation; never silently falls back.
    if not torch.__version__.startswith('2.8.0') or np.__version__ != '2.0.2':
        parser.error('Expected pinned PyTorch 2.8.0 and NumPy 2.0.2')
    output = (args.output or ROOT / 'results/windows-cuda' /
              datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')).resolve()
    output.mkdir(parents=True, exist_ok=False)  # Refuse stale evidence.
    report = {
        'scope': 'Headless portable CUDA; live Rhino and generated CUDA extension excluded',
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
        'environment': dict(os=platform.platform(), python=sys.version, torch=torch.__version__,
                            numpy=np.__version__, cuda_runtime=torch.version.cuda,
                            gpu=torch.cuda.get_device_name(0),
                            capability=torch.cuda.get_device_capability(0), backend=backend.info()),
        'source_audit': audit(), 'stages': [], 'passed': False,
    }
    before = snapshot(ROOT)
    report['source_before'] = before
    report['requested_stages'] = args.stages
    report['full_scope'] = set(args.stages) == {'suite', 'upstream', 'parity', 'examples'}
    report['full_passed'] = False
    (output / 'source.diff').write_bytes(subprocess.check_output(['git', 'diff', 'HEAD', '--binary'], cwd=ROOT))
    (output / 'index.diff').write_bytes(subprocess.check_output(['git', 'diff', '--cached', '--binary'], cwd=ROOT))
    env = clean_environment()

    def save():
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

    def run(name, arguments, xml=None, expected=None):
        command = [sys.executable, *map(str, arguments)]
        start = time.monotonic()
        print('Running ' + name, flush=True)
        with (output / (name + '.log')).open('w', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        entry = dict(name=name, command=command, exit_code=result.returncode,
                     seconds=time.monotonic()-start, passed=result.returncode == 0)
        if xml is not None:
            try:
                entry['counts'] = validate_pytest(expected, output / (name + '.json'), xml,
                                                  require_cuda=name.startswith('hawa'))
            except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
                entry.update(passed=False, error='Invalid pytest evidence: ' + str(exc))
        after = snapshot(ROOT)
        entry['source_unchanged'] = after == before
        if not entry['source_unchanged']:
            entry.update(passed=False, error='Source/index changed during verification')
        report['source_after'] = after
        report['stages'].append(entry)
        save()
        print('{}: {}'.format(name, 'PASS' if entry['passed'] else 'FAIL'), flush=True)
        return entry['passed']

    def pytest_stage(name, arguments):
        expected = output / (name + '-collection.json')
        common = ['-m', 'pytest', *arguments, '-o', 'addopts=', '-p', 'scripts.pytest_evidence']
        if not run(name + '-collection', [*common, '--collect-only', '-q',
                                         '--verification-evidence=' + str(expected)]):
            return
        xml = output / (name + '.xml')
        run(name, [*common, '-q', '-ra', '--junitxml=' + str(xml),
                   '--verification-evidence=' + str(output / (name + '.json'))], xml, expected)

    save()
    if 'suite' in args.stages:
        for repeat in range(1, args.repeats+1):
            pytest_stage('hawa-{}'.format(repeat), ['tests', '--require-cuda'])
    if 'upstream' in args.stages:
        pytest_stage('upstream-portable', ['vendor/lettuce/tests', '-p', 'scripts.pytest_portable',
                     '--ignore=vendor/lettuce/tests/native', '-k', 'not Native'])
    if 'parity' in args.stages:
        run('core-parity', ['scripts/compare_engines.py', '--output', output / 'parity'])
    if 'examples' in args.stages:
        examples = output / 'examples'
        for device in ('cpu', 'cuda:0'):
            run('examples-' + device.replace(':', '-'), ['scripts/run_examples.py', '--device', device,
                                                        '--output-root', examples])
        run('example-parity', ['scripts/compare_examples.py', '--cpu-dir', examples / 'backport-cpu',
                              '--gpu-dir', examples / 'backport-cuda-0', '--output', examples / 'parity.json'])
    report['passed'] = bool(report['stages']) and all(s['passed'] for s in report['stages'])
    report['full_passed'] = report['passed'] and report['full_scope']
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    save()
    print('Evidence: ' + str(output), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
