using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;
namespace Hawa.Grasshopper;

public sealed class WallRoughnessComponent:HawaQueryComponent {
    public WallRoughnessComponent():base("Hawa Wall Roughness","Roughness","Assign aerodynamic roughness to planar ground regions. Physical metres; last region wins. Does not create waves or displacement geometry.","03 Physics"){}
    public override Guid ComponentGuid=>new("3c7b9535-cfa0-473e-8dbb-61c984374f16");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Case","C","Neutral Flow case",GH_ParamAccess.item);p.AddRectangleParameter("Regions","R","Rectangles parallel to the domain ground; projected onto Z-",GH_ParamAccess.list);p.AddNumberParameter("Roughness lengths","z0","One metre value per region, or one shared value; 0 < z0 < dx/2",GH_ParamAccess.list,.001);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Case","C","Case with ground material field",GH_ParamAccess.item);p.AddTextParameter("Report","R","Coverage, order and limits",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){
        var spec=ReadObject(da,0);var regions=new List<Rectangle3d>();var lengths=new List<double>();da.GetDataList(1,regions);da.GetDataList(2,lengths);
        if(lengths.Count!=1&&lengths.Count!=regions.Count)throw new ArgumentException("Use one roughness or one value per region");
        var world=new JsonObject{["case"]=spec.DeepClone()};var rows=new JsonArray();
        for(int i=0;i<regions.Count;i++){
            if(!regions[i].IsValid)throw new ArgumentException("Valid ground rectangles required");
            var points=Enumerable.Range(0,4).Select(k=>Coordinates.Grid(world,regions[i].Corner(k))).ToArray();
            var zs=points.Select(p=>p[2]!.GetValue<double>()).ToArray();if(zs.Max()-zs.Min()>1e-7)throw new ArgumentException("Roughness regions must be parallel to the ground plane");
            rows.Add(new JsonObject{["polygon"]=new JsonArray(points.Select(p=>(JsonNode)new JsonArray(p[0]!.DeepClone(),p[1]!.DeepClone())).ToArray()),["length_m"]=lengths.Count==1?lengths[0]:lengths[i]});
        }
        var result=View(new JsonObject{["op"]="wall_roughness",["case"]=spec,["regions"]=rows});if(result==null)return;da.SetData(0,new HawaGoo(result["case"]!.AsObject()));da.SetData(1,result["report"]!.ToJsonString());
    }
}

public sealed class FlowStatisticsComponent:HawaQueryComponent {
    public FlowStatisticsComponent():base("Hawa Flow Statistics","Statistics","Probe means, Reynolds covariance, resolved TKE, spectra and approximate mean uncertainty from a completed timed recording. Shows statistical adequacy separately from numerical health.","06 Results"){}
    public override Guid ComponentGuid=>new("3c7b9535-cfa0-473e-8dbb-61c984374f17");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddTextParameter("Manifest","M","Completed recording manifest",GH_ParamAccess.item);p.AddGenericParameter("Frame","F","Playback frame from this recording, for model coordinates",GH_ParamAccess.item);p.AddPointParameter("Probes","P","1..200 fluid points in model coordinates",GH_ParamAccess.list);p.AddNumberParameter("Start time","T0","Discard frames before this parent-relative time [s]",GH_ParamAccess.item,0d);p.AddNumberParameter("End time","T1","Negative selects recording end [s]",GH_ParamAccess.item,-1d);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddVectorParameter("Mean velocity","U","World-axis m/s",GH_ParamAccess.list);p.AddNumberParameter("Mean pressure","P","Gauge Pa",GH_ParamAccess.list);p.AddNumberParameter("Resolved TKE","k","Resolved kinetic energy [m2/s2]",GH_ParamAccess.list);p.AddTextParameter("Report","R","Sampling status, time window, uncertainty and limitations",GH_ParamAccess.item);p.AddGenericParameter("Statistics","S","Full covariance, spectra and source identity; tensor components use case axes",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){
        string manifest="";double start=0,end=-1;da.GetData(0,ref manifest);var frame=ReadObject(da,1);var world=FieldTools.World(frame);var probes=new List<Point3d>();da.GetDataList(2,probes);da.GetData(3,ref start);da.GetData(4,ref end);
        var r=View(new JsonObject{["op"]="statistics",["manifest"]=LocalPath(manifest),["points"]=new JsonArray(probes.Select(p=>(JsonNode)Coordinates.Grid(world,p)).ToArray()),["start_time"]=start,["end_time"]=end<0?null:JsonValue.Create(end)});if(r==null)return;
        if(r["case"]!.ToJsonString()!=frame["case"]!.ToJsonString())throw new ArgumentException("Playback frame and statistics recording belong to different cases");
        da.SetDataList(0,r["mean_velocity"]!.AsArray().Select(v=>Coordinates.Velocity(world,v!)));da.SetDataList(1,r["mean_pressure"]!.AsArray().Select(v=>v!.GetValue<double>()));da.SetDataList(2,r["resolved_tke"]!.AsArray().Select(v=>v!.GetValue<double>()));
        var summary=(JsonObject)r.DeepClone();foreach(var key in new[]{"case","source","velocity_psd","frequency_hz"})summary.Remove(key);da.SetData(3,summary.ToJsonString());da.SetData(4,new HawaGoo(r));
        Message=r["status"]!.GetValue<string>();foreach(var warning in r["warnings"]!.AsArray())AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,warning!.GetValue<string>());
    }
}
