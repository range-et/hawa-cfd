"""HAWA-004 reflection harness: protocol settings, metrics and small real runs.

Protocol values come from docs/boundary-reflection-review.md, not from the
harness. Small runs check behavior with physical expectations; they are not the
qualification measurements, which use the full-size CASES.
"""
import importlib.util
import json
import math
from pathlib import Path
import runpy
import sys

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'scripts'/'verify_boundary_reflection.py'
spec = importlib.util.spec_from_file_location('verify_boundary_reflection', SCRIPT)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

C = 1/math.sqrt(3)
U = .05/math.sqrt(3)  # 5 m/s at Mach 0.05 on the 5 m/s scale


def test_declared_criteria_and_lattice_scale():
    assert v.CRITERIA == dict(acoustic=.10, vortex=.10, uniform_m_s=3e-5, mass_lu=1e-10, reversal_mean=.02,
                              reversal_node=.05, cut_interior_l2=.02, cut_interior_linf=.05, cut_band_l2=.05,
                              cut_band_linf=.10, settled=.01)
    assert v.lattice_speed(5.) == pytest.approx(U, rel=1e-15)
    assert v.lattice_speed(-1.) == pytest.approx(-U/5, rel=1e-15)
    assert v.SOUND == pytest.approx(C, rel=1e-15)


def test_specs_and_faces_for_both_systems():
    from hawa.atmosphere import scaling_report
    s = v.spec_for('S', (8, 6, 4), v.faces_x('S', (5., 0., 0.)), dx=2.)
    assert s['boundary_method'] == 'shifted-links-v1' and s['collision'] == 'shifted-regularized-sgs-v1'
    assert s['shape'] == [8, 6, 4] and s['dx'] == 2. and s['speed'] == 5. and s['mach'] == .05
    assert s['density'] == 1.225 and s['viscosity'] == 1.5e-5
    assert s['neutral_precursor'] == dict(schema=1, experimental=True, mode='external', perturbation_fraction=0.,
                                          reference_height_m=4., roughness_length_m=.02, smagorinsky_constant=.17)
    assert [p['face'] for p in s['boundary_set']['patches']] == ['x-', 'x+', 'y-', 'y+', 'z-', 'z+']
    assert [p['condition']['type'] for p in s['boundary_set']['patches']] == ['velocity', 'open', 'periodic', 'periodic', 'wall', 'slip']
    assert s['boundary_set']['patches'][0]['condition']['velocity'] == [5., 0., 0.]
    assert s['boundary_set']['patches'][1]['condition'] == dict(type='open', velocity=[0., 0., 0.])
    n = v.spec_for('N', (8, 6, 4), v.faces_x('N', (5., 0., 0.)))
    assert n['boundary_method'] == 'hawa-nee-v1' and n['collision'] == 'regularized'
    assert n['initial_velocity'] == [0., 0., 0.] and 'neutral_precursor' not in n
    assert scaling_report(1., 5., n['viscosity'])['tau_minus_half'] == pytest.approx(.01, rel=1e-12)
    assert [p['condition']['type'] for p in n['boundary_set']['patches']][4:] == ['periodic', 'periodic']
    custom = dict(type='open', velocity=[0., 0., 0.], backflow_mode='pressure')
    assert v.faces_x('S', (1., 2., 0.), custom)[1] is custom
    assert v.spec_for('S', (8, 6, 4), v.faces_x('S', (5., 0., 0.)), viscosity=.3, cs=0.)['viscosity'] == .3
    with pytest.raises(ValueError, match='S or N'):
        v.spec_for('X', (8, 6, 4), [])


def test_block_occupancy_and_halo():
    def block(c):
        return (c[0] >= 5) & (c[1] == 2)
    s = v.spec_for('S', (6, 4, 4), v.faces_x('S', (5., 0., 0.)), block=block)
    halo = np.zeros((8, 6, 6), bool); halo.flat[s['solid_halo']] = True
    solid = np.zeros((6, 4, 4), bool); solid.flat[s['solid']] = True
    assert np.array_equal(halo[1:-1, 1:-1, 1:-1], solid)
    assert solid.sum() == 4 and solid[5, 2].all() and halo[6:, 3].all() and halo.sum() == 2*6
    n = v.spec_for('N', (6, 4, 4), v.faces_x('N', (5., 0., 0.)), block=block)
    assert n['solid'] == s['solid'] and 'solid_halo' not in n


@pytest.mark.parametrize('system', ['S', 'N'])
def test_build_state_roundtrip_and_incoming_count(system):
    spec = v.spec_for(system, (8, 6, 4), v.faces_x(system, (5., 0., 0.)), block=lambda c: (c[0] == 3) & (c[1] == 2))
    flow, solver = v.build(spec)
    assert flow.f.dtype == torch.float64 and flow.f.device.type == 'cpu'
    if system == 'S':
        assert solver.rough_floor.factor == 0.
    else:
        assert not hasattr(solver, 'rough_floor')
    rng = np.random.default_rng(4)
    delta = 1e-3*rng.standard_normal(flow.resolution); u = 1e-2*rng.standard_normal((3, *flow.resolution))
    v.set_state(flow, delta, u)
    solid = flow.solid.numpy()
    d, w = v.state(flow)
    np.testing.assert_allclose(d[~solid], delta[~solid], rtol=0, atol=1e-15)
    np.testing.assert_allclose(w[:, ~solid], u[:, ~solid], rtol=0, atol=1e-14)
    assert not d[solid].any() and not w[:, solid].any() and solid.sum() == 4
    assert v.finite([(flow,)])
    u[0] = -U; v.set_state(flow, np.zeros(flow.resolution), u); solver(1)
    assert v.incoming_links(solver) > 0
    flow.f[0, 0, 0, 0] = float('nan')
    assert not v.finite([(flow,)])
    assert v.build(spec, torch.float32)[0].f.dtype == torch.float32


def test_taylor_vortex_is_an_exact_incompressible_balance():
    u, w, p = v.taylor((41, 41), (20., 20.), 5., .1)
    speed = np.hypot(u, w)
    assert speed[20, 20] == 0 and speed[25, 20] == pytest.approx(.1) and speed[20, 15] == pytest.approx(.1)
    assert w[25, 20] == pytest.approx(.1) and u[20, 25] == pytest.approx(-.1)
    assert p[20, 20] == pytest.approx(-.5*.01*math.e) and p.max() < 0
    # dp/dr = u_theta^2/r along +x (central difference, analytic profile).
    r = 7.; h = 1e-4
    def pressure(radius):
        return -.5*.01*math.exp(1-(radius/5)**2)
    assert (pressure(r+h)-pressure(r-h))/(2*h) == pytest.approx((.1*r/5*math.exp(.5*(1-(r/5)**2)))**2/r, rel=1e-6)
    assert p[27, 20] == pytest.approx(pressure(7.)) and w[27, 20] == pytest.approx(.1*7/5*math.exp(.5*(1-49/25)))


def test_acoustic_protocol_and_causality():
    g = v.acoustic_setup()
    assert (g['n'], g['sigma'], g['amplitude'], g['centre'], g['reference_length'], g['offset'], g['direction']) == (64, 4., 1e-3, 32., 192, 0, 1)
    assert g['steps'] == math.ceil(32/(C+U)+60/(C-U)) == 163
    assert g['reference_return_steps'] == pytest.approx(160/(C+U)+128/(C-U))
    h = v.acoustic_setup(2, 'inlet')
    assert (h['n'], h['sigma'], h['offset'], h['reference_length'], h['direction']) == (128, 8., 256, 384, -1)
    assert h['steps'] == math.ceil(64/(C-U)+124/(C+U))
    assert h['reference_return_steps'] == pytest.approx(320/(C-U)+256/(C+U))
    with pytest.raises(ValueError, match='outlet or inlet'):
        v.acoustic_setup(side='top')
    with pytest.raises(ValueError, match='causal'):
        v.acoustic('S', scale=.25, steps=10**4)


@pytest.mark.parametrize('system', ['S', 'N'])
def test_acoustic_pressure_dirichlet_faces_reflect(system):
    before = v.acoustic(system, scale=.25, steps=0)
    assert before['history_max_every_10'] == [0.] and before['reflection'] == 0.
    r = v.acoustic(system, scale=.25)
    # 36 requested steps; samples every 10 steps, so 30 were run and measured.
    assert (r['case'], r['system'], r['scale'], r['dtype']) == ('A1', system, .25, 'torch.float64')
    assert (r['requested_steps'], r['steps']) == (36, 30)
    assert len(r['history_max_every_10']) == 4 and r['history_max_every_10'][0] == 0.
    assert r['reflection'] == max(r['history_max_every_10'])
    # A held exterior pressure reflects an incident pulse with order-one amplitude.
    assert .4 < r['reflection'] < 1.5 and r['finite'] and r['criterion'] == .10 and r['passed'] is False
    i = v.acoustic(system, scale=.25, side='inlet')
    assert (i['case'], i['criterion'], i['passed'], i['requested_steps'], i['steps']) == ('A2', None, None, 35, 30)
    assert .4 < i['reflection'] < 1.5


def test_finite_requires_finite_populations_and_metrics():
    flow, _ = v.build(v.spec_for('S', (6, 6, 4), v.faces_x('S', (5., 0., 0.))))
    assert v.finite([(flow,)]) and v.finite([(flow,)], 0., .2)
    assert not v.finite([(flow,)], .2, float('nan')) and not v.finite([(flow,)], float('inf'))


def nan_state_on_call(monkeypatch, call):
    """A finite run whose `call`-th sampled state is NaN, as after a transient blow-up."""
    original, calls = v.state, []

    def state(flow):
        calls.append(1)
        delta, u = original(flow)
        return (delta*np.nan, u*np.nan) if len(calls) == call else (delta, u)
    monkeypatch.setattr(v, 'state', state)


# max() keeps an earlier passing value when a later sample is NaN.
def test_acoustic_and_vortex_reject_a_nan_metric_sample(monkeypatch):
    monkeypatch.setitem(v.CRITERIA, 'acoustic', 10.)
    monkeypatch.setitem(v.CRITERIA, 'vortex', 10.)
    nan_state_on_call(monkeypatch, 3)
    a = v.acoustic('S', scale=.25, steps=20)
    assert math.isnan(a['history_max_every_10'][1]) and a['finite'] is False and a['passed'] is False
    nan_state_on_call(monkeypatch, 3)
    w = v.vortex('S', scale=.25, steps=20)
    assert math.isnan(w['history_max_every_10'][1]) and w['finite'] is False and w['passed'] is False


def test_cut_face_nan_metric_is_inconclusive(monkeypatch):
    seen = []
    original = v.cut_status
    monkeypatch.setattr(v, 'cut_status', lambda ok, *a: seen.append(ok) or original(ok, *a))
    nan_state_on_call(monkeypatch, 3)  # the small domain at the end of the window
    r = v.cut_face('S', flowthroughs=.005, scale=.5)
    assert seen == [False] and r['finite'] is False and r['status'] == 'INCONCLUSIVE'


class NanAfter:
    """Solver wrapper that corrupts the flow or its mass report on call `last`."""

    def __init__(self, flow, solver, last, target):
        self.flow, self.solver, self.last, self.target, self.calls = flow, solver, last, target, 0
        self.external_links = solver.external_links

    def __call__(self, n):
        self.solver(n)
        self.calls += 1
        if self.calls == self.last:
            if self.target == 'population':
                self.flow.f[:, 5, 1, 1] = float('nan')
            else:
                self.external_links.report['mass_budget_residual_lu'] = float('nan')


def test_cut_face_backflow_counts_the_small_domain_face(monkeypatch):
    built, original = [], v.build
    monkeypatch.setattr(v, 'build', lambda *a: (lambda f, s: built.append(s) or (f, s))(*original(*a)))
    monkeypatch.setattr(v, 'incoming_links', lambda solver: 5 if solver is built[0] else 0)
    r = v.cut_face('S', flowthroughs=.005, scale=.5)
    assert len(built) == 2 and r['incoming_open_at_end'] == 5 and r['separated_cut'] is True


@pytest.mark.parametrize('target', ['population', 'mass'])
def test_reversal_rejects_nan_after_both_branches(target, monkeypatch):
    dt = .05*3/(math.sqrt(3)*5)
    last = math.ceil(2*2*1.225*63/20/dt)//10  # the final 10-step call
    original = v.build
    monkeypatch.setattr(v, 'build', lambda *a: (lambda f, s: (f, NanAfter(f, s, last, target)))(*original(*a)))
    r = v.reversal(dx=3.)
    assert r['incoming_observed'] == dict(outlet=True, inlet=True)
    assert r['finite'] is False and r['passed'] is False
    nan = r['max_node_error_m_s'] if target == 'population' else r['max_mass_budget_residual_lu']
    assert math.isnan(nan)


def test_uniform_corner_accepts_an_error_equal_to_the_criterion(monkeypatch):
    error = v.uniform_corner(torch.float32, steps=1)['max_velocity_error_m_s']
    assert error > 0
    monkeypatch.setitem(v.CRITERIA, 'uniform_m_s', error)
    assert v.uniform_corner(torch.float32, steps=1)['passed'] is True


def test_uniform_corner_rejects_a_nan_mass_report(monkeypatch):
    original = v.build
    monkeypatch.setattr(v, 'build', lambda *a: (lambda f, s: (f, NanAfter(f, s, 3, 'mass')))(*original(*a)))
    r = v.uniform_corner(steps=5)
    assert math.isnan(r['max_mass_budget_residual_lu']) and r['max_velocity_error_m_s'] < 1e-12
    assert r['finite'] is False and r['passed'] is False


def test_acoustic_pass_decision_uses_the_criterion(monkeypatch):
    monkeypatch.setitem(v.CRITERIA, 'acoustic', 10.)
    r = v.acoustic('S', scale=.25, steps=21)
    assert r['passed'] is True and (r['requested_steps'], r['steps'], len(r['history_max_every_10'])) == (21, 20, 3)


def test_vortex_protocol():
    g = v.vortex_setup()
    assert g['radius'] == 5. and list(g['direction']) == [1., 0.] and list(g['centre']) == [32., 24.]
    assert g['steps'] == math.ceil(62/U) == 2148
    assert g['shapes'] == [(64, 48), (math.ceil(32+U*(62/U)+40), 48)] == [(64, 48), (134, 48)]
    o = v.vortex_setup(oblique=True)
    assert list(o['direction']) == [.6, .8] and list(o['centre']) == [40., 32.]
    t = max(54/.6, 62/.8)/U
    assert o['steps'] == math.ceil(t) and o['shapes'] == [(64, 64), (math.ceil(32+.8*U*t+40),)*2]
    f = v.vortex_setup(2)
    assert f['radius'] == 10. and f['shapes'][0] == (128, 96) and list(f['centre']) == [64., 48.]


@pytest.mark.parametrize('system', ['S', 'N'])
def test_vortex_identical_until_the_face_is_reached(system):
    r = v.vortex(system, scale=.5, steps=21)  # sampled every 10 steps: 20 run
    assert (r['case'], r['system'], r['strength'], r['backflow_mode']) == ('V1', system, .5, 'velocity')
    assert (r['scale'], r['requested_steps'], r['steps'], r['finite']) == (.5, 21, 20, True)
    assert r['reference_shape'] == [67, 24] and r['history_max_every_10'][0] == 0.
    # Before the vortex reaches the face only its weak start-up transient differs.
    assert 0 < r['error'] < 1e-3 and r['passed'] is True and r['criterion'] == .10 and r['max_incoming_open'] == 0


def test_vortex_strong_pressure_and_oblique_variants(monkeypatch):
    r = v.vortex('S', scale=.5, steps=10, strength=1.5, backflow='pressure')
    assert (r['case'], r['backflow_mode'], r['strength']) == ('V2', 'pressure', 1.5)
    o = v.vortex('S', scale=.5, steps=10, oblique=True)
    assert o['case'] == 'C2' and o['reference_shape'][0] == o['reference_shape'][1] and o['error'] < 1e-2
    calls = []
    original = v.build
    def spy(spec, *args):
        calls.append([p['condition'] for p in spec['boundary_set']['patches']])
        return original(spec, *args)
    monkeypatch.setattr(v, 'build', spy)
    v.vortex('S', scale=.25, steps=0, oblique=True)
    assert calls[0][2] == dict(type='velocity', velocity=[3., 4., 0.])
    assert calls[0][3] == dict(type='open', velocity=[0., 0., 0.], backflow_mode='velocity')
    assert calls[0][0] == calls[0][2] and calls[0][1] == calls[0][3]


def test_vortex_failure_and_incoming_reporting(monkeypatch):
    monkeypatch.setitem(v.CRITERIA, 'vortex', -1.)
    r = v.vortex('S', scale=.25, steps=10)
    assert r['passed'] is False
    monkeypatch.setattr(v, 'incoming_links', lambda solver: 7)
    assert v.vortex('S', scale=.25, steps=10)['max_incoming_open'] == 7


@pytest.mark.parametrize('dtype', [torch.float64, torch.float32])
def test_uniform_oblique_corner_flow_is_preserved(dtype):
    r = v.uniform_corner(dtype, steps=5)
    assert (r['case'], r['system'], r['steps'], r['dtype'], r['criterion_m_s']) == ('C1', 'S', 5, str(dtype), 3e-5)
    assert r['max_velocity_error_m_s'] < (1e-12 if dtype == torch.float64 else 3e-5)
    assert r['max_mass_budget_residual_lu'] < (1e-13 if dtype == torch.float64 else 1e-5) and r['passed'] is True
    assert r['finite'] is True


def test_uniform_corner_failure_paths(monkeypatch):
    monkeypatch.setitem(v.CRITERIA, 'uniform_m_s', -1.)
    assert v.uniform_corner(steps=1)['passed'] is False
    monkeypatch.setitem(v.CRITERIA, 'uniform_m_s', 1.)
    monkeypatch.setitem(v.CRITERIA, 'mass_lu', -1.)
    assert v.uniform_corner(steps=1)['passed'] is False
    assert v.uniform_corner(torch.float32, steps=1)['passed'] is True


def test_reversal_protocol():
    g = v.reversal_setup()
    assert (g['nx'], g['length'], g['drop'], g['density'], g['start']) == (64, 63., 20., 1.225, -1.)
    assert g['period'] == pytest.approx(2*1.225*63/20)
    np.testing.assert_allclose(g['pressure'], 20*(1-np.arange(64)/63))
    f = v.reversal_setup(.5)
    assert f['nx'] == 127 and f['length'] == 63. and f['pressure'][0] == 20. and f['pressure'][-1] == 0.

def test_cut_protocol_and_status():
    assert v.cut_setup('S') == dict(n=40, ny=36, nz=12, edge=28, width=6, low=15)
    assert v.cut_setup('N') == dict(n=40, ny=36, nz=4, edge=28, width=6, low=15)
    assert v.cut_setup('S', .5) == dict(n=20, ny=18, nz=6, edge=14, width=3, low=8)
    good, edge = (.02, .05), (.05, .10)
    assert v.cut_status(True, .01, good, edge) == 'PASS'
    assert v.cut_status(False, 0., good, edge) == 'INCONCLUSIVE'
    assert v.cut_status(True, .0101, good, edge) == 'INCONCLUSIVE'
    for interior, band in (((.0201, .05), edge), ((.02, .0501), edge), (good, (.0501, .1)), (good, (.05, .1001))):
        assert v.cut_status(True, 0., interior, band) == 'FAIL'


@pytest.mark.parametrize('system', ['S', 'N'])
def test_cut_face_reports_comparison_and_settling(system, monkeypatch):
    r = v.cut_face(system, flowthroughs=.01, scale=.5)
    g = v.cut_setup(system, .5)
    assert r['shape'] == [20, 18, g['nz']] and r['reference_shape'] == [40, 18, g['nz']]
    assert r['steps'] == math.ceil(.01*40/U) and r['case'] == 'K1' and r['finite']
    # One short window cannot be settled.
    assert r['settled_change'] > .01 and r['status'] == 'INCONCLUSIVE' and r['passed'] is False
    # The face is the only difference, so the band nearest it differs most.
    assert 0 < r['interior_l2'] < r['band_l2'] and r['interior_linf_over_u'] < r['band_linf_over_u']
    assert r['separated_cut'] is (r['incoming_open_at_end'] > 0)
    monkeypatch.setattr(v, 'cut_status', lambda *a: 'PASS')
    monkeypatch.setattr(v, 'incoming_links', lambda solver: 3)
    p = v.cut_face(system, flowthroughs=.005, scale=.5)
    assert p['passed'] is True and p['separated_cut'] is True and p['incoming_open_at_end'] == 3


def test_case_inventory_matches_protocol_rows():
    assert set(v.CASES) == {'A1-S', 'A1-N', 'A1-S-fp32', 'A1-N-fp32', 'A1-S-fine', 'A2-S', 'A2-N', 'V1-S', 'V1-N',
                            'V1-S-fp32', 'V1-N-fp32', 'V1-S-fine', 'V2-S', 'V2-S-pressure', 'C1-S', 'C1-S-fp32',
                            'C2-S', 'C2-S-fp32', 'R1-S', 'R1-S-fine', 'R1-S-fp32',
                            'K1-S', 'K1-N', 'K1-S-fp32', 'K1-N-fp32'}
    for name, (function, arguments) in v.CASES.items():
        assert (arguments.get('dtype') == torch.float32) == name.endswith('-fp32'), name
        assert arguments.get('system', 'S') == name.split('-')[1], name
    assert v.CASES['V2-S'][1] == dict(system='S', strength=1.5)
    assert v.CASES['V2-S-pressure'][1] == dict(system='S', strength=1.5, backflow='pressure')
    assert v.CASES['A2-N'][1] == dict(system='N', side='inlet') and v.CASES['C2-S'][1] == dict(system='S', oblique=True)
    assert v.CASES['R1-S-fine'][1] == dict(dx=.5) and v.CASES['A1-S-fine'][1] == dict(system='S', scale=2)
    assert v.CASES['V1-S-fine'][1] == dict(system='S', scale=2) and v.CASES['K1-N'][0] is v.cut_face
    assert [v.CASES[k][0] for k in ('A1-S', 'V1-S', 'C1-S', 'R1-S')] == [v.acoustic, v.vortex, v.uniform_corner, v.reversal]


def test_main_writes_reports_and_selects_rows(tmp_path, monkeypatch, capsys):
    seen = []
    def fake(device, value):
        seen.append(device); return dict(passed=value, history_max_every_10=[1.])
    monkeypatch.setattr(v, 'CASES', {'P': (fake, dict(value=True)), 'Q-fp32': (fake, dict(value=None)),
                                     'R': (fake, dict(value=False))})
    out = tmp_path/'nested'/'report.json'
    assert v.main(['--output', str(out), '--cases', 'P,Q-fp32']) == 0
    data = json.loads(out.read_text())
    assert data['criteria'] == v.CRITERIA and data['device'] == 'cpu' and data['physical_validation'] is False
    assert data['torch'] == torch.__version__ and list(data['cases']) == ['P', 'Q-fp32']
    assert data['cases']['P']['device'] == 'cpu' and data['cases']['P']['wall_seconds'] >= 0
    text = capsys.readouterr().out
    assert 'history_max_every_10' not in text and text.endswith('failed: none\n') and text.startswith('P {')
    assert v.main(['--output', str(out)]) == 1 and seen[-3:] == ['cpu']*3
    assert capsys.readouterr().out.endswith('failed: R\n')
    assert v.main(['--output', str(out), '--device', 'mps']) == 0 and seen[-1] == 'mps' and len(seen) == 6
    assert list(json.loads(out.read_text())['cases']) == ['Q-fp32']
    with pytest.raises(SystemExit, match='Unknown cases: X, Y'):
        v.main(['--output', str(out), '--cases', 'Y,P,X'])
    with pytest.raises(SystemExit, match='Only -fp32 rows run on mps'):
        v.main(['--output', str(out), '--device', 'mps', '--cases', 'Q-fp32,P'])
    assert len(seen) == 6


def test_script_entrypoint_runs_one_row(tmp_path, monkeypatch):
    out = tmp_path/'c1.json'
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--output', str(out), '--cases', 'C1-S-fp32'])
    with pytest.raises(SystemExit) as stop:
        runpy.run_path(str(SCRIPT), run_name='__main__')
    assert stop.value.code == 0 and json.loads(out.read_text())['cases']['C1-S-fp32']['passed'] is True


# Slowest real runs last, so fail-fast mutation runs stop early.
def test_pressure_driven_reversal_matches_plug_flow():
    r = v.reversal(dx=3.)
    dt = .05*3/(math.sqrt(3)*5)
    requested = math.ceil(2*2*1.225*63/20/dt)
    # Reported time and speed belong to the last 10-step sample actually run.
    assert requested % 10 and (r['requested_steps'], r['steps']) == (requested, requested//10*10)
    assert r['physical_seconds'] == pytest.approx(r['steps']*dt) and r['finite'] is True
    assert r['final_expected_m_s'] == pytest.approx(-1+20/(1.225*63)*r['steps']*dt)
    assert r['incoming_observed'] == dict(outlet=True, inlet=True)
    # Declared node reference, L=(Nx-1)dx. Before the time-consistent pressure
    # face, the drive acted half a cell outside each node: about 4/22 m/s here.
    assert r['max_mean_error_m_s'] < .02 and r['max_node_error_m_s'] < .05
    assert r['max_mass_budget_residual_lu'] < 1e-12 and r['passed'] is True
    assert (r['case'], r['system'], r['dx'], r['dtype']) == ('R1', 'S', 3., 'torch.float64')

def test_reversal_requires_both_branches_and_mass_budget(monkeypatch):
    early = v.reversal(dx=3., steps=100)
    assert early['incoming_observed'] == dict(outlet=True, inlet=False) and early['passed'] is False
    monkeypatch.setitem(v.CRITERIA, 'mass_lu', -1.)
    assert v.reversal(dx=3.)['passed'] is False
    assert v.reversal(dx=3., dtype=torch.float32)['passed'] is True


def test_cut_face_settling_window_spans_last_1000_steps(monkeypatch):
    calls = []
    original = v.build

    class Counting:
        def __init__(self, solver):
            self.solver, self.general_boundary = solver, solver.general_boundary

        def __call__(self, n):
            calls.append(n)
            return self.solver(n)

    monkeypatch.setattr(v, 'build', lambda spec, *args: (lambda f, s: (f, Counting(s)))(*original(spec, *args)))
    r = v.cut_face('N', flowthroughs=1.6, scale=.25)
    assert r['steps'] == math.ceil(1.6*20/U) and calls == [r['steps']-1000]*2+[1000]*2
