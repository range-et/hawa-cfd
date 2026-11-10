"""Developer-runner evidence contracts; synthetic observations are not qualification."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import lettuce as lt
import numpy as np
import pytest
import torch

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('failure', ['none','operator','source','inventory'])
def test_g6_orchestrator_preserves_blocked_failed_and_incomplete_rows(tmp_path,monkeypatch,failure):
    m=load('run_compatibility_matrix')
    topology=[dict(id='faces/reject',expected=False)]
    rows=[dict(id='solver/accept',expected=True)]
    refinement=[dict(id='refinement/accept',expected=True)]
    fields=[dict(id='field/reject',expected=False)]
    monkeypatch.setattr(m,'topologies',lambda:iter(topology))
    monkeypatch.setattr(m,'combinations',lambda:iter(rows));monkeypatch.setattr(m,'refinements',lambda:iter(refinement))
    monkeypatch.setattr(m,'field_cases',lambda:iter(fields));monkeypatch.setattr(m,'collection_cases',lambda:iter([]));monkeypatch.setattr(m,'nesting_cases',lambda:iter([]))
    monkeypatch.setattr(m,'DEVICES',['cpu','cuda:0'])
    monkeypatch.setattr(m.torch.cuda,'is_available',lambda:False)
    monkeypatch.setattr(m.torch.backends.mps,'is_available',lambda:False)
    assert m.available('cpu') and not m.available('mps') and not m.available('cuda:0')
    monkeypatch.setattr(m,'make_topology',lambda row:row)
    monkeypatch.setattr(m,'make_combination',lambda row,fixtures:row)
    monkeypatch.setattr(m,'make_refinement',lambda row,fixtures:row)
    def reject(*args):raise ValueError('declared unsupported contract')
    monkeypatch.setattr(m,'check_case',reject);monkeypatch.setattr(m,'exercise_field',reject)
    class Session:
        def __init__(self,spec,device):self.flow=SimpleNamespace(i=0);self.quality=dict(finite=True,positive_density=True)
        def advance(self,steps):
            if failure=='operator':raise RuntimeError('injected operator failure')
            self.flow.i+=steps
        def fields(self):return dict(velocity=np.zeros((3,2,2,2)))
    monkeypatch.setattr(m,'Session',Session)
    def refined(request,checkpoint):checkpoint(0);return dict(relative_mass_change=0.)
    monkeypatch.setattr(m,'run_refined',refined)
    hashes=iter([{'a':'same'},{'a':'changed' if failure=='source' else 'same'}])
    monkeypatch.setattr(m,'source_hashes',lambda:next(hashes));monkeypatch.setattr(m,'environment',lambda:dict(device='fixture'))
    monkeypatch.setattr(m,'verify_examples',lambda path:dict(nodes=54))
    monkeypatch.setattr(m,'expected_rows',lambda:list(range(7 if failure=='inventory' else 6)))
    verified=[];monkeypatch.setattr(m,'verify_evidence',lambda path:verified.append(path))
    out=tmp_path/'run'
    assert m.run(out)==(0 if failure=='none' else 1)
    report=json.loads((out/'summary.json').read_text());recorded=[json.loads(line) for line in (out/'rows.jsonl').read_text().splitlines()]
    assert report['state']=='complete' and report['recorded_rows']==6
    assert report['counts']['blocked']==2 and report['release_pass'] is False
    assert report['rows_sha256']==hashlib.sha256((out/'rows.jsonl').read_bytes()).hexdigest()
    assert [r['status'] for r in recorded if r['id'].endswith('/cuda:0')]==['blocked','blocked']
    assert bool(verified)==(failure=='none')
    if failure=='operator':assert report['counts']['failed']==1 and 'injected operator failure' in report['failures'][0]['error']
    if failure=='source':assert report['sources_changed_during_run']
    if failure=='inventory':assert report['expected_rows']==7
    with pytest.raises(FileExistsError):m.run(out)


def test_notebook_worker_executes_driver_and_records_magic_omissions(tmp_path,monkeypatch):
    m=load('example_worker')
    from matplotlib import pyplot as plt
    source=tmp_path/'source';source.mkdir();(source/'profile_reference_data').mkdir()
    (source/'profile_reference_data/data.txt').write_text('fixture')
    (source/'driver.py').write_text('''import sys
from matplotlib import pyplot as plt
import lettuce as lt
flow=lt.TaylorGreenVortex(lt.Context(),resolution=[8,8],reynolds_number=100,mach_number=.05)
sim=lt.Simulation(flow,lt.BGKCollision(flow.units.relaxation_parameter_lu),[])
plt.plot([0,1]);plt.savefig('suppressed.png');plt.show()
assert sys.argv[1:]==['quoted value']
sim(500)
''')
    notebook=dict(cells=[dict(cell_type='markdown',source=['ignored']),dict(cell_type='code',source=['%matplotlib inline\n','!echo ignored\n',"%run driver.py 'quoted value'\n",'print("after driver")\n'])])
    (source/'tiny.ipynb').write_text(json.dumps(notebook));output=tmp_path/'out'
    monkeypatch.chdir(tmp_path);monkeypatch.setattr(sys,'path',list(sys.path));monkeypatch.setattr(sys,'argv',['worker','tiny.ipynb','--source-root',str(source),'--output',str(output)])
    for obj,attr in [(np.random,'seed'),(lt.Context,'__init__'),(lt.Simulation,'__init__'),(lt.Simulation,'__call__'),(lt.BreakableSimulation,'__call__'),(plt,'show'),(plt,'savefig')]:monkeypatch.setattr(obj,attr,getattr(obj,attr))
    assert m.main()==0
    report=json.loads((output/'report.json').read_text())
    assert report['budget_reached'] and report['simulations'][0]['iterations']==50
    assert report['notebook_magics_not_executed']==['%matplotlib inline','!echo ignored']
    assert report['source_sha256']==hashlib.sha256((source/'tiny.ipynb').read_bytes()).hexdigest()
    assert not (output/'suppressed.png').exists()
    assert (output/'profile_reference_data/data.txt').read_text()=='fixture'
    assert 'after driver' in (output/'stdout.txt').read_text()


def test_aij_measurements_geometry_and_insufficient_window_are_not_a_pass(tmp_path,monkeypatch):
    m=load('verify_atmospheric_reference')
    approach,observations=m.measurements()
    assert approach.shape[1]>=2 and observations.shape[1]>=7 and np.isfinite(approach).all()
    spec=m.case(1)
    assert spec['shape']==[15,8,8] and spec['dx']==.1
    assert spec['boundary_set']['patches'][0]['condition']['type']=='velocity'
    out=tmp_path/'reference'
    monkeypatch.setattr(sys,'argv',['reference','--cells','1','--steps','0','--device','cpu','--output',str(out)])
    assert m.main()==1
    result=json.loads((out/'result.json').read_text())
    assert result['steps']==0 and not result['passed'] and result['history']==[]
    assert 'sufficient averaging' in result['reason']


@pytest.mark.parametrize('passes',[True,False])
def test_general_boundary_driver_retains_failed_cases(tmp_path,monkeypatch,passes):
    m=load('verify_general_boundaries');seen=[]
    def run(n,kind,device):seen.append((n,kind,device));return dict(passed=passes,n=n,kind=kind)
    monkeypatch.setattr(m,'run',run);out=tmp_path/'boundary'
    monkeypatch.setattr(sys,'argv',['boundary','--grids','9','--output',str(out)])
    if passes:m.main()
    else:
        with pytest.raises(SystemExit) as failure:m.main()
        assert failure.value.code==1
    report=json.loads((out/'report.json').read_text())
    assert seen==[(9,'couette','cpu'),(9,'poiseuille','cpu')]
    assert report['criteria']==dict(relative_l2=.04,wall_error_m_s=5e-6,relative_mass_change=.02)
    assert all(r['passed'] is passes for r in report['cases'])


@pytest.mark.parametrize('kind', ['couette','poiseuille'])
def test_general_boundary_run_keeps_declared_error_criteria(kind):
    r=load('verify_general_boundaries').run(5,kind,'cpu')
    assert r['kind']==kind and r['n']==5 and r['steps']>0
    assert r['passed']==(r['relative_l2']<.04 and r['wall_error_m_s']<5e-6 and r['relative_mass_change']<.02)
    assert np.isfinite(r['relative_l2']) and r['wall_error_m_s']<5e-6


@pytest.mark.parametrize('passes',[True,False])
def test_neutral_coupling_driver_preserves_numeric_failures(tmp_path,monkeypatch,passes):
    m=load('verify_neutral_coupling')
    monkeypatch.setattr(m,'analytic',lambda n:dict(nz=n,passed=True))
    def pulse(n):
        values=np.zeros((3,n,8,8))
        if n==32 and not passes:values[1]=.021
        return values,dict(mass_budget_residual_lu=0.)
    monkeypatch.setattr(m,'pulse',pulse);out=tmp_path/'coupling.json'
    monkeypatch.setattr(sys,'argv',['coupling','--output',str(out)])
    if passes:m.main()
    else:
        with pytest.raises(SystemExit) as failure:m.main()
        assert failure.value.code==1
    report=json.loads(out.read_text())
    assert report['passed'] is passes and report['physical_validation'] is False
    assert report['pulse']['criterion']==.1
    assert report['pulse']['relative_linf']==pytest.approx(0 if passes else .105)


def test_neutral_analytic_and_pulse_controls_use_finite_real_cpu_fields():
    m=load('verify_neutral_coupling')
    r=m.analytic(12)
    assert r['steps']==2000 and r['passed']==(r['profile_relative_l2']<=.001 and r['drag_error']<=.001)
    fields,budget=m.pulse(32)
    assert fields.shape==(3,32,8,8) and np.isfinite(fields).all()
    assert abs(budget['mass_budget_residual_lu'])<1e-8
