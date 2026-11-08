"""Coverage of public features omitted or skipped by the original suite."""

import numpy as np
import pytest
import torch
import lettuce as lt
from lettuce.util.moments import D1Q3Transform, D2Q9Lallemand, D3Q27Hermite, Transform

DEVICES = ["cpu", "mps", "cuda:0"]


@pytest.fixture(params=DEVICES)
def context(request):
    device = request.param
    if device == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS hardware unavailable")
    if device.startswith("cuda") and not torch.cuda.is_available():
        pytest.skip("CUDA hardware unavailable")
    return lt.Context(device=device, dtype=torch.float32, use_native=False)


def build_flow(kind, context):
    args = dict(context=context, reynolds_number=10, mach_number=0.05)
    if kind == "cavity":
        return lt.Cavity2D(resolution=16, **args)
    if kind == "couette":
        return lt.CouetteFlow2D(resolution=16, **args)
    if kind == "shear":
        return lt.DoublyPeriodicShear2D(resolution=16, **args)
    if kind == "lamb":
        return lt.LambOseenVortex2D(resolution=16, **args)
    if kind == "poiseuille":
        return lt.PoiseuilleFlow2D(resolution=16, **args)
    if kind.startswith("decay"):
        dim = int(kind[-1])
        return lt.DecayingTurbulence(resolution=[12] * dim, randseed=123,
                                     k0=3, initialize_pressure=False, **args)
    if kind.startswith("obstacle"):
        dim = int(kind[-1])
        flow = lt.Obstacle(resolution=[16] * dim, domain_length_x=4, **args)
        mask = context.zero_tensor(flow.resolution, dtype=torch.bool)
        mask[tuple(slice(6, 9) for _ in range(dim))] = True
        flow.mask = mask
        flow.initialize()
        return flow
    stencil = {"d2q9": lt.D2Q9, "d3q15": lt.D3Q15,
               "d3q19": lt.D3Q19, "d3q27": lt.D3Q27}[kind]()
    return lt.TaylorGreenVortex(resolution=[12] * stencil.d, stencil=stencil, **args)


FLOW_KINDS = ["cavity", "couette", "shear", "lamb", "poiseuille", "decay2",
              "decay3", "obstacle2", "obstacle3", "d2q9", "d3q15", "d3q19", "d3q27"]


@pytest.mark.parametrize("kind", FLOW_KINDS)
def test_all_flow_families_run(context, kind):
    flow = build_flow(kind, context)
    sim = lt.Simulation(flow, lt.BGKCollision(flow.units.relaxation_parameter_lu), [])
    sim(5)
    context.synchronize()
    assert torch.isfinite(flow.f).all()
    assert (flow.rho() > 0).all()
    assert flow.i == 5


@pytest.mark.parametrize("name", ["BGKCollision", "TRTCollision", "RegularizedCollision",
                                  "SmagorinskyCollision", "KBCCollision", "MRTCollision"])
def test_collision_families_conserve_mass_and_momentum(context, name):
    flow = build_flow("d2q9", context)
    tau = flow.units.relaxation_parameter_lu
    if name == "MRTCollision":
        collision = lt.MRTCollision(D2Q9Lallemand(flow.stencil, context), [tau] * 9, context)
    else:
        collision = getattr(lt, name)(tau)
    before_rho, before_j = flow.rho(), flow.j()
    after = collision(flow)
    torch.testing.assert_close(flow.rho(after), before_rho, rtol=2e-5, atol=2e-6)
    torch.testing.assert_close(flow.j(after), before_j, rtol=2e-5, atol=2e-6)


@pytest.mark.parametrize("name", ["QuadraticEquilibrium", "QuadraticEquilibriumLessMemory",
                                  "IncompressibleQuadraticEquilibrium"])
def test_equilibria_are_instantiable_and_conserve(context, name):
    flow = build_flow("d2q9", context)
    equilibrium = getattr(lt, name)()
    feq = equilibrium(flow)
    torch.testing.assert_close(flow.rho(feq), flow.rho(), rtol=1e-5, atol=1e-6)
    assert torch.isfinite(feq).all()


def test_generic_mrt_transform_equilibrium_uses_current_flow_api(context):
    flow = build_flow("d2q9", context)
    transform = Transform(flow.stencil, context)
    torch.testing.assert_close(transform.equilibrium(flow.f, flow), flow.equilibrium(flow))


@pytest.mark.parametrize("stencil,transform", [(lt.D1Q3, D1Q3Transform),
                                             (lt.D2Q9, D2Q9Lallemand),
                                             (lt.D3Q27, D3Q27Hermite)])
def test_transform_round_trip_on_all_devices(context, stencil, transform):
    stencil = stencil()
    mapping = transform(stencil, context)
    f = context.convert_to_tensor(np.random.default_rng(42).random((stencil.q, *([4] * stencil.d))))
    torch.testing.assert_close(mapping.inverse_transform(mapping.transform(f)), f, rtol=2e-5, atol=2e-6)


def test_couette_has_nonzero_velocity_scale_and_linear_profile(context):
    flow = build_flow("couette", context)
    assert flow.units.characteristic_velocity_pu == 1.0
    assert torch.isfinite(flow.f).all()
    u = flow.analytic_solution()
    assert tuple(u.shape) == (2, 16, 16)
    assert float(u[0, 0, -1].cpu()) == pytest.approx(1)


def test_cli_benchmark_runs_on_cpu_without_cuda_extension(tmp_path):
    from click.testing import CliRunner
    from lettuce.cli import main
    for flow in ("taylor2d", "poiseuille2d", "couette2d", "decay2d"):
        result = CliRunner().invoke(main, ["--no-cuda", "-p", "single", "benchmark",
                                          "-f", flow, "-r", "12", "-s", "2"])
        assert result.exit_code == 0, (flow, result.output, result.exception)
