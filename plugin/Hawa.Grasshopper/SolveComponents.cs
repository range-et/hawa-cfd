using System.Text.Json.Nodes;
using Grasshopper.Kernel;

namespace Hawa.Grasshopper;

public sealed class RuntimeComponent : HawaComponent
{
    public RuntimeComponent() : base("Hawa Runtime", "Runtime", "Initialize embedded dependencies and inspect CPU/CUDA/MPS availability", "00 Setup") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077107");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddBooleanParameter("Initialize", "I", "First use downloads compatible dependencies inside Rhino", GH_ParamAccess.item, false); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddTextParameter("Runtime", "R", "Runtime report", GH_ParamAccess.item); p.AddTextParameter("Credits", "C", "Third-party attribution", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        bool init = false; da.GetData(0, ref init);
        da.SetData(1, "Lettuce: Copyright (c) 2019 Andreas Kraemer, MIT; original authors retained. Butterfly by Ladybug Tools: GPL-3.0+ workflow reference; no source included. See THIRD_PARTY_NOTICES.md.");
        da.SetData(0, init ? EmbeddedRuntime.Call(new JsonObject { ["op"] = "info" }).ToJsonString() : "Set Initialize true to prepare Hawa's embedded runtime");
    }
}

public sealed class CheckComponent : HawaQueryComponent
{
    public CheckComponent() : base("Hawa Check Case", "Check", "Validate physical scaling, boundary pairs and estimated GPU memory before allocating a solver", "04 Case") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077108");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddGenericParameter("Case", "C", "Hawa Case", GH_ParamAccess.item); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddBooleanParameter("Valid", "V", "Case preflight passed", GH_ParamAccess.item); p.AddTextParameter("Report", "R", "Scaling and allocation estimate", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da) { var r = View(new JsonObject { ["op"] = "check", ["case"] = ReadObject(da, 0) }); if(r==null)return; da.SetData(0, true); da.SetData(1, r.ToJsonString()); }
}

public sealed class SolveComponent : HawaComponent
{
    private string? session, specText, deviceText, creation;
    private bool previousRun, previousReset, scheduled, runArmed;
    private bool first = true;
    public SolveComponent() : base("Hawa Solve", "Solve", "Persistent background solver. Run true starts/resumes, false pauses. Reset uses a rising edge. No external process.", "05 Solve") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077109");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddGenericParameter("Case", "C", "Hawa Case", GH_ParamAccess.item); p.AddTextParameter("Device", "D", "auto, cpu, mps or cuda:0", GH_ParamAccess.item, "auto"); p.AddIntegerParameter("Target steps", "N", "Absolute total iteration target", GH_ParamAccess.item, 200); p.AddBooleanParameter("Run", "R", "Start/resume on rising edge; false pauses", GH_ParamAccess.item, false); p.AddBooleanParameter("Reset", "X", "Reset on rising edge", GH_ParamAccess.item, false); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddGenericParameter("Solution", "S", "Live Hawa session", GH_ParamAccess.item); p.AddTextParameter("State", "State", "ready, running, paused, completed or failed", GH_ParamAccess.item); p.AddIntegerParameter("Steps", "N", "Completed iterations", GH_ParamAccess.item); p.AddTextParameter("Monitor", "M", "Time, mass change, backend and diagnostics", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        scheduled = false;
        var spec = ReadObject(da, 0); string device = "auto"; int target = 200; bool run = false, reset = false;
        da.GetData(1, ref device); da.GetData(2, ref target); da.GetData(3, ref run); da.GetData(4, ref reset);
        if (target < 0) throw new ArgumentException("Target steps must be nonnegative");
        var text = spec.ToJsonString();
        // Set the saved-toggle guard before queuing the allocation.
        if (first) { previousRun = run; previousReset = reset; runArmed = !run; first = false; }
        if (!run) runArmed = true;
        bool changed = specText != text || deviceText != device;
        if (creation == null || changed)
        {
            bool restartChanged = changed && creation != null && run && runArmed;
            CloseSession();
            if (restartChanged) previousRun = false;
            var submitted=EmbeddedRuntime.Call(new JsonObject { ["op"]="evaluate_submit", ["kind"]="create", ["case"]=spec.DeepClone(), ["device"]=device });
            creation=submitted["job"]!.GetValue<string>();specText=text;deviceText=device;
        }
        if(session==null){
            var ready=EmbeddedRuntime.Call(new JsonObject { ["op"]="evaluate_poll", ["job"]=creation });
            string phase=ready["state"]!.GetValue<string>();
            if(phase=="failed")throw new Exception(ready["error"]!.GetValue<string>());
            if(phase!="completed"){
                Message=Hawa.Shared.LifecycleText.Pending(phase);da.SetData(1,Message);string expected=creation!;
                HawaPollScheduler.Request(this,()=>
                    creation==expected
                );return;
            }
            session=ready["result"]!["status"]!["session"]!.GetValue<string>();
        }
        if (reset && !previousReset) EmbeddedRuntime.Call(Request("reset_async", session));
        if (run && !previousRun) { var start = Request("start", session); start["steps"] = target; EmbeddedRuntime.Call(start); }
        if (!run && previousRun) EmbeddedRuntime.Call(Request("pause_async", session));
        var status = EmbeddedRuntime.Call(Request("status", session));
        previousRun = run; previousReset = reset;
        var state = status["state"]!.GetValue<string>(); Message = state + " / " + status["quality"]?["status"]?.GetValue<string>();
        var solution = new JsonObject { ["kind"] = "Solution", ["label"] = $"Hawa {state}: {status["steps"]} steps", ["session"] = session, ["revision"]=status["steps"]!.DeepClone(), ["case"] = spec.DeepClone() };
        da.SetData(0, new HawaGoo(solution)); da.SetData(1, state); da.SetData(2, status["steps"]!.GetValue<int>()); var backend = status["backend"]!["selected"]!.GetValue<string>();
        var grid = string.Join(" × ", status["resolution"]!.AsArray().Select(v =>
            v!.ToString()
        ));
        var time = status["physical_time"]!.GetValue<double>();
        var mass = status["relative_mass_change"]!.GetValue<double>();
        da.SetData(3, $"Backend: {backend.ToUpperInvariant()}\nGrid: {grid}\nIterations: {status["steps"]} / {status["target"]}\nState: {state}\nSimulation time: {time:g5}\nRelative mass change: {mass:g3}\nMean samples: {status["averaging_samples"]}\nQuality: {status["quality"]?.ToJsonString()}");
        if (status["error"] != null) AddRuntimeMessage(GH_RuntimeMessageLevel.Error, status["error"]!.GetValue<string>());
        if ((state == "running" || state == "pausing" || state == "resetting") && !scheduled)
        {
            scheduled = true;
            string expectedSession=session;HawaPollScheduler.Request(this,()=>
                session==expectedSession
            ,200);
        }
    }
    protected override void InputsMissing(){CloseSession();}
    private void CloseSession()
    {
        var ownedCreation=creation;var ownedSession=session;
        creation=session=null; // Invalidate local ownership before bridge callbacks.
        Hawa.Shared.CaseHub.ReleaseJob(ownedCreation);
        Hawa.Shared.CaseHub.ReleaseSession(ownedSession);
    }
    public override void RemovedFromDocument(GH_Document document) { CloseSession(); base.RemovedFromDocument(document); }
}

public sealed class CheckpointComponent : HawaQueryComponent
{
    private bool previous;
    private JsonObject? operation;
    private bool first = true;
    public CheckpointComponent() : base("Hawa Checkpoint", "Checkpoint", "Save/load a numerical checkpoint or export NPZ fields. Actions use a rising edge and pause the solver for checkpoint operations.", "08 Files") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077110");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddGenericParameter("Solution", "S", "Hawa Solution", GH_ParamAccess.item); p.AddTextParameter("Path", "P", "Local .npz output/input file", GH_ParamAccess.item); p.AddTextParameter("Operation", "O", "save, load or export", GH_ParamAccess.item, "save"); p.AddBooleanParameter("Execute", "E", "Rising edge executes operation", GH_ParamAccess.item, false); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddTextParameter("Report", "R", "Operation result", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da) {
        var s=ReadObject(da,0);string path="",op="save";bool execute=false;
        da.GetData(1,ref path);da.GetData(2,ref op);da.GetData(3,ref execute);
        if(!new[]{"save","load","export"}.Contains(op))throw new ArgumentException("Use save, load or export");
        if(first){previous=execute;first=false;}
        if(execute&&!previous){operation=Request(op,s["session"]!.GetValue<string>());operation["path"]=LocalPath(path);operation["request_id"]=Guid.NewGuid().ToString();}
        previous=execute;
        if(operation!=null){var result=View(operation);if(result!=null)da.SetData(0,result.ToJsonString());}
    }
    protected override void InputsMissing(){base.InputsMissing();}
}
