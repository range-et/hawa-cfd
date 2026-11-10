"""Near-equilibrium KBC must not amplify FP32 cancellation into a load change."""
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
