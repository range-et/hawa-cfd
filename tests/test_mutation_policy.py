"""Mutation evidence must fail closed on incomplete, changed or unexpected results."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mutation_policy',ROOT/'tools/mutation/check_results.py')
policy_tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy_tool)


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
    (output/'collected.txt').write_text('tests/test_cli.py::test_one\n')
    (output/'control.xml').write_text('<testsuite><testcase name="test_one"/></testsuite>')
    (output/'mutations.xml').write_text('<testsuite><testcase name="Mutant #1"/><testcase name="Mutant #2"><failure message="bad_survived">reviewed diff</failure></testcase></testsuite>')
    (output/'mutation-exit.txt').write_text('2\n')
    policy=dict(mutants=2,sources=sources,reviewed_survivors={'Mutant #2':dict(diff_sha256=hashlib.sha256(b'reviewed diff').hexdigest(),reason='fixture equivalent')})
    return root,output,policy


def test_exact_reviewed_inventory_passes_without_hiding_survivors(evidence):
    root,output,policy=evidence
    result=policy_tool.verify(output,policy,root)
    assert result['killed']==1 and result['reviewed_survivors']==1 and result['raw_mutmut_exit']==2
    assert result['control_tests']==1 and result['policy_pass']


@pytest.mark.parametrize('change', ['source','copy','during','missing_control','failed_control','skipped_control',
    'duplicate','missing_mutant','unknown_name','error','timeout','unknown_survivor','diff','exit'])
def test_incomplete_or_changed_mutation_evidence_is_rejected(evidence,change):
    root,output,policy=evidence
    if change=='source':(root/'src/hawa/cli.py').write_text('changed')
    elif change=='copy':(output/'src/hawa/cli.py').write_text('changed')
    elif change=='during':(output/'working-source-after.sha256').write_text('changed')
    elif change=='missing_control':(output/'collected.txt').write_text('tests/test_cli.py::other\n')
    elif change in ('failed_control','skipped_control'):
        tag='failure' if change=='failed_control' else 'skipped'
        (output/'control.xml').write_text('<testsuite><testcase name="test_one"><'+tag+'/></testcase></testsuite>')
    elif change=='exit':(output/'mutation-exit.txt').write_text('0')
    else:
        path=output/'mutations.xml';tree=ET.parse(path);parent=tree.getroot();first,second=list(parent)
        if change=='duplicate':second.set('name','Mutant #1')
        elif change=='missing_mutant':parent.remove(second)
        elif change=='unknown_name':first.set('name','invented')
        elif change=='error':ET.SubElement(first,'error')
        elif change=='timeout':second.find('failure').set('message','bad_timeout')
        elif change=='unknown_survivor':ET.SubElement(first,'failure',message='bad_survived').text='new'
        elif change=='diff':second.find('failure').text='different'
        tree.write(path)
    with pytest.raises(ValueError):policy_tool.verify(output,policy,root)


def test_policy_cli_reports_exact_verifier_result(evidence,monkeypatch,capsys):
    root,output,policy=evidence
    # Keep real verification and explicitly supply the synthetic checkout root.
    real=policy_tool.verify
    monkeypatch.setattr(policy_tool,'verify',lambda directory,config:real(directory,config,root))
    path=output/'policy.json';path.write_text(json.dumps(policy))
    assert policy_tool.main([str(output),'--policy',str(path)])==0
    assert json.loads(capsys.readouterr().out)['reviewed_survivors']==1


def test_reviewed_all_killed_inventory_requires_zero_exit(evidence):
    root,output,policy=evidence
    tree=ET.parse(output/'mutations.xml');second=list(tree.getroot())[1]
    second.remove(second.find('failure'));tree.write(output/'mutations.xml')
    policy['reviewed_survivors']={};(output/'mutation-exit.txt').write_text('0')
    result=policy_tool.verify(output,policy,root)
    assert result['killed']==2 and result['reviewed_survivors']==0


@pytest.mark.parametrize('prefix', ['', 'results/cli-mutation/', '/tmp/study/'])
def test_collection_paths_are_relative_to_pytest_root(evidence,prefix):
    root,output,policy=evidence
    (output/'collected.txt').write_text(prefix+'tests/test_cli.py::test_one\n')
    assert policy_tool.verify(output,policy,root)['control_tests']==1


def test_runtime_policy_checks_its_own_collected_inventory(evidence):
    root, output, policy = evidence
    policy.update(control_test_file='tests/test_runtime_admission.py', scope='Runtime admission')
    (output/'collected.txt').write_text('/tmp/study/tests/test_runtime_admission.py::test_one\n')
    assert policy_tool.verify(output, policy, root)['scope'] == 'Runtime admission'
    (output/'collected.txt').write_text('tests/test_cli.py::test_one\n')
    with pytest.raises(ValueError, match='control tests'):
        policy_tool.verify(output, policy, root)


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
