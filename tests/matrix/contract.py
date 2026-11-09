"""Evidence integrity and drift checks, independent of the executing loop."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from .cases import topologies,combinations,DEVICES
from .operations import refinements,field_cases
from .nesting import nesting_cases
from .collections import collection_cases

ROOT=Path(__file__).resolve().parents[2]


def source_hashes():
    paths=list((ROOT/'src/hawa').glob('*.py'))+list((ROOT/'vendor/lettuce/lettuce').rglob('*.py'))+list((ROOT/'plugin').rglob('*.cs'))+list((ROOT/'tests/matrix').glob('*.py'))+[ROOT/'scripts/run_compatibility_matrix.py',ROOT/'pyproject.toml',ROOT/'uv.lock']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths) if not {'obj','bin'}&set(p.parts)}


def environment():
    import sys,platform,torch,numpy,lettuce
    return dict(python=sys.version,platform=platform.platform(),machine=platform.machine(),torch=torch.__version__,numpy=numpy.__version__,lettuce=lettuce.__version__)


def expected_rows():
    rows={r['id']:r['expected'] for r in topologies()}
    for family in (combinations(),refinements(),(dict(r,id=r['id'].replace('faces/','topology-run/')) for r in topologies() if r['expected'])):
        for r in family:
            for device in DEVICES:rows[r['id']+'/'+device]=r['expected']
    rows.update((r['id'],r['expected']) for r in field_cases())
    rows.update((r['id'],r['expected']) for r in collection_cases())
    for r in nesting_cases():
        for device in DEVICES:rows[r['id']+'/'+device]=r['expected']
    return rows


def verify_rows(rows, expected):
    counts=Counter();seen=set()
    for row in rows:
        ident=row['id']
        if ident in seen:raise ValueError('Duplicate matrix row: '+ident)
        if ident not in expected:raise ValueError('Unexpected matrix row: '+ident)
        seen.add(ident)
        if row['expected']!=('accept' if expected[ident] else 'reject'):raise ValueError('Oracle mismatch: '+ident)
        status=row['status']
        if status not in ('passed','failed','blocked'):raise ValueError('Invalid terminal state')
        if status=='passed' and (row['observed'] in ('run','accept'))!=expected[ident]:raise ValueError('False pass: '+ident)
        if status=='blocked' and (ident.rsplit('/',1)[-1] not in DEVICES or not row.get('reason')):raise ValueError('Invalid hardware block')
        counts[status]+=1
    if seen!=set(expected):raise ValueError('Missing matrix rows: '+str(len(set(expected)-seen)))
    return {state:counts[state] for state in ('passed','failed','blocked')}


def verify_evidence(directory, current_sources=True):
    directory=Path(directory);summary=json.loads((directory/'summary.json').read_text());path=directory/'rows.jsonl'
    if summary['state']!='complete':raise ValueError('Matrix did not finish')
    with path.open() as f:counts=verify_rows((json.loads(line) for line in f),expected_rows())
    if counts!=summary['counts'] or sum(counts.values())!=summary['expected_rows']:raise ValueError('Count mismatch')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=summary['rows_sha256']:raise ValueError('Row artifact changed')
    if summary['sources_changed_during_run']:raise ValueError('Sources changed while matrix ran')
    if current_sources and (summary['sources']!=source_hashes() or summary['environment']!=environment()):raise ValueError('Stale matrix sources or environment')
    if counts['failed']:raise ValueError('Matrix failures remain')
    return summary


def verify_examples(report):
    graph=json.loads(Path(report).read_text())
    files={str(p.relative_to(ROOT)):p for p in (ROOT/'examples').rglob('*.gh') if not p.name.startswith('09-')}
    if set(files)!=set(r['file'] for r in graph['examples']):raise ValueError('Example inventory drift')
    used=set()
    for example in graph['examples']:
        if hashlib.sha256(files[example['file']].read_bytes()).hexdigest()!=example['sha256']:raise ValueError('Stale graph: '+example['file'])
        if example['true_toggles'] or example['archive_errors'] or not example['guide_panels']:raise ValueError('Unsafe/unannotated archive: '+example['file'])
        used.update(example['nodes'])
    declared=set()
    for source in (ROOT/'plugin/Hawa.Grasshopper').glob('*.cs'):
        declared.update(re.findall(r'public sealed class (\w+Component)\s*:',source.read_text()))
    declared.discard('LegacyHullComponent')  # Explicit hidden compatibility reader, preserved user example 09.
    nodes={n['type'] for n in graph['nodes']}
    if declared!=nodes:raise ValueError('Public component inventory drift')
    if nodes-used or graph['nodes_without_example']:raise ValueError('Public nodes without example')
    return dict(public_nodes=len(nodes),examples=len(files),unique_edges=len({(e['from_type'],e['from_port'],e['to_type'],e['to_port']) for r in graph['examples'] for e in r['edges']}))
