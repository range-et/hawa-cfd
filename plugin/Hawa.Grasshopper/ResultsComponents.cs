using System.Drawing;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Hawa.Grasshopper;

internal static class Coordinates
{
    internal static double[] Origin(JsonObject solution) => solution["case"]!["origin"]?.AsArray().Select(x => x!.GetValue<double>()).ToArray() ?? new double[3];
    internal static double Spacing(JsonObject solution) => solution["case"]!["spacing"]?.GetValue<double>() ?? 1;
    internal static Vector3d Axis(JsonObject s, int i) { var basis = s["case"]!["basis"]; if (basis == null) return i == 0 ? Vector3d.XAxis : i == 1 ? Vector3d.YAxis : Vector3d.ZAxis; var a = basis[i]!; return new Vector3d(a[0]!.GetValue<double>(), a[1]!.GetValue<double>(), a[2]!.GetValue<double>()); }
    internal static Point3d World(JsonObject s, JsonNode p) { var o = Origin(s); var d = Spacing(s); return new Point3d(o[0], o[1], o[2]) + d * (Axis(s, 0) * p[0]!.GetValue<double>() + Axis(s, 1) * p[1]!.GetValue<double>() + Axis(s, 2) * p[2]!.GetValue<double>()); }
    internal static JsonArray Grid(JsonObject s, Point3d p) { var o = Origin(s); var d = Spacing(s); var delta = p - new Point3d(o[0], o[1], o[2]); return new JsonArray(delta * Axis(s, 0) / d, delta * Axis(s, 1) / d, delta * Axis(s, 2) / d); }
    internal static Vector3d Velocity(JsonObject s, JsonNode v) => Axis(s, 0) * v[0]!.GetValue<double>() + Axis(s, 1) * v[1]!.GetValue<double>() + Axis(s, 2) * v[2]!.GetValue<double>();
}

public sealed class SliceComponent : HawaComponent
{
    public SliceComponent() : base("Hawa Slice", "Slice", "Colored field slice. Speed in m/s, pressure in Pa, density in kg/m³ for physical wind cases.", "07 Visualize") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077111");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddGenericParameter("Solution", "S", "Hawa Solution", GH_ParamAccess.item); p.AddIntegerParameter("Axis", "A", "Normal: 0=X, 1=Y, 2=Z", GH_ParamAccess.item, 2); p.AddIntegerParameter("Index", "I", "Grid slice index; -1 selects center", GH_ParamAccess.item, -1); p.AddTextParameter("Field", "F", "speed, pressure or density", GH_ParamAccess.item, "speed"); p.AddBooleanParameter("Mean", "M", "Use sampled mean velocity", GH_ParamAccess.item, false); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddMeshParameter("Mesh", "M", "Colored slice mesh", GH_ParamAccess.item); p.AddNumberParameter("Values", "V", "Field values; masked sites are zero", GH_ParamAccess.list); p.AddNumberParameter("Range", "R", "Color legend minimum and maximum", GH_ParamAccess.list); p.AddBooleanParameter("Valid", "Valid", "Fluid sites; solid geometry is excluded", GH_ParamAccess.list); }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        var s = ReadObject(da, 0); int axis = 2, index = -1; string field = "speed"; bool mean = false; da.GetData(1, ref axis); da.GetData(2, ref index); da.GetData(3, ref field); da.GetData(4, ref mean);
        var req = Request("slice", s["session"]!.GetValue<string>()); req["axis"] = axis; if (index >= 0) req["index"] = index; req["field"] = field; req["mean"] = mean;
        var data = EmbeddedRuntime.Call(req); var values = data["values"]!.AsArray().Select(v => v!.GetValue<double>()).ToArray();
        var valid = data["valid"]!.AsArray().Select(v => v!.GetValue<bool>()).ToArray();
        var shape = data["shape"]!.AsArray().Select(v => v!.GetValue<int>()).ToArray(); var mesh = new Mesh(); var fluid = values.Where((v, i) => valid[i]).ToArray(); var min = fluid.Length > 0 ? fluid.Min() : 0; var max = fluid.Length > 0 ? fluid.Max() : 0;
        var points = data["coordinates"]!.AsArray();
        for (int i = 0; i < points.Count; i++) { mesh.Vertices.Add(Coordinates.World(s, points[i]!)); double t = Math.Clamp(max > min ? (values[i] - min) / (max - min) : .5, 0, 1); mesh.VertexColors.Add(Color.FromArgb((int)(255 * t), (int)(100 * (1 - Math.Abs(2 * t - 1))), (int)(255 * (1 - t)))); }
        for (int a = 0; a < shape[0] - 1; a++) for (int b = 0; b < shape[1] - 1; b++) { int i = a * shape[1] + b; if (valid[i] && valid[i + shape[1]] && valid[i + shape[1] + 1] && valid[i + 1]) mesh.Faces.AddFace(i, i + shape[1], i + shape[1] + 1, i + 1); }
        mesh.Normals.ComputeNormals(); da.SetData(0, mesh); da.SetDataList(1, values); da.SetDataList(2, new[] { min, max }); da.SetDataList(3, valid);
    }
}

public sealed class SampleComponent : HawaComponent
{
    public SampleComponent() : base("Hawa Sample", "Sample", "Trilinear interpolation at Rhino points. Out-of-domain points return a validity flag.", "06 Results") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077112");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddGenericParameter("Solution", "S", "Hawa Solution", GH_ParamAccess.item); p.AddPointParameter("Points", "P", "Sample locations in model coordinates", GH_ParamAccess.list); p.AddBooleanParameter("Mean", "M", "Use sampled mean velocity", GH_ParamAccess.item, false); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddVectorParameter("Velocity", "U", "Physical velocity vectors", GH_ParamAccess.list); p.AddNumberParameter("Pressure", "P", "Physical pressure", GH_ParamAccess.list); p.AddBooleanParameter("Valid", "V", "Point lies inside the lattice", GH_ParamAccess.list); }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        var s = ReadObject(da, 0); var points = new List<Point3d>(); bool mean = false; da.GetDataList(1, points); da.GetData(2, ref mean);
        var r = Request("sample", s["session"]!.GetValue<string>()); r["points"] = new JsonArray(points.Select(p => (JsonNode)Coordinates.Grid(s, p)).ToArray()); r["mean"] = mean;
        var values = EmbeddedRuntime.Call(r)["values"]!.AsArray(); var u = new List<Vector3d>(); var pressure = new List<double>(); var valid = new List<bool>();
        foreach (var value in values) { valid.Add(value != null); if (value == null) { u.Add(Vector3d.Unset); pressure.Add(double.NaN); } else { u.Add(Coordinates.Velocity(s, value["velocity"]!)); pressure.Add(value["pressure"]!.GetValue<double>()); } }
        da.SetDataList(0, u); da.SetDataList(1, pressure); da.SetDataList(2, valid);
    }
}

public sealed class VectorsComponent : HawaComponent
{
    public VectorsComponent() : base("Hawa Vectors", "Vectors", "Velocity segments for field visualization; lengths are scaled for display", "07 Visualize") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077113");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddPointParameter("Points", "P", "Sample points", GH_ParamAccess.list); p.AddVectorParameter("Velocity", "U", "Vectors from Hawa Sample", GH_ParamAccess.list); p.AddNumberParameter("Scale", "S", "Model length per velocity unit", GH_ParamAccess.item, 1); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddLineParameter("Lines", "L", "Velocity segments", GH_ParamAccess.list); }
    protected override void SolveHawa(IGH_DataAccess da) { var points = new List<Point3d>(); var u = new List<Vector3d>(); double scale = 1; da.GetDataList(0, points); da.GetDataList(1, u); da.GetData(2, ref scale); if (points.Count != u.Count) throw new ArgumentException("Point and velocity counts differ"); da.SetDataList(0, points.Zip(u).Where(p => p.Second.IsValid).Select(p => new Line(p.First, p.First + p.Second * scale))); }
}

public sealed class StreamlinesComponent : HawaComponent
{
    public StreamlinesComponent() : base("Hawa Streamlines", "Streamlines", "Instantaneous streamlines using midpoint integration on a field snapshot", "07 Visualize") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077114");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddGenericParameter("Solution", "S", "Hawa Solution", GH_ParamAccess.item); p.AddPointParameter("Seeds", "P", "Up to 200 seed points", GH_ParamAccess.list); p.AddIntegerParameter("Steps", "N", "Integration steps, at most 1000", GH_ParamAccess.item, 100); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddCurveParameter("Streamlines", "C", "Snapshot streamlines (not particle pathlines)", GH_ParamAccess.list); }
    protected override void SolveHawa(IGH_DataAccess da) { var s = ReadObject(da, 0); var seeds = new List<Point3d>(); int steps = 100; da.GetDataList(1, seeds); da.GetData(2, ref steps); var r = Request("streamlines", s["session"]!.GetValue<string>()); r["seeds"] = new JsonArray(seeds.Select(p => (JsonNode)Coordinates.Grid(s, p)).ToArray()); r["steps"] = steps; var paths = EmbeddedRuntime.Call(r)["paths"]!.AsArray(); da.SetDataList(0, paths.Where(p => p!.AsArray().Count >= 2).Select(p => new PolylineCurve(p!.AsArray().Select(v => Coordinates.World(s, v!))))); }
}
