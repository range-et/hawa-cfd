# Operate Hawa through Rhino MCP

This guide is for an agent using an installed Hawa plugin in Rhino 8. Use Rhino
MCP tools for the entire simulation workflow. Hawa runs its Python 3.9 engine
inside Rhino; a shell, standalone Python, OpenFOAM and browser control are not
needed. First dependency initialization uses Rhino's package installer and may
take time. Do not start a second initialization while the first is running.

## 1. Inspect the session

1. Call `mcp__rhino__list_slots({})`. Reuse an appropriate existing slot. Do not
   assume the example slot ID `aardvark` exists on another machine.
2. If no instance is available, call `mcp__rhino__spawn_slot({})` once.
3. Call `mcp__rhino__get_context({"slot": "<returned ID>"})` to inspect the
   document and Grasshopper state. Call `g1_start` if Grasshopper is not open.
4. Read the active graph with `g1_get_canvas_graph`, using `include_data: true`
   and a small `sample_size` such as 2. Record object IDs and current controls.
   Preserve any document the user was already editing.

A `slot_not_found` response alone does not establish a crash. Call `list_slots`
to let the router readopt an existing Rhino instance. Check the actual process
and document state before opening another instance.

Use installed examples under the Hawa package's `examples` folder, or this
checkout's `examples/grasshopper`. Paths are machine-specific. The user or host
must supply a location if it cannot be established from the open document.
Do not scan unrelated folders.

## 2. Open a definition safely

Use `run_csharp` for operations not exposed by a dedicated MCP tool. This opens
an example as a separate Grasshopper document and reports its identity:

```csharp
using Grasshopper.Kernel;
var path = @"/absolute/path/to/Hawa/examples/01-tgv3d-bgk.gh";
var io = new GH_DocumentIO();
if (!io.Open(path)) throw new Exception("Cannot open definition: " + path);
var doc = io.Document;
Grasshopper.Instances.DocumentServer.AddDocument(doc);
Grasshopper.Instances.ActiveCanvas.Document = doc;
doc.NewSolution(false);
Console.WriteLine("Opened " + doc.DisplayName + "; ID " + doc.DocumentID);
```

Keep this document ID for later checks. Hawa has an activation guard for saved
Run=true graphs, but inspect toggles before starting. Definitions normally open
with run controls off. Changing the active definition can pause/clear owned
jobs; recheck status when returning to it.

Use `__rhino_doc__` when a script needs the Rhino document. It is the slot's
injected document. Do not use `RhinoDoc.ActiveDoc` to guess the target.

## 3. Change inputs and start

Read the graph first. Address objects by `InstanceGuid`, not list position or a
name that may occur twice. Sliders and toggles are native Grasshopper objects.
For example, after finding a toggle's ID in the graph:

```csharp
using Grasshopper.Kernel.Special;
var doc = Grasshopper.Instances.ActiveCanvas.Document;
var id = new Guid("<toggle InstanceGuid from the graph>");
var toggle = (GH_BooleanToggle)doc.Objects.Single(o => o.InstanceGuid == id);
toggle.Value = true;
toggle.ExpireSolution(false);
doc.NewSolution(false);
```

For a slider, use `GH_NumberSlider.SetSliderValue(decimal)`, expire it and request
one solution. Respect its range. For component inputs with persistent values,
inspect their names and types, clear the old persistent data before assigning a
replacement, then expire the input. Do not detach a source wire to replace its
value unless the user requested a wiring change.

Choose `cpu`, `mps`, `cuda:0` or `auto` in the existing backend input. MPS is the
Apple PyTorch backend. CUDA needs suitable hardware and a compatible installed
PyTorch build. `auto` selects an available accelerator; it does not benchmark
speed. Small moving-mesh cases can run faster on CPU. Do not claim CUDA was
verified from an MPS run.

## 4. Monitor without blocking Rhino

After starting work, return from the MCP call. Poll `g1_get_canvas_graph` in
separate calls. Read runtime errors, the component state, completed iteration
count and output data. Do not repeatedly force new solutions just to poll.
Do not use a busy loop, `Thread.Sleep`, `.Wait()` or an unfinished task's
`.Result` inside `run_csharp`; that can block Rhino's UI thread.

Typical progression is preparation, ready, running, then completed. An async
output may be absent while a query is pending. A component's displayed message
can briefly refer to its previous result. Require the actual expected output
and matching completed state before reporting success.

| Workflow | Start | Pause / resume | Cancel / reset |
| --- | --- | --- | --- |
| Solve | Run true after preparation | Run false / true | Reset true then false clears simulation |
| Evaluate / Motion Evaluate | Enable true | Pause true / false | Enable false cancels |
| Search | Enable evaluator and Run search | Pause search true / false | Run search false; disable evaluator if separately wired |
| Record | Set new absolute directory, Run true | Pause true / false | Run false cancels |
| Playback | Completed manifest and frame index | Change frame index | No simulation job |

Target iterations is an absolute total, not an additional step count. A case
edit creates a new simulation. Keep the initial grid and target small.

Use Hawa Search with completed fitness and candidate IDs. Galapagos can wait
synchronously for fitness and block the workflow; example 09 is retained only
as a historical user file. Use example 10 or 20 for the supported path.

## 5. Inspect and record results

For visualization, connect one Field Snapshot to all views that must share a
simulation time. Keep colour-map ranges fixed for comparisons. Use Domain
Preview for the wireframe. For moving cases, pass the same snapshot to Body
Loads and use its motion-state output with Body Preview and the reference mesh.
Do not display a live body pose over an older recorded field.

Check the field mesh exists, is valid and has faces. Check body meshes are
closed. For recorded results, confirm the manifest reports completion and the
chosen frame exists. Use a new output directory per recording; do not overwrite
another run. A paused or cancelled recording is not a completed recording.

Use `get_viewport_image` to inspect the native preview. Supply a known domain
bounding box when framing it. The tool returns camera and scene metadata; use
that information to diagnose an empty capture. To save a full-resolution image
through MCP, use Rhino's native capture API:

```csharp
var view = __rhino_doc__.Views.ActiveView;
var capture = new Rhino.Display.ViewCapture {
    Width = 1600, Height = 1000, ScaleScreenItems = true,
    DrawAxes = false, DrawGrid = false, DrawGridAxes = false
};
using (var image = capture.CaptureToBitmap(view)) {
    image.Save(@"/absolute/new/output.png", System.Drawing.Imaging.ImageFormat.Png);
}
```

Keep evidence with device, grid, physical time, iteration count and relevant
parameters. Distinguish a smoke test, numerical comparison and convergence
study. Moving loads are experimental and can contain cell-transition spikes.
Mean-field capture is disabled for moving cases; use instantaneous snapshots
and complete-cycle load averages.

## 6. Save a copy and clean up owned work

To preserve a changed definition, use `new GH_DocumentIO { Document = doc }
.SaveQuiet(copyPath)` with a new absolute `.gh` path. Do not overwrite the
shipped examples or the user's original without instruction.

Disable the relevant run controls before closing. Remove and dispose only the
document created for this task. Match the recorded document ID; do not clear the
whole document server:

```csharp
using Grasshopper.Kernel;
var ownedId = new Guid("<DocumentID recorded when opened>");
var owned = Grasshopper.Instances.DocumentServer.ToArray()
    .SingleOrDefault(d => d.DocumentID == ownedId);
if (owned != null) {
    if (Grasshopper.Instances.ActiveCanvas.Document == owned)
        Grasshopper.Instances.ActiveCanvas.Document = null;
    Grasshopper.Instances.DocumentServer.RemoveDocument(owned);
    owned.Dispose();
}
```

Component disposal cancels owned jobs. A later poll or graph inspection must
show that work has stopped. Do not use private runtime reflection as the normal
control API; repository verification scripts use it only for internal audits.

Do not call `close_slot`, send process signals or force-quit Rhino. A plugin
assembly update requires a normal application quit after saving user work. If
the available MCP tools cannot perform a safe normal quit, leave Rhino running
and explain the pending restart. Never discard a user's document to obtain a
clean test environment.

## Maintainer scripts and scope

`annotate_grasshopper_examples.cs` and `capture_example_layouts.cs` can be run
through `run_csharp` after updating their checkout path. They preserve functional
connections; the annotation pass excludes legacy example 09 and keeps backups
under `results/motion/example-backups`.

The `verify_*.cs` scripts are developer harnesses. Some close generated test
documents, change values in memory, or inspect internal runtime fields. Read a
harness before running it and use a dedicated test session. They are not a safe
substitute for the document-scoped operations above in a user's working session.

Read [the plugin guide](../plugin.md), [moving-surface limits](../moving-surfaces-v0.4.md)
and [the example catalogue](../../examples/grasshopper/README.md). The installed
bundle contains this guide under `docs/agents` and the catalogue under `examples`.
