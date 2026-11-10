import json
import math
from pathlib import Path
import sys

import pytest
import torch
import lettuce as lt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import verify_atmospheric_precision as precision


def test_shear_wave_initial_amplitude_and_contract():
    flow = precision.ShearWave(lt.Context('cpu', torch.float64, use_native=False), 16, .1, 1e-3)
    assert precision.amplitude(flow) == pytest.approx(.1*.05/math.sqrt(3), rel=1e-12)
    # Mean flow is perpendicular to the wave and density starts at the reference.
    assert flow.u()[2].mean().item() == pytest.approx(.05/math.sqrt(3), rel=1e-12)
    torch.testing.assert_close(flow.rho(), torch.ones_like(flow.rho()), atol=1e-15, rtol=0)
    assert flow.post_boundaries == []
    with pytest.raises(NotImplementedError):
        flow.initial_pu()


def test_fp64_decay_matches_analytic_viscosity_and_rejects_short_runs():
    # nu_lu = margin/3; the analytic shear-wave decay gives delta_ratio = 1.
    result = precision.measure(1., 0., .01, 'cpu', torch.float64, n=16, steps=1000, sample=50, margin=1e-2)
    assert result['delta_ratio'] == pytest.approx(1., abs=.02)
    assert result['physical_time_s'] == pytest.approx(1000*.05/(math.sqrt(3)*5.))
    assert result['storage']['molecular_status'] == 'resolved'
    with pytest.raises(ValueError):
        precision.measure(1., 0., .01, steps=500, sample=100)
    with pytest.raises(ValueError):
        precision.measure(1., 0., .01, steps=1050, sample=100)


def test_vanished_amplitude_is_an_error_not_a_fit(monkeypatch):
    monkeypatch.setattr(precision, 'amplitude', lambda flow: 0.)
    with pytest.raises(RuntimeError, match='vanished'):
        precision.measure(1., 0., .01, n=16, steps=100, sample=10)


def test_compare_flags_disagreement_between_measurement_and_diagnostic():
    reference = dict(delta_effective=2.)
    close = dict(delta_effective=2.08, storage=dict(model_status='below-storage-precision'))
    result = precision.compare(reference, close)
    assert result['relative_error_vs_fp64'] == pytest.approx(.04)
    assert result['represented'] and not result['diagnostic_predicted_resolved']
    assert result['diagnostic_agrees'] is False
    far = dict(delta_effective=-1., storage=dict(model_status='below-storage-precision'))
    assert precision.compare(reference, far)['diagnostic_agrees'] is True


def test_fp32_physical_air_loses_molecular_dissipation_and_main_reports_it(tmp_path, monkeypatch):
    cases = {'physical': [dict(dx=10., cs=0., wave=.01, n=16, steps=2000, sample=50)]}
    rows, summary = precision.run(['cpu'], cases)
    fp32 = rows[0]['fp32']['cpu']
    # FP64 keeps the 2.6e-8 molecular increment; FP32 storage cannot.
    assert rows[0]['reference_fp64']['delta_ratio'] == pytest.approx(1., abs=.05)
    assert fp32['represented'] is False and fp32['storage']['molecular_status'] == 'below-storage-precision'
    assert summary == dict(collision_fp64_represents_molecular=True, diagnostic_agrees_on_all_fp32_cases=True,
                           fp32_molecular_represented={'cpu:10.0': False}, passed=True)
    monkeypatch.setattr(precision, 'CASES', cases)
    output = tmp_path/'report.json'
    assert precision.main(['--output', str(output)]) == 0
    report = json.loads(output.read_text())
    assert report['passed'] is True and report['environment']['devices'] == ['cpu']
    # A collision that misrepresents molecular viscosity fails the exit gate.
    monkeypatch.setattr(precision, 'run', lambda devices: ([], dict(passed=False)))
    assert precision.main(['--output', str(output), '--device', 'cpu']) == 2
