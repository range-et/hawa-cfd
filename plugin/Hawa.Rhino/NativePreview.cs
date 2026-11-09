using System.Drawing;
using System.Text.Json.Nodes;
using Rhino;
using Rhino.Display;
using Rhino.Geometry;
using Hawa.Shared;
namespace Hawa.Native;

public sealed class NativePreview : DisplayConduit, IDisposable
{
    private readonly Dictionary<uint, (Guid caseId, long version, UnitSystem units, Mesh? mesh, double low, double high)> cache = new();
    public NativePreview() { CaseHub.Changed += Changed; }
    private void Changed(CaseState c, string origin) { if (origin == "closed" && cache.Remove(c.Document, out var entry)) entry.mesh?.Dispose(); }
    public void Dispose() { Enabled = false; CaseHub.Changed -= Changed; foreach (var entry in cache.Values) entry.mesh?.Dispose(); cache.Clear(); }
    protected override void CalculateBoundingBox(CalculateBoundingBoxEventArgs e) {
        var c = CaseHub.Find(e.RhinoDoc.RuntimeSerialNumber); if (c != null) e.IncludeBoundingBox(CaseGeometry.Bounds(c,c.Outdated));
    }
    protected override void PostDrawObjects(DrawEventArgs e) {
        var c = CaseHub.Find(e.RhinoDoc.RuntimeSerialNumber); if (c == null) return;
        var view = c.View;
        if (!view["domain"]!.GetValue<bool>() && !view["body"]!.GetValue<bool>() && !view["field"]!.GetValue<bool>()) return;
        if (view["domain"]!.GetValue<bool>()) e.Display.DrawBox(CaseGeometry.Bounds(c,c.Outdated), Color.FromArgb(65,85,95),2);
        double s = RhinoMath.UnitScale(UnitSystem.Meters,e.RhinoDoc.ModelUnitSystem);
        if (view["body"]!.GetValue<bool>()) {
            if (!c.SelectedGeometry) {
                double h = (c.Outdated ? c.ResultSpec?["hawa_block_width"]?.GetValue<double>() ?? c.Width : c.Width)/2;
                e.Display.DrawBox(new BoundingBox(new Point3d((3-h)*s,(3-h)*s,(2-h)*s),new Point3d((3+h)*s,(3+h)*s,(2+h)*s)),Color.DarkOrange,2);
            } else if (!c.Outdated) foreach (var id in c.Setup["objects"]!.AsArray()) {
                var obj = e.RhinoDoc.Objects.FindId(Guid.Parse(id!.GetValue<string>()));
                if (obj != null) e.Display.DrawBox(obj.Geometry.GetBoundingBox(false),Color.DarkOrange,1);
            }
        }
        if (!cache.TryGetValue(c.Document,out var entry) || entry.caseId != c.Id || entry.version != c.ResultVersion || entry.units != e.RhinoDoc.ModelUnitSystem) {
            entry.mesh?.Dispose(); var range = CaseGeometry.Range(c); entry = (c.Id,c.ResultVersion,e.RhinoDoc.ModelUnitSystem,CaseGeometry.ResultMesh(c),range.Min,range.Max); cache[c.Document] = entry;
        }
        if (view["field"]!.GetValue<bool>() && entry.mesh != null) e.Display.DrawMeshFalseColors(entry.mesh);
        e.Display.Draw2dText($"Hawa · {c.Result?.Field ?? c.Field} · field {c.Result?.Steps ?? 0} / solver {c.Steps} · t={c.Result?.PhysicalTime ?? 0:g4} s" + (c.Outdated ? " · OUTDATED" : ""),Color.DarkSlateGray,new Point2d(20,55),false,14);
        if (view["field"]!.GetValue<bool>() && c.Result != null) {
            var (lo,hi) = (entry.low,entry.high);
            for (int i=0;i<5;i++) e.Display.Draw2dText($"■ {lo+(hi-lo)*i/4:g4}",CaseGeometry.ColorAt(i/4d,view["palette"]!.GetValue<string>()),new Point2d(20,80+i*20),false,13);
            e.Display.Draw2dText(CaseGeometry.FieldUnits(c.Result.Field)+(view["auto_range"]!.GetValue<bool>() ? " · auto range" : " · fixed range"),Color.DarkSlateGray,new Point2d(20,184),false,12);
            if(c.HasInterpolatedWalls)
                e.Display.Draw2dText(c.Result.Field=="speed"?"Clipped boundary · stationary wall speed = 0":"Clipped boundary · colours use adjacent fluid samples",Color.DarkSlateGray,new Point2d(20,207),false,12);
        }
    }
}
