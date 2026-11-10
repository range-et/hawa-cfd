"""Public airfoil routing: independent data expectations and dimensional controls."""
import numpy as np
import pytest

from hawa.plugin import dispatch


def test_naca_defaults_and_explicit_trailing_edge():
    default = dispatch({'op': 'airfoil', 'action': 'naca', 'code': ' NACA 0012 '})
    assert default['name'] == 'NACA 0012'
    assert default['closed_trailing_edge'] is True
    xy = np.asarray(default['coordinates'])
    assert xy.shape == (161, 2)
    assert np.isfinite(xy).all()
    np.testing.assert_allclose(xy[:, 0], xy[::-1, 0], atol=1e-12)
    np.testing.assert_allclose(xy[:, 1], -xy[::-1, 1], atol=1e-12)
    assert np.ptp(xy[:, 0]) == pytest.approx(1)
    np.testing.assert_allclose(xy[0], xy[-1], atol=1e-12)
    opened = dispatch({'op': 'airfoil', 'action': 'naca', 'code': '0012',
                       'count': 41, 'closed': False})
    assert opened['closed_trailing_edge'] is False
    assert len(opened['coordinates']) == 41
    assert opened['coordinates'][0][1] - opened['coordinates'][-1][1] == pytest.approx(.00252)


def test_import_normalizes_translated_scaled_coordinates(tmp_path):
    path = tmp_path / 'scaled.dat'
    text = 'scaled foil\n4 0\n3 .2\n2 0\n3 -.2\n4 0\n'
    path.write_text(text)
    result = dispatch({'op': 'airfoil', 'action': 'import', 'path': str(path)})
    np.testing.assert_allclose(result['coordinates'], [[1, 0], [.5, .1], [0, 0], [.5, -.1], [1, 0]])
    assert result['name'] == 'scaled'
    assert result['original_text'] == text
    assert result['source'] == str(path.resolve())


def test_polar_metadata_sorting_and_degree_interpolation(tmp_path):
    path = tmp_path / 'polar.csv'
    path.write_text('alpha,cl,cd,cm\n4,.4,.02,0\n-4,-.4,.02,-.08\n0,0,.01,-.04\n')
    polar = dispatch({'op': 'airfoil', 'action': 'polar', 'path': str(path),
                      'reynolds': 100000, 'mach': .12})
    assert polar['source'] == str(path.resolve())
    assert polar['reynolds'] == 100000 and polar['mach'] == .12
    assert polar['columns'] == ['alpha', 'cl', 'cd', 'cm']
    assert [row[0] for row in polar['rows']] == [-4, 0, 4]
    result = dispatch({'op': 'airfoil', 'action': 'operating_point', 'polar': polar, 'alpha': 2})
    assert result == pytest.approx({'alpha': 2, 'cl': .2, 'cd': .015, 'cm': -.02, 'lift_drag': .2/.015})


def test_wing_degree_units_similarity_and_forwarded_options():
    request = {'op': 'airfoil', 'action': 'wing', 'span': 2, 'root_chord': .3,
               'tip_chord': .15, 'alpha': 4, 'stations': 11}
    wing = dispatch(request)
    assert len(wing['span_positions']) == 11
    assert wing['area'] == pytest.approx(.45)
    assert wing['aspect_ratio'] == pytest.approx(4/.45)
    assert 0 < wing['CL'] < 2*np.pi*np.deg2rad(4)
    assert wing['CDi'] >= wing['CL']**2/(np.pi*wing['aspect_ratio'])
    negative = dispatch(dict(request, alpha=-4))
    assert negative['CL'] == pytest.approx(-wing['CL'])
    assert negative['CDi'] == pytest.approx(wing['CDi'])
    scaled = dispatch(dict(request, span=20, root_chord=3, tip_chord=1.5))
    for coefficient in ('CL', 'CDi', 'aspect_ratio'):
        assert scaled[coefficient] == pytest.approx(wing[coefficient])
    assert scaled['area'] == pytest.approx(100*wing['area'])
    np.testing.assert_allclose(scaled['span_positions'], 10*np.asarray(wing['span_positions']))
    np.testing.assert_allclose(scaled['section_cl'], wing['section_cl'], atol=1e-12)
    zero = dispatch(dict(request, alpha_zero=4))
    assert zero['CL'] == 0 and zero['CDi'] == 0
    twisted = dispatch(dict(request, alpha_zero=4, twist=2))
    assert twisted['CL'] > 0 and twisted['CDi'] > 0
    polar = {'source': 'synthetic constant-drag control', 'rows': [[-20, -2, .02], [20, 2, .02]]}
    profiled = dispatch(dict(request, polar=polar))
    assert profiled['polar_source'] == polar['source']
    assert profiled['CD_profile'] == pytest.approx(.02, rel=.003)
    assert profiled['CD_total'] == pytest.approx(profiled['CDi'] + profiled['CD_profile'])


@pytest.mark.parametrize('options, message', [
    ({'code': 'abc'}, 'four-digit'), ({'code': '0000'}, 'thickness'),
    ({'code': '1012'}, 'camber'), ({'count': 20}, 'Point count'),
    ({'count': True}, 'Point count'),
])
def test_naca_invalid_inputs(options, message):
    request = {'op': 'airfoil', 'action': 'naca', 'code': '0012'}
    request.update(options)
    with pytest.raises(ValueError, match=message):
        dispatch(request)


@pytest.mark.parametrize('text, message', [
    ('1 0\n.5 nan\n0 0\n.5 -.1\n1 0\n', 'finite'),
    ('1 0\n1 .1\n1 0\n1 -.1\n1 0\n', 'chord'),
])
def test_import_rejects_invalid_coordinates(tmp_path, text, message):
    path = tmp_path / 'bad.dat'
    path.write_text(text)
    with pytest.raises(ValueError, match=message):
        dispatch({'op': 'airfoil', 'action': 'import', 'path': str(path)})


@pytest.mark.parametrize('options, rows, message', [
    ({'reynolds': 0}, '0,0,.01\n', 'Reynolds'),
    ({'mach': -1}, '0,0,.01\n', 'Mach'),
    ({}, '0,0,-.01\n', 'nonnegative drag'),
    ({}, '0,0,.01\n0,.1,.02\n', 'duplicate angles'),
])
def test_polar_rejects_invalid_conditions_and_data(tmp_path, options, rows, message):
    path = tmp_path / 'bad.csv'
    path.write_text('alpha,cl,cd\n' + rows)
    with pytest.raises(ValueError, match=message):
        dispatch(dict(op='airfoil', action='polar', path=str(path), **options))


@pytest.mark.parametrize('alpha', [-5, 5, float('nan')])
def test_operating_point_never_extrapolates(alpha):
    with pytest.raises(ValueError, match='extrapolation is disabled'):
        dispatch({'op': 'airfoil', 'action': 'operating_point', 'alpha': alpha,
                  'polar': {'rows': [[-4, -.4, .02], [4, .4, .02]]}})


@pytest.mark.parametrize('options, message', [
    ({'span': 0}, 'positive dimensions'), ({'alpha': float('nan')}, 'Finite'),
    ({'stations': 4}, 'Stations'), ({'stations': True}, 'Stations'),
])
def test_wing_rejects_invalid_geometry_and_discretization(options, message):
    request = {'op': 'airfoil', 'action': 'wing', 'span': 2, 'root_chord': .3,
               'tip_chord': .15, 'alpha': 4}
    request.update(options)
    with pytest.raises(ValueError, match=message):
        dispatch(request)


def test_unknown_action_and_missing_required_field():
    with pytest.raises(ValueError, match='Unknown airfoil operation'):
        dispatch({'op': 'airfoil', 'action': 'not_an_operation'})
    with pytest.raises(KeyError, match='code'):
        dispatch({'op': 'airfoil', 'action': 'naca'})
