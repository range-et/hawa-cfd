"""Gate regressions: inventory, actual calls, stale evidence and debt ratcheting."""
import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from tools import function_coverage as fc


def fixture_root(tmp_path):
    root = tmp_path / "repo"
    (root / "src/hawa").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src/hawa/sample.py").write_text("def used(x):\n    return x + 1\n\ndef unused():\n    return 4\n")
    (root / "tests/test_sample.py").write_text("from src.hawa.sample import used\ndef test_used():\n    assert used(2) == 3\n")
    return root


def test_python_inventory_includes_async_properties_nested_and_lambdas():
    text = '''class Example:
    @property
    def value(self):
        """Read the value."""
        return 1
    @value.setter
    def value(self, x: int): self.x = x
async def outer(x=2, *, y=3):
    def inner():
        return x
    return inner
alias = lambda x: x + 1
'''
    rows = fc.python_functions("src/hawa/a.py", text)
    assert [r['name'] for r in rows] == ['Example.value', 'Example.value#2', 'outer', 'outer.inner', '<lambda>#1']
    assert rows[0]['first_line'] == 2 and rows[0]['summary'] == 'Read the value.'
    assert 'x: int' in rows[1]['signature'] and 'y=3' in rows[2]['signature']
    assert 9 not in rows[2]['body_lines']
    assert fc.python_functions('a.py', '\n' + text)[0]['fingerprint'] == rows[0]['fingerprint']


def test_source_inventory_excludes_generated_vendor_tests_and_snapshot_sees_additions(tmp_path):
    root = fixture_root(tmp_path)
    for name in ['plugin/One.cs', 'plugin/obj/Generated.cs', 'vendor/other.py', 'tools/helper.py']:
        p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('')
    assert fc.sources(root) == ['plugin/One.cs', 'src/hawa/sample.py', 'tools/helper.py']
    before = fc.snapshot(root)
    (root / 'tests/test_new.py').write_text('def test_new(): pass')
    assert fc.snapshot(root) != before


def test_csharp_inventory_overloads_accessors_local_functions_and_parse_errors(tmp_path):
    root = fixture_root(tmp_path)
    (root / 'plugin').mkdir()
    path = root / 'plugin/Example.cs'
    path.write_text('''namespace Test;
public class Example {
 public Example() { }
 public int Read(int x) { int Local(int y) => y + 1; return Local(x); }
 public int Read() => 1;
 public int Value { get { return 1; } set { System.Console.WriteLine(value); } }
 public int Twice => Read() * 2;
 public System.Func<int,int> Callback() => x => x + 1;
}''')
    rows = [r for r in fc.inventory(root) if r['language'] == 'C#']
    assert len(rows) == 9
    assert len({r['id'] for r in rows}) == len(rows)
    assert any(r['kind'] == 'LocalFunctionStatement' for r in rows)
    assert any(r['kind'] == 'SimpleLambdaExpression' for r in rows)
    path.write_text('class Broken { void Run( ')
    with pytest.raises(subprocess.CalledProcessError): fc.inventory(root)


def test_actual_call_evidence_requires_passing_case_and_handles_threads(tmp_path, monkeypatch):
    root = fixture_root(tmp_path)
    path = (root / 'src/hawa/sample.py').resolve()
    evidence = fc.CallEvidence(root, ['src/hawa/sample.py'])
    frame = SimpleNamespace(f_code=SimpleNamespace(co_filename=str(path), co_firstlineno=1, co_name='used'))
    # Exercise the callback with the real outer test context before synthetic IDs.
    evidence.profile(frame,'return',None)
    evidence.pytest_collection_finish(SimpleNamespace(items=[SimpleNamespace(nodeid='tests/test_sample.py::test_used')]))
    for case, status in [('tests/test_sample.py::test_used','passed'), ('tests/test_bad.py::test_bad','failed')]:
        monkeypatch.setenv('PYTEST_CURRENT_TEST',case + ' (call)')
        evidence.profile(frame,'call',None)
        evidence.pytest_runtest_logreport(SimpleNamespace(nodeid=case,when='call',outcome=status))
    evidence.profile(frame,'return',None)
    monkeypatch.delenv('PYTEST_CURRENT_TEST')
    evidence.profile(frame,'call',None)
    result = evidence.report()
    assert result['calls'][0]['tests'] == ['tests/test_sample.py::test_used']
    assert result['collected'] == result['passed']


def test_annotation_imports_do_not_cover_bodies_and_csharp_scope_is_explicit():
    rows = fc.python_functions('a.py','def f(): return 1\ndef g(): return 2\n')
    rows += [dict(path='c.cs',language='C#',name='M',body_lines=[4],declaration=False),
             dict(path='unknown.cs',language='C#',name='N',body_lines=[4],declaration=False),
             dict(path='c.cs',language='C#',name='I',body_lines=[],declaration=True)]
    calls = dict(calls=[dict(path='a.py',first_line=1,code_name='f',tests=['test_f'])])
    python = dict(files={'a.py':dict(executed_lines=[1,2],missing_lines=[],executed_branches=[[1,2]],missing_branches=[])})
    result = fc.annotate(rows,python,calls,{'c.cs':{4:2}})
    assert [r['status'] for r in result] == ['covered','uncovered','covered','unmeasured','declaration']
    assert result[2]['tests'] == ['tests/dotnet/StateContracts (suite-level)']
    assert result[0]['branches'] == dict(hit=1,total=1)


def test_ambiguous_same_line_lambdas_cannot_claim_coverage():
    rows = fc.python_functions('a.py', 'a, b = (lambda: 1), (lambda: 2)')
    result = fc.annotate(rows,dict(files={'a.py':dict(executed_lines=[1])}),
                         dict(calls=[dict(path='a.py',first_line=1,code_name='<lambda>',tests=['test_a'])]),{})
    assert all(r['status'] == 'uncovered' for r in result)


def test_csharp_coverage_merges_hits_and_ignores_external_files(tmp_path):
    root = tmp_path.resolve()
    data = {'module':{str(root/'a.cs'):{'C':{'M':{'Lines':{'4':1,'5':0}},'N':{'Lines':{'4':3}}}},
                      '/elsewhere/b.cs':{'B':{'M':{'Lines':{'1':3}}}}}}
    assert fc.csharp_lines(data,root) == {'a.cs':{4:3,5:0}}


def test_ratchet_rejects_new_changed_and_lost_coverage_without_hiding_old_debt():
    baseline = dict(schema=1,functions={'old':dict(status='uncovered',fingerprint='a'), 'good':dict(status='covered',fingerprint='b')})
    row = dict(id='old',status='uncovered',fingerprint='a')
    assert fc.gate([row],baseline) == []
    assert fc.gate([dict(row,id='new')],baseline)[0].startswith('NEW')
    assert fc.gate([dict(row,fingerprint='changed')],baseline)[0].startswith('CHANGED')
    assert fc.gate([dict(row,id='good')],baseline)[0].startswith('LOST')
    assert fc.gate([dict(row,id='new',status='covered')],baseline) == []
    with pytest.raises(ValueError): fc.gate([],dict(schema=999))


def test_validate_rejects_stale_missing_duplicate_and_failed_evidence(tmp_path):
    root = fixture_root(tmp_path)
    rows = fc.inventory(root)
    for row in rows: row.update(status='uncovered',tests=[])
    report = dict(schema=1,snapshot=fc.snapshot(root),python_exit=0,
                  tests=dict(collected=['test'],passed=['test'],outcomes={'test':[['call','passed']]}),functions=rows)
    fc.validate_report(root,report)
    for change in [dict(python_exit=1),dict(functions=rows[:-1]),dict(functions=rows+rows[:1]),dict(snapshot={})]:
        with pytest.raises(ValueError):fc.validate_report(root,dict(report,**change))
    bad = copy.deepcopy(report);bad['functions'][0]['status']='covered'
    with pytest.raises(ValueError):fc.validate_report(root,bad)
    bad=copy.deepcopy(report);bad['tests']['collected']+=['missing']
    with pytest.raises(ValueError,match='inventory'):fc.validate_report(root,bad)
    bad=copy.deepcopy(report);bad['functions'][0]['tests']=['not_a_real_test']
    with pytest.raises(ValueError,match='absent'):fc.validate_report(root,bad)


def test_csharp_shared_source_line_does_not_credit_both_methods():
    rows=[dict(path='a.cs',language='C#',name=name,body_lines=[2],declaration=False) for name in ('A','B')]
    assert all(r['status']=='uncovered' for r in fc.annotate(rows,{},dict(calls=[]),{'a.cs':{2:5}}))


def test_render_escapes_signatures_and_keeps_missing_coverage_visible():
    row = dict(name='Thing',path='src/hawa/a.py',line=2,language='Python',visibility='public',
               signature='f(a: A | B)',summary='summary\nline',status='unmeasured',lines=dict(hit=0,total=2),branches=None,tests=[])
    text=fc.render(dict(functions=[row]))
    assert 'A &#124; B' in text and 'unmeasured' in text and '../src/hawa/a.py#L2' in text


def test_measure_worker_failure_and_cleanup(tmp_path, monkeypatch):
    import coverage
    import threading
    root=fixture_root(tmp_path);output=tmp_path/'output';output.mkdir()
    calls=[]
    class FakeCoverage:
        def __init__(self,**kwargs): pass
        def start(self): calls.append('start')
        def stop(self): calls.append('stop')
        def save(self): calls.append('save')
        def json_report(self,**kwargs): pass
    monkeypatch.setattr(coverage,'Coverage',FakeCoverage)
    monkeypatch.setattr(sys,'setprofile',lambda p: None)
    monkeypatch.setattr(threading,'setprofile',lambda p: None)
    monkeypatch.chdir(root)
    monkeypatch.setattr(pytest,'main',lambda *a,**k: 1)
    assert fc.measure_python(root,output) == 1
    assert calls == ['start','stop','save']
    assert json.loads((output/'calls.json').read_text())['exit_code'] == 1


def test_end_to_end_measurement_and_gate(tmp_path, capsys, monkeypatch):
    root = fixture_root(tmp_path)
    (root/'tests/test_sample.py').write_text((root/'tests/test_sample.py').read_text()+'''
def test_worker():
    import threading
    result=[]
    thread=threading.Thread(target=lambda: result.append(used(4)))
    thread.start(); thread.join()
    assert result == [5]
''')
    output = tmp_path / 'run'
    monkeypatch.setenv('PYTEST_ADDOPTS','-k no_such_test')
    report = fc.run(root, output)
    assert len(report['tests']['passed']) == 2
    assert [r['status'] for r in report['functions']] == ['covered','uncovered']
    assert any('test_worker' in t for t in report['functions'][0]['tests'])
    baseline = dict(schema=1,functions={r['id']:dict(status=r['status'],fingerprint=r['fingerprint']) for r in report['functions']})
    (root/'baseline.json').write_text(json.dumps(baseline))
    args=['--root',str(root),'--output',str(output),'--baseline','baseline.json']
    assert fc.main(['check']+args) == 0
    assert fc.main(['render']+args) == 0
    assert 'Function test matrix' in capsys.readouterr().out
    docs=root/'docs/function-tests'; docs.mkdir(parents=True)
    (docs/'matrix.json').write_text(json.dumps(report))
    docs_args=['check','--root',str(root),'--output',str(docs),'--baseline','baseline.json']
    with pytest.raises(ValueError,match='Markdown'):fc.main(docs_args)
    (root/'docs/function-test-matrix.md').write_text(fc.render(report))
    assert fc.main(docs_args)==0
    # A checkout cannot weaken the trusted base-commit baseline.
    old=copy.deepcopy(baseline)
    for row in old['functions'].values():row['status']='covered'
    (root/'baseline.json').write_text(json.dumps(old))
    subprocess.run(['git','init','-q'],cwd=root,check=True)
    subprocess.run(['git','add','baseline.json'],cwd=root,check=True)
    subprocess.run(['git','-c','user.name=Coverage fixture','-c','user.email=fixture@example.invalid','commit','-qm','Baseline fixture'],cwd=root,check=True)
    (root/'baseline.json').write_text(json.dumps(baseline))
    assert fc.main(['check']+args+['--base-ref','HEAD']) == 1
    with pytest.raises(FileExistsError):fc.run(root,output)
    (root/'src/hawa/sample.py').write_text((root/'src/hawa/sample.py').read_text()+'\ndef added(): return 5\n')
    with pytest.raises(ValueError,match='stale'):fc.main(['check']+args)


def test_failed_suite_never_creates_success_matrix(tmp_path):
    root=fixture_root(tmp_path)
    (root/'tests/test_sample.py').write_text('def test_failure(): assert False\n')
    output=tmp_path/'failed'
    with pytest.raises(ValueError,match='failure'):fc.run(root,output)
    assert not (output/'matrix.json').exists()
