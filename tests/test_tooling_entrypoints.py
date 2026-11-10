"""CLI contracts run original source with outputs confined to fixture roots."""
import json
from pathlib import Path
import runpy
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name', [
    'analyze_neutral_stationary', 'benchmark_rotating_sphere', 'build_plugin',
    'build_site', 'compare_engines', 'compare_examples', 'example_worker',
    'parity_worker', 'preview_site', 'run_examples', 'run_compatibility_matrix',
    'verify_atmospheric_reference', 'verify_general_boundaries',
    'verify_neutral_coupling', 'verify_boundary_transfer', 'verify_cuda',
    'verify_cuda_benchmarks', 'verify_atmospheric_scaling', 'run_upstream_tests',
])
def test_cli_help_exits_successfully_without_creating_outputs(name, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    monkeypatch.setattr(sys, 'argv', [name, '--help'])
    with pytest.raises(SystemExit) as stop:
        runpy.run_path(str(ROOT / 'scripts' / (name + '.py')), run_name='__main__')
    assert stop.value.code == 0
    assert 'usage:' in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def execute_fixture(name, root, initial=None):
    """Keep real code filenames for traceback/coverage while isolating ROOT."""
    source = ROOT / 'scripts' / (name + '.py')
    namespace = {'__name__': '__main__', '__file__': str(source)}
    namespace.update(initial or {})
    original_resolve = Path.resolve
    def fixture_resolve(path, *args, **kwargs):
        return root / 'scripts' / source.name if path == source else original_resolve(path, *args, **kwargs)
    from unittest.mock import patch
    with patch.object(Path, 'resolve', fixture_resolve):
        exec(compile(source.read_text(), str(source), 'exec'), namespace)
    return namespace


@pytest.mark.parametrize('count', [40, 200])
def test_stationary_analysis_keeps_declared_results_and_computes_window_balance(count, tmp_path, monkeypatch):
    from matplotlib import pyplot as plt
    spec = dict(shape=[4,4,12], dx=1., density=1.225, speed=2.,
                neutral_precursor=dict(reference_height_m=10., roughness_length_m=.1))
    ustar=.41*2/np.log1p(100.)
    drive=1.225*ustar**2
    rows=[dict(step=100000+i*500,time=float(i+1),drag=drive,profile=[[2.]*12,[0.]*12,[0.]*12]) for i in range(count)]
    source=tmp_path/'input.json';out=tmp_path/'out/report.json'
    source.write_text(json.dumps(dict(spec=spec,samples=rows,steps=rows[-1]['step'],stationarity_change=.2,drag_relative_error=.3,log_profile_relative_l2=.4,passed=False)))
    monkeypatch.setattr(sys,'argv',['analyze',str(source),'--output',str(out)])
    try:execute_fixture('analyze_neutral_stationary',tmp_path)
    finally:plt.close('all')
    report=json.loads(out.read_text())
    assert not report['final_predeclared_check']['passed']
    assert not report['physical_validation']
    assert len(report['window_sensitivity'])==(1 if count==40 else 3)
    assert all(w['mean_profile_change']==0 for w in report['window_sensitivity'])
    assert report['post_spinup']['momentum_residual_relative_to_drive']<1e-12
    assert out.with_suffix('.png').read_bytes().startswith(b'\x89PNG')


@pytest.mark.parametrize('failure', ['none','numeric','source','device','status','count','shape','iterations','intentional','disappeared'])
def test_example_comparator_rejects_false_or_incompatible_evidence(failure,tmp_path,monkeypatch):
    import copy
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    source=tmp_path/'vendor/lettuce/examples';source.mkdir(parents=True)
    (source/'tiny.py').write_text('# fixture')
    sim=dict(shape=[2,2],iterations=50,velocity_conversion_scale=2.,pressure_conversion_scale=3.,failure_detection_example=failure=='intentional')
    cpu=dict(source='tiny.py',source_sha256='fixture-sha',device='cpu',status='passed',simulations=[sim])
    gpu=copy.deepcopy(cpu);gpu['device']='fixture-accelerator'
    if failure=='source':gpu['source_sha256']='changed'
    if failure=='device':gpu['device']='cpu'
    if failure=='status':gpu['status']='failed'
    if failure=='count':gpu['simulations']=[]
    if failure=='shape':gpu['simulations'][0]['shape']=[4,4]
    if failure=='iterations':gpu['simulations'][0]['iterations']=51
    for device,report in [('cpu',cpu),('gpu',gpu)]:
        folder=tmp_path/device/'tiny.py';folder.mkdir(parents=True)
        (folder/'report.json').write_text(json.dumps(report))
        fields={name:np.ones((2,2)) for name in ('f','rho','u','p')}
        if device=='gpu' and failure in ('numeric','intentional'):fields['u']*=2
        np.savez(folder/'fields_0.npz',**fields)
    if failure=='disappeared':
        import example_inventory
        original=example_inventory.require_complete_reports
        def verify_then_disappear(folder,expected):
            original(folder,expected)
            if folder==tmp_path/'gpu':(folder/'tiny.py/report.json').unlink()
        monkeypatch.setattr(example_inventory,'require_complete_reports',verify_then_disappear)
    out=tmp_path/'parity.json';out.write_text('{"passed":true}')
    monkeypatch.setattr(sys,'argv',['compare','--cpu-dir',str(tmp_path/'cpu'),'--gpu-dir',str(tmp_path/'gpu'),'--output',str(out)])
    if failure in ('source','device','status','count','shape','iterations','disappeared'):
        with pytest.raises(RuntimeError):execute_fixture('compare_examples',tmp_path)
        assert not out.exists(), 'a failed rerun must remove stale success evidence'
    else:
        with pytest.raises(SystemExit) as stop:execute_fixture('compare_examples',tmp_path)
        assert stop.value.code==(1 if failure=='numeric' else 0)
        result=json.loads(out.read_text());assert result['passed'] is (failure!='numeric')
        comparisons=result['examples'][0]['comparisons']
        assert len(comparisons)==(0 if failure=='intentional' else 4)
        if comparisons:
            assert comparisons[2]['atol']==2e-5
            assert comparisons[3]['atol']==pytest.approx(3e-5)
            assert comparisons[2]['passed'] is (failure!='numeric')


@pytest.mark.parametrize('scenario', ['clean','wrong-python','wrong-numpy','foreign-hawa','foreign-lettuce','diagnostic','matching'])
def test_rhino_bootstrap_rejects_contaminated_runtime_and_limits_diagnostic_reload(scenario,tmp_path):
    import builtins
    from types import SimpleNamespace
    package=tmp_path/'package'; modules={}
    if scenario in ('wrong-numpy','diagnostic'):modules['numpy']=SimpleNamespace(__version__='1.26.4')
    else:modules['numpy']=SimpleNamespace(__version__='2.0.2')
    for name in ('hawa','lettuce'):
        if scenario in ('foreign-'+name,'diagnostic','matching'):
            location=package/'python'/name if scenario=='matching' else tmp_path/'other'/name
            modules[name]=SimpleNamespace(__file__=str(location/'__init__.py'))
            modules[name+'.child']=object()
    numpy_before=modules['numpy'];modules['unrelated']=object()
    runtime=SimpleNamespace(version_info=(3,10) if scenario=='wrong-python' else (3,9),path=[],modules=modules)
    environment={'HAWA_DIAGNOSTIC_ALLOW_EXISTING_NUMPY':'1'} if scenario=='diagnostic' else {}
    imported=[];dispatch=object()
    def import_module(name,*args,**kwargs):
        if name=='sys':return runtime
        if name=='os':return SimpleNamespace(environ=environment)
        if name=='hawa.plugin':imported.append(name);return SimpleNamespace(dispatch_json=dispatch)
        return builtins.__import__(name,*args,**kwargs)
    builtins_copy=dict(vars(builtins),__import__=import_module)
    source=ROOT/'plugin/Bootstrap.py'
    scope=dict(__file__=str(source),HAWA_PACKAGE_DIR=str(package),__builtins__=builtins_copy)
    if scenario.startswith(('wrong-','foreign-')):
        with pytest.raises(RuntimeError,match='requires|already loaded'):exec(compile(source.read_text(),str(source),'exec'),scope)
        assert imported==[]
    else:
        exec(compile(source.read_text(),str(source),'exec'),scope)
        assert scope['dispatch_json'] is dispatch and environment['MPLBACKEND']=='Agg'
        assert runtime.path==[str(package/'python')]
    assert modules['numpy'] is numpy_before and 'unrelated' in modules
    if scenario=='diagnostic':assert not any(k=='hawa' or k.startswith('hawa.') or k=='lettuce' or k.startswith('lettuce.') for k in modules)
    if scenario=='matching':assert 'hawa.child' in modules and 'lettuce.child' in modules


@pytest.mark.parametrize('scenario',['ready','run','numpy','python','missing'])
def test_development_gh_component_validates_environment_before_running(scenario,tmp_path):
    import builtins
    from types import SimpleNamespace
    runtime=SimpleNamespace(version_info=(3,10) if scenario=='python' else (3,9),path=[],modules={'numpy':SimpleNamespace(__version__='1.0' if scenario=='numpy' else '2.0.2')})
    (tmp_path/'src').mkdir();(tmp_path/'vendor/lettuce').mkdir(parents=True)
    if scenario=='missing':(tmp_path/'src').rmdir()
    calls=[]
    class Simulation:
        def __init__(self,case,device):calls.append((case,device))
        def advance(self,n):calls.append(n)
        def diagnostics(self):return {'fixture':True,'steps':50}
    def importing(name,*a,**kw):
        if name=='sys':return runtime
        if name=='hawa.engine':return SimpleNamespace(LettuceSimulation=Simulation)
        return builtins.__import__(name,*a,**kw)
    source=ROOT/'scripts/grasshopper_component.py'
    scope=dict(__file__=str(source),repo=str(tmp_path),run=scenario=='run',device='cpu',__builtins__=dict(vars(builtins),__import__=importing))
    if scenario in ('numpy','python','missing'):
        with pytest.raises(RuntimeError,match='Restart|targets|checkout'):exec(compile(source.read_text(),str(source),'exec'),scope)
        assert not calls
    else:
        exec(compile(source.read_text(),str(source),'exec'),scope)
        assert scope['a']==({'fixture':True,'steps':50} if scenario=='run' else {'status':'ready'})
        assert calls==([('tgv3d-bgk','cpu'),50] if scenario=='run' else [])
        assert runtime.path==[str(tmp_path/'vendor/lettuce'),str(tmp_path/'src')]


@pytest.mark.parametrize('failure',['none','diagnostic','parity'])
def test_runtime_verifier_serializes_all_device_rows_and_rejects_failed_fixture_observations(failure,tmp_path,monkeypatch):
    import torch
    import hawa.backends
    import hawa.lbm
    monkeypatch.setattr(sys,'path',list(sys.path))
    monkeypatch.setattr(torch.backends.mps,'is_available',lambda:True)
    monkeypatch.setattr(torch.cuda,'is_available',lambda:True)
    monkeypatch.setattr(hawa.backends,'select_backend',lambda device:device)
    calls=[]
    class Simulation:
        def __init__(self,device):
            self.device=device;self.steps=0
            self.f=torch.ones((2,2))*(2 if failure=='parity' and device=='mps' else 1)
        def advance(self,steps):self.steps+=steps;calls.append((self.device,steps));return self
        def diagnostics(self):return dict(passed=not(failure=='diagnostic' and self.device=='mps'),fixture=True,steps=self.steps)
    monkeypatch.setattr(hawa.lbm,'VortexSimulation',Simulation)
    out=tmp_path/'results/headless-verification.json'
    if failure=='diagnostic':
        with pytest.raises(RuntimeError,match='Verification failed on mps'):execute_fixture('verify_runtime',tmp_path)
        assert not out.exists()
    elif failure=='parity':
        with pytest.raises(AssertionError):execute_fixture('verify_runtime',tmp_path)
        assert not out.exists()
    else:
        execute_fixture('verify_runtime',tmp_path)
        report=json.loads(out.read_text())
        assert set(report['reports'])=={'cpu','mps','cuda:0','auto'}
        assert all(r['fixture'] and r['steps']==200 for r in report['reports'].values())
        assert all(value==0 for value in report['max_population_difference_from_cpu'].values())
        assert calls==[(device,steps) for device in ('cpu','mps','cuda:0','auto') for steps in (75,125)]


@pytest.mark.parametrize('scenario',['pass','numeric','rejected','late-rejection','resume'])
def test_stationarity_runner_reports_rejections_and_resumed_history_without_relaxing_targets(scenario,tmp_path,monkeypatch):
    from types import SimpleNamespace
    import hawa.plugin
    from hawa.atmosphere import neutral_profile
    target=1.225*(.41*5/np.log1p(6/.01))**2
    profile=neutral_profile(np.arange(12)+.5,[5.,0,0],6.,.01).T
    if scenario=='numeric':profile*=2
    class Session:
        flow=SimpleNamespace(i=0,units=SimpleNamespace(convert_time_to_pu=lambda n:n*.01))
        quality=dict(status='rejected' if scenario=='rejected' else 'within-tested-envelope')
        solver=SimpleNamespace(rough_floor=SimpleNamespace(report=dict(mean_traction_on_fluid_pa=[-target,0,0])))
        def advance(self,n):
            self.flow.i+=n
            if scenario=='late-rejection' and self.flow.i>20000:self.quality['status']='rejected'
        def fields(self):return dict(velocity=np.broadcast_to(profile[:,None,None,:],(3,2,2,12)))
    session=Session();calls=[]
    out=tmp_path/'stationary.json'
    def dispatch(request):
        calls.append(request)
        if request['op']=='create':return dict(session='fixture')
        if request['op']=='load':session.flow.i=10000
    monkeypatch.setattr(hawa.plugin,'dispatch',dispatch)
    monkeypatch.setattr(hawa.plugin,'SESSIONS',{'fixture':session})
    args=['stationary','--steps','20500' if scenario=='late-rejection' else '20000','--device','cpu','--output',str(out)]
    if scenario=='resume':
        old=[dict(step=i*500,time=i*5.,profile=profile.tolist(),uw=[0]*12,drag=target,quality='within-tested-envelope') for i in range(1,21)]
        old.append(dict(step=999999,invalid=True))
        out.write_text(json.dumps(dict(samples=old)));args.append('--resume')
    monkeypatch.setattr(sys,'argv',args)
    if scenario in ('numeric','rejected','late-rejection'):
        with pytest.raises(SystemExit) as stop:execute_fixture('verify_neutral_stationary',tmp_path)
        assert stop.value.code==1
    else:execute_fixture('verify_neutral_stationary',tmp_path)
    result=json.loads(out.read_text())
    assert result['passed'] is (scenario in ('pass','resume'))
    assert result['targets']==dict(stationarity=.02,drag=.05,profile=.05)
    assert result['physical_validation'] is False
    assert result['steps']==(500 if scenario=='rejected' else 20500 if scenario=='late-rejection' else 20000)
    assert len(result['samples'])==(1 if scenario=='rejected' else 41 if scenario=='late-rejection' else 40)
    assert calls[-1]==dict(op='close',session='fixture')
    assert any(c['op']=='save' for c in calls) is (scenario!='rejected')
    if scenario=='numeric':assert result['log_profile_relative_l2']==pytest.approx(1.)
    if scenario=='rejected':assert result['samples'][0]['quality']=='rejected'


@pytest.mark.parametrize('existing',[False,True])
def test_reference_environment_bootstrap_pins_oracle_requirements_without_launching_installers(existing,tmp_path,monkeypatch):
    import subprocess
    import os
    interpreter=tmp_path/'.venv-reference'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if existing:interpreter.parent.mkdir(parents=True);interpreter.touch()
    calls=[]
    monkeypatch.setattr(subprocess,'run',lambda command,**kwargs:calls.append((command,kwargs)))
    execute_fixture('bootstrap_reference',tmp_path)
    assert len(calls)==(1 if existing else 2)
    if not existing:assert calls[0][0]==['uv','venv','--python','3.12',str(tmp_path/'.venv-reference')]
    assert calls[-1][0]==['uv','pip','install','--python',str(interpreter),'-r',str(tmp_path/'requirements/reference-py312.txt')]
    assert all(kw==dict(check=True,cwd=tmp_path) for _,kw in calls)


def test_site_build_copies_nested_assets_and_generated_palette_svg(tmp_path,monkeypatch):
    import xml.etree.ElementTree as ET
    palette=tmp_path/'vendor/monad_system';palette.mkdir(parents=True)
    (palette/'colors.json').write_bytes((ROOT/'vendor/monad_system/colors.json').read_bytes())
    assets=tmp_path/'site/assets';assets.mkdir(parents=True)
    (assets.parent/'index.html').write_text('<h1>Fixture</h1>')
    execute_fixture('sync_design_tokens',tmp_path)
    svg=ET.fromstring((assets/'hawa.svg').read_text())
    ui=json.loads((palette/'colors.json').read_text())['Default_Colors']['General_UI_Colors']
    assert svg.find('{http://www.w3.org/2000/svg}rect').attrib['fill']==ui['Background']['hex']
    out=tmp_path/'published'
    monkeypatch.setattr(sys,'argv',['site','--output',str(out)])
    execute_fixture('build_site',tmp_path)
    assert (out/'.nojekyll').is_file()
    assert (out/'index.html').read_text()=='<h1>Fixture</h1>'
    assert (out/'assets/hawa.svg').read_bytes()==(assets/'hawa.svg').read_bytes()


@pytest.mark.parametrize('scenario',['pass','failed','numpy','override'])
def test_rhino_lettuce_script_checks_dependencies_and_writes_failed_diagnostics(scenario,tmp_path,monkeypatch):
    import hawa.engine
    calls=[]
    class Simulation:
        def __init__(self,case,device):calls.append((case,device))
        def advance(self,steps):calls.append(steps);return self
        def diagnostics(self):return dict(passed=scenario!='failed',fixture=True)
        def snapshot(self):return dict(f=np.ones((2,2)))
    monkeypatch.setattr(hawa.engine,'LettuceSimulation',Simulation)
    monkeypatch.setattr(sys,'path',list(sys.path))
    monkeypatch.setattr(np,'__version__','1.0' if scenario in ('numpy','override') else '2.0.2')
    initial=dict(HAWA_CASE='fixture-case',HAWA_DEVICE='cpu',HAWA_ALLOW_EXISTING_NUMPY=scenario=='override')
    if scenario in ('failed','numpy'):
        with pytest.raises(RuntimeError,match='failed|Restart Rhino'):execute_fixture('rhino_lettuce',tmp_path,initial)
    else:execute_fixture('rhino_lettuce',tmp_path,initial)
    out=tmp_path/'results/rhino-lettuce'
    if scenario=='numpy':
        assert not calls and not out.exists()
    else:
        assert calls==[('fixture-case','cpu'),10,40]
        report=json.loads((out/'report.json').read_text())
        assert report['passed'] is (scenario!='failed') and report['fixture']
        assert report['strict_dependency_versions'] is (scenario!='override')
        with np.load(out/'fields.npz') as archive:np.testing.assert_array_equal(archive['f'],np.ones((2,2)))


def test_native_glyph_generation_produces_svg_png_and_multisize_icon(tmp_path):
    import xml.etree.ElementTree as ET
    from PIL import Image
    (tmp_path/'plugin/Hawa.Rhino').mkdir(parents=True)
    scope=execute_fixture('create_native_icons',tmp_path)
    out=tmp_path/'plugin/Hawa.Rhino/Assets'
    assert len(list(out.glob('*.png')))==len(scope['glyphs'])==11
    for name,paths in scope['glyphs'].items():
        with Image.open(out/(name+'.png')) as im:
            assert im.size==(24,24) and im.mode=='RGBA'
            assert np.asarray(im)[...,3].max()==255
        svg=ET.fromstring((out/(name+'.svg')).read_text())
        assert len(svg.findall('{http://www.w3.org/2000/svg}polyline'))==len(paths)
    with Image.open(out/'hawa.ico') as icon:
        assert icon.ico.sizes()=={(16,16),(24,24),(32,32),(48,48),(64,64)}
