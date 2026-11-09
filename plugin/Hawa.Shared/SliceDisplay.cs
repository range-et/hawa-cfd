using System.Drawing;
using System.Text.Json.Nodes;
using Rhino.Geometry;
namespace Hawa.Shared;

public static class SliceDisplay
{
    public static Mesh Build(JsonObject data, JsonObject spec, string field,
        Func<double[],Point3d> world, Func<double,Color> color)
    {
        var points=data["coordinates"]!.AsArray().Select(p=>p!.AsArray().Select(v=>v!.GetValue<double>()).ToArray()).ToArray();
        var values=data["values"]!.AsArray().Select(v=>v!.GetValue<double>()).ToArray();
        var valid=data["valid"]!.AsArray().Select(v=>v!.GetValue<bool>()).ToArray();
        var shape=spec["shape"]?.AsArray().Select(v=>v!.GetValue<int>()).ToArray()??Array.Empty<int>();
        var mesh=new Mesh();var vertices=new Dictionary<(double,double,double,double),int>();
        foreach(var polygon in SliceCutCells.Polygons(points,values,valid,data["shape"]![0]!.GetValue<int>(),data["shape"]![1]!.GetValue<int>(),shape,spec["wall_links"]?.AsArray(),field)){
            var indices=new int[polygon.Length];
            for(int i=0;i<polygon.Length;i++){
                var vertex=polygon[i];var key=(vertex.Grid[0],vertex.Grid[1],vertex.Grid[2],vertex.Value);
                if(!vertices.TryGetValue(key,out int index)){index=mesh.Vertices.Add(world(vertex.Grid));mesh.VertexColors.Add(color(vertex.Value));vertices[key]=index;}
                indices[i]=index;
            }
            for(int i=1;i<polygon.Length-1;i++)mesh.Faces.AddFace(indices[0],indices[i],indices[i+1]);
        }
        mesh.Normals.ComputeNormals();return mesh;
    }
}
