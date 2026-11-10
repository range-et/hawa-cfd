"""Full-coverage CI must not turn missing host/line evidence into a pass."""
import copy
import json
from types import SimpleNamespace

import pytest
from tools import function_coverage as fc


@pytest.fixture
def measured(tmp_path):
    (tmp_path/'src/hawa').mkdir(parents=True);(tmp_path/'plugin').mkdir()
    (tmp_path/'src/hawa/unit.py').write_text('def f():\n    return 1\n')
    (tmp_path/'plugin/Unit.cs').write_text('class Unit { int F() => 1; }')
    rows=[dict(id='python-f',path='src/hawa/unit.py',language='Python',status='covered',declaration=False),
          dict(id='csharp-f',path='plugin/Unit.cs',language='C#',status='covered',declaration=False)]
    python=dict(files={'src/hawa/unit.py':dict(executed_lines=[1,2],missing_lines=[],excluded_lines=[],summary=dict(num_statements=2))})
    return tmp_path,dict(functions=rows),python,{'plugin/Unit.cs':{1:1}}


def test_complete_firstparty_functions_and_lines_pass(measured):
    assert fc.strict_gate(*measured)==[]


@pytest.mark.parametrize('fault', ['function','host','python_missing','lines','excluded','incomplete','inconsistent','csharp_lines'])
def test_any_debt_or_missing_evidence_fails_strict_gate(measured,fault):
    root,report,python,cs=measured
    if fault=='function':report['functions'][0]['status']='uncovered'
    elif fault=='host':cs.clear();report['functions'][1]['status']='unmeasured'
    elif fault=='python_missing':python['files'].clear()
    elif fault=='lines':python['files']['src/hawa/unit.py'].update(executed_lines=[1],missing_lines=[2])
    elif fault=='excluded':python['files']['src/hawa/unit.py']['excluded_lines']=[2]
    elif fault=='incomplete':python['files']['src/hawa/unit.py'].pop('summary')
    elif fault=='inconsistent':python['files']['src/hawa/unit.py']['summary']['num_statements']=99
    elif fault=='csharp_lines':cs['plugin/Unit.cs'][1]=0
    assert fc.strict_gate(root,report,python,cs)


def test_declarations_are_not_executable_but_new_unmeasured_python_is(measured):
    root,report,python,cs=measured
    report['functions'].append(dict(id='declaration',path='plugin/Interface.cs',language='C#',status='declaration',declaration=True))
    (root/'plugin/Interface.cs').write_text('interface I { void Run(); }')
    assert fc.strict_gate(root,report,python,cs)==[]
    (root/'src/hawa/new.py').write_text('print("new module code")\n')
    assert any('new.py' in failure for failure in fc.strict_gate(root,report,python,cs))


def test_strict_cli_uses_raw_line_evidence_and_returns_failure(measured,monkeypatch,capsys):
    root,report,python,cs=measured
    output=root/'evidence';output.mkdir()
    (output/'matrix.json').write_text(json.dumps(report));(output/'python.json').write_text(json.dumps(python))
    (output/'state.json').write_text('{}');(root/'baseline.json').write_text('{}')
    monkeypatch.setattr(fc,'validate_report',lambda *args:None)
    monkeypatch.setattr(fc,'gate',lambda *args:[])
    monkeypatch.setattr(fc,'csharp_lines',lambda *args:cs)
    args=['check','--root',str(root),'--output',str(output),'--baseline','baseline.json','--strict']
    assert fc.main(args)==0
    cs.clear()
    assert fc.main(args)==1
    assert 'C# source unmeasured' in capsys.readouterr().out


def test_headless_scope_keeps_python_strict_but_does_not_claim_host_coverage(measured):
    root,report,python,cs=measured
    cs.clear();report['functions'][1]['status']='unmeasured'
    assert fc.strict_gate(root,report,python,cs,scope='headless')==[]
    assert fc.strict_gate(root,report,python,cs,scope='all')
    report['functions'][0]['status']='uncovered'
    assert fc.strict_gate(root,report,python,cs,scope='headless')


def test_docstring_trace_locations_do_not_inflate_statement_denominator(measured):
    root, report, python, cs = measured
    (root/'src/hawa/unit.py').write_text('"""Module documentation."""\ndef f():\n    return 1\n')
    row = python['files']['src/hawa/unit.py']
    row.update(executed_lines=[1, 2, 3], summary=dict(num_statements=2))
    assert fc.strict_gate(root, report, python, cs) == []
    row['executed_lines'] = [1, 2, 99]
    assert any('Inconsistent' in failure for failure in fc.strict_gate(root, report, python, cs))
