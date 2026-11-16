using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino;
using Rhino.Geometry;

namespace Hawa.Grasshopper;
public sealed class GeometryComponent : HawaComponent
{
    private Task<JsonObject>? task;
    private CancellationTokenSource? cancellation;
    private string? signature;
    public GeometryComponent() : base("Hawa Geometry", "Geometry", "Cancellable background discretization of closed meshes or solid Breps. Brep approximation follows cell size; interpolated walls resolve subcell positions.", "02 Geometry")
    {
    }

    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077102");

    protected override void RegisterInputParams(GH_InputParamManager p)
    {
        p.AddGenericParameter("Domain", "D", "Hawa Domain", GH_ParamAccess.item);
        p.AddMeshParameter("Obstacles", "M", "Closed solid meshes", GH_ParamAccess.list);
        p[1].Optional = true;
        p.AddBooleanParameter("Curved walls", "W", "Compute link/surface intersections for interpolated bounce-back", GH_ParamAccess.item, false);
        p.AddBrepParameter("Solid Breps", "S", "Optional closed solid Breps; meshed in the background with cell-dependent tolerance. Existing meshes retain their supplied shape.", GH_ParamAccess.list);
        p[3].Optional = true;
    }

    protected override void RegisterOutputParams(GH_OutputParamManager p)
    {
        p.AddGenericParameter("Geometry", "G", "Voxelized obstacles", GH_ParamAccess.item);
        p.AddIntegerParameter("Solid cells", "N", "Occupied lattice sites", GH_ParamAccess.item);
    }

    internal static bool Contains(Mesh mesh, BoundingBox bounds, Point3d point, double tolerance) => Hawa.Shared.MeshContainment.Contains(mesh, bounds, point, tolerance);
    internal static double LinkFraction(Mesh mesh, Point3d origin, Vector3d segment) => Hawa.Shared.WallLinks.Fraction(mesh, origin, segment);
    protected override void SolveHawa(IGH_DataAccess da)
    {
        if (new[]
        {
            1,
            3
        }.Any(i =>
        {
            return Params.Input[i].SourceCount > 0 && !Params.Input[i].VolatileData.AllData(true).Any(v =>
            {
                return v != null;
            });
        }))
        {
            InputsMissing();
            Message = "waiting for geometry";
            return;
        }

        var domain = ReadObject(da, 0);
        Hawa.Shared.GeometryDomain.Require(domain);
        var meshes = new List<Mesh>();
        da.GetDataList(1, meshes);
        var breps = new List<Brep>();
        da.GetDataList(3, breps);
        if (breps.Any(b =>
        {
            return !b.IsValid || !b.IsSolid;
        }))
            throw new ArgumentException("Brep obstacles must be valid closed solids");
        bool curved = false;
        da.GetData(2, ref curved);
        string key = curved + domain.ToJsonString() + string.Join(",", meshes.Select(m =>
        {
            return m.DataCRC(0);
        })) + ";breps=" + string.Join(",", breps.Select(b =>
        {
            return b.DataCRC(0);
        }));
        if (key != signature || task == null)
        {
            cancellation?.Cancel();
            cancellation = new CancellationTokenSource();
            var token = cancellation.Token;
            var copies = meshes.Select(m =>
            {
                return m.DuplicateMesh();
            }).ToList();
            var surfaces = breps.Select(b =>
            {
                return b.DuplicateBrep();
            }).ToArray();
            signature = key;
            task = Task.Run(() =>
            {
                try
                {
                    var n = domain["shape"]!.AsArray().Select(v =>
                    {
                        return v!.GetValue<int>();
                    }).ToArray();
                    double dx = domain["spacing"]!.GetValue<double>();
                    foreach (var surface in surfaces)
                    {
                        token.ThrowIfCancellationRequested();
                        copies.Add(Hawa.Shared.SurfaceMeshing.Create(surface, dx));
                    }

                    for (int i = 0; i < copies.Count; i++)
                        Hawa.Shared.ObstaclePreflight.Require(copies[i], $"Obstacle {i + 1}", token);
                    var solution = new JsonObject
                    {
                        ["case"] = domain.DeepClone()
                    };
                    var bounds = copies.Select(m =>
                    {
                        return m.GetBoundingBox(false);
                    }).ToArray();
                    var o = Coordinates.Origin(solution);
                    var origin = new Point3d(o[0], o[1], o[2]);
                    var ax = Coordinates.Axis(solution, 0) * dx;
                    var ay = Coordinates.Axis(solution, 1) * dx;
                    var az = Coordinates.Axis(solution, 2) * dx;
                    // Shared parent geometry can include bodies wholly outside
                    // a child. Exclude only provably disjoint local bounds; keep
                    // unresolved intersecting bodies as errors, including halo.
                    var axes = new[]
                    {
                        ax / dx,
                        ay / dx,
                        az / dx
                    };
                    var relevant = copies.Select(mesh =>
                    {
                        var local = new BoundingBox(mesh.Vertices.Select(v =>
                        {
                            var r = (Point3d)v - origin;
                            return new Point3d(r * axes[0] / dx, r * axes[1] / dx, r * axes[2] / dx);
                        }));
                        return local.Max.X >= -1 && local.Min.X <= n[0] && local.Max.Y >= -1 && local.Min.Y <= n[1] && local.Max.Z >= -1 && local.Min.Z <= n[2];
                    }).ToArray();
                    if (curved && copies.Where((mesh, i) =>
                    {
                        return relevant[i];
                    }).Any(mesh =>
                    {
                        return mesh.Vertices.Any(v =>
                        {
                            var r = (Point3d)v - origin;
                            return r * axes[0] / dx < 2 || r * axes[0] / dx > n[0] - 3
                                || r * axes[1] / dx < 2 || r * axes[1] / dx > n[1] - 3
                                || r * axes[2] / dx < 2 || r * axes[2] / dx > n[2] - 3;
                        });
                    }))
                        throw new ArgumentException("Curved walls require two-cell domain clearance. Enlarge or move the domain before voxelizing.");

                    var solid = new JsonArray();
                    var halo = new JsonArray();
                    var represented = new bool[copies.Count];
                    for (int x = -1; x <= n[0]; x++)
                    {
                        token.ThrowIfCancellationRequested();
                        for (int y = -1; y <= n[1]; y++)
                            for (int z = -1; z <= n[2]; z++)
                            {
                                var point = origin + x * ax + y * ay + z * az;
                                bool inside = x >= 0 && x < n[0] && y >= 0 && y < n[1] && z >= 0 && z < n[2];
                                bool occupied = false;
                                for (int m = 0; m < copies.Count; m++)
                                    if (relevant[m] && Contains(copies[m], bounds[m], point, dx * 1e-5))
                                    {
                                        represented[m] = true;
                                        occupied = true;
                                    }

                                if (occupied)
                                {
                                    halo.Add(((x + 1) * (n[1] + 2) + y + 1) * (n[2] + 2) + z + 1);
                                    if (inside)
                                        solid.Add((x * n[1] + y) * n[2] + z);
                                }
                            }
                    }

                    if (represented.Where((v, i) =>
                    {
                        return relevant[i] && !v;
                    }).Any())
                        throw new ArgumentException("An intersecting obstacle has no solid or halo cells. Reduce cell size or check domain placement.");
                    var data = new JsonObject
                    {
                        ["kind"] = "Geometry",
                        ["label"] = $"Hawa geometry: {solid.Count} solid cells",
                        ["domain"] = domain.DeepClone(),
                        ["solid"] = solid,
                        ["solid_halo"] = halo,
                        ["ignored_outside_bodies"] = relevant.Count(v =>
                        {
                            return !v;
                        })
                    };
                    if (curved)
                    {
                        data["wall_links"] = Hawa.Shared.WallLinks.Build(copies, n, solid.Select(v =>
                        {
                            return v!.GetValue<int>();
                        }), origin, ax, ay, az, token);
                    }

                    return data;
                }
                finally
                {
                    foreach (var m in copies)
                        m.Dispose();
                    foreach (var b in surfaces)
                        b.Dispose();
                }
            });
        }

        if (!task.IsCompleted)
        {
            Message = "voxelizing";
            string expected = signature!;
            HawaPollScheduler.Request(this, () =>
            {
                return signature == expected;
            });
            return;
        }

        if (task.IsFaulted)
            throw task.Exception!.GetBaseException();
        var data = task.Result;
        Message = "ready";
        AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, Hawa.Shared.ObstaclePreflight.Limits);
        var ignored = data["ignored_outside_bodies"]?.GetValue<int>() ?? 0;
        if (ignored > 0)
            AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, $"{ignored} bodies lie wholly outside the domain and its halo.");
        da.SetData(0, new HawaGoo(data));
        da.SetData(1, data["solid"]!.AsArray().Count);
    }

    protected override void InputsMissing()
    {
        cancellation?.Cancel();
        task = null;
        signature = null;
    }

    public override void RemovedFromDocument(GH_Document document)
    {
        InputsMissing();
        base.RemovedFromDocument(document);
    }
}
