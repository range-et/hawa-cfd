"""Regressions for the combined-base review; no live host or CUDA claims."""
from pathlib import Path
import sys
import zipfile

import pytest
import torch


def test_imported_wall_filter_survives_repeated_reset(tmp_path):
    from test_boundary_series import case
    from hawa.recording import record
    from hawa.boundary_data import capture
    from hawa.plugin import Session, SESSIONS, dispatch
    parent = case()
    parent['neutral_precursor']['wall_filter_seconds'] = .3
    parent['boundary_set']['patches'][0]['condition'] = dict(type='velocity', velocity=[1., 0, 0], profile='neutral')
    for patch in parent['boundary_set']['patches']:
        if patch['condition']['type'] == 'open': patch['condition']['backflow_mode'] = 'pressure'
    source = Session(parent, 'cpu'); source.advance(20)
    recorded = record(source, 24, 1, tmp_path/'parent', lambda n: None)
    child = case((6, 6, 8), 1., [2, 2, .5])
    child['neutral_precursor']['wall_filter_seconds'] = .3
    mapped = capture(recorded['manifest'], child, tmp_path/'boundary.npz')
    session = Session(mapped['case'], 'cpu'); SESSIONS[session.id] = session
    wall = session.solver.rough_floor
    initial = wall.filtered.clone()
    try:
        session.advance(2)
        expected_f = session.flow.f.clone(); expected_wall = wall.filtered.clone()
        for _ in range(2):
            dispatch(dict(op='reset', session=session.id))
            assert wall.filtered is not None
            torch.testing.assert_close(wall.filtered, initial, rtol=0, atol=0)
            session.advance(2)
            torch.testing.assert_close(session.flow.f, expected_f, rtol=0, atol=0)
            torch.testing.assert_close(wall.filtered, expected_wall, rtol=0, atol=0)
    finally:
        dispatch(dict(op='close', session=session.id))


def test_external_memory_rejected_before_link_allocation(monkeypatch):
    from test_boundary_series import case
    from hawa.plugin import check_case
    import hawa.neutral_external as external
    spec = case((4, 128, 1024))
    called = []
    def forbidden(_):
        called.append(True)
        raise AssertionError('large link arrays allocated before budget check')
    monkeypatch.setattr(external, 'compile_links', forbidden)
    with pytest.raises(ValueError, match='budget'):
        check_case(spec)
    assert not called


def test_source_bundle_contains_verification_inputs(tmp_path, monkeypatch):
    from scripts import build_plugin
    root = tmp_path/'repo'
    folders = ['src/hawa', 'vendor/lettuce/lettuce', 'vendor/monad_system', 'scripts', 'requirements',
               'tests', 'tools', '.config', 'docs/agents', 'docs/function-tests',
               'examples/grasshopper', 'examples/native-prototype']
    for folder in folders: (root/folder).mkdir(parents=True)
    for name in ['Hawa.Rhino.rhp', 'Hawa.Shared.dll']:
        p=root/'plugin/Hawa.Rhino/bin/Release/net7.0'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'test assembly')
    p=root/'plugin/Hawa.Grasshopper/bin/Release/net7.0/Hawa.Grasshopper.gha';p.parent.mkdir(parents=True);p.write_bytes(b'test assembly')
    files=['plugin/Bootstrap.py','pyproject.toml','uv.lock','LICENSE','THIRD_PARTY_NOTICES.md',
           'README.md','AGENTS.md','features.md','issues.md','tools/function_coverage.py',
           '.config/dotnet-tools.json','docs/function-tests/matrix.json','examples/grasshopper/01-test.gh',
           'examples/grasshopper/09-parametric-hull-galapagos.gh']
    for name in ('LICENSE','AUTHORS.rst','PORTING.md','upstream.json'):files.append('vendor/lettuce/'+name)
    for name in ('LICENSE','colors.json','upstream.json'):files.append('vendor/monad_system/'+name)
    for name in files:(root/name).write_text('fixture '+name)
    monkeypatch.setattr(build_plugin,'ROOT',root)
    output=tmp_path/'bundle';archive=tmp_path/'bundle.zip'
    monkeypatch.setattr(sys,'argv',['build_plugin','--package-only','--output',str(output),'--archive',str(archive)])
    build_plugin.main()
    for name in ['tools/function_coverage.py','.config/dotnet-tools.json','docs/function-tests/matrix.json','examples/grasshopper/01-test.gh','vendor/monad_system/colors.json','vendor/monad_system/upstream.json','vendor/monad_system/LICENSE']:
        assert (output/'source'/name).read_bytes()==(root/name).read_bytes()
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        for name in ('colors.json','upstream.json','LICENSE'):
            assert bundle.read('Hawa/source/vendor/monad_system/'+name)==(root/'vendor/monad_system'/name).read_bytes()
        assert not any(Path(n).name.startswith('09-') for n in bundle.namelist())


def test_boundary_memory_increases_with_exposed_faces_before_allocation(monkeypatch):
    from test_boundary_series import case
    from hawa.plugin import check_case
    import hawa.neutral_external as external
    spec = case((12, 12, 12))
    spec['boundary_set']['patches'][5]['condition']['type'] = 'slip'
    all_open = check_case(spec)
    # Even the two persistent dense float64 matrices alone need this much.
    nodes = 12*12*12 - 10*10*12
    assert all_open['estimated_boundary_preparation_mb'] * 1024**2 >= nodes * 2 * 19 * 19 * 8
    for i in (2, 3):spec['boundary_set']['patches'][i]['condition']['type'] = 'periodic'
    paired = check_case(spec)
    assert 0 < paired['estimated_boundary_preparation_mb'] < all_open['estimated_boundary_preparation_mb']
    spec['memory_limit_mb'] = int(paired['estimated_peak_mb'])
    def forbidden(_):
        raise AssertionError('link compilation must follow the budget check')
    monkeypatch.setattr(external, 'compile_links', forbidden)
    with pytest.raises(ValueError, match='budget'):check_case(spec)
