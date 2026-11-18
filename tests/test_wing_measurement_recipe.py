"""Independent topology, transform and provenance assertions for the example."""
from collections import Counter
from copy import deepcopy
import importlib.util
from pathlib import Path

import numpy as np
import pytest

PATH = Path(__file__).parents[1] / 'scripts' / 'wing_measurement_recipe.py'
SPEC = importlib.util.spec_from_file_location('wing_recipe', PATH)
recipe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recipe)


def test_full_span_closed_oriented_distinct_sections_and_reference_area():
    wing = recipe.wing_mesh(root='2412', tip='0012', span_m=2., root_chord_m=.4, tip_chord_m=.2)
    vertices = np.asarray(wing['vertices_m'])
    triangles = np.asarray(wing['triangles'])
    edges = Counter(tuple(sorted((int(face[i]), int(face[(i + 1) % 3]))))
                    for face in triangles for i in range(3))
    directed = Counter((int(face[i]), int(face[(i + 1) % 3])) for face in triangles for i in range(3))
    assert set(edges.values()) == {2}
    assert all(directed[(b, a)] == count for (a, b), count in directed.items())
    assert len(vertices) - len(edges) + len(triangles) == 2
    assert len(np.unique(vertices, axis=0)) == len(vertices)
    assert set(triangles.flat) == set(range(len(vertices)))
    area = np.linalg.norm(np.cross(vertices[triangles[:, 1]] - vertices[triangles[:, 0]],
                                   vertices[triangles[:, 2]] - vertices[triangles[:, 0]]), axis=1)
    assert np.all(area > 0)
    assert wing['volume_m3'] > 0
    assert wing['reference_area_m2'] == pytest.approx(.6)
    assert wing['reference_chord_m'] == pytest.approx(2 * (.16 + .08 + .04) / (3 * .6))
    sections = np.asarray(wing['sections_m'])
    assert sections.shape == (9, 80, 3)
    np.testing.assert_allclose(sections[0, :, [0, 2]], sections[-1, :, [0, 2]], atol=1e-15)
    assert sections[4, 20, 2] > 2 * sections[0, 20, 2]  # root camber, after chord scaling
    assert vertices[:, 1].min() == -1 and vertices[:, 1].max() == 1
    assert wing['geometry_hash'] == recipe.wing_mesh(root='2412', tip='0012', span_m=2., root_chord_m=.4, tip_chord_m=.2)['geometry_hash']


def test_positive_angle_rotation_and_pivot_invariance():
    pivot = [.1, 0., .2]
    rotated = recipe.rotate_y([[0., 0., .2], [.4, 0., .2], pivot], 30., pivot)
    assert rotated[0][2] > rotated[1][2]
    np.testing.assert_allclose(rotated[2], pivot)
    np.testing.assert_allclose(recipe.rotate_y(rotated, -30., pivot), [[0., 0., .2], [.4, 0., .2], pivot])
    a = recipe.wing_mesh(angle_deg=0.)
    b = recipe.wing_mesh(angle_deg=10., pivot_m=pivot)
    assert a['reference_area_m2'] == b['reference_area_m2']
    assert a['reference_chord_m'] == b['reference_chord_m']
    assert a['volume_m3'] == pytest.approx(b['volume_m3'], rel=1e-12)
    assert a['geometry_hash'] != b['geometry_hash']
    np.testing.assert_allclose(recipe.rotate_y(b['vertices_m'], -10., pivot), a['vertices_m'], atol=1e-15)


def test_sweep_order_hashes_fresh_geometry_fixed_area_and_no_start():
    params = dict(root='2412', tip='0012', section_points=21, span_stations=3)
    points = [dict(angle_deg=-2., speed_m_s=3.), dict(angle_deg=2., speed_m_s=3.),
              dict(angle_deg=2., speed_m_s=4.), dict(angle_deg=2., speed_m_s=4.)]
    settings = dict(density=1.225, viscosity=.001, domain={'shape': [20, 20, 20]})
    old = deepcopy(settings)
    study = recipe.sweep_recipe(params, points, settings)
    settings['domain']['shape'][0] = 30
    assert study['case_settings'] == old
    assert study['run'] is False
    c = study['candidates']
    assert [p['candidate_id'] for p in c] == ['wing-000', 'wing-001', 'wing-002', 'wing-003']
    assert [p['angle_deg'] for p in c] == [-2., 2., 2., 2.]
    assert c[0]['geometry_hash'] != c[1]['geometry_hash']
    assert c[1]['geometry_hash'] == c[2]['geometry_hash']
    assert c[1]['case_hash'] != c[2]['case_hash']
    assert c[2]['case_hash'] == c[3]['case_hash']  # repetitions retain unique candidate ID
    assert all(len(p['case_hash']) == len(p['geometry_hash']) == 64 for p in c)
    assert all(g['reference_area_m2'] == study['references']['area_m2'] for g in study['geometry'].values())
    assert 'preflight' in study['identity_scope']
    other = recipe.sweep_recipe(params, points, settings)
    assert other['candidates'][0]['case_hash'] != c[0]['case_hash']


@pytest.mark.parametrize('kwargs', [dict(root=12), dict(tip=None), dict(root='nope'),
    dict(span_m=0), dict(root_chord_m=-1), dict(tip_chord_m=True), dict(span_m='2'),
    dict(span_m=float('nan')), dict(angle_deg=float('inf')), dict(section_points=20),
    dict(section_points=22), dict(section_points=403), dict(section_points=True),
    dict(span_stations=2), dict(span_stations=4), dict(span_stations=67),
    dict(pivot_m=[0, 0]), dict(pivot_m=[0, 0, False]), dict(span_m=1e-300),
    dict(root_chord_m=1e200), dict(tip_chord_m=1e-300, root_chord_m=1e-300)])
def test_invalid_geometry_rejects(kwargs):
    with np.errstate(all='ignore'), pytest.raises(ValueError):
        recipe.wing_mesh(**kwargs)


@pytest.mark.parametrize('points,pivot,angle', [([[0, 0]], [0, 0, 0], 0),
    ([[float('nan'), 0, 0]], [0, 0, 0], 0),
    ([[False, 0, 0]], [0, 0, 0], 0), ([['1', 0, 0]], [0, 0, 0], 0),
    ([], [0, 0, 0], 0), ([[0, 0, 0]], 'bad', 0),
    ([[0, 0, 0]], [0, 0, 0], '3'), ([[1e308, 0, 1e308]], [-1e308, 0, 0], 45)])
def test_rotation_rejects_invalid(points, pivot, angle):
    with np.errstate(all='ignore'), pytest.raises(ValueError):
        recipe.rotate_y(points, angle, pivot)


@pytest.mark.parametrize('params,points,settings', [([], [], {}), ({'angle_deg': 2}, [], {}),
    ({}, [], {'x': 1}), ({}, [{}] * 65, {'x': 1}), ({}, [{}], {}),
    ({}, [{}], {'x': 1}), ({}, [dict(angle_deg=0, speed_m_s=0)], {'x': 1}),
    ({}, [dict(angle_deg=False, speed_m_s=1)], {'x': 1}),
    ({}, [dict(angle_deg=0, speed_m_s=1)], {'x': float('nan')}),
    ({}, [dict(angle_deg=0, speed_m_s=1)], [])])
def test_invalid_sweep_rejects(params, points, settings):
    with pytest.raises(ValueError):
        recipe.sweep_recipe(params, points, settings)


def test_symmetric_zero_camber_caps_and_uniform_scale():
    a = recipe.wing_mesh(root='0012', tip='0012', root_chord_m=.2, tip_chord_m=.2, span_m=.6,
                         section_points=21, span_stations=3)
    b = recipe.wing_mesh(root='0012', tip='0012', root_chord_m=.4, tip_chord_m=.4, span_m=1.2,
                         section_points=21, span_stations=3)
    assert a['reference_area_m2'] == pytest.approx(.12)
    assert b['volume_m3'] == pytest.approx(8 * a['volume_m3'])
    np.testing.assert_allclose(np.array(a['vertices_m']) * 2, b['vertices_m'])
    z = np.asarray(a['vertices_m'])[:, 2]
    assert z.max() == pytest.approx(-z.min())


def test_upstream_collapsed_or_reversed_profile_is_rejected(monkeypatch):
    original = recipe.naca
    def collapsed(*args, **kwargs):
        profile = original(*args, **kwargs)
        profile['coordinates'] = [[x, 0.] for x, z in profile['coordinates']]
        return profile
    monkeypatch.setattr(recipe, 'naca', collapsed)
    with pytest.raises(ValueError, match='degenerate'):
        recipe.wing_mesh()
    def reversed_profile(*args, **kwargs):
        profile = original(*args, **kwargs)
        profile['coordinates'] = [[x, -z] for x, z in profile['coordinates']]
        return profile
    monkeypatch.setattr(recipe, 'naca', reversed_profile)
    with pytest.raises(ValueError, match='positive oriented volume'):
        recipe.wing_mesh()
