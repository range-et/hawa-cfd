using System.Drawing;
using System.Text.Json.Nodes;
using Hawa.Shared;
using Hawa.Grasshopper;
using Rhino;
using Rhino.Geometry;
using Grasshopper.Kernel;
using Eto.Forms;

static class QualityContracts
{
    public static void Run(Action<string,Action> test, Action<bool,string> assert)
    {
        void Reject(Action action) { bool rejected=false;try { action(); } catch(ArgumentException) { rejected=true; }assert(rejected,"Invalid settings accepted"); }
        test("settings shape enforces axis and product budgets", () => {
            var setup=NativeSettings.DefaultSetup();
            assert(NativeSettings.Shape(setup,.5).SequenceEqual(new[]{17,13,9}),"Shape rounding changed");
            setup["size"]=new JsonArray(1d,1d,1d);
            Reject(()=>NativeSettings.Shape(setup,1));
            setup["size"]=new JsonArray(100d,100d,100d);
            Reject(()=>NativeSettings.Shape(setup,.01));
            Reject(()=>NativeSettings.Shape(setup,0));
            assert(NativeSettings.Parameters(true).Single(p=>p.Key=="cell").Minimum==.00001,"Selected geometry precision lost");
        });
        test("settings validators reject malformed geometry and preview contracts", () => {
            var setup=NativeSettings.DefaultSetup();var view=NativeSettings.DefaultView();
            NativeSettings.Validate(setup,view,.5);
            foreach(var patch in new JsonObject[] {
                new(){["boundaries"]=new JsonArray("inlet")},new(){["boundaries"]=new JsonArray("wall","outlet","wall","wall","wall","wall")},new(){["mode"]="unknown"},new(){["origin"]=new JsonArray(0d,0d)},
                new(){["size"]=new JsonArray(1d,-1d,1d)},new(){["mach"] = .21},
                new(){["viscosity"]=0d},new(){["collision"]="unknown"},new(){["curved_walls"]=true},
                new(){["boundaries"]=new JsonArray("inlet","outlet","periodic","wall","wall","slip")},
                new(){["objects"]=new JsonArray(Guid.Empty.ToString())},
                new(){["objects"]=new JsonArray("bad-id")}
            }) {
                var bad=setup.DeepClone().AsObject();foreach(var pair in patch)bad[pair.Key]=pair.Value?.DeepClone();
                Reject(()=>NativeSettings.Validate(bad,view,.5));
            }
            var id=Guid.NewGuid().ToString();setup["objects"]=new JsonArray(id,id);
            Reject(()=>NativeSettings.Validate(setup,view,.5));setup["objects"]=new JsonArray(id);
            setup["mode"]="selected";NativeSettings.Validate(setup,view,.5);
            foreach(var patch in new JsonObject[] {new(){["axis"]=3},new(){["position"]=-.1},new(){["palette"]="unknown"},new(){["min"]=2d}}) {
                var bad=view.DeepClone().AsObject();foreach(var pair in patch)bad[pair.Key]=pair.Value?.DeepClone();
                Reject(()=>NativeSettings.Validate(setup,bad,.5));
            }
        });
        test("preview sample budget rejects an oversized slice",()=>{
            var setup=NativeSettings.DefaultSetup();setup["mode"]="selected";setup["size"]=new JsonArray(3d,299d,299d);
            var view=NativeSettings.DefaultView();view["axis"]=0;
            Reject(()=>NativeSettings.Validate(setup,view,1));
        });
        test("JSON compatibility clone is structurally equal and independent", () => {
            JsonNode source=JsonNode.Parse("{\"values\":[1,{\"x\":2}]}")!;
            var clone=JsonCompatibility.DeepClone(source);
            assert(clone.ToJsonString()==source.ToJsonString(),"Clone changed content");
            clone["values"]![1]!["x"]=9;
            assert(source["values"]![1]!["x"]!.GetValue<int>()==2,"Clone shares child nodes");
        });
        test("geometry units convert detached coordinates and bounds", () => {
            var document=new RhinoDoc(401){ModelUnitSystem=UnitSystem.Millimeters};
            var c=new CaseState{Document=401,Cell=.5};
            assert(CaseGeometry.SpecInModelUnits(c)==null,"Invented absent spec");
            c.SpecData=new JsonObject{["dx"]=.5,["origin_m"]=new JsonArray(1d,2d,3d)};
            var model=CaseGeometry.SpecInModelUnits(c)!;
            assert(model["spacing"]!.GetValue<double>()==500 && model["origin"]![1]!.GetValue<double>()==2000,"Wrong unit scale");
            model["origin_m"]![0]=99d;assert(c.SpecData["origin_m"]![0]!.GetValue<double>()==1,"Converted spec aliased source");
            var bounds=CaseGeometry.Bounds(c);assert(bounds.Min==new Point3d(0,0,0) && bounds.Max==new Point3d(8000,6000,4000),"Default bound extent wrong");
            c.SetupData["mode"]="selected";c.SetupData["origin"]=new JsonArray(1d,2d,3d);c.SetupData["size"]=new JsonArray(2d,3d,4d);
            assert(CaseGeometry.GridShape(c).SequenceEqual(new[]{5,7,9}),"Selected grid extent wrong");
            bounds=CaseGeometry.Bounds(c);assert(bounds.Min==new Point3d(1000,2000,3000)&&bounds.Max==new Point3d(3000,5000,7000),"Selected bound extent wrong");
            c.ResultSpecData=new JsonObject{["dx"]=1d,["shape"]=new JsonArray(2,3,4),["origin_m"]=new JsonArray(-1d,0d,0d)};
            bounds=CaseGeometry.Bounds(c,true);assert(bounds.Min.X==-1000&&bounds.Max==new Point3d(0,2000,3000),"Result bounds used current setup");
        });
        test("geometry ranges use valid recorded data and preserve manual limits", () => {
            var c=new CaseState{Document=401};assert(CaseGeometry.Range(c)==(0d,1d),"Absent field range wrong");
            c.SliceData=JsonNode.Parse("{\"values\":[2.0,4.0,999.0],\"valid\":[true,true,false]}")!.AsObject();
            assert(CaseGeometry.Range(c)==(2d,4d),"Invalid sample leaked into range");
            c.Result=new ResultStamp(c.Id,0,0,"s","speed",1);
            c.ResultSpecData=new JsonObject{["wall_links"]=new JsonArray(new JsonArray(1,0,.5))};
            assert(CaseGeometry.Range(c)==(0d,4d),"Stationary wall speed omitted");
            c.ViewData["auto_range"]=false;c.ViewData["min"]=-2d;c.ViewData["max"]=3d;
            assert(CaseGeometry.Range(c)==(-2d,3d),"Manual range ignored");
            assert(CaseGeometry.FieldUnits("pressure")=="Pa"&&CaseGeometry.FieldUnits("density")=="kg/m³"&&CaseGeometry.FieldUnits("speed")=="m/s","Field units wrong");
        });
        test("palette endpoints clamp and interpolate without changing channels", () => {
            assert(CaseGeometry.ColorAt(-1,"blue-green").ToArgb()==Color.FromArgb(8,48,107).ToArgb(),"Low clamp wrong");
            assert(CaseGeometry.ColorAt(2,"blue-green").ToArgb()==Color.FromArgb(150,235,140).ToArgb(),"High clamp wrong");
            assert(CaseGeometry.ColorAt(.5,"diverging").ToArgb()==Color.White.ToArgb(),"Diverging midpoint wrong");
            assert(CaseGeometry.ColorAt(1,"spectrum").ToArgb()==Color.Red.ToArgb(),"Spectrum endpoint wrong");
        });
        test("display mesh preserves grid units topology and sample colours", () => {
            var c=new CaseState{Document=401};assert(CaseGeometry.ResultMesh(c)==null,"Absent result created mesh");
            c.SliceData=JsonNode.Parse("{\"coordinates\":[[0.0,0.0,0.0],[0.0,1.0,0.0],[1.0,0.0,0.0],[1.0,1.0,0.0]],\"values\":[1.0,1.0,1.0,1.0],\"valid\":[true,true,true,true],\"shape\":[2,2]}")!.AsObject();
            c.ResultSpecData=new JsonObject{["dx"]=.5,["shape"]=new JsonArray(2,2,1),["origin_m"]=new JsonArray(1d,2d,3d)};
            var mesh=CaseGeometry.ResultMesh(c)!;
            assert(mesh.Vertices.Count==4 && mesh.Faces.Count==2 && mesh.VertexColors.Count==4 && mesh.Normals.Calls==1,"Mesh topology or colours lost");
            assert(mesh.Vertices.Contains(new Point3d(1000,2000,3000))&&mesh.Vertices.Contains(new Point3d(1500,2500,3000)),"Grid-to-document transformation wrong");
            assert(mesh.VertexColors.All(v=>v.ToArgb()==CaseGeometry.ColorAt(.5,"blue-green").ToArgb()),"Constant range division changed colour");
        });
        test("cancel observes failed preparation without retaining its ownership", () => {
            var document=new RhinoDoc(402);var c=CaseHub.Get(402);var scheduler=new InlineScheduler();
            c.Preparation=Task.FromException<JsonObject>(new InvalidOperationException("preparation failed"));
            var cancellation=new CancellationTokenSource();var token=cancellation.Token;c.PreparationCancel=cancellation;
            var cancel=new Task(()=>CaseHub.Cancel(402));cancel.RunSynchronously(scheduler);
            assert(cancel.IsCompletedSuccessfully && scheduler.Queued==1 && c.Preparation==null && c.PreparationCancel==null && token.IsCancellationRequested && c.State=="cancelled","Fault observer did not execute or cancellation retained preparation");
            CaseHub.Close(402);
        });
        GeometryKernelContracts.Run(test,assert);
        SchedulerTests(test,assert);
    }

    private static void SchedulerTests(Action<string,Action> test,Action<bool,string> assert)
    {
        void Clear() { foreach(var timer in UITimer.Active.ToArray())timer.Pulse();global::Grasshopper.Instances.DocumentServer.Clear();foreach(var timer in UITimer.Active.ToArray())timer.Pulse();GH_Document.EnableSolutions=true; }
        test("polling ignores detached components and batches one solution per document", () => {
            Clear();var detached=new GH_Component();HawaPollScheduler.Request(detached,()=>true,-1);assert(HawaPollScheduler.PendingCount==0,"Detached component retained");
            var doc=new GH_Document();global::Grasshopper.Instances.DocumentServer.Add(doc);var a=new GH_Component{Document=doc};var b=new GH_Component{Document=doc};
            HawaPollScheduler.Request(a,()=>true,-1);HawaPollScheduler.Request(b,()=>true,-1);var timer=UITimer.Active.Single();timer.Pulse();
            assert(a.Expirations==1&&b.Expirations==1&&doc.Solutions==1&&HawaPollScheduler.PendingCount==0&&timer.Disposed,"Batch or timer ownership wrong");Clear();
        });
        test("polling waits for enabled idle documents and earliest due request", () => {
            Clear();var doc=new GH_Document{Enabled=false};global::Grasshopper.Instances.DocumentServer.Add(doc);var c=new GH_Component{Document=doc};
            HawaPollScheduler.Request(c,()=>true,100000);HawaPollScheduler.Request(c,()=>true,-1);var timer=UITimer.Active.Single();timer.Pulse();assert(c.Expirations==0,"Disabled document solved");
            doc.Enabled=true;GH_Document.EnableSolutions=false;timer.Pulse();assert(c.Expirations==0,"Global disable ignored");
            GH_Document.EnableSolutions=true;doc.SolutionDepth=1;timer.Pulse();assert(c.Expirations==0,"Nested solution entered");
            doc.SolutionDepth=0;timer.Pulse();assert(c.Expirations==1&&doc.Solutions==1,"Earlier due request lost");Clear();
        });
        test("polling removes stale identity and isolates predicate errors", () => {
            Clear();var doc=new GH_Document();global::Grasshopper.Instances.DocumentServer.Add(doc);
            var stale=new GH_Component{Document=doc};var bad=new GH_Component{Document=doc};var locked=new GH_Component{Document=doc,Locked=true};
            HawaPollScheduler.Request(stale,()=>false,-1);HawaPollScheduler.Request(bad,()=>throw new InvalidOperationException("identity failed"),-1);HawaPollScheduler.Request(locked,()=>true,-1);
            UITimer.Active.Single().Pulse();assert(HawaPollScheduler.PendingCount==0&&doc.Solutions==0&&bad.Errors.Single().Contains("identity failed"),"Stale predicates retained or error lost");Clear();
        });
        test("polling preserves reentrant requests and reports solve failures", () => {
            Clear();var doc=new GH_Document();global::Grasshopper.Instances.DocumentServer.Add(doc);var c=new GH_Component{Document=doc};bool once=true;
            doc.DuringSolution=()=>{if(once){once=false;HawaPollScheduler.Request(c,()=>true,-1);UITimer.Active.Single().Pulse();}};
            HawaPollScheduler.Request(c,()=>true,-1);var timer=UITimer.Active.Single();timer.Pulse();assert(doc.Solutions==1&&HawaPollScheduler.PendingCount==1,"Reentrant drain lost or recursively solved request");
            doc.DuringSolution=()=>throw new InvalidOperationException("solve failed");timer.Pulse();assert(c.Message=="refresh failed"&&c.Errors.Single().Contains("solve failed")&&HawaPollScheduler.PendingCount==0,"Solve failure did not clean up");Clear();
        });
        test("explicit polling cancellation disposes its timer", () => {
            Clear();var doc=new GH_Document();global::Grasshopper.Instances.DocumentServer.Add(doc);var c=new GH_Component{Document=doc};
            HawaPollScheduler.Request(c,()=>true,100000);var timer=UITimer.Active.Single();HawaPollScheduler.Cancel(c);
            assert(HawaPollScheduler.PendingCount==0&&timer.Disposed&&UITimer.Active.Count==0,"Cancellation leaked timer");Clear();
        });
    }
}

sealed class InlineScheduler : TaskScheduler
{
    public int Queued;
    protected override void QueueTask(Task task) { Queued++;TryExecuteTask(task); }
    protected override bool TryExecuteTaskInline(Task task,bool previouslyQueued) => TryExecuteTask(task);
    protected override IEnumerable<Task> GetScheduledTasks() => Array.Empty<Task>();
}
