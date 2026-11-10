"""Check a finished local G6 run; missing, stale or partial evidence fails closed."""
import argparse
import subprocess
from collections import Counter
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from matrix.contract import verify_evidence,verify_examples


def main():
    p=argparse.ArgumentParser();p.add_argument('--matrix',required=True);p.add_argument('--junit',required=True);p.add_argument('--state-log',required=True);p.add_argument('--release',action='store_true');a=p.parse_args()
    matrix=verify_evidence(a.matrix);examples=verify_examples(ROOT/'docs/coverage-example-graphs.json')
    suites=ET.parse(a.junit).getroot();cases=list(suites.iter('testcase'))
    if not cases or any(c.find('error') is not None or c.find('failure') is not None for c in cases):raise ValueError('Missing or failed unit suite')
    collected=subprocess.run([sys.executable,'-m','pytest','tests','--collect-only','-q'],cwd=ROOT,text=True,capture_output=True,check=True).stdout
    expected=Counter((Path(line.split('::',1)[0]).stem,line.split('::',1)[1]) for line in collected.splitlines() if line.startswith('tests/') and '::' in line)
    observed=Counter((c.get('classname','').split('.')[-1],c.get('name')) for c in cases)
    if not expected or expected!=observed:raise ValueError('Unit inventory missing, duplicated or stale')
    lines=Path(a.state_log).read_text().splitlines()
    state=json.loads(next(line for line in reversed(lines) if line.startswith('{')))
    if state['passed']!=67 or any(line.startswith('FAIL') for line in lines):raise ValueError('State contract failure or inventory drift')
    skipped=sum(c.find('skipped') is not None for c in cases)
    report=dict(matrix=matrix['counts'],examples=examples,unit_tests=dict(passed=len(cases)-skipped,skipped=skipped),state_contracts=state['passed'],
                local_pass=True,release_pass=matrix['release_pass'] and skipped==0,
                scope='Finite compatibility and complete declared test-module execution. Host and numerical qualification remain separate gates.')
    print(json.dumps(report,indent=2))
    return 1 if a.release and not report['release_pass'] else 0


if __name__=='__main__':raise SystemExit(main())
