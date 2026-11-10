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


@pytest.mark.parametrize('rejected',[False,True])
def test_aij_reporting_preserves_rejection_and_fixed_averaging_criteria(tmp_path,monkeypatch,rejected):
    m=load('verify_atmospheric_reference')
    observations=np.array([[.1,0,.2,1.,0,0,.01],[0,0,.05,0,0,0,.01]])
    monkeypatch.setattr(m,'measurements',lambda:(np.array([[.1,1.]]),observations))
    calls=[]
    class Session:
        def __init__(self,spec,device):
            self.flow=SimpleNamespace(i=0,units=SimpleNamespace(convert_time_to_pu=lambda n:n*.01),f=torch.ones((1,)))
            self.quality=dict(status='rejected' if rejected else 'within-tested-envelope',max_lattice_mach=.02,max_density_deviation=.001)
            self.solver=SimpleNamespace(external_links=SimpleNamespace(report=dict(mass_budget_residual_lu=0.)))
            self.shape=spec['shape']
        def advance(self,n):self.flow.i+=n;calls.append(n)
        def fields(self):return dict(velocity=np.ones((3,)+tuple(self.shape)),density=np.ones(self.shape),pressure=np.zeros(self.shape),solid=np.zeros(self.shape,bool))
    monkeypatch.setattr(m,'Session',Session)
    def sample(fields,spec,points,mask):
        assert points.tolist()==[[.1,0,.2]] and not mask.any()
        return np.array([[1.,0,0]]),np.zeros(1),dict(fixture=True)
    monkeypatch.setattr(m,'sample_parent',sample)
    out=tmp_path/'aij'
    monkeypatch.setattr(sys,'argv',['reference','--cells','1','--steps','1000','--inflow','log','--top','slip','--output',str(out)])
    assert m.main()==int(rejected)
    report=json.loads((out/'result.json').read_text())
    assert report['passed'] is not rejected
    if rejected:
        assert report['steps']==100 and len(calls)==1
        assert (out/'latest-state.npz').exists()
        assert report['reason']=='Numerical envelope failed before sufficient averaging'
    else:
        assert report['steps']==1000 and len(calls)==10
        assert report['excluded_inside_model']==1 and report['points']==1
        assert report['thresholds']==dict(streamwise_hit_rate_min=.66,relative_error_or_absolute=[.25,.085],stationarity_max=.05)
        assert report['sampling']==dict(fixture=True)
        assert (out/'samples.npz').exists() and (out/'progress.json').exists()
        assert report['stationarity_change']==0 and report['hit_rate_components']==[1.,1.,1.]


@pytest.mark.parametrize('failure',['none','topology','field','solver-reject','nesting-reject','nesting-error'])
def test_g6_orchestrator_records_each_operator_failure_without_losing_rows(tmp_path,monkeypatch,failure):
    m=load('run_compatibility_matrix')
    monkeypatch.setattr(m,'DEVICES',['cpu','cuda:0'])
    monkeypatch.setattr(m,'available',lambda device:device=='cpu')
    monkeypatch.setattr(m,'topologies',lambda:iter([dict(id='faces/valid',expected=True)]))
    monkeypatch.setattr(m,'combinations',lambda:iter([]));monkeypatch.setattr(m,'refinements',lambda:iter([]))
    monkeypatch.setattr(m,'field_cases',lambda:iter([dict(id='field/valid',expected=True)]))
    monkeypatch.setattr(m,'collection_cases',lambda:iter([dict(id='collection/valid',expected=True)]))
    monkeypatch.setattr(m,'nesting_cases',lambda:iter([dict(id='nesting/valid',expected=failure!='nesting-reject')]))
    monkeypatch.setattr(m,'make_topology',lambda row:row)
    def check(spec):
        if failure=='topology':raise RuntimeError('topology fixture error')
    monkeypatch.setattr(m,'check_case',check)
    class Session:
        def __init__(self,*args):
            if failure=='solver-reject':raise ValueError('solver fixture rejection')
            self.flow=SimpleNamespace(i=0);self.quality=dict(finite=True,positive_density=True)
        def advance(self,n):self.flow.i=n
        def fields(self):return dict(velocity=np.zeros((3,1,1,1)))
    monkeypatch.setattr(m,'Session',Session)
    def field(*args):
        if failure=='field':raise RuntimeError('field fixture error')
    monkeypatch.setattr(m,'exercise_field',field)
    monkeypatch.setattr(m,'exercise_collection',lambda *args:None)
    def nesting(*args):
        if failure=='nesting-reject':raise ValueError('nesting fixture rejection')
        if failure=='nesting-error':raise RuntimeError('nesting fixture error')
    monkeypatch.setattr(m,'exercise_nesting',nesting)
    monkeypatch.setattr(m,'source_hashes',lambda:{'fixture':'stable'})
    monkeypatch.setattr(m,'environment',lambda:{'fixture':True})
    monkeypatch.setattr(m,'verify_examples',lambda path:{'fixture':True})
    monkeypatch.setattr(m,'expected_rows',lambda:list(range(7)))
    monkeypatch.setattr(m,'verify_evidence',lambda path:None)
    out=tmp_path/'gate'
    assert m.run(out,release=True)==1  # Unavailable accelerator always blocks release.
    report=json.loads((out/'summary.json').read_text())
    assert report['recorded_rows']==7 and report['counts']['blocked']==2
    assert report['counts']['failed']==(0 if failure in ('none','nesting-reject') else 1)
    if report['failures']:assert 'fixture' in report['failures'][0]['error']
    assert report['local_pass'] is (failure in ('none','nesting-reject'))


@pytest.mark.parametrize('scenario',['full','error','nonfinite','expected-nonfinite','budget','subclass'])
def test_original_example_worker_reports_budget_and_failure_semantics(tmp_path,monkeypatch,scenario):
    m=load('example_worker')
    from matplotlib import pyplot as plt
    source=tmp_path/'source';source.mkdir()
    name='FailingTGV.py' if scenario=='expected-nonfinite' else 'tiny.py'
    code='''import numpy as np
import torch
import lettuce as lt
np.random.seed()
flow=lt.TaylorGreenVortex(lt.Context(),resolution=[8,8],reynolds_number=100,mach_number=.05)
flow.mask=torch.zeros((8,8),dtype=torch.bool)
'''
    if scenario=='error':code='raise ValueError("fixture execution failure")'
    else:
        if scenario=='subclass':
            code+='''class OwnSimulation(lt.Simulation):
    def __call__(self,n):return super().__call__(n)
sim=OwnSimulation(flow,lt.BGKCollision(flow.units.relaxation_parameter_lu),[])
'''
        else:code+='sim=lt.Simulation(flow,lt.BGKCollision(flow.units.relaxation_parameter_lu),[])\n'
        if scenario in ('nonfinite','expected-nonfinite'):code+='flow.f.fill_(float("nan"))\n'
        elif scenario=='budget':code+='sim(50)\nsim(1)\n'
        else:code+='sim(2)\n'
    (source/name).write_text(code);out=tmp_path/'out'
    argv=['worker',name,'--source-root',str(source),'--output',str(out)]
    if scenario=='full':argv.append('--full')
    monkeypatch.chdir(tmp_path);monkeypatch.setattr(sys,'path',list(sys.path));monkeypatch.setattr(sys,'argv',argv)
    for obj,attr in [(np.random,'seed'),(lt.Context,'__init__'),(lt.Simulation,'__init__'),(lt.Simulation,'__call__'),(lt.BreakableSimulation,'__call__'),(plt,'show'),(plt,'savefig')]:monkeypatch.setattr(obj,attr,getattr(obj,attr))
    assert m.main()==int(scenario in ('error','nonfinite'))
    report=json.loads((out/'report.json').read_text())
    if scenario=='error':
        assert report['status']=='failed' and 'fixture execution failure' in report['error']
        assert 'ValueError' in report['traceback'] and report['simulations']==[]
    else:
        observed=report['simulations'][0]
        assert observed['finite'] is (scenario not in ('nonfinite','expected-nonfinite'))
        assert observed['failure_detection_example'] is (scenario=='expected-nonfinite')
        assert (out/'mask_0.npy').exists() and (out/'fields_0.npz').exists()
        if scenario=='nonfinite':assert report['error']=='Nonfinite populations'
        if scenario=='budget':assert observed['iterations']==50 and report['budget_reached']
        if scenario=='full':assert report['profile']=='full' and observed['iterations']==2
        if scenario=='subclass':assert observed['iterations']==2


@pytest.mark.parametrize('scenario',['upstream','commit','fork','source','backport-source','python','fallback','known-error','unexpected-error','nonfinite','density'])
def test_parity_worker_enforces_source_runtime_and_numerical_evidence(tmp_path,monkeypatch,scenario):
    import hawa.cases
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    m=load('parity_worker')
    vendor=tmp_path/'vendor/lettuce';(vendor/'lettuce').mkdir(parents=True)
    original=b'# exact fixture source\n';(vendor/'lettuce/__init__.py').write_bytes(original)
    manifest=dict(commit='pinned-fixture',source_sha256={'lettuce/__init__.py':hashlib.sha256(original).hexdigest()})
    (vendor/'upstream.json').write_text(json.dumps(manifest))
    external=tmp_path/'oracle/lettuce';external.mkdir(parents=True)
    (external/'__init__.py').write_bytes(b'# modified\n' if scenario in ('source','backport-source') else original)
    monkeypatch.setattr(m,'ROOT',tmp_path)
    monkeypatch.setattr(lt,'__file__',str((vendor/'lettuce' if scenario=='fork' else external)/'__init__.py'))
    direct=json.dumps(dict(vcs_info=dict(commit_id='wrong' if scenario=='commit' else 'pinned-fixture')))
    monkeypatch.setattr(m,'distribution',lambda name:SimpleNamespace(read_text=lambda file:direct,metadata={'Name':name},version='fixture'))
    if scenario=='python':monkeypatch.setattr(m,'sys',SimpleNamespace(version_info=(3,10)))
    monkeypatch.setenv('PYTORCH_ENABLE_MPS_FALLBACK','1' if scenario=='fallback' else '0')
    name='cavity2d-bgk' if scenario=='known-error' else 'fixture'
    monkeypatch.setattr(hawa.cases,'CASES',{name:None})
    def make_case(name,context):
        if scenario=='known-error':raise TypeError("missing 1 required positional argument: 'velocity'")
        if scenario=='unexpected-error':raise TypeError('unexpected fixture signature')
        flow=lt.TaylorGreenVortex(context,[8,8],100,.05)
        if scenario=='nonfinite':flow.f.fill_(float('nan'))
        if scenario=='density':flow.f.fill_(-1.)
        return flow,lt.Simulation(flow,lt.BGKCollision(flow.units.relaxation_parameter_lu),[])
    monkeypatch.setattr(hawa.cases,'make_case',make_case)
    role='backport' if scenario in ('backport-source','python','fallback') else 'upstream'
    out=tmp_path/'out'
    if scenario not in ('upstream','known-error'):
        with pytest.raises((RuntimeError,TypeError)):m.run(role,'mps' if scenario=='fallback' else 'cpu',out)
        assert not (out/'metadata.json').exists()
    else:
        result=m.run(role,'cpu',out)
        assert result['passed'] and result['upstream_commit']=='pinned-fixture'
        if scenario=='known-error':assert result['cases'][name]['status']=='known-upstream-error'
        else:
            assert result['cases'][name]['steps']==50
            with np.load(out/(name+'.npz')) as fields:assert set(fields.files)=={str(step)+'_'+field for step in (0,1,10,50) for field in ('f','rho','u','p')}
