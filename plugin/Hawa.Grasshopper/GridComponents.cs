using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;
namespace Hawa.Grasshopper;

public sealed class GridPreviewComponent:HawaComponent {
    public GridPreviewComponent():base("Hawa Grid Preview","Grid","Show exposed voxel faces and occupied volume. Limit 50000 solid sites.","02 Geometry"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077135");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Geometry","G","Voxelized geometry",GH_ParamAccess.item);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddMeshParameter("Voxels","M","Exposed voxel faces",GH_ParamAccess.item);p.AddNumberParameter("Volume","V","Occupied volume in m³",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){var g=ReadObject(da,0);var domain=g["domain"]!.AsObject();var world=new JsonObject{["case"]=domain.DeepClone()};var n=domain["shape"]!.AsArray().Select(v=>v!.GetValue<int>()).ToArray();var solid=g["solid"]!.AsArray().Select(v=>v!.GetValue<int>()).ToHashSet();if(solid.Count>50000)throw new ArgumentException("Grid preview limited to 50000 occupied sites");var mesh=new Mesh();foreach(int index in solid){int x=index/(n[1]*n[2]),y=index/n[2]%n[1],z=index%n[2];int[] p={x,y,z};for(int axis=0;axis<3;axis++)foreach(int sign in new[]{-1,1}){var neighbor=(int[])p.Clone();neighbor[axis]+=sign;bool inside=Enumerable.Range(0,3).All(a=>neighbor[a]>=0&&neighbor[a]<n[a]);if(inside&&solid.Contains((neighbor[0]*n[1]+neighbor[1])*n[2]+neighbor[2]))continue;int start=mesh.Vertices.Count;foreach(var corner in new[]{new[]{-1,-1},new[]{1,-1},new[]{1,1},new[]{-1,1}}){var q=p.Select(v=>(double)v).ToArray();q[axis]+=.5*sign;q[(axis+1)%3]+=.5*corner[0];q[(axis+2)%3]+=.5*corner[1];mesh.Vertices.Add(Coordinates.World(world,new JsonArray(q[0],q[1],q[2])));}if(sign>0)mesh.Faces.AddFace(start,start+1,start+2,start+3);else mesh.Faces.AddFace(start+3,start+2,start+1,start);}}mesh.Normals.ComputeNormals();da.SetData(0,mesh);double dx=domain["dx"]!.GetValue<double>();da.SetData(1,solid.Count*dx*dx*dx);}
}
