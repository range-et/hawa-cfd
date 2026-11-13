using System.Drawing;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Hawa.Grasshopper;
using Hawa.Native;
using Hawa.Shared;
using Rhino;
using Rhino.Display;
using Rhino.DocObjects;
using Rhino.Geometry;

// Boundary annotation previews (#38): the shared glyph model, the native conduit
// and the selected-only Grasshopper Case/Boundary Set previews, against recording
// display doubles. Positions and labels are derived by hand from each frame.
// These checks cannot show legibility, label overlap or live redraw timing.
static class PreviewContracts
{
    sealed class Args(DisplayPipeline display) : IGH_PreviewArgs { public DisplayPipeline Display { get; } = display; }
    static bool Near(Point3d a, Point3d b) => a.DistanceTo(b) < 1e-9;
    static bool Segment(object line, Point3d from, Point3d to) => line is Line l && Near(l.From, from) && Near(l.To, to);
    static List<(Point3d At, string Text, Color Color)> Dots(DisplayPipeline d) => d.Of("dot").Select(a => ((Point3d)a[0], (string)a[1], (Color)a[2])).ToList();
    static bool HasDot(DisplayPipeline d, Point3d at, string text, Color color) => Dots(d).Any(x => Near(x.At, at) && x.Text == text && x.Color == color);

    public static void Run(Action<string, Action> test, Action<bool, string> assert)
    {
        test("native preview annotates the default block case with the domain box", () => {
            var doc = new RhinoDoc(501); var c = CaseHub.Get(501); using var preview = new NativePreview(); var d = new DisplayPipeline();
            preview.RaisePostDraw(new DrawEventArgs(doc, d));
            var boxes = d.Of("box").ToList();
            assert(boxes.Count == 2 && (BoundingBox)boxes[0][0] == new BoundingBox(new(0, 0, 0), new(8, 6, 4)) && (BoundingBox)boxes[1][0] == new BoundingBox(new(2.5, 2.5, 1.5), new(3.5, 3.5, 2.5)), "Domain or block box changed");
            var dots = Dots(d);
            assert(dots.Count == 6 && HasDot(d, new(0, 3, 3), "X- inlet · +X 1 m/s", BoundaryAnnotations.Velocity) && HasDot(d, new(8, 3, 3), "X+ outlet · open, extrapolated", BoundaryAnnotations.Open)
                && HasDot(d, new(4, 0, 3), "Y- periodic ↔ Y+", BoundaryAnnotations.Periodic) && HasDot(d, new(4, 6, 3), "Y+ periodic ↔ Y-", BoundaryAnnotations.Periodic)
                && HasDot(d, new(4, 4.5, 0), "Z- wall", BoundaryAnnotations.Wall) && HasDot(d, new(4, 4.5, 4), "Z+ slip", BoundaryAnnotations.Slip), "Accepted faces mislabelled or misplaced");
            assert(dots.Select(x => x.Text).All(t => !t.Contains("outflow")), "A face label implies guaranteed outflow");
            var arrows = d.Of("arrow").ToList(); var dotted = d.Of("dotted").ToList();
            assert(arrows.Count == 1 && Segment(arrows[0][0], new(0, 3, 2), new(.8, 3, 2)), "Inlet arrow must point +X into the box");
            assert(dotted.Count == 2 && Near((Point3d)dotted[0][0], new(4, 0, 2)) && Near((Point3d)dotted[0][1], new(4, 6, 2)) && Near((Point3d)dotted[1][0], new(8, 3, 2)) && Near((Point3d)dotted[1][1], new(7.6, 3, 2)) && !d.Of("line").Any(), "Periodic pair or outlet tick wrong");
            assert(d.Calls.FindIndex(x => x.Op == "dot") > d.Calls.FindIndex(x => x.Op == "box") && !d.Of("mesh").Any() && !((string)d.Of("text").Single()[0]).Contains("OUTDATED"), "Annotation order or status changed");
            int push = d.Calls.FindIndex(x => x.Op == "depth"), pop = d.Calls.FindIndex(x => x.Op == "depth-pop");
            assert(push >= 0 && !(bool)d.Calls[push].Args[0] && push < d.Calls.FindIndex(x => x.Op == "dotted") && pop > d.Calls.FindLastIndex(x => x.Op == "dot") && pop < d.Calls.FindIndex(x => x.Op == "box" && d.Calls.IndexOf(x) > push), "Annotations must draw without depth testing and restore it before the body box");
            CaseHub.Close(501);
        });

        test("native annotations follow selected-domain origin, units and edited faces", () => {
            var doc = new RhinoDoc(502) { ModelUnitSystem = UnitSystem.Millimeters }; var c = CaseHub.Get(502); using var preview = new NativePreview();
            var found = Guid.NewGuid(); doc.Objects.Items[found] = new RhinoObject(new GeometryBase { Bounds = new(new(1, 1, 1), new(2, 2, 2)) });
            c.SetupData["mode"] = "selected"; c.SetupData["origin"] = new JsonArray(10d, -2d, 1d); c.SetupData["size"] = new JsonArray(4d, 2d, 2d);
            c.SetupData["objects"] = new JsonArray(found.ToString(), Guid.NewGuid().ToString());
            c.SetupData["boundaries"] = new JsonArray("inlet", "outlet", "wall", "wall", "wall", "slip");
            var d = new DisplayPipeline(); preview.RaisePostDraw(new DrawEventArgs(doc, d));
            var boxes = d.Of("box").ToList();
            assert(boxes.Count == 2 && (BoundingBox)boxes[0][0] == new BoundingBox(new(10000, -2000, 1000), new(14000, 0, 3000)) && (int)boxes[1][2] == 1, "Selected domain or found object box wrong");
            assert(HasDot(d, new(10000, -1000, 2500), "X- inlet · +X 1 m/s", BoundaryAnnotations.Velocity) && HasDot(d, new(12000, -2000, 2500), "Y- wall", BoundaryAnnotations.Wall) && HasDot(d, new(12000, 0, 2500), "Y+ wall", BoundaryAnnotations.Wall), "Edited faces not shown in document units");
            var dotted = d.Of("dotted").ToList();
            assert(Segment(d.Of("arrow").Single()[0], new(10000, -1000, 2000), new(10400, -1000, 2000)) && dotted.Count == 1 && Near((Point3d)dotted[0][1], new(13800, -1000, 2000)), "Walled Y faces kept a periodic pair or arrow scale wrong");
            CaseHub.Close(502);
        });

        test("native preview hides setup labels for outdated results and keeps field legend and cache", () => {
            var doc = new RhinoDoc(503); var c = CaseHub.Get(503); var preview = new NativePreview();
            c.SliceData = JsonNode.Parse("{\"coordinates\":[[0.0,0.0,0.0],[0.0,1.0,0.0],[1.0,0.0,0.0],[1.0,1.0,0.0]],\"values\":[1.0,2.0,3.0,4.0],\"valid\":[true,true,true,true],\"shape\":[2,2]}")!.AsObject();
            c.ResultSpecData = new JsonObject { ["dx"] = .5, ["shape"] = new JsonArray(2, 2, 1), ["origin_m"] = new JsonArray(1d, 2d, 3d), ["wall_links"] = new JsonArray(new JsonArray(1, 0, .5)), ["hawa_block_width"] = 2d };
            c.Result = new ResultStamp(c.Id, c.Revision, c.Generation, "s", "speed", 7, .7);
            var d = new DisplayPipeline(); preview.RaisePostDraw(new DrawEventArgs(doc, d));
            var texts = d.Of("text").Select(a => (string)a[0]).ToList(); var first = (Mesh)d.Of("mesh").Single()[0];
            assert(Dots(d).Count == 6 && texts[0] == "Hawa · speed · field 7 / solver 0 · t=0.7 s" && texts.Count == 8 && texts[1] == "■ 0" && texts[5] == "■ 4" && texts[6] == "m/s · auto range" && texts[7] == "Clipped boundary · stationary wall speed = 0", "Current result lost annotations or legend");
            c.Field = "pressure"; c.Result = c.Result with { Field = "pressure" }; c.ResultVersion++;
            d = new DisplayPipeline(); preview.RaisePostDraw(new DrawEventArgs(doc, d)); texts = d.Of("text").Select(a => (string)a[0]).ToList();
            assert(first.Disposed && texts[6] == "Pa · auto range" && texts[7] == "Clipped boundary · colours use adjacent fluid samples", "Recache did not dispose or relabel");
            c.Revision++;
            d = new DisplayPipeline(); preview.RaisePostDraw(new DrawEventArgs(doc, d));
            var boxes = d.Of("box").ToList();
            assert(!d.Of("dot").Any() && !d.Of("arrow").Any() && !d.Of("dotted").Any() && ((string)d.Of("text").First()[0]).EndsWith(" · OUTDATED · boundary labels hidden"), "Outdated result showed accepted setup labels");
            assert((BoundingBox)boxes[0][0] == new BoundingBox(new(1, 2, 3), new(1.5, 2.5, 3)) && (BoundingBox)boxes[1][0] == new BoundingBox(new(2, 2, 1), new(4, 4, 3)), "Outdated boxes must show the result domain and block");
            var bounds = new CalculateBoundingBoxEventArgs(doc); preview.RaiseBoundingBox(bounds); var none = new CalculateBoundingBoxEventArgs(new RhinoDoc(504)); preview.RaiseBoundingBox(none);
            assert(bounds.Included.Single() == new BoundingBox(new(1, 2, 3), new(1.5, 2.5, 3)) && none.Included.Count == 0, "Conduit bounds wrong");
            var empty = new DisplayPipeline(); preview.RaisePostDraw(new DrawEventArgs(none.RhinoDoc, empty));
            foreach (var key in new[] { "domain", "body", "field" }) c.ViewData[key] = false;
            preview.RaisePostDraw(new DrawEventArgs(doc, empty));
            assert(empty.Calls.Count == 0, "Hidden views or absent case drew");
            var current = (Mesh)d.Of("mesh").Single()[0]; CaseHub.Close(503);
            assert(current.Disposed, "Closing the case retained its preview mesh");
            var other = new RhinoDoc(505); var o = CaseHub.Get(505); o.SliceData = c.SliceData; o.ResultSpecData = c.ResultSpecData; o.Result = new ResultStamp(o.Id, o.Revision, o.Generation, "s", "speed", 1);
            d = new DisplayPipeline(); preview.RaisePostDraw(new DrawEventArgs(other, d)); var retained = (Mesh)d.Of("mesh").Single()[0];
            preview.Enabled = true; preview.Dispose();
            assert(retained.Disposed && !preview.Enabled, "Dispose kept meshes or left the conduit enabled");
            CaseHub.Close(505);
        });

        test("shared annotations keep outward arrows inside, pair periodic patches and tolerate missing frames", () => {
            var frame = """{"origin":[0,0,0],"basis":[[1,0,0],[0,1,0],[0,0,1]],"spacing":1,"shape":[11,5,3]""";
            string P(string id, string face, string condition) => $$"""{"id":"{{id}}","face":"{{face}}","condition":{{condition}}}""";
            var json = frame + ""","boundary_set":{"schema":1,"patches":[""" + string.Join(",", P("in", "x-", """{"type":"velocity","velocity":[1,0,0]}"""), P("jet", "x+", """{"type":"velocity","velocity":[2,0,0]}"""),
                P("s1", "y-", """{"type":"periodic"}"""), P("s2", "y+", """{"type":"periodic"}"""), P("floor", "z-", """{"type":"wall"}"""), P("lid", "z+", """{"type":"slip"}""")) + "]}}";
            var a = BoundaryAnnotations.ForCase(json);
            assert(ReferenceEquals(a, BoundaryAnnotations.ForCase(json)), "Same accepted case reparsed on redraw");
            assert(a.Bounds == new BoundingBox(new(0, 0, 0), new(10, 4, 2)) && a.Pairs.Count == 1 && Near(a.Pairs[0].From, new(5, 0, 1)) && Near(a.Pairs[0].To, new(5, 4, 1)), "Bounds or periodic pair wrong");
            var jet = a.Marks.Single(m => m.Text == "jet velocity · 2 m/s");
            assert(jet.Arrow is Line out1 && Near(out1.From, new(9.6, 2, 1)) && Near(out1.To, new(10, 2, 1)), "Outward arrow left the domain box");
            assert(a.Marks.Any(m => m.Text == "s1 periodic ↔ y+") && a.Marks.Any(m => m.Text == "floor wall" && m.Arrow == null) && a.Marks.Any(m => m.Text == "lid slip" && m.Color == BoundaryAnnotations.Slip), "Patch labels wrong");
            var legacy = BoundaryAnnotations.ForCase(frame + "}");
            assert(legacy.Marks[0].Text == "X- inlet · +X" && legacy.Pairs.Count == 1, "Case without speed or boundaries must use the plugin default faces");
            assert(ReferenceEquals(BoundaryAnnotations.ForCase("""{"kind":"Case","example":"tgv3d-bgk","origin":[0,0,0],"spacing":1}"""), BoundaryAnnotations.None) && BoundaryAnnotations.None.Marks.Count == 0, "Example case without a frame drew annotations");
        });

        var doc = new GH_Document { FilePath = "/work/defs/case.gh" };
        HawaGoo Goo(string json) => new((JsonObject)JsonNode.Parse(json)!);
        GhAccess Solve(GH_Component c, params object?[] inputs) { var da = new GhAccess(c, inputs); c.Compute(da); var output = c.Params.Output[0].VolatileData.Items; output.Clear(); if (da.Outputs.TryGetValue(0, out var v) && v is IGH_Goo g) output.Add(g); return da; }
        const string DomainJson = """{"kind":"Domain","label":"d","shape":[5,4,3],"origin":[5,5,0],"basis":[[0,1,0],[-1,0,0],[0,0,1]],"spacing":2,"dx":2}""";
        var domain = Goo(DomainJson);
        var physics = Goo("""{"kind":"Physics","label":"p","speed":3,"viscosity":0.1,"density":1.2,"mach":0.05,"collision":"bgk"}""");

        test("GH Case previews its accepted boundaries in the domain frame only while selected", () => {
            var comp = new CaseComponent { Document = doc };
            assert(comp.ComponentGuid == new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077105") && comp.IsPreviewCapable && comp.ClippingBox == BoundingBox.Empty, "Identity or empty preview changed");
            var da = Solve(comp, domain, null, physics, null); var result = ((HawaGoo)da.Outputs[0]!).Data;
            assert(result["speed"]!.GetValue<double>() == 3 && result["collision"]!.GetValue<string>() == "bgk" && result["kind"]!.GetValue<string>() == "Case" && result["label"]!.GetValue<string>() == "Hawa wind case" && result["boundaries"] == null && result["solid"] == null, "Case composition changed");
            assert(comp.ClippingBox == new BoundingBox(new(-1, 5, 0), new(5, 13, 4)), "Clipping box ignores the oriented domain");
            var d = new DisplayPipeline(); comp.DrawViewportWires(new Args(d));
            assert(d.Calls.Count == 0, "Unselected Case drew annotations");
            comp.Attributes.Selected = true; comp.DrawViewportWires(new Args(d));
            assert(HasDot(d, new(2, 5, 3), "X- inlet · +X 3 m/s", BoundaryAnnotations.Velocity) && HasDot(d, new(2, 13, 3), "X+ outlet · open, extrapolated", BoundaryAnnotations.Open) && Segment(d.Of("arrow").Single()[0], new(2, 5, 2), new(2, 5.8, 2)), "Default faces not drawn along the domain X axis");
            var pair = d.Of("dotted").First();
            assert(Near((Point3d)pair[0], new(5, 9, 2)) && Near((Point3d)pair[1], new(-1, 9, 2)), "Default periodic Y pair wrong");
            var shifted = Goo(((HawaGoo)da.Outputs[0]!).Value.Replace("\"origin\":[5,5,0]", "\"origin\":[20,0,0]"));
            comp.Params.Output[0].VolatileData.Items.Add(shifted);
            d = new DisplayPipeline(); comp.DrawViewportWires(new Args(d));
            assert(comp.ClippingBox == new BoundingBox(new(-1, 0, 0), new(20, 13, 4)) && Dots(d).Count == 12 && HasDot(d, new(17, 0, 3), "X- inlet · +X 3 m/s", BoundaryAnnotations.Velocity), "A second list-matched case was not drawn or bounded");
            comp.Params.Output[0].VolatileData.Items.Remove(shifted);
            var geometry = Goo("""{"kind":"Geometry","domain":""" + DomainJson + ""","solid":[1],"solid_halo":[2],"wall_links":[[1,0,0.5]]}""");
            var faces = Goo("""{"kind":"Boundaries","boundaries":["inlet","outlet","wall","wall","periodic","periodic"]}""");
            comp.Params.Input[1].Sources.Add(comp.Params.Input[0]);
            da = Solve(comp, domain, geometry, physics, faces); result = ((HawaGoo)da.Outputs[0]!).Data;
            assert(result["solid"]!.ToJsonString() == "[1]" && result["solid_halo"]!.ToJsonString() == "[2]" && result["wall_links"]!.ToJsonString() == "[[1,0,0.5]]" && result["boundaries"]![4]!.GetValue<string>() == "periodic", "Geometry or boundaries not copied");
            d = new DisplayPipeline(); comp.DrawViewportWires(new Args(d)); pair = d.Of("dotted").First();
            assert(HasDot(d, new(5, 9, 3), "Y- wall", BoundaryAnnotations.Wall) && Near((Point3d)pair[0], new(2, 9, 0)) && Near((Point3d)pair[1], new(2, 9, 4)), "Connected boundaries not previewed");
            Solve(comp, domain, Goo("""{"kind":"Geometry","domain":{"other":1},"solid":[]}"""), physics, null);
            assert(comp.Errors.Contains("Geometry was voxelized on a different domain") && comp.ClippingBox == BoundingBox.Empty, "Mismatched geometry accepted or stale preview kept");
            assert(Solve(comp, domain, null, physics, null).Outputs.Count == 0, "Case solved while connected geometry was pending");
        });

        test("GH Boundary Set previews accepted NEE patches after the worker check only while selected", () => {
            using var bridge = new GhBridge(); string state = "running";
            bridge.Respond = r => r["op"]!.GetValue<string>() switch {
                "evaluate_submit" => new JsonObject { ["job"] = "j1" },
                "evaluate_poll" => state == "completed" ? new JsonObject { ["state"] = "completed", ["result"] = new JsonObject { ["ok"] = true } } : new JsonObject { ["state"] = "running" },
                _ => null
            };
            var caseGoo = (HawaGoo)Solve(new CaseComponent { Document = doc }, domain, null, physics, null).Outputs[0]!;
            HawaGoo P(string face, string condition) => Goo($$"""{"kind":"BoundaryPatch","label":"{{face}}","id":"{{face}}","face":"{{face}}","condition":{{condition}}}""");
            var patches = new List<object> { P("x-", """{"type":"velocity","velocity":[2,0,0],"profile":"parabolic","profile_axis":1}"""), new GH_ObjectWrapper(P("x+", """{"type":"open","velocity":[0,0,0],"pressure_pa":0,"backflow_mode":"velocity","profile":"uniform"}""")),
                P("y-", """{"type":"wall","velocity":[0,0,0]}"""), P("y+", """{"type":"wall","velocity":[1.5,0,0]}"""), P("z-", """{"type":"slip"}"""), P("z+", """{"type":"pressure","pressure_pa":5}""") };
            var comp = new BoundarySetComponent { Document = doc };
            assert(comp.ComponentGuid == new Guid("3c7b9535-cfa0-473e-8dbb-61c984374f14") && comp.IsPreviewCapable, "Identity changed");
            var da = Solve(comp, caseGoo, patches);
            assert(da.Outputs.Count == 0 && comp.ClippingBox == BoundingBox.Empty && comp.Message == "running", "Unchecked patches published");
            state = "completed"; da = Solve(comp, caseGoo, patches); var spec = ((HawaGoo)da.Outputs[0]!).Data;
            var check = bridge.Ops("evaluate_submit").Single()["request"]!;
            assert(check["op"]!.GetValue<string>() == "check" && check["case"]!["boundary_set"]!["patches"]!.AsArray().Count == 6 && (string)da.Outputs[1]! == """{"ok":true}""", "Worker check request or report wrong");
            assert(spec["boundary_method"]!.GetValue<string>() == "hawa-nee-v1" && spec["initial_velocity"]!.ToJsonString() == "[0,0,0]" && spec["boundary_set"]!["patches"]![0]!["kind"] == null && spec["boundary_set"]!["patches"]![1]!["face"]!.GetValue<string>() == "x+", "Compiled boundary set changed");
            var d = new DisplayPipeline(); comp.DrawViewportWires(new Args(d));
            assert(d.Calls.Count == 0 && comp.ClippingBox == new BoundingBox(new(-1, 5, 0), new(5, 13, 4)), "Unselected Boundary Set drew or lost bounds");
            comp.Attributes.Selected = true; comp.DrawViewportWires(new Args(d));
            var arrows = d.Of("arrow").ToList(); var solid = d.Of("line").Single(); var dotted = d.Of("dotted").Single();
            assert(HasDot(d, new(2, 5, 3), "x- velocity · 2 m/s parabolic", BoundaryAnnotations.Velocity) && HasDot(d, new(2, 13, 3), "x+ open/pressure reference · 0 Pa gauge", BoundaryAnnotations.Open)
                && HasDot(d, new(5, 9, 3), "y- wall", BoundaryAnnotations.Wall) && HasDot(d, new(-1, 9, 3), "y+ wall · moving 1.5 m/s", BoundaryAnnotations.Wall)
                && HasDot(d, new(0.5, 9, 0), "z- slip", BoundaryAnnotations.Slip) && HasDot(d, new(0.5, 9, 4), "z+ pressure reference · 5 Pa gauge", BoundaryAnnotations.Pressure), "Patch labels or anchors wrong");
            assert(arrows.Count == 2 && Segment(arrows[0][0], new(2, 5, 2), new(2, 5.8, 2)) && Segment(arrows[1][0], new(-1, 9, 2), new(-1, 9.8, 2)), "Velocity or moving-wall arrows wrong");
            assert(Near((Point3d)solid[0], new(2, 9, 4)) && Near((Point3d)solid[1], new(2, 9, 3.6)) && (int)solid[3] == 3 && Near((Point3d)dotted[0], new(2, 13, 2)) && Near((Point3d)dotted[1], new(2, 12.6, 2)), "Pressure and open markers must be distinct inward normal ticks");
            Solve(comp, caseGoo, new List<object> { new GH_String("x-") });
            assert(comp.Errors.Contains("Use Boundary Patch objects"), "Non-patch input accepted");
            Solve(comp, caseGoo, patches, Vector3d.Unset);
            assert(comp.Errors.Contains("Finite initial velocity required"), "Unset initial velocity accepted");
        });
    }
}
