"""Regressions for MPS memory release on session/job teardown (#76)."""
import pytest
import torch

from hawa.plugin import Session, SESSIONS, dispatch


def _small_case(shape=(12, 10, 8)):
    return {
        "shape": list(shape),
        "dx": 0.25,
        "speed": 2.0,
        "viscosity": 0.02,
        "density": 1.225,
        "mach": 0.05,
        "collision": "regularized",
        "boundaries": ["inlet", "outlet", "periodic", "periodic", "wall", "slip"],
    }


def test_session_close_breaks_references_and_flushes_mps_cache_on_cpu_host(monkeypatch):
    """Covers Session.release() including the MPS cache flush branch on non-MPS CI hosts."""
    s = Session(_small_case(), "cpu")
    SESSIONS[s.id] = s
    calls = []

    class _FakeDev:
        type = "mps"

    monkeypatch.setattr(s.backend, "device", _FakeDev())
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    monkeypatch.setattr(torch.mps, "synchronize", lambda: calls.append("sync"), raising=False)
    monkeypatch.setattr(torch.mps, "empty_cache", lambda: calls.append("empty"), raising=False)

    assert dispatch({"op": "close", "session": s.id}) == {"closed": True}
    assert s.id not in SESSIONS
    assert s.flow is None and s.solver is None and s.initial_f is None
    assert calls == ["sync", "empty"]


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS unavailable")
def test_mps_teardown_returns_current_and_driver_memory():
    """On Apple Silicon MPS, closing a session returns current and driver allocations."""
    torch.mps.synchronize()
    torch.mps.empty_cache()
    before_cur = torch.mps.current_allocated_memory()

    sid = dispatch({"op": "create", "case": _small_case((64, 48, 32)), "device": "mps"})["session"]
    dispatch({"op": "step", "session": sid, "steps": 10})
    peak_drv = torch.mps.driver_allocated_memory()
    assert peak_drv > 100 * 1024 * 1024

    dispatch({"op": "close", "session": sid})
    after_cur = torch.mps.current_allocated_memory()
    after_drv = torch.mps.driver_allocated_memory()
    assert after_cur <= before_cur + 1024 * 1024
    assert after_drv < peak_drv * 0.25


def test_disposed_create_job_releases_owned_session():
    """Cancelling/disposing a create job calls pause + release on its owned session."""
    import time
    from hawa.jobs import JOBS, dispatch_job

    submitted = dispatch_job({"op": "evaluate_submit", "kind": "create", "case": _small_case(), "device": "cpu"})
    jid = submitted["job"]
    deadline = time.time() + 10.0
    while time.time() < deadline:
        snap = dispatch_job({"op": "evaluate_poll", "job": jid})
        if snap["state"] == "completed":
            break
        time.sleep(0.02)
    assert snap["state"] == "completed"
    # Verify job close removes registry entry and session is no longer registered
    sid = snap["result"]["status"]["session"] if "status" in snap["result"] else snap["result"]["session"]
    dispatch_job({"op": "evaluate_control", "job": jid, "action": "close"})
    assert sid not in SESSIONS
    assert jid not in JOBS

