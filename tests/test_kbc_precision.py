"""Near-equilibrium KBC must not amplify FP32 cancellation into a load change."""
from types import SimpleNamespace

import numpy as np
import pytest
import torch
import lettuce as lt


# One cell from the original 512-square PorousMedium run, before step ten.
# The old FP32 moment calculation differed from FP64 by up to 6.8e-7 here.
POPULATIONS = [0.46215876936912537, 0.12010455876588821, 0.11050435900688171,
               0.11057711392641068, 0.12013725191354752, 0.028833307325839996,
               0.026515554636716843, 0.02889091707766056, 0.03128119930624962]


@pytest.mark.parametrize('size', [1, 8])
@pytest.mark.parametrize('device', ['cpu', 'cuda:0'])
def test_kbc_near_equilibrium_matches_double_collision(size, device):
    if device.startswith('cuda') and not torch.cuda.is_available():pytest.skip('CUDA hardware unavailable')
    outputs=[]
    for dtype in (torch.float32, torch.float64):
        ctx=lt.Context(device,dtype,use_native=False)
        flow=lt.TaylorGreenVortex(ctx,[8,8],10,.05)
        flow.units=lt.UnitConversion(reynolds_number=lt.D2Q9.cs*.05*512/(1/6),
                                     mach_number=.05,characteristic_length_lu=1)
        # Start from exactly the same representable FP32 data on both paths.
        flow.f=torch.tensor(POPULATIONS,device=device,dtype=torch.float32).to(dtype)[:,None,None].expand(-1,size,size).clone()
        before=flow.f.clone();context=flow.context;stencil=flow.torch_stencil
        output=lt.KBCCollision()(flow)
        assert output.device == flow.f.device and output.dtype == dtype
        assert flow.context is context and flow.torch_stencil is stencil
        torch.testing.assert_close(flow.f,before,rtol=0,atol=0)
        torch.testing.assert_close(flow.rho(output),flow.rho(before),rtol=2e-6,atol=2e-7)
        torch.testing.assert_close(flow.j(output),flow.j(before),rtol=2e-6,atol=2e-7)
        outputs.append(output.cpu().numpy())
    # The exact rounded FP64 reference is attainable for this local collision.
    np.testing.assert_array_equal(outputs[0],outputs[1].astype(np.float32))


@pytest.mark.parametrize('stencil', [lt.D2Q9, lt.D3Q27])
def test_kbc_equilibrium_is_fixed_and_preserves_storage(solver_device, stencil):
    ctx=lt.Context(solver_device,torch.float32,use_native=False)
    lattice=stencil()
    flow=lt.TaylorGreenVortex(ctx,[8]*lattice.d,10,.05,stencil=lattice)
    flow.f=flow.equilibrium(flow,flow.rho(),torch.zeros_like(flow.u()))
    before=flow.f.clone();collision=lt.KBCCollision()
    for _ in range(5):flow.f=collision(flow)
    assert flow.f.dtype==torch.float32 and flow.f.device==before.device
    torch.testing.assert_close(flow.f,before,rtol=2e-6,atol=2e-7)


def _near_equilibrium_flow(stencil, device, dtype, resolution, seed=3):
    """Random FP32-representable near-equilibrium populations, identical for every dtype."""
    generator=torch.Generator().manual_seed(seed)
    ctx=lt.Context(device,dtype,use_native=False)
    flow=lt.TaylorGreenVortex(ctx,[4]*stencil.d,10,.05,stencil=stencil)
    flow.units=lt.UnitConversion(reynolds_number=lt.D2Q9.cs*.05*512/(1/6),
                                 mach_number=.05,characteristic_length_lu=1)
    reference=lt.TaylorGreenVortex(lt.Context('cpu',torch.float64,use_native=False),[4]*stencil.d,10,.05,stencil=stencil)
    rho=1+.01*torch.randn(1,*resolution,generator=generator,dtype=torch.float64)
    u=.05*torch.randn(stencil.d,*resolution,generator=generator,dtype=torch.float64)
    feq=reference.equilibrium(reference,rho,u)
    f=(feq*(1+1e-3*torch.randn(feq.shape,generator=generator,dtype=torch.float64))).float()
    flow.f=f.to(device=device,dtype=dtype)
    return flow


@pytest.mark.parametrize('stencil,resolution',[(lt.D2Q9,[32,32]),(lt.D3Q27,[8,8,8])])
def test_compensated_fp32_kbc_reproduces_rounded_double_collision(stencil,resolution):
    # HAWA-001: devices without FP64 (MPS) use FP32 hi/lo intermediates. On
    # identical inputs they must give the CPU FP64-intermediate result, which
    # plain FP32 arithmetic misses by up to ~150 ulp in most populations.
    eps=torch.finfo(torch.float32).eps
    double=_near_equilibrium_flow(stencil(),'cpu',torch.float64,resolution)
    expected=lt.KBCCollision()._collide(double,eps).float()
    single=_near_equilibrium_flow(stencil(),'cpu',torch.float32,resolution)
    before=single.f.clone()
    plain=lt.KBCCollision()._collide(single,eps)
    assert (plain!=expected).float().mean()>.5
    output=lt.KBCCollision()._collide_compensated(single,eps)
    torch.testing.assert_close(single.f,before,rtol=0,atol=0)
    assert output.dtype==torch.float32
    np.testing.assert_array_equal(output.numpy(),expected.numpy())


def test_compensated_kbc_keeps_porous_cell_stabilizer_sign_at_every_shape():
    # Frozen PorousMedium cell (step 50, cell 294,125). FP64 stabilizer is
    # +0.0016; plain FP32 gives +0.0053 on CPU and a shape-dependent negative
    # value (reset to 2) on MPS at 512 x 512. Shapes must not change the result.
    cell=torch.tensor([0.43819519877433777,0.10960162431001663,0.10923780500888824,
                       0.10090156644582748,0.11824554204940796,0.027240581810474396,
                       0.025348886847496033,0.027386868372559547,0.02978522703051567])
    def flow(dtype,size):
        f=lt.TaylorGreenVortex(lt.Context('cpu',dtype,use_native=False),[8,8],10,.05)
        f.units=lt.UnitConversion(reynolds_number=lt.D2Q9.cs*.05*512/(1/6),
                                  mach_number=.05,characteristic_length_lu=1)
        f.f=cell.to(dtype)[:,None,None].expand(-1,size,size).clone()
        return f
    eps=torch.finfo(torch.float32).eps
    expected=lt.KBCCollision()._collide(flow(torch.float64,1),eps).float()[:,0,0]
    for size in (1,8,64):
        output=lt.KBCCollision()._collide_compensated(flow(torch.float32,size),eps)
        np.testing.assert_array_equal(output.numpy(),expected[:,None,None].expand(-1,size,size).numpy())


def test_compensated_kbc_preserves_degenerate_and_nonfinite_handling():
    eps=torch.finfo(torch.float32).eps
    single=_near_equilibrium_flow(lt.D2Q9(),'cpu',torch.float32,[4,4])
    # Exact equilibrium: delta_h is zero, so the storage-precision guard applies.
    single.f=single.equilibrium(single,single.rho(),single.u())
    double=_near_equilibrium_flow(lt.D2Q9(),'cpu',torch.float64,[4,4])
    double.f=single.f.double()
    np.testing.assert_array_equal(lt.KBCCollision()._collide_compensated(single,eps).numpy(),
                                  lt.KBCCollision()._collide(double,eps).float().numpy())
    single.f[:,0,0]=float('nan')
    output=lt.KBCCollision()._collide_compensated(single,eps)
    assert torch.isnan(output[:,0,0]).all() and torch.isfinite(output[:,1:,:]).all()


def test_double_float_primitives_are_exact(solver_device):
    # TwoSum/TwoProduct exactness needs separately rounded IEEE FP32 operations;
    # on MPS this checks the actual Metal kernels. FP64 holds both results exactly.
    from lettuce.ext._collision import kbc_collision as kbc
    generator=torch.Generator().manual_seed(7)
    a=(torch.rand(4096,generator=generator)*2-1)*torch.logspace(-6,1,4096)
    b=(torch.rand(4096,generator=generator)*2-1)*torch.logspace(1,-6,4096)
    a32,b32=a.to(solver_device),b.to(solver_device)
    s,e=kbc._two_sum(a32,b32)
    p,r=kbc._two_product(a32,b32)
    a64,b64=a.double(),b.double()
    np.testing.assert_array_equal((s.cpu().double()+e.cpu().double()).numpy(),(a64+b64).numpy())
    np.testing.assert_array_equal((p.cpu().double()+r.cpu().double()).numpy(),(a64*b64).numpy())
    assert (e!=0).any() and (r!=0).any()


@pytest.mark.parametrize('size',[1,8,32,512])
def test_mps_kbc_matches_cpu_collision_on_identical_input(size):
    if not torch.backends.mps.is_available():pytest.skip('MPS hardware unavailable')
    cell=[0.43819519877433777,0.10960162431001663,0.10923780500888824,0.10090156644582748,
          0.11824554204940796,0.027240581810474396,0.025348886847496033,0.027386868372559547,
          0.02978522703051567]
    outputs=[]
    for device in ('cpu','mps'):
        flow=lt.TaylorGreenVortex(lt.Context(device,torch.float32,use_native=False),[8,8],10,.05)
        flow.units=lt.UnitConversion(reynolds_number=lt.D2Q9.cs*.05*512/(1/6),
                                     mach_number=.05,characteristic_length_lu=1)
        flow.f=torch.tensor(cell,device=device)[:,None,None].expand(-1,size,size).clone()
        outputs.append(lt.KBCCollision()(flow).cpu().numpy())
    np.testing.assert_array_equal(outputs[1],outputs[0])


class _AcceleratorTensor:
    """Stands in for FP32 storage on a device this host cannot allocate."""
    dtype=torch.float32
    def __init__(self,device):self.device=torch.device(device)
    def to(self,dtype):return torch.zeros(9,2,2,dtype=dtype)


def _spy_collisions(monkeypatch):
    calls=[]
    monkeypatch.setattr(lt.KBCCollision,'_collide_compensated',
                        lambda self,flow,eps:calls.append(('compensated',flow,eps)) or flow.f)
    monkeypatch.setattr(lt.KBCCollision,'_collide',lambda self,flow,eps:calls.append(('plain',flow,eps)) or flow.f)
    return calls


@pytest.mark.parametrize('equilibrium,path',[(lt.QuadraticEquilibrium,'compensated'),
                                             (lt.QuadraticEquilibriumLessMemory,'compensated'),
                                             (lt.IncompressibleQuadraticEquilibrium,'plain')])
def test_fp32_storage_without_fp64_uses_double_float_only_for_quadratic_equilibrium(monkeypatch,equilibrium,path):
    calls=_spy_collisions(monkeypatch)
    for device in ('mps','meta'):
        flow=SimpleNamespace(f=_AcceleratorTensor(device),equilibrium=equilibrium())
        assert lt.KBCCollision()(flow) is flow.f
        assert calls.pop()==(path,flow,torch.finfo(torch.float32).eps)
    assert not calls


def test_fp64_storage_without_fp64_intermediate_promotion_uses_plain_kernel(monkeypatch):
    calls=_spy_collisions(monkeypatch)
    flow=SimpleNamespace(f=torch.empty(9,2,2,dtype=torch.float64,device='meta'),equilibrium=lt.QuadraticEquilibrium())
    assert lt.KBCCollision()(flow) is flow.f
    assert calls==[('plain',flow,torch.finfo(torch.float64).eps)]


@pytest.mark.parametrize('device',['cpu','cuda'],ids=['host','nvidia'])
def test_fp32_storage_on_fp64_capable_devices_keeps_fp64_intermediates(monkeypatch,device):
    calls=_spy_collisions(monkeypatch)
    flow=lt.TaylorGreenVortex(lt.Context('cpu',torch.float32,use_native=False),[2,2],10,.05)
    flow.f=_AcceleratorTensor(device)
    collision=lt.KBCCollision()
    output=collision(flow)
    assert len(calls)==1 and calls[0][0]=='plain' and calls[0][2]==torch.finfo(torch.float32).eps
    working=calls[0][1]
    assert working is not flow and working.f.dtype==torch.float64 and output.dtype==torch.float32
    assert working.context.dtype==torch.float64 and flow.context.dtype==torch.float32
    # The promoted context and stencil are built once and reused.
    context=collision._compute_context
    collision(flow)
    assert calls[1][1].context is context and calls[1][1].torch_stencil is working.torch_stencil


def test_kbc_rejects_unsupported_stencils_and_keeps_deprecated_aliases():
    import re
    units=SimpleNamespace(relaxation_parameter_lu=.6)
    for stencil,error,message in ((lt.D1Q3(),NotImplementedError,'KBC Collision is only implemented for 2d and 3d!'),
                                  (lt.D3Q19(),AssertionError,'KBC Collision is only implemented for D3Q27!'),
                                  (SimpleNamespace(d=2),AssertionError,'KBC Collision is only implemented for D2Q9!')):
        with pytest.raises(error,match='^'+re.escape(message)+'$'):
            lt.KBCCollision()._initialize(SimpleNamespace(units=units,stencil=stencil))
    for alias in (lt.KBCCollision2D,lt.KBCCollision3D):
        # Upstream's message names KBCCollision2D for both aliases.
        with pytest.warns(UserWarning,match='^'+re.escape('KBCCollision2D is is deprecated! Use KBCCollision instead!')+'$'):
            collision=alias()
        assert isinstance(collision,lt.KBCCollision) and not collision.native_available()
        assert collision.native_generator(0) is None


def test_initialization_binds_dimension_specific_moment_kernels():
    collision=lt.KBCCollision(tau=.7)
    # Construction is lazy: the flow's relaxation parameter replaces tau later.
    assert collision.tau==.7 and collision.beta is None and collision.M is None
    assert collision._compute_context is None and collision._compute_stencil is None
    f=torch.ones(9,1,1)
    # Unbound class placeholders do nothing until a flow selects the dimension.
    assert collision.kbc_moment_transform(f) is None and collision.compute_s_seq_from_m(f,f) is None
    flow=lt.TaylorGreenVortex(lt.Context('cpu',torch.float64,use_native=False),[2,2],10,.05)
    collision._initialize(flow)
    assert collision.kbc_moment_transform.__func__ is lt.KBCCollision.kbc_moment_transform_2d
    assert collision.compute_s_seq_from_m.__func__ is lt.KBCCollision.compute_s_seq_from_m_2d
    assert collision.tau==flow.units.relaxation_parameter_lu!=.7
    assert collision.beta==pytest.approx(1/(2*flow.units.relaxation_parameter_lu))
    assert collision.M.shape==(3,3,9) and collision.M[2,1].tolist()==[0,0,0,0,0,1,1,-1,-1]
    collision=lt.KBCCollision()
    collision._initialize(lt.TaylorGreenVortex(lt.Context('cpu',torch.float64,use_native=False),[2,2,2],10,.05,stencil=lt.D3Q27()))
    assert collision.kbc_moment_transform.__func__ is lt.KBCCollision.kbc_moment_transform_3d
    assert collision.compute_s_seq_from_m.__func__ is lt.KBCCollision.compute_s_seq_from_m_3d
    e=torch.tensor(lt.D3Q27().e,dtype=torch.float64)
    assert collision.M.shape==(3,3,3,27)
    torch.testing.assert_close(collision.M[2,1,1],e[:,0]**2*e[:,1]*e[:,2],rtol=0,atol=0)


def test_storage_precision_guard_scales_with_density_in_both_kernels():
    # rho = 1/4 puts this residual between the guard threshold (q eps)^2 rho
    # and the wrong-way scaling (q eps)^2 / rho; the guard must stay off in
    # both kernels, so the double-float result still equals the FP64 one.
    flow=_near_equilibrium_flow(lt.D2Q9(),'cpu',torch.float32,[1,1])
    reference=lt.TaylorGreenVortex(lt.Context('cpu',torch.float64,use_native=False),[1,1],10,.05)
    rho=.25
    feq=reference.equilibrium(reference,torch.full((1,1,1),rho,dtype=torch.float64),
                              torch.tensor([.02,-.01],dtype=torch.float64).view(2,1,1))
    higher=torch.tensor([1,-.5,-.5,-.5,-.5,.25,.25,.25,.25],dtype=torch.float64).view(9,1,1)  # m22 basis
    shear=torch.tensor([0,0,0,0,0,.25,-.25,.25,-.25],dtype=torch.float64).view(9,1,1)       # m11 basis
    threshold=(9*torch.finfo(torch.float32).eps)**2
    flow.f=(feq+1e-4*shear+(threshold*rho/20.25)**.5*higher).float()
    eps=torch.finfo(torch.float32).eps
    # Precondition, measured with the reference kernel's own decomposition.
    double=lt.TaylorGreenVortex(lt.Context('cpu',torch.float64,use_native=False),[1,1],10,.05)
    double.units=flow.units;double.f=flow.f.double()
    collision=lt.KBCCollision();collision._initialize(double)
    fneq=double.f-double.equilibrium(double)
    delta_s=collision.compute_s_seq_from_m(double.f,collision.kbc_moment_transform(double.f))
    delta_s-=collision.compute_s_seq_from_m(double.f,collision.kbc_moment_transform(double.equilibrium(double)))
    sum_h=double.rho((fneq-delta_s)**2/double.equilibrium(double)).item()
    assert threshold*rho*2<sum_h<threshold/rho/2
    public=lt.KBCCollision()(flow)
    compensated=lt.KBCCollision()._collide_compensated(flow,eps)
    np.testing.assert_array_equal(compensated.numpy(),public.numpy())
    # With the guard on, the stabilizer would be 2 instead of about 1.
    guarded=(double.f-collision.beta*(2*delta_s+2*(fneq-delta_s))).float()
    assert (public-guarded).abs().max()>3*torch.finfo(torch.float32).eps*public.abs().max()
