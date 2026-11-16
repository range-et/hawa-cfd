using Grasshopper.Kernel;
using Rhino.Geometry;
using Hawa.Shared;
namespace Hawa.Grasshopper;

public sealed class GeometryCheckComponent : HawaComponent
{
    private Task<(bool[] Accepted, string[] Reports, Curve[] Edges)>? task;
    private CancellationTokenSource? cancellation;
    private string? signature;
    public GeometryCheckComponent() : base("Hawa Geometry Check", "GeoCheck", "Check obstacle topology and bounded transverse self-intersections before voxelization", "02 Geometry") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077134");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddMeshParameter("Meshes", "M", "Obstacles", GH_ParamAccess.list); p.AddNumberParameter("Spacing", "dx", "Proposed cell size in model units", GH_ParamAccess.item, 1); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddBooleanParameter("Closed valid", "V", "Passes obstacle admission; self-intersection limits are in Report", GH_ParamAccess.list); p.AddCurveParameter("Open edges", "E", "Naked mesh edges", GH_ParamAccess.list); p.AddTextParameter("Report", "R", "Obstacle admission, dimensions, volume and unsupported geometry limits", GH_ParamAccess.list); }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        var meshes = new List<Mesh>();
        double dx = 1;
        da.GetDataList(0, meshes);
        da.GetData(1, ref dx);
        if (!double.IsFinite(dx) || dx <= 0)
            throw new ArgumentException("Spacing must be positive");
        string key = dx.ToString("R", System.Globalization.CultureInfo.InvariantCulture) + ":" + string.Join(",", meshes.Select(m =>
            m.DataCRC(0)
        ));
        if (task == null || signature != key)
        {
            InputsMissing();
            signature = key;
            cancellation = new();
            var token = cancellation.Token;
            var copies = meshes.Select(m =>
                m.DuplicateMesh()
            ).ToArray();
            task = Task.Run(() =>
            {
                try
                {
                    var reports = new List<string>();
                    var accepted = new List<bool>();
                    var edges = new List<Curve>();
                    for (int i = 0; i < copies.Length; i++)
                    {
                        token.ThrowIfCancellationRequested();
                        var m = copies[i];
                        var error = ObstaclePreflight.Error(m, $"Obstacle {i + 1}", token);
                        var size = m.GetBoundingBox(true).Diagonal;
                        var naked = m.GetNakedEdges();
                        if (naked != null)
                            edges.AddRange(naked.Select(p =>
                                new PolylineCurve(p)
                            ));
                        double volume = error == null ? Math.Abs(VolumeMassProperties.Compute(m)?.Volume ?? 0) : 0;
                        accepted.Add(error == null);
                        reports.Add($"{error ?? $"Obstacle {i + 1}: passes obstacle admission"}; volume={volume:g7}; cells across bounds={size.X / dx:g3}, {size.Y / dx:g3}, {size.Z / dx:g3}. Internal thin features require grid inspection. {ObstaclePreflight.Limits}");
                    }
                    return (accepted.ToArray(), reports.ToArray(), edges.ToArray());
                }
                finally
                {
                    foreach (var mesh in copies)
                        mesh.Dispose();
                }
            });
        }
        if (!task.IsCompleted)
        {
            Message = "checking geometry";
            string expected = signature!;
            HawaPollScheduler.Request(this, () =>
                signature == expected
            );
            return;
        }
        if (task.IsFaulted)
            throw task.Exception!.GetBaseException();
        da.SetDataList(0, task.Result.Accepted);
        da.SetDataList(1, task.Result.Edges);
        da.SetDataList(2, task.Result.Reports);
        Message = "checked";
    }
    protected override void InputsMissing() { cancellation?.Cancel(); task = null; signature = null; }
    public override void RemovedFromDocument(GH_Document document) { InputsMissing(); base.RemovedFromDocument(document); }
}
