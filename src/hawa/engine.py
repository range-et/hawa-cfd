"""Hawa's adapter to the Python 3.9 Lettuce compatibility engine."""

import time

import lettuce as lt
import torch

from .backends import select_backend
from .cases import make_case


class LettuceSimulation:
    def __init__(self, case="tgv2d-bgk", device="auto", size=None):
        self.backend = select_backend(device)
        self.context = lt.Context(device=self.backend.device, dtype=torch.float32,
                                  use_native=False)
        self.flow, self.simulation = make_case(case, self.context, size)
        self.case = case
        self.elapsed_seconds = 0.0

    @torch.no_grad()
    def advance(self, steps):
        if not isinstance(steps, int) or isinstance(steps, bool) or steps < 0:
            raise ValueError("steps must be a nonnegative integer")
        self.backend.synchronize()
        start = time.perf_counter()
        self.simulation(steps)
        self.backend.synchronize()
        self.elapsed_seconds += time.perf_counter() - start
        return self

    def snapshot(self):
        return {
            "populations": self.flow.f.detach().cpu().numpy().copy(),
            "density": self.flow.rho().detach().cpu().numpy().copy(),
            "velocity": self.flow.u().detach().cpu().numpy().copy(),
            "pressure": self.flow.p_pu.detach().cpu().numpy().copy(),
            "iteration": self.flow.i,
        }

    def diagnostics(self):
        finite = bool(torch.isfinite(self.flow.f).all().cpu())
        positive = bool((self.flow.rho() > 0).all().cpu())
        return {
            "engine": "hawa-lettuce", "engine_version": lt.__version__,
            "case": self.case, "backend": self.backend.info(),
            "resolution": self.flow.resolution, "steps": self.flow.i,
            "finite": finite, "positive_density": positive,
            "passed": finite and positive, "advance_seconds": self.elapsed_seconds,
        }
