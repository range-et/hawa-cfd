using System.Drawing;
using System.Text.Json.Nodes;
using Rhino.Geometry;

namespace Hawa.Shared;
public static class CaseGeometry
{
    public static JsonObject? SpecInModelUnits(CaseState c)
    {
        var spec = c.Spec;
        if (spec == null)
            return null;
        double scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters, Rhino.RhinoDoc.FromRuntimeSerialNumber(c.Document)!.ModelUnitSystem);
        spec["spacing"] = spec["dx"]!.GetValue<double>() * scale;
        if (spec["origin_m"] != null)
            spec["origin"] = new JsonArray(spec["origin_m"]!.AsArray().Select(v =>
                JsonValue.Create(v!.GetValue<double>() * scale)
            ).ToArray());
        return spec;
    }

    public static int[] GridShape(CaseState c) => c.SelectedGeometry ? NativeSettings.Shape(c.SetupData, c.Cell) : new[]
    {
        8d,
        6d,
        4d
    }.Select(v =>
        (int)Math.Floor(v / c.Cell) + 1
    ).ToArray();
    public static BoundingBox Bounds(CaseState c, bool result = false)
    {
        var spec = result && c.ResultSpecData != null ? c.ResultSpecData : new JsonObject
        {
            ["dx"] = c.Cell,
            ["origin_m"] = c.SelectedGeometry ? c.SetupData["origin"]!.DeepClone() : new JsonArray(0d, 0d, 0d),
            ["shape"] = new JsonArray(GridShape(c).Select(v =>
                JsonValue.Create(v)
            ).ToArray())
        };
        double scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters, Rhino.RhinoDoc.FromRuntimeSerialNumber(c.Document)!.ModelUnitSystem);
        var o = spec["origin_m"]?.AsArray().Select(v =>
            v!.GetValue<double>()
        ).ToArray() ?? new double[3];
        double dx = spec["dx"]!.GetValue<double>() * scale;
        var start = new Point3d(o[0] * scale, o[1] * scale, o[2] * scale);
        return new BoundingBox(start, start + new Vector3d((spec["shape"]![0]!.GetValue<int>() - 1) * dx, (spec["shape"]![1]!.GetValue<int>() - 1) * dx, (spec["shape"]![2]!.GetValue<int>() - 1) * dx));
    }

    public static string FieldUnits(string field) => field == "pressure" ? "Pa" : field == "density" ? "kg/m³" : "m/s";
    public static (double Min, double Max) Range(CaseState c)
    {
        if (!c.ViewData["auto_range"]!.GetValue<bool>())
            return (c.ViewData["min"]!.GetValue<double>(), c.ViewData["max"]!.GetValue<double>());
        if (c.SliceData == null)
            return (0, 1);
        var values = c.SliceData["values"]!.AsArray().Where((_, i) =>
            c.SliceData["valid"]![i]!.GetValue<bool>()
        ).Select(v =>
            v!.GetValue<double>()
        ).ToArray();
        return values.Length == 0 ? (0, 1) : ((c.Result?.Field == "speed" && c.ResultSpecData?["wall_links"] is JsonArray links && links.Count > 0 ? 0 : values.Min()), values.Max());
    }

    public static Color ColorAt(double t, string palette)
    {
        t = Math.Clamp(t, 0, 1);
        Color[] colors = palette switch
        {
            "spectrum" => new[]
            {
                Color.DarkBlue,
                Color.Cyan,
                Color.Lime,
                Color.Yellow,
                Color.Red
            },
            "diverging" => new[]
            {
                Color.RoyalBlue,
                Color.White,
                Color.Firebrick
            },
            _ => new[]
            {
                Color.FromArgb(8, 48, 107),
                Color.FromArgb(0, 160, 180),
                Color.FromArgb(150, 235, 140)
            }
        };
        double u = t * (colors.Length - 1);
        int i = Math.Min(colors.Length - 2, (int)u);
        double f = u - i;
        return Color.FromArgb((int)(colors[i].R * (1 - f) + colors[i + 1].R * f), (int)(colors[i].G * (1 - f) + colors[i + 1].G * f), (int)(colors[i].B * (1 - f) + colors[i + 1].B * f));
    }

    public static Mesh? ResultMesh(CaseState c)
    {
        if (c.SliceData == null || c.ResultSpecData == null)
            return null;
        var(lo, hi) = Range(c);
        double scale = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Meters, Rhino.RhinoDoc.FromRuntimeSerialNumber(c.Document)!.ModelUnitSystem);
        var origin = c.ResultSpecData["origin_m"]?.AsArray().Select(v =>
            v!.GetValue<double>() * scale
        ).ToArray() ?? new double[3];
        double dx = c.ResultSpecData["dx"]!.GetValue<double>() * scale;
        return SliceDisplay.Build(c.SliceData, c.ResultSpecData, c.Result?.Field ?? c.Field, p =>
            new Point3d(origin[0] + p[0] * dx, origin[1] + p[1] * dx, origin[2] + p[2] * dx)
        , v =>
            ColorAt(hi > lo ? (v - lo) / (hi - lo) : .5, c.ViewData["palette"]!.GetValue<string>())
        );
    }
}
