using System.Text.Json.Nodes;
using Rhino;

namespace Hawa.Shared;

public sealed record Parameter(string Key, string Label, double Minimum, double Maximum, double Default, string Unit);

public sealed class CaseState
{
    public uint Document { get; init; }
    public Guid Id { get; set; } = Guid.NewGuid();
    public long Revision { get; set; }
    public double Speed { get; set; } = 1;
    public double Cell { get; set; } = .5;
    public double Width { get; set; } = 1;
    public int Target { get; set; } = 200;
    public string Device { get; set; } = "cpu";
    public string Field { get; set; } = "speed";
    public string State { get; set; } = "idle";
    public string Error { get; set; } = "";
    public string? Job, Session, Query;
    public int Steps;
    public long RunRevision = -1, ResultRevision = -1;
    public bool StartWhenReady;
    public JsonObject? Spec, Slice, Status, ResultSpec;
    public int SliceSteps = -1, QuerySteps;
    public Guid? BindingOwner;
    public HashSet<string> Driven { get; } = new();
    public DateTime LastQuery;
    public double Value(string key) => key switch { "speed" => Speed, "cell" => Cell, "width" => Width, _ => throw new ArgumentException("Unknown parameter") };
    public JsonObject Settings() => new() { ["schema"] = 1, ["id"] = Id.ToString(), ["speed"] = Speed, ["cell"] = Cell, ["width"] = Width, ["target"] = Target, ["device"] = Device, ["field"] = Field };
    public JsonObject Describe() => new() { ["id"] = Id.ToString(), ["revision"] = Revision, ["run_revision"] = RunRevision, ["result_revision"] = ResultRevision, ["state"] = State, ["steps"] = Steps, ["session"] = Session, ["job"] = Job, ["error"] = Error, ["settings"] = Settings(), ["linked"] = BindingOwner != null, ["outdated"] = Slice != null && ResultRevision != Revision };
}

// All entry points run on Rhino's UI thread. Numerical work is submitted to the
// existing embedded Python worker; no UI entry point joins a numerical thread.
public static class CaseHub
{
    public static readonly Parameter[] Parameters = {
        new("speed","Inlet speed",.1,3,1,"m/s"),
        new("cell","Cell size",.25,1,.5,"m"),
        new("width","Block width",.5,2,1,"m")
    };
    private static readonly Dictionary<uint, CaseState> Cases = new();
    public static event Action<CaseState, string>? Changed;
    public static IEnumerable<CaseState> All => Cases.Values.ToArray();
    public static CaseState Get(uint document)
    {
        if (RhinoDoc.FromRuntimeSerialNumber(document) == null) throw new InvalidOperationException("Rhino document is closed");
        if (!Cases.TryGetValue(document, out var c)) { Cases[document] = c = new() { Document = document }; Notify(c, "created"); }
        return c;
    }
    public static CaseState? Find(uint document) => Cases.GetValueOrDefault(document);
    private static void Notify(CaseState c, string origin) => Changed?.Invoke(c, origin);
    public static void Bind(CaseState c, Guid owner, IEnumerable<string> driven)
    {
        if (c.BindingOwner != null && c.BindingOwner != owner) throw new InvalidOperationException("This case already has a live Grasshopper binding");
        c.BindingOwner = owner; c.Driven.Clear(); foreach (var key in driven) c.Driven.Add(key); Notify(c, "binding");
    }
    public static void Unbind(CaseState c, Guid owner) { if (c.BindingOwner == owner) { c.BindingOwner = null; c.Driven.Clear(); Notify(c, "binding"); } }
    public static void Edit(uint document, JsonObject values, long expectedRevision, string origin = "panel", bool undo = true)
    {
        var c = Get(document); if (c.Revision != expectedRevision) throw new InvalidOperationException("Case changed; refresh before applying this edit");
        var next = c.Settings(); foreach (var pair in values) { if (!new[] { "speed", "cell", "width", "target", "device", "field" }.Contains(pair.Key)) throw new ArgumentException("Unknown setting: " + pair.Key); if (origin == "panel" && c.Driven.Contains(pair.Key)) throw new InvalidOperationException(pair.Key + " is driven by Grasshopper"); next[pair.Key] = pair.Value?.DeepClone(); }
        Validate(next); if (next.ToJsonString() == c.Settings().ToJsonString()) return;
        var doc = RhinoDoc.FromRuntimeSerialNumber(document)!; string before = c.Settings().ToJsonString(); uint record = undo ? doc.BeginUndoRecord("Hawa case edit") : 0;
        if (undo) RegisterUndo(doc, before);
        Apply(c, next, origin); doc.Modified = true; if (record != 0) doc.EndUndoRecord(record);
    }
    private static void RegisterUndo(RhinoDoc doc, string settings)
    {
        doc.AddCustomUndoEvent("Hawa case edit", (_, e) => { var c = Get(e.Document.RuntimeSerialNumber); RegisterUndo(e.Document, c.Settings().ToJsonString()); Apply(c, JsonNode.Parse(settings)!.AsObject(), "undo"); });
    }
    public static void Validate(JsonObject settings)
    {
        if (settings["schema"]?.GetValue<int>() != 1 || !Guid.TryParse(settings["id"]?.GetValue<string>(), out _)) throw new ArgumentException("Unsupported case schema or ID");
        foreach (var p in Parameters) { double v = settings[p.Key]!.GetValue<double>(); if (!double.IsFinite(v) || v < p.Minimum || v > p.Maximum) throw new ArgumentException($"{p.Label}: {p.Minimum}..{p.Maximum} {p.Unit}"); }
        int target = settings["target"]!.GetValue<int>(); if (target < 1 || target > 100000) throw new ArgumentException("Target steps: 1..100000");
        if (!new[] { "cpu", "mps", "auto", "cuda:0" }.Contains(settings["device"]!.GetValue<string>())) throw new ArgumentException("Unknown backend");
        if (!new[] { "speed", "pressure", "density" }.Contains(settings["field"]!.GetValue<string>())) throw new ArgumentException("Unknown field");
    }
    private static void Apply(CaseState c, JsonObject n, string origin)
    {
        bool physical = c.Speed != n["speed"]!.GetValue<double>() || c.Cell != n["cell"]!.GetValue<double>() || c.Width != n["width"]!.GetValue<double>() || c.Device != n["device"]!.GetValue<string>();
        bool display = c.Field != n["field"]!.GetValue<string>();
        if (physical) { Stop(c); c.Revision++; c.State = c.Slice == null ? "idle" : "outdated"; }
        c.Id = Guid.Parse(n["id"]!.GetValue<string>()); c.Speed = n["speed"]!.GetValue<double>(); c.Cell = n["cell"]!.GetValue<double>(); c.Width = n["width"]!.GetValue<double>(); c.Target = n["target"]!.GetValue<int>(); c.Device = n["device"]!.GetValue<string>(); c.Field = n["field"]!.GetValue<string>(); c.Error = "";
        if (display) { CloseQuery(c); c.Slice = null; c.LastQuery = DateTime.MinValue; }
        Notify(c, origin);
    }
    public static string Save(uint doc) => Get(doc).Settings().ToJsonString();
    public static void Restore(uint doc, string settings)
    {
        var data = JsonNode.Parse(settings)!.AsObject(); Validate(data); var c = Get(doc); Stop(c); Apply(c, data, "restore"); c.Slice = null; c.ResultSpec = null; c.Spec = null; c.Steps = 0; c.SliceSteps = -1; c.RunRevision = -1; c.ResultRevision = -1; c.State = "idle"; Notify(c, "restore");
    }
    public static JsonObject BuildSpec(CaseState c)
    {
        var lengths = new[] { 8d, 6d, 4d }; var n = lengths.Select(x => (int)Math.Floor(x / c.Cell) + 1).ToArray(); var solid = new JsonArray();
        for (int x = 0; x < n[0]; x++) for (int y = 0; y < n[1]; y++) for (int z = 0; z < n[2]; z++) if (Math.Abs(x * c.Cell - 3) <= c.Width / 2 && Math.Abs(y * c.Cell - 3) <= c.Width / 2 && Math.Abs(z * c.Cell - 2) <= c.Width / 2) solid.Add((x * n[1] + y) * n[2] + z);
        if (solid.Count == 0) throw new ArgumentException("The block is unresolved; reduce cell size or increase block width");
        double scale = RhinoMath.UnitScale(UnitSystem.Meters, RhinoDoc.FromRuntimeSerialNumber(c.Document)!.ModelUnitSystem);
        return new() { ["kind"] = "Case", ["label"] = "Hawa native block prototype", ["shape"] = new JsonArray(n[0], n[1], n[2]), ["origin"] = new JsonArray(0d, 0d, 0d), ["spacing"] = c.Cell * scale, ["dx"] = c.Cell, ["speed"] = c.Speed, ["viscosity"] = .1, ["density"] = 1.225, ["mach"] = .04, ["collision"] = "bgk", ["boundaries"] = new JsonArray("inlet", "outlet", "periodic", "periodic", "wall", "slip"), ["solid"] = solid };
    }
    private static JsonObject Call(string op, string session) => EmbeddedRuntime.Call(new() { ["op"] = op, ["session"] = session });
    public static void Run(uint doc)
    {
        var c = Get(doc); c.Error = "";
        if (c.Job != null && c.Session == null) { c.StartWhenReady = true; return; }
        if (c.Session != null && c.RunRevision == c.Revision) { EmbeddedRuntime.Call(new() { ["op"] = "start", ["session"] = c.Session, ["steps"] = c.Target }); c.State = "running"; Notify(c, "run"); return; }
        Stop(c); c.Spec = BuildSpec(c); EmbeddedRuntime.Call(new() { ["op"] = "check", ["case"] = c.Spec.DeepClone() });
        var r = EmbeddedRuntime.Call(new() { ["op"] = "evaluate_submit", ["kind"] = "create", ["case"] = c.Spec.DeepClone(), ["device"] = c.Device });
        c.Job = r["job"]!.GetValue<string>(); c.RunRevision = c.Revision; c.StartWhenReady = true; c.State = "preparing"; Notify(c, "run");
    }
    public static void Pause(uint doc) { var c = Get(doc); c.StartWhenReady = false; if (c.Session != null) Call("pause_async", c.Session); c.State = c.Session == null ? "paused" : "pausing"; Notify(c, "pause"); }
    public static void Cancel(uint doc) { var c = Get(doc); Stop(c); c.State = "cancelled"; Notify(c, "cancel"); }
    public static void Reset(uint doc) { var c = Get(doc); Stop(c); c.Slice = null; c.ResultRevision = -1; c.Steps = 0; c.State = "idle"; Notify(c, "reset"); }
    private static void CloseQuery(CaseState c) { if (c.Query != null) { try { EmbeddedRuntime.Call(new() { ["op"] = "evaluate_control", ["job"] = c.Query, ["action"] = "close" }); } catch { } c.Query = null; } }
    private static void Stop(CaseState c)
    {
        CloseQuery(c); if (c.Job != null) { try { EmbeddedRuntime.Call(new() { ["op"] = "evaluate_control", ["job"] = c.Job, ["action"] = "close" }); } catch { } c.Job = null; }
        else if (c.Session != null) { try { Call("close_async", c.Session); } catch { } }
        c.Session = null; c.StartWhenReady = false; c.Status = null;
    }
    public static void Close(uint doc) { if (Cases.Remove(doc, out var c)) { Stop(c); Notify(c, "closed"); } }
    private static bool polling;
    public static void Tick()
    {
        if (polling) return; polling = true;
        try
        {
            foreach (var c in All) try
                {
                    var previousState = c.State; var previousSteps = c.Steps; var previousSlice = c.Slice;
                    if (c.Job != null && c.Session == null) { var r = EmbeddedRuntime.Call(new() { ["op"] = "evaluate_poll", ["job"] = c.Job }); string state = r["state"]!.GetValue<string>(); if (state == "failed") throw new Exception(r["error"]!.GetValue<string>()); if (state != "completed") continue; c.Session = r["result"]!["status"]!["session"]!.GetValue<string>(); if (c.StartWhenReady) Run(c.Document); else c.State = "paused"; }
                    if (c.Session == null) continue;
                    c.Status = Call("status", c.Session); c.Steps = c.Status["steps"]!.GetValue<int>(); c.State = c.Status["state"]!.GetValue<string>(); if (c.Status["error"] != null) throw new Exception(c.Status["error"]!.GetValue<string>());
                    if (c.Query != null) { var r = EmbeddedRuntime.Call(new() { ["op"] = "evaluate_poll", ["job"] = c.Query }); string state = r["state"]!.GetValue<string>(); if (state == "failed") throw new Exception(r["error"]!.GetValue<string>()); if (state == "completed") { c.Slice = r["result"]!.DeepClone().AsObject(); c.ResultSpec = c.Spec?.DeepClone().AsObject(); c.SliceSteps = c.QuerySteps; c.ResultRevision = c.RunRevision; CloseQuery(c); } }
                    if (c.Query == null && (DateTime.UtcNow - c.LastQuery).TotalSeconds > .6 && (c.State == "running" || c.Slice == null || c.SliceSteps != c.Steps))
                    {
                        var request = new JsonObject { ["op"] = "slice", ["session"] = c.Session, ["field"] = c.Field, ["axis"] = 2 };
                        c.QuerySteps = c.Steps; c.Query = EmbeddedRuntime.Call(new() { ["op"] = "evaluate_submit", ["kind"] = "query", ["request"] = request })["job"]!.GetValue<string>(); c.LastQuery = DateTime.UtcNow;
                    }
                    if (previousState != c.State || previousSteps != c.Steps || !ReferenceEquals(previousSlice, c.Slice)) Notify(c, "progress");
                }
                catch (Exception ex) { c.Error = ex.Message; Stop(c); c.State = "failed"; Notify(c, "error"); }
        }
        finally { polling = false; }
    }
}
