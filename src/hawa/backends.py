"""Explicit device selection; fallback happens only during auto selection."""

from dataclasses import dataclass, field
from typing import List

import torch


@dataclass
class Backend:
    device: torch.device
    requested: str
    notes: List[str] = field(default_factory=list)

    def synchronize(self):
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
        elif self.device.type == "mps":
            torch.mps.synchronize()

    def info(self):
        return {
            "requested": self.requested,
            "selected": str(self.device),
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "mps_available": torch.backends.mps.is_available(),
            "notes": self.notes,
        }


def _probe(device):
    """Exercise the same operation families as the solver, and check results."""
    with torch.no_grad():
        x = torch.arange(16, dtype=torch.float32, device=device).reshape(4, 4)
        y = torch.roll(x, (1, -1), (0, 1))
        actual = torch.where(y >= 0, y * 0.5, y).sum().cpu().item()
        if abs(actual - 60.0) > 1e-5:
            raise RuntimeError("Device operation probe returned incorrect results")


def select_backend(requested="auto"):
    requested = requested.lower()
    if requested == "cuda":
        requested = "cuda:0"
    try:
        device = None if requested == "auto" else torch.device(requested)
    except (RuntimeError, ValueError) as exc:
        raise ValueError("Use auto, cpu, mps, or cuda:<index>") from exc
    if device is not None and (
        device.type not in ("cpu", "mps", "cuda")
        or (device.type != "cuda" and device.index is not None)
    ):
        raise ValueError("Use auto, cpu, mps, or cuda:<index>")

    notes = []
    candidates = [device] if device is not None else [
        torch.device("cuda:0"), torch.device("mps"), torch.device("cpu")
    ]
    for candidate in candidates:
        try:
            if candidate.type == "cuda" and not torch.cuda.is_available():
                raise RuntimeError("CUDA is unavailable; check GPU, driver and PyTorch build")
            if candidate.type == "mps" and not torch.backends.mps.is_available():
                raise RuntimeError("MPS is unavailable; check architecture, macOS and PyTorch build")
            _probe(candidate)
            backend = Backend(candidate, requested, notes)
            backend.synchronize()
            return backend
        except (RuntimeError, NotImplementedError) as exc:
            if device is not None:
                raise RuntimeError("Cannot use {}: {}".format(candidate, exc)) from exc
            notes.append("{}: {}".format(candidate, exc))
    raise RuntimeError("No usable backend: " + "; ".join(notes))
