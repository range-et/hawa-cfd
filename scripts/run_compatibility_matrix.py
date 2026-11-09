"""G6 finite compatibility gate. Missing hardware remains BLOCKED, never PASS.

Default: every declared six-face topology is preflighted (2 * 6**6); every
solver/method/geometry/import row is constructed and stepped on each device.
Use --release to fail if any required hardware is unavailable. Raw row inventory
is written incrementally, so crashes and incomplete runs cannot look complete.
"""
import argparse
import itertools
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from matrix.cases import combinations,make_combination,topologies,make_topology,DEVICES
from matrix.operations import refinements,make_refinement,field_cases,exercise_field
from matrix.nesting import nesting_cases,exercise_nesting
from matrix.collections import collection_cases,exercise_collection
from hawa.refinement import run_refined
from matrix.contract import source_hashes,expected_rows,verify_evidence,verify_examples,environment
import numpy as np
import torch
from hawa.plugin import Session,check_case


def available(device):
    return device=='cpu' or (device=='mps' and torch.backends.mps.is_available()) or (device.startswith('cuda') and torch.cuda.is_available())


def run(output, release=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    fixtures=output/'fixtures';fixtures.mkdir()
    counts=dict(passed=0,failed=0,blocked=0);family={};failures=[];start=time.monotonic()
    summary=dict(schema=1,inventory='hawa-compatibility-v1',state='running',counts=counts,families=family,failures=failures,
                 scope='Exhaustive declared discrete topology and solver products; not arbitrary graphs or physical validation')
    def save():
        summary['wall_seconds']=time.monotonic()-start
        (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    summary['sources']=source_hashes()
    summary['environment']=environment()
    summary['example_coverage']=verify_examples(ROOT/'docs/coverage-example-graphs.json')
    save()
    with (output/'rows.jsonl').open('w') as log:
        def record(row,status,**extra):
            kind=row['id'].split('/')[0];counts[status]+=1
            family.setdefault(kind,dict(passed=0,failed=0,blocked=0))[status]+=1
            value=dict(id=row['id'],expected='accept' if row['expected'] else 'reject',status=status,**extra)
            log.write(json.dumps(value)+'\n')
            if status=='failed':failures.append(value)
        for i,row in enumerate(topologies()):
            try:check_case(make_topology(row));accepted=True;error=''
            except ValueError as e:accepted=False;error=str(e)
            except Exception as e:record(row,'failed',error=type(e).__name__+': '+str(e));continue
            record(row,'passed' if accepted==row['expected'] else 'failed',observed='accept' if accepted else 'reject',error=error)
            if i%5000==0:save();log.flush();print('faces',i,counts,flush=True)
        for i,row in enumerate(itertools.chain(combinations(), refinements(), (dict(r,id=r['id'].replace('faces/','topology-run/')) for r in topologies() if r['expected']))):
            kind=row['id'].split('/')[0]
            spec=make_topology(row) if kind=='topology-run' else (make_refinement(row,fixtures) if kind=='refinement' else make_combination(row,fixtures))
            for device in DEVICES:
                item=dict(row,id=row['id']+'/'+device)
                if not available(device):record(item,'blocked',reason='device unavailable');continue
                try:
                    if kind=='refinement':
                        result=run_refined(dict(spec,device=device),lambda n:None)
                        assert np.isfinite(result['relative_mass_change'])
                    else:
                        session=Session(spec,device)
                        session.advance(4)
                        assert session.flow.i==4 and session.quality['finite'] and session.quality['positive_density']
                        assert np.isfinite(session.fields()['velocity']).all()
                    accepted=True;error=''
                except ValueError as e:accepted=False;error=str(e)
                except Exception as e:record(item,'failed',error=type(e).__name__+': '+str(e));continue
                record(item,'passed' if accepted==row['expected'] else 'failed',observed='run' if accepted else 'reject',device=device,steps=(2 if kind=='refinement' else 4) if accepted else 0,error=error)
            if i%20==0:gc.collect();save();log.flush();print('solver',i,counts,flush=True)
        for row in itertools.chain(field_cases(),collection_cases()):
            try:
                (exercise_collection if row['id'].startswith('collection/') else exercise_field)(row,fixtures);accepted=True;error=''
            except ValueError as e:accepted=False;error=str(e)
            except Exception as e:record(row,'failed',error=type(e).__name__+': '+str(e));continue
            record(row,'passed' if accepted==row['expected'] else 'failed',observed='run' if accepted else 'reject',error=error)
        for i,row in enumerate(nesting_cases()):
            for device in DEVICES:
                item=dict(row,id=row['id']+'/'+device)
                if not available(device):record(item,'blocked',reason='device unavailable');continue
                try:exercise_nesting(row,fixtures,device);accepted=True;error=''
                except ValueError as e:accepted=False;error=str(e)
                except Exception as e:record(item,'failed',error=type(e).__name__+': '+str(e));continue
                record(item,'passed' if accepted==row['expected'] else 'failed',observed='run' if accepted else 'reject',error=error)
            if i%30==0:save();log.flush();print('nesting',i,counts,flush=True)
    expected=len(expected_rows())
    changed=summary['sources']!=source_hashes()
    summary.update(state='complete',expected_rows=expected,recorded_rows=sum(counts.values()),sources_changed_during_run=changed,
                   rows_sha256=hashlib.sha256((output/'rows.jsonl').read_bytes()).hexdigest(),
                   local_pass=not changed and counts['failed']==0 and sum(counts.values())==expected,
                   release_pass=not changed and counts['failed']==0 and counts['blocked']==0 and sum(counts.values())==expected)
    save()
    if summary['local_pass']:verify_evidence(output)
    print(json.dumps({k:v for k,v in summary.items() if k!='sources'},indent=2))
    return 0 if summary['release_pass' if release else 'local_pass'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--release',action='store_true');a=p.parse_args();raise SystemExit(run(a.output,a.release))
