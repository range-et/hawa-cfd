using System.Text.Json.Nodes;
using Hawa.Shared;
using Rhino;
using Rhino.Geometry;

namespace Hawa.Native;
public static partial class NativeGeometry
{
    public static Task<JsonObject> Prepare(CaseState c, CancellationToken token)
    {
        var doc = RhinoDoc.FromRuntimeSerialNumber(c.Document)!;
        var ids = c.Setup["objects"]!.AsArray().Select(v =>
        {
            return Guid.Parse(v!.GetValue<string>());
        }).ToArray();
        if (ids.Length == 0)
            throw new ArgumentException("Select closed Rhino geometry before running");
        var spec = CaseHub.BuildSpec(c); // Check domain before capturing any geometry.
        var captured = new List<GeometryBase>();
        try
        {
            foreach (var id in ids)
            {
                var obj = doc.Objects.FindId(id) ?? throw new ArgumentException("Selected geometry is missing. Reselect the objects.");
                CheckGeometry(obj.Geometry, $"Obstacle {id}");
                captured.Add(obj.Geometry.Duplicate());
            }
        }
        catch
        {
            foreach (var g in captured)
                g.Dispose();
            throw;
        }

        double units = RhinoMath.UnitScale(doc.ModelUnitSystem, UnitSystem.Meters);
        bool curved = c.Setup["curved_walls"]?.GetValue<bool>() ?? false;
        // No Rhino document access after this capture.
        return Task.Run(() =>
        {
            var meshes = new List<Mesh>();
            try
            {
                foreach (var geometry in captured)
                {
                    token.ThrowIfCancellationRequested();
                    Mesh mesh;
                    if (geometry is Mesh m)
                        mesh = m.DuplicateMesh();
                    else
                        mesh = SurfaceMeshing.Create((Brep)geometry, spec["dx"]!.GetValue<double>() / units);
                    meshes.Add(mesh);
                    mesh.Transform(Transform.Scale(Point3d.Origin, units));
                    ObstaclePreflight.Require(mesh, $"Obstacle {ids[meshes.Count - 1]}", token);
                }

                var n = spec["shape"]!.AsArray().Select(v =>
                {
                    return v!.GetValue<int>();
                }).ToArray();
                double dx = spec["dx"]!.GetValue<double>();
                var a = spec["origin_m"]!.AsArray().Select(v =>
                {
                    return v!.GetValue<double>();
                }).ToArray();
                var origin = new Point3d(a[0], a[1], a[2]);
                var inside = new BoundingBox(origin + new Vector3d(2 * dx, 2 * dx, 2 * dx), origin + new Vector3d((n[0] - 3) * dx, (n[1] - 3) * dx, (n[2] - 3) * dx));
                var boxes = meshes.Select(m =>
                {
                    return m.GetBoundingBox(false);
                }).ToArray();
                if (boxes.Any(b =>
                {
                    return !inside.Contains(b.Min) || !inside.Contains(b.Max);
                }))
                    throw new ArgumentException("Keep selected bodies at least two cells inside every domain face. Fit or enlarge the domain.");
                var solid = new JsonArray();
                var represented = new bool[meshes.Count];
                for (int x = 0; x < n[0]; x++)
                {
                    token.ThrowIfCancellationRequested();
                    for (int y = 0; y < n[1]; y++)
                        for (int z = 0; z < n[2]; z++)
                        {
                            var p = origin + new Vector3d(x * dx, y * dx, z * dx);
                            bool occupied = false;
                            for (int j = 0; j < meshes.Count; j++)
                                if (MeshContainment.Contains(meshes[j], boxes[j], p, dx * 1e-5))
                                {
                                    represented[j] = true;
                                    occupied = true;
                                }

                            if (occupied)
                                solid.Add((x * n[1] + y) * n[2] + z);
                        }
                }

                if (represented.Any(v =>
                {
                    return !v;
                }))
                    throw new ArgumentException("At least one selected body has no solid cells. Reduce cell size.");
                spec["solid"] = solid;
                if (curved)
                    spec["wall_links"] = WallLinks.Build(meshes, n, solid.Select(v =>
                    {
                        return v!.GetValue<int>();
                    }), origin, Vector3d.XAxis * dx, Vector3d.YAxis * dx, Vector3d.ZAxis * dx, token);
                return spec;
            }
            finally
            {
                foreach (var mesh in meshes)
                    mesh.Dispose();
                foreach (var geometry in captured)
                    geometry.Dispose();
            }
        }); // Always enter the delegate so cancellation also disposes captured geometry.
    }
}
