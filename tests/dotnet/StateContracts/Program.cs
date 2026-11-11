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
Test("undo restores the same live case and creates a redo snapshot", () => {
    var c=Fresh();var identity=c.Id;Edit(c,new(){["speed"]=1.25});var revision=c.Revision;var records=doc.UndoEvents.Count;
    doc.Undo();Assert(c.Id==identity && c.Speed==1 && c.Revision>revision && doc.UndoEvents.Count==records,"Undo failed to restore state or retain inverse action");
    doc.Undo();Assert(c.Speed==1.25 && c.Id==identity,"Redo snapshot lost original edit");
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
Test("startup block keeps both face layers when faces lie on lattice planes", () => {
    // 0.3 m cells, 1.2 m block at (3, 3, 2): faces at 2.4/3.6 m are nodes 8 and 12, which
    // floating products land a few ULP either side of. Exact count: 5 x 5 x 4 (z 1.4..2.6 m).
    var c = Fresh(); Edit(c, new() { ["cell"] = .3, ["width"] = 1.2 });
    Assert(CaseHub.BuildSpec(c)["solid"]!.AsArray().Count == 100, "Block lost a face layer");
    Edit(c, new() { ["cell"] = .4, ["width"] = .8 });
    Assert(CaseHub.BuildSpec(c)["solid"]!.AsArray().Count == 2 * 2 * 3, "Block lost a face layer at 0.4 m"); // x,y 2.6..3.4 m: nodes 7, 8; z 1.6..2.4 m: nodes 4..6
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
double Sum(IEnumerable<SliceCutCells.Piece> pieces,bool solid)=>pieces.Where(p=>p.Solid==solid).Sum(p=>Area(p.Polygon));
// SliceDisplay fans each piece from its first vertex: every fan triangle must keep the piece's orientation and the triangles must add up to the outline.
bool Fans(IEnumerable<SliceCutCells.Piece> pieces)=>pieces.All(p=>{var v=p.Polygon;double Cross(double[] a,double[] b,double[] c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
    var t=Enumerable.Range(1,v.Length-2).Select(i=>Cross(v[0].Grid,v[i].Grid,v[i+1].Grid)/2).ToArray();double sign=Math.Sign(t.Sum());return t.All(x=>x*sign>=-1e-12)&&Math.Abs(Math.Abs(t.Sum())-Area(v))<1e-12;});
Test("fractional wall clips a cell at its actual link position",()=>{
    var links=new JsonArray(new JsonArray(1,0,.25),new JsonArray(1,1,.25));
    var pieces=SliceCutCells.Polygons(plane,new[]{2d,4d,99d,99d},new[]{true,true,false,false},2,2,new[]{2,2,1},links,"pressure").ToArray();
    var p=pieces.Single(x=>!x.Solid).Polygon;
    Assert(Math.Abs(Area(p)-.25)<1e-12&&p.Max(v=>v.Grid[0])==.25,"Whole-cell erasure or half-cell approximation");
    Assert(p.All(v=>v.Value==2||v.Value==4),"Solid value leaked into colour reconstruction");
    Assert(Math.Abs(Sum(pieces,true)-.75)<1e-12&&pieces.Single(x=>x.Solid).Polygon.Min(v=>v.Grid[0])==.25,"Solid side of the wall left undrawn");
});
Test("stationary speed colours reach zero without mutating sampled values",()=>{
    double[] values={2d,4d,99d,99d};var links=new JsonArray(new JsonArray(1,0,.25),new JsonArray(1,1,.25));
    var p=SliceCutCells.Polygons(plane,values,new[]{true,true,false,false},2,2,new[]{2,2,1},links,"speed").Single(x=>!x.Solid).Polygon;
    Assert(p.Where(v=>v.Grid[0]==.25).All(v=>v.Value==0)&&values[2]==99&&values[0]==2,"Display changed samples or wall speed");
});
Test("missing wall data partitions mixed cells at the halfway lines",()=>{
    var pieces=SliceCutCells.Polygons(plane,new[]{2d,4d,99d,99d},new[]{true,true,false,false},2,2,new[]{2,2,1},null,"pressure").ToArray();
    Assert(pieces.Length==4&&Sum(pieces,false)==.5&&Sum(pieces,true)==.5,"Mixed cell dropped or wall moved from halfway");
    Assert(pieces.Where(x=>!x.Solid).All(x=>x.Polygon.Max(v=>v.Grid[0])==.5)&&pieces.Where(x=>x.Solid).All(x=>x.Polygon.Min(v=>v.Grid[0])==.5),"Quadrant crosses the halfway line");
    // Fluid-only midpoints: the wall-side vertices carry their fluid corner values, never 99.
    Assert(pieces.Where(x=>!x.Solid).SelectMany(x=>x.Polygon).All(v=>v.Value>=2&&v.Value<=4),"Solid value leaked into a quadrant");
    Assert(pieces.Where(x=>!x.Solid).SelectMany(x=>x.Polygon).Any(v=>v.Value==3&&v.Grid[1]==.5),"Fluid edge midpoint not interpolated");
    var full=SliceCutCells.Polygons(plane,new double[4],new[]{true,true,true,true},2,2,new[]{2,2,1},null,"pressure").Single();Assert(!full.Solid&&Area(full.Polygon)==1,"Fluid cell lost");
    var solid=SliceCutCells.Polygons(plane,new double[4],new bool[4],2,2,new[]{2,2,1},null,"pressure").Single();Assert(solid.Solid&&Area(solid.Polygon)==1,"Solid cell left undrawn");
});
Test("diagonal fluid corners stay separate",()=>{
    var links=new JsonArray(new JsonArray(1,0,.5),new JsonArray(3,0,.5),new JsonArray(2,3,.5),new JsonArray(4,3,.5));
    var p=SliceCutCells.Polygons(plane,new double[4],new[]{true,false,false,true},2,2,new[]{2,2,1},links,"pressure").ToArray();
    var fluid=p.Where(x=>!x.Solid).ToArray();
    Assert(fluid.Length==2&&fluid.All(x=>x.Polygon.Length==3)&&Math.Abs(Sum(p,false)-.25)<1e-12,"Bridged a solid corner");
    Assert(p.Single(x=>x.Solid).Polygon.Length==6&&Math.Abs(Sum(p,true)-.75)<1e-12,"Solid remainder not tiled");
    var voxel=SliceCutCells.Polygons(plane,new double[4],new[]{true,false,false,true},2,2,new[]{2,2,1},null,"pressure").ToArray();
    Assert(voxel.Count(x=>!x.Solid)==2&&Sum(voxel,false)==.5&&Sum(voxel,true)==.5,"Voxel diagonal corners not quadrants");
    // A missing crossing on the first corner's closing edge also falls back to quadrants.
    var partial=SliceCutCells.Polygons(plane,new double[4],new[]{true,false,false,true},2,2,new[]{2,2,1},new JsonArray(new JsonArray(1,0,.5),new JsonArray(2,3,.5),new JsonArray(4,3,.5)),"pressure").ToArray();
    Assert(partial.Length==4&&Sum(partial,false)==.5,"Partial diagonal crossings drawn or cell dropped");
});
Test("exact wall endpoints do not create duplicate polygon corners",()=>{
    var links=new JsonArray(new JsonArray(1,1,1d),new JsonArray(3,2,1d));
    var p=SliceCutCells.Polygons(plane,new double[4],new[]{true,true,true,false},2,2,new[]{2,2,1},links,"pressure").Single();
    Assert(!p.Solid&&p.Polygon.Length==4&&Area(p.Polygon)==1,"Degenerate endpoint clipping");
});
Test("slice partition tiles every cell and keeps every fluid corner",()=>{
    // 13x13 nodes, a 3x3 solid block: the halfway representation is 9, so 135 of 144 is fluid.
    int n=13;var points=new double[n*n][];var valid=new bool[n*n];var values=new double[n*n];
    for(int x=0;x<n;x++)for(int y=0;y<n;y++){points[x*n+y]=new[]{(double)x,y,0d};valid[x*n+y]=!(x>=5&&x<=7&&y>=5&&y<=7);values[x*n+y]=valid[x*n+y]?x:99;}
    JsonArray Links(bool diagonals){var links=new JsonArray();
        foreach(var (e,dir) in new[]{(new[]{1,0},1),(new[]{-1,0},2),(new[]{0,1},3),(new[]{0,-1},4),(new[]{1,1},15),(new[]{-1,-1},16),(new[]{1,-1},17),(new[]{-1,1},18)})
            for(int x=0;x<n;x++)for(int y=0;y<n;y++){int u=x+e[0],v=y+e[1];
                if(u>=0&&u<n&&v>=0&&v<n&&valid[x*n+y]&&!valid[u*n+v]&&(diagonals||dir<=4))links.Add(new JsonArray(dir,x*n+y,.5));}
        return links;}
    foreach(var links in new[]{null,Links(true)}){
        var pieces=SliceCutCells.Polygons(points,values,valid,n,n,new[]{n,n,1},links,"pressure").ToArray();
        Assert(Math.Abs(Sum(pieces,false)-135)<1e-9&&Math.Abs(Sum(pieces,true)-9)<1e-9,$"Halfway partition wrong: fluid {Sum(pieces,false)}, solid {Sum(pieces,true)}");
        Assert(pieces.Where(x=>!x.Solid).SelectMany(x=>x.Polygon).All(v=>v.Value!=99),"Solid sample coloured the fluid");
        Assert(Fans(pieces),"Fan triangulation leaves a piece");
    }
    // Off-centre diagonal crossings make the fluid piece concave (q = 0.25) or the solid piece concave (q = 0.75).
    foreach(double q in new[]{.25,.75}){
        var links=new JsonArray(new JsonArray(1,0,.5),new JsonArray(4,3,.5),new JsonArray(17,1,q));
        var cut=SliceCutCells.Polygons(plane,new double[4],new[]{true,true,false,true},2,2,new[]{2,2,1},links,"pressure").ToArray();
        Assert(cut.Length==2&&Fans(cut)&&Math.Abs(Sum(cut,false)+Sum(cut,true)-1)<1e-12,$"q {q}: concave piece mis-triangulated");
    }
    // Without the in-plane diagonal crossings, chords would cut each convex corner (+0.125 each).
    var chords=SliceCutCells.Polygons(points,values,valid,n,n,new[]{n,n,1},Links(false),"pressure").ToArray();
    Assert(Math.Abs(Sum(chords,false)-135.5)<1e-9&&Math.Abs(Sum(chords,false)+Sum(chords,true)-144)<1e-9,"Axis-only cut changed or lost area");
    // Every dual cell with a fluid corner keeps exactly count/4 fluid in the voxel partition.
    var rng=new Random(7);var mask=Enumerable.Range(0,n*n).Select(_=>rng.NextDouble()<.6).ToArray();
    var random=SliceCutCells.Polygons(points,values,mask,n,n,new[]{n,n,1},null,"pressure").ToArray();
    double expected=0;for(int x=0;x<n-1;x++)for(int y=0;y<n-1;y++){int a=x*n+y;expected+=new[]{a,a+n,a+n+1,a+1}.Count(i=>mask[i])/4d;}
    Assert(Math.Abs(Sum(random,false)-expected)<1e-9&&Math.Abs(Sum(random,false)+Sum(random,true)-144)<1e-9,"Random mask dropped or overlapped cells");
});
Test("curved sphere slices tile the plane at two resolutions",()=>{
    // Analytic circle (sphere cut through its centre) with exact link fractions; off-grid centre.
    foreach(var (n,r) in new[]{(13,3.2),(25,6.4)}){
        double cx=(n-1)/2d+.3,cy=(n-1)/2d+.1;bool Fluid(int x,int y)=>(x-cx)*(x-cx)+(y-cy)*(y-cy)>r*r;
        var points=new double[n*n][];var valid=new bool[n*n];var values=new double[n*n];var links=new JsonArray();
        for(int x=0;x<n;x++)for(int y=0;y<n;y++){points[x*n+y]=new[]{(double)x,y,0d};valid[x*n+y]=Fluid(x,y);values[x*n+y]=1;}
        foreach(var (e,dir) in new[]{(new[]{1,0},1),(new[]{-1,0},2),(new[]{0,1},3),(new[]{0,-1},4),(new[]{1,1},15),(new[]{-1,-1},16),(new[]{1,-1},17),(new[]{-1,1},18)})
            for(int x=0;x<n;x++)for(int y=0;y<n;y++){int u=x+e[0],v=y+e[1];if(u<0||u>=n||v<0||v>=n||!Fluid(x,y)||Fluid(u,v))continue;
                // Smallest t in (0,1] where |p + t e - c| = r.
                double px=x-cx,py=y-cy,a=e[0]*e[0]+e[1]*e[1],b=2*(px*e[0]+py*e[1]),c=px*px+py*py-r*r,t=(-b-Math.Sqrt(b*b-4*a*c))/(2*a);
                links.Add(new JsonArray(dir,x*n+y,t));}
        var pieces=SliceCutCells.Polygons(points,values,valid,n,n,new[]{n,n,1},links,"pressure").ToArray();
        double total=(n-1)*(n-1),fluid=Sum(pieces,false),black=Sum(pieces,true);
        Assert(Math.Abs(fluid+black-total)<1e-9,$"n {n}: pieces cover {fluid+black} of {total}");
        Assert(Math.Abs(black-Math.PI*r*r)<.02*Math.PI*r*r,$"n {n}: black {black} far from circle {Math.PI*r*r}");
        Assert(pieces.Where(x=>!x.Solid).SelectMany(x=>x.Polygon).All(v=>v.Value==1),"Wall colour invented");
        Assert(Fans(pieces),$"n {n}: fan triangulation leaves a piece");
    }
});
Test("slice display draws solid pieces black and keeps zero samples coloured",()=>{
    var data=JsonNode.Parse("{\"coordinates\":[[0.0,0.0,0.0],[0.0,1.0,0.0],[1.0,0.0,0.0],[1.0,1.0,0.0]],\"values\":[0.0,0.0,5.0,5.0],\"valid\":[true,true,false,false],\"shape\":[2,2]}")!.AsObject();
    var colour=System.Drawing.Color.FromArgb(10,20,30);
    var mesh=SliceDisplay.Build(data,new JsonObject{["shape"]=new JsonArray(2,2,1)},"speed",p=>new Rhino.Geometry.Point3d(p[0],p[1],p[2]),v=>v==0?colour:System.Drawing.Color.White);
    Assert(mesh.Faces.Count==8&&mesh.VertexColors.Count(c=>c.ToArgb()==System.Drawing.Color.Black.ToArgb())==6&&mesh.VertexColors.Count(c=>c.ToArgb()==colour.ToArgb())==6,"Solid colour or zero-speed fluid colour wrong");
    Assert(mesh.VertexColors.All(c=>c.ToArgb()!=System.Drawing.Color.White.ToArgb()),"Solid sample value coloured the display");
});
var benchmarkCase = Fresh();
for (int i = 0; i < 1000; i++) { var sw = Stopwatch.StartNew(); CaseHub.Edit(1, new() { ["target"] = 200 + i % 2 }, benchmarkCase.Version, "panel", false); timings.Add(sw.Elapsed.TotalMilliseconds); }
CaseHub.Close(1); Test("binding and schema guards reject invalid commands without mutation", () => {
    var c=Fresh(); var owner=Guid.NewGuid();
    Reject(()=>CaseHub.Get(999999)); Reject(()=>CaseHub.Bind(c,Guid.Empty,Array.Empty<string>()));
    Reject(()=>CaseHub.Bind(c,owner,new[]{"unknown"}));
    var lease=CaseHub.Bind(c,owner,new[]{"speed"});
    Reject(()=>CaseHub.Bind(c,Guid.NewGuid(),Array.Empty<string>()));
    Reject(()=>CaseHub.ConfigureBinding(c,owner,Guid.NewGuid(),new Dictionary<string,int>()));
    Reject(()=>CaseHub.ConfigureBinding(c,owner,lease,new Dictionary<string,int>{{"speed",13}}));
    Reject(()=>CaseHub.Edit(1,new(),c.Version,"gh"));Reject(()=>Edit(c,new(){["unknown"]=1}));
    foreach(var patch in new JsonObject[]{new(){["schema"]=99},new(){["speed"]=-1d},new(){["target"]=0},new(){["device"]="unknown"},new(){["field"]="unknown"}}) {
        var settings=c.Settings();foreach(var p in patch)settings[p.Key]=p.Value?.DeepClone();Reject(()=>CaseHub.Validate(settings));
    }
    Assert(c.Version==0 && c.Speed==1,"Rejected command mutated state");
    CaseHub.Close(1);Reject(()=>CaseHub.Bind(c,owner,Array.Empty<string>()));
});
Test("run resumes sessions and does not duplicate pending preparation", () => {
    var c=Fresh();CaseHub.Run(1);var job=c.Job;CaseHub.Run(1);Assert(c.Job==job && c.StartWhenReady,"Pending job replaced");
    Tick();CaseHub.Pause(1);Assert(c.State=="pausing"&&fake.State=="paused","Pause not dispatched");
    CaseHub.Run(1);Assert(c.State=="running" && c.Job==job,"Resume recreated session");
    var transport=CaseHub.Transport;
    try {CaseHub.Transport=request=>request["op"]!.GetValue<string>()=="pause_async"?throw new Exception("pause failed"):transport(request);
        CaseHub.Pause(1);Assert(c.State=="failed"&&c.Fault?.Area=="control"&&c.Session==null,"Pause failure retained ownership");
    } finally {CaseHub.Transport=transport;}
});
Test("preparation pending cancelled faulted and unavailable states remain explicit", () => {
    var c=Fresh();var pending=new TaskCompletionSource<JsonObject>();c.Preparation=pending.Task;
    CaseHub.Run(1);Tick();Assert(c.Preparation==pending.Task&&c.StartWhenReady,"Pending preparation lost");
    pending.SetCanceled();Tick();Assert(c.State=="cancelled"&&c.Preparation==null,"Cancelled preparation published");
    c.Preparation=Task.FromException<JsonObject>(new Exception("geometry failed"));Tick();
    Assert(c.State=="failed"&&c.Error=="geometry failed","Geometry fault hidden");
    var selected=NativeSettings.DefaultSetup();selected["mode"]="selected";Edit(c,new(){["setup"]=selected});
    var prepare=CaseHub.PrepareGeometry;try {CaseHub.PrepareGeometry=null;CaseHub.Run(1);Assert(c.State=="failed"&&c.Error.Contains("unavailable"),"Unavailable service not reported");}finally{CaseHub.PrepareGeometry=prepare;}
});
Test("runtime pending and failed jobs release resources and report status errors", () => {
    var transport=CaseHub.Transport;var c=Fresh();CaseHub.Run(1);string state="running";
    try {CaseHub.Transport=request=>request["op"]!.GetValue<string>()=="evaluate_poll"?new(){["state"]=state,["error"]="creation failed"}:transport(request);
        Tick();Assert(c.State=="preparing"&&c.Session==null,"Pending job published");state="failed";Tick();Assert(c.State=="failed"&&c.Error=="creation failed"&&c.Job==null,"Failed job retained");
    } finally {CaseHub.Transport=transport;}
    c=Fresh();Start(c);
    try {CaseHub.Transport=request=>request["op"]!.GetValue<string>()=="status"?new(){["steps"]=0,["state"]="failed",["error"]="solver failed"}:transport(request);
        Tick();Assert(c.State=="failed"&&c.Error=="solver failed"&&c.Session==null,"Solver error hidden");
    } finally {CaseHub.Transport=transport;}
});
Test("malformed field snapshots preserve the last good result", () => {
    foreach(var patch in new JsonObject[]{new(){["shape"]=new JsonArray(3,2)},new(){["coordinates"]=new JsonArray(new JsonArray(0,0),new JsonArray(0,1,0),new JsonArray(1,0,0),new JsonArray(1,1,0))},new(){["session"]="wrong"},new(){["steps"]=-1},new(){["physical_time"]=-.1}}) {
        var c=Fresh();Start(c);Field(c);var previous=c.Slice!.ToJsonString();var transport=CaseHub.Transport;
        try {CaseHub.Transport=request=>{var response=transport(request);if(response["result"] is JsonObject result && result["values"]!=null)foreach(var p in patch)result[p.Key]=p.Value?.DeepClone();return response;};
            Field(c);Assert(c.ViewFailures>0&&c.ViewError.Length>0&&c.Slice!.ToJsonString()==previous&&c.Session!=null,"Bad field replaced result or stopped solver");
        } finally {CaseHub.Transport=transport;}
    }
});
Test("polling tolerates reentrancy and closes missing documents", () => {
    var c=Fresh();Start(c);var transport=CaseHub.Transport;
    try {CaseHub.Transport=request=>{CaseHub.Tick();return transport(request);};Tick();Assert(c.Session!=null,"Reentrant poll damaged session");}finally{CaseHub.Transport=transport;}
    var temporary=new RhinoDoc(909);var orphan=CaseHub.Get(909);RhinoDoc.Remove(909);Tick();Assert(CaseHub.Find(909)==null,"Closed document retained case");
    CaseHub.GeometryChanged(909,Guid.NewGuid());CaseHub.GeometryChanged(1,Guid.NewGuid());
});

Test("nested commands are rejected while polling skips busy ownership",()=>{
    var c=Fresh();var transport=CaseHub.Transport;bool checkedBusy=false;
    try{CaseHub.Transport=request=>{if(request["op"]!.GetValue<string>()=="check"){Reject(()=>CaseHub.Pause(1));CaseHub.Tick();checkedBusy=true;}return transport(request);};CaseHub.Run(1);Assert(checkedBusy&&c.State=="preparing","Reentrant command corrupted preparation");}finally{CaseHub.Transport=transport;}
    Tick();c.Job=null;CaseHub.Cancel(1);Assert(c.Session==null&&CaseHub.PendingCleanupCount==0,"Session-only ownership leaked");
    var owner=Guid.NewGuid();var lease=CaseHub.Bind(c,owner,Array.Empty<string>());CaseHub.ConfigureBinding(c,owner,lease,new Dictionary<string,int>{{"speed",2}});Edit(c,new(){["target"]=201});Assert(c.Target==201,"Representable linked precision rejected");
    c.Cell=1.7;c.Width=.01;CaseHub.Run(1);Assert(c.State=="failed"&&c.Error.Contains("unresolved"),"Empty voxel block accepted");
});
Test("stale field identity and unit-change close callbacks cannot publish",()=>{
    var c=Fresh();Start(c);Field(c);var old=c.Result;
    fake.OnQuery=()=>c.Generation++;
    try{Field(c);Assert(c.Result==old,"Stale query published");}finally{fake.OnQuery=null;}
    Action<CaseState,string> close=(state,reason)=>{if(state==c&&reason=="units")CaseHub.Close(1);};
    CaseHub.Changed+=close;try{doc.ModelUnitSystem=UnitSystem.Millimeters;Tick();Assert(CaseHub.Find(1)==null,"Unit callback close ignored");}finally{CaseHub.Changed-=close;doc.ModelUnitSystem=UnitSystem.Meters;}
});
Test("cut cells replace unresolved crossings with the halfway partition and deduplicate a shared solid corner",()=>{
    var links=new JsonArray(new JsonArray(1,0,.5));
    foreach(var spec in new[]{(plane,new[]{2,2}), (new[]{new[]{.1,0d,0d},plane[1],plane[2],plane[3]},new[]{2,2,1}), (new[]{plane[0],plane[1],new[]{2d,0d,0d},plane[3]},new[]{2,2,1})}){
        var pieces=SliceCutCells.Polygons(spec.Item1,new double[4],new[]{true,true,false,false},2,2,spec.Item2,links,"speed").ToArray();
        Assert(pieces.Length==4&&pieces.Count(x=>!x.Solid)==2,"Unresolved crossing drawn or cell dropped");}
    var invalid=SliceCutCells.Polygons(plane,new double[4],new[]{true,true,false,false},2,2,new[]{2,2,1},new JsonArray(new JsonArray(1,0,0d)),"speed").ToArray();
    Assert(invalid.Length==4&&Sum(invalid,false)==.5,"Invalid fraction drawn");
    var corners=new JsonArray(new JsonArray(2,2,1d),new JsonArray(4,1,1d));
    var polygon=SliceCutCells.Polygons(plane,new double[4],new[]{false,true,true,true},2,2,new[]{2,2,1},corners,"speed").Single();
    Assert(!polygon.Solid&&polygon.Polygon.Length==4&&Area(polygon.Polygon)==1,"Coincident solid corner duplicated or area lost");
});

QualityContracts.Run(Test, Assert);
ComponentContracts.Run(Test, Assert);
timings.Sort();
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
