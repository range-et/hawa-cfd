using System.Text.Json.Nodes;
using Hawa.Shared;
using Rhino;
using Rhino.Geometry;
using Eto.Forms;
using Hawa.Native;

static class NativeExportContracts
{
    static IEnumerable<Control> Walk(Control c) => new[] { c }.Concat(c.Children.SelectMany(Walk));
    public static void Run(Action<string, Action> test, Action<bool, string> assert)
    {
        void Reject(Action action) { bool rejected=false; try { action(); } catch { rejected=true; } assert(rejected,"Invalid export accepted"); }
        test("native export freezes completed identity and maps millimetre probes independently of preview", () =>
        {
            using var f=new Fixture();
            f.Doc.ModelUnitSystem=UnitSystem.Millimeters;f.C.ModelUnits=UnitSystem.Millimeters;
            f.C.SpecData=new(){["origin"]=new JsonArray(1000d,2000d,3000d),["spacing"]=500d};
            var points=new[]{new Point3d(1500,3000,4500)};
            CaseHub.Export(f.Id,"/tmp/native-test.csv","probes",points);points[0]=new(0,0,0);
            assert(f.Request!["points"]!.ToJsonString()=="[[1,2,3]]","Document coordinates not frozen/mapped");
            assert(f.C.ExportJob=="export" && f.C.Query==null && f.C.ExportState=="pending","Ownership mixed with preview");
            Reject(()=>CaseHub.Export(f.Id,"/tmp/other.csv","fields"));
            f.PollState="running";CaseHub.Tick();assert(f.C.ExportResult==null,"Pending result published");
            f.PollState="completed";CaseHub.Tick();
            assert(f.C.ExportState=="completed" && f.C.ExportJob==null && f.Closed==1,"Completion did not release query");
            assert(f.C.ExportResult!["iteration"]!.GetValue<int>()==40 && f.C.State=="completed" && f.C.Fault==null,"Export damaged solver or lost capture");
            var copy=f.C.ExportResult!;copy["iteration"]=0;assert(f.C.ExportResult!["iteration"]!.GetValue<int>()==40,"Result not detached");
            CaseHub.Edit(f.Id,new(){["speed"]=1.2},f.C.Version);
            assert(f.C.ExportResult==null && f.C.ExportState=="idle","Physical edit presents a prior artifact as current");
        });
        test("native export admission rejects unavailable states and invalid probes before submission", () =>
        {
            using var f=new Fixture();
            Reject(()=>CaseHub.Export(99999,"a","fields"));
            foreach(var state in new[]{"running","paused","failed","idle"}) { f.C.State=state;Reject(()=>CaseHub.Export(f.Id,"a","fields")); } f.C.State="completed";
            Reject(()=>CaseHub.Export(f.Id,"a","loads"));Reject(()=>CaseHub.Export(f.Id," ","fields"));
            f.Doc.ModelUnitSystem=UnitSystem.Millimeters;Reject(()=>CaseHub.Export(f.Id,"a","fields"));f.Doc.ModelUnitSystem=UnitSystem.Meters;
            f.C.StatusData=null;Reject(()=>CaseHub.Export(f.Id,"a","fields"));f.C.StatusData=new(){["case_hash"]="hash"};
            Reject(()=>CaseHub.Export(f.Id,"a","probes"));Reject(()=>CaseHub.Export(f.Id,"a","probes",Enumerable.Repeat(new Point3d(),10001)));
            Reject(()=>CaseHub.Export(f.Id,"a","probes",new[]{new Point3d(double.NaN,0,0)}));
            assert(f.Request==null,"Rejected request submitted");
            RhinoApp.InvokeRequired=true;try { Reject(()=>CaseHub.Export(f.Id,"a","fields")); } finally { RhinoApp.InvokeRequired=false; }
            CaseHub.CancelExport(99999);CaseHub.CancelExport(f.Id);
            f.FailSubmit=true;CaseHub.Export(f.Id,"a","fields");assert(f.C.ExportState=="failed" && f.C.ExportError.Contains("submit") && f.C.Fault==null,"Submit failure not isolated");
            f.FailSubmit=false;f.EmptyJob=true;CaseHub.Export(f.Id,"a","fields");assert(f.C.ExportState=="failed","Empty job accepted");
        });
        test("native export rejects malformed captured provenance without publishing partial results", () =>
        {
            using var f=new Fixture();
            Action<JsonObject>[] corruptions={
                r=>r["session"]="wrong",r=>r["path"]="wrong",r=>r["format"]="npz",r=>r["table"]="loads",
                r=>r["case_hash"]="wrong",r=>r["iteration"]=41,r=>r["source_state"]="running",
                r=>r["attribution"]!["case_id"]="wrong",r=>r["attribution"]!["revision"]=99L,
                r=>r["attribution"]!["generation"]=99L,r=>r["attribution"]!["version"]=99L,
                r=>r["attribution"]!["extra"]=1,r=>r["artifact_id"]="",r=>r["rows"]=0,
                r=>r["local_time"]=-1d,r=>r["time_origin"]=-1d,r=>r["absolute_time"]=-1d,
                r=>r["absolute_time"]=2d,r=>r.Remove("local_time")
            };
            foreach(var corrupt in corruptions) { f.Corrupt=corrupt;CaseHub.Export(f.Id,"a","fields");CaseHub.Tick();assert(f.C.ExportState=="failed" && f.C.ExportResult==null && f.C.ExportError.Length>0 && f.C.State=="completed" && f.C.ViewError=="","Malformed reply damaged solver/view or published"); }
            f.Corrupt=null;foreach(var state in new[]{"failed","cancelled"}) { f.PollState=state;CaseHub.Export(f.Id,"a","fields");CaseHub.Tick();assert(f.C.ExportState=="failed","Failed job accepted"); }
            f.PollState="completed";f.OnPoll=()=>f.C.Generation++;CaseHub.Export(f.Id,"a","fields");CaseHub.Tick();assert(f.C.ExportState=="failed","Stale generation published");
        });
        test("native export cancellation and disposal retain cleanup ownership and suppress late replies", () =>
        {
            using var f=new Fixture();
            CaseHub.Export(f.Id,"a","fields");f.FailClose=true;CaseHub.CancelExport(f.Id);
            assert(f.C.ExportState=="cancelled" && f.C.ExportJob==null && CaseHub.PendingCleanupCount>0,"Cancel lost cleanup ownership");
            f.FailClose=false;CaseHub.RetryCleanup();assert(CaseHub.PendingCleanupCount==0,"Cleanup not retried");
            CaseHub.Export(f.Id,"a","fields");f.OnPoll=()=>{ f.C.ExportJob=null; };CaseHub.Tick();assert(f.C.ExportResult==null,"Detached reply published");
            f.OnPoll=null;CaseHub.Export(f.Id,"a","fields");CaseHub.Edit(f.Id,new(){["speed"]=1.1},f.C.Version);assert(f.C.ExportJob==null && f.C.ExportState=="cancelled","Physics edit retained export");
            f.Ready();CaseHub.Export(f.Id,"a","fields");CaseHub.Reset(f.Id);assert(f.C.ExportJob==null,"Reset retained export");
            f.Ready();CaseHub.Export(f.Id,"a","fields");CaseHub.Close(f.Id);var replacement=CaseHub.Get(f.Id);assert(replacement.ExportResult==null && f.C.ExportJob==null,"Replacement inherited export");
        });
        test("native export panel captures only selected points and survives panel close", () =>
        {
            using var f=new Fixture();
            using(var panel=new HawaPanel(f.Id)) {
                var controls=Walk(panel).ToArray();
                Button Button(string name)=>controls.OfType<Button>().Single(b=>b.Text==name);
                var path=controls.OfType<TextBox>().Single();
                SaveFileDialog.Result=DialogResult.Cancel;Button("Browse CSV").PerformClick();assert(path.Text=="","Cancelled path dialog changed destination");
                SaveFileDialog.Result=DialogResult.Ok;SaveFileDialog.Chosen="/tmp/"+new string('x',180)+".csv";Button("Browse CSV").PerformClick();assert(path.Text==SaveFileDialog.Chosen,"Chosen path lost");
                Button("Capture selected probes").PerformClick();
                assert(controls.OfType<Label>().Any(l=>l.Text.Contains("Select 1..10000")),"Empty probes silently accepted");
                f.Doc.Objects.Items[Guid.NewGuid()]=new(new Rhino.Geometry.Point(new(1,2,3))){Selected=true};
                f.Doc.Objects.Items[Guid.NewGuid()]=new(new Rhino.Geometry.Point(new(9,9,9)));
                Button("Capture selected probes").PerformClick();assert(controls.OfType<Label>().Any(l=>l.Text.Contains("Captured probes: 1")),"Selection scope lost");
                var otherDoc=new RhinoDoc(f.Id+10000);
                try {
                    var other=CaseHub.Get(otherDoc.RuntimeSerialNumber);other.State="completed";other.Session="other";
                    using var otherPanel=new HawaPanel(otherDoc.RuntimeSerialNumber);
                    var otherControls=Walk(otherPanel).ToArray();
                    assert(otherControls.OfType<Label>().Any(l=>l.Text.StartsWith("Select Rhino point objects")),"Same-unit document inherited captured probes");
                    otherControls.OfType<Button>().Single(b=>b.Text=="Capture selected probes").PerformClick();
                    assert(otherControls.OfType<Label>().Any(l=>l.Text.Contains("Select 1..10000")),"Probe capture used another document's selection");
                } finally {CaseHub.Close(otherDoc.RuntimeSerialNumber);RhinoDoc.Remove(otherDoc.RuntimeSerialNumber);}
                controls.OfType<DropDown>().Single(d=>d.DataStore.Contains("probes")).SelectedValue="probes";
                f.Doc.ModelUnitSystem=UnitSystem.Millimeters;Button("Export CSV").PerformClick();assert(f.C.ExportJob==null,"Changed-unit probes submitted");f.Doc.ModelUnitSystem=UnitSystem.Meters;
                Button("Export CSV").PerformClick();assert(f.C.ExportJob!=null && Button("Cancel export").Enabled,"Panel export not owned");
                Button("Cancel export").PerformClick();assert(f.C.ExportJob==null,"Panel cancel failed");
                Button("Export CSV").PerformClick();CaseHub.Tick();var summary=controls.OfType<Label>().Single(l=>l.Text.Contains("Artifact: artifact"));
                assert(summary.ToolTip.Contains(SaveFileDialog.Chosen) && summary.ToolTip.Contains("Case:") && summary.ToolTip.Contains("Session: session"),"Full file/capture identity is inaccessible");
                assert(!summary.Text.Contains(SaveFileDialog.Chosen) && !summary.Text.Contains(new string('x',17)),"Long destination leaks into dock summary");
                f.FailSubmit=true;Button("Export CSV").PerformClick();assert(summary.Text.Contains("Hover for error details") && summary.ToolTip.Contains("submit failed"),"Failure details lost from compact display");f.FailSubmit=false;
                Button("Export CSV").PerformClick();
            }
            assert(f.C.ExportJob!=null,"Closing panel cancelled service-owned export");CaseHub.Tick();assert(f.C.ExportState=="completed","Detached panel export did not complete");
        });
    }
    sealed class Fixture : IDisposable
    {
        static uint sequence=9000;
        readonly Func<JsonObject,JsonObject> prior=CaseHub.Transport;
        public readonly uint Id=++sequence;
        public readonly RhinoDoc Doc;
        public readonly CaseState C;
        public JsonObject? Request;
        public string PollState="completed";
        public bool FailSubmit, EmptyJob, FailClose;
        public int Closed;
        public Action<JsonObject>? Corrupt;
        public Action? OnPoll;
        public Fixture() { Doc=new(Id);C=CaseHub.Get(Id);Ready();CaseHub.Transport=Call; }
        public void Ready() { C.Session="session";C.State="completed";C.RunRevision=C.Revision;C.Steps=40;C.StatusData=new(){["case_hash"]="hash"};C.SpecData=new(){["origin"]=new JsonArray(0d,0d,0d),["spacing"]=1d};C.SliceData=new();C.SliceSteps=40;C.LastQuery=DateTime.UtcNow; }
        JsonObject Call(JsonObject request) {
            switch(request["op"]!.GetValue<string>()) {
                case "evaluate_submit": if(FailSubmit)throw new Exception("submit failed");Request=request["request"]!.DeepClone().AsObject();return new(){["job"]=EmptyJob?"":"export"};
                case "evaluate_poll":
                    OnPoll?.Invoke();var r=new JsonObject{["path"]=Request!["path"]!.DeepClone(),["format"]="csv",["table"]=Request["table"]!.DeepClone(),["rows"]=1,["artifact_id"]="artifact",["session"]="session",["case_hash"]="hash",["iteration"]=40,["local_time"]=.4,["time_origin"]=0d,["absolute_time"]=.4,["source_state"]="completed",["attribution"]=Request["attribution"]!.DeepClone()};Corrupt?.Invoke(r);return new(){["state"]=PollState,["result"]=r};
                case "status": return new(){["state"]="completed",["steps"]=40,["case_hash"]="hash"};
                case "evaluate_control":case "close_async":if(FailClose)throw new Exception("close failed");Closed++;return new();
                default:throw new Exception("Unexpected fixture operation");
            }
        }
        public void Dispose(){ FailClose=false;CaseHub.Close(Id);CaseHub.RetryCleanup();CaseHub.Transport=prior; }
    }
}
