"""Poll-driven Rhino MCP acceptance pilot; never executes host actions itself.

The caller executes request.cs through Rhino MCP, then calls ``poll``. Each
request has an identity; old/missing replies cannot earn a pass. No host waits.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import time
import uuid


def create(root, output, timeout=180.0, now=None, document=None):
    """Create new evidence storage; never reuse a previous run's output."""
    if type(document) is not int or document <= 0:
        raise ValueError("Explicit scratch Rhino document serial required")
    root, output = Path(root).resolve(), Path(output).resolve()
    if not 0 < timeout <= 3600:
        raise ValueError("Timeout must be in (0, 3600] seconds")
    sources = [next((root / "examples/grasshopper").glob(str(n) + "-*.gh")) for n in (31, 32)]
    output.mkdir(parents=True, exist_ok=False)
    copies, hashes = [], {}
    for source in sources:
        data = source.read_bytes()
        target = output / source.name
        target.write_bytes(data)
        copies.append(str(target))
        hashes[str(source)] = hashlib.sha256(data).hexdigest()
    stamp = time.time() if now is None else now
    state = dict(run_id=uuid.uuid4().hex, sequence=0, phase="preflight", status="running",
                 root=str(root), output=str(output), examples=copies, source_hashes=hashes,
                 index=0, owned=None, original_gh=None, rhino_serial=document,
                 timeout=timeout, deadline=stamp + timeout, failure=None, results=[])
    publish(state)
    return state


def advance(state, reply, now=None, cancel=False, recovered_owned=None):
    """Advance one acknowledged host operation; cleanup precedes failure exit."""
    state = json.loads(json.dumps(state))
    if state["status"] != "running":
        raise ValueError("Run is terminal")
    stamp = time.time() if now is None else now
    expired = stamp >= state["deadline"]
    if reply is None:
        if not (cancel or expired):
            raise ValueError("Host reply pending; execute request or cancel")
        reply = dict(run_id=state["run_id"], sequence=state["sequence"], phase=state["phase"])
    if (reply.get("run_id"), reply.get("sequence"), reply.get("phase")) != (
            state["run_id"], state["sequence"], state["phase"]):
        raise ValueError("Missing or stale host acknowledgement")
    phase = state["phase"]
    state["owned"] = state["owned"] or recovered_owned or reply.get("owned")
    error = reply.get("error") or ("Cancelled by operator" if cancel else None)
    if expired:
        error = "Timeout in " + phase
    if error:
        state["failure"] = state["failure"] or error
        if phase in ("close", "cleanup"):
            state["status"] = "blocked"
        elif state["owned"]:
            state["phase"] = "close"
        else:
            state["status"] = "failed"
    elif phase == "preflight":
        if reply.get("safe") is not True or reply.get("rhino_serial") != state["rhino_serial"]:
            state["failure"], state["status"] = "Unsafe host preflight", "blocked"
        else:
            state.update(rhino_serial=reply["rhino_serial"], original_gh=reply["original_gh"], phase="open")
    elif phase == "open":
        state.update(owned=reply["owned"], phase="prepare")
    elif phase == "prepare":
        if reply["ready"] is True:
            state["phase"] = "start"
    elif phase == "start":
        state["phase"] = "observe"
    elif phase == "observe":
        if reply["passed"] is True:
            state["results"].append(reply)
            state["phase"] = "close"
    elif phase == "close":
        state["phase"] = "cleanup"
    elif phase == "cleanup":
        if reply["clean"] is True:
            state["owned"] = None
            state["index"] += 1
            if state["failure"]:
                state["status"] = "failed"
            elif state["index"] == len(state["examples"]):
                state["status"] = "passed"
            else:
                state["phase"] = "open"
    else:
        raise ValueError("Unknown phase")
    if state["phase"] != phase:
        state["deadline"] = stamp + state["timeout"]
    state["sequence"] += 1
    return state


def publish(state):
    """Write fresh request and durable state; replies are unique per request."""
    output = Path(state["output"])
    state_text = json.dumps(state, indent=2)
    pending = output / "state.tmp"
    pending.write_text(state_text)
    pending.replace(output / "state.json")
    if state["status"] == "running":
        template = (Path(__file__).with_name("host_acceptance.cs")).read_text()
        encoded = base64.b64encode(state_text.encode()).decode()
        (output / "request.cs").write_text(template.replace("__REQUEST_BASE64__", encoded))
        audit = Path(__file__).with_name("host_acceptance_audit.py").read_text()
        (output / "audit.py").write_text(audit.replace("__REQUEST_BASE64__", encoded))
    else:
        (output / "request.cs").unlink(missing_ok=True)
        (output / "audit.py").unlink(missing_ok=True)


def main(argv=None):
    """Create or advance the pilot using the latest identity-bound MCP reply."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--root", type=Path, required=True)
    start.add_argument("--output", type=Path, required=True)
    start.add_argument("--timeout", type=float, default=180)
    start.add_argument("--document", type=int, required=True)
    poll = sub.add_parser("poll")
    poll.add_argument("--output", type=Path, required=True)
    poll.add_argument("--cancel", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "start":
        state = create(args.root, args.output, args.timeout, document=args.document)
    else:
        state = json.loads((args.output / "state.json").read_text())
        reply_path = args.output / ("reply-%04d.json" % state["sequence"])
        reply = json.loads(reply_path.read_text()) if reply_path.exists() and not args.cancel else None
        owner_path = args.output / "ownership.json"
        owner = json.loads(owner_path.read_text()) if owner_path.exists() else None
        if owner is not None and owner["run_id"] != state["run_id"]:
            raise ValueError("Wrong ownership record")
        state = advance(state, reply, cancel=args.cancel,
                        recovered_owned=owner["owned"] if owner is not None else None)
        publish(state)
    print(json.dumps({key: state[key] for key in ("run_id", "sequence", "phase", "status", "failure")}))
    return 0 if state["status"] in ("running", "passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
