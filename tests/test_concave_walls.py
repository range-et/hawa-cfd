"""Regressions for concave-corner and midpoint curved-wall fallback (#78)."""
import lettuce as lt
import numpy as np
import pytest
import torch

from hawa.plugin import Session


def _l_shape_case(fraction=0.29):
    """Build a 3D channel with an L-shaped solid whose re-entrant corner triggers behind-solid q < 0.5."""
    shape = [14, 10, 8]
    solid = []
    for i in range(4, 8):
        for j in range(3, 7):
            for k in range(2, 6):
                # Carve out the upper-right quadrant (i >= 6, j >= 5) to create a 90-degree concave corner at (6, 5, k)
                if i >= 6 and j >= 5:
                    continue
                solid.append(int(np.ravel_multi_index((i, j, k), shape)))
    solid_set = set(solid)
    links = []
    fallback_expected = 0
    stencil = lt.D3Q19().e
    for site in sorted(solid_set):
        c = np.array(np.unravel_index(site, shape))
        for d, e in enumerate(stencil[1:], 1):
            fluid = c - e
            behind = fluid - e
            f_idx = int(np.ravel_multi_index(fluid, shape))
            b_idx = int(np.ravel_multi_index(behind, shape))
            if f_idx not in solid_set:
                links.append([d, f_idx, fraction])
                if fraction < 0.5 and b_idx in solid_set:
                    fallback_expected += 1
    case = {
        "shape": shape,
        "dx": 0.1,
        "speed": 1.0,
        "viscosity": 0.05,
        "density": 1.225,
        "mach": 0.05,
        "collision": "bgk",
        "boundaries": ["inlet", "outlet", "wall", "wall", "periodic", "periodic"],
        "solid": solid,
        "wall_links": links,
    }
    return case, fallback_expected


def test_concave_l_shape_fallback_never_reads_solid_behind_and_preserves_equilibrium():
    case, expected_fallbacks = _l_shape_case(fraction=0.29)
    assert expected_fallbacks > 0
    s = Session(case, "cpu")
    assert s.solver.wall_fallback_links == expected_fallbacks

    # Put fluid in exact rest equilibrium while corrupting solid nodes with huge values;
    # if fallback ever read `back` from a solid node, equilibrium would be destroyed.
    u_zero = torch.zeros_like(s.flow.u())
    s.flow.f = s.flow.equilibrium(s.flow, torch.ones_like(s.flow.rho()), u_zero)
    solid_mask = s.flow.solid
    s.flow.f[:, solid_mask] = 999.0

    fluid_mask = ~solid_mask
    before_fluid = s.flow.f[:, fluid_mask].clone()
    s.solver._collide = lambda: None
    # Exercise bounce-back without inlet/outlet overrides touching the corner.
    s.solver.post_boundaries = [b for b in s.solver.post_boundaries if isinstance(b, lt.BounceBackBoundary)]
    s.solver._collide_and_stream()

    after_fluid = s.flow.f[:, fluid_mask]
    np.testing.assert_allclose(after_fluid.cpu().numpy(), before_fluid.cpu().numpy(), atol=1e-7)
    np.testing.assert_allclose(s.solver.wall_history[-1].cpu().numpy(), 0.0, atol=1e-6)


def test_midpoint_rounding_overlapping_boxes_and_live_flow_stability():
    # Exact reproduction of #78's q = 0.49999999999999983 rounding case
    case_mid, expected_mid = _l_shape_case(fraction=0.49999999999999983)
    assert expected_mid > 0
    s_mid = Session(case_mid, "cpu")
    assert s_mid.solver.wall_fallback_links == expected_mid
    s_mid.advance(25)
    f_mid = s_mid.fields()
    assert np.isfinite(f_mid["velocity"]).all()
    assert np.isfinite(f_mid["pressure"]).all()



@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS device unavailable")
def test_concave_full_fluid_velocity_pressure_cpu_mps():
    # Existing CPU/accelerator field criterion: scripts/compare_examples.py,
    # including the SI conversion scales from scripts/example_worker.py.
    case, expected = _l_shape_case(fraction=0.29)
    fluid_fields = []
    speeds = []
    for dev in ("cpu", "mps"):
        s = Session(case, dev)
        assert s.solver.wall_fallback_links == expected
        s.advance(40)
        fields = s.fields()
        assert np.isfinite(fields["velocity"]).all()
        assert np.isfinite(fields["pressure"]).all()
        assert abs(s.relative_mass_change) < 0.05
        fluid = ~s.flow.solid.cpu().numpy()
        fluid_fields.append((fields["velocity"][:, fluid], fields["pressure"][fluid], fluid))
        speeds.append(float(np.linalg.norm(fields["velocity"], axis=0).mean()))
        if dev == "cpu":
            velocity_scale = float(s.flow.units.convert_velocity_to_pu(1.0))
            pressure_scale = float(s.flow.units.convert_density_lu_to_pressure_pu(2.0)
                                   - s.flow.units.convert_density_lu_to_pressure_pu(1.0))
    # Retain the original mean-speed assertion as a separate, weaker check.
    np.testing.assert_allclose(speeds, speeds[0], rtol=5e-4)
    np.testing.assert_array_equal(fluid_fields[1][2], fluid_fields[0][2])
    np.testing.assert_allclose(fluid_fields[1][0], fluid_fields[0][0],
                               rtol=1e-3, atol=1e-5 * abs(velocity_scale), equal_nan=False)
    np.testing.assert_allclose(fluid_fields[1][1], fluid_fields[0][1],
                               rtol=1e-3, atol=1e-5 * abs(pressure_scale), equal_nan=False)
