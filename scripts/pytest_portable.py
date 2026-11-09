"""Opt-in upstream test adapter for Hawa's use_native=False execution contract.

Upstream Context() otherwise implicitly enables generated CUDA extensions when
a GPU exists. Keep device/dtype selection unchanged, and change only that omitted
native default. Explicit native=True remains untouched and must be excluded by
the caller. No upstream source or test is modified.
"""
import lettuce as lt

_original = None


def pytest_configure(config):
    global _original
    _original = lt.Context.__init__

    def portable(self, device=None, dtype=None, use_native=None):
        return _original(self, device=device, dtype=dtype,
                         use_native=False if use_native is None else use_native)

    lt.Context.__init__ = portable


def pytest_unconfigure(config):
    if _original is not None:
        lt.Context.__init__ = _original
