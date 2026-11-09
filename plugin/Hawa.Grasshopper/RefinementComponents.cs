using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;
namespace Hawa.Grasshopper;

public sealed class RefinementDomainComponent:HawaComponent {
    public RefinementDomainComponent():base("Hawa Refinement Patch","Patch","Experimental fixed 2:1 patch. Keep its interface at least two coarse cells from geometry.","01 Domain"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077137");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Parent","D","Coarse domain",GH_ParamAccess.item);p.AddBoxParameter("Region","B","Region snapped outward to parent grid axes",GH_ParamAccess.item);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Fine domain","D","Voxelize the original geometry on this domain and use the same physics",GH_ParamAccess.item);p.AddBoxParameter("Bounds","B","Snapped patch",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){var parent=ReadObject(da,0);Box region=default;if(!da.GetData(1,ref region)||!region.IsValid)return;
        var world=new JsonObject{["case"]=parent.DeepClone()};var corners=region.GetCorners().Select(p=>Coordinates.Grid(world,p).Select(v=>v!.GetValue<double>()).ToArray()).ToArray();
        var lo=Enumerable.Range(0,3).Select(a=>(int)Math.Floor(corners.Min(v=>v[a])+1e-8)).ToArray();var hi=Enumerable.Range(0,3).Select(a=>(int)Math.Ceiling(corners.Max(v=>v[a])-1e-8)).ToArray();var n=parent["shape"]!.AsArray().Select(v=>v!.GetValue<int>()).ToArray();
        if(Enumerable.Range(0,3).Any(a=>lo[a]<2||hi[a]>n[a]-3||hi[a]-lo[a]<4))throw new ArgumentException("Patch needs two cells of outer clearance and at least four coarse intervals per axis");
        double spacing=parent["spacing"]!.GetValue<double>();var origin=Coordinates.World(world,new JsonArray(lo.Select(v=>(JsonNode)JsonValue.Create((double)v)!).ToArray()));var axes=parent["basis"]!.AsArray().Select(v=>new Vector3d(v![0]!.GetValue<double>(),v[1]!.GetValue<double>(),v[2]!.GetValue<double>())).ToArray();
        var box=new Box(new Plane(origin,axes[0],axes[1]),new Interval(0,(hi[0]-lo[0])*spacing),new Interval(0,(hi[1]-lo[1])*spacing),new Interval(0,(hi[2]-lo[2])*spacing));var fine=DomainComponent.MakeDomain(box,spacing/2,parent["dx"]!.GetValue<double>()/spacing);
        fine["refinement_lower"]=new JsonArray(lo.Select(v=>(JsonNode)JsonValue.Create(v)!).ToArray());fine["refinement_upper"]=new JsonArray(hi.Select(v=>(JsonNode)JsonValue.Create(v)!).ToArray());da.SetData(0,new HawaGoo(fine));da.SetData(1,box);Message="experimental 2:1";
    }
}

public sealed class RefinedSolveComponent:HawaComponent {
    private string? job,key;private bool first=true,requireOff;
    public RefinedSolveComponent():base("Hawa Refined Solve","Refine","Experimental static two-level BGK solver. Run false cancels. Outputs two field frames on completion.","05 Solve"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077138");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Coarse case","C","Parent case, BGK, voxel walls",GH_ParamAccess.item);p.AddGenericParameter("Fine case","F","Patch case, same physics, voxel walls",GH_ParamAccess.item);p.AddIntegerParameter("Steps","N","Coarse iterations",GH_ParamAccess.item,200);p.AddTextParameter("Device","GPU","auto, mps, cpu, cuda:0",GH_ParamAccess.item,"auto");p.AddBooleanParameter("Run","R","False cancels. Saved true opens idle.",GH_ParamAccess.item,false);p.AddBooleanParameter("Pause","P","Pause at a step boundary",GH_ParamAccess.item,false);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Coarse frame","C","Parent field, covered interior masked",GH_ParamAccess.item);p.AddGenericParameter("Fine frame","F","Patch field",GH_ParamAccess.item);p.AddTextParameter("State","S","State and progress",GH_ParamAccess.item);p.AddTextParameter("Report","R","Method limits and mass change",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){bool run=false,pause=false;da.GetData(4,ref run);da.GetData(5,ref pause);if(first){first=false;requireOff=run;}if(!run){requireOff=false;InputsMissing();Message="stopped";return;}if(requireOff){Message="enable again";return;}var coarse=ReadObject(da,0);var fine=ReadObject(da,1);int steps=200;string device="auto";da.GetData(2,ref steps);da.GetData(3,ref device);
        var req=new JsonObject{["op"]="evaluate_submit",["kind"]="refine",["case"]=coarse.DeepClone(),["fine_case"]=fine.DeepClone(),["steps"]=steps,["device"]=device};string signature=req.ToJsonString();if(job==null||key!=signature){InputsMissing();job=EmbeddedRuntime.Call(req)["job"]!.GetValue<string>();key=signature;}
        EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_control",["job"]=job,["action"]=pause?"pause":"resume"});var status=EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_poll",["job"]=job});string state=status["state"]!.GetValue<string>();Message=state;da.SetData(2,$"{state}: {status["steps"]}/{status["target"]}");if(state=="failed")throw new Exception(status["error"]!.GetValue<string>());
        if(state=="completed"){var r=status["result"]!;for(int i=0;i<2;i++){var f=r[i==0?"coarse_frame":"fine_frame"]!.DeepClone().AsObject();f["kind"]="Frame";da.SetData(i,new HawaGoo(f));}da.SetData(3,$"{r["report"]}\nRelative composite mass change: {r["relative_mass_change"]}");}else{string expected=job;HawaPollScheduler.Request(this,()=>job==expected);}}
    public override void DocumentContextChanged(GH_Document document,GH_DocumentContext context){if(context==GH_DocumentContext.Close||context==GH_DocumentContext.Unloaded||context==GH_DocumentContext.Lock)requireOff=true;base.DocumentContextChanged(document,context);}
    protected override void InputsMissing(){var owned=job;job=key=null;Hawa.Shared.CaseHub.ReleaseJob(owned);}
    public override void RemovedFromDocument(GH_Document doc){InputsMissing();base.RemovedFromDocument(doc);}
}
