# Native Hawa through Rhino MCP

Read `rhino-mcp.md` first. Use an isolated test document. Preserve user files and never kill Rhino.

For Hawa 0.5, run the `Hawa` command and use the public `Hawa.Shared.CaseHub` API from `run_csharp`. MCP's C# compiler may not reference the plugin assembly automatically. This public reflection adapter works without accessing private fields:

```csharp
var hub = AppDomain.CurrentDomain.GetAssemblies()
    .First(a => a.GetName().Name == "Hawa.Shared")
    .GetType("Hawa.Shared.CaseHub");
object Call(string method, params object[] args) =>
    hub.GetMethod(method).Invoke(null, args);
uint document = __rhino_doc__.RuntimeSerialNumber;
dynamic c = Call("Get", document);
Console.WriteLine(c.Describe());
```

Use `Edit(document, JsonObject patch, (long)c.Version, "panel", true)` to apply a validated change with undo. Supported keys: speed, cell, width, target, device, field, setup, view. Use `Run(document)`, `Pause(document)`, `Cancel(document)`, `Reset(document)` and `Save(document)`. `Restore(document, json)` validates settings and stays idle. Do not write CaseState fields directly. Do not call Tick in a wait loop; the plugin already polls on its timer.

Read Describe on later MCP turns to observe progress. Pause is cooperative; wait for the reported paused state before comparing steps. Fields are queried asynchronously, so a completed solver may precede a field update. Require `outdated == false`, and compare `result_steps` with the required capture step. `steps` is solver progress; `result_steps` and `result_time_seconds` describe the field actually captured. Physical edits stop the old session. Field and target edits increment Version while retaining the physical revision.

Use the Version captured when reading the settings as `expectedVersion`; do not reread it just before submitting a delayed patch. A version conflict requires reading and reconciling the new settings. Do not retry an old patch blindly. `CaseState` is a read-only live view. Its JSON getters return detached copies. Read and submit commands on Rhino's UI thread.

`ViewError` reports a field-query failure separately from a solver/control `Fault`. Use `RefreshView(document)` after correcting a view failure; it keeps the solver. A last good native field can remain visible with an outdated label. GH withholds outdated field meshes. `PendingCleanupCount` and `RetryCleanup()` expose retained cleanup work; do not assume a detached session handle proves its worker has already exited.

Linked Case owns its binding protocol. For a custom adapter, `Bind(case, ownerGuid, drivenKeys)` returns a lease. Use `EditFromBinding(document, caseId, ownerGuid, lease, patch, expectedVersion)` and `Unbind(case, ownerGuid, lease)`. Configure direct-slider precision with `ConfigureBinding`. Never impersonate a panel writer to bypass computed-input ownership. One component may bind a case at a time. Defer native-to-GH slider changes to a validated GH pre-solution callback, never to `SolveInstance`.

The shared service is scoped by document runtime serial, while the persisted case ID identifies saved settings. Use the injected `__rhino_doc__`, not an assumed active document. A Linked Case definition carries its case ID after first binding. Never force it onto another document's case. Use a fresh component or the distributed unbound template.

To inspect live binding, get the GH document through the GH MCP tools. Change connected slider values through their public slider API and expire the slider. Computed inputs are panel-read-only. Check runtime messages after changes.

Use `scripts/create_native_example.cs` and `scripts/verify_native_prototype.cs` only in the isolated developer test setup described in their comments. They create/close test GH documents. Adjust the repository path first. Tests are nonblocking and write their completion report to results/v05.

Additional maintainer checks: `scripts/verify_state_hardening.cs` exercises live
sync, invalid inputs, units and CPU/MPS lifecycle; `scripts/verify_binding_callbacks.cs`
exercises duplicate owners and replacement cases. Both create their own temporary
definitions. See [the architecture review](../architecture-v0.5.md) for contracts
and remaining release gates.


## Hawa 0.5 selected geometry

The expanded native workflow is described in `../native-v0.5.md`. Schema 2 adds
`setup` and `view`; schema 1 still reads as the block preset. `Setup` and `View`
return detached JSON copies. Edit a complete copy through `CaseHub.Edit` with the
version read before editing. Setup coordinates are metres. View edits preserve
physics; geometry/domain/fluid edits invalidate the run.

The public `Hawa.Native.NativeGeometry` adapter in `Hawa.Rhino` provides
`SelectObjects(documentSerial, IEnumerable<Guid>, fitDomain)` and
`FitDomain(documentSerial)`. Use object IDs from the intended document. Selection
requires valid closed meshes or solid Breps. Do not call the asynchronous geometry
preparer directly as an operating API; use `CaseHub.Run`, then poll on later turns.
Missing objects fail explicitly. Unit changes invalidate selected geometry for
review; the block preset retains display-only unit conversion.

For selected cases, Linked Case accepts speed/cell inputs; disconnect block width.
Use example 22 and save its bound `.gh` together with its `.3dm`. The distributed
GH template stays unbound. Geometry selection and configuration are through the
public native service; agents need no private runtime fields for these operations.

For stationary curved solids, `setup.curved_walls=true` enables fractional wall
links on selected geometry. Missing keys in older archives mean false. The block
preset rejects this flag. `NativeGeometry.Prepare` meshes selected solid Breps
using cell/body-scaled tolerances; closed meshes keep their supplied shape.
GH Geometry also accepts optional solid Breps at input S. See example 14 and
`examples/native-prototype/23-curved-solid.3dm`.

The cleanup queue also owns detached legacy GH jobs and Solve sessions. Failed
requests retry on Rhino Idle even without the native panel. Maintainers can run
`scripts/verify_legacy_cleanup.cs` in an isolated session to inject bridge-close
failures and verify recovery after GH disposal. It temporarily changes the
process transport and stops the native polling timer; do not run it in a user's
active working session. See `../review-cleanup-v0.5.md` for scope and evidence.
