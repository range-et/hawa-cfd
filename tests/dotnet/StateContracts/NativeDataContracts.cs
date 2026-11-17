using System.Text.Json.Nodes;
using Hawa.Shared;
using Hawa.Native;
using Rhino;
using Eto.Forms;

static class NativeDataContracts
{
    static IEnumerable<Control> Walk(Control c) => new[] { c }.Concat(c.Children.SelectMany(Walk));
    public static void Run(Action<string,Action> test,Action<bool,string> assert)
    {
        void Reject(Action action) { bool rejected=false;try{action();}catch{rejected=true;}assert(rejected,"Invalid data action accepted"); }
        test("native controls apply dynamics without Run, pair periodic faces and retain range drafts",()=>{
            using var f=new Fixture();CaseHub.Cancel(f.Id);using var panel=new HawaPanel(f.Id);var controls=Walk(panel).ToArray();
            assert(!controls.OfType<Button>().Any(b=>b.Text.StartsWith("Apply")),"Apply clicks still required");
            var boundary=controls.OfType<DropDown>().Where(d=>d.DataStore.Contains("inlet")).ToArray();
            boundary[2].SelectedValue="wall";assert(f.C.Setup["boundaries"]![3]!.GetValue<string>()=="wall","Leaving periodic retained unmatched partner");
            boundary[3].SelectedValue="periodic";assert(f.C.Setup["boundaries"]![2]!.GetValue<string>()=="periodic","Entering periodic omitted partner");
            boundary[2].SelectedIndex=-1;boundary[2].SelectedValue="slip";
            var collision=controls.OfType<DropDown>().Single(d=>d.DataStore.Contains("trt"));collision.SelectedValue="trt";assert(f.C.Setup["collision"]!.GetValue<string>()=="trt","Collision not automatic");collision.SelectedIndex=-1;collision.SelectedValue="bgk";
            controls.OfType<NumericStepper>().Single(n=>n.MinValue==1e-9).Value=.2;assert(f.C.Setup["viscosity"]!.GetValue<double>()==.2 && f.Starts==0 && f.C.Session==null,"Physics edit ran solver or was not committed");
            var axis=controls.OfType<DropDown>().Single(d=>d.DataStore.Contains("XY · Z normal"));axis.SelectedIndex=1;axis.SelectedIndex=-1;axis.SelectedIndex=2;
            var palette=controls.OfType<DropDown>().Single(d=>d.DataStore.Contains("spectrum"));palette.SelectedValue="spectrum";palette.SelectedIndex=-1;palette.SelectedValue="blue-green";
            var position=controls.OfType<NumericStepper>().Single(n=>n.MaxValue==1 && n.MinValue==0);position.Value=.25;
            foreach(var check in controls.OfType<CheckBox>().Where(b=>b.Text!="Interpolated stationary walls"))check.Checked=check.Checked!=true;
            assert(f.C.View["position"]!.GetValue<double>()==.25 && !f.C.View["domain"]!.GetValue<bool>(),"View edits require apply");
            var limits=controls.OfType<NumericStepper>().Where(n=>n.MinValue==-1e12).ToArray();long version=f.C.Version;limits[0].Value=2;
            assert(f.C.Version==version && f.C.View["min"]!.GetValue<double>()==0,"Invalid draft partially changed accepted range");limits[1].Value=3;assert(f.C.View["min"]!.GetValue<double>()==2 && f.C.View["max"]!.GetValue<double>()==3,"Valid pair not committed");
            limits[0].Value=5;CaseHub.Edit(f.Id,new(){["target"]=201},f.C.Version);assert(limits[0].Value==2 && !controls.OfType<Label>().Any(l=>l.Text.Contains("upper colour limit")),"External accepted version retained stale draft");
            // Re-establish only a stopped fixture session; two public ticks produce an actual progress notification.
            f.C.Session="old";f.C.State="paused";f.C.SpecData=f.Spec.DeepClone().AsObject();f.C.RunRevision=f.C.Revision;f.C.LastQuery=DateTime.MinValue;f.C.SliceData=null;
            limits[0].Value=5;CaseHub.Tick();CaseHub.Tick();assert(controls.OfType<Label>().Any(l=>l.Text.Contains("upper colour limit")),"Same-version progress erased draft validation");limits[1].Value=6;assert(f.C.View["min"]!.GetValue<double>()==5,"Draft did not recover after progress");
            CaseHub.Close(f.Id);collision.SelectedValue="trt";axis.SelectedIndex=1;boundary[2].SelectedValue="wall";assert(CaseHub.Find(f.Id)==null,"Detached control recreated case");
        });
        test("native data save captures paused identity despite independent view edits",()=>{
            using var f=new Fixture();var id=f.C.Id;CaseHub.SaveData(f.Id,"saved.npz");
            Reject(()=>CaseHub.SaveData(f.Id,"again.npz"));Reject(()=>CaseHub.ImportData(f.Id,"other.npz","cpu"));
            f.State="running";CaseHub.Tick();assert(f.C.DataState=="saving" && f.C.Session=="old","Pending save changed run");
            CaseHub.Edit(f.Id,new(){["field"]="pressure"},f.C.Version);f.State="completed";CaseHub.Tick();
            assert(f.C.DataState=="saved" && f.C.Id==id && f.C.Session=="old" && f.C.Field=="pressure","View change invalidated valid save or save changed case");
            var summary=f.C.DataResult!;assert(summary["metadata"]!["case"]==null && summary["metadata"]!["native_settings"]==null,"Large solver payload leaked into UI summary");summary["metadata"]!["artifact_id"]="mutated";assert(f.C.DataResult!["metadata"]!["artifact_id"]!.GetValue<string>()=="artifact","Data summary is mutable");
            CaseHub.Reset(f.Id);assert(f.C.DataResult==null,"Reset presents prior saved result as current");
        });
        test("native data import atomically adopts paused physics and preserves explicit resume",()=>{
            using var f=new Fixture();var old=f.C.Id;var lease=CaseHub.Bind(f.C,Guid.NewGuid(),Array.Empty<string>());
            f.Spec["dx"]=.1;f.Spec["spacing"]=100d;f.Spec["origin"]=new JsonArray(1000d,2000d,3000d);f.Spec["shape"]=new JsonArray(8,7,6);f.Spec["speed"]=2d;f.Spec["viscosity"]=.2;
            f.Corrupt=r=>{r["metadata"]!["native_settings"]!["speed"]=99d;r["metadata"]!["native_settings"]!["cell"]=99d;};
            CaseHub.ImportData(f.Id,"saved.npz","cpu");assert(f.C.Id==old && f.C.Session=="old","Import discarded old case before validation");CaseHub.Tick();
            assert(f.C.Id!=old && f.C.Imported && f.C.State=="paused" && f.C.Session=="new" && f.C.Job=="data" && f.Starts==0,"Import did not retain paused creation ownership");
            assert(f.Closed.Contains("old-job") && !f.Closed.Contains("data") && f.C.BindingLease==null,"Old ownership retained or adopted session closed");
            assert(f.C.Speed==2 && f.C.Cell==.1 && f.C.Setup["viscosity"]!.GetValue<double>()==.2,"Presentation metadata overrode authoritative physics");
            assert(CaseGeometry.GridShape(f.C).SequenceEqual(new[]{8,7,6}) && f.C.Setup["size"]![0]!.GetValue<double>()==7*.1,"Fractional dx inflated archived shape");
            var bounds=CaseGeometry.Bounds(f.C);assert(bounds.Min.X==1 && bounds.Min.Y==2 && bounds.Min.Z==3,"Legacy model origin lost physical mapping");
            f.Doc.ModelUnitSystem=UnitSystem.Millimeters;CaseHub.Tick();assert(f.C.Session=="new" && CaseGeometry.Bounds(f.C).Min.X==1000 && CaseGeometry.SpecInModelUnits(f.C)!["origin"]![1]!.GetValue<double>()==2000,"Imported unit change invalidated data or mapped origin wrongly");
            var detached=f.C.ImportedSource!;detached["artifact_id"]="changed";assert(f.C.ImportedSource!["artifact_id"]!.GetValue<string>()=="artifact","Imported identity not detached");
            Reject(()=>CaseHub.Edit(f.Id,new(){["speed"]=1d},f.C.Version));Reject(()=>CaseHub.Bind(f.C,Guid.NewGuid(),Array.Empty<string>()));Reject(()=>CaseHub.BuildSpec(f.C));
            CaseHub.Edit(f.Id,new(){["target"]=40},f.C.Version);Reject(()=>CaseHub.Run(f.Id));assert(f.C.Session=="new","Invalid resume target destroyed imported session");
            CaseHub.Edit(f.Id,new(){["target"]=41},f.C.Version);CaseHub.Run(f.Id);assert(f.Starts==1 && f.C.Session=="new","Explicit resume rebuilt physics");
            CaseHub.Cancel(f.Id);assert(f.C.Outdated && CaseGeometry.Bounds(f.C,true).Min.X==1000 && CaseGeometry.Bounds(f.C,true).Min.Y==2000,"Cancelled imported result lost its archived origin");
            var saved=CaseHub.Save(f.Id);CaseHub.Restore(f.Id,saved);assert(f.C.Imported && f.C.Session==null && f.C.State=="idle","Restore implicitly resumed data");Reject(()=>CaseHub.Run(f.Id));
            CaseHub.UseBlockPreset(f.Id);assert(!f.C.Imported && f.C.State=="idle" && f.C.Session==null,"Explicit new block retained imported restrictions");
        });
        test("native data malformed import and stale contexts preserve the prior case",()=>{
            using var f=new Fixture();var old=f.C.Id;
            var invalid=f.C.Settings();invalid["imported_source"]=new JsonObject{["schema"]="bad"};Reject(()=>CaseHub.Restore(f.Id,invalid.ToJsonString()));assert(f.C.Id==old && f.C.Session=="old","Malformed persisted source mutated case");
            Action<JsonObject>[] corruptions={r=>r["context"]!["case_id"]="bad",r=>r["context"]!["version"]=99L,r=>r["metadata"]!["schema"]="bad",r=>r["metadata"]!["artifact_id"]="",r=>r["metadata"]!["local_time"]=-1d,r=>r["metadata"]!["absolute_time"]=99d,r=>r["status"]!["session"]="old",r=>r["status"]!["state"]="running",r=>r["status"]!["steps"]=41,r=>r["status"]!["case_hash"]="wrong",r=>r["case"]!["speed"]=99d,r=>r["metadata"]!["native_settings"]!["field"]="unknown"};
            foreach(var corrupt in corruptions){f.Corrupt=corrupt;CaseHub.ImportData(f.Id,"bad.npz","cpu");CaseHub.Tick();assert(f.C.DataState=="failed" && f.C.Id==old && f.C.Session=="old" && f.C.DataResult==null,"Malformed import replaced accepted case");}
            f.Corrupt=null;CaseHub.ImportData(f.Id,"saved.npz","cpu");CaseHub.Edit(f.Id,new(){["field"]="pressure"},f.C.Version);CaseHub.Tick();assert(f.C.DataState=="failed" && f.C.Id==old,"Late import overwrote newer settings");
            foreach(var state in new[]{"failed","cancelled"}){f.State=state;CaseHub.ImportData(f.Id,"saved.npz","cpu");CaseHub.Tick();assert(f.C.DataState=="failed" && f.C.Session=="old","Failed backend replaced case");}
            f.State="completed";CaseHub.ImportData(f.Id,"saved.npz","cpu");CaseHub.CancelData(f.Id);assert(f.C.DataJob==null && f.C.Session=="old" && f.C.DataState=="cancelled","Cancelled import discarded accepted case");
            CaseHub.ImportData(f.Id,"saved.npz","cpu");CaseHub.Close(f.Id);assert(f.C.DataJob==null && CaseHub.Find(f.Id)==null,"Document close leaked pending data");
        });
        test("native save validation failures and missing case never invent success",()=>{
            using var f=new Fixture();Reject(()=>CaseHub.SaveData(999999,"save.npz"));assert(CaseHub.Find(999999)==null,"Missing save created a case");
            f.C.State="running";Reject(()=>CaseHub.SaveData(f.Id,"save.npz"));f.C.State="paused";
            Reject(()=>CaseHub.ImportData(f.Id," ","cpu"));Reject(()=>CaseHub.ImportData(f.Id,"x","bad"));
            f.FailSubmit=true;CaseHub.SaveData(f.Id,"save.npz");assert(f.C.DataState=="failed","Submission failure hidden");f.FailSubmit=false;f.EmptyJob=true;CaseHub.SaveData(f.Id,"save.npz");assert(f.C.DataState=="failed","Missing job accepted");f.EmptyJob=false;
            Action<JsonObject>[] corruptions={r=>r["path"]="other",r=>r["format"]="csv",r=>r["metadata"]!["attribution"]!["revision"]=99L,r=>r["metadata"]!["source_state"]="running",r=>r["metadata"]!["iteration"]=41};
            foreach(var corrupt in corruptions){f.Corrupt=corrupt;CaseHub.SaveData(f.Id,"save.npz");CaseHub.Tick();assert(f.C.DataState=="failed" && f.C.Session=="old","Malformed save damaged solver or claimed success");}
            f.Corrupt=null;CaseHub.SaveData(f.Id,"save.npz");f.OnPoll=()=>f.C.DataJob=null;CaseHub.Tick();assert(f.C.DataResult==null,"Detached data reply published");f.OnPoll=null;
            CaseHub.CancelData(999999);CaseHub.CancelData(f.Id);
        });
        test("empty import placeholder preserves absence of accepted physics across document save",()=>{
            using var f=new Fixture();CaseHub.Close(f.Id);f.FailSubmit=true;CaseHub.ImportData(f.Id,"missing.npz","cpu");var c=CaseHub.Find(f.Id)!;
            assert(c.DataPlaceholder && c.Imported && c.Session==null && c.DataState=="failed","Failed empty import invented accepted block");
            using var preview=new NativePreview();var draw=new Rhino.Display.DisplayPipeline();preview.RaisePostDraw(new(f.Doc,draw));preview.RaiseForeground(new(f.Doc,draw));var bounds=new Rhino.Display.CalculateBoundingBoxEventArgs(f.Doc);preview.RaiseBoundingBox(bounds);assert(draw.Calls.Count==0 && bounds.Included.Count==0,"Placeholder drew fabricated physics");
            var saved=CaseHub.Save(f.Id);CaseHub.Restore(f.Id,saved);assert(c.DataPlaceholder && c.State=="idle","Placeholder persistence invented accepted case");Reject(()=>CaseHub.Run(f.Id));
            using var panel=new HawaPanel(f.Id);assert(Walk(panel).OfType<Label>().Any(l=>l.Text.StartsWith("NO ACCEPTED CASE")) && !Walk(panel).OfType<Button>().Single(b=>b.Text=="Run / Resume").Enabled,"Placeholder can run or looks accepted");
            CaseHub.UseBlockPreset(f.Id);assert(!c.Imported,"Explicit block did not leave placeholder");
        });
        test("native data controls choose files, import paused, save and cancel without implicit run",()=>{
            using var f=new Fixture();using var panel=new HawaPanel(f.Id);var controls=Walk(panel).ToArray();Button B(string text)=>controls.OfType<Button>().Single(b=>b.Text==text);var path=controls.OfType<TextBox>().Single(t=>t.ToolTip.StartsWith("Hawa data"));
            SaveFileDialog.Result=DialogResult.Cancel;B("Choose save file").PerformClick();assert(path.Text=="","Cancelled save chooser changed path");
            SaveFileDialog.Result=DialogResult.Ok;SaveFileDialog.Chosen="saved.npz";B("Choose save file").PerformClick();assert(path.Text=="saved.npz","Save path not chosen");
            B("Save data").PerformClick();B("Cancel data operation").PerformClick();assert(f.C.DataJob==null,"Panel cancel retained operation");B("Save data").PerformClick();CaseHub.Tick();assert(f.C.DataState=="saved" && controls.OfType<Label>().Any(l=>l.Text.Contains("Artifact:")),"Panel save missing");
            OpenFileDialog.Result=DialogResult.Cancel;B("Choose import file").PerformClick();OpenFileDialog.Result=DialogResult.Ok;OpenFileDialog.Chosen="import.npz";B("Choose import file").PerformClick();assert(path.Text=="import.npz","Import path not chosen");B("Import data").PerformClick();CaseHub.Tick();
            assert(f.C.Imported && f.Starts==0 && controls.OfType<NumericStepper>().Where(n=>n.ToolTip.StartsWith("Inlet speed")||n.ToolTip.StartsWith("Cell size")).All(n=>!n.Enabled),"Imported controls writable or automatically ran");
            CaseHub.Close(f.Id);assert(!B("Save data").Enabled,"Closed case can save data");
        });
    }
    sealed class Fixture:IDisposable
    {
        static uint serial=12000;readonly Func<JsonObject,JsonObject> prior=CaseHub.Transport;
        public readonly uint Id=++serial;public readonly RhinoDoc Doc;public readonly CaseState C;public JsonObject Spec;
        public string State="completed";public bool FailSubmit,EmptyJob;public int Starts;public Action<JsonObject>? Corrupt;public Action? OnPoll;
        public readonly List<string> Closed=new();JsonObject request=new();bool importing;string viewField="speed";
        public Fixture(){Doc=new(Id);C=CaseHub.Get(Id);C.Session="old";C.Job="old-job";C.State="paused";C.Steps=40;C.RunRevision=C.Revision;C.StatusData=new(){["case_hash"]="hash"};C.SpecData=CaseHub.BuildSpec(C);Spec=C.SpecData.DeepClone().AsObject();C.SliceData=new();C.SliceSteps=40;C.LastQuery=DateTime.UtcNow;CaseHub.Transport=Call;}
        JsonObject Metadata()=>new(){["schema"]="hawa-native-data-1",["artifact_id"]="artifact",["case"]=Spec.DeepClone(),["case_hash"]="hash",["iteration"]=40,["local_time"]=4d,["time_origin"]=0d,["absolute_time"]=4d,["source_state"]="paused",["source_session"]="old",["native_settings"]=(importing?C.Settings():request["native_settings"]!.DeepClone()),["attribution"]=(importing?new JsonObject():request["attribution"]!.DeepClone())};
        JsonObject Call(JsonObject r){switch(r["op"]!.GetValue<string>()){
            case "evaluate_submit":if(FailSubmit)throw new Exception("submit failed");if(r["request"]?["op"]?.GetValue<string>()=="slice"){viewField=r["request"]!["field"]!.GetValue<string>();return new(){["job"]="view"};}importing=r["kind"]!.GetValue<string>()=="native_data_import";request=(importing?r:r["request"]!).DeepClone().AsObject();return new(){["job"]=EmptyJob?"":"data"};
            case "evaluate_poll":if(r["job"]!.GetValue<string>()=="view")return new(){["state"]="completed",["result"]=new JsonObject{["session"]=C.Session,["field"]=viewField,["steps"]=40,["physical_time"]=4d,["shape"]=new JsonArray(1,1),["values"]=new JsonArray(1d),["valid"]=new JsonArray(true),["coordinates"]=new JsonArray(new JsonArray(0d,0d,0d))}};
                OnPoll?.Invoke();var result=importing?new JsonObject{["status"]=new JsonObject{["session"]="new",["state"]="paused",["steps"]=40,["case_hash"]="hash"},["case"]=Spec.DeepClone(),["metadata"]=Metadata(),["context"]=request["context"]!.DeepClone()}:new JsonObject{["path"]=request["path"]!.DeepClone(),["format"]="npz",["schema"]="hawa-native-data-1",["metadata"]=Metadata()};Corrupt?.Invoke(result);return new(){["state"]=State,["result"]=result};
            case "status":return new(){["session"]=C.Session,["state"]="paused",["steps"]=40,["case_hash"]="hash"};
            case "start":Starts++;return new(){["state"]="running"};
            case "evaluate_control":Closed.Add(r["job"]!.GetValue<string>());return new();case "close_async":Closed.Add(r["session"]!.GetValue<string>());return new();
            default:throw new Exception("Unexpected fixture operation");}}
        public void Dispose(){CaseHub.Close(Id);CaseHub.RetryCleanup();CaseHub.Transport=prior;}
    }
}
