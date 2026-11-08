using System.Drawing;
using System.Text.Json.Nodes;
using Rhino.Geometry;
namespace Hawa.Shared;

public static class CaseGeometry
{
    public static Mesh? ResultMesh(CaseState c)
    {
        if (c.Slice == null || c.ResultSpec == null) return null;
        var data = c.Slice; var values = data["values"]!.AsArray().Select(x => x!.GetValue<double>()).ToArray(); var valid = data["valid"]!.AsArray().Select(x => x!.GetValue<bool>()).ToArray();
        var range = values.Where((_, i) => valid[i]).ToArray(); double lo = range.Length == 0 ? 0 : range.Min(), hi = range.Length == 0 ? 1 : range.Max();
        double dx = c.ResultSpec["spacing"]!.GetValue<double>(); var mesh = new Mesh(); int k = 0;
        foreach (var p in data["coordinates"]!.AsArray())
        {
            mesh.Vertices.Add(p![0]!.GetValue<double>() * dx, p[1]!.GetValue<double>() * dx, p[2]!.GetValue<double>() * dx);
            double t = hi > lo ? Math.Clamp((values[k++] - lo) / (hi - lo), 0, 1) : .5; Color a = t < .5 ? Color.FromArgb(8, 48, 107) : Color.FromArgb(0, 160, 180), b = t < .5 ? Color.FromArgb(0, 160, 180) : Color.FromArgb(150, 235, 140); double f = t < .5 ? t * 2 : (t - .5) * 2;
            mesh.VertexColors.Add(Color.FromArgb((int)(a.R + (b.R - a.R) * f), (int)(a.G + (b.G - a.G) * f), (int)(a.B + (b.B - a.B) * f)));
        }
        int nx = data["shape"]![0]!.GetValue<int>(), ny = data["shape"]![1]!.GetValue<int>();
        for (int x = 0; x < nx - 1; x++) for (int y = 0; y < ny - 1; y++) { int a = x * ny + y; if (valid[a] && valid[a + ny] && valid[a + ny + 1] && valid[a + 1]) mesh.Faces.AddFace(a, a + ny, a + ny + 1, a + 1); }
        mesh.Normals.ComputeNormals(); return mesh;
    }
}
