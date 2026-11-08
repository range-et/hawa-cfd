# Native Hawa through Rhino MCP

Read `rhino-mcp.md` first. Use an isolated test document. Preserve user files and never kill Rhino.

For the 0.5 prototype, run the `Hawa` command and use the public `Hawa.Shared.CaseHub` API from `run_csharp`. MCP's C# compiler may not reference the plugin assembly automatically. This public reflection adapter works without accessing private fields:

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

Use `Edit(document, JsonObject patch, (long)c.Revision, "panel", true)` to apply a validated change with undo. Supported keys: speed, cell, width, target, device, field. Use `Run(document)`, `Pause(document)`, `Cancel(document)`, `Reset(document)` and `Save(document)`. `Restore(document, json)` validates settings and stays idle. Do not write CaseState fields directly. Do not call Tick in a wait loop; the plugin already polls on its timer.

Read Describe on later MCP turns to observe progress. Pause is cooperative; wait for the reported paused state before comparing steps. Fields are queried asynchronously, so a completed solver may precede a field update. Only use results whose result_revision equals revision. A case edit cancels the old session.

The shared service is scoped by document runtime serial, while the persisted case ID identifies saved settings. Use the injected `__rhino_doc__`, not an assumed active document. A Linked Case definition carries its case ID after first binding. Never force it onto another document's case. Use a fresh component or the distributed unbound template.

To inspect live binding, get the GH document through the GH MCP tools. Change connected slider values through their public slider API and expire the slider. Computed inputs are panel-read-only. Check runtime messages after changes.

Use `scripts/create_native_example.cs` and `scripts/verify_native_prototype.cs` only in the isolated developer test setup described in their comments. They create/close test GH documents. Adjust the repository path first. Tests are nonblocking and write their completion report to results/v05.
