"""Headless command contracts; deterministic doubles plus actual CPU smoke output."""
import json
import platform
import sys

import numpy as np
import pytest

from hawa import engine


@pytest.fixture
def command(monkeypatch):
    from hawa import cli
    calls = []
    report = {'passed': True, 'steps': 7, 'backend': {'device': 'cpu'}}
    fields = {'density': np.array([[1., 2.]], dtype=np.float32),
              'velocity': np.array([[[.1, .2]], [[.3, .4]]], dtype=np.float32),
              'iteration': 7}

    class Simulation:
        def __init__(self, *args, **kwargs):
            calls.append(('construct', args, kwargs))

        def advance(self, steps):
            calls.append(('advance', steps))

        def diagnostics(self):
            calls.append(('diagnostics',))
            return dict(report)

        def snapshot(self):
            calls.append(('snapshot',))
            return fields

    monkeypatch.setattr(engine, 'LettuceSimulation', Simulation)
    monkeypatch.setattr(cli, 'VortexSimulation', Simulation)
    monkeypatch.setattr(cli, 'select_backend', lambda device: ('selected', device))
    return calls, report, fields


def invoke(monkeypatch, *args):
    from hawa import cli
    monkeypatch.setattr(sys, 'argv', ['hawa', *map(str, args)])
    return cli.main()


def test_default_command_and_output_contract(command, monkeypatch, tmp_path, capsys):
    calls, report, fields = command
    monkeypatch.chdir(tmp_path)
    assert invoke(monkeypatch) == 0
    assert calls == [('construct', (), {'case': 'tgv2d-bgk', 'device': 'auto', 'size': None}),
                     ('advance', 200), ('diagnostics',), ('snapshot',)]
    saved = json.loads((tmp_path/'results/headless/report.json').read_text())
    assert saved == dict(report, python=sys.version, architecture=platform.machine(), host='headless')
    assert json.loads(capsys.readouterr().out) == saved
    with np.load(tmp_path/'results/headless/fields.npz', allow_pickle=False) as actual:
        assert set(actual.files) == set(fields)
        for key, expected in fields.items():
            np.testing.assert_array_equal(actual[key], expected)


@pytest.mark.parametrize('passed,expected_exit', [(True, 0), (False, 1)])
def test_explicit_lettuce_arguments_and_failed_report(command, monkeypatch, tmp_path, passed, expected_exit):
    calls, report, _ = command
    report['passed'] = passed
    output = tmp_path/'nested'/'output'
    assert invoke(monkeypatch, '--engine', 'lettuce', '--case', 'tgv2d-trt',
                  '--device', 'cpu', '--size', 24, '--steps', 7, '--output', output) == expected_exit
    assert calls[:2] == [('construct', (), {'case': 'tgv2d-trt', 'device': 'cpu', 'size': 24}), ('advance', 7)]
    assert json.loads((output/'report.json').read_text())['passed'] is passed
    assert (output/'fields.npz').is_file()
    # Reusing an existing directory is supported.
    assert invoke(monkeypatch, '--output', output) == expected_exit


@pytest.mark.parametrize('size,expected', [(None, 64), (16, 16)])
def test_smoke_backend_selection_and_size(command, monkeypatch, tmp_path, size, expected):
    calls, _, _ = command
    args = ['--engine', 'smoke', '--device', 'cpu', '--steps', '0', '--output', str(tmp_path)]
    if size is not None:
        args += ['--size', str(size)]
    assert invoke(monkeypatch, *args) == 0
    assert calls[0][1][0] == ('selected', 'cpu')
    assert calls[0][1][1].size == expected
    assert calls[0][2] == {}
    assert calls[1] == ('advance', 0)


@pytest.mark.parametrize('args', [('--engine', 'unknown'), ('--case', 'unknown'),
                                  ('--size', 'bad'), ('--steps', 'bad'), ('--unknown',)])
def test_invalid_arguments_do_not_construct_solver(command, monkeypatch, args):
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *args)
    assert error.value.code == 2
    assert command[0] == []


def test_solver_failure_propagates_without_output(command, monkeypatch, tmp_path):
    def failed(*args, **kwargs):
        raise RuntimeError('solver failed')
    monkeypatch.setattr(engine, 'LettuceSimulation', failed)
    output = tmp_path/'absent'
    with pytest.raises(RuntimeError, match='solver failed'):
        invoke(monkeypatch, '--output', output)
    assert not output.exists()


def test_output_failure_is_not_reported_as_success(command, monkeypatch, tmp_path):
    output = tmp_path/'file'
    output.write_text('preserved')
    with pytest.raises(FileExistsError):
        invoke(monkeypatch, '--output', output)
    assert output.read_text() == 'preserved'
    assert ('snapshot',) not in command[0]


def test_actual_cpu_smoke_exports_physical_arrays(monkeypatch, tmp_path, capsys):
    assert invoke(monkeypatch, '--engine', 'smoke', '--device', 'cpu', '--size', 16,
                  '--steps', 0, '--output', tmp_path) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['steps'] == 0 and report['size'] == 16 and report['passed']
    with np.load(tmp_path/'fields.npz', allow_pickle=False) as data:
        axis = np.arange(16)*2*np.pi/16
        y, x = np.meshgrid(axis, axis, indexing='ij')
        np.testing.assert_allclose(data['density'], 1 + .75*.04**2*(np.cos(2*x)+np.cos(2*y)), rtol=2e-7)
        np.testing.assert_allclose(data['velocity'], [.04*np.sin(x)*np.cos(y), -.04*np.cos(x)*np.sin(y)], atol=3e-8)
        assert data['iteration'] == 0


def test_smoke_snapshot_is_detached_from_live_state():
    from hawa.backends import select_backend
    from hawa.lbm import VortexConfig, VortexSimulation
    sim = VortexSimulation(select_backend('cpu'), VortexConfig(size=16))
    saved = sim.snapshot()
    saved['density'][:] = 0
    saved['velocity'][:] = 0
    fresh = sim.snapshot()
    assert np.all(fresh['density'] > 0)
    assert np.any(fresh['velocity'] != 0)
    sim.advance(1)
    assert sim.snapshot()['iteration'] == 1 and saved['iteration'] == 0


@pytest.mark.parametrize('passed,exit_code', [(True, 0), (False, 1)])
def test_python_module_entrypoint_propagates_exit_status(command, monkeypatch, tmp_path, passed, exit_code):
    import runpy
    command[1]['passed'] = passed
    monkeypatch.setattr(sys, 'argv', ['hawa', '--steps', '0', '--output', str(tmp_path)])
    # Exercise the executable guard, not just a direct call to main().
    with pytest.warns(RuntimeWarning, match='found in sys.modules'):
        with pytest.raises(SystemExit) as result:
            runpy.run_module('hawa.cli', run_name='__main__')
    assert result.value.code == exit_code
    assert json.loads((tmp_path/'report.json').read_text())['passed'] is passed
