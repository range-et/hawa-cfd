import copy
from pathlib import Path
import numpy as np
import pytest
from matrix.cases import topologies,combinations
from matrix.operations import field_cases,exercise_field
from matrix.exports import export_cases,exercise_export
from matrix.native_data import native_data_cases,exercise_native_data
from matrix.contract import expected_rows,verify_rows,verify_examples,ROOT


def test_matrix_products_have_unique_complete_ids():
    rows=list(topologies());assert len(rows)==2*6**6
    assert len({r['id'] for r in rows})==len(rows)
    assert sum(r['expected'] for r in rows)==1392
    assert len(list(combinations()))==240
    assert len(expected_rows())==99291+576*3+1440+81+42


def test_evidence_rejects_missing_duplicate_false_pass_and_unknown_rows():
    rows=[dict(id='a',expected='accept',status='passed',observed='run'),dict(id='b',expected='reject',status='passed',observed='reject')]
    expected=dict(a=True,b=False)
    assert verify_rows(rows,expected)['passed']==2
    for bad in (rows[:1],rows+rows[:1],rows+[dict(rows[0],id='unknown')],[rows[0],dict(rows[1],observed='run')],[dict(rows[0],expected='reject'),rows[1]]):
        with pytest.raises(ValueError):verify_rows(bad,expected)


def test_public_component_example_inventory_is_current():
    result=verify_examples(ROOT/'docs/coverage-example-graphs.json')
    assert result['public_nodes']>0 and result['examples']>0


@pytest.mark.parametrize('row',list(field_cases()),ids=lambda row:row['id'])
def test_field_product(row,tmp_path):
    if row['expected']:exercise_field(row,tmp_path)
    else:
        with pytest.raises(ValueError,match='3D'):exercise_field(row,tmp_path)


@pytest.mark.parametrize('coordinates',(2,3))
def test_legacy_2d_streamlines_accept_planar_seeds(coordinates):
    from hawa.plugin import dispatch
    r=dispatch(dict(op='create',case=dict(example='tgv2d-bgk',size=12),device='cpu'));ident=r['session']
    try:
        result=dispatch(dict(op='streamlines',session=ident,seeds=[[2.,3.]+([0.] if coordinates==3 else [])],steps=4))
        assert len(result['paths'][0])>2
        assert len(result['paths'][0][0])==coordinates
        assert np.isfinite(result['paths']).all()
    finally:dispatch(dict(op='close',session=ident))


def test_declared_collision_boundary_and_scalar_options_do_not_drift():
    import ast
    from matrix.cases import COLLISIONS,FACE_TYPES
    from matrix.operations import SCALARS
    def tuples(path):
        return [{c.value for c in node.elts if isinstance(c,ast.Constant) and isinstance(c.value,str)} for node in ast.walk(ast.parse(path.read_text())) if isinstance(node,(ast.Tuple,ast.List))]
    assert set(COLLISIONS) in tuples(ROOT/'src/hawa/plugin.py')
    assert set(FACE_TYPES) in tuples(ROOT/'src/hawa/boundary_contracts.py')
    tree=ast.parse((ROOT/'src/hawa/fields.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='scalar');names=set()
    for node in ast.walk(fn):
        if isinstance(node,ast.Compare) and isinstance(node.left,ast.Name) and node.left.id=='name':
            for value in node.comparators:
                names.update(n.value for n in ast.walk(value) if isinstance(n,ast.Constant) and isinstance(n.value,str))
    assert names==set(SCALARS)


def test_export_inventory_is_complete_and_independent():
    rows=list(export_cases())
    assert len(rows)==27 and len({row['id'] for row in rows})==27
    assert sum(row['expected'] for row in rows)==7
    inventory=expected_rows()
    assert len([key for key in inventory if key.startswith('exports/')])==81
    assert all(inventory[row['id']+'/'+device]==row['expected'] for row in rows for device in ('cpu','mps','cuda:0'))


@pytest.mark.parametrize('row',list(export_cases()),ids=lambda row:row['id'])
def test_export_product_cpu(row,tmp_path):
    assert exercise_export(row,tmp_path,'cpu') is row['expected']


def test_native_data_inventory_is_complete_and_independent():
    rows=list(native_data_cases())
    assert len(rows)==14 and len({row['id'] for row in rows})==14
    assert sum(row['expected'] for row in rows)==2
    inventory=expected_rows()
    assert len([key for key in inventory if key.startswith('native-data/')])==42
    assert all(inventory[row['id']+'/'+device]==row['expected'] for row in rows for device in ('cpu','mps','cuda:0'))


@pytest.mark.parametrize('row',list(native_data_cases()),ids=lambda row:row['id'])
def test_native_data_product_cpu(row,tmp_path):
    assert exercise_native_data(row,tmp_path,'cpu') is row['expected']


@pytest.mark.parametrize('row',list(native_data_cases()),ids=lambda row:row['id'])
def test_native_data_product_relative_output_directory(row,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert exercise_native_data(row,Path('relative-fixtures'),'cpu') is row['expected']
