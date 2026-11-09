using System.Text.Json.Nodes;
using Grasshopper.Kernel;
namespace Hawa.Grasshopper;

public sealed class BoundaryCaptureComponent : HawaQueryComponent
{
    private bool first=true, requireOff;
    public BoundaryCaptureComponent():base("Hawa Boundary Capture","Capture BC","Map a completed parent recording to a child. Neutral external cases use v2 velocity/pressure on all open/velocity faces and mapped initial fields; legacy cases retain v1 X-. Cancellable worker.","12 Flow Transfer"){}
    public override Guid ComponentGuid=>new("3c7b9535-cfa0-473e-8dbb-61c984374f10");
    protected override void RegisterInputParams(GH_InputParamManager p){
        p.AddTextParameter("Parent recording","M","Completed recording manifest with quality diagnostics; waits while upstream recording runs",GH_ParamAccess.item);p[0].Optional=true;
        p.AddGenericParameter("Child case","C","Stationary uniform child; Neutral Flow enables multi-face v2",GH_ParamAccess.item);p[1].Optional=true;
        p.AddTextParameter("New boundary file","P","Absolute path for a new .npz file; existing files are preserved",GH_ParamAccess.item);
        p.AddBooleanParameter("Capture","R","Enable to capture when upstream data is ready; false cancels. Saved true opens idle.",GH_ParamAccess.item,false);
        p.AddNumberParameter("Start time","T0","First parent time in seconds; v2 only. Frames before this time are excluded.",GH_ParamAccess.item,0d);
        p.AddNumberParameter("End time","T1","Last parent time in seconds; negative selects the recording end. v2 only.",GH_ParamAccess.item,-1d);
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Mapped case","C","Child case with imported inlet",GH_ParamAccess.item);p.AddTextParameter("Boundary file","P","Saved file for Boundary Data",GH_ParamAccess.item);p.AddTextParameter("Report","R","Mapping and source quality report",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){
        bool run=false;da.GetData(3,ref run);if(first){first=false;requireOff=run;}if(!run){requireOff=false;InputsMissing();Message="idle";return;}if(requireOff){Message="enable again";return;}
        if(new[]{0,1}.Any(i=>!Params.Input[i].VolatileData.AllData(true).Any(v=>v!=null))){InputsMissing();Message="waiting for upstream data";return;}
        string manifest="",path="";double start=0,end=-1;da.GetData(0,ref manifest);da.GetData(2,ref path);da.GetData(4,ref start);da.GetData(5,ref end);
        var r=View(new JsonObject{["op"]="boundary",["action"]="capture",["manifest"]=LocalPath(manifest),["case"]=ReadObject(da,1),["path"]=LocalPath(path),["start_time"]=start,["end_time"]=end<0?null:JsonValue.Create(end)});
        if(r==null)return;da.SetData(0,new HawaGoo(r["case"]!.AsObject()));da.SetData(1,path);da.SetData(2,r["report"]!.ToJsonString());
    }
    public override bool Read(GH_IO.Serialization.GH_IReader reader){bool ok=base.Read(reader);Params.Input[0].Optional=true;Params.Input[1].Optional=true;return ok;}
    public override void DocumentContextChanged(GH_Document document,GH_DocumentContext context){if(context==GH_DocumentContext.Close||context==GH_DocumentContext.Unloaded||context==GH_DocumentContext.Lock)requireOff=true;base.DocumentContextChanged(document,context);}
}

public sealed class BoundaryDataComponent : HawaQueryComponent
{
    public BoundaryDataComponent():base("Hawa Boundary Data","Read BC","Validate a local boundary dataset and attach it to its matching child grid. Checks units, coverage, hash, source quality and imported Mach.","12 Flow Transfer"){}
    public override Guid ComponentGuid=>new("3c7b9535-cfa0-473e-8dbb-61c984374f11");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddTextParameter("Boundary file","P","Local .npz from Boundary Capture",GH_ParamAccess.item);p.AddGenericParameter("Child case","C","Matching child grid and physical scaling",GH_ParamAccess.item);p.AddIntegerParameter("Reload","R","Increment to re-read an externally replaced file",GH_ParamAccess.item,0);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Mapped case","C","Connect to Solve or Record",GH_ParamAccess.item);p.AddTextParameter("Report","R","Validation report",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){string path="";int reload=0;da.GetData(0,ref path);da.GetData(2,ref reload);var r=View(new JsonObject{["op"]="boundary",["action"]="attach",["path"]=LocalPath(path),["case"]=ReadObject(da,1),["reload"]=reload});if(r==null)return;da.SetData(0,new HawaGoo(r["case"]!.AsObject()));da.SetData(1,r["report"]!.ToJsonString());}
}

public sealed class ResultQualityComponent : HawaComponent
{
    public ResultQualityComponent():base("Hawa Result Quality","Quality","Inspect sampled numerical-envelope diagnostics. Completion does not establish convergence or physical validation.","06 Results"){}
    public override Guid ComponentGuid=>new("3c7b9535-cfa0-473e-8dbb-61c984374f12");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Solution","S","Live solution",GH_ParamAccess.item);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddTextParameter("Quality","Q","Sampled envelope status",GH_ParamAccess.item);p.AddBooleanParameter("Transfer eligible","T","Passes the bounded transfer policy; not physical validation",GH_ParamAccess.item);p.AddTextParameter("Report","R","Diagnostics, time, cadence and limits",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){var solution=ReadObject(da,0);var s=EmbeddedRuntime.Call(new JsonObject{["op"]="status",["session"]=solution["session"]!.DeepClone()});var q=s["quality"]!;string state=q["status"]!.GetValue<string>();Message=state;da.SetData(0,state);da.SetData(1,q["transfer_eligible"]!.GetValue<bool>());da.SetData(2,q.ToJsonString());if(state!="within-tested-envelope")AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,"Result quality: "+state);}
}

public sealed class BoundaryPatchComponent : HawaComponent
{
    public BoundaryPatchComponent():base("Hawa Boundary Patch","Patch","Named physical condition on a complete oriented face. Velocities use domain axes and m/s; pressure is gauge Pa. No solver arrays are stored here.","03 Physics"){}
    public override Guid ComponentGuid=>new("3c7b9535-cfa0-473e-8dbb-61c984374f13");
    protected override void RegisterInputParams(GH_InputParamManager p){
        p.AddTextParameter("Face","F","x-, x+, y-, y+, z-, z+",GH_ParamAccess.item,"x-");
        p.AddTextParameter("Condition","C","velocity, pressure, open, wall, slip, periodic",GH_ParamAccess.item,"velocity");
        p.AddVectorParameter("Velocity","U","Domain-axis m/s. Velocity peak; wall velocity; or exterior incoming velocity for open.",GH_ParamAccess.item,Rhino.Geometry.Vector3d.Zero);
        p.AddNumberParameter("Pressure","P","Gauge Pa, used only by pressure/open",GH_ParamAccess.item,0);
        p.AddTextParameter("Profile","V","uniform, parabolic, mapped (attached X- file), neutral (Neutral Flow only)",GH_ParamAccess.item,"uniform");
        p.AddIntegerParameter("Profile axis","A","Parabolic cross-channel axis: 0=X, 1=Y, 2=Z",GH_ParamAccess.item,1);
        p.AddTextParameter("Backflow mode","B","Open faces: velocity prescribes incoming U; pressure derives normal speed from the flow and prescribes only incoming tangential U. Pressure mode requires Neutral Flow. Mapped v2 uses parent data.",GH_ParamAccess.item,"velocity");
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Patch","B","Connect all six patches to Boundary Set",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){
        string face="",kind="",profile="",backflow="velocity";int axis=1;double pressure=0;var velocity=Rhino.Geometry.Vector3d.Zero;
        da.GetData(0,ref face);da.GetData(1,ref kind);da.GetData(2,ref velocity);da.GetData(3,ref pressure);da.GetData(4,ref profile);da.GetData(5,ref axis);
        da.GetData(6,ref backflow);backflow=backflow.Trim().ToLowerInvariant();if(backflow!="velocity"&&backflow!="pressure")throw new ArgumentException("Backflow mode: velocity or pressure");
        face=face.Trim().ToLowerInvariant();kind=kind.Trim().ToLowerInvariant();profile=profile.Trim().ToLowerInvariant();
        if(!velocity.IsValid||!double.IsFinite(pressure))throw new ArgumentException("Finite velocity and pressure required");
        var c=new JsonObject{["type"]=kind};
        if(kind=="velocity"||kind=="wall"||kind=="open")c["velocity"]=Numbers(new[]{velocity.X,velocity.Y,velocity.Z});
        if(kind=="pressure"||kind=="open")c["pressure_pa"]=pressure;
        if(kind=="open")c["backflow_mode"]=backflow;
        if(kind=="velocity"||kind=="open"){c["profile"]=profile;if(profile=="parabolic")c["profile_axis"]=axis;}
        da.SetData(0,new HawaGoo(new JsonObject{["kind"]="BoundaryPatch",["label"]=face+" / "+kind,["id"]=face,["face"]=face,["condition"]=c}));
    }
}

public sealed class BoundarySetComponent : HawaQueryComponent
{
    public BoundarySetComponent():base("Hawa Boundary Set","Boundary Set","Compile six physical patches for stationary uniform-grid NEE. Supports one opposite flow-face pair and compatible wall/slip edges. Validation runs in a worker.","03 Physics"){}
    public override Guid ComponentGuid=>new("3c7b9535-cfa0-473e-8dbb-61c984374f14");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Case","C","Base or mapped case; legacy face strings are replaced explicitly",GH_ParamAccess.item);p.AddGenericParameter("Patches","B","Exactly six named Boundary Patch objects",GH_ParamAccess.list);p.AddVectorParameter("Initial velocity","U0","Domain-axis m/s at t=0; default starts from rest",GH_ParamAccess.item,Rhino.Geometry.Vector3d.Zero);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Case","C","Validated NEE case; connect to Solve",GH_ParamAccess.item);p.AddTextParameter("Plan","P","Ownership, scaling and supported limits",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){
        var spec=ReadObject(da,0);var inputs=new List<global::Grasshopper.Kernel.Types.IGH_Goo>();da.GetDataList(1,inputs);var patches=new JsonArray();
        foreach(var input in inputs){var value=input is HawaGoo h?h:(input as global::Grasshopper.Kernel.Types.GH_ObjectWrapper)?.Value as HawaGoo;if(value==null)throw new ArgumentException("Use Boundary Patch objects");var p=value.Data;p.Remove("kind");p.Remove("label");patches.Add(p);}
        var initial=Rhino.Geometry.Vector3d.Zero;da.GetData(2,ref initial);if(!initial.IsValid)throw new ArgumentException("Finite initial velocity required");
        spec["boundary_set"]=new JsonObject{["schema"]=1,["patches"]=patches};spec["boundary_method"]="hawa-nee-v1";spec["initial_velocity"]=Numbers(new[]{initial.X,initial.Y,initial.Z});
        var report=View(new JsonObject{["op"]="check",["case"]=spec});if(report==null)return;
        da.SetData(0,new HawaGoo(spec));da.SetData(1,report.ToJsonString());
    }
}

public sealed class NeutralPrecursorComponent : HawaQueryComponent
{
    public NeutralPrecursorComponent():base("Hawa Neutral Flow","Neutral Lab","Experimental rough-floor flow. Without patches: periodic precursor. Six patches: external flow with halo-classified buildings. V2 parent-flow import preserves numerical and model qualification separately.","03 Physics"){}
    public override Guid ComponentGuid=>new("3c7b9535-cfa0-473e-8dbb-61c984374f15");
    protected override void RegisterInputParams(GH_InputParamManager p){
        p.AddGenericParameter("Case","C","Domain and physical properties from Case. External mode accepts closed geometry from Geometry, including a one-cell halo.",GH_ParamAccess.item);
        p.AddNumberParameter("Reference height","H","Metres above the rough wall, inside the channel",GH_ParamAccess.item,6d);
        p.AddNumberParameter("Roughness length","z0","Aerodynamic roughness in metres; less than half a cell",GH_ParamAccess.item,.01);
        p.AddNumberParameter("Smagorinsky constant","Cs","0 to 0.3",GH_ParamAccess.item,.17);
        p.AddNumberParameter("Perturbation fraction","P","Deterministic initial disturbance, 0 to 0.1; not a validated turbulence inlet",GH_ParamAccess.item,.02);
        p.AddBooleanParameter("Experimental","E","Enable the unvalidated research model explicitly",GH_ParamAccess.item,false);
        p.AddIntegerParameter("Wall sample index","S","0: first fluid plane; higher planes require clear fluid sampling",GH_ParamAccess.item,0);
        p.AddNumberParameter("Wall filter time","T","Reference-velocity exponential filter in seconds; zero disables",GH_ParamAccess.item,0d);
        p.AddGenericParameter("External patches","B","Optional six Boundary Patch objects. Absent means periodic precursor; present enables external mode.",GH_ParamAccess.list);p[8].Optional=true;
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Case","C","Experimental case for Solve/Record and v2 flow transfer; inspect quality and statistics",GH_ParamAccess.item);p.AddTextParameter("Report","R","Numerical method, wall placement and limits",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){
        if(Params.Input[8].SourceCount>0&&!Params.Input[8].VolatileData.AllData(true).Any(v=>v!=null)){InputsMissing();Message="waiting for patches";return;}
        bool enable=false;da.GetData(5,ref enable);if(!enable){InputsMissing();Message="experimental: off";return;}
        double h=6,z0=.01,cs=.17,perturb=.02;da.GetData(1,ref h);da.GetData(2,ref z0);da.GetData(3,ref cs);da.GetData(4,ref perturb);
        if(new[]{h,z0,cs,perturb}.Any(v=>!double.IsFinite(v)))throw new ArgumentException("Use finite physical parameters");
        var spec=ReadObject(da,0);spec["collision"]="shifted-regularized-sgs-v1";
        spec["boundaries"]=new JsonArray("periodic","periodic","periodic","periodic","wall","slip");
        spec["neutral_precursor"]=new JsonObject{["schema"]=1,["experimental"]=true,["reference_height_m"]=h,["roughness_length_m"]=z0,["smagorinsky_constant"]=cs,["perturbation_fraction"]=perturb};
        int sample=0;double filter=0;da.GetData(6,ref sample);da.GetData(7,ref filter);
        spec["neutral_precursor"]!["wall_sample_index"]=sample;spec["neutral_precursor"]!["wall_filter_seconds"]=filter;
        var inputs=new List<global::Grasshopper.Kernel.Types.IGH_Goo>();da.GetDataList(8,inputs);
        if(inputs.Count>0){
            var patches=new JsonArray();foreach(var input in inputs){var value=input is HawaGoo hgoo?hgoo:(input as global::Grasshopper.Kernel.Types.GH_ObjectWrapper)?.Value as HawaGoo;if(value==null)throw new ArgumentException("Use Boundary Patch objects");var patch=value.Data;patch.Remove("kind");patch.Remove("label");patches.Add(patch);}
            spec["neutral_precursor"]!["mode"]="external";spec["boundary_set"]=new JsonObject{["schema"]=1,["patches"]=patches};spec["boundary_method"]="shifted-links-v1";
        }
        var report=View(new JsonObject{["op"]="check",["case"]=spec});if(report==null)return;
        AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,"Experimental neutral model. V2 transfer uses numerical quality; inspect separate model/statistical limits. Walls lie half a cell outside the Z lattice planes.");
        da.SetData(0,new HawaGoo(spec));da.SetData(1,report.ToJsonString());
    }
}
