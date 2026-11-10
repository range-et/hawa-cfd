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

Test("GH-only cleanup survives a lost acknowledgement and retries on host idle", () => {
    var transport = CaseHub.Transport; bool fail = true; int calls = 0; bool resource = true;
    try {
        CaseHub.Transport = request => { calls++; resource = false; if(fail) throw new Exception("Reply lost after close"); return new JsonObject(); };
        CaseHub.ReleaseSession("gh-session"); CaseHub.ReleaseSession("gh-session");
        Assert(CaseHub.PendingCleanupCount==1 && RhinoApp.IdleSubscribers==1 && calls==1 && !resource,"Transfer/deduplication failed");
        fail=false; RhinoApp.RaiseIdle();
        Assert(CaseHub.PendingCleanupCount==0 && calls==2 && RhinoApp.IdleSubscribers==0,"GH-only idle retry leaked ownership/subscription");
    } finally { CaseHub.Transport=transport; CaseHub.RetryCleanup(); }
});
Test("cleanup bounds retry batches and persistent failures cannot starve other owners", () => {
    var transport=CaseHub.Transport; bool failAll=true, recover=false; int calls=0;
    try {
        CaseHub.Transport = request => { calls++; int n=int.Parse(request["job"]!.GetValue<string>()); if(failAll || (!recover && n<8))throw new Exception("Bridge unavailable");return new JsonObject();};
        for(int i=0;i<20;i++)CaseHub.ReleaseJob(i.ToString());
        Assert(CaseHub.PendingCleanupCount==20,"Lost pending jobs");failAll=false;calls=0;
        CaseHub.RetryCleanup();Assert(calls==8 && CaseHub.PendingCleanupCount==20,"Retry batch not bounded");
        CaseHub.RetryCleanup();Assert(calls==16 && CaseHub.PendingCleanupCount==12,"Failed head starved healthy owners");
        recover=true;for(int i=0;i<3;i++)CaseHub.RetryCleanup();
        Assert(CaseHub.PendingCleanupCount==0 && RhinoApp.IdleSubscribers==0,"Recovered batch retained cleanup");
    } finally { CaseHub.Transport=transport; CaseHub.RetryCleanup(); }
});
Test("cleanup bridge reentrancy preserves nested and duplicate ownership", () => {
    var transport=CaseHub.Transport;bool nested=false;int depth=0,maxDepth=0;
    try {
        CaseHub.Transport=request=>{depth++;maxDepth=Math.Max(depth,maxDepth);try{
            if(!nested){nested=true;CaseHub.ReleaseJob("parent");CaseHub.ReleaseJob("child");CaseHub.RetryCleanup();throw new Exception("Interrupted parent close");}
            return new JsonObject();
        }finally{depth--;}};
        CaseHub.ReleaseJob("parent");Assert(CaseHub.PendingCleanupCount==2 && maxDepth==1,"Reentrant cleanup lost or recursively closed jobs");
        CaseHub.RetryCleanup();Assert(CaseHub.PendingCleanupCount==0 && maxDepth==1,"Nested cleanup did not recover");
    } finally { CaseHub.Transport=transport;CaseHub.RetryCleanup(); }
});
Test("read-only outward state and detached JSON", () => {
    var c = Fresh(); Assert(typeof(CaseState).GetProperty("Speed")!.SetMethod!.IsAssembly, "Public settings setter");
    Assert(typeof(CaseState).GetField("Session") == null, "Public mutable handle");
    var settings = c.Settings(); settings["speed"] = 2; Assert(c.Speed == 1, "Settings alias");
    Start(c); Field(c); var result = c.Slice!; result["values"]![0] = 900; Assert(c.Slice!["values"]![0]!.GetValue<double>() != 900, "Field alias");
});
Test("public state views are detached and retain result identity", () => {
    var c = Fresh();
    Assert(c.ResultRevision == -1 && !c.HasInterpolatedWalls && c.Spec == null && c.Status == null && c.ResultSpec == null, "Empty state invented results");
    c.SpecData = new JsonObject { ["shape"] = new JsonArray(8, 8, 8) };
    c.StatusData = new JsonObject { ["steps"] = 7 };
    c.ResultSpecData = new JsonObject { ["wall_links"] = new JsonArray(new JsonArray(1, 2, .5)) };
    c.Result = new ResultStamp(c.Id, 4, 5, "recorded-session", "speed", 7, .25);
    c.DrivenKeys.Add("speed");
    var spec = c.Spec!; var status = c.Status!; var result = c.ResultSpec!; var driven = c.Driven;
    spec["shape"]![0] = 99; status["steps"] = 99; result["wall_links"]!.AsArray().Clear();
    c.DrivenKeys.Add("cell");
    Assert(c.Spec!["shape"]![0]!.GetValue<int>() == 8 && c.Status!["steps"]!.GetValue<int>() == 7 && c.HasInterpolatedWalls, "Public JSON aliases live state");
    Assert(driven.Count == 1 && c.Driven.Count == 2 && c.ResultRevision == 4, "Detached ownership or result revision incorrect");
    Assert(c.Value("speed") == c.Speed && c.Value("cell") == c.Cell && c.Value("width") == c.Width, "Wrong parameter lookup");
    Reject(() => c.Value("unknown"));
    var description = c.Describe();
    Assert(description["result_steps"]!.GetValue<int>() == 7 && description["result_time_seconds"]!.GetValue<double>() == .25 && description["outdated"]!.GetValue<bool>(), "Result identity lost in description");
    description["settings"]!["speed"] = 99;
    Assert(c.Speed == 1, "Description aliases settings");
});
Test("cancel and reset release ownership while retaining physical settings", () => {
    var c = Fresh(); Edit(c, new() { ["speed"] = 1.2 }); Start(c); Field(c);
    var setup = c.Settings().ToJsonString();
    CaseHub.Cancel(1);
    Assert(c.State == "cancelled" && c.Session == null && c.Job == null && c.Query == null, "Cancel retained owned work");
    c.Error = "old"; c.ViewError = "old view"; c.Fault = new CaseFault("test", "old", true);
    CaseHub.Reset(1);
    Assert(c.State == "idle" && c.Steps == 0 && c.Spec == null && c.Slice == null && c.ResultRevision == -1 && c.RunRevision == -1, "Reset retained stale result");
    Assert(c.Error == "" && c.ViewError == "" && c.Fault == null && c.Settings().ToJsonString() == setup, "Reset changed settings or retained failure");
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
Test("schema 1 settings migrate to explicit physical setup and view", () => {
    var c = Fresh(); var legacy = c.Settings(); legacy["schema"] = 1; legacy.Remove("setup"); legacy.Remove("view");
    CaseHub.Restore(1,legacy.ToJsonString()); Assert(!c.SelectedGeometry && c.Settings()["schema"]!.GetValue<int>() == 2 && c.Setup["viscosity"]!.GetValue<double>() == .1, "Migration failed");
});
Test("native setup validates cell budget, periodic pairs and finite domain", () => {
    var c = Fresh(); var setup = c.Setup; setup["mode"] = "selected";
    Edit(c,new(){["setup"]=setup,["cell"]=.1}); Assert(c.SelectedGeometry,"Selection mode missing");
    Reject(()=>Edit(c,new(){["cell"]=.00001}));
    var bad = c.Setup; bad["boundaries"]![2]="wall"; Reject(()=>Edit(c,new(){["setup"]=bad}));
    Assert(c.Setup["boundaries"]![2]!.GetValue<string>() == "periodic","Rejected patch mutated setup");
});
Test("curved walls persist and cannot silently apply to the block preset", () => {
    var c=Fresh();var setup=c.Setup;setup["curved_walls"]=true;
    Reject(()=>Edit(c,new(){["setup"]=setup.DeepClone()}));
    setup["mode"]="selected";Edit(c,new(){["setup"]=setup});
    CaseHub.Restore(1,CaseHub.Save(1));Assert(c.Setup["curved_walls"]!.GetValue<bool>(),"Wall setting lost");
    var old=c.Settings();old["setup"]!.AsObject().Remove("curved_walls");
    CaseHub.Restore(1,old.ToJsonString());Assert(!(c.Setup["curved_walls"]?.GetValue<bool>()??false),"Old archive changed wall mode");
});
Test("palette edits recolor without restarting or replacing field capture", () => {
    var c = Fresh(); Start(c); Field(c); var stamp=c.Result; var session=c.Session; long rv=c.ResultVersion;
    var view=c.View;view["palette"]="spectrum";Edit(c,new(){["view"]=view});
    Assert(c.Session==session && c.Result==stamp && c.ResultVersion>rv && !c.Outdated,"Display changed physics");
    view=c.View;view["axis"]=0;Edit(c,new(){["view"]=view}); Assert(c.Session==session && c.Result==null,"Slice edit retained wrong plane or stopped solver");
});
Test("geometry preparation is cancellable and late completion cannot publish", () => {
    var c=Fresh();var setup=c.Setup;setup["mode"]="selected";Edit(c,new(){["setup"]=setup});
    var pending=new TaskCompletionSource<JsonObject>(); CancellationToken token=default;
    CaseHub.PrepareGeometry=(state,t)=>{token=t;return pending.Task;};
    CaseHub.Run(1); Assert(c.State=="voxelizing","Preparation not visible");CaseHub.Cancel(1);
    pending.SetResult(CaseHub.BuildSpec(c));Tick();Assert(token.IsCancellationRequested && c.Session==null && c.State=="cancelled","Late preparation escaped cancellation");CaseHub.PrepareGeometry=null;
});
Test("pause during geometry preparation suppresses automatic solver start", () => {
    var c=Fresh();var setup=c.Setup;setup["mode"]="selected";Edit(c,new(){["setup"]=setup});
    var pending=new TaskCompletionSource<JsonObject>();CaseHub.PrepareGeometry=(_,_)=>pending.Task;
    CaseHub.Run(1);CaseHub.Pause(1);Assert(c.State=="pausing","Preparation pause misreported");
    pending.SetResult(CaseHub.BuildSpec(c));Tick();Assert(c.State=="paused" && fake.State=="ready","Preparation started paused run");CaseHub.PrepareGeometry=null;
});
Test("geometry edits invalidate runtime even during a notification", () => {
    var c=Fresh();var setup=c.Setup;var id=Guid.NewGuid();setup["mode"]="selected";setup["objects"]=new JsonArray(id.ToString());Edit(c,new(){["setup"]=setup});
    long revision=c.Revision;Action<CaseState,string> edit=(state,origin)=>{if(origin=="panel")CaseHub.GeometryChanged(1,id);};
    CaseHub.Changed+=edit;try{Edit(c,new(){["target"]=201});}finally{CaseHub.Changed-=edit;}
    Assert(c.Revision==revision+1 && c.GeometryError.Length>0,"Geometry invalidation was lost");
});
Test("unit change invalidates referenced geometry but preserves physical setup", () => {
    var c=Fresh();var setup=c.Setup;setup["mode"]="selected";setup["objects"]=new JsonArray(Guid.NewGuid().ToString());Edit(c,new(){["setup"]=setup});
    var before=c.Setup.ToJsonString();long revision=c.Revision;doc.ModelUnitSystem=UnitSystem.Millimeters;Tick();
    Assert(c.Revision==revision+1 && c.Setup.ToJsonString()==before && c.GeometryError.Length>0,"Units silently reinterpreted geometry");doc.ModelUnitSystem=UnitSystem.Meters;
});
double[][] plane={new[]{0d,0d,0d},new[]{0d,1d,0d},new[]{1d,0d,0d},new[]{1d,1d,0d}};
double Area(SliceCutCells.Vertex[] polygon){double area=0;for(int i=0;i<polygon.Length;i++){var a=polygon[i].Grid;var b=polygon[(i+1)%polygon.Length].Grid;area+=a[0]*b[1]-a[1]*b[0];}return Math.Abs(area)/2;}
Test("fractional wall clips a cell at its actual link position",()=>{
    var links=new JsonArray(new JsonArray(1,0,.25),new JsonArray(1,1,.25));
    var p=SliceCutCells.Polygons(plane,new[]{2d,4d,99d,99d},new[]{true,true,false,false},2,2,new[]{2,2,1},links,"pressure").Single();
    Assert(Math.Abs(Area(p)-.25)<1e-12&&p.Max(v=>v.Grid[0])==.25,"Whole-cell erasure or half-cell approximation");
    Assert(p.All(v=>v.Value==2||v.Value==4),"Solid value leaked into colour reconstruction");
});
Test("stationary speed colours reach zero without mutating sampled values",()=>{
    double[] values={2d,4d,99d,99d};var links=new JsonArray(new JsonArray(1,0,.25),new JsonArray(1,1,.25));
    var p=SliceCutCells.Polygons(plane,values,new[]{true,true,false,false},2,2,new[]{2,2,1},links,"speed").Single();
    Assert(p.Where(v=>v.Grid[0]==.25).All(v=>v.Value==0)&&values[2]==99&&values[0]==2,"Display changed samples or wall speed");
});
Test("missing wall data preserves conservative masking",()=>{
    Assert(!SliceCutCells.Polygons(plane,new double[4],new[]{true,true,false,false},2,2,new[]{2,2,1},null,"pressure").Any(),"Invented boundary");
    var full=SliceCutCells.Polygons(plane,new double[4],new[]{true,true,true,true},2,2,new[]{2,2,1},null,"pressure").Single();Assert(Area(full)==1,"Fluid cell lost");
    Assert(!SliceCutCells.Polygons(plane,new double[4],new bool[4],2,2,new[]{2,2,1},null,"pressure").Any(),"Solid cell drawn");
});
Test("diagonal fluid corners stay separate",()=>{
    var links=new JsonArray(new JsonArray(1,0,.5),new JsonArray(3,0,.5),new JsonArray(2,3,.5),new JsonArray(4,3,.5));
    var p=SliceCutCells.Polygons(plane,new double[4],new[]{true,false,false,true},2,2,new[]{2,2,1},links,"pressure").ToArray();
    Assert(p.Length==2&&p.All(v=>v.Length==3)&&Math.Abs(p.Sum(Area)-.25)<1e-12,"Bridged a solid corner");
});
Test("exact wall endpoints do not create duplicate polygon corners",()=>{
    var links=new JsonArray(new JsonArray(1,1,1d),new JsonArray(3,2,1d));
    var p=SliceCutCells.Polygons(plane,new double[4],new[]{true,true,true,false},2,2,new[]{2,2,1},links,"pressure").Single();
    Assert(p.Length==4&&Area(p)==1,"Degenerate endpoint clipping");
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
