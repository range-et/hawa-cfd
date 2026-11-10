"""Hawa numerical models. Upstream models retain their archived behaviour."""
import math
import torch
import lettuce as lt


class SmagorinskyV1(lt.Collision):
    """BGK with |S|=sqrt(2 S:S), solved analytically for effective relaxation.

    A = Pi_neq/(2 rho cs²), S=-A/tau_eff and
    tau_eff = tau_0 + 3 Cs² sqrt(2 A:A)/tau_eff (D3Q19, dx=dt=1).
    No force model is supported by this version.
    """
    def __init__(self, tau, smagorinsky_constant=.17):
        if not math.isfinite(tau) or tau <= .5:
            raise ValueError('Smagorinsky requires tau > 0.5')
        if not math.isfinite(smagorinsky_constant) or smagorinsky_constant < 0:
            raise ValueError('Smagorinsky constant must be finite and nonnegative')
        self.tau = tau
        self.constant = smagorinsky_constant
        self.tau_eff = tau

    def __call__(self, flow):
        rho = flow.rho()
        equilibrium = flow.equilibrium(flow, rho, flow.u())
        a = flow.shear_tensor(flow.f-equilibrium)/(2*rho*flow.stencil.cs**2)
        magnitude = torch.sqrt(2*torch.einsum('ab...,ab...->...', a, a))
        self.tau_eff = .5*(self.tau+torch.sqrt(self.tau**2+12*self.constant**2*magnitude))
        return flow.f-(flow.f-equilibrium)/self.tau_eff

    def native_available(self):
        return False

    def native_generator(self, index):
        raise NotImplementedError('Use the portable tensor path')
