using System.Diagnostics;
using System.Text.Json.Nodes;
using Hawa.Shared;
using Rhino;

int passed = 0;
var timings = new List<double>();
void Assert(bool ok, string message) { if (!ok) throw new Exception(message); }
void Reject(Action action) { bool rejected = false; try { action(); } catch { rejected = true; } Assert(rejected, "Command was accepted"); }
void Test(string name, Action action) { action(); passed++; Console.WriteLine("PASS " + name); }
var doc = new RhinoDoc(1); var other = new RhinoDoc(2);
var fake = new FakeRuntime(); CaseHub.Transport = request => JsonNode.Parse(fake.Call(request).ToJsonString())!.AsObject();
CaseState Fresh() { CaseHub.Close(1); return CaseHub.Get(1); }
void Edit(CaseState c, JsonObject patch) => CaseHub.Edit(c.Document, patch, c.Version);
void Tick() { CaseHub.Tick(); }
void Start(CaseState c) { CaseHub.Run(c.Document); Tick(); }
void Field(CaseState c) { c.LastQuery = DateTime.MinValue; Tick(); Tick(); }

Test("read-only outward state and detached JSON", () => {
    var c = Fresh(); Assert(typeof(CaseState).GetProperty("Speed")!.SetMethod!.IsAssembly, "Public settings setter");
    Assert(typeof(CaseState).GetField("Session") == null, "Public mutable handle");
    var settings = c.Settings(); settings["speed"] = 2; Assert(c.Speed == 1, "Settings alias");
    Start(c); Field(c); var result = c.Slice!; result["values"]![0] = 900; Assert(c.Slice!["values"]![0]!.GetValue<double>() != 900, "Field alias");
});
Test("all edits use version, physical revision stays separate", () => {
    var c = Fresh(); long version = c.Version; Edit(c, new() { ["field"] = "pressure" });
    Assert(c.Version == version + 1 && c.Revision == 0, "Wrong version domain");
    Reject(() => CaseHub.Edit(1, new() { ["target"] = 50 }, version));
    Edit(c, new() { ["target"] = 75 }); Assert(c.Revision == 0 && c.Version == 2, "Target not versioned");
});
Test("observer faults cannot abort edit, undo or healthy solver", () => {
    var c = Fresh(); Action<CaseState, string> bad = (_, _) => throw new Exception("bad view");
    int delivered = 0; Action<CaseState, string> good = (_, _) => delivered++;
    CaseHub.Changed += bad; CaseHub.Changed += good;
    try { Edit(c, new() { ["speed"] = 1.2 }); Start(c); Field(c); Assert(c.Speed == 1.2 && c.Session != null && c.State != "failed", "Observer broke model"); Assert(doc.OpenUndoRecords == 0 && delivered > 0, "Undo leaked or observer starved"); }
    finally { CaseHub.Changed -= bad; CaseHub.Changed -= good; }
});
Test("binding leases reject stale writers and protect computed inputs", () => {
    var c = Fresh(); var owner = Guid.NewGuid(); var lease = CaseHub.Bind(c, owner, new[] { "speed" });
    Reject(() => Edit(c, new() { ["speed"] = 2 }));
    Reject(() => CaseHub.EditFromBinding(1, c.Id, Guid.NewGuid(), lease, new() { ["speed"] = 2 }, c.Version));
    CaseHub.EditFromBinding(1, c.Id, owner, lease, new() { ["speed"] = 1.2 }, c.Version);
    CaseHub.Unbind(c, owner, lease); var replacement = CaseHub.Bind(c, owner, Array.Empty<string>());
    Assert(replacement != lease, "Lease reused");
    CaseHub.Unbind(c, owner, lease); Assert(c.BindingLease == replacement, "Expired lease released current owner");
    Reject(() => CaseHub.EditFromBinding(1, c.Id, owner, lease, new() { ["speed"] = 2 }, c.Version));
    CaseHub.ConfigureBinding(c, owner, replacement, new Dictionary<string, int> { ["speed"] = 2 });
    Reject(() => Edit(c, new() { ["speed"] = 1.234 }));
});
Test("restore publishes one idle state with no old runtime", () => {
    var c = Fresh(); Start(c); Field(c); string saved = CaseHub.Save(1); int events = 0; bool coherent = true;
    Action<CaseState, string> watch = (v, origin) => { if (origin == "restore") { events++; coherent &= v.Session == null && v.Slice == null && v.Steps == 0 && v.State == "idle"; } };
    CaseHub.Changed += watch; try { CaseHub.Restore(1, saved); } finally { CaseHub.Changed -= watch; }
    Assert(events == 1 && coherent, "Restore event count or coherence");
});
Test("old undo cannot recreate or change a replacement case", () => {
    var c = Fresh(); Edit(c, new() { ["speed"] = 1.2 }); var id = c.Id; CaseHub.Close(1); doc.Undo(); Assert(CaseHub.Find(1) == null, "Undo resurrected case");
    c = Fresh(); Edit(c, new() { ["speed"] = 1.3 }); CaseHub.Close(1); var replacement = CaseHub.Get(1); doc.Undo(); Assert(replacement.Speed == 1 && replacement.Id != id, "Undo mutated replacement");
});
Test("query failure preserves healthy solver and last good field", () => {
    var c = Fresh(); Start(c); Field(c); string session = c.Session!; var stamp = c.Result; long version = c.ResultVersion;
    fake.FailQuery = true; c.LastQuery = DateTime.MinValue; Tick(); Tick(); fake.FailQuery = false;
    Assert(c.Session == session && c.State != "failed" && c.Result == stamp && c.ResultVersion == version && c.ViewError.Length > 0, "Query failure damaged solver/result");
    CaseHub.RefreshView(1); Field(c); Assert(c.ViewError == "", "View recovery failed");
});
Test("malformed field metadata does not partially replace a snapshot", () => {
    var c = Fresh(); Start(c); Field(c); var previous = c.Slice!.ToJsonString(); var stamp = c.Result; long version = c.ResultVersion;
    fake.BadTime = true; c.LastQuery = DateTime.MinValue; Tick(); Tick(); fake.BadTime = false;
    Assert(c.Slice!.ToJsonString() == previous && c.Result == stamp && c.ResultVersion == version && c.ViewError.Length > 0, "Partial result publication");
});
Test("field reports capture step, time, field and session", () => {
    var c = Fresh(); Start(c); Field(c); Assert(c.Result!.Steps == 7 && c.Result.PhysicalTime == .7 && c.Result.Session == c.Session && c.Result.Field == c.Field, "Provenance not from snapshot");
});
Test("failed cleanup stays owned and can be retried idempotently", () => {
    var c = Fresh(); Start(c); fake.FailClose = true; CaseHub.Cancel(1); Assert(CaseHub.PendingCleanupCount > 0 && c.Session == null, "Cleanup lost");
    fake.FailClose = false; CaseHub.RetryCleanup(); Assert(CaseHub.PendingCleanupCount == 0, "Cleanup retry failed");
});
Test("close during notification drains without another command", () => {
    var c = Fresh(); Action<CaseState, string> close = (v, origin) => { if (origin == "panel") CaseHub.Close(v.Document); };
    CaseHub.Changed += close; try { Edit(c, new() { ["speed"] = 1.2 }); } finally { CaseHub.Changed -= close; }
    Assert(CaseHub.Find(1) == null, "Deferred close leaked");
});
Test("close during transport rejects late publication and releases jobs", () => {
    var c = Fresh(); Start(c); fake.OnQuery = () => CaseHub.Close(1); c.LastQuery = DateTime.MinValue; Tick(); Tick(); fake.OnQuery = null;
    Assert(CaseHub.Find(1) == null && CaseHub.PendingCleanupCount == 0, "Late result escaped closure");
});
Test("same persisted ID in two documents remains isolated", () => {
    var c = Fresh(); CaseHub.Restore(2, c.Settings().ToJsonString()); var second = CaseHub.Get(2); Edit(second, new() { ["speed"] = 2 }); Assert(c.Speed == 1 && second.Id == c.Id, "Cross-document write"); CaseHub.Close(2);
});
Test("off-thread mutation fails explicitly", () => {
    RhinoApp.InvokeRequired = true; try { Reject(() => CaseHub.Get(1)); } finally { RhinoApp.InvokeRequired = false; }
});
Test("unit edits notify views without changing physics or restarting", () => {
    var c = Fresh(); Start(c); string session = c.Session!; long revision = c.Revision;
    int events = 0; Action<CaseState, string> watch = (_, origin) => { if (origin == "units") events++; };
    CaseHub.Changed += watch;
    try { doc.ModelUnitSystem = UnitSystem.Millimeters; Tick(); Assert(events == 1 && c.Session == session && c.Revision == revision, "Units changed solver or missed view notification"); }
    finally { CaseHub.Changed -= watch; doc.ModelUnitSystem = UnitSystem.Meters; }
});
Test("pause during preparation never auto-starts", () => {
    var c = Fresh(); CaseHub.Run(1); CaseHub.Pause(1); Tick(); Assert(c.State == "paused" && !c.StartWhenReady && fake.State == "ready", "Preparation pause lost");
});
Test("solver submission failure is visible and retryable", () => {
    var c = Fresh(); fake.FailCreate = true; CaseHub.Run(1); Assert(c.State == "failed" && c.Fault?.Area == "solver" && c.Fault.Retryable && c.Session == null, "Invisible failure"); fake.FailCreate = false; Start(c); Assert(c.Session != null, "Retry failed");
});
var benchmarkCase = Fresh();
for (int i = 0; i < 1000; i++) { var sw = Stopwatch.StartNew(); CaseHub.Edit(1, new() { ["target"] = 200 + i % 2 }, benchmarkCase.Version, "panel", false); timings.Add(sw.Elapsed.TotalMilliseconds); }
CaseHub.Close(1); timings.Sort();
Console.WriteLine(new JsonObject { ["passed"] = passed, ["host"] = "Rhino/transport doubles; production CaseHub source", ["edit_p50_ms"] = timings[500], ["edit_p95_ms"] = timings[950], ["edit_max_ms"] = timings[^1] }.ToJsonString());

sealed class FakeRuntime
{
    int sequence;
    readonly Dictionary<string, string> jobs = new();
    public bool FailClose, FailQuery, BadTime, FailCreate;
    public Action? OnQuery;
    public string State = "ready";
    public JsonObject Call(JsonObject request)
    {
        string op = request["op"]!.GetValue<string>();
        if (op == "check") return new();
        if (op == "evaluate_submit") { string kind = request["kind"]!.GetValue<string>(); if (kind == "create") { if (FailCreate) throw new Exception("device unavailable"); State = "ready"; } string id = "job" + ++sequence; jobs[id] = kind == "create" ? kind : request["request"]!["field"]!.GetValue<string>(); return new() { ["job"] = id }; }
        if (op == "evaluate_control" || op == "close_async") { if (FailClose) throw new Exception("transport interrupted"); if (request["job"] != null) jobs.Remove(request["job"]!.GetValue<string>()); return new() { ["closed"] = true }; }
        if (op == "start") { State = "running"; return new() { ["state"] = State }; }
        if (op == "pause_async") { State = "paused"; return new(); }
        if (op == "status") return new() { ["state"] = State, ["steps"] = 0, ["error"] = null };
        if (op == "evaluate_poll") {
            string kind = jobs[request["job"]!.GetValue<string>()];
            if (kind == "create") return new() { ["state"] = "completed", ["result"] = new JsonObject { ["status"] = new JsonObject { ["session"] = "session" } } };
            OnQuery?.Invoke();
            if (FailQuery) return new() { ["state"] = "failed", ["error"] = "bad field" };
            var result = new JsonObject { ["session"] = "session", ["field"] = kind, ["steps"] = 7, ["physical_time"] = .7, ["shape"] = new JsonArray(2, 2), ["values"] = new JsonArray(1d, 2d, 3d, 4d), ["valid"] = new JsonArray(true, true, true, true), ["coordinates"] = new JsonArray(new JsonArray(0, 0, 0), new JsonArray(0, 1, 0), new JsonArray(1, 0, 0), new JsonArray(1, 1, 0)) };
            if (BadTime) result.Remove("physical_time");
            return new() { ["state"] = "completed", ["result"] = result };
        }
        throw new Exception("Unexpected operation " + op);
    }
}
