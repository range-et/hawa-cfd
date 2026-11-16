using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Rhino.Geometry;

namespace Hawa.Grasshopper;
public sealed class MovingBodyComponent : HawaComponent
{
    private Task<JsonObject>? task;
    private CancellationTokenSource? cancel;
    private string? signature;
    public MovingBodyComponent() : base("Hawa Moving Body", "Body", "Prepare a closed rigid mesh once in a background task. Experimental signed-distance representation, half-cell sampling.", "02 Geometry")
    {
    }

    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077142");

    protected override void RegisterInputParams(GH_InputParamManager p)
    {
        p.AddGenericParameter("Case", "C", "Base physical Case; uniform BGK", GH_ParamAccess.item);
        p.AddMeshParameter("Mesh", "M", "Closed reference mesh", GH_ParamAccess.item);
        p.AddGenericParameter("Motion", "V", "Translation, Rotation or Oscillation", GH_ParamAccess.item);
        p.AddPointParameter("Pivot", "P", "Rotation pivot in model coordinates", GH_ParamAccess.item);
        p.AddTextParameter("Body ID", "ID", "Unique stable body name", GH_ParamAccess.item, "body");
    }

    protected override void RegisterOutputParams(GH_OutputParamManager p)
    {
        p.AddGenericParameter("Body", "B", "Prepared body assigned to this domain", GH_ParamAccess.item);
        p.AddTextParameter("Report", "R", "Geometry preparation status", GH_ParamAccess.item);
    }

    protected override void SolveHawa(IGH_DataAccess da)
    {
        var spec = ReadObject(da, 0);
        Mesh mesh = null!;
        da.GetData(1, ref mesh);
        var motion = ReadObject(da, 2);
        Point3d pivot = default;
        string id = "body";
        da.GetData(3, ref pivot);
        da.GetData(4, ref id);
        if (mesh == null || !pivot.IsValid || string.IsNullOrWhiteSpace(id))
            throw new ArgumentException("Closed valid mesh, pivot and unique ID required");
        var key = spec.ToJsonString() + motion.ToJsonString() + mesh.DataCRC(0) + pivot.ToString() + id;
        if (task == null || signature != key)
        {
            InputsMissing();
            signature = key;
            cancel = new();
            var token = cancel.Token;
            var copy = mesh.DuplicateMesh();
            var world = new JsonObject
            {
                ["case"] = spec.DeepClone()
            };
            double dx = spec["dx"]!.GetValue<double>();
            task = Task.Run(() =>
            {
                try
                {
                    Hawa.Shared.ObstaclePreflight.Require(copy, $"Moving body {id}", token);
                    for (int i = 0; i < copy.Vertices.Count; i++)
                    {
                        var p = Coordinates.Grid(world, (Point3d)copy.Vertices[i]);
                        copy.Vertices.SetVertex(i, p[0]!.GetValue<double>() * dx, p[1]!.GetValue<double>() * dx, p[2]!.GetValue<double>() * dx);
                    }

                    var bounds = copy.GetBoundingBox(true);
                    var lo = bounds.Min - new Vector3d(dx, dx, dx);
                    double h = dx / 2;
                    var size = bounds.Max + new Vector3d(dx, dx, dx) - lo;
                    int[] n =
                    {
                        (int)Math.Ceiling(size.X / h) + 1,
                        (int)Math.Ceiling(size.Y / h) + 1,
                        (int)Math.Ceiling(size.Z / h) + 1
                    };
                    if ((long)n[0] * n[1] * n[2] > 200000)
                        throw new ArgumentException("Body SDF exceeds 200000 samples; use a coarser grid or smaller body");
                    var values = new JsonArray();
                    for (int x = 0; x < n[0]; x++)
                    {
                        token.ThrowIfCancellationRequested();
                        for (int y = 0; y < n[1]; y++)
                            for (int z = 0; z < n[2]; z++)
                            {
                                var point = lo + new Vector3d(x * h, y * h, z * h);
                                var nearest = copy.ClosestPoint(point);
                                double distance = point.DistanceTo(nearest);
                                bool inside = GeometryComponent.Contains(copy, bounds, point, dx * 1e-5);
                                values.Add(inside ? -distance : distance);
                            }
                    }

                    var localMotion = motion.DeepClone().AsObject();
                    var a = motion["axis"]!;
                    var axis = new Vector3d(a[0]!.GetValue<double>(), a[1]!.GetValue<double>(), a[2]!.GetValue<double>());
                    localMotion["axis"] = Numbers(Enumerable.Range(0, 3).Select(i =>
                    {
                        return axis * Coordinates.Axis(world, i);
                    }));
                    var pvt = Coordinates.Grid(world, pivot).Select(v =>
                    {
                        return v!.GetValue<double>() * dx;
                    });
                    return new JsonObject
                    {
                        ["kind"] = "Body",
                        ["id"] = id,
                        ["pivot"] = Numbers(pvt),
                        ["motion"] = localMotion,
                        ["geometry"] = new JsonObject
                        {
                            ["type"] = "sdf",
                            ["origin"] = Numbers(new[] { lo.X, lo.Y, lo.Z }),
                            ["spacing"] = h,
                            ["shape"] = new JsonArray(n[0], n[1], n[2]),
                            ["values"] = values
                        },
                        ["domain_key"] = spec.ToJsonString()
                    };
                }
                finally
                {
                    copy.Dispose();
                }
            });
        }

        if (!task.IsCompleted)
        {
            Message = "preparing body";
            string expected = signature!;
            HawaPollScheduler.Request(this, () =>
            {
                return signature == expected;
            });
            return;
        }

        if (task.IsFaulted)
            throw task.Exception!.GetBaseException();
        da.SetData(0, new HawaGoo(task.Result));
        da.SetData(1, "Body prepared; verify thin features and motion clearance. " + Hawa.Shared.ObstaclePreflight.Limits);
        Message = "ready";
    }

    protected override void InputsMissing()
    {
        cancel?.Cancel();
        task = null;
        signature = null;
    }

    public override void RemovedFromDocument(GH_Document d)
    {
        InputsMissing();
        base.RemovedFromDocument(d);
    }
}
