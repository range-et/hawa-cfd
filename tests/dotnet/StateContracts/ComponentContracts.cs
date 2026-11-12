using System.Collections;
using System.Drawing;
using System.Text.Json.Nodes;
using Eto.Forms;
using GH_IO.Serialization;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Hawa.Grasshopper;
using Hawa.Shared;
using Rhino.Geometry;

// Grasshopper host harness: production component sources linked against the
// GH/Rhino doubles in GrasshopperDouble.cs and HostDouble.cs. Every linked file
// is exercised in full; each test asserts observable outputs, labels, runtime
// messages and bridge requests. Doubles cannot prove live GH scheduling; that
// remains a Rhino acceptance check.
static class ComponentContracts
{
    static readonly object D = GhAccess.Default;

    public static void Run(Action<string, Action> test, Action<bool, string> assert)
    {
        var doc = new GH_Document { FilePath = "/work/defs/case.gh" };
        void Reset() { foreach (var t in UITimer.Active.ToArray()) t.Pulse(); global::Grasshopper.Instances.DocumentServer.Clear(); foreach (var t in UITimer.Active.ToArray()) t.Pulse(); GH_Document.EnableSolutions = true; global::Grasshopper.Instances.DocumentServer.Add(doc); }
        void Pulse() { foreach (var t in UITimer.Active.ToArray()) t.Pulse(); }
        GhAccess Solve(GH_Component c, params object?[] inputs) { var da = new GhAccess(c, inputs); c.Compute(da); return da; }
        HawaGoo Goo(string json) => new((JsonObject)JsonNode.Parse(json)!);
        string Json(JsonNode? n) => n?.ToJsonString() ?? "null";
        bool Has(GH_Component c, GH_RuntimeMessageLevel level, string text) => c.RuntimeMessages.Contains((level, text));

        test("GH runtime types expose assembly info, goo archive and bridge wrappers", () => {
            var info = new HawaInfo();
            assert(info.Name == "Hawa" && info.Description.StartsWith("Embedded Python 3.9 GPU LBM") && info.Id == new Guid("e8e18bc1-cb70-4d66-9969-6fd9ec6d152e")
                && info.AuthorName == "Hawa contributors" && info.AuthorContact.Contains("THIRD_PARTY_NOTICES.md") && info.Icon!.Name == "Hawa", "Assembly info changed");
            var empty = new HawaGoo();
            assert(empty.Value == "{}" && empty.IsValid && empty.TypeName == "Hawa Object" && empty.ToString() == "Hawa Object", "Empty goo wrong");
            assert(!new HawaGoo { Value = "" }.IsValid, "Empty JSON text reported valid");
            var goo = Goo("""{"kind":"Frame","label":"frame 7","n":[1]}""");
            assert(goo.TypeName == "Hawa Frame" && goo.ToString() == "frame 7" && goo.TypeDescription.Contains("embedded runtime"), "Goo labels wrong");
            var copy = (HawaGoo)goo.Duplicate(); var data = goo.Data; data["n"]![0] = 9;
            assert(copy.Value == goo.Value && goo.Data["n"]![0]!.GetValue<int>() == 1 && !ReferenceEquals(copy, goo), "Duplicate or Data aliases the stored JSON");
            string text = ""; int number = 0;
            assert(goo.CastTo(ref text) && text == goo.Value && !goo.CastTo(ref number) && number == 0, "Cast contract wrong");
            var archive = new GhArchive(0, 0); var restored = new HawaGoo();
            assert(goo.Write(archive) && archive.Strings["json"] == goo.Value && restored.Read(archive) && restored.Data["label"]!.GetValue<string>() == "frame 7", "Archive round trip lost data");
            var source = new JsonObject { ["a"] = new JsonArray(1) }; var clone = Hawa.Grasshopper.JsonCompatibility.DeepClone(source); clone["a"]![0] = 2;
            assert(source["a"]![0]!.GetValue<int>() == 1 && clone["a"]![0]!.GetValue<int>() == 2, "DeepClone aliases");
            using var bridge = new GhBridge { Respond = r => new JsonObject { ["echo"] = r["op"]!.DeepClone() } };
            assert(Hawa.Grasshopper.EmbeddedRuntime.Root == "/hawa-test-root" && Hawa.Grasshopper.EmbeddedRuntime.Call(new() { ["op"] = "info" })["echo"]!.GetValue<string>() == "info", "Bridge wrapper changed request or root");
        });

        test("HawaComponent reads Hawa objects, local paths and request helpers", () => {
            var probe = new ProbeComponent { Document = doc };
            var da = new GhAccess(probe, Goo("""{"k":1}"""), new GH_ObjectWrapper(Goo("""{"k":2}""")), new GH_ObjectWrapper("""{"k":3}"""), new GH_String("""{"k":4}"""), null, new GH_ObjectWrapper(5));
            for (int i = 0; i < 4; i++) assert(ProbeComponent.Object(da, i)["k"]!.GetValue<int>() == i + 1, "Object form " + i + " not read");
            var missing = Catch(() => ProbeComponent.Object(da, 4)); var wrong = Catch(() => ProbeComponent.Object(da, 5));
            assert(missing is ArgumentException { Message: "Missing Hawa input" } && wrong is ArgumentException { Message: "Connect a compatible Hawa object" }, "Bad input accepted");
            assert(Json(ProbeComponent.NumberArray(new[] { 1.5, -2 })) == "[1.5,-2]" && Json(ProbeComponent.Operation("status", "s1")) == """{"op":"status","session":"s1"}""", "Helpers changed");
            assert(probe.Path("/tmp/a/../b.npz") == "/tmp/b.npz" && probe.Path("out/x.npz") == "/work/defs/out/x.npz", "Path resolution wrong");
            var unsaved = new ProbeComponent { Document = new GH_Document() };
            assert(Catch(() => unsaved.Path("x.npz")) is ArgumentException { Message: "Save the definition before using relative file paths" } && Catch(() => new ProbeComponent().Path("x")) is ArgumentException, "Relative path accepted without a saved definition");
            HawaIcons.Requests.Clear();
            assert(probe.IconForTest!.Name == "Probe" && HawaIcons.Requests.SequenceEqual(new[] { "Probe" }) && probe.Category == "Hawa" && probe.SubCategory == "test", "Icon or category wrong");
        });

        test("HawaComponent archive reads hide appended parameters from older definitions", () => {
            // Archived counts inside [the original count, the current count] hide the appended ports from GH's reader.
            foreach (var (component, inputs, outputs, seen, inRange) in new (GH_Component, int, int, (int, int), bool)[] {
                (new GeometryComponent(), 2, 2, (2, 2), true), (new GeometryComponent(), 1, 2, (3, 3), false), (new GeometryComponent(), 4, 3, (3, 3), false), (new GeometryComponent(), 2, 1, (3, 3), false), (new GeometryComponent(), 3, 4, (3, 3), false),
                (new EvaluateComponent(), 6, 4, (6, 4), true), (new BoundaryCaptureComponent(), 4, 3, (4, 3), true), (new BoundaryPatchComponent(), 6, 1, (6, 1), true), (new ProbeComponent(), 1, 1, (1, 1), true) }) {
                var before = component.Params.Input.ToArray(); var outBefore = component.Params.Output.ToArray();
                assert(component.Read(new GhArchive(inputs, outputs)), "Read failed");
                assert(component.BaseReads == 1 && (component.InputsAtBaseRead, component.OutputsAtBaseRead) == seen, $"{component.GetType().Name} {inputs}/{outputs}: base read saw {component.InputsAtBaseRead}/{component.OutputsAtBaseRead}");
                assert(component.Params.Input.SequenceEqual(before) && component.Params.Output.SequenceEqual(outBefore) && component.Params.ParameterChanges == (inRange ? 1 : 0), "Parameters reordered, lost or not refreshed");
            }
            var failing = new GeometryComponent { BaseReadResult = false }; assert(!failing.Read(new GhArchive(2, 2)) && failing.Params.Input.Count == 3, "Base read failure hidden or params lost");
            var plane = new PlaneFieldComponent(); var probe = new ProbeComponent(); plane.Params.Input[0].Access = GH_ParamAccess.item;
            assert(plane.Read(new GhArchive(6, 3)) && plane.Params.Input[0].Access == GH_ParamAccess.list && probe.Read(new GhArchive(1, 1)) && probe.Params.Input[0].Access == GH_ParamAccess.item, "Composed-frame port access not restored");
            var record = new RecordComponent(); record.Params.Input[0].Optional = false;
            assert(record.Read(new GhArchive(7, 3)) && record.Params.Input[0].Optional, "Record case input not optional after reading");
        });

        test("SolveInstance replaces a stale status when inputs go away and labels failures (#74)", () => {
            Reset(); using var bridge = new GhBridge(); string state = "completed";
            bridge.Respond = r => r["op"]!.GetValue<string>() switch { "evaluate_submit" => new() { ["job"] = "q" + bridge.Ops("evaluate_submit").Count() }, "evaluate_poll" => new() { ["state"] = state, ["error"] = "bad case", ["result"] = new JsonObject { ["ok"] = true } }, _ => null };
            var check = new CheckComponent { Document = doc }; var da = Solve(check, Goo("""{"cell":1}"""));
            assert(check.Message == "completed" && da.Out<bool>(0) && da.Out<string>(1) == """{"ok":true}""" && Json(bridge.Ops("evaluate_submit").Single()["request"]) == """{"op":"check","case":{"cell":1}}""", "Check result wrong");
            Solve(check, new object?[] { null });
            assert(check.Message == LifecycleText.WaitingForInput && bridge.Ops("evaluate_control").Single()["job"]!.GetValue<string>() == "q1", "Missing upstream kept a stale completed label or leaked the job");
            var fresh = new CheckComponent(); Solve(fresh, new object?[] { null }); assert(fresh.Message == null, "A never-run component invented a status");
            var plane = new PlaneFieldComponent { Message = "domains: 2" }; Solve(plane, null, D); assert(plane.Message == "waiting for frames", "Component-specific waiting label overwritten");
            state = "failed"; Solve(check, Goo("""{"cell":2}"""));
            assert(check.Message == LifecycleText.Failed && check.Errors.SequenceEqual(new[] { "bad case" }), "Query failure not labelled");
            var solve = new SolveComponent { Message = "running / ok" }; Solve(solve, Goo("{}"), D, -1, D, D);
            assert(solve.Message == "failed" && solve.Errors.Single() == "Target steps must be nonnegative" && bridge.Ops("evaluate_submit").Count() == 2, "Exception kept the stale running label");
            var quiet = new SolveComponent(); Solve(quiet, Goo("{}"), D, -1, D, D); assert(quiet.Message == null && quiet.Errors.Count == 1, "Failure invented a label on a never-run component");
            state = "completed"; var dup = new CheckComponent(); Solve(dup, new GhMany(Goo("{}"), Goo("{}")));
            assert(dup.Errors.Single().StartsWith("Use one value per item input") && bridge.Ops("evaluate_submit").Count() == 2, "Several items started background work");
            foreach (var c in new HawaComponent[] { new GeometryComponent(), new EvaluateComponent(), new RefinedSolveComponent(), new SearchComponent(), new MovingBodyComponent(), new MotionEvaluateComponent() }) {
                Solve(c, c.Params.Input.Select((_, i) => i == 0 ? new GhMany(Goo("{}"), Goo("{}")) : (object)Goo("{}")).ToArray()); assert(c.Errors.Single().StartsWith("Use one value per item input"), c.GetType().Name + " accepted several items"); }
            var runtime = new RuntimeComponent(); var ok = Solve(runtime, new GhMany(false, true)); assert(runtime.Errors.Count == 0 && ok.Outputs.Count == 2, "Foreground component rejected several items");
            Reset();
        });

        test("document switch reports cancellation instead of a stale running label (#74)", () => {
            Reset(); using var bridge = new GhBridge();
            bridge.Respond = r => r["op"]!.GetValue<string>() switch { "evaluate_submit" => new() { ["job"] = "q1" }, "evaluate_poll" => new() { ["state"] = "running" }, _ => null };
            var check = new CheckComponent { Document = doc }; Solve(check, Goo("{}"));
            assert(check.Message == "running" && HawaPollScheduler.PendingCount == 1, "Running query not polled");
            Pulse(); assert(HawaPollScheduler.PendingCount == 1, "Current poll predicate rejected");
            check.DocumentContextChanged(doc, GH_DocumentContext.Unloaded);
            assert(check.Message == LifecycleText.DocumentInactive && Has(check, GH_RuntimeMessageLevel.Remark, LifecycleText.DocumentInactiveReason) && HawaPollScheduler.PendingCount == 0
                && bridge.Ops("evaluate_control").Single()["job"]!.GetValue<string>() == "q1" && check.BaseContextChanges == 1, "Document switch kept the running label or the job");
            check.RuntimeMessages.Clear(); check.Message = "completed";
            foreach (var context in new[] { GH_DocumentContext.Close, GH_DocumentContext.Lock, GH_DocumentContext.Open }) check.DocumentContextChanged(doc, context);
            assert(check.Message == "completed" && check.RuntimeMessages.Count == 0 && check.Expirations == 0, "Only an inactive document is labelled cancelled");
            check.DocumentContextChanged(doc, GH_DocumentContext.Loaded); check.DocumentContextChanged(doc, GH_DocumentContext.Unlock);
            assert(check.Expirations == 2 && check.BaseContextChanges == 6, "Reactivation did not recompute");
            var idle = new IdleProbe(); idle.DocumentContextChanged(doc, GH_DocumentContext.Unloaded); assert(idle.Message == null && idle.RuntimeMessages.Count == 0, "Idle component labelled cancelled");
            Solve(check, Goo("{}")); check.RemovedFromDocument(doc);
            assert(bridge.Ops("evaluate_control").Count() == 2 && HawaPollScheduler.PendingCount == 0 && check.BaseRemovals == 1, "Removal leaked the job or poll");
            Reset();
        });

        test("composed views name missing children and duplicate frames (#74)", () => {
            Reset(); using var bridge = new GhBridge();
            var f1 = Goo("""{"frame":{"id":1},"case":{"spacing":1}}"""); var f3 = Goo("""{"frame":{"id":3},"case":{"spacing":1}}""");
            var iso = new IsosurfaceComponent(); iso.Params.Input[0].Access = GH_ParamAccess.list;
            GH_TestParam Source(string nick, bool owned, bool data) { var p = new GH_TestParam("Frame", "F", "", GH_ParamAccess.item, "Generic", null); if (owned) p.Owner = new GhNamed(nick); else p.NickName = nick; if (data) p.VolatileData.Items.Add(f1); return p; }
            foreach (var s in new[] { Source("Parent", true, true), Source("Child A", true, false), Source("Child B", true, false), Source("loose", false, false) }) iso.Params.Input[0].Sources.Add(s);
            var da = Solve(iso, new List<object?> { f1, new GH_ObjectWrapper(Goo(f1.Value)), f3, null }, D);
            var warnings = iso.RuntimeMessages.Where(m => m.Level == GH_RuntimeMessageLevel.Warning).Select(m => m.Text).ToArray();
            assert(warnings.SequenceEqual(new[] { "3 of 4 wired inputs delivered no frame (cancelled, failed or still running upstream): Child A, Child B, loose", "1 duplicate frame is used once" }), "Composed-view warnings wrong: " + string.Join(" | ", warnings));
            assert(Json(da.Out<JsonObject>(0)["frames"]) == """[{"id":1},{"id":1},{"id":3}]""" && iso.Errors.Count == 0, "Composed frames changed");
            var plane = new PlaneFieldComponent(); foreach (var s in new[] { Source("Child A", true, false), Source("Child B", true, false) }) plane.Params.Input[0].Sources.Add(s);
            da = Solve(plane, new List<object?>(), D);
            assert(plane.Message == "waiting for frames" && da.Outputs.Count == 0 && plane.RuntimeMessages.SequenceEqual(new[] { (GH_RuntimeMessageLevel.Warning, "2 of 2 wired inputs delivered no frame (cancelled, failed or still running upstream): Child A, Child B") }), "Children unnamed when none delivered a frame");
            var probe = new ProbeComponent(); probe.Params.Input[0].Sources.Add(Source("Child A", true, false)); Solve(probe, new object?[] { null });
            assert(probe.RuntimeMessages.Count == 0, "A non-composing component reported empty sources");
            iso.Params.Input[0].Sources.Clear(); Solve(iso, new List<object?> { f1, f3 }, D);
            assert(iso.RuntimeMessages.Count == 0, "Complete, distinct frames warned");
            foreach (var view in new HawaComponent[] { new PlaneFieldComponent(), new FlowDisplayComponent(), new SurfaceFieldComponent() }) {
                view.Params.Input[0].Access = GH_ParamAccess.list; view.Params.Input[0].Sources.Add(Source("Cancelled", true, false)); Solve(view, new List<object?> { f1, f1 }, D);
                assert(view.RuntimeMessages.Count(m => m.Level == GH_RuntimeMessageLevel.Warning) == 2, view.GetType().Name + " not reported");
            }
            var query = new BoundaryCaptureComponent(); query.Params.Input[0].Sources.Add(Source("Cancelled", true, false)); Solve(query, f1, f1, f1, f1);
            assert(!query.RuntimeMessages.Any(m => m.Level == GH_RuntimeMessageLevel.Warning), "A non-composing view reported frame sources");
        });

        test("field tools validate frames and map requests, colours and meshes", () => {
            var probe = new ProbeComponent(); JsonObject Frames(params object?[] items) => FieldTools.Frames(new GhAccess(probe, items.ToList()), 0);
            var frame = Goo("""{"frame":{"id":1},"case":{"origin":[1,2,3],"spacing":2,"shape":[2,2,2]}}""");
            assert(Catch(() => Frames(new GH_String("x"))) is ArgumentException { Message: "Connect Field Snapshot or Playback frames" }, "Non-frame accepted");
            assert(Catch(() => Frames(Goo("""{"case":{}}"""))) is ArgumentException { Message: "Connect immutable field frames" } && Catch(() => Frames(Goo("""{"frame":{}}"""))) is ArgumentException, "Frame without identity accepted");
            assert(Catch(() => Frames(null, null)) is ArgumentException { Message: "Use 1..16 field frames" } && Catch(() => Frames(Enumerable.Repeat<object?>(frame, 17).ToArray())) is ArgumentException { Message: "Use 1..16 field frames" }, "Frame count limits not enforced");
            var single = Frames(frame); assert(Json(single) == frame.Value && single["frames"] == null, "Single frame changed");
            assert(Frames(Enumerable.Repeat<object?>(frame, 16).ToArray())["frames"]!.AsArray().Count == 16, "Sixteen frames rejected");
            var plane = FieldTools.Request(single, "plane"); var trace = FieldTools.Request(single, "trace", "q");
            assert(Json(plane) == """{"op":"field","action":"plane","frame":{"id":1},"frames":[{"id":1}],"field":"speed"}""" && Json(trace) == """{"op":"field","action":"trace","frame":{"id":1},"frames":null,"field":"q"}""", "Request shape changed");
            var flat = (JsonObject)JsonNode.Parse("""{"frame":{"id":2},"case":{"shape":[4,4]}}""")!; var composed = (JsonObject)JsonNode.Parse("""{"frame":{"id":2},"frames":[{"id":2},{"id":5}],"case":{}}""")!;
            assert(Json(FieldTools.Request(flat, "plane")["frames"]) == "null" && Json(FieldTools.Request(composed, "plane")["frames"]) == """[{"id":2},{"id":5}]""", "2D or composed frames misrouted");
            var world = FieldTools.World(single); world["case"]!["spacing"] = 9; assert(single["case"]!["spacing"]!.GetValue<int>() == 2 && world.Count == 1, "World aliases the frame");
            int Argb(int r, int g, int b) => Color.FromArgb(r, g, b).ToArgb();
            assert(FieldTools.ColorAt(0, "blue-green").ToArgb() == Argb(8, 48, 107) && FieldTools.ColorAt(.25, "blue-green").ToArgb() == Argb(4, 104, 143) && FieldTools.ColorAt(.5, "x").ToArgb() == Argb(0, 160, 180)
                && FieldTools.ColorAt(1, "blue-green").ToArgb() == Argb(150, 235, 140) && FieldTools.ColorAt(-3, "blue-green").ToArgb() == Argb(8, 48, 107) && FieldTools.ColorAt(7, "blue-green").ToArgb() == Argb(150, 235, 140), "Default palette wrong");
            assert(FieldTools.ColorAt(0, "SPECTRUM").ToArgb() == Argb(0, 0, 139) && FieldTools.ColorAt(1, "spectrum").ToArgb() == Argb(255, 0, 0) && FieldTools.ColorAt(.5, "diverging").ToArgb() == Argb(255, 255, 255), "Named palette wrong");
            var mesh = FieldTools.Mesh((JsonObject)JsonNode.Parse("""{"vertices":[[0,0,0],[1,0,0],[0,1,0]],"faces":[[0,1,2]]}""")!, single);
            assert(mesh.Vertices.SequenceEqual(new[] { new Point3d(1, 2, 3), new Point3d(3, 2, 3), new Point3d(1, 4, 3) }) && mesh.Faces.Single() == new MeshFace(0, 1, 2) && mesh.Normals.Calls == 1, "Mesh not mapped to world");
        });

        test("coordinates map grid, world and velocity through a rotated basis", () => {
            var s = (JsonObject)JsonNode.Parse("""{"case":{"origin":[1,2,3],"spacing":0.5,"basis":[[0,1,0],[-1,0,0],[0,0,1]]}}""")!;
            assert(Coordinates.World(s, JsonNode.Parse("[2,4,6]")!) == new Point3d(-1, 3, 6) && Json(Coordinates.Grid(s, new Point3d(-1, 3, 6))) == "[2,4,6]" && Coordinates.Velocity(s, JsonNode.Parse("[1,2,3]")!) == new Vector3d(-2, 1, 3), "Rotated frame mapping wrong");
            var plain = (JsonObject)JsonNode.Parse("""{"case":{}}""")!;
            assert(Coordinates.Origin(plain).SequenceEqual(new double[3]) && Coordinates.Spacing(plain) == 1 && Coordinates.Axis(plain, 0) == Vector3d.XAxis && Coordinates.Axis(plain, 1) == Vector3d.YAxis && Coordinates.Axis(plain, 2) == Vector3d.ZAxis, "Defaults wrong");
            assert(Coordinates.World(plain, JsonNode.Parse("[1,2,3]")!) == new Point3d(1, 2, 3), "Identity frame moved points");
        });

        test("result components request, map and filter lattice samples", () => {
            Reset(); using var bridge = new GhBridge(); JsonObject? reply = null;
            bridge.Respond = r => r["op"]!.GetValue<string>() switch { "evaluate_submit" => new() { ["job"] = "q" + bridge.Ops("evaluate_submit").Count() }, "evaluate_poll" => reply == null ? new() { ["state"] = "running" } : new() { ["state"] = "completed", ["result"] = reply.DeepClone() }, _ => null };
            JsonObject Request() => bridge.Ops("evaluate_submit").Last()["request"]!.AsObject();
            var slice = new SliceComponent { Document = doc }; var lattice = Goo("""{"session":"s1","revision":4,"case":{"origin":[10,0,0],"spacing":2,"shape":[2,2,1]}}""");
            var pending = Solve(slice, lattice, D, 0, D, D);
            assert(slice.Message == "running" && pending.Outputs.Count == 0 && Json(Request()) == """{"op":"slice","session":"s1","axis":2,"index":0,"field":"speed","mean":false,"revision":4}""", "Pending slice published or request wrong");
            reply = (JsonObject)JsonNode.Parse("""{"shape":[2,2],"values":[1,2,3,9],"valid":[true,true,true,false],"coordinates":[[0,0,0],[0,1,0],[1,0,0],[1,1,0]]}""")!;
            var da = Solve(slice, lattice, 1, -1, "pressure", true); var mesh = da.Out<Mesh>(0);
            assert(Json(Request()) == """{"op":"slice","session":"s1","axis":1,"field":"pressure","mean":true,"revision":4}""" && slice.Message == "lattice display", "Centre slice request or label wrong");
            assert(slice.RuntimeMessages.SequenceEqual(new[] { (GH_RuntimeMessageLevel.Remark, "Black = not simulated (solid or no-data nodes). Walls: voxel, halfway between nodes; cell 2 model units. Colours within about one cell of a surface depend on the wall mode and this resolution, so treat near-wall flow as approximate.") }), "Slice key or voxel near-wall caveat missing (#29)");
            assert(da.List(1).SequenceEqual(new object?[] { 1d, 2d, 3d, 9d }) && da.List(2).SequenceEqual(new object?[] { 1d, 3d }) && da.List(3).SequenceEqual(new object?[] { true, true, true, false }), "Slice values, range or validity wrong");
            assert(mesh.Vertices.Contains(new Point3d(10, 0, 0)) && mesh.Vertices.Contains(new Point3d(12, 2, 0)) && mesh.VertexColors.Any(c => c.ToArgb() == Color.Black.ToArgb()) && mesh.VertexColors.Any(c => c.ToArgb() == Color.FromArgb(8, 48, 107).ToArgb()) && mesh.Normals.Calls >= 1, "Slice mesh not in world space or not coloured");
            var walled = Goo("""{"session":"s1","case":{"spacing":1,"dx":0.025,"shape":[2,2,1],"wall_links":[[1,0,0.5]]}}""");
            da = Solve(slice, walled, D, D, D, D); assert(da.List(2).SequenceEqual(new object?[] { 0d, 3d }) && slice.Message == "wall-clipped display", "Wall-clipped speed range must start at zero wall speed");
            assert(slice.RuntimeMessages.Single().Text.StartsWith("Black = not simulated (solid or no-data nodes). Walls: interpolated at link crossings; cell 0.025 m. "), "Interpolated wall mode or physical cell size not named (#29)");
            Solve(slice, Goo("""{"session":"s1","case":{"spacing":1,"dx":0.5,"shape":[2,2,1],"wall_links":[]}}"""), D, D, D, D);
            assert(slice.Message == "lattice display" && slice.RuntimeMessages.Single().Text.Contains("Walls: voxel, halfway between nodes; cell 0.5 m."), "An empty link list was labelled as interpolated walls");
            assert(slice.Params.Output[0] is GH_TestParam { Description: var key } && key.Contains("Black = not simulated") && key.Contains("Near-wall colours depend on the wall mode and resolution"), "Mesh output lost the colour key");
            reply["valid"] = new JsonArray(false, false, false, false); da = Solve(slice, walled, D, D, "density", D);
            assert(da.List(2).SequenceEqual(new object?[] { 0d, 0d }) && da.Out<Mesh>(0).VertexColors.All(c => c.ToArgb() == Color.Black.ToArgb()), "All-solid slice not black");

            var sample = new SampleComponent(); reply = (JsonObject)JsonNode.Parse("""{"values":[null,{"velocity":[1,0,0],"pressure":5}]}""")!;
            da = Solve(sample, Goo("""{"session":"s2","case":{"origin":[1,0,0],"spacing":0.5}}"""), new List<Point3d> { new(1, 0, 0), new(2, 1, 0) }, true);
            assert(Json(Request()) == """{"op":"sample","session":"s2","points":[[0,0,0],[2,2,0]],"mean":true,"revision":null}""", "Sample request wrong");
            assert(da.List(0).SequenceEqual(new object?[] { Vector3d.Unset, new Vector3d(1, 0, 0) }) && double.IsNaN((double)da.List(1)[0]!) && (double)da.List(1)[1]! == 5 && da.List(2).SequenceEqual(new object?[] { false, true }), "Invalid sample not kept as unset/NaN/false");
            reply = null; assert(Solve(sample, Goo("""{"session":"s3","case":{}}"""), new List<Point3d>(), D).Outputs.Count == 0, "Pending sample published");

            var stream = new StreamlinesComponent(); reply = (JsonObject)JsonNode.Parse("""{"paths":[[[0,0,0],[1,0,0]],[[5,5,5]]]}""")!;
            da = Solve(stream, Goo("""{"session":"s4","case":{"spacing":2}}"""), new List<Point3d> { new(2, 4, 6) }, 30);
            assert(Json(Request()) == """{"op":"streamlines","session":"s4","seeds":[[1,2,3]],"steps":30,"revision":null}""", "Streamline request wrong");
            assert(da.List(0).Cast<PolylineCurve>().Single().Points.SequenceEqual(new[] { new Point3d(0, 0, 0), new Point3d(2, 0, 0) }), "Short path drawn or path not mapped");
            reply = null; assert(Solve(stream, Goo("""{"session":"s5","case":{}}"""), new List<Point3d>(), D).Outputs.Count == 0, "Pending streamlines published");

            var vectors = new VectorsComponent(); da = Solve(vectors, new List<Point3d> { new(0, 0, 0), new(1, 0, 0) }, new List<Vector3d> { new(1, 0, 0), Vector3d.Unset }, 2.0);
            assert(da.List(0).SequenceEqual(new object?[] { new Line(new(0, 0, 0), new(2, 0, 0)), null }), "Vectors not index-aligned with Points (#81)");
            da = Solve(vectors, new List<Point3d> { new(0, 0, 0), new(1, 0, 0), new(0, 1, 0) }, new List<Vector3d> { Vector3d.Unset, new(0, 0, 1), new(double.NaN, 0, 0) }, D);
            assert(da.List(0).SequenceEqual(new object?[] { null, new Line(new(1, 0, 0), new(1, 0, 1)), null }), "Leading or non-finite sample shifted the remaining lines (#81)");
            Solve(vectors, new List<Point3d> { new(0, 0, 0) }, new List<Vector3d> { new(1, 0, 0), new(0, 1, 0) }, D); assert(vectors.Errors.Single() == "Point and velocity counts differ", "Count mismatch accepted");
            assert(slice.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077111") && sample.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077112") && vectors.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077113") && stream.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077114"), "Component GUID changed; saved definitions would break");
            assert(Names(slice) == "Solution,Axis,Index,Field,Mean|Mesh,Values,Range,Valid" && Names(sample) == "Solution,Points,Mean|Velocity,Pressure,Valid" && Names(vectors) == "Points,Velocity,Scale|Lines" && Names(stream) == "Solution,Seeds,Steps|Streamlines", "Parameter layout changed");
            Reset();
        });

        test("Solve labels queued and preparing jobs and drives the session lifecycle (#74)", () => {
            Reset(); using var bridge = new GhBridge(); string phase = "queued"; var status = new JsonObject();
            JsonObject Status(string state, JsonNode? error = null) => new() { ["state"] = state, ["steps"] = 5, ["target"] = 50, ["backend"] = new JsonObject { ["selected"] = "cpu" }, ["resolution"] = new JsonArray(4, 3, 2), ["physical_time"] = .25, ["relative_mass_change"] = .001, ["quality"] = new JsonObject { ["status"] = "ok" }, ["averaging_samples"] = 0, ["error"] = error };
            bridge.Respond = r => r["op"]!.GetValue<string>() switch {
                "evaluate_submit" => new() { ["job"] = "c" + bridge.Ops("evaluate_submit").Count() },
                "evaluate_poll" => new() { ["state"] = phase, ["error"] = "no device", ["result"] = new JsonObject { ["status"] = new JsonObject { ["session"] = "s" + bridge.Ops("evaluate_submit").Count() } } },
                "status" => (JsonObject)status.DeepClone(), "start" or "reset_async" or "pause_async" => new(), _ => null };
            int Count(string op) => bridge.Ops(op).Count();
            var solve = new SolveComponent { Document = doc }; var spec = Goo("""{"cell":1}""");
            var da = Solve(solve, spec, "cpu", 50, false, false);
            assert(solve.Message == "queued: waiting for the device" && da.Out<string>(1) == solve.Message && Json(bridge.Ops("evaluate_submit").Single()) == """{"op":"evaluate_submit","kind":"create","case":{"cell":1},"device":"cpu"}""" && HawaPollScheduler.PendingCount == 1, "Queued creation not labelled or not polled");
            Pulse(); assert(HawaPollScheduler.PendingCount == 1, "Current creation poll dropped");
            phase = "running"; Solve(solve, spec, "cpu", 50, false, false); assert(solve.Message == "preparing" && Count("evaluate_submit") == 1, "Started creation not shown as preparing");
            phase = "completed"; status = Status("ready"); da = Solve(solve, spec, "cpu", 50, false, false);
            var solution = da.Out<HawaGoo>(0).Data;
            assert(solve.Message == "ready / ok" && da.Out<string>(1) == "ready" && da.Out<int>(2) == 5 && solution["label"]!.GetValue<string>() == "Hawa ready: 5 steps" && solution["session"]!.GetValue<string>() == "s1" && solution["revision"]!.GetValue<int>() == 5, "Ready session outputs wrong");
            assert(da.Out<string>(3).StartsWith("Backend: CPU\nGrid: 4 × 3 × 2\nIterations: 5 / 50\nState: ready\nSimulation time: 0.25\nRelative mass change: 0.001") && Count("start") == 0, "Monitor text wrong or started without a rising edge");
            status = Status("running"); HawaPollScheduler.Cancel(solve); Solve(solve, spec, "cpu", 50, true, false);
            assert(Json(bridge.Ops("start").Single()) == """{"op":"start","session":"s1","steps":50}""" && solve.Message == "running / ok" && HawaPollScheduler.PendingCount == 1, "Run rising edge did not start or poll");
            Pulse(); Solve(solve, spec, "cpu", 50, true, true); assert(Count("reset_async") == 1 && Count("start") == 1, "Reset edge or repeated start wrong");
            status = Status("paused", "diverged"); Solve(solve, spec, "cpu", 50, false, true);
            assert(Count("pause_async") == 1 && solve.Errors.SequenceEqual(new[] { "diverged" }) && Count("reset_async") == 1, "Pause edge or status error lost");
            status = Status("running"); Solve(solve, spec, "cpu", 50, true, false); assert(Count("start") == 2, "Second run edge ignored");
            Solve(solve, Goo("""{"cell":2}"""), "cpu", 50, true, false);
            assert(bridge.Ops("close_async").Single()["session"]!.GetValue<string>() == "s1" && bridge.Ops("evaluate_control").Single()["job"]!.GetValue<string>() == "c1" && Count("start") == 3 && bridge.Ops("start").Last()["session"]!.GetValue<string>() == "s2", "Changed case did not restart cleanly");
            phase = "failed"; Solve(solve, spec, "cpu", 50, true, false); assert(solve.Message == "failed" && solve.Errors.Single() == "no device", "Failed creation not reported");
            phase = "completed"; Solve(solve, spec, "cpu", 50, true, false); Solve(solve, new object?[] { null });
            assert(solve.Message == LifecycleText.WaitingForInput && bridge.Ops("close_async").Count() >= 2, "Missing case kept the session");
            Solve(solve, spec, "cpu", 50, false, false); solve.RemovedFromDocument(doc); assert(solve.BaseRemovals == 1 && HawaPollScheduler.PendingCount == 0, "Removal leaked");
            int starts = Count("start"); var saved = new SolveComponent(); Solve(saved, spec, "cpu", 50, true, false); assert(Count("start") == starts && saved.Message == "running / ok", "Saved Run true started on open");
            assert(solve.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077109") && Names(solve) == "Case,Device,Target steps,Run,Reset|Solution,State,Steps,Monitor", "Solve layout changed");
            Reset();
        });

        test("runtime, check and checkpoint components keep their contracts", () => {
            Reset(); using var bridge = new GhBridge(); string state = "running";
            bridge.Respond = r => r["op"]!.GetValue<string>() switch { "info" => new() { ["python"] = "3.9" }, "evaluate_submit" => new() { ["job"] = "k" + bridge.Ops("evaluate_submit").Count() }, "evaluate_poll" => new() { ["state"] = state, ["result"] = new JsonObject { ["saved"] = true } }, _ => null };
            var runtime = new RuntimeComponent(); var da = Solve(runtime, D);
            assert(da.Out<string>(0) == "Set Initialize true to prepare Hawa's embedded runtime" && da.Out<string>(1).StartsWith("Lettuce: Copyright (c) 2019 Andreas Kraemer, MIT") && !bridge.Ops("info").Any(), "Runtime initialized without request");
            assert(Solve(runtime, true).Out<string>(0) == """{"python":"3.9"}""" && Solve(runtime, new object?[] { null }).Outputs.Count == 0, "Runtime report wrong");
            var check = new CheckComponent { Document = doc }; assert(Solve(check, Goo("{}")).Outputs.Count == 0 && check.Message == "running", "Pending check published");
            var point = new CheckpointComponent { Document = doc }; var solution = Goo("""{"session":"s1"}""");
            Solve(point, solution, "out.npz", "bogus", true); assert(point.Errors.Single() == "Use save, load or export", "Unknown operation accepted");
            Solve(point, solution, "out.npz", "save", true); Solve(point, solution, "out.npz", "save", true); assert(bridge.Ops("evaluate_submit").Count() == 1, "Saved Execute true ran on open");
            Solve(point, solution, "out.npz", "save", false); da = Solve(point, solution, "out.npz", "export", true);
            var request = bridge.Ops("evaluate_submit").Last()["request"]!.AsObject();
            assert(request["op"]!.GetValue<string>() == "export" && request["session"]!.GetValue<string>() == "s1" && request["path"]!.GetValue<string>() == "/work/defs/out.npz" && Guid.TryParse(request["request_id"]!.GetValue<string>(), out _) && da.Outputs.Count == 0, "Checkpoint request wrong");
            state = "completed"; da = Solve(point, solution, "out.npz", "export", true); assert(da.Out<string>(0) == """{"saved":true}""" && bridge.Ops("evaluate_submit").Count() == 2, "Checkpoint result missing or repeated");
            Solve(point, new object?[] { null }); assert(bridge.Ops("evaluate_control").Any(r => r["job"]!.GetValue<string>() == "k2"), "Checkpoint job leaked");
            assert(runtime.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077107") && check.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077108") && point.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077110"), "GUID changed");
            assert(Names(runtime) == "Initialize|Runtime,Credits" && Names(check) == "Case|Valid,Report" && Names(point) == "Solution,Path,Operation,Execute|Report", "Layout changed");
            Reset();
        });

        test("Record reports restarts, document switches and failures plainly (#74)", () => {
            Reset(); using var bridge = new GhBridge(); string state = "running";
            bridge.Respond = r => r["op"]!.GetValue<string>() switch {
                "evaluate_submit" => new() { ["job"] = "r" + bridge.Ops("evaluate_submit").Count() }, "evaluate_control" when r["action"]!.GetValue<string>() != "close" => new(),
                "evaluate_poll" => new() { ["state"] = state, ["steps"] = 3, ["target"] = 10, ["error"] = "disk full", ["result"] = new JsonObject { ["manifest"] = "/tmp/rec2/manifest.json", ["status"] = new JsonObject { ["session"] = "rs" } } }, _ => null };
            int Submits() => bridge.Ops("evaluate_submit").Count();
            var record = new RecordComponent { Document = doc }; var spec = Goo("""{"cell":1}""");
            object?[] Inputs(object? c, string dir, bool run, bool pause = false) => new[] { c, dir, 10, 2, "cpu", run, pause };
            Solve(record, Inputs(spec, "/tmp/rec1", true)); assert(record.Message == "enable again" && Submits() == 0 && record.RuntimeMessages.Count == 0, "Saved Run true recorded on open");
            Solve(record, Inputs(spec, "/tmp/rec1", false)); assert(record.Message == "stopped", "Run false not stopped");
            Solve(record, Inputs(null, "/tmp/rec1", true)); assert(record.Message == "waiting for case" && Submits() == 0, "Recorded without a case");
            Solve(record, Inputs(spec, "rec", true)); assert(record.Message == "failed" && record.Errors.Single() == "Choose an absolute path for a new recording directory", "Relative directory accepted");
            var da = Solve(record, Inputs(spec, "/tmp/rec1", true));
            assert(Json(bridge.Ops("evaluate_submit").Single()) == """{"op":"evaluate_submit","kind":"record","case":{"cell":1},"directory":"/tmp/rec1","device":"cpu","steps":10,"interval":2}""" && record.Message == "running" && da.Out<string>(1) == "running: 3/10" && record.RuntimeMessages.Count == 0 && HawaPollScheduler.PendingCount == 1, "First recording wrong");
            Pulse(); Solve(record, Inputs(spec, "/tmp/rec1", true, true));
            assert(bridge.Ops("evaluate_control").Select(r => r["action"]!.GetValue<string>()).SequenceEqual(new[] { "resume", "pause" }) && Submits() == 1, "Pause not forwarded or unchanged inputs restarted");
            da = Solve(record, Inputs(spec, "/tmp/rec2", true));
            assert(Submits() == 2 && bridge.Ops("evaluate_control").Any(r => r["action"]!.GetValue<string>() == "close" && r["job"]!.GetValue<string>() == "r1") && record.Message == "running (restarted: directory changed)" && da.Out<string>(1) == "running (restarted: directory changed): 3/10"
                && Has(record, GH_RuntimeMessageLevel.Remark, "A changed input started a new recording; the previous one stays in its own directory."), "Restart was silent");
            state = "completed"; da = Solve(record, Inputs(spec, "/tmp/rec2", true));
            assert(da.Out<string>(0) == "/tmp/rec2/manifest.json" && Json(da.Out<HawaGoo>(2).Data) == """{"kind":"Solution","session":"rs","case":{"cell":1}}""" && record.Message == "completed (restarted: directory changed)", "Completed recording outputs wrong");
            state = "failed"; Solve(record, Inputs(spec, "/tmp/rec2", true)); assert(record.Message == "failed" && record.Errors.Single() == "disk full", "Recording failure hidden");
            state = "running"; Solve(record, Inputs(spec, "/tmp/rec2", true)); assert(record.Message == "running" && record.RuntimeMessages.Count == 0, "Failure restart reported as an input change");
            record.DocumentContextChanged(doc, GH_DocumentContext.Unloaded);
            assert(record.Message == LifecycleText.DocumentInactive && HawaPollScheduler.PendingCount == 0 && bridge.Ops("evaluate_control").Last()["action"]!.GetValue<string>() == "close", "Document switch kept the recording label or job");
            int before = Submits(); Solve(record, Inputs(spec, "/tmp/rec2", true));
            assert(record.Message == LifecycleText.DocumentInactive && Has(record, GH_RuntimeMessageLevel.Remark, LifecycleText.DocumentInactiveReason + " Set Run false, then true, to record again.") && Submits() == before, "Inactive recording restarted or gave no reason");
            Solve(record, Inputs(spec, "/tmp/rec2", false)); Solve(record, Inputs(spec, "/tmp/rec2", true)); assert(Submits() == before + 1 && record.Message == "running", "Toggle did not resume recording");
            record.DocumentContextChanged(doc, GH_DocumentContext.Lock); Solve(record, Inputs(spec, "/tmp/rec2", true)); assert(record.Message == "enable again" && record.RuntimeMessages.Count == 0, "Locked document gave a document-switch reason");
            record.DocumentContextChanged(doc, GH_DocumentContext.Unloaded); Solve(record, Inputs(spec, "/tmp/rec2", true)); assert(record.Message == "enable again" && record.RuntimeMessages.Count == 0, "Idle recording claimed a cancellation reason");
            Solve(record, Inputs(spec, "/tmp/rec2", false)); Solve(record, Inputs(spec, "/tmp/rec2", true)); int closes = bridge.Ops("evaluate_control").Count(r => r["action"]!.GetValue<string>() == "close");
            record.RemovedFromDocument(doc); assert(bridge.Ops("evaluate_control").Count(r => r["action"]!.GetValue<string>() == "close") == closes + 1 && record.BaseRemovals == 1, "Removal leaked the recording");
            assert(record.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077131") && Names(record) == "Case,Directory,Steps,Interval,Device,Run,Pause|Manifest,State,Solution" && record.Params.Input[0].Optional, "Record layout changed");
            Reset();
        });

        test("playback resolves recordings; removed Particles opens old definitions with an error", () => {
            Reset(); using var bridge = new GhBridge(); JsonObject? reply = null;
            bridge.Respond = r => r["op"]!.GetValue<string>() switch { "evaluate_submit" => new() { ["job"] = "p" + bridge.Ops("evaluate_submit").Count() }, "evaluate_poll" => reply == null ? new() { ["state"] = "running" } : new() { ["state"] = "completed", ["result"] = reply.DeepClone() }, _ => null };
            JsonObject Request() => bridge.Ops("evaluate_submit").Last()["request"]!.AsObject();
            var playback = new PlaybackComponent { Document = doc };
            assert(Solve(playback, "rec/manifest.json", 2).Outputs.Count == 0 && Json(Request()) == """{"op":"recording","action":"load","manifest":"/work/defs/rec/manifest.json","index":2}""", "Pending playback published or path wrong");
            reply = (JsonObject)JsonNode.Parse("""{"time":1.5,"frame":{"id":2},"case":{}}""")!; var da = Solve(playback, "/abs/manifest.json", 2);
            assert(Json(da.Out<HawaGoo>(0).Data) == """{"time":1.5,"frame":{"id":2},"case":{},"kind":"Frame"}""" && da.Out<double>(1) == 1.5, "Playback frame wrong");
            int submits = bridge.Ops("evaluate_submit").Count();
            var particles = new ParticlesComponent { Document = doc };
            var gone = Solve(particles);
            assert(ParticlesComponent.Removed == "Hawa Particles was removed. Use Flow Display on a Playback frame, or Streamlines on a live Solution.", "Removal message must point playback frames at Flow Display; Streamlines needs a live session");
            assert(gone.Outputs.Count == 0 && particles.Errors.SequenceEqual(new[] { ParticlesComponent.Removed }) && bridge.Ops("evaluate_submit").Count() == submits, "Removed Particles must only report its removal");
            particles.RuntimeMessages.Clear(); Solve(particles, "/abs/manifest.json", Goo("""{"case":{}}"""), new List<Point3d> { new(3, 2, 0) }, 3);
            assert(particles.Errors.SequenceEqual(new[] { ParticlesComponent.Removed }) && bridge.Ops("evaluate_submit").Count() == submits, "Wired old Particles must report its removal without a request");
            assert(playback.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077132") && particles.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077133") && Names(playback) == "Manifest,Index|Frame,Time" && Names(particles) == "Manifest,Frame,Seeds,Last frame|Trails,Particles", "Recording layouts changed; Particles must keep its archive GUID and parameter names");
            assert(particles.Exposure == GH_Exposure.hidden && playback.Exposure == GH_Exposure.primary && particles.Params.Input.All(p => p.Optional), "Removed Particles must stay hidden and accept an unwired archive");
            Reset();
        });

        test("lifecycle text names queued, restarted, missing and duplicate states", () => {
            assert(LifecycleText.Pending("queued") == "queued: waiting for the device" && LifecycleText.Pending("running") == "preparing" && LifecycleText.Pending("paused") == "preparing", "Queued job looks like preparation");
            var before = (JsonObject)JsonNode.Parse("""{"op":"evaluate_submit","directory":"/a","steps":200,"case":{"size":8}}""")!;
            assert(LifecycleText.Restart(before, before.DeepClone().AsObject()) == null, "Unchanged inputs called a restart");
            var after = before.DeepClone().AsObject(); after["directory"] = "/b"; after["case"]!["size"] = 9;
            var added = before.DeepClone().AsObject(); added["device"] = "cpu"; var removed = before.DeepClone().AsObject(); removed.Remove("steps");
            assert(LifecycleText.Restart(before, after) == "restarted: directory, case changed" && LifecycleText.Restart(before, added) == "restarted: device changed" && LifecycleText.Restart(before, removed) == "restarted: steps changed", "Restart reason lost or misnamed");
            assert(LifecycleText.Missing(new List<(string, bool)> { ("Parent", false), ("Child", false) }) == null && LifecycleText.Missing(new List<(string, bool)>()) == null, "Complete inputs reported missing");
            assert(LifecycleText.Duplicates(new[] { "a", "b" }) == null && LifecycleText.Duplicates(new[] { "a", "a", "a", "b", "b" }) == "3 duplicate frames are used once", "Duplicates not counted");
        });

        test("plane field draws fluid in colour and solid, invalid and no-data pieces in black (#81)", () => {
            Reset(); using var bridge = new GhBridge(); JsonObject? reply = null;
            bridge.Respond = r => r["op"]!.GetValue<string>() switch { "evaluate_submit" => new() { ["job"] = "f" + bridge.Ops("evaluate_submit").Count() }, "evaluate_poll" => reply == null ? new() { ["state"] = "running" } : new() { ["state"] = "completed", ["result"] = reply.DeepClone() }, _ => null };
            var plane = new PlaneFieldComponent { Document = doc }; var frame = Goo("""{"frame":{"id":1},"case":{"origin":[10,0,0],"spacing":2}}""");
            var map = Goo("""{"kind":"ColorMap","palette":"blue-green","min":0,"max":2,"units":"m/s"}"""); var rect = new Rectangle3d(new(10, 0, 0), new(2, 0, 0), new(0, 2, 0));
            assert(Solve(plane, new List<object?> { frame }, rect, 2, D, map, new List<double> { .5 }).Outputs.Count == 0 && plane.Message == "running", "Pending plane published");
            assert(Json(bridge.Ops("evaluate_submit").Single()["request"]) == """{"op":"field","action":"plane","frame":{"id":1},"frames":null,"field":"speed","points":[[0,0,0],[0,1,0],[1,0,0],[1,1,0]],"shape":[2,2],"levels":[0.5]}""", "Plane request wrong");
            reply = (JsonObject)JsonNode.Parse("""{"values":[0,1,2,3],"valid":[true,true,true,false],"mesh_vertices":[[0,0,0],[1,0,0],[1,1,0],[0,1,0],[2,0,0]],"mesh_values":[0,2,1,0,0],"mesh_faces":[[0,1,2]],"solid_faces":[[0,2,3]],"invalid_faces":[[3,4,0]],"no_data_faces":[[1,4,2]],"lines":[[[0,0,0],[1,0,0]]],"collection":{"domains":1}}""")!;
            var da = Solve(plane, new List<object?> { frame }, rect, 2, D, map, new List<double> { .5 }); var mesh = da.Out<Mesh>(0);
            Point3d W(double x, double y) => new(10 + 2 * x, 2 * y, 0);
            assert(mesh.Vertices.SequenceEqual(new[] { W(0, 0), W(1, 0), W(1, 1), W(0, 1), W(2, 0), W(0, 0), W(1, 1), W(0, 1), W(2, 0), W(1, 0) }), "Black pieces must use their own vertex copies in world space");
            assert(mesh.Faces.SequenceEqual(new[] { new MeshFace(0, 1, 2), new MeshFace(5, 6, 7), new MeshFace(7, 8, 5), new MeshFace(9, 8, 6) }), "A solid, invalid or no-data piece was dropped or not remapped");
            int[] Argb(params Color[] c) => c.Select(x => x.ToArgb()).ToArray();
            assert(mesh.VertexColors.Select(c => c.ToArgb()).SequenceEqual(Argb(Color.FromArgb(8, 48, 107), Color.FromArgb(150, 235, 140), Color.FromArgb(0, 160, 180), Color.FromArgb(8, 48, 107), Color.FromArgb(8, 48, 107), Color.Black, Color.Black, Color.Black, Color.Black, Color.Black)), "Fluid colours or the not-simulated black wrong");
            assert(da.List(2).SequenceEqual(new object?[] { 0d, 1d, 2d, 3d }) && da.List(1).SequenceEqual(new object?[] { new Line(W(0, 0), W(1, 0)) }) && plane.Message == "domains: 1" && mesh.Normals.Calls == 1, "Plane values, contours or label wrong");
            Solve(plane, new List<object?> { frame }, rect, 1, D, map, D); assert(plane.Errors.Single() == "Resolution 2..100", "Resolution 1 accepted");
            assert(plane.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077123") && Names(plane) == "Frames,Rectangle,Resolution,Field,Colors,Contour levels|Mesh,Contours,Values" && plane.Params.Input[5].Optional && ((GH_TestParam)plane.Params.Output[0]).Description.Contains("Black = not simulated"), "Plane layout changed");
            Reset();
        });

        test("flow display skips undrawable seeds and blacks unsimulated colour samples (#82)", () => {
            Reset(); using var bridge = new GhBridge(); JsonObject? reply = null;
            bridge.Respond = r => r["op"]!.GetValue<string>() switch { "evaluate_submit" => new() { ["job"] = "t" + bridge.Ops("evaluate_submit").Count() }, "evaluate_poll" => reply == null ? new() { ["state"] = "running" } : new() { ["state"] = "completed", ["result"] = reply.DeepClone() }, _ => null };
            var flow = new FlowDisplayComponent { Document = doc }; var frame = Goo("""{"frame":{"id":1},"case":{"spacing":1}}"""); var map = Goo("""{"palette":"blue-green","min":0,"max":2}""");
            var seeds = new List<Point3d> { new(5, 5, 5), new(1, 1, 1), new(0, 0, 0), new(0, 2, 0) };
            assert(Solve(flow, new List<object?> { frame }, seeds, map, D, D, D, D).Outputs.Count == 0, "Pending trace published");
            assert(Json(bridge.Ops("evaluate_submit").Single()["request"]) == """{"op":"field","action":"trace","frame":{"id":1},"frames":null,"field":"speed","seeds":[[5,5,5],[1,1,1],[0,0,0],[0,2,0]],"steps":150,"direction":1}""", "Trace request wrong");
            // Skipped seeds come first so a colour shifted onto the wrong seed shows on the later paths.
            reply = (JsonObject)JsonNode.Parse("""{"paths":[[],[[1,1,1]],[[0,0,0],[1,0,0],[2,0,0]],[[0,2,0],[0,3,0]]],"values":[[],[0],[0,1,0],[2,2]],"valid":[[],[true],[true,true,false],[true,true]],"reasons":["invalid_seed","stalled","completed","left_flow"]}""")!;
            var da = Solve(flow, new List<object?> { frame }, seeds, map, D, D, D, D); var tubes = da.Out<Mesh>(1);
            var curves = da.List(0).Cast<PolylineCurve>().ToArray();
            assert(curves.Length == 2 && curves[0].Points.SequenceEqual(new[] { new Point3d(0, 0, 0), new Point3d(1, 0, 0), new Point3d(2, 0, 0) }) && curves[1].Points.SequenceEqual(new[] { new Point3d(0, 2, 0), new Point3d(0, 3, 0) }), "Seeds with fewer than two points drawn, or a path shifted");
            assert(tubes.Vertices.Count == 30 && tubes.Faces.Count == 18 && tubes.Faces[0] == new MeshFace(0, 1, 7, 6) && tubes.Faces[12] == new MeshFace(18, 19, 25, 24) && tubes.Normals.Calls == 1, "Tube rings or faces wrong");
            var centres = new[] { (new Point3d(0, 0, 0), 0), (new Point3d(1, 0, 0), 0), (new Point3d(2, 0, 0), 0), (new Point3d(0, 2, 0), 1), (new Point3d(0, 3, 0), 1) };
            double Along(Point3d p, int axis) => axis == 0 ? p.X : p.Y;
            assert(Enumerable.Range(0, 30).All(i => Math.Abs(tubes.Vertices[i].DistanceTo(centres[i / 6].Item1) - .03) < 1e-12 && Math.Abs(Along(tubes.Vertices[i], centres[i / 6].Item2) - Along(centres[i / 6].Item1, centres[i / 6].Item2)) < 1e-12), "Tube ring not a radius-0.03 circle across its path point");
            var ring = tubes.VertexColors.Select(c => c.ToArgb()).Where((_, i) => i % 6 == 0).ToArray();
            assert(ring.SequenceEqual(new[] { Color.FromArgb(8, 48, 107).ToArgb(), Color.FromArgb(0, 160, 180).ToArgb(), Color.Black.ToArgb(), Color.FromArgb(150, 235, 140).ToArgb(), Color.FromArgb(150, 235, 140).ToArgb() }) && tubes.VertexColors.Count == 30, "Colours shifted between seeds or unsimulated sample not black");
            da = Solve(flow, new List<object?> { frame }, seeds, map, "q", 40, 0.0, true);
            assert(Json(bridge.Ops("evaluate_submit").Last()["request"]!["direction"]) == "-1" && bridge.Ops("evaluate_submit").Last()["request"]!["field"]!.GetValue<string>() == "q" && da.List(0).Count == 2 && da.Out<Mesh>(1).Vertices.Count == 0, "Zero radius or backward trace wrong");
            Solve(flow, new List<object?> { frame }, seeds, map, D, D, -1.0, D); assert(flow.Errors.Single() == "Radius must be nonnegative", "Negative radius accepted");
            assert(flow.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077129") && Names(flow) == "Frames,Seeds,Colors,Field,Steps,Radius,Backward|Lines,Tubes", "Flow layout changed");
            Reset();
        });

        test("surface field keeps every face and blacks faces with an invalid sample (#81)", () => {
            Reset(); using var bridge = new GhBridge(); JsonObject? reply = null;
            bridge.Respond = r => r["op"]!.GetValue<string>() switch { "evaluate_submit" => new() { ["job"] = "u" + bridge.Ops("evaluate_submit").Count() }, "evaluate_poll" => reply == null ? new() { ["state"] = "running" } : new() { ["state"] = "completed", ["result"] = reply.DeepClone() }, _ => null };
            var surface = new SurfaceFieldComponent { Document = doc }; var frame = Goo("""{"frame":{"id":1},"case":{"spacing":1}}"""); var map = Goo("""{"palette":"blue-green","min":0,"max":2}""");
            var input = new Mesh(); input.Vertices.AddRange(new Point3d[] { new(0, 0, 0), new(1, 0, 0), new(1, 1, 0), new(0, 1, 0), new(2, 0, 0), new(2, 1, 0) });
            input.Faces.AddFace(0, 1, 2, 3); input.Faces.AddFace(1, 4, 5); input.Faces.AddFace(1, 5, 2);
            assert(Solve(surface, new List<object?> { frame }, input, D, D, map).Outputs.Count == 0, "Pending surface published");
            assert(Json(bridge.Ops("evaluate_submit").Single()["request"]!["points"]) == "[[0,0,1],[1,0,1],[1,1,1],[0,1,1],[2,0,1],[2,1,1]]", "Samples not offset along outward normals");
            reply = (JsonObject)JsonNode.Parse("""{"valid":[true,true,true,true,false,true],"values":[0,1,2,0,0,1]}""")!;
            var da = Solve(surface, new List<object?> { frame }, input, D, D, map); var mesh = da.Out<Mesh>(0);
            assert(mesh.Faces.SequenceEqual(new[] { new MeshFace(0, 1, 2, 3), new MeshFace(6, 4, 7), new MeshFace(1, 5, 2) }) && mesh.Vertices.Count == 8 && mesh.Vertices[6] == input.Vertices[1] && mesh.Vertices[7] == input.Vertices[5], "Faces dropped, or an invalid face shares coloured vertices");
            assert(mesh.VertexColors.Select(c => c.ToArgb()).SequenceEqual(new[] { Color.FromArgb(8, 48, 107), Color.FromArgb(0, 160, 180), Color.FromArgb(150, 235, 140), Color.FromArgb(8, 48, 107), Color.Black, Color.FromArgb(0, 160, 180), Color.Black, Color.Black }.Select(c => c.ToArgb())), "Invalid samples coloured as values");
            assert(da.List(1).SequenceEqual(new object?[] { true, true, true, true, false, true }) && da.List(2).SequenceEqual(new object?[] { 0d, 1d, 2d, 0d, 0d, 1d }) && surface.Message == "offset sample; 1 of 3 faces not simulated", "Validity, values or label wrong");
            assert(input.Faces.Count == 3 && input.Vertices.Count == 6 && input.VertexColors.Count == 0, "Input mesh modified");
            reply["valid"] = new JsonArray(false, true, true, true, true, true); da = Solve(surface, new List<object?> { frame }, input, "cp", D, map);
            assert(da.Out<Mesh>(0).Faces[0] == new MeshFace(0, 6, 7, 8) && da.Out<Mesh>(0).Faces.Skip(1).SequenceEqual(input.Faces.Skip(1)) && surface.Message == "offset sample; 1 of 3 faces not simulated", "Invalid quad not blacked on its own vertices");
            reply["valid"] = new JsonArray(true, true, true, true, true, true); da = Solve(surface, new List<object?> { frame }, input, "cp", 2.0, map);
            assert(da.Out<Mesh>(0).Faces.SequenceEqual(input.Faces) && da.Out<Mesh>(0).Vertices.Count == 6 && surface.Message == "offset sample", "Valid surface changed");
            Solve(surface, new List<object?> { frame }, input, D, -1.0, map); assert(surface.Errors.Single() == "Offset must be nonnegative", "Negative offset accepted");
            assert(surface.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077130") && Names(surface) == "Frames,Surface,Field,Offset,Colors|Colored surface,Valid,Values" && surface.Description.Contains("Every face is kept"), "Surface layout changed");
            Reset();
        });

        test("query views finish a pending capture, reuse results and report failures", () => {
            Reset(); using var bridge = new GhBridge(); string state = "running";
            bridge.Respond = r => r["op"]!.GetValue<string>() switch { "evaluate_submit" => new() { ["job"] = "v" + bridge.Ops("evaluate_submit").Count() }, "evaluate_poll" => new() { ["state"] = state, ["error"] = "query failed", ["result"] = new JsonObject { ["n"] = bridge.Ops("evaluate_poll").Count() } }, _ => null };
            var view = new ProbeQuery { Document = doc }; JsonObject Req(int revision) => new() { ["op"] = "field", ["action"] = "capture", ["session"] = "s", ["revision"] = revision };
            assert(view.Query(Req(1)) == null && view.Message == "running" && HawaPollScheduler.PendingCount == 1, "Pending query not polled");
            state = "completed"; var result = view.Query(Req(2), true);
            assert(result!["n"]!.GetValue<int>() == 2 && bridge.Ops("evaluate_submit").Count() == 1 && HawaPollScheduler.PendingCount == 1, "Live capture replaced instead of finished, or newer revision not rescheduled");
            Pulse(); assert(HawaPollScheduler.PendingCount == 1, "Finished capture poll dropped");
            assert(view.Query(Req(1))!["n"]!.GetValue<int>() == 2 && bridge.Ops("evaluate_poll").Count() == 2, "Cached result polled again");
            view.Query(Req(2)); assert(bridge.Ops("evaluate_submit").Count() == 2 && bridge.Ops("evaluate_control").Single()["job"]!.GetValue<string>() == "v1", "Newer revision did not replace the finished job");
            state = "failed"; view.Release(); assert(Catch(() => view.Query(Req(3))) is InvalidOperationException { Message: "query failed" }, "Query failure swallowed");
            Reset();
        });
    }

    static string Names(GH_Component c) => string.Join(",", c.Params.Input.Select(p => p.Name)) + "|" + string.Join(",", c.Params.Output.Select(p => p.Name));
    static Exception? Catch(Action action) { try { action(); return null; } catch (Exception ex) { return ex; } }
}

sealed class IdleProbe() : StandInComponent("Idle");
sealed record GhMany(params object?[] Items);
sealed record GhNamed(string NickName) : IGH_DocumentObject;

// IGH_DataAccess double: inputs by index (D = registered default), VolatileData
// mirrored onto the component's parameters as GH would, outputs recorded.
sealed class GhAccess : IGH_DataAccess
{
    readonly object?[] inputs; readonly GH_Component component;
    public readonly Dictionary<int, object?> Outputs = new();
    public GhAccess(GH_Component c, params object?[] values)
    {
        component = c; inputs = values;
        for (int i = 0; i < c.Params.Input.Count; i++)
        {
            var p = c.Params.Input[i]; p.VolatileData.Items.Clear();
            foreach (var item in Items(Value(i), p.Access)) p.VolatileData.Items.Add(item as IGH_Goo ?? (item == null ? null : new GH_ObjectWrapper(item)));
        }
    }
    static IEnumerable<object?> Items(object? v, GH_ParamAccess access) => v switch { null => Array.Empty<object?>(), GhMany m => m.Items, IEnumerable e when v is not string && access == GH_ParamAccess.list => e.Cast<object?>(), _ => new[] { v } };
    public static readonly object Default = new();
    object? Value(int i) { var v = i < inputs.Length ? inputs[i] : Default; return ReferenceEquals(v, Default) ? Fallback(i) : v; }
    object? Fallback(int i) => i < component.Params.Input.Count ? ((GH_TestParam)component.Params.Input[i]).Default : null;
    public bool GetData<T>(int index, ref T destination)
    {
        var v = Value(index); if (v is GhMany m) v = m.Items[0];
        if (v == null) return false;
        if (v is T t) { destination = t; return true; }
        throw new InvalidCastException($"Input {index}: {v.GetType().Name} is not {typeof(T).Name}");
    }
    public bool GetDataList<T>(int index, List<T> list)
    {
        if (Value(index) is not IEnumerable e) return false;
        foreach (var x in e) list.Add(x is null ? default! : (T)x);
        return true;
    }
    public bool SetData(int index, object? data) { Outputs[index] = data; return true; }
    public bool SetDataList(int index, IEnumerable data) { Outputs[index] = data.Cast<object?>().ToList(); return true; }
    public T Out<T>(int index) => (T)Outputs[index]!;
    public List<object?> List(int index) => (List<object?>)Outputs[index]!;
}

// Scripted embedded runtime for both the component bridge and CaseHub cleanup.
sealed class GhBridge : IDisposable
{
    public readonly List<JsonObject> Calls = new();
    public Func<JsonObject, JsonObject?> Respond = _ => null;
    readonly Func<JsonObject, JsonObject> previous = CaseHub.Transport;
    public GhBridge() { Hawa.Shared.EmbeddedRuntime.Handler = Call; CaseHub.Transport = Call; }
    JsonObject Call(JsonObject request)
    {
        Calls.Add(request.DeepClone().AsObject());
        var reply = Respond(request);
        if (reply != null) return reply;
        var op = request["op"]!.GetValue<string>();
        if (op is "evaluate_control" or "close_async") return new() { ["closed"] = true };
        throw new InvalidOperationException("Unexpected bridge operation " + op);
    }
    public IEnumerable<JsonObject> Ops(string op) => Calls.Where(c => c["op"]!.GetValue<string>() == op);
    public void Dispose() { Hawa.Shared.EmbeddedRuntime.Handler = null; CaseHub.Transport = previous; CaseHub.RetryCleanup(); }
}

sealed class GhArchive(int inputs, int outputs) : GH_IReader, GH_IWriter
{
    public readonly Dictionary<string, string> Strings = new();
    public bool ChunkExists(string name, int index) => name == "param_input" ? index < inputs : name == "param_output" && index < outputs;
    public string GetString(string name) => Strings[name];
    public void SetString(string name, string value) => Strings[name] = value;
}
