using System.Drawing;
using System.Text.Json.Nodes;
using Rhino;
using Rhino.Display;
using Rhino.Geometry;
using Hawa.Shared;
namespace Hawa.Native;

public sealed class NativePreview : DisplayConduit, IDisposable
{
    private readonly Dictionary<uint, (Guid caseId, long version, UnitSystem units, Mesh? mesh)> cache = new();
    public NativePreview() { CaseHub.Changed += Changed; }
    private void Changed(CaseState c, string origin) { if (origin == "closed" && cache.Remove(c.Document, out var entry)) entry.mesh?.Dispose(); }
    public void Dispose() { Enabled = false; CaseHub.Changed -= Changed; foreach (var entry in cache.Values) entry.mesh?.Dispose(); cache.Clear(); }
    protected override void CalculateBoundingBox(CalculateBoundingBoxEventArgs e)
    {
        if (CaseHub.Find(e.RhinoDoc.RuntimeSerialNumber) == null) return;
        double s = RhinoMath.UnitScale(UnitSystem.Meters, e.RhinoDoc.ModelUnitSystem); e.IncludeBoundingBox(new BoundingBox(Point3d.Origin, new Point3d(8 * s, 6 * s, 4 * s)));
    }
    protected override void PostDrawObjects(DrawEventArgs e)
    {
        var c = CaseHub.Find(e.RhinoDoc.RuntimeSerialNumber); if (c == null) return;
        double s = RhinoMath.UnitScale(UnitSystem.Meters, e.RhinoDoc.ModelUnitSystem);
        double cell = c.Outdated ? c.ResultSpec?["dx"]?.GetValue<double>() ?? c.Cell : c.Cell;
        e.Display.DrawBox(new BoundingBox(Point3d.Origin, new Point3d(Math.Floor(8 / cell) * cell * s, Math.Floor(6 / cell) * cell * s, Math.Floor(4 / cell) * cell * s)), Color.FromArgb(65, 85, 95), 2);
        double h = (c.Outdated ? c.ResultSpec?["hawa_block_width"]?.GetValue<double>() ?? c.Width : c.Width) / 2; e.Display.DrawBox(new BoundingBox(new Point3d((3 - h) * s, (3 - h) * s, (2 - h) * s), new Point3d((3 + h) * s, (3 + h) * s, (2 + h) * s)), Color.DarkOrange, 2);
        if (!cache.TryGetValue(c.Document, out var entry) || entry.caseId != c.Id || entry.version != c.ResultVersion || entry.units != e.RhinoDoc.ModelUnitSystem)
        {
            entry.mesh?.Dispose(); entry = (c.Id, c.ResultVersion, e.RhinoDoc.ModelUnitSystem, CaseGeometry.ResultMesh(c)); cache[c.Document] = entry;
        }
        if (entry.mesh != null) e.Display.DrawMeshFalseColors(entry.mesh);
        e.Display.Draw2dText($"Hawa · {c.Result?.Field ?? c.Field} · field step {c.Result?.Steps ?? 0} / solver {c.Steps}" + (c.Outdated ? " · OUTDATED RESULT" : ""), Color.DarkSlateGray, new Point2d(20, 55), false, 16);
        foreach (var id in cache.Keys.Where(id => RhinoDoc.FromRuntimeSerialNumber(id) == null).ToArray()) { cache[id].mesh?.Dispose(); cache.Remove(id); }
    }
}
