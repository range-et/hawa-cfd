"""Deterministic metamorphic controls for numerical utility contracts."""
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from hawa.atmosphere import neutral_profile, neutral_wall_traction, scaling_report
from hawa.flow_statistics import summarize
from hawa.step import coordinator


@pytest.mark.parametrize('scale', [.01, 1., 100.])
def test_neutral_relations_preserve_length_similarity_and_rotation(scale):
    rotation = np.array([[0., -1., 0.], [0., 0., 1.], [-1., 0., 0.]])
    normal = np.array([0., 0., 1.]); velocity = np.array([3., 4., 0.])
    heights = np.array([0., 1., 10., 100.])
    profile = neutral_profile(heights, velocity, 10., .01)
    transformed = neutral_profile(heights*scale, rotation@velocity, 10.*scale, .01*scale, rotation@normal)
    np.testing.assert_allclose(transformed, profile@rotation.T, atol=1e-12)
    np.testing.assert_array_equal(profile[0], np.zeros(3))
    np.testing.assert_allclose(profile[2], velocity, atol=1e-12)
    wall = neutral_wall_traction(velocity + 9*normal, 1., .01)
    transformed_wall = neutral_wall_traction(rotation@(velocity + 9*normal), scale, .01*scale, normal=rotation@normal)
    np.testing.assert_allclose(transformed_wall['traction_on_fluid_pa'], rotation@wall['traction_on_fluid_pa'], atol=1e-12)
    assert transformed_wall['friction_velocity_m_s'] == pytest.approx(wall['friction_velocity_m_s'])
    assert wall['traction_on_fluid_pa']@velocity < 0
    assert wall['traction_on_fluid_pa']@normal == 0


@pytest.mark.parametrize('bad', [True, '1', None, -1, 0, np.nan, np.inf])
def test_scaling_rejects_nonpositive_or_non_numeric_inputs(bad):
    for index in range(4):
        args = [1., 2., .01, .05]; args[index] = bad
        with pytest.raises(ValueError, match='finite positive'): scaling_report(*args)


@pytest.mark.parametrize('dx', [1e-200, 1e200])
def test_scaling_extreme_lengths_fail_before_misleading_report(dx):
    with pytest.raises(ValueError, match='numerical range'): scaling_report(dx, 1., .01)


def test_log_profile_extreme_height_ratio_remains_finite():
    result = neutral_profile([0., 1e-100, 1e100], [1., 0., 0.], 1., 1e-200)
    np.testing.assert_allclose(result[:, 0], [0., .5, 1.5], atol=1e-12)
    assert np.isfinite(result).all()


def test_traction_zero_and_overflow_are_explicit():
    result = neutral_wall_traction([[0., 0., 0.], [0., 0., 12.]], 1., .01)
    np.testing.assert_array_equal(result['traction_on_fluid_pa'], np.zeros((2,3)))
    np.testing.assert_array_equal(result['friction_velocity_m_s'], [0.,0.])
    with np.errstate(over='ignore', invalid='ignore'):
        with pytest.raises(ValueError, match='numerical range'):
            neutral_wall_traction([1e200, 1e200, 0.], 1., .01)


@pytest.mark.parametrize('samples', [8, 9, 64])
def test_statistics_covariance_rotation_and_time_scale(samples):
    time = np.arange(samples)*.25
    wave = np.sin(2*np.pi*np.arange(samples)/samples)
    velocity = np.stack((2+wave, 3+2*wave, np.ones(samples)), axis=-1)[:,None,:]
    pressure = np.arange(samples)[:,None]*.1
    rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0.,0.,1.]])
    report = summarize(time, velocity, pressure)
    transformed = summarize(3*time + 100., velocity@rotation.T, pressure+4.)
    np.testing.assert_allclose(transformed['mean_velocity'], np.asarray(report['mean_velocity'])@rotation.T, atol=1e-12)
    np.testing.assert_allclose(transformed['reynolds_covariance'], rotation@np.asarray(report['reynolds_covariance'])@rotation.T, atol=1e-12)
    np.testing.assert_allclose(transformed['resolved_tke'], report['resolved_tke'], atol=1e-12)
    np.testing.assert_allclose(transformed['mean_pressure'], np.asarray(report['mean_pressure'])+4.)
    np.testing.assert_allclose(transformed['frequency_hz'], np.asarray(report['frequency_hz'])/3.)
    np.testing.assert_allclose(np.asarray(report['reynolds_covariance'])[0], [[.5,1.,0.],[1.,2.,0.],[0.,0.,0.]], atol=1e-12)
    assert report['samples'] == samples and report['duration_seconds'] == time[-1]
    assert report['resolved_tke'][0] == pytest.approx(1.25)


def test_step_coordinator_orders_callbacks_and_accounts_each_stage():
    state = torch.tensor([[[1., 2., 99.]]])
    log=[]
    flow=SimpleNamespace(solid=torch.tensor([[False,False,True]]),rho=lambda:state)
    def collide():
        log.append('collision'); state[0,0,:2] += 1.
    def stream():
        log.append('stream'); state[0,0,:2] += 3.
    simulation=SimpleNamespace(flow=flow,_collide=collide,_stream=stream,general_boundary=SimpleNamespace(report={}))
    step=coordinator(simulation)
    assert coordinator(simulation) is step and simulation._collide_and_stream is step
    def post_collision(): log.append('post-collision'); state[0,0,:2] += 2.
    def post_stream(): log.append('post-stream'); state[0,0,:2] += 4.
    step.register('walls', post_collision, post_stream)
    with pytest.raises(ValueError,match='Duplicate'): step.register('walls')
    step()
    assert log == ['collision','post-collision','stream','post-stream']
    report=simulation.general_boundary.report
    assert report['fluid_mass_lu']==23. and report['storage_change_lu']==20.
    assert report['collision_change_lu']==2. and report['streaming_exchange_lu']==10. and report['reconstruction_change_lu']==8.
    assert 'not a physical flux conservation test' in report['mass_accounting_scope']
    # Extensions are valid without optional boundary diagnostics, too.
    del simulation.general_boundary
    log.clear(); step()
    assert log == ['collision','post-collision','stream','post-stream']
