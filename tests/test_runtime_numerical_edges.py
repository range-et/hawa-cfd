"""CPU state and numerical boundary limits omitted by ordinary success cases."""
import json
import numpy as np
import pytest
import torch
from hawa.plugin import Session
from test_general_boundaries import channel
from test_boundary_data import series
from test_boundary_series import case as external_case, recording, mapped


def test_minimal_solver_rejects_invalid_steps_without_state_change():
    from hawa.lbm import VortexSimulation, VortexConfig
    from hawa.backends import select_backend
    sim = VortexSimulation(select_backend('cpu'), VortexConfig(size=16)); before = sim.f.clone()
    for count in (True, -1, 1.5):
        with pytest.raises(ValueError, match='nonnegative integer'): sim.advance(count)
        torch.testing.assert_close(sim.f, before, rtol=0, atol=0)
        assert sim.iteration == 0


def test_nee_pressure_backflow_is_reserved_for_neutral():
    from hawa.boundaries import compile_plan
    spec = channel(wall=False)
    spec['boundary_set']['patches'][1]['condition']['backflow_mode'] = 'pressure'
    with pytest.raises(ValueError, match='requires Neutral Flow'): compile_plan(spec)


def test_mapped_nee_rejects_reversed_fluid_inflow(tmp_path):
    from hawa.boundaries import compile_plan
    from hawa.boundary_data import digest
    spec = channel(wall=False); velocity = np.zeros((2,3,9,9)); velocity[:,0] = -1.
    path = series(tmp_path/'reverse.npz', spec, velocity)
    spec['boundary_field'] = {'path': str(path), 'sha256': digest(path)}
    spec['boundary_set']['patches'][0]['condition']['profile'] = 'mapped'
    with pytest.raises(ValueError, match='cannot reverse'): compile_plan(spec)


def test_nee_pressure_exceeding_density_budget_is_rejected():
    spec = channel(wall=False)
    spec['boundary_set']['patches'][1]['condition']['pressure_pa'] = 1e6
    with pytest.raises(ValueError, match='10% density'): Session(spec, 'cpu')


def test_neutral_external_rejects_floor_and_discontinuous_prescription():
    from hawa.neutral_external import compile_links
    spec = external_case(); patches = spec['boundary_set']['patches']
    patches[4]['condition']['type'] = 'slip'
    with pytest.raises(ValueError, match='rough Z- wall'): compile_links(spec)
    patches[4]['condition']['type'] = 'wall'
    patches[0]['condition'].update(type='velocity', velocity=[1.,0.,0.])
    patches[2]['condition'].update(type='velocity', velocity=[0.,1.,0.])
    with pytest.raises(ValueError, match='matching exterior data'): compile_links(spec)


def test_curved_wall_links_require_nonperiodic_padding():
    from hawa.walls import install_interpolated_walls
    from test_optimization import spec
    session = Session(spec(), 'cpu')
    direction = next(i for i, e in enumerate(session.flow.stencil.e) if e[0] == 1)
    with pytest.raises(ValueError, match='one-cell fluid padding'):
        install_interpolated_walls(session.solver, [[direction, 0, .5]])


def test_pathlines_reject_changed_lattice_shapes(tmp_path):
    from hawa.recording import pathlines
    spec = external_case((6,6,6)); manifest = recording(tmp_path/'parent', spec, times=(0.,1.))
    path = tmp_path/'parent'/'frame1.npz'
    with np.load(path) as archive: data = {key: archive[key] for key in archive}
    for name in ('velocity','pressure','density','solid'):
        data[name] = data[name][..., :-1].copy()
    np.savez_compressed(path, **data)
    with pytest.raises(ValueError, match='lattice shapes'): pathlines(manifest, [[1.,1.,1.]])


def test_optimization_rejects_zero_drag_rest_state():
    from hawa.optimization import evaluate
    from test_optimization import spec
    case = spec(); case['initial_velocity'] = [0.,0.,0.]
    # The obstacle is too far from the inlet for a disturbance to reach it in two steps.
    session = Session(case, 'cpu')
    with pytest.raises(RuntimeError, match='Nonpositive or nonfinite resistance'):
        evaluate(session, 2, 1, 1.)


def test_legacy_v2_without_strain_reconstructs_density_and_velocity(tmp_path):
    from hawa.boundary_data import attach
    result, _ = mapped(tmp_path); path = result['case']['boundary_field']['path']
    with np.load(path) as archive:
        data = {key: archive[key] for key in archive if key not in ('strain_rate', 'initial_strain_rate')}
    np.savez_compressed(path, **data)
    spec = external_case((6,6,8), .5, [2,2,.25]); spec = attach(path, spec)['case']
    session = Session(spec, 'cpu')
    np.testing.assert_allclose(session.fields()['velocity'], data['initial_velocity'], atol=5e-6)
    np.testing.assert_allclose(session.fields()['pressure'], data['initial_pressure'], atol=5e-5)
    session.advance(1)
    assert session.quality['finite'] and session.quality['positive_density']


def test_underresolved_exterior_pore_cannot_satisfy_fluid_moments():
    # A single fluid voxel connected to the exterior by one axial link has too
    # few independent free populations for simultaneous mass/momentum constraints.
    spec = external_case((4,4,4)); halo = np.ones((6,6,6), bool)
    halo[1,2,2] = False; halo[0,2,2] = False
    spec['solid'] = np.flatnonzero(halo[1:-1,1:-1,1:-1]).tolist()
    spec['solid_halo'] = np.flatnonzero(halo).tolist()
    with pytest.raises(ValueError, match='cannot satisfy independent fluid moments'):
        Session(spec, 'cpu')
