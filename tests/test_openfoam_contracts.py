"""Independent physical and dictionary checks for the OpenFOAM control handoff."""
import re
import sys
from pathlib import Path

import numpy as np
import pytest

from hawa import openfoam

SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


@pytest.mark.parametrize('face,expected', [
    ('x-', [(10, 21, 31), (10, 23, 31)]),
    ('x+', [(12, 21, 31), (12, 23, 31)]),
    ('y-', [(10.5, 20, 31), (11.5, 20, 31)]),
    ('y+', [(10.5, 24, 31), (11.5, 24, 31)]),
    ('z-', [(10.5, 21, 30), (11.5, 21, 30), (10.5, 23, 30), (11.5, 23, 30)]),
    ('z+', [(10.5, 21, 32), (11.5, 21, 32), (10.5, 23, 32), (11.5, 23, 32)]),
])
def test_translated_patch_centers_preserve_foam_order(face, expected):
    assert openfoam._blockmesh_patch_face_centers([10, 20, 30], [2, 4, 2], [2, 2, 1], face) == expected


def test_parabolic_face_samples_all_velocity_components():
    text = openfoam._render_parabolic_u_field([10, 20, 30], [2, 4, 2], [2, 4, 1], 'x-', [1, 2, 3], 1)
    assert 'type            fixedValue;' in text
    assert 'value           nonuniform List<vector>\n        4\n' in text
    vectors = [[float(x) for x in v.split()] for v in re.findall(r'\(([^()]+)\)', text) if len(v.split()) == 3]
    np.testing.assert_allclose(vectors, [[.4375, .875, 1.3125], [.9375, 1.875, 2.8125],
                                       [.9375, 1.875, 2.8125], [.4375, .875, 1.3125]], rtol=0, atol=0)
    assert text.endswith(');')


def test_2d_z_parabolic_profile_rejected_before_handoff_or_publication(tmp_path):
    spec, bundle, _ = openfoam.channel_poiseuille_case(6)
    bundle['boundaries'][0]['condition']['profile_axis'] = 2
    spec['boundary_set']['patches'][0]['condition']['profile_axis'] = 2
    message = 'Z-dependent parabolic profile; use dimensions=3'
    with pytest.raises(ValueError, match=message):
        openfoam.validate_bundle(bundle)
    destination = tmp_path / 'invalid-2d'
    with pytest.raises(ValueError, match=message):
        openfoam.write_openfoam_case(bundle, destination)
    assert not destination.exists()
    with pytest.raises(ValueError, match=message):
        openfoam.bundle_from_hawa_spec(spec=spec, case_id='z-profile', description='Z profile',
                                      probes=bundle['probes'], pressure_pairs=bundle['pressure_pairs'],
                                      mesh=bundle['mesh'], dimensions=2)


@pytest.mark.parametrize('axis', [0, 1, 2])
def test_parabolic_profiles_remain_resolved_in_supported_dimensions(axis):
    _, bundle, _ = openfoam.channel_poiseuille_case(6)
    if axis == 0:
        # Rotate the inlet/outlet to Y so X is an in-plane tangential axis.
        for patch in bundle['boundaries']:
            patch['face'] = patch['face'].translate(str.maketrans('xy', 'yx'))
            if 'velocity' in patch['condition']:
                velocity = patch['condition']['velocity']
                velocity[0], velocity[1] = velocity[1], velocity[0]
    elif axis == 2:
        bundle['dimensions'] = 3
        bundle['mesh']['cells'][2] = 4
    inlet = bundle['boundaries'][0]
    inlet['condition']['profile_axis'] = axis
    openfoam.validate_bundle(bundle)
    text = openfoam._render_parabolic_u_field(
        bundle['domain_origin_m'], bundle['domain_size_m'], bundle['mesh']['cells'],
        inlet['face'], inlet['condition']['velocity'], axis)
    vectors = np.asarray([[float(x) for x in v.split()] for v in re.findall(r'\(([^()]+)\)', text)
                          if len(v.split()) == 3])
    centers = openfoam._blockmesh_patch_face_centers(
        bundle['domain_origin_m'], bundle['domain_size_m'], bundle['mesh']['cells'], inlet['face'])
    fraction = np.asarray(centers)[:, axis] / bundle['domain_size_m'][axis]
    expected = (4 * fraction * (1 - fraction))[:, None] * inlet['condition']['velocity']
    np.testing.assert_allclose(vectors, expected, rtol=1e-10, atol=1e-12)
    assert np.ptp(np.linalg.norm(vectors, axis=1)) > 0


def test_channel_physical_recipe_and_analytic_pressure_gradient():
    spec, bundle, analytic = openfoam.channel_poiseuille_case(8, lx=8, ly=2, u_max=2, nu=.1, rho=3, mach=.02)
    assert spec['shape'] == [33, 9, 4]
    assert spec['dx'] == .25
    assert (spec['speed'], spec['viscosity'], spec['density'], spec['mach']) == (2, .1, 3, .02)
    assert spec['collision'] == 'bgk' and spec['boundary_method'] == 'hawa-nee-v1'
    assert spec['initial_velocity'] == [4/3, 0, 0]
    assert bundle['dimensions'] == 2
    assert bundle['domain_origin_m'] == [0, 0, 0]
    assert bundle['domain_size_m'] == [8, 2, .75]
    assert bundle['density_kg_m3'] == 3 and bundle['kinematic_viscosity_m2_s'] == .1
    assert bundle['reference_speed_m_s'] == 2 and bundle['reference_length_m'] == 2
    assert bundle['initial_velocity_m_s'] == [4/3, 0, 0]
    assert bundle['pressure_reference_pa'] == 0
    assert bundle['mesh'] == dict(cells=[32, 8, 1], solver='simpleFoam', max_iterations=2000,
                                  residual_tolerance=1e-7, delta_t=1.)
    assert [(p['id'], p['face']) for p in bundle['boundaries']] == [
        ('inlet', 'x-'), ('outlet', 'x+'), ('bottom', 'y-'), ('top', 'y+'), ('back', 'z-'), ('front', 'z+')]
    assert bundle['boundaries'][0]['condition'] == dict(type='velocity', profile='parabolic',
                                                      profile_axis=1, velocity=[2, 0, 0])
    assert [p['condition']['type'] for p in bundle['boundaries']] == ['velocity', 'pressure', 'wall', 'wall', 'periodic', 'periodic']
    coords = {p['id']: p['location_m'] for p in bundle['probes']}
    assert coords == dict(p_x1_mid=[2, 1, .375], p_x2_mid=[4, 1, .375], p_x3_mid=[6, 1, .375],
                         p_x2_y20=[4, .4, .375], p_x2_y35=[4, .7, .375],
                         p_x2_y65=[4, 1.3, .375], p_x2_y80=[4, 1.6, .375])
    assert analytic['dp_dx_pa_m'] == pytest.approx(-1.2)
    for pid, (x, y, z) in coords.items():
        expected = 2*y*(2-y)
        assert analytic['probes'][pid]['velocity_m_s'] == pytest.approx([expected, 0, 0])
        assert analytic['probes'][pid]['pressure_pa'] == pytest.approx(1.2*(8-x))
    assert set(analytic['pressure_pairs']) == {'dp_x1_x3', 'dp_x1_x2', 'dp_x2_x3'}
    for pid, distance in [('dp_x1_x3', 4), ('dp_x1_x2', 2), ('dp_x2_x3', 2)]:
        assert analytic['pressure_pairs'][pid] == pytest.approx(dict(delta_p_pa=1.2*distance,
                                                                    gradient_pa_m=-1.2, distance_m=distance))


def test_cavity_physical_recipe_and_moving_lid():
    cfg, bundle = openfoam.cavity_control_case(20, reynolds=25, mach=.03)
    assert cfg == dict(resolution=20, reynolds_number=25., mach_number=.03)
    assert bundle['domain_size_m'] == [1, 1, .1] and bundle['domain_origin_m'] == [0, 0, 0]
    assert bundle['dimensions'] == 2 and bundle['density_kg_m3'] == 1
    assert bundle['kinematic_viscosity_m2_s'] == .04
    assert bundle['reference_speed_m_s'] == bundle['reference_length_m'] == 1
    assert bundle['initial_velocity_m_s'] == [0, 0, 0] and bundle['pressure_reference_pa'] == 0
    assert bundle['mesh'] == dict(cells=[20, 20, 1], solver='simpleFoam', max_iterations=2000,
                                  residual_tolerance=1e-7, delta_t=1., p_ref_cell=0, p_ref_value=0.)
    assert [p['condition'] for p in bundle['boundaries']] == [
        {'type': 'wall', 'velocity': [0., 0., 0.]}, {'type': 'wall', 'velocity': [0., 0., 0.]},
        {'type': 'wall', 'velocity': [0., 0., 0.]}, {'type': 'wall', 'velocity': [1., 0., 0.]},
        {'type': 'periodic'}, {'type': 'periodic'}]
    assert [p['location_m'] for p in bundle['probes']] == [[.5, .25, .05], [.5, .5, .05], [.5, .75, .05],
                                                        [.25, .5, .05], [.75, .5, .05], [.25, .75, .05], [.75, .75, .05]]
    assert bundle['pressure_pairs'] == [dict(id='dp_upper_lr', a_probe_id='c_75_75', b_probe_id='c_25_75'),
                                        dict(id='dp_mid_lr', a_probe_id='c_75_50', b_probe_id='c_25_50')]


def test_pressure_pair_distance_sign_and_observable_drift():
    _, bundle, _ = openfoam.channel_poiseuille_case(10)
    probes = {p['id']: dict(pressure_pa=p['location_m'][0]*2, velocity_m_s=[1, 2, 3]) for p in bundle['probes']}
    pairs = openfoam._pressure_pairs_from_probes(bundle, probes)
    assert pairs['dp_x1_x3'] == dict(delta_p_pa=-4, gradient_pa_m=2, distance_m=2)
    current = {pid: dict(velocity_m_s=[1, 5, 7]) for pid in probes}
    cur_pairs = {pid: dict(delta_p_pa=row['delta_p_pa']+3) for pid, row in pairs.items()}
    assert openfoam._max_observable_drift(probes, current, pairs, cur_pairs, 10, 2) == 1.5
    assert openfoam._max_observable_drift(probes, current, pairs, cur_pairs, 2, 10) == 2.5


@pytest.mark.parametrize('case', ['channel_poiseuille_ny10', 'cavity_re10_n32'])
def test_generated_dictionaries_match_solver_verified_control_artifacts(case):
    # These fixtures come from the November 23 local OpenFOAM run artifacts,
    # verified against their original manifest hashes, not this test's renderer.
    import json
    from pathlib import Path
    fixture = json.loads((Path(__file__).parent / 'fixtures' / 'openfoam' / (case + '.json')).read_text())
    assert openfoam._render_openfoam_files(fixture['bundle']) == fixture['files']


def test_comparison_metrics_use_declared_velocity_and_pressure_scales():
    _, bundle, _ = openfoam.channel_poiseuille_case(10)
    bundle['probes'] = bundle['probes'][:2]
    bundle['pressure_pairs'] = [dict(id='dp', a_probe_id='p_x1_mid', b_probe_id='p_x2_mid')]
    h = dict(probes={p['id']: dict(velocity_m_s=[3, 4, 0], pressure_pa=7) for p in bundle['probes']},
             pressure_pairs={'dp': dict(delta_p_pa=4, gradient_pa_m=-2)})
    o = dict(probes={p['id']: dict(velocity_m_s=[0, 0, 0], pressure_pa=2) for p in bundle['probes']},
             pressure_pairs={'dp': dict(delta_p_pa=2, gradient_pa_m=-1)})
    a = dict(probes={p['id']: dict(velocity_m_s=[0, 0, 0], pressure_pa=2) for p in bundle['probes']},
             pressure_pairs={'dp': dict(delta_p_pa=1, gradient_pa_m=-.5)})
    result = openfoam.compare_probe_results(bundle, h, o, a, velocity_tol=10, pressure_tol=1)
    assert result['passed'] is True and result['failures'] == []
    assert result['case_id'] == bundle['case_id']
    assert result['velocity_l2_norm'] == result['velocity_linf_norm'] == 10
    assert result['pressure_pair_linf_norm'] == 1
    assert result['probes'] == [dict(id=p['id'], location_m=p['location_m'],
                                      hawa_velocity_m_s=[3, 4, 0], openfoam_velocity_m_s=[0, 0, 0],
                                      abs_velocity_err_m_s=5, norm_velocity_err=10,
                                      hawa_pressure_pa=7, openfoam_pressure_pa=2,
                                      analytic_velocity_m_s=[0, 0, 0], hawa_vs_analytic_norm_u=10,
                                      openfoam_vs_analytic_norm_u=0) for p in bundle['probes']]
    assert result['pressure_pairs'] == [dict(id='dp', hawa_delta_p_pa=4, openfoam_delta_p_pa=2,
                                            abs_delta_p_err_pa=2, norm_delta_p_err=1,
                                            hawa_gradient_pa_m=-2, openfoam_gradient_pa_m=-1,
                                            abs_gradient_err_pa_m=1, norm_gradient_err=.5, analytic_delta_p_pa=1,
                                            analytic_gradient_pa_m=-.5, hawa_vs_analytic_norm_dp=3,
                                            openfoam_vs_analytic_norm_dp=1)]
    # Nonzero q_ref is the fallback scale for a zero reference pressure drop.
    o['pressure_pairs']['dp']['delta_p_pa'] = 0
    result = openfoam.compare_probe_results(bundle, h, o)
    assert result['pressure_pair_linf_norm'] == pytest.approx(4 / .153125)
    bundle['pressure_pairs'] = []
    assert openfoam.compare_probe_results(bundle, h, o)['pressure_pair_linf_norm'] == 0


def test_omitted_render_defaults_match_explicit_physical_defaults():
    import copy
    _, bundle, _ = openfoam.channel_poiseuille_case(10)
    implicit = copy.deepcopy(bundle)
    implicit['mesh'] = {'cells': [40, 10, 1]}
    del implicit['pressure_reference_pa']
    del implicit['boundaries'][1]['condition']['pressure_pa']
    for patch in implicit['boundaries'][2:4]:
        del patch['condition']['velocity']
    explicit = copy.deepcopy(implicit)
    explicit['mesh'].update(solver='simpleFoam', max_iterations=1000, residual_tolerance=1e-9, delta_t=1.)
    explicit['pressure_reference_pa'] = 0.
    explicit['boundaries'][1]['condition']['pressure_pa'] = 0.
    for patch in explicit['boundaries'][2:4]:
        patch['condition']['velocity'] = [0., 0., 0.]
    openfoam.validate_bundle(implicit)
    assert openfoam._render_openfoam_files(implicit) == openfoam._render_openfoam_files(explicit)


def test_three_dimensional_cyclic_slip_pressure_units_and_transient_time():
    _, bundle, _ = openfoam.channel_poiseuille_case(10)
    bundle.update(dimensions=3, domain_origin_m=[10, 20, 30], domain_size_m=[4, 1, 2],
                  density_kg_m3=2., pressure_reference_pa=10., initial_velocity_m_s=[1, 2, 3])
    bundle['mesh'] = dict(cells=[4, 2, 3], solver='icoFoam', max_iterations=12, delta_t=.25,
                          residual_tolerance=.001, p_ref_cell=3, p_ref_value=4.)
    bundle['boundaries'][0]['condition'] = dict(type='velocity', velocity=[2, 3, 4])
    bundle['boundaries'][1]['condition'] = dict(type='pressure', pressure_pa=6.)
    bundle['boundaries'][2]['condition'] = dict(type='wall', velocity=[.5, 1, 1.5])
    bundle['boundaries'][3]['condition'] = dict(type='slip')
    files = openfoam._render_openfoam_files(bundle)
    assert 'hex (0 1 2 3 4 5 6 7) (4 2 3)' in files['system/blockMeshDict']
    assert '(10 20 30)' in files['system/blockMeshDict'] and '(14 21 32)' in files['system/blockMeshDict']
    assert 'neighbourPatch zMax;' in files['system/blockMeshDict']
    assert 'neighbourPatch zMin;' in files['system/blockMeshDict']
    assert 'uniform (1 2 3)' in files['0/U'] and 'uniform (2 3 4)' in files['0/U']
    assert 'uniform (0.5 1 1.5)' in files['0/U'] and 'type            slip;' in files['0/U']
    assert 'internalField   uniform 5;' in files['0/p'] and 'value           uniform 3;' in files['0/p']
    assert 'pRefCell        3;' in files['system/fvSolution'] and 'pRefValue       2;' in files['system/fvSolution']
    assert 'application     icoFoam;' in files['system/controlDict']
    assert 'endTime         3;' in files['system/controlDict'] and 'deltaT          0.25;' in files['system/controlDict']
    assert 'default         Euler;' in files['system/fvSchemes']


@pytest.mark.parametrize('version', ['v2506', 'v2312', '13', '', 'v2606-custom'])
def test_discovery_rejects_unqualified_openfoam_versions(version):
    def runner(cmd, timeout):
        return 0, 'VERSION=' + version + '\nOPTIONS=test\n' + '\n'.join(
            'TOOL:' + name + '=/bin/' + name for name in openfoam._REQUIRED_TOOLS), ''
    result = openfoam.detect_openfoam(launcher='/fake', runner=runner)
    assert result['available'] is False
    assert 'v2606' in result['reason']


@pytest.mark.parametrize('channels,cavities', [((), ((16, .05),)), ((10,), ()), ((), ())])
def test_control_suite_rejects_empty_required_inventory(tmp_path, channels, cavities):
    import compare_openfoam_controls as cli
    with pytest.raises(ValueError, match='nonempty'):
        cli.run_control_suite(tmp_path / 'out', channel_grids=channels, cavity_configs=cavities,
                              runner=lambda cmd, timeout: (1, '', 'no'))
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('failure', [None, 'convergence', 'settling', 'comparison', 'sensitivity'])
def test_suite_requires_every_channel_gate_and_preserves_run_metadata(tmp_path, monkeypatch, failure):
    import compare_openfoam_controls as cli
    monkeypatch.setattr(cli, 'detect_openfoam', lambda **kw: {'available': True, 'version': 'v2606'})
    monkeypatch.setattr(cli, 'git_provenance', lambda root: {'commit': 'source', 'dirty': False})
    monkeypatch.setattr(cli.platform, 'platform', lambda: 'test-platform')
    writes, foam_runs, hawa_channels, hawa_cavities = [], [], [], []

    def write(bundle, root, overwrite):
        assert overwrite is True
        writes.append(root)
        return {'openfoam_dir': root / 'openfoam'}

    def foam(path, bundle, launcher, runner):
        assert launcher == '/test/foam' and runner == 'runner-token'
        foam_runs.append(path)
        return dict(solver='simpleFoam', converged=failure != 'convergence', sample_time=123,
                    check_mesh={'mesh_ok': True}, probes={}, pressure_pairs={})

    def hawa_channel(spec, bundle, **kwargs):
        hawa_channels.append(kwargs)
        return dict(device='cpu', dtype='torch.float32', steps=321, physical_time_s=2.5, tau=.7,
                    settled=failure != 'settling', final_drift=.0001, relative_mass_change=.0002)

    def hawa_cavity(cfg, bundle, **kwargs):
        hawa_cavities.append(kwargs)
        return dict(device='cpu', dtype='torch.float64', steps=456, physical_time_s=3., tau=.8)

    def compare(bundle, h, o, **kwargs):
        if 'channel' in bundle['case_id']:
            assert kwargs['velocity_tol'] == .02 and kwargs['pressure_tol'] == .05
            assert kwargs['analytic']['dp_dx_pa_m'] == pytest.approx(-.1225)
        return dict(passed=failure != 'comparison', velocity_l2_norm=(1 if failure == 'sensitivity'
                    else 1 / bundle['mesh']['cells'][1]))

    monkeypatch.setattr(cli, 'write_openfoam_case', write)
    monkeypatch.setattr(cli, 'run_openfoam_case', foam)
    monkeypatch.setattr(cli, 'run_hawa_channel', hawa_channel)
    monkeypatch.setattr(cli, 'run_hawa_cavity', hawa_cavity)
    monkeypatch.setattr(cli, 'compare_probe_results', compare)
    result = cli.run_control_suite(tmp_path, channel_grids=(20, 40), cavity_configs=((16, .05), (16, .015)),
                                  launcher='/test/foam', runner='runner-token', channel_max_steps=777,
                                  cavity_target_time_s=4.5)
    assert result['status'] == ('COMPLETED' if failure is None else 'FAILED')
    assert result['adapter_version'] == openfoam.ADAPTER_VERSION
    assert result['platform'] == 'test-platform' and result['provenance'] == {'commit': 'source', 'dirty': False}
    assert result['openfoam'] == {'available': True, 'version': 'v2606'}
    assert result['monotonic_channel_velocity_convergence'] is (failure != 'sensitivity')
    assert len(writes) == len(foam_runs) == 3
    assert hawa_channels == [dict(device='cpu', max_steps=777, check_interval=1000, settle_tol=.001)] * 2
    assert hawa_cavities == [dict(device='cpu', dtype='float64', target_time_s=4.5)] * 2
    assert len(result['channel_cases']) == len(result['cavity_cases']) == 2
    for row, ny in zip(result['channel_cases'], (20, 40)):
        assert row == dict(ny_cells=ny, case_id=f'channel_poiseuille_ny{ny}', role='resolved_gate',
                          openfoam=dict(solver='simpleFoam', converged=failure != 'convergence', sample_time=123,
                                        check_mesh={'mesh_ok': True}),
                          hawa=dict(device='cpu', dtype='torch.float32', steps=321, physical_time_s=2.5, tau=.7,
                                    settled=failure != 'settling', final_drift=.0001, relative_mass_change=.0002),
                          comparison=dict(passed=failure != 'comparison', velocity_l2_norm=1 if failure == 'sensitivity' else 1/ny))
    for row, mach, suffix in zip(result['cavity_cases'], (.05, .015), ('0p05', '0p015')):
        assert row == dict(resolution=16, mach_number=mach, case_id='cavity_re10_n16_ma'+suffix,
                          openfoam=dict(solver='simpleFoam', converged=failure != 'convergence', sample_time=123,
                                        check_mesh={'mesh_ok': True}),
                          hawa=dict(device='cpu', dtype='torch.float64', steps=456, physical_time_s=3., tau=.8),
                          comparison=dict(passed=failure != 'comparison', velocity_l2_norm=1 if failure == 'sensitivity' else 1/16))


def test_cli_default_paths_device_and_failure_exit(tmp_path, monkeypatch, capsys):
    import json
    import compare_openfoam_controls as cli
    calls = []
    monkeypatch.setattr(cli, 'ROOT', tmp_path)

    def suite(output, device):
        calls.append((output, device))
        return {'status': 'FAILED', 'reason': 'test'}

    monkeypatch.setattr(cli, 'run_control_suite', suite)
    assert cli.main([]) == 1
    assert calls == [(str(tmp_path / 'results' / 'openfoam' / 'controls'), 'cpu')]
    report = tmp_path / 'docs' / 'verification-openfoam-controls.json'
    saved = json.loads(report.read_text())
    assert saved['status'] == 'FAILED' and saved['reason'] == 'test'
    assert len(saved['run_id']) == 32
    assert json.loads(capsys.readouterr().out) == {'status': 'FAILED', 'report': str(report)}


def test_comparison_rejects_overflowed_scales_and_derived_metrics():
    import copy
    _, bundle, analytic = openfoam.channel_poiseuille_case(10)
    result = {'probes': analytic['probes'], 'pressure_pairs': analytic['pressure_pairs']}
    for speed in (1e300, 1e-300):
        invalid = copy.deepcopy(bundle)
        invalid['reference_speed_m_s'] = speed
        with pytest.raises(ValueError, match='pressure scale'):
            openfoam.compare_probe_results(invalid, result, result)
    bad = copy.deepcopy(result)
    bad['pressure_pairs']['dp_x1_x3']['delta_p_pa'] = 1e308
    ref = copy.deepcopy(result)
    ref['pressure_pairs']['dp_x1_x3']['delta_p_pa'] = -1e308
    with pytest.raises(ValueError, match='Out of range float'):
        openfoam.compare_probe_results(bundle, bad, ref)


def test_gradient_disagreement_cannot_pass_pressure_gate():
    import copy
    _, bundle, analytic = openfoam.channel_poiseuille_case(10)
    original = {'probes': analytic['probes'], 'pressure_pairs': analytic['pressure_pairs']}
    altered = copy.deepcopy(original)
    altered['pressure_pairs']['dp_x1_x3']['gradient_pa_m'] = 123456.
    result = openfoam.compare_probe_results(bundle, altered, original, velocity_tol=.02, pressure_tol=.05)
    assert result['passed'] is False
    assert len(result['failures']) == 1 and 'norm_gradient_err' in result['failures'][0]
    assert result['pressure_pairs'][0]['norm_delta_p_err'] == 0
    assert result['pressure_pairs'][0]['abs_gradient_err_pa_m'] == pytest.approx(123456.1225)
    assert result['pressure_pairs'][0]['norm_gradient_err'] == pytest.approx(123456.1225 * 2 / .245)


def test_cli_failed_rerun_replaces_old_completed_report_before_work(tmp_path, monkeypatch):
    import json
    import compare_openfoam_controls as cli
    path = tmp_path / 'report.json'
    path.write_text(json.dumps({'status': 'COMPLETED', 'run_id': 'old'}))
    observed = []

    def fail(output, device):
        observed.append(json.loads(path.read_text()))
        raise RuntimeError('solver failed')

    monkeypatch.setattr(cli, 'run_control_suite', fail)
    with pytest.raises(RuntimeError, match='solver failed'):
        cli.main(['--report', str(path), '--output-dir', str(tmp_path / 'case')])
    final = json.loads(path.read_text())
    assert observed[0]['status'] == 'RUNNING'
    assert final == dict(status='FAILED', run_id=observed[0]['run_id'], reason='solver failed')
    assert len(final['run_id']) == 32 and final['run_id'] != 'old'


def test_real_control_runners_preserve_units_steps_and_probe_identity():
    import math
    spec, bundle, _ = openfoam.channel_poiseuille_case(8)
    result = openfoam.run_hawa_channel(spec, bundle, max_steps=35, check_interval=20, settle_tol=1e-12)
    dt = spec['mach'] * spec['dx'] / (math.sqrt(3) * spec['speed'])
    assert result['device'] == 'cpu' and result['dtype'] == 'torch.float32'
    assert result['steps'] == 35 and result['settled'] is False
    assert result['physical_time_s'] == pytest.approx(35 * dt)
    assert result['tau'] == pytest.approx(.5 + 3 * spec['viscosity'] * dt / spec['dx']**2)
    assert result['final_drift'] > 1e-12 and abs(result['relative_mass_change']) < .05
    assert set(result['pressure_pairs']) == {pair['id'] for pair in bundle['pressure_pairs']}
    for probe in bundle['probes']:
        assert result['probes'][probe['id']]['location_m'] == probe['location_m']
    cfg, cavity = openfoam.cavity_control_case(16, reynolds=10, mach=.05)
    result = openfoam.run_hawa_cavity(cfg, cavity, target_time_s=.05)
    dt = .05 / (math.sqrt(3) * 16)
    assert result['device'] == 'cpu' and result['dtype'] == 'torch.float64'
    assert result['steps'] == round(.05 / dt)
    assert result['physical_time_s'] == pytest.approx(result['steps'] * dt)
    assert result['tau'] == pytest.approx(.5 + 3 * .1 * dt * 16**2)
    assert result['resolution'] == 16 and result['mach_number'] == .05
    assert set(result['pressure_pairs']) == {pair['id'] for pair in cavity['pressure_pairs']}
