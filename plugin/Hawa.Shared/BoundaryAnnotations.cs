using System.Drawing;
using System.Runtime.CompilerServices;
using System.Text.Json.Nodes;
using Rhino.Display;
using Rhino.Geometry;

namespace Hawa.Shared;

public sealed record BoundaryMark(Point3d Anchor, string Text, Color Color, Line? Arrow = null, Line? Tick = null, bool Dotted = false);
public sealed record BoundaryAnnotationSet(IReadOnlyList<BoundaryMark> Marks, IReadOnlyList<Line> Pairs, BoundingBox Bounds);

// Ephemeral viewport annotations of accepted boundary assignments, shared by the
// native preview and the Grasshopper Case/Boundary Set previews. Display only:
// no picking, editing, document geometry or physics change. Arrows and normal
// ticks stay inside the domain box, so the preview bounds equal the domain.
public static class BoundaryAnnotations
{
    public static readonly string[] Faces = { "x-", "x+", "y-", "y+", "z-", "z+" };
    public static readonly BoundaryAnnotationSet None = new(Array.Empty<BoundaryMark>(), Array.Empty<Line>(), BoundingBox.Empty);
    static readonly string[] LegacyDefault = { "inlet", "outlet", "periodic", "periodic", "wall", "slip" };
    public static readonly Color Velocity = Color.FromArgb(25, 105, 210), Pressure = Color.FromArgb(135, 60, 175), Open = Color.FromArgb(0, 135, 125), Wall = Color.FromArgb(85, 85, 85), Slip = Color.FromArgb(160, 115, 30), Periodic = Color.FromArgb(40, 140, 60);
    static readonly ConditionalWeakTable<string, BoundaryAnnotationSet> parsed = new();
    readonly record struct Frame(Point3d Origin, Vector3d[] Axes, double[] Lengths);

    // Native cases are axis-aligned and use the six legacy face strings.
    public static BoundaryAnnotationSet ForNative(CaseState c)
    {
        var b = CaseGeometry.Bounds(c);
        var d = b.Diagonal;
        return Build(new Frame(b.Min, new[] { Vector3d.XAxis, Vector3d.YAxis, Vector3d.ZAxis }, new[] { d.X, d.Y, d.Z }), c.Setup["boundaries"]!.AsArray(), null, c.Speed);
    }

    // Grasshopper case JSON: NEE patches win; otherwise legacy strings or the plugin default.
    // Cached per JSON text instance so a redraw does not reparse large solid lists.
    public static BoundaryAnnotationSet ForCase(string json) => parsed.GetValue(json, Parse);

    static BoundaryAnnotationSet Parse(string json)
    {
        var c = JsonNode.Parse(json)!.AsObject();
        if (c["origin"] is not JsonArray o || c["basis"] is not JsonArray basis || c["shape"] is not JsonArray shape || c["spacing"] == null)
            return None;
        double dx = c["spacing"]!.GetValue<double>();
        var axes = basis.Select(v =>
            new Vector3d(v![0]!.GetValue<double>(), v[1]!.GetValue<double>(), v[2]!.GetValue<double>())
        ).ToArray();
        var lengths = shape.Select(n =>
            (n!.GetValue<int>() - 1) * dx
        ).ToArray();
        var frame = new Frame(new Point3d(o[0]!.GetValue<double>(), o[1]!.GetValue<double>(), o[2]!.GetValue<double>()), axes, lengths);
        return Build(frame, c["boundaries"] as JsonArray, c["boundary_set"]?["patches"] as JsonArray, c["speed"]?.GetValue<double>());
    }

    static BoundaryAnnotationSet Build(Frame f, JsonArray? legacy, JsonArray? patches, double? speed)
    {
        var marks = new List<BoundaryMark>();
        var types = new string[6];
        double l = .2 * f.Lengths.Min();
        if (patches != null)
            foreach (var node in patches)
            {
                int face = Array.IndexOf(Faces, node!["face"]!.GetValue<string>());
                var condition = node["condition"]!.AsObject();
                types[face] = condition["type"]!.GetValue<string>();
                marks.Add(Patch(f, face, node["id"]!.GetValue<string>(), types[face], condition, l));
            }
        else
            for (int i = 0; i < 6; i++)
            {
                types[i] = legacy?[i]!.GetValue<string>() ?? LegacyDefault[i];
                marks.Add(Legacy(f, i, types[i], speed, l));
            }
        var pairs = new List<Line>();
        for (int a = 0; a < 3; a++)
            if (types[2 * a] == "periodic" && types[2 * a + 1] == "periodic")
                pairs.Add(new Line(Anchor(f, 2 * a), Anchor(f, 2 * a + 1)));
        var corners = new List<Point3d>();
        for (int i = 0; i < 8; i++)
            corners.Add(At(f, i & 1, i >> 1 & 1, i >> 2));
        return new(marks, pairs, new BoundingBox(corners));
    }

    static BoundaryMark Legacy(Frame f, int face, string type, double? speed, double l)
    {
        string name = Faces[face].ToUpperInvariant();
        return type switch
        {
            "inlet" => new(Anchor(f, face), $"{name} inlet · +X" + (speed is double u ? $" {u:g3} m/s" : ""), Velocity, Arrow(f, face, f.Axes[0], l)),
            "outlet" => new(Anchor(f, face), $"{name} outlet · open, extrapolated", Open, Tick: Tick(f, face, l), Dotted: true),
            "periodic" => new(Anchor(f, face), $"{name} periodic ↔ {Faces[face ^ 1].ToUpperInvariant()}", Periodic),
            _ => new(Anchor(f, face), $"{name} {type}", type == "slip" ? Slip : Wall)
        };
    }

    static BoundaryMark Patch(Frame f, int face, string id, string type, JsonObject c, double l)
    {
        var u = c["velocity"]?.AsArray().Select(v =>
            v!.GetValue<double>()
        ).ToArray() ?? new double[3];
        var world = f.Axes[0] * u[0] + f.Axes[1] * u[1] + f.Axes[2] * u[2];
        Line? arrow = world.Length > 0 ? Arrow(f, face, world, l) : null;
        var anchor = Anchor(f, face);
        return type switch
        {
            "velocity" => new(anchor, $"{id} velocity · {world.Length:g3} m/s {c["profile"]?.GetValue<string>()}".TrimEnd(), Velocity, arrow),
            "wall" => new(anchor, arrow == null ? $"{id} wall" : $"{id} wall · moving {world.Length:g3} m/s", Wall, arrow),
            "pressure" => new(anchor, $"{id} pressure reference · {c["pressure_pa"]!.GetValue<double>():g3} Pa gauge", Pressure, Tick: Tick(f, face, l)),
            "open" => new(anchor, $"{id} open/pressure reference · {c["pressure_pa"]!.GetValue<double>():g3} Pa gauge", Open, Tick: Tick(f, face, l), Dotted: true),
            "periodic" => new(anchor, $"{id} periodic ↔ {Faces[face ^ 1]}", Periodic),
            _ => new(anchor, $"{id} {type}", Slip)
        };
    }

    static Point3d At(Frame f, double x, double y, double z) => f.Origin + f.Axes[0] * (x * f.Lengths[0]) + f.Axes[1] * (y * f.Lengths[1]) + f.Axes[2] * (z * f.Lengths[2]);
    static Point3d Anchor(Frame f, int face)
    {
        var t = new[] { .5, .5, .5 };
        t[face / 2] = face % 2;
        return At(f, t[0], t[1], t[2]);
    }

    static Vector3d Normal(Frame f, int face) => f.Axes[face / 2] * (face % 2 == 1 ? 1 : -1);
    // The arrow shows direction only; an outward vector ends at the face instead of leaving the box.
    static Line Arrow(Frame f, int face, Vector3d direction, double l)
    {
        var d = direction;
        d.Unitize();
        d *= l;
        var anchor = Anchor(f, face);
        return d * Normal(f, face) > 0 ? new Line(anchor + d * -1, anchor) : new Line(anchor, anchor + d);
    }

    // Inward normal tick: marks the face type without implying a flow direction.
    static Line Tick(Frame f, int face, double l) => new(Anchor(f, face), Anchor(f, face) + Normal(f, face) * (-l / 2));
    public static void Draw(DisplayPipeline display, BoundaryAnnotationSet a)
    {
        foreach (var pair in a.Pairs)
            display.DrawDottedLine(pair.From, pair.To, Periodic);
        foreach (var m in a.Marks)
        {
            if (m.Arrow is Line arrow)
                display.DrawArrow(arrow, m.Color);
            if (m.Tick is Line tick && m.Dotted)
                display.DrawDottedLine(tick.From, tick.To, m.Color);
            else if (m.Tick is Line solid)
                display.DrawLine(solid.From, solid.To, m.Color, 3);
            display.DrawDot(m.Anchor, m.Text, m.Color, Color.White);
        }
    }
}
