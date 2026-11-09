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
    assert flow.f.dtype == torch.float32 and flow.f.device == before.device
    torch.testing.assert_close(flow.f,before,rtol=2e-6,atol=2e-7)
