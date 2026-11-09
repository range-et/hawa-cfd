using System.Text.Json.Nodes;
using Hawa.Shared;
using Rhino;
using Rhino.Geometry;
using Rhino.Input.Custom;
using Rhino.DocObjects;
namespace Hawa.Native;

public static class NativeGeometry
{
    public static void Pick(uint serial) {
        var doc = RhinoDoc.FromRuntimeSerialNumber(serial) ?? throw new InvalidOperationException("Document closed");
        if (RhinoDoc.ActiveDoc != doc) throw new InvalidOperationException("Activate this Rhino document before selecting objects");
        using var pick = new GetObject(); pick.SetCommandPrompt("Select closed meshes or solid surfaces for Hawa");
        pick.GeometryFilter = ObjectType.Mesh | ObjectType.Brep; pick.SubObjectSelect = false;
        pick.GetMultiple(1, 100);
        if (pick.CommandResult() != Rhino.Commands.Result.Success) return;
        SelectObjects(serial, Enumerable.Range(0, pick.ObjectCount).Select(i => pick.Object(i).ObjectId), true);
    }
    public static void SelectObjects(uint serial, IEnumerable<Guid> objectIds, bool fitDomain) {
        var c = CaseHub.Get(serial); var doc = RhinoDoc.FromRuntimeSerialNumber(serial)!;
        var ids = objectIds.Distinct().ToArray();
        if (ids.Length == 0 || ids.Length > 100) throw new ArgumentException("Select 1..100 closed meshes or solids");
        var bounds = BoundingBox.Empty;
        foreach (var id in ids) {
            var obj = doc.Objects.FindId(id) ?? throw new ArgumentException("A selected object no longer exists");
            CheckGeometry(obj.Geometry); bounds.Union(obj.Geometry.GetBoundingBox(true));
        }
        double scale = RhinoMath.UnitScale(doc.ModelUnitSystem, UnitSystem.Meters);
        bounds.Transform(Transform.Scale(Point3d.Origin, scale));
        var setup = c.Setup; setup["mode"] = "selected"; setup["objects"] = new JsonArray(ids.Select(id => JsonValue.Create(id.ToString())).ToArray());
        if (fitDomain) Fit(setup, bounds, c.Cell);
        CaseHub.Edit(serial, new() { ["setup"] = setup }, c.Version);
    }
    public static void FitDomain(uint serial) {
        var c = CaseHub.Get(serial); if (!c.SelectedGeometry) throw new ArgumentException("Select Rhino geometry first");
        SelectObjects(serial, c.Setup["objects"]!.AsArray().Select(v => Guid.Parse(v!.GetValue<string>())), true);
    }
    private static void Fit(JsonObject setup, BoundingBox b, double cell) {
        double h = Math.Max(cell * 2, Math.Max(b.Diagonal.Y, b.Diagonal.Z));
        var origin = b.Min - new Vector3d(2*h, h, h);
        var end = b.Max + new Vector3d(4*h, h, h);
        setup["origin"] = new JsonArray(origin.X, origin.Y, origin.Z);
        setup["size"] = new JsonArray(end.X-origin.X, end.Y-origin.Y, end.Z-origin.Z);
    }
    private static void CheckGeometry(GeometryBase geometry) {
        if (geometry is Mesh m && m.IsValid && m.IsClosed) return;
        if (geometry is Brep b && b.IsValid && b.IsSolid) return;
        throw new ArgumentException("Select valid closed meshes or closed solid Breps. Repair open geometry before running.");
    }
    public static Task<JsonObject> Prepare(CaseState c, CancellationToken token) {
        var doc = RhinoDoc.FromRuntimeSerialNumber(c.Document)!;
        var ids = c.Setup["objects"]!.AsArray().Select(v => Guid.Parse(v!.GetValue<string>())).ToArray();
        if (ids.Length == 0) throw new ArgumentException("Select closed Rhino geometry before running");
        var captured = new List<GeometryBase>();
        try {
            foreach (var id in ids) {
                var obj = doc.Objects.FindId(id) ?? throw new ArgumentException("Selected geometry is missing. Reselect the objects.");
                CheckGeometry(obj.Geometry); captured.Add(obj.Geometry.Duplicate());
            }
        } catch { foreach (var g in captured) g.Dispose(); throw; }
        double units = RhinoMath.UnitScale(doc.ModelUnitSystem, UnitSystem.Meters);
        bool curved = c.Setup["curved_walls"]?.GetValue<bool>() ?? false;
        var spec = CaseHub.BuildSpec(c); // No Rhino document access after this capture.
        return Task.Run(() => {
            var meshes = new List<Mesh>();
            try {
                foreach (var geometry in captured) {
                    token.ThrowIfCancellationRequested();
                    Mesh mesh;
                    if (geometry is Mesh m) mesh = m.DuplicateMesh();
                    else mesh = SurfaceMeshing.Create((Brep)geometry, spec["dx"]!.GetValue<double>() / units);
                    meshes.Add(mesh); mesh.Transform(Transform.Scale(Point3d.Origin, units));
                    if (!mesh.IsValid || !mesh.IsClosed) throw new ArgumentException("Meshing did not produce a closed solid. Use a repaired closed mesh.");
                }
                var n = spec["shape"]!.AsArray().Select(v => v!.GetValue<int>()).ToArray(); double dx = spec["dx"]!.GetValue<double>();
                var a = spec["origin_m"]!.AsArray().Select(v => v!.GetValue<double>()).ToArray(); var origin = new Point3d(a[0],a[1],a[2]);
                var inside = new BoundingBox(origin + new Vector3d(2*dx,2*dx,2*dx), origin + new Vector3d((n[0]-3)*dx,(n[1]-3)*dx,(n[2]-3)*dx));
                var boxes = meshes.Select(m => m.GetBoundingBox(false)).ToArray();
                if (boxes.Any(b => !inside.Contains(b.Min) || !inside.Contains(b.Max))) throw new ArgumentException("Keep selected bodies at least two cells inside every domain face. Fit or enlarge the domain.");
                var solid = new JsonArray(); var represented = new bool[meshes.Count];
                for (int x=0;x<n[0];x++) {
                    token.ThrowIfCancellationRequested();
                    for (int y=0;y<n[1];y++) for (int z=0;z<n[2];z++) {
                        var p = origin + new Vector3d(x*dx,y*dx,z*dx); bool occupied = false;
                        for (int j=0;j<meshes.Count;j++) if (MeshContainment.Contains(meshes[j],boxes[j],p,dx*1e-5)) { represented[j] = true; occupied = true; }
                        if (occupied) solid.Add((x*n[1]+y)*n[2]+z);
                    }
                }
                if (represented.Any(v => !v)) throw new ArgumentException("At least one selected body has no solid cells. Reduce cell size.");
                spec["solid"] = solid;
                if (curved) spec["wall_links"] = WallLinks.Build(meshes,n,solid.Select(v=>v!.GetValue<int>()),origin,Vector3d.XAxis*dx,Vector3d.YAxis*dx,Vector3d.ZAxis*dx,token);
                return spec;
            } finally { foreach (var mesh in meshes) mesh.Dispose(); foreach (var geometry in captured) geometry.Dispose(); }
        }); // Always enter the delegate so cancellation also disposes captured geometry.
    }
}
