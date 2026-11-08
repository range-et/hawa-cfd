using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;
namespace Hawa.Grasshopper;

public sealed class GeometryCheckComponent:HawaComponent {
    public GeometryCheckComponent():base("Hawa Geometry Check","GeoCheck","Report mesh closure, naked edges, dimensions, and mesh volume before voxelization","02 Geometry"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077134");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddMeshParameter("Meshes","M","Obstacles",GH_ParamAccess.list);p.AddNumberParameter("Spacing","dx","Proposed cell size in model units",GH_ParamAccess.item,1);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddBooleanParameter("Closed valid","V","Basic geometry check",GH_ParamAccess.list);p.AddCurveParameter("Open edges","E","Naked mesh edges",GH_ParamAccess.list);p.AddTextParameter("Report","R","Dimensions and volume",GH_ParamAccess.list);}
    protected override void SolveHawa(IGH_DataAccess da){var meshes=new List<Mesh>();double dx=1;da.GetDataList(0,meshes);da.GetData(1,ref dx);if(!double.IsFinite(dx)||dx<=0)throw new ArgumentException("Spacing must be positive");var reports=new List<string>();var edges=new List<Curve>();foreach(var m in meshes){var b=m.GetBoundingBox(true);var size=b.Diagonal;var naked=m.GetNakedEdges();if(naked!=null)edges.AddRange(naked.Select(p=>new PolylineCurve(p)));double volume=m.IsClosed?Math.Abs(VolumeMassProperties.Compute(m)?.Volume??0):0;reports.Add($"Closed={m.IsClosed}; Valid={m.IsValid}; volume={volume:g7}; cells across bounds={size.X/dx:g3}, {size.Y/dx:g3}, {size.Z/dx:g3}. Internal thin features require grid inspection.");}da.SetDataList(0,meshes.Select(m=>m.IsClosed&&m.IsValid));da.SetDataList(1,edges);da.SetDataList(2,reports);}
}

public sealed class GridPreviewComponent:HawaComponent {
    public GridPreviewComponent():base("Hawa Grid Preview","Grid","Show exposed voxel faces and occupied volume. Limit 50000 solid sites.","02 Geometry"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077135");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Geometry","G","Voxelized geometry",GH_ParamAccess.item);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddMeshParameter("Voxels","M","Exposed voxel faces",GH_ParamAccess.item);p.AddNumberParameter("Volume","V","Occupied volume in m³",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){var g=ReadObject(da,0);var domain=g["domain"]!.AsObject();var world=new JsonObject{["case"]=domain.DeepClone()};var n=domain["shape"]!.AsArray().Select(v=>v!.GetValue<int>()).ToArray();var solid=g["solid"]!.AsArray().Select(v=>v!.GetValue<int>()).ToHashSet();if(solid.Count>50000)throw new ArgumentException("Grid preview limited to 50000 occupied sites");var mesh=new Mesh();foreach(int index in solid){int x=index/(n[1]*n[2]),y=index/n[2]%n[1],z=index%n[2];int[] p={x,y,z};for(int axis=0;axis<3;axis++)foreach(int sign in new[]{-1,1}){var neighbor=(int[])p.Clone();neighbor[axis]+=sign;bool inside=Enumerable.Range(0,3).All(a=>neighbor[a]>=0&&neighbor[a]<n[a]);if(inside&&solid.Contains((neighbor[0]*n[1]+neighbor[1])*n[2]+neighbor[2]))continue;int start=mesh.Vertices.Count;foreach(var corner in new[]{new[]{-1,-1},new[]{1,-1},new[]{1,1},new[]{-1,1}}){var q=p.Select(v=>(double)v).ToArray();q[axis]+=.5*sign;q[(axis+1)%3]+=.5*corner[0];q[(axis+2)%3]+=.5*corner[1];mesh.Vertices.Add(Coordinates.World(world,new JsonArray(q[0],q[1],q[2])));}if(sign>0)mesh.Faces.AddFace(start,start+1,start+2,start+3);else mesh.Faces.AddFace(start+3,start+2,start+1,start);}}mesh.Normals.ComputeNormals();da.SetData(0,mesh);double dx=domain["dx"]!.GetValue<double>();da.SetData(1,solid.Count*dx*dx*dx);}
}
