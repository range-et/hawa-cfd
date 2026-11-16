"""Opt-in pytest plugin: model a CPU-only host for forked mutation studies.

Device qualification must never load this plugin. CUDA_VISIBLE_DEVICES does not
hide Apple MPS, and a mutant that removes a CPU argument can otherwise initialise
Metal after fork. Availability is deliberately false in this study process.
"""
import torch


def unavailable():
    return False


def pytest_configure(config):
    torch.cuda.is_available = unavailable
    torch.backends.mps.is_available = unavailable
