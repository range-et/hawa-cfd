"""Read-only maintainer runtime audit, executed by Rhino MCP before preflight/cleanup.

Do not import a second Hawa install: inspect only modules already loaded in this
Rhino interpreter. No private EmbeddedRuntime reflection or state mutation.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

request = json.loads(base64.b64decode("__REQUEST_BASE64__").decode())
plugin = sys.modules.get("hawa.plugin")
jobs = sys.modules.get("hawa.jobs")
report = dict(run_id=request["run_id"], sequence=request["sequence"],
              pid=os.getpid(), time=time.time(), jobs=0, sessions=0,
              workers=[t.name for t in threading.enumerate() if t.name.startswith("Hawa ")],
              sources={})
if plugin is not None:
    with plugin.REGISTRY_LOCK:
        report["sessions"] = len(plugin.SESSIONS)
    path = Path(plugin.__file__)
    report["sources"]["plugin"] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
if jobs is not None:
    with jobs.LOCK:
        report["jobs"] = len(jobs.JOBS)
    path = Path(jobs.__file__)
    report["sources"]["jobs"] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
path = Path(request["output"]) / ("audit-%04d.json" % request["sequence"])
path.write_text(json.dumps(report, indent=2))
print(json.dumps(report))
