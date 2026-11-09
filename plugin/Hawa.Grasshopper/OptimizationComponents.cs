using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Hawa.Grasshopper;

public sealed class EvaluateComponent : HawaComponent
{
    private string? job, signature;
    private bool first = true, requireDisable, wasCancelled;
    public EvaluateComponent() : base("Hawa Evaluate", "Evaluate", "Cancellable stationary-body resistance evaluation. Fitness is mean domain-X force / (0.5 rho U² V^(2/3)), not an arbitrary objective or a conventional area-based Cd. Outputs only completed candidates.", "05 Solve") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077117");
    protected override void RegisterInputParams(GH_InputParamManager p) {
        p.AddGenericParameter("Case", "C", "Stationary single-fluid body case; flow follows domain X", GH_ParamAccess.item);
        p.AddTextParameter("Device", "D", "auto, cpu, mps or cuda:0", GH_ParamAccess.item, "auto");
        p.AddIntegerParameter("Iterations", "N", "Duration per candidate", GH_ParamAccess.item, 200);
        p.AddIntegerParameter("Average window", "W", "Final force averaging window", GH_ParamAccess.item, 20);
        p.AddNumberParameter("Reference volume", "V", "Fixed reference volume in m³", GH_ParamAccess.item, 6);
        p.AddBooleanParameter("Enable", "E", "False cancels and clears the current job", GH_ParamAccess.item, false);
        p.AddBooleanParameter("Pause", "P", "Pause at the next batch boundary", GH_ParamAccess.item, false);
        p.AddBooleanParameter("Cancel", "X", "Cancel. Disable and enable to restart", GH_ParamAccess.item, false);
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p) {
        p.AddNumberParameter("Fitness", "F", "Completed mean X-force coefficient using reference volume^(2/3); not an area-based Cd", GH_ParamAccess.item);
        p.AddGenericParameter("Solution", "S", "Completed candidate", GH_ParamAccess.item);
        p.AddNumberParameter("Resistance", "Fx", "Mean X force in N", GH_ParamAccess.item);
        p.AddTextParameter("Report", "R", "Progress or final diagnostics", GH_ParamAccess.item);
        p.AddTextParameter("Candidate", "ID", "Completed unique job ID", GH_ParamAccess.item);
    }
    internal void RequestCandidate(){Close();ExpireSolution(false);}
    protected override void SolveHawa(IGH_DataAccess da) {
        bool enable=false,pause=false,cancel=false;
        da.GetData(5,ref enable);da.GetData(6,ref pause);da.GetData(7,ref cancel);
        if(first){first=false;requireDisable=enable;}
        if(!enable){requireDisable=false;wasCancelled=false;Close();Message="disabled";return;}
        if(requireDisable){Message="enable again";return;}
        if(cancel){wasCancelled=true;Close();}
        if(wasCancelled){Message="cancelled";da.SetData(3,"Disable and enable to restart.");return;}
        var doc=OnPingDocument();
        if(doc!=null && doc.Objects.Any(o=>o.GetType().Name=="GalapagosObject" && o.GetType().GetProperty("Output")?.GetValue(o) is Guid target && target==Params.Output[0].InstanceGuid))throw new InvalidOperationException("Use Hawa Search for background evaluation. The legacy Galapagos fitness connection cannot wait for an asynchronous result.");
        var spec=ReadObject(da,0);string device="auto";int steps=200,window=20;double volume=6;
        da.GetData(1,ref device);da.GetData(2,ref steps);da.GetData(3,ref window);da.GetData(4,ref volume);
        var request=new JsonObject{["op"]="evaluate_submit",["case"]=spec.DeepClone(),["device"]=device,["steps"]=steps,["window"]=window,["reference_volume"]=volume};
        string key=request.ToJsonString();
        if(key!=signature || job==null){Close();var submitted=EmbeddedRuntime.Call(request);job=submitted["job"]!.GetValue<string>();signature=key;}
        EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_control",["job"]=job,["action"]=pause?"pause":"resume"});
        var status=EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_poll",["job"]=job});
        string state=status["state"]!.GetValue<string>();Message=state;
        da.SetData(3,$"{state}: {status["steps"]} / {status["target"]} iterations\n{status["error"]}");
        if(state=="failed"){AddRuntimeMessage(GH_RuntimeMessageLevel.Error,status["error"]!.GetValue<string>());return;}
        if(state=="completed") {
            var result=status["result"]!;var runtime=result["status"]!;
            da.SetData(0,result["fitness"]!.GetValue<double>());
            da.SetData(1,new HawaGoo(new JsonObject{["kind"]="Solution",["session"]=runtime["session"]!.DeepClone(),["case"]=spec.DeepClone(),["candidate"]=job}));
            da.SetData(2,result["force_newtons"]![0]!.GetValue<double>());da.SetData(4,job);
            da.SetData(3,$"{runtime["backend"]!["selected"]} / completed\nIterations: {steps}\nFitness: {result["fitness"]}\nForce: {result["force_newtons"]} N\nSingle phase submerged body. No waves.");
        } else if(state!="cancelled") {
            string expected=job;
            OnPingDocument()?.ScheduleSolution(100,_=>{if(!Locked && job==expected)ExpireSolution(false);});
        }
    }
    public override void DocumentContextChanged(GH_Document document, GH_DocumentContext context){if(context==GH_DocumentContext.Close||context==GH_DocumentContext.Unloaded||context==GH_DocumentContext.Lock)requireDisable=true;base.DocumentContextChanged(document,context);}
    protected override void InputsMissing(){Close();}
    private void Close(){if(job!=null){try{EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_control",["job"]=job,["action"]="close"});}catch{}job=null;}signature=null;}
    public override void RemovedFromDocument(GH_Document document){Close();base.RemovedFromDocument(document);}
}
