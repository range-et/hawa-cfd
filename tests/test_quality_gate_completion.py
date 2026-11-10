"""Adversarial evidence integrity and executable entry-point contracts."""
import copy
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest
from tools import function_coverage as fc
from test_function_coverage import fixture_root


def valid_report(root):
    rows = fc.inventory(root)
    for row in rows: row.update(status='uncovered', tests=[], lines=dict(hit=0,total=len(row['body_lines'])), branches=dict(hit=0,total=0))
    return dict(schema=1, snapshot=fc.snapshot(root), python_exit=0,
                tests=dict(collected=['case'], passed=['case'], outcomes={'case': [['call','passed']]}),
                functions=rows)


def test_duplicate_inventory_id_is_rejected(tmp_path, monkeypatch):
    root = fixture_root(tmp_path); original = fc.python_functions
    def duplicate(path, source):
        rows = original(path, source)
        return rows + rows[:1]
    monkeypatch.setattr(fc, 'python_functions', duplicate)
    with pytest.raises(ValueError, match='Duplicate function identities'): fc.inventory(root)


@pytest.mark.parametrize('fault', ['unreported_failure', 'inconsistent_pass_list'])
def test_report_cannot_hide_failed_or_inconsistent_outcomes(tmp_path, fault):
    root = fixture_root(tmp_path); report = valid_report(root)
    if fault == 'unreported_failure': report['tests']['outcomes']['case'].append(['teardown','failed'])
    else:
        report['tests']['collected'].append('other')
        report['tests']['outcomes']['other'] = [['call','passed']]
    with pytest.raises(ValueError, match='outcome evidence'): fc.validate_report(root, report)


def test_render_bounds_displayed_test_list_but_links_full_evidence():
    row = dict(name='f', path='src/hawa/a.py', line=1, language='Python', visibility='public',
               signature='f()', summary='', status='covered', lines=dict(hit=1,total=1),
               branches=dict(hit=2,total=2), tests=['case'+str(i) for i in range(6)])
    result = fc.render(dict(functions=[row]))
    assert 'case0<br>case1<br>case2<br>case3' in result
    assert 'case4' not in result and '+2 more in [JSON](function-tests/matrix.json)' in result


@pytest.mark.parametrize('fault', ['none', 'empty_csharp', 'changed_inputs'])
def test_run_orchestrates_state_instrumentation_and_rejects_incomplete_results(tmp_path, monkeypatch, fault):
    root = fixture_root(tmp_path)
    project = root/'tests/dotnet/StateContracts/StateContracts.csproj'
    project.parent.mkdir(parents=True); project.write_text('<Project/>')
    source = root/'plugin/State.cs'; source.parent.mkdir(); source.write_text('class State {}')
    output = tmp_path/'run'; commands = []
    # Keep real orchestration/serialization/checks while substituting external
    # process responses, including the Coverlet file contract.
    monkeypatch.setattr(fc, 'inventory', lambda _: [])
    def process(command, **kwargs):
        commands.append(command)
        if '_measure' in command:
            (output/'calls.json').write_text(json.dumps(dict(exit_code=0,collected=['case'],passed=['case'],outcomes={'case':[['call','passed']]},calls=[])))
            (output/'python.json').write_text('{"files": {}}')
        if 'coverlet' in command:
            state = {} if fault == 'empty_csharp' else {'module': {str(source): {'State': {'Run': {'Lines': {'1': 1}}}}}}
            (output/'state.json').write_text(json.dumps(state))
            if fault == 'changed_inputs': source.write_text('class Changed {}')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(fc.subprocess, 'run', process)
    if fault == 'none':
        report = fc.run(root, output)
        assert report['python_exit'] == 0 and report['tests']['passed'] == ['case']
        assert json.loads((output/'matrix.json').read_text()) == report
    else:
        with pytest.raises(ValueError, match='Empty C#' if fault == 'empty_csharp' else 'Inputs changed'):
            fc.run(root, output)
        assert not (output/'matrix.json').exists()
    assert commands[1][:3] == ['dotnet','tool','restore']
    assert commands[2][:2] == ['dotnet','build']
    assert commands[3][:4] == ['dotnet','tool','run','coverlet']
    assert '--include-test-assembly' in commands[3]


def test_measure_subcommand_returns_worker_exit_code(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(fc, 'measure_python', lambda root, output: calls.append((root, output)) or 7)
    assert fc.main(['_measure','--root',str(tmp_path),'--output',str(tmp_path/'out')]) == 7
    assert calls == [(tmp_path, tmp_path/'out')]


def test_function_gate_script_entrypoint_validates_and_renders(tmp_path, monkeypatch, capsys):
    root = fixture_root(tmp_path); report = valid_report(root)
    output = tmp_path/'evidence'; output.mkdir(); (output/'matrix.json').write_text(json.dumps(report))
    monkeypatch.setattr(sys, 'argv', ['function_coverage.py','render','--root',str(root),'--output',str(output)])
    with pytest.raises(SystemExit) as exit_info: runpy.run_path(str(Path(fc.__file__)), run_name='__main__')
    assert exit_info.value.code == 0
    text = capsys.readouterr().out
    assert '# Function test matrix' in text and '2 uncovered' in text


def test_mutation_policy_script_entrypoint_checks_real_artifact(tmp_path, monkeypatch, capsys):
    from tools.mutation import check_results as mutation
    output = tmp_path/'run'; output.mkdir()
    name = 'tools/mutation/check_results.py'; target = output/name
    target.parent.mkdir(parents=True); target.write_bytes(Path(mutation.__file__).read_bytes())
    for suffix in ('before','after'): (output/('working-source-'+suffix+'.sha256')).write_text('same')
    (output/'collected.txt').write_text('tests/test_runtime_admission.py::test_contract\n')
    (output/'control.xml').write_text('<testsuite><testcase name="test_contract"/></testsuite>')
    (output/'mutations.xml').write_text('<testsuite><testcase name="Mutant #1"/></testsuite>')
    (output/'mutation-exit.txt').write_text('0')
    policy = dict(mutants=1, sources={name: mutation.digest(target)}, reviewed_survivors={},
                  control_test_file='tests/test_runtime_admission.py', scope='entrypoint fixture')
    config = output/'policy.json'; config.write_text(json.dumps(policy))
    monkeypatch.setattr(sys, 'argv', ['check_results.py',str(output),'--policy',str(config)])
    with pytest.raises(SystemExit) as exit_info: runpy.run_path(mutation.__file__, run_name='__main__')
    assert exit_info.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result['policy_pass'] and result['killed'] == result['control_tests'] == 1
    assert result['scope'] == 'entrypoint fixture' and result['reviewed_survivors'] == 0
