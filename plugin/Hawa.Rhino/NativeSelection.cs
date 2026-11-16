using System.Text.Json.Nodes;
using Hawa.Shared;
using Rhino;
using Rhino.Geometry;

namespace Hawa.Native;
public static partial class NativeGeometry
{
    public static void SelectObjects(uint serial, IEnumerable<Guid> objectIds, bool fitDomain)
    {
        if (RhinoApp.InvokeRequired)
            throw new InvalidOperationException("Hawa selection must run on Rhino's UI thread");
        var doc = RhinoDoc.FromRuntimeSerialNumber(serial) ?? throw new InvalidOperationException("Document closed");
        var ids = objectIds.Distinct().ToArray();
        if (ids.Length == 0 || ids.Length > 100)
            throw new ArgumentException("Select 1..100 closed meshes or solids");
        var bounds = BoundingBox.Empty;
        foreach (var id in ids)
        {
            var obj = doc.Objects.FindId(id) ?? throw new ArgumentException("A selected object no longer exists");
            CheckGeometry(obj.Geometry);
            bounds.Union(obj.Geometry.GetBoundingBox(true));
        }

        double scale = RhinoMath.UnitScale(doc.ModelUnitSystem, UnitSystem.Meters);
        bounds.Transform(Transform.Scale(Point3d.Origin, scale));
        var c = CaseHub.Find(serial) ?? new CaseState();
        var setup = c.Setup;
        setup["mode"] = "selected";
        setup["objects"] = new JsonArray(ids.Select(id =>
        {
            return JsonValue.Create(id.ToString());
        }).ToArray());
        if (fitDomain)
            Fit(setup, bounds, c.Cell);
        // Reject geometry/domain errors before publishing a first case or preview.
        var settings = c.Settings();
        settings["setup"] = JsonNode.Parse(setup.ToJsonString());
        CaseHub.Validate(settings);
        CaseHub.Get(serial);
        CaseHub.Edit(serial, new() { ["setup"] = setup }, c.Version);
    }

    public static void FitDomain(uint serial)
    {
        var c = CaseHub.Find(serial);
        if (c == null || !c.SelectedGeometry)
            throw new ArgumentException("Select Rhino geometry first");
        SelectObjects(serial, c.Setup["objects"]!.AsArray().Select(v =>
        {
            return Guid.Parse(v!.GetValue<string>());
        }), true);
    }

    private static void Fit(JsonObject setup, BoundingBox b, double cell)
    {
        double h = Math.Max(cell * 2, Math.Max(b.Diagonal.Y, b.Diagonal.Z));
        var origin = b.Min - new Vector3d(2 * h, h, h);
        var end = b.Max + new Vector3d(4 * h, h, h);
        setup["origin"] = new JsonArray(origin.X, origin.Y, origin.Z);
        setup["size"] = new JsonArray(end.X - origin.X, end.Y - origin.Y, end.Z - origin.Z);
    }

    private static void CheckGeometry(GeometryBase geometry)
    {
        if (geometry is Mesh m && m.IsValid && m.IsClosed)
            return;
        if (geometry is Brep b && b.IsValid && b.IsSolid)
            return;
        throw new ArgumentException("Select valid closed meshes or closed solid Breps. Repair open geometry before running.");
    }
}
