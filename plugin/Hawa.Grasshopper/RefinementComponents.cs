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
