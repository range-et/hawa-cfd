"""Exact geometry admission and source identity checks; CPU-only preparation."""
from copy import deepcopy

import numpy as np
import pytest

from hawa.plugin import case_key
from scripts.wing_measurement_recipe import _hash
from scripts.wing_solver_recipe import demo_sweep, prepare_sweep, voxelize_mesh


def box_mesh(low=(0., 0., 0.), high=(1., 1., 1.)):
    vertices = [[low[0], low[1], low[2]], [high[0], low[1], low[2]],
                [high[0], high[1], low[2]], [low[0], high[1], low[2]],
                [low[0], low[1], high[2]], [high[0], low[1], high[2]],
                [high[0], high[1], high[2]], [low[0], high[1], high[2]]]
    faces = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
             [0, 1, 5], [0, 5, 4], [3, 7, 6], [3, 6, 2],
             [0, 4, 7], [0, 7, 3], [1, 2, 6], [1, 6, 5]]
    return dict(vertices_m=vertices, triangles=faces)


def domain():
    return dict(shape=[9, 9, 9], dx=.25, origin_world_m=[-.5, -.5, -.5])


def test_box_matches_exact_surface_inclusive_analytic_set():
    mesh = box_mesh()
    solid = voxelize_mesh(mesh, domain())
    expected = [np.ravel_multi_index((i, j, k), (9, 9, 9)) for i in range(2, 7)
                for j in range(2, 7) for k in range(2, 7)]
    assert solid == expected  # diagonal/shared-edge and cap-plane ray ties included
    translated = box_mesh(low=(2., 3., 4.), high=(3., 4., 5.))
    shifted_domain = dict(shape=[9, 9, 9], dx=.25, origin_world_m=[1.5, 2.5, 3.5])
    assert voxelize_mesh(translated, shifted_domain) == expected


def test_partial_cells_are_not_fabricated_as_solid_nodes():
    solid = voxelize_mesh(box_mesh(low=(.05, .05, .05), high=(.95, .95, .95)), domain())
    expected = [np.ravel_multi_index((i, j, k), (9, 9, 9)) for i in range(3, 6)
                for j in range(3, 6) for k in range(3, 6)]
    assert solid == expected


def test_demo_final_angle_geometry_and_spec_identity():
    study = demo_sweep()
    c0, c1 = study['candidates']
    p0, p1 = [study['prepared'][c['candidate_id']] for c in study['candidates']]
    assert p0['case']['solid'] != p1['case']['solid']
    assert c0['case_hash'] != c1['case_hash']
    assert c0['geometry_hash'] != c1['geometry_hash']
    for c, p in [(c0, p0), (c1, p1)]:
        assert c['case_hash'] == case_key(p['case'])
        assert c['geometry_hash'] == _hash(p['geometry'])
        assert c == p['candidate']
        assert p['geometry_hash'] == c['geometry_hash']
        assert p['body_indices']['wing'] == p['case']['solid']
        assert p['body_indices']['wing'] is not p['case']['solid']
        assert p['references']['area_m2'] == pytest.approx(.15)
        assert p['references']['chord_m'] == pytest.approx(2 * (.09 + .06 + .04) / 1.5)
        assert p['references']['speed_m_s'] == p['case']['speed']
        assert p['case']['origin'] == p['origin_world_m'] == [-.2, -.5, -.2]
        assert p['case']['basis'] == p['basis'] == np.eye(3).tolist()
        assert p['bodies'][0]['moment_origin_world_m'] == [.075, 0., 0.]
        ijk = np.asarray(np.unravel_index(p['case']['solid'], p['case']['shape'])).T
        assert np.all(ijk >= 2) and np.all(ijk < np.array(p['case']['shape']) - 2)
    assert study['identity_scope'] == 'final solver case'
    assert 'synthetic' in study['claim']
    p0['basis'][0][0] = 9.
    assert p1['basis'] == np.eye(3).tolist()


def options():
    return dict(wing_parameters=dict(root='2418', tip='0018', span_m=.3,
                                    root_chord_m=.2, tip_chord_m=.15,
                                    section_points=21, span_stations=3),
                operating_points=[dict(angle_deg=0., speed_m_s=1.)],
                domain=dict(shape=[25, 25, 17], dx=.025, origin_world_m=[-.2, -.3, -.2]),
                fluid=dict(density=1., viscosity=.01, mach=.03, pressure_pa=0.))


def test_speed_changes_final_case_not_geometry_and_no_mutation():
    kwargs = options()
    kwargs['operating_points'] *= 2
    kwargs['operating_points'][1] = dict(angle_deg=0., speed_m_s=2.)
    before = deepcopy(kwargs)
    study = prepare_sweep(**kwargs)
    assert kwargs == before
    c0, c1 = study['candidates']
    assert c0['geometry_hash'] == c1['geometry_hash']
    assert c0['case_hash'] != c1['case_hash']
    assert study['prepared'][c1['candidate_id']]['case']['speed'] == 2.
    kwargs['domain']['shape'][0] = 4
    assert study['prepared'][c0['candidate_id']]['case']['shape'] == [25, 25, 17]


@pytest.mark.parametrize('change', [dict(shape=[3, 9, 9]), dict(shape=[9, 9]),
    dict(shape=[True, 9, 9]), dict(shape=[100, 100, 100]), dict(dx=0),
    dict(dx='1'), dict(origin_world_m=[0, 0]), dict(origin_world_m=[0, False, 0]),
    dict(origin_world_m=[1e300, 1e300, 1e300]), dict(extra=1)])
def test_invalid_domain(change):
    d = domain(); d.update(change)
    with pytest.raises(ValueError):
        voxelize_mesh(box_mesh(), d)


@pytest.mark.parametrize('change', [dict(wing_parameters={'angle_deg': 3}),
    dict(operating_points=[]), dict(operating_points=[{}] * 65), dict(operating_points=[{}]),
    dict(operating_points=[dict(angle_deg=0., speed_m_s=False)]), dict(fluid={}),
    dict(fluid=dict(density=1., viscosity=.01, mach=.2, pressure_pa=0.)),
    dict(fluid=dict(density=1., viscosity=0, mach=.03, pressure_pa=0.))])
def test_invalid_preparation(change):
    kwargs = options(); kwargs.update(change)
    with pytest.raises(ValueError):
        prepare_sweep(**kwargs)


def test_mesh_shape_types_and_closure_rejections():
    mutations = [dict(vertices_m=[[False, 0., 0.]] * 8), dict(triangles=[[0, 1, 80]] * 4),
                 dict(triangles=[[0., 1., 2.]] * 4), dict(triangles=[[0, 1, 2]]),
                 dict(vertices_m=[[0., 0., 0.]] * 8), dict(extra=1)]
    for update in mutations:
        mesh = box_mesh(); mesh.update(update)
        with pytest.raises(ValueError):
            voxelize_mesh(mesh, domain())
    mesh = box_mesh(); mesh['triangles'].pop()
    with pytest.raises(ValueError, match='manifold'):
        voxelize_mesh(mesh, domain())
    mesh = box_mesh(); mesh['triangles'] = [f[::-1] for f in mesh['triangles']]
    with pytest.raises(ValueError, match='positive volume'):
        voxelize_mesh(mesh, domain())


def test_outside_or_unresolved_geometry_rejects():
    with pytest.raises(ValueError, match='clear lattice'):
        voxelize_mesh(box_mesh(low=(-.1, 0., 0.)), domain())
    with pytest.raises(ValueError, match='unresolved'):
        voxelize_mesh(box_mesh(low=(.1, .1, .1), high=(.11, .11, .11)), domain())
    # YZ rays intersect this cube, but no X lattice node lies within its span.
    with pytest.raises(ValueError, match='unresolved'):
        voxelize_mesh(box_mesh(low=(.1, .2, .2), high=(.11, .3, .3)), domain())


def test_overlapping_closed_shells_cannot_silently_publish_partial_winding():
    # Two closed shells share an entrance plane but have different exits.
    # Topological closure alone does not certify an embedded nonoverlapping body.
    first, second = box_mesh(), box_mesh(high=(.8, .8, .8))
    mesh = dict(vertices_m=first['vertices_m'] + second['vertices_m'],
                triangles=first['triangles'] + [[i + 8 for i in face] for face in second['triangles']])
    with pytest.raises(ValueError, match='ray did not close'):
        voxelize_mesh(mesh, domain())
