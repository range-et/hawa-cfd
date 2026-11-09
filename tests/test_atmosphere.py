import numpy as np
import pytest

from hawa.atmosphere import neutral_profile, neutral_wall_traction, scaling_report


def test_profile_and_wall_law_consistency():
    heights = np.array([1., 2., 5., 10., 20.])
    velocity = neutral_profile(heights, [3., 4., 0.], 10., .1)
    np.testing.assert_allclose(neutral_profile(0., [3., 4., 0.], 10., .1), 0)
    np.testing.assert_allclose(velocity[3], [3., 4., 0.])
    expected_friction = .41*5/np.log(101.)
    for height, u in zip(heights, velocity):
        wall = neutral_wall_traction(u, height, .1)
        assert wall['friction_velocity_m_s'] == pytest.approx(expected_friction)
        np.testing.assert_allclose(wall['traction_on_fluid_pa'],
                                  -1.225*expected_friction**2*np.array([.6, .8, 0.]))


def test_stress_reversal_rotation_and_no_work_in_normal_direction():
    u = np.array([[2., 3., 9.], [0., 0., 0.]])
    wall = neutral_wall_traction(u, 1., .01)
    traction = wall['traction_on_fluid_pa']
    assert np.all(np.sum(traction*u, axis=-1) <= 0)
    np.testing.assert_array_equal(traction[:, 2], 0)
    np.testing.assert_allclose(neutral_wall_traction(-u, 1., .01)['traction_on_fluid_pa'], -traction)
    rotation = np.array([[0., 0., 1.], [1., 0., 0.], [0., 1., 0.]])
    rotated = neutral_wall_traction(u @ rotation.T, 1., .01, normal=rotation[:, 2])
    np.testing.assert_allclose(rotated['traction_on_fluid_pa'], traction @ rotation.T)
    # Drag is quadratic in tangential speed, linear in density.
    np.testing.assert_allclose(neutral_wall_traction(2*u, 1., .01)['traction_on_fluid_pa'], 4*traction)
    np.testing.assert_allclose(neutral_wall_traction(u, 1., .01, density_kg_m3=2.45)['traction_on_fluid_pa'], 2*traction)


@pytest.mark.parametrize('value',[0., -1., np.nan, np.inf, True, '1'])
def test_invalid_parameters(value):
    with pytest.raises(ValueError): neutral_profile([1.], [1., 0., 0.], 10., value)
    with pytest.raises(ValueError): neutral_wall_traction([1., 0., 0.], value, .1)
    with pytest.raises(ValueError): scaling_report(value, 5., 1.5e-5)


def test_invalid_geometry():
    with pytest.raises(ValueError, match='nonnegative'):
        neutral_profile([-1.], [1., 0., 0.], 10., .1)
    with pytest.raises(ValueError, match='tangential'):
        neutral_profile([1.], [1., 0., 1.], 10., .1)
    with pytest.raises(ValueError, match='unit vector'):
        neutral_wall_traction([1., 0., 0.], 1., .1, normal=[0., 0., 2.])
    with pytest.raises(ValueError, match='above'):
        neutral_wall_traction([1., 0., 0.], .1, .1)


def test_actual_air_scaling_and_production_rejection():
    from hawa.plugin import check_case
    values = [scaling_report(dx, 5., 1.5e-5) for dx in (.1, 1., 10.)]
    np.testing.assert_allclose([v['tau_minus_half'] for v in values],
                              np.sqrt(3)*1.5e-5*.05/(5*np.array([.1, 1., 10.])))
    assert [v['production_supported'] for v in values] == [True, False, False]
    assert values[-1]['fp32_rounds_to_half']
    for dx in (1., 10.):
        with pytest.raises(ValueError, match='no qualified coarse-grid atmospheric model'):
            check_case(dict(shape=[9, 9, 9], dx=dx, speed=5., viscosity=1.5e-5, collision='smagorinsky-v1'))


def test_preflight_reports_scaling_without_changing_legacy_case():
    from hawa.plugin import check_case, case_key
    spec = dict(shape=[9, 9, 9], dx=.1, speed=1., viscosity=.1)
    key = case_key(spec)
    report = check_case(spec)
    assert report['case_hash'] == key == case_key(spec)
    assert report['numerical_scaling']['production_supported']
    assert report['tau'] == report['numerical_scaling']['tau']


def test_numerical_range_is_explicit():
    for dx in (1e-300, 1e300):
        with pytest.raises(ValueError, match='numerical range'):
            scaling_report(dx, 5., 1.5e-5)
    # Finite heights with an overflowing direct h/z0 ratio remain meaningful.
    np.testing.assert_allclose(neutral_profile(1e200, [1., 0., 0.], 1e200, 1e-200), [1., 0., 0.])
    wall = neutral_wall_traction([1., 0., 0.], 1e200, 1e-200)
    assert np.isfinite(wall['traction_on_fluid_pa']).all()
