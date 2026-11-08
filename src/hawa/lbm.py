"""D2Q9 BGK solver, periodic in both directions, in lattice units.

This independent minimal implementation is a runtime/physics verification case,
not a port of Lettuce or an architectural airflow solver.
"""

from dataclasses import dataclass
import math
import time

import torch

from .backends import Backend

VELOCITIES = ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1),
              (1, 1), (-1, 1), (-1, -1), (1, -1))
WEIGHTS = (4 / 9, 1 / 9, 1 / 9, 1 / 9, 1 / 9,
           1 / 36, 1 / 36, 1 / 36, 1 / 36)


@dataclass(frozen=True)
class VortexConfig:
    size: int = 64
    tau: float = 0.8
    speed: float = 0.04

    def __post_init__(self):
        if not isinstance(self.size, int) or isinstance(self.size, bool) or self.size < 16:
            raise ValueError("size must be an integer >= 16")
        if not math.isfinite(self.tau) or self.tau <= 0.5:
            raise ValueError("tau must be finite and > 0.5")
        if not math.isfinite(self.speed) or not 0 < self.speed <= 0.08:
            raise ValueError("speed must be in (0, 0.08] lattice units")


class VortexSimulation:
    """Persistent state; callers can advance in bounded chunks for UI integration."""

    def __init__(self, backend: Backend, config=None):
        self.backend = backend
        self.config = config or VortexConfig()
        self.iteration = 0
        self.elapsed_seconds = 0.0
        self.dtype = torch.float32
        kwargs = {"device": backend.device, "dtype": self.dtype}
        self.c = torch.tensor(VELOCITIES, **kwargs)
        self.w = torch.tensor(WEIGHTS, **kwargs)[:, None, None]
        n = self.config.size
        axis = torch.arange(n, **kwargs) * (2 * math.pi / n)
        y, x = torch.meshgrid(axis, axis, indexing="ij")
        self.initial_u = torch.stack((self.config.speed * torch.sin(x) * torch.cos(y),
                                     -self.config.speed * torch.cos(x) * torch.sin(y)))
        rho = 1 + 0.75 * self.config.speed ** 2 * (torch.cos(2 * x) + torch.cos(2 * y))
        self.f = self._equilibrium(rho, self.initial_u)
        self._next = torch.empty_like(self.f)
        self.initial_mass = float(self.f.sum().cpu())

    def _equilibrium(self, rho, u):
        cu = self.c[:, 0, None, None] * u[0] + self.c[:, 1, None, None] * u[1]
        uu = (u * u).sum(dim=0)
        return self.w * rho * (1 + 3 * cu + 4.5 * cu * cu - 1.5 * uu)

    def fields(self):
        rho = self.f.sum(dim=0)
        momentum = (self.f[:, None] * self.c[:, :, None, None]).sum(dim=0)
        return rho, momentum / rho[None]

    @torch.no_grad()
    def advance(self, steps):
        if not isinstance(steps, int) or isinstance(steps, bool) or steps < 0:
            raise ValueError("steps must be a nonnegative integer")
        self.backend.synchronize()
        start = time.perf_counter()
        for _ in range(steps):
            rho, u = self.fields()
            self.f.add_((self._equilibrium(rho, u) - self.f) / self.config.tau)
            for q, (cx, cy) in enumerate(VELOCITIES):
                self._next[q].copy_(torch.roll(self.f[q], (cy, cx), (0, 1)))
            self.f, self._next = self._next, self.f
            self.iteration += 1
        self.backend.synchronize()
        self.elapsed_seconds += time.perf_counter() - start
        return self

    @torch.no_grad()
    def diagnostics(self):
        rho, u = self.fields()
        nu = (self.config.tau - 0.5) / 3
        decay = math.exp(-2 * nu * (2 * math.pi / self.config.size) ** 2 * self.iteration)
        expected = self.initial_u * decay
        mass = float(rho.sum().cpu())
        error = float(torch.sqrt(((u - expected) ** 2).sum() / (expected ** 2).sum()).cpu())
        finite = bool(torch.isfinite(self.f).all().cpu())
        positive_density = bool((rho > 0).all().cpu())
        speed = torch.sqrt((u * u).sum(dim=0))
        max_speed = float(speed.max().cpu())
        energy = float((0.5 * (u * u).sum(dim=0)).mean().cpu())
        mass_drift = abs(mass - self.initial_mass) / self.initial_mass
        return {
            "backend": self.backend.info(), "size": self.config.size,
            "steps": self.iteration, "tau": self.config.tau,
            "viscosity_lattice": nu, "precision": "float32",
            "finite": finite, "positive_density": positive_density,
            "relative_mass_drift": mass_drift,
            "velocity_relative_l2_error": error,
            "max_speed_lattice": max_speed, "max_mach": max_speed * math.sqrt(3),
            "mean_kinetic_energy": energy,
            "expected_mean_kinetic_energy": self.config.speed ** 2 / 4 * decay ** 2,
            "advance_seconds": self.elapsed_seconds,
            "mlups": self.iteration * self.config.size ** 2 / max(self.elapsed_seconds, 1e-12) / 1e6,
            "passed": finite and positive_density and mass_drift < 1e-4 and error < 0.05,
        }

    @torch.no_grad()
    def snapshot(self):
        rho, u = self.fields()
        return {"density": rho.cpu().numpy().copy(), "velocity": u.cpu().numpy().copy(),
                "iteration": self.iteration}
