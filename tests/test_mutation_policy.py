"""Mutation evidence must fail closed on incomplete, changed or unexpected results."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
# Load each tool under the module name its study imports it by (tools/mutation is an import root).
spec=importlib.util.spec_from_file_location('check_results',ROOT/'tools/mutation/check_results.py')
policy_tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy_tool)
spec=importlib.util.spec_from_file_location('mutmut3',ROOT/'tools/mutation/mutmut3.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

KILLED_DIFF='--- src/hawa/cli.py\n+++ src/hawa/cli.py\n-    return 1\n+    return 2'
SURVIVOR_DIFF='--- src/hawa/cli.py\n+++ src/hawa/cli.py\n-    x = a\n+    x = None'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write_mutants(output,rows):
    (output/'mutants.json').write_text(json.dumps(
        {name:dict(path='src/hawa/cli.py',exit_code=code,diff=diff) for name,(code,diff) in rows.items()}))


@pytest.fixture
def evidence(tmp_path):
    root=tmp_path/'checkout';output=tmp_path/'evidence';output.mkdir()
    sources={}
    for name in ('src/hawa/cli.py','tests/test_cli.py'):
        for base in (root,output):
            path=base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture\n')
        sources[name]=policy_tool.digest(root/name)
    (output/'working-source-before.sha256').write_text('unchanged')
    (output/'working-source-after.sha256').write_text('unchanged')
    (output/'tool.txt').write_text('mutmut==3.7.0\n')
    (output/'collected.txt').write_text('tests/test_cli.py::test_one\n')
    (output/'control.xml').write_text('<testsuite><testcase name="test_one"/></testsuite>')
    write_mutants(output,{'hawa.cli.x_main__mutmut_1':(1,KILLED_DIFF),'hawa.cli.x_main__mutmut_2':(0,SURVIVOR_DIFF)})
    (output/'mutation-exit.txt').write_text('0\n')
    policy=dict(tool='mutmut==3.7.0',mutants=2,scope='CLI fixture',control_test_files=['tests/test_cli.py'],
                inventory_sha256=sha('hawa.cli.x_main__mutmut_1\nhawa.cli.x_main__mutmut_2'),sources=sources,
                reviewed_survivors={'hawa.cli.x_main__mutmut_2':dict(status='survived',diff_sha256=sha(SURVIVOR_DIFF),
                                                                     reason='fixture equivalent')})
    return root,output,policy


def test_exact_reviewed_inventory_passes_without_hiding_survivors(evidence):
    root,output,policy=evidence
    result=policy_tool.verify(output,policy,root)
    assert result['mutants']==2 and result['killed']==1 and result['reviewed_survivors']==1
    assert result['control_tests']==1 and result['policy_pass'] and result['scope']=='CLI fixture'


def test_reviewed_no_tests_mutant_is_reported_as_a_survivor_not_a_kill(evidence):
    root,output,policy=evidence
    write_mutants(output,{'hawa.cli.x_main__mutmut_1':(1,KILLED_DIFF),'hawa.cli.x_main__mutmut_2':(33,SURVIVOR_DIFF)})
    with pytest.raises(ValueError,match='Survivors changed'):
        policy_tool.verify(output,policy,root)
    policy['reviewed_survivors']['hawa.cli.x_main__mutmut_2']['status']='no tests'
    result=policy_tool.verify(output,policy,root)
    assert result['killed']==1 and result['reviewed_survivors']==1


# mutmut 3.7.0 itself reports exit 3 (pytest internal error) as killed; the checker must not.
@pytest.mark.parametrize('code',[3,2,4,5,34,35,36,37,24,-24,152,255,-9,-11,None])
def test_errors_timeouts_and_unchecked_mutants_are_never_kills(evidence,code):
    root,output,policy=evidence
    write_mutants(output,{'hawa.cli.x_main__mutmut_1':(code,KILLED_DIFF),'hawa.cli.x_main__mutmut_2':(0,SURVIVOR_DIFF)})
    with pytest.raises(ValueError,match='Timeout, error, suspicious or unchecked mutant: hawa.cli.x_main__mutmut_1'):
        policy_tool.verify(output,policy,root)


REJECTIONS={'source':'snapshot changed: src/hawa/cli.py','copy':'snapshot changed: src/hawa/cli.py',
    'during':'changed during','tool':'tool differs','missing_control':'control tests',
    'failed_control':'did not pass','error_control':'did not pass','skipped_control':'did not pass',
    'exit':'did not complete','missing_mutant':'inventory changed','added_mutant':'inventory changed',
    'renamed_mutant':'inventory changed','unknown_survivor':'Survivors changed','diff':'Survivors changed',
    'no_reason':'no reason: hawa.cli.x_main__mutmut_2'}


@pytest.mark.parametrize('change',sorted(REJECTIONS))
def test_incomplete_or_changed_mutation_evidence_is_rejected(evidence,change):
    root,output,policy=evidence
    if change=='source':(root/'src/hawa/cli.py').write_text('changed')
    elif change=='copy':(output/'src/hawa/cli.py').write_text('changed')
    elif change=='during':(output/'working-source-after.sha256').write_text('changed')
    elif change=='tool':(output/'tool.txt').write_text('mutmut==3.8.1\n')
    elif change=='missing_control':(output/'collected.txt').write_text('tests/test_cli.py::other\n')
    elif change.endswith('_control'):
        tag=change.split('_')[0].replace('failed','failure')
        (output/'control.xml').write_text('<testsuite><testcase name="test_one"><'+tag+'/></testcase></testsuite>')
    elif change=='exit':(output/'mutation-exit.txt').write_text('1')
    elif change=='no_reason':policy['reviewed_survivors']['hawa.cli.x_main__mutmut_2']['reason']=' '
    else:
        rows={'hawa.cli.x_main__mutmut_1':(1,KILLED_DIFF),'hawa.cli.x_main__mutmut_2':(0,SURVIVOR_DIFF)}
        if change=='missing_mutant':del rows['hawa.cli.x_main__mutmut_1']
        elif change=='added_mutant':rows['hawa.cli.x_main__mutmut_3']=(1,KILLED_DIFF)
        elif change=='renamed_mutant':rows['hawa.cli.x_run__mutmut_1']=rows.pop('hawa.cli.x_main__mutmut_1')
        elif change=='unknown_survivor':rows['hawa.cli.x_main__mutmut_1']=(0,KILLED_DIFF)
        elif change=='diff':rows['hawa.cli.x_main__mutmut_2']=(0,SURVIVOR_DIFF+' ')
        write_mutants(output,rows)
    with pytest.raises(ValueError,match=REJECTIONS[change]):policy_tool.verify(output,policy,root)


def test_policy_cli_reports_exact_verifier_result(evidence,monkeypatch,capsys):
    root,output,policy=evidence
    # Keep real verification and explicitly supply the synthetic checkout root.
    real=policy_tool.verify
    monkeypatch.setattr(policy_tool,'verify',lambda directory,config:real(directory,config,root))
    path=output/'policy.json';path.write_text(json.dumps(policy))
    assert policy_tool.main([str(output),'--policy',str(path)])==0
    assert json.loads(capsys.readouterr().out)['reviewed_survivors']==1


def test_reviewed_all_killed_inventory_passes(evidence):
    root,output,policy=evidence
    write_mutants(output,{'hawa.cli.x_main__mutmut_1':(1,KILLED_DIFF),'hawa.cli.x_main__mutmut_2':(1,SURVIVOR_DIFF)})
    policy['reviewed_survivors']={}
    result=policy_tool.verify(output,policy,root)
    assert result['killed']==2 and result['reviewed_survivors']==0


def test_draft_keeps_reasons_only_for_unchanged_survivor_diffs(evidence,capsys):
    root,output,policy=evidence
    write_mutants(output,{'hawa.cli.x_main__mutmut_1':(33,KILLED_DIFF),'hawa.cli.x_main__mutmut_2':(0,SURVIVOR_DIFF),
                          'hawa.cli.x_main__mutmut_3':(1,KILLED_DIFF)})
    (output/'src/hawa/cli.py').write_text('edited\n')
    policy['tool']='mutmut==2.4.5'
    path=output/'policy.json';path.write_text(json.dumps(policy))
    assert policy_tool.main([str(output),'--policy',str(path),'--draft'])==0
    drafted=json.loads(capsys.readouterr().out)
    assert drafted['mutants']==3 and drafted['scope']=='CLI fixture' and drafted['tool']=='mutmut==3.7.0'
    assert drafted['inventory_sha256']==sha('\n'.join('hawa.cli.x_main__mutmut_'+n for n in '123'))
    assert drafted['sources']['src/hawa/cli.py']==sha('edited\n')
    assert drafted['reviewed_survivors']=={
        'hawa.cli.x_main__mutmut_1':dict(status='no tests',diff_sha256=sha(KILLED_DIFF),reason=''),
        'hawa.cli.x_main__mutmut_2':dict(status='survived',diff_sha256=sha(SURVIVOR_DIFF),reason='fixture equivalent')}
    # A changed diff loses its old reason, and an empty reason fails verification until reviewed.
    write_mutants(output,{'hawa.cli.x_main__mutmut_1':(1,KILLED_DIFF),'hawa.cli.x_main__mutmut_2':(0,'other')})
    assert policy_tool.draft(output,policy)['reviewed_survivors']['hawa.cli.x_main__mutmut_2']['reason']==''
    write_mutants(output,{'hawa.cli.x_main__mutmut_1':(1,KILLED_DIFF),'hawa.cli.x_main__mutmut_2':(33,SURVIVOR_DIFF)})
    assert policy_tool.draft(output,policy)['reviewed_survivors']['hawa.cli.x_main__mutmut_2']['reason']==''
    with pytest.raises(ValueError,match='Timeout'):
        write_mutants(output,{'hawa.cli.x_main__mutmut_1':(36,KILLED_DIFF)});policy_tool.draft(output,policy)


@pytest.mark.parametrize('prefix', ['', 'results/cli-mutation/', '/tmp/study/'])
def test_collection_paths_are_relative_to_pytest_root(evidence,prefix):
    root,output,policy=evidence
    (output/'collected.txt').write_text(prefix+'tests/test_cli.py::test_one\n')
    assert policy_tool.verify(output,policy,root)['control_tests']==1


def test_policy_can_name_several_control_files(evidence):
    root, output, policy = evidence
    policy['control_test_files'] = ['tests/test_a.py', 'tests/test_b.py']
    (output/'control.xml').write_text('<testsuite><testcase name="test_one"/><testcase name="test_two"/></testsuite>')
    (output/'collected.txt').write_text('tests/test_a.py::test_one\ntests/test_b.py::test_two\ntests/test_c.py::test_three\n')
    assert policy_tool.verify(output, policy, root)['control_tests'] == 2
    (output/'collected.txt').write_text('tests/test_a.py::test_one\n')
    with pytest.raises(ValueError, match='control tests'):
        policy_tool.verify(output, policy, root)
    # A listed suite missing from both collection and the control run is incomplete evidence.
    (output/'control.xml').write_text('<testsuite><testcase name="test_one"/></testsuite>')
    with pytest.raises(ValueError, match='control tests'):
        policy_tool.verify(output, policy, root)
    (output/'collected.txt').write_text('tests/test_a.py::test_one\ntests/test_c.py::test_two\n')
    with pytest.raises(ValueError, match='control tests'):
        policy_tool.verify(output, policy, root)
    # JUnit names carry no class prefix, so a class-qualified id fails closed with the policy error.
    (output/'control.xml').write_text('<testsuite><testcase name="test_one"/><testcase name="test_two"/></testsuite>')
    (output/'collected.txt').write_text('tests/test_a.py::TestK::test_one\ntests/test_b.py::test_two\n')
    with pytest.raises(ValueError, match='control tests'):
        policy_tool.verify(output, policy, root)


@pytest.mark.parametrize('name', sorted(p.name for p in (ROOT/'tools/mutation').glob('*-policy.json')))
def test_committed_policies_are_complete_and_reviewed(name):
    policy=json.loads((ROOT/'tools/mutation'/name).read_text())
    assert policy['tool']=='mutmut==3.7.0' and policy['scope'] and policy['control_test_files']
    assert policy['mutants']>len(policy['reviewed_survivors'])
    for row in policy['reviewed_survivors'].values():
        assert row['status'] in ('survived','no tests') and len(row['diff_sha256'])==64 and row['reason'].strip()
    for source,expected in policy['sources'].items():
        assert policy_tool.digest(ROOT/source)==expected, source


# Changed-lines scope: only lines a patch adds may be mutated.
PATCH='''diff --git src/pkg/a.py src/pkg/a.py
--- src/pkg/a.py
+++ src/pkg/a.py
@@ -2,3 +2,4 @@ def f():
     keep = 1
-    old = 2
+    new = 2
+    more = 3
     tail = 4
@@ -20 +21 @@ def g():
-    x = 1
+    x = 2
@@ -30,0 +32,1 @@
+++counter = 1
--- src/pkg/b.py
+++ src/pkg/b.py
@@ -1,2 +1,0 @@
-gone = 1
-also = 2
@@ -9,2 +7,2 @@
 context = 0
-last = 1
\\ No newline at end of file
+last = 2
\\ No newline at end of file
--- /dev/null
+++ src/pkg/new file.py\t
@@ -0,0 +1 @@
+x = 1
'''


def test_changed_lines_are_the_added_new_side_lines_only():
    # Removed lines and context are not in scope; a "+++" content line is an added line, not a header.
    # Git ends a name that contains a space with a tab.
    assert launcher.changed_lines(PATCH)=={'src/pkg/a.py':[3,4,21,32],'src/pkg/b.py':[8],'src/pkg/new file.py':[1]}
    assert launcher.changed_lines('')=={}


@pytest.mark.parametrize('patch,message',[
    ('--- a\n+++ a\n@@ -1,2 +1,2 @@\n context\n','ends inside a hunk'),
    ('--- a\n+++ a\n@@ -1,2 +1,0 @@\n-x\n','ends inside a hunk'),
    ('--- a\n+++ a\n@@ -1,0 +1,2 @@\n+x\n','ends inside a hunk'),
    ('--- a\n+++ a\n@@ -1 +1 @@\nnot a diff line\n','Truncated hunk'),
    ('--- a\n+++ a\n@@ garbage @@\n','Unreadable hunk header'),
    ('@@ -1 +1 @@\n-x\n+y\n','Unreadable hunk header')])
def test_malformed_patches_are_rejected(patch,message):
    with pytest.raises(ValueError,match=message):launcher.changed_lines(patch)


@pytest.mark.parametrize('path,roots,name',[
    ('src/hawa/cli.py',['src'],'hawa.cli'),
    ('src/hawa/sub/__init__.py',['src'],'hawa.sub'),
    ('src.py',['src'],'src'),
    ('scripts/device_smoke.py',['src','scripts'],'device_smoke'),
    ('tools/mutation/check_results.py',['tools','tools/mutation'],'check_results'),
    ('tools/mutation/check_results.py',['src'],'tools.mutation.check_results'),
    ('vendor/lettuce/lettuce/ext/k.py',['src','vendor/lettuce'],'lettuce.ext.k')])
def test_module_names_follow_the_innermost_import_root(path,roots,name):
    assert launcher.module_name(path,roots)==name


def fake_mutmut(tmp_path,monkeypatch):
    calls=[]
    main=SimpleNamespace(mutmut=SimpleNamespace(_covered_lines='untouched'),get_mutant_name=None,
                         setup_source_paths=lambda:calls.append('mutmut setup'))
    file_mutation=SimpleNamespace(get_mutant_name=None)
    monkeypatch.chdir(tmp_path)
    for root in ('src','scripts'):(tmp_path/root).mkdir(exist_ok=True)
    monkeypatch.setattr(sys,'path',[str(tmp_path/'scripts'),'/elsewhere',str(tmp_path/'src')])
    return main,file_mutation,calls


def test_install_names_mutants_by_import_root_and_scopes_lines(tmp_path,monkeypatch):
    main,file_mutation,calls=fake_mutmut(tmp_path,monkeypatch)
    launcher.install(main,file_mutation,['src','scripts'],{'scripts/s.py':[4,9]},['scripts/s.py','src/hawa/x.py'])
    assert main.get_mutant_name is file_mutation.get_mutant_name
    assert main.get_mutant_name(Path('scripts/s.py'),'x_f__mutmut_1')=='s.x_f__mutmut_1'
    main.setup_source_paths()
    mutants=tmp_path/'mutants'
    assert calls==['mutmut setup']
    # The mutated copies come first and the originals are no longer importable.
    assert sys.path==[str(mutants/'scripts'),str(mutants/'src'),'/elsewhere']
    assert main.mutmut._covered_lines=={str(mutants/'scripts/s.py'):{4,9},str(mutants/'src/hawa/x.py'):set()}


def test_install_without_scope_mutates_every_line_and_rejects_foreign_scope(tmp_path,monkeypatch):
    main,file_mutation,_=fake_mutmut(tmp_path,monkeypatch)
    launcher.install(main,file_mutation,['src'],None,['src/hawa/x.py'])
    main.setup_source_paths()
    assert main.mutmut._covered_lines=='untouched'
    main,file_mutation,_=fake_mutmut(tmp_path,monkeypatch)
    launcher.install(main,file_mutation,['src'],{'src/hawa/other.py':[1]},['src/hawa/x.py'])
    with pytest.raises(ValueError,match='outside the mutated sources: src/hawa/other.py'):
        main.setup_source_paths()


class FakeData:
    codes={'src/a.py':{'a.x_f__mutmut_2':0,'a.x_f__mutmut_1':1},'src/b.py':{}}

    def __init__(self,path):self.path=path

    def load(self):self.exit_code_by_key=self.codes[str(self.path)]


def test_export_writes_raw_exit_codes_and_diffs(tmp_path):
    main=SimpleNamespace(walk_mutatable_files=lambda:[Path('src/a.py'),Path('src/b.py')],
                         get_diff_for_mutant=lambda name,path:'diff of '+name+' in '+str(path))
    assert launcher.export(main,lambda path:FakeData(path),tmp_path)==2
    assert json.loads((tmp_path/'mutants.json').read_text())=={
        'a.x_f__mutmut_1':dict(path='src/a.py',exit_code=1,diff='diff of a.x_f__mutmut_1 in src/a.py'),
        'a.x_f__mutmut_2':dict(path='src/a.py',exit_code=0,diff='diff of a.x_f__mutmut_2 in src/a.py')}
    assert (tmp_path/'mutations.diff').read_text()==(
        '# a.x_f__mutmut_1 exit 1\ndiff of a.x_f__mutmut_1 in src/a.py\n\n'
        '# a.x_f__mutmut_2 exit 0\ndiff of a.x_f__mutmut_2 in src/a.py\n\n')


def install_fake_package(monkeypatch,version='3.7.0'):
    """Stand in for the pinned mutmut, which only installs on Python 3.10+."""
    import importlib.metadata
    calls=[]
    package=ModuleType('mutmut');main=ModuleType('mutmut.__main__');mutation=ModuleType('mutmut.mutation')
    file_mutation=ModuleType('mutmut.mutation.file_mutation');data=ModuleType('mutmut.mutation.data')
    data.SourceFileMutationData=lambda path:FakeData(path)
    main.mutmut=SimpleNamespace(_covered_lines=None)
    main.Config=SimpleNamespace(ensure_loaded=lambda:calls.append('config'))
    main.walk_mutatable_files=lambda:[Path('src/a.py')]
    main.setup_source_paths=lambda:None
    main.get_diff_for_mutant=lambda name,path:'d'
    main.cli=lambda args,standalone_mode:calls.append((args,standalone_mode))
    package.__main__=main;package.mutation=mutation;mutation.file_mutation=file_mutation;mutation.data=data
    for module in (package,main,mutation,file_mutation,data):monkeypatch.setitem(sys.modules,module.__name__,module)
    real=importlib.metadata.version
    monkeypatch.setattr(importlib.metadata,'version',lambda name:version if name=='mutmut' else real(name))
    return main,calls


def test_launcher_refuses_any_other_mutmut_version(monkeypatch):
    install_fake_package(monkeypatch,'3.8.1')
    with pytest.raises(SystemExit,match='mutmut==3.7.0'):launcher.load_mutmut()


def test_launcher_commands_drive_the_pinned_mutmut(tmp_path,monkeypatch):
    main,calls=install_fake_package(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys,'path',list(sys.path))
    patch=tmp_path/'p.patch';patch.write_text('--- src/a.py\n+++ src/a.py\n@@ -1 +1 @@\n-x\n+y\n')
    assert launcher.main(['changed-lines',str(patch),'scope.json'])==0
    assert json.loads((tmp_path/'scope.json').read_text())=={'src/a.py':[1]}
    for args in ([],['run'],['run','--max-children','two']):
        with pytest.raises(SystemExit) as exit_info:launcher.main(args)
        assert exit_info.value.code==2 and calls==[]
    assert launcher.main(['run','--max-children','2'])==0
    assert main.get_mutant_name(Path('scripts/s.py'),'x_f__mutmut_1')=='scripts.s.x_f__mutmut_1'
    calls.clear()
    assert launcher.main(['run','--max-children','3','--scope','scope.json','--import-root','scripts'])==0
    assert calls==['config',(['run','--max-children','3'],False)]
    assert main.get_mutant_name(Path('scripts/s.py'),'x_f__mutmut_1')=='s.x_f__mutmut_1'
    assert main.get_mutant_name(Path('src/hawa/x.py'),'x_f__mutmut_1')=='hawa.x.x_f__mutmut_1'
    main.setup_source_paths()
    assert main.mutmut._covered_lines=={str(tmp_path/'mutants/src/a.py'):{1}}
    assert launcher.main(['export'])==0
    assert set(json.loads((tmp_path/'mutants.json').read_text()))=={'a.x_f__mutmut_1','a.x_f__mutmut_2'}


FIXTURE_SOURCE='''def scale(x):
    a = x * 2
    b = x + 3
    return a, b
'''


def test_real_mutmut_never_mutates_a_line_outside_the_patch(tmp_path):
    """Run the pinned mutmut on a tiny project whose patch adds only line 3."""
    import importlib.metadata
    try:
        installed=importlib.metadata.version('mutmut')
    except importlib.metadata.PackageNotFoundError:
        installed=None
    if installed!=launcher.MUTMUT_VERSION:
        pytest.skip('needs mutmut '+launcher.MUTMUT_VERSION+' (.venv-dev, Python 3.10+)')
    (tmp_path/'src/pkg').mkdir(parents=True);(tmp_path/'tests').mkdir()
    (tmp_path/'src/pkg/__init__.py').write_text('')
    (tmp_path/'src/pkg/mod.py').write_text(FIXTURE_SOURCE)
    (tmp_path/'tests/test_mod.py').write_text('from pkg.mod import scale\n\n\ndef test_scale():\n    assert scale(5) == (10, 8)\n')
    (tmp_path/'setup.cfg').write_text('[mutmut]\nsource_paths = src\nuse_git_change_detection = false\n'
                                     'pytest_add_cli_args_test_selection = tests\n')
    (tmp_path/'pytest.ini').write_text('[pytest]\n')
    (tmp_path/'changed.patch').write_text('--- src/pkg/mod.py\n+++ src/pkg/mod.py\n@@ -3 +3 @@\n-    b = x + 4\n+    b = x + 3\n')
    tool=[sys.executable,str(ROOT/'tools/mutation/mutmut3.py')]
    env=dict(PATH='/usr/bin:/bin',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',HOME=str(tmp_path))
    for args in (['changed-lines','changed.patch','scope.json'],['run','--max-children','1','--scope','scope.json'],['export']):
        subprocess.run(tool+args,cwd=tmp_path,env=env,check=True,capture_output=True,timeout=300)
    rows=json.loads((tmp_path/'mutants.json').read_text())
    changed={line for row in rows.values() for line in row['diff'].splitlines()
             if line[:1] in '+-' and not line.startswith(('+++','---'))}
    assert rows and changed>={'-    b = x + 3'} and not any('x * 2' in line for line in changed)
    assert {row['exit_code'] for row in rows.values()}=={1}


def test_launcher_script_entrypoint_writes_the_scope(tmp_path,monkeypatch):
    import runpy
    patch=tmp_path/'p.patch';patch.write_text('--- src/a.py\n+++ src/a.py\n@@ -0,0 +1,2 @@\n+x = 1\n+y = 2\n')
    monkeypatch.setattr(sys,'argv',['mutmut3.py','changed-lines',str(patch),str(tmp_path/'scope.json')])
    with pytest.raises(SystemExit) as exit_info:runpy.run_path(str(ROOT/'tools/mutation/mutmut3.py'),run_name='__main__')
    assert exit_info.value.code==0 and json.loads((tmp_path/'scope.json').read_text())=={'src/a.py':[1,2]}
