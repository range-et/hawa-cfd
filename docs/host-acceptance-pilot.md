# Sequential Rhino acceptance pilot (#39)

This maintainer pilot sequences **31 (CPU60 probes/vectors)** and **32 (CPU40
recording/playback/body pose)** through Rhino MCP. It does not replace the full
[local acceptance review](local-rhino-acceptance.md), run native Undo/Redo, qualify
numerics, or close [#39](https://github.com/range-et/hawa-cfd/issues/39).
The adapter derives its workflow from `verify_coverage_examples.cs`; the Python
tool is a developer control plane, never a standalone solver.

## Preconditions

Read [the Rhino guide](agents/rhino-mcp.md). Acquire the single host/device lease.
Inspect all open native and GH documents, including GH `AllDocuments`, before
selecting an empty unnamed scratch model in metres with no native Hawa case.
Do not switch documents while user jobs are active. Existing Hawa jobs, sessions,
workers, cleanup requests or refreshes block the pilot, including another
model's. Record the injected `__rhino_doc__` runtime serial and verify actual
native activation. `--document` is explicit operator opt-in to that scratch
model. The native dirty flag is recorded, never cleared: command history can
mark an empty scratch model modified. The runner never changes native geometry,
units or cases and never closes Rhino. Prepare/restore scratch windows separately.

The pilot copies archives into a new run directory, overrides only unconnected
device inputs to CPU, and gives recording unique paths. Original hashes are
rechecked at cleanup. Example 09 is never loaded or copied.

## One action per MCP call

Create fresh evidence storage from the developer checkout:

```sh
.venv/bin/python scripts/host_acceptance.py start \
  --root /absolute/checkout --output /absolute/checkout/results/host-run-NEW \
  --document 123456 --timeout 180
```

1. Read `state.json`. In `preflight` and `cleanup`, execute generated `audit.py`
   through Rhino MCP `run_python`. It inspects already-loaded module registries
   and thread names, without importing a second engine. C# requires a same-process,
   same-run/sequence audit no more than 30 seconds old.
2. Execute `request.cs` through Rhino MCP `run_csharp`, once. It writes
   `reply-NNNN.json`. Return to the agent between calls; never wait inside Rhino.
3. Run `.venv/bin/python scripts/host_acceptance.py poll --output /absolute/run`.
   It emits the next request or records a terminal status. Poll at human-scale
   intervals, e.g. 1–2 seconds. `prepare` and `observe` never force a new solution.
4. Continue until `passed`, `failed` or `blocked`. Owned-only disposal and a fresh
   cleanup audit precede the next example. `blocked` requires operator attention.

Requests check native serial, GH GUID/path, active canvas and sequence. Ownership
is persisted before registration/solution and retained under a per-run AppDomain
key. GH registration must be visible through the active-document filter before
solving. Cleanup also checks `AllDocuments`. No global clear/filter override is
used. The original canvas is restored only when still available and the user has
not chosen another graph.

Replaying a completed request returns its reply. An uncertain in-flight request
is refused by its claim file; do not remove claims and blindly repeat a start.
A lost, stale or absent reply cannot earn success. Explicit cancellation works
even when the response is missing or corrupt:

```sh
.venv/bin/python scripts/host_acceptance.py poll --output /absolute/run --cancel
```

Execute its `close` and `cleanup` requests. A timeout also routes to cleanup;
no worker is killed. Cleanup failure becomes `blocked`, retaining ownership.
If Rhino exits, keep that record as failure evidence and use a new run directory.

## Evidence and limits

Evidence includes run/request identities, archive hashes, installed assembly
locations/file hashes, embedded source hashes, numerical outputs, screenshots
on success and fresh resource counts. Installed-file hashes are not hashes of
in-memory assemblies. Passing requires 60 completed Solve steps, three valid
fluid vectors/probes, and a complete recording with valid playback/body mesh.
Captures still need visual inspection; a saved PNG is not a visual pass.

Run twice in new directories, then verify cancellation/failure recovery, original
content and zero resources. C# maintainer scripts are outside the product
function inventory; Python tests/mutation cannot establish host scheduling.
`verify_grasshopper_examples.cs` remains an obsolete blocking harness, never a
fallback. Timer-based `verify_binding_callbacks.cs` and `verify_state_hardening.cs`
remain separate scoped checks until adapted for explicit failure cleanup.

Sources: [official GH DocumentServer API](https://developer.rhino3d.com/api/gh1/type/grasshopper.kernel.gh-documentserver/)
and [GH Document API](https://developer.rhino3d.com/api/grasshopper/html/T_Grasshopper_Kernel_GH_Document.htm).
Those web references are newer than Rhino 8; the adapter is also compiled against
actual installed SDK references. See [review and omissions](review-host-acceptance-pilot.md).

Ownership records are published by same-directory atomic rename. If that record
is unreadable or malformed, normal polling stops new work and cancellation still
reaches owned cleanup using the host's per-run reference. A valid foreign run ID
remains an error; do not replace it with another document's identity.
