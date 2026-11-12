using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;
namespace Hawa.Grasshopper;

public sealed class RecordComponent:HawaComponent {
    private string? job,key,restart,offReason;private bool first=true,requireOff;
    public RecordComponent():base("Hawa Record","Record","Run a fresh simulation and write timed field frames to a new local directory. Cancellable.","11 Animation"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077131");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Case","C","Waits for the prepared upstream case",GH_ParamAccess.item);p[0].Optional=true;p.AddTextParameter("Directory","D","New output directory",GH_ParamAccess.item);p.AddIntegerParameter("Steps","N","Total iterations",GH_ParamAccess.item,200);p.AddIntegerParameter("Interval","I","Iterations between recorded frames",GH_ParamAccess.item,10);p.AddTextParameter("Device","GPU","auto, mps, cpu, cuda:0",GH_ParamAccess.item,"auto");p.AddBooleanParameter("Run","R","False cancels; saved true opens idle",GH_ParamAccess.item,false);p.AddBooleanParameter("Pause","P","Pause recording",GH_ParamAccess.item,false);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddTextParameter("Manifest","M","Recording manifest path",GH_ParamAccess.item);p.AddTextParameter("State","S","Progress",GH_ParamAccess.item);p.AddGenericParameter("Solution","Sln","Completed simulation",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){
        bool run=false,pause=false;da.GetData(5,ref run);da.GetData(6,ref pause);if(first){first=false;requireOff=run;}
        if(!run){requireOff=false;offReason=null;InputsMissing();Message="stopped";return;}
        // A document switch cancelled the recording; say why it is idle (#74).
        if(requireOff){Message=offReason??"enable again";if(offReason!=null)AddRuntimeMessage(GH_RuntimeMessageLevel.Remark,Hawa.Shared.LifecycleText.DocumentInactiveReason+" Set Run false, then true, to record again.");return;}
        if(!Params.Input[0].VolatileData.AllData(true).Any(v=>
            v!=null
        )){InputsMissing();Message="waiting for case";return;}
        var spec=ReadObject(da,0);string path="",device="auto";int steps=200,interval=10;da.GetData(1,ref path);da.GetData(2,ref steps);da.GetData(3,ref interval);da.GetData(4,ref device);if(!System.IO.Path.IsPathRooted(path))throw new ArgumentException("Choose an absolute path for a new recording directory");
        var req=new JsonObject{["op"]="evaluate_submit",["kind"]="record",["case"]=spec.DeepClone(),["directory"]=path,["device"]=device,["steps"]=steps,["interval"]=interval};string signature=req.ToJsonString();
        // A changed input starts a new recording; name what changed instead of restarting silently.
        if(job==null||key!=signature){var why=job!=null?Hawa.Shared.LifecycleText.Restart(JsonNode.Parse(key!)!.AsObject(),req):null;InputsMissing();restart=why;job=EmbeddedRuntime.Call(req)["job"]!.GetValue<string>();key=signature;}
        EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_control",["job"]=job,["action"]=pause?"pause":"resume"});var status=EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_poll",["job"]=job});string state=status["state"]!.GetValue<string>();
        Message=restart==null?state:$"{state} ({restart})";da.SetData(1,$"{Message}: {status["steps"]}/{status["target"]}");
        if(restart!=null)AddRuntimeMessage(GH_RuntimeMessageLevel.Remark,"A changed input started a new recording; the previous one stays in its own directory.");
        if(state=="failed")throw new Exception(status["error"]!.GetValue<string>());
        if(state=="completed"){var r=status["result"]!;da.SetData(0,r["manifest"]!.GetValue<string>());da.SetData(2,new HawaGoo(new JsonObject{["kind"]="Solution",["session"]=r["status"]!["session"]!.DeepClone(),["case"]=spec.DeepClone()}));}
        else{string expected=job;HawaPollScheduler.Request(this,()=>
            job==expected
        );}
    }
    public override bool Read(GH_IO.Serialization.GH_IReader reader){bool ok=base.Read(reader);Params.Input[0].Optional=true;return ok;}
    public override void DocumentContextChanged(GH_Document document, GH_DocumentContext context){if(context==GH_DocumentContext.Close||context==GH_DocumentContext.Unloaded||context==GH_DocumentContext.Lock)requireOff=true;if(context==GH_DocumentContext.Unloaded&&job!=null)offReason=Hawa.Shared.LifecycleText.DocumentInactive;base.DocumentContextChanged(document,context);}
    protected override void InputsMissing(){var owned=job;job=key=restart=null;Hawa.Shared.CaseHub.ReleaseJob(owned);}
    public override void RemovedFromDocument(GH_Document doc){InputsMissing();base.RemovedFromDocument(doc);}
}

public sealed class PlaybackComponent:HawaQueryComponent {
    public PlaybackComponent():base("Hawa Playback","Playback","Load a timed field frame from a local recording. Animate the frame slider.","11 Animation"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077132");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddTextParameter("Manifest","M","Local manifest.json",GH_ParamAccess.item);p.AddIntegerParameter("Index","I","Zero-based frame index",GH_ParamAccess.item,0);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Frame","F","Captured field",GH_ParamAccess.item);p.AddNumberParameter("Time","T","Simulation time",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){string manifest="";int index=0;da.GetData(0,ref manifest);da.GetData(1,ref index);var r=View(new JsonObject{["op"]="recording",["action"]="load",["manifest"]=LocalPath(manifest),["index"]=index});if(r==null)return;var f=r.DeepClone().AsObject();f["kind"]="Frame";da.SetData(0,new HawaGoo(f));da.SetData(1,f["time"]!.GetValue<double>());}
}

// Archive compatibility only: Particles and time-dependent pathlines were removed by owner decision.
// Keeps the original GUID and parameters so an old definition opens with its wires and explains the removal.
public sealed class ParticlesComponent:HawaComponent {
    public const string Removed="Hawa Particles was removed. Use Streamlines or Flow Display on a Playback frame.";
    public ParticlesComponent():base("Hawa Particles","Particles","Removed. Opens old definitions only; use Streamlines or Flow Display on a Playback frame.","11 Animation"){}
    public override GH_Exposure Exposure=>GH_Exposure.hidden;
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077133");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddTextParameter("Manifest","M","Removed",GH_ParamAccess.item);p.AddGenericParameter("Frame","F","Removed",GH_ParamAccess.item);p.AddPointParameter("Seeds","P","Removed",GH_ParamAccess.list);p.AddIntegerParameter("Last frame","I","Removed",GH_ParamAccess.item,1);for(int i=0;i<4;i++)p[i].Optional=true;}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddCurveParameter("Trails","C","Removed",GH_ParamAccess.list);p.AddPointParameter("Particles","P","Removed",GH_ParamAccess.list);}
    protected override void SolveHawa(IGH_DataAccess da)=>throw new NotSupportedException(Removed);
}
