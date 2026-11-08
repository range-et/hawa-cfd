using System.Drawing;
using System.Text.Json.Nodes;
using Rhino;
using Rhino.Display;
using Rhino.Geometry;
using Hawa.Shared;
namespace Hawa.Native;

public sealed class NativePreview : DisplayConduit
{
    private readonly Dictionary<uint, (JsonObject? source, Mesh? mesh)> cache = new();
    protected override void CalculateBoundingBox(CalculateBoundingBoxEventArgs e)
    {
        if (CaseHub.Find(e.RhinoDoc.RuntimeSerialNumber) == null) return;
        double s = RhinoMath.UnitScale(UnitSystem.Meters, e.RhinoDoc.ModelUnitSystem); e.IncludeBoundingBox(new BoundingBox(Point3d.Origin, new Point3d(8 * s, 6 * s, 4 * s)));
    }
    protected override void PostDrawObjects(DrawEventArgs e)
    {
        var c = CaseHub.Find(e.RhinoDoc.RuntimeSerialNumber); if (c == null) return;
        double s = RhinoMath.UnitScale(UnitSystem.Meters, e.RhinoDoc.ModelUnitSystem);
        e.Display.DrawBox(new BoundingBox(Point3d.Origin, new Point3d(Math.Floor(8 / c.Cell) * c.Cell * s, Math.Floor(6 / c.Cell) * c.Cell * s, Math.Floor(4 / c.Cell) * c.Cell * s)), Color.FromArgb(65, 85, 95), 2);
        double h = c.Width / 2; e.Display.DrawBox(new BoundingBox(new Point3d((3 - h) * s, (3 - h) * s, (2 - h) * s), new Point3d((3 + h) * s, (3 + h) * s, (2 + h) * s)), Color.DarkOrange, 2);
        if (!cache.TryGetValue(c.Document, out var entry) || !ReferenceEquals(entry.source, c.Slice))
        {
            entry.mesh?.Dispose(); entry = (c.Slice, CaseGeometry.ResultMesh(c)); cache[c.Document] = entry;
        }
        if (entry.mesh != null) e.Display.DrawMeshFalseColors(entry.mesh);
        e.Display.Draw2dText($"Hawa · {c.Field} · {c.Steps} steps" + (c.ResultRevision >= 0 && c.ResultRevision != c.Revision ? " · OUTDATED RESULT" : ""), Color.DarkSlateGray, new Point2d(20, 35), false, 16);
        foreach (var id in cache.Keys.Where(id => RhinoDoc.FromRuntimeSerialNumber(id) == null).ToArray()) { cache[id].mesh?.Dispose(); cache.Remove(id); }
    }
}
