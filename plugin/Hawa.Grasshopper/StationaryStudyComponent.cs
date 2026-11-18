using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Hawa.Grasshopper;

/// <summary>Document-owned CPU study; all voxelization and solving belongs to the backend worker.</summary>
public sealed class StationaryStudyComponent : HawaComponent
{
    private string? job, signature;
    private bool first = true, requireOff;
    private int generation;
    public StationaryStudyComponent() : base("Hawa Stationary Study", "Study", "Experimental CPU body-load and pressure study. Each angle/speed starts fresh. Run off/on after edits. Forces are whole-body fluid loads, not per-face pressure or qualified aerodynamics.", "05 Solve") { }
    public override Guid ComponentGuid => new("4823e5ad-f4fb-4b62-96e3-127989a184b5");

    protected override void RegisterInputParams(GH_InputParamManager p)
    {
        p.AddGenericParameter("Case", "C", "Empty-solid, world-axis uniform physical BGK case", GH_ParamAccess.item);
        p.AddMeshParameter("Mesh", "M", "Closed reference body mesh in model coordinates", GH_ParamAccess.item);
        p.AddNumberParameter("Angles", "A", "Degrees about world +Y; ordered outer loop", GH_ParamAccess.list);
        p.AddNumberParameter("Speeds", "U", "Positive inlet speeds in m/s; ordered inner loop", GH_ParamAccess.list);
        p.AddNumberParameter("Reference area", "S", "Fixed physical reference area in m²", GH_ParamAccess.item);
        p.AddNumberParameter("Reference chord", "c", "Physical reference chord in m", GH_ParamAccess.item);
        p.AddPointParameter("Pivot", "P", "Rotation and moment origin in model coordinates", GH_ParamAccess.item);
        p.AddPointParameter("Probes", "Q", "Optional fixed-world pressure probes in model coordinates", GH_ParamAccess.list); p[7].Optional = true;
        p.AddIntegerParameter("Settling steps", "Ns", "Discard before the averaging window", GH_ParamAccess.item, 3000);
        p.AddIntegerParameter("Sample steps", "Nm", "At least four samples per candidate", GH_ParamAccess.item, 201);
        p.AddNumberParameter("Stationarity tolerance", "T", "Absolute coefficient drift criterion", GH_ParamAccess.item, .05);
        p.AddIntegerParameter("Selected case", "I", "Zero-based completed result to view; does not restart", GH_ParamAccess.item, 0);
        p.AddBooleanParameter("Run", "R", "False cancels; saved true opens idle; off/on after input edits", GH_ParamAccess.item, false);
        p.AddBooleanParameter("Pause", "P", "Cooperatively pause at a step boundary", GH_ParamAccess.item, false);
        p.AddBooleanParameter("Cancel", "X", "Cancel and clear this study; set Run off/on to restart", GH_ParamAccess.item, false);
    }

    protected override void RegisterOutputParams(GH_OutputParamManager p)
    {
        p.AddGenericParameter("Field", "F", "Selected accepted immutable field capture", GH_ParamAccess.item);
        p.AddMeshParameter("Selected mesh", "M", "Same selected candidate mesh in model coordinates", GH_ParamAccess.item);
        p.AddVectorParameter("Force", "F", "Whole-body mean fluid force in world axes, N", GH_ParamAccess.item);
        p.AddVectorParameter("Moment", "M", "Whole-body mean moment about Pivot, world axes, N m", GH_ParamAccess.item);
        p.AddNumberParameter("CL", "CL", "Aligned coefficients; null for unusable cases", GH_ParamAccess.list);
        p.AddNumberParameter("CD", "CD", "Aligned coefficients; null for unusable cases", GH_ParamAccess.list);
        p.AddNumberParameter("CM", "CM", "Aligned pitching coefficients; null for unusable cases", GH_ParamAccess.list);
        p.AddTextParameter("Cases", "C", "Ordered candidate IDs, state and rejection reason", GH_ParamAccess.list);
        p.AddTextParameter("Report", "R", "Study progress and limitations", GH_ParamAccess.item);
        p.AddTextParameter("Identity", "ID", "Selected candidate, capture and mean-window provenance", GH_ParamAccess.item);
        p.AddNumberParameter("Angles", "A", "Aligned operating angles in degrees", GH_ParamAccess.list);
        p.AddNumberParameter("Speeds", "U", "Aligned operating speeds in m/s", GH_ParamAccess.list);
        p.AddNumberParameter("Lift", "L", "Whole-body mean force projected on world +Z, N", GH_ParamAccess.item);
        p.AddNumberParameter("Drag", "D", "Whole-body mean force projected on world +X, N", GH_ParamAccess.item);
    }

    private static double Number(JsonNode? value)
    {
        double result = value?.GetValue<double>() ?? throw new ArgumentException("Missing numerical result");
        if (!double.IsFinite(result)) throw new ArgumentException("Numerical values must be finite");
        return result;
    }
    private static double[] Triple(JsonNode? value)
    {
        if (value is not JsonArray array || array.Count != 3) throw new ArgumentException("Expected three coordinates");
        return array.Select(Number).ToArray();
    }
    private static JsonArray Point(Point3d point, double scale)
    {
        if (!point.IsValid) throw new ArgumentException("Mesh, pivot and probe coordinates must be finite");
        return Numbers(new[] { point.X * scale, point.Y * scale, point.Z * scale });
    }

    // Rhino's CombineIdentical can compare the float vertex view even when the
    // mesh stores doubles. Index exact source coordinates without mutating it.
    private static JsonObject SerializeMesh(Mesh mesh, double scale)
    {
        var indices = new Dictionary<(double, double, double), int>();
        var remap = new int[mesh.Vertices.Count];
        var vertices = new JsonArray();
        for (int i = 0; i < mesh.Vertices.Count; i++)
        {
            var point = mesh.Vertices.Point3dAt(i);
            if (!point.IsValid) throw new ArgumentException("Mesh coordinates must be finite");
            var key = (point.X, point.Y, point.Z);
            if (!indices.TryGetValue(key, out int index))
            {
                index = vertices.Count;
                indices.Add(key, index);
                vertices.Add(Point(point, scale));
            }
            remap[i] = index;
        }
        var triangles = new JsonArray();
        foreach (var face in mesh.Faces)
        {
            triangles.Add(new JsonArray(remap[face.A], remap[face.B], remap[face.C]));
            if (face.IsQuad) triangles.Add(new JsonArray(remap[face.A], remap[face.C], remap[face.D]));
        }
        if (triangles.Count < 4 || triangles.Count > 52000) throw new ArgumentException("Mesh requires 4..52000 triangles");
        return new JsonObject { ["vertices_m"] = vertices, ["triangles"] = triangles };
    }

    private JsonObject Submission(IGH_DataAccess da, out double scale, out JsonArray points)
    {
        var spec = ReadObject(da, 0); spec.Remove("kind"); spec.Remove("label");
        double dx = Number(spec["dx"]), spacing = spec["spacing"] == null ? dx : Number(spec["spacing"]);
        if (dx <= 0 || spacing <= 0 || !double.IsFinite(scale = dx / spacing) || scale <= 0)
            throw new ArgumentException("Case spacing and physical dx must be positive finite");
        var origin = spec["origin"] == null ? new double[3] : Triple(spec["origin"]);
        double factor = scale;
        spec["origin"] = Numbers(origin.Select(v =>
            v * factor
        )); spec["spacing"] = dx;
        Mesh mesh = null!; da.GetData(1, ref mesh);
        if (mesh == null || !mesh.IsValid || !mesh.IsClosed || mesh.Vertices.Count < 4 || mesh.Vertices.Count > 26000 || mesh.Faces.Count > 52000)
            throw new ArgumentException("Use one valid closed mesh with at most 26000 vertices and 52000 triangles");
        var geometry = SerializeMesh(mesh, scale);
        var angles = new List<double>(); var speeds = new List<double>(); var probes = new List<Point3d>();
        da.GetDataList(2, angles); da.GetDataList(3, speeds); da.GetDataList(7, probes);
        if (angles.Count == 0 || speeds.Count == 0 || (long)angles.Count * speeds.Count > 64 ||
            angles.Any(v =>
                !double.IsFinite(v)
            ) || speeds.Any(v =>
                !double.IsFinite(v) || v <= 0
            ) || probes.Count > 256)
            throw new ArgumentException("Use 1..64 finite angle/speed pairs, positive speeds and at most 256 probes");
        points = new JsonArray();
        foreach (var angle in angles) foreach (var speed in speeds) points.Add(new JsonObject { ["angle_deg"] = angle, ["speed_m_s"] = speed });
        double area = 0, chord = 0, tolerance = .05; int settling = 3000, samples = 201; Point3d pivot = default;
        da.GetData(4, ref area); da.GetData(5, ref chord); da.GetData(6, ref pivot);
        da.GetData(8, ref settling); da.GetData(9, ref samples); da.GetData(10, ref tolerance);
        if (!double.IsFinite(area) || area <= 0 || !double.IsFinite(chord) || chord <= 0 || !double.IsFinite(tolerance) || tolerance < 0 ||
            settling < 0 || samples < 4 || (long)settling + samples > 100000)
            throw new ArgumentException("Positive area/chord, nonnegative settling/tolerance, at least four samples and at most 100000 steps required");
        var probeNodes = new JsonArray();
        for (int i = 0; i < probes.Count; i++) probeNodes.Add(new JsonObject { ["probe_id"] = "p" + i, ["position_world_m"] = Point(probes[i], scale) });
        return new JsonObject { ["op"] = "evaluate_submit", ["kind"] = "stationary_study", ["device"] = "cpu", ["case"] = spec,
            ["geometry"] = geometry, ["operating_points"] = points.DeepClone(),
            ["references"] = new JsonObject { ["area_m2"] = area, ["chord_m"] = chord, ["pressure_pa"] = 0d },
            ["pivot_world_m"] = Point(pivot, scale), ["probes"] = probeNodes, ["settling_steps"] = settling,
            ["sample_steps"] = samples, ["stationarity_tolerance"] = tolerance, ["case_id"] = InstanceGuid.ToString() };
    }

    protected override void SolveHawa(IGH_DataAccess da)
    {
        bool run = false, pause = false, cancel = false; int selected = 0;
        da.GetData(12, ref run); da.GetData(13, ref pause); da.GetData(14, ref cancel); da.GetData(11, ref selected);
        if (first) { first = false; requireOff = run; }
        if (!run) { InputsMissing(); requireOff = false; Message = "stopped"; return; }
        if (cancel) { InputsMissing(); Message = "cancelled; set Run off/on"; return; }
        if (requireOff) { Message = "set Run off/on"; return; }
        var request = Submission(da, out var scale, out var points);
        if (selected < 0 || selected >= points.Count) throw new ArgumentException("Selected case index is outside this study");
        string key = request.ToJsonString();
        if (job != null && signature != key) { InputsMissing(); Message = "inputs changed; set Run off/on"; return; }
        if (job == null)
        {
            request["generation"] = ++generation;
            job = EmbeddedRuntime.Call(request)["job"]!.GetValue<string>(); signature = key;
        }
        EmbeddedRuntime.Call(new JsonObject { ["op"] = "evaluate_control", ["job"] = job, ["action"] = pause ? "pause" : "resume" });
        var status = EmbeddedRuntime.Call(new JsonObject { ["op"] = "evaluate_poll", ["job"] = job, ["selected_candidate"] = selected });
        if (status["job"]?.GetValue<string>() != job) throw new InvalidOperationException("Study job identity mismatch");
        string state = status["state"]!.GetValue<string>();
        if (!new[] { "queued", "preparing", "running", "pausing", "paused", "cancelling", "cancelled", "failed", "completed" }.Contains(state))
            throw new InvalidOperationException("Unknown stationary study state");
        if (state == "failed") throw new InvalidOperationException(status["error"]?.GetValue<string>() ?? "Stationary study failed");
        if (state == "cancelled") { InputsMissing(); Message = "cancelled; set Run off/on"; return; }
        var payload = (state == "completed" ? status["result"] : status["progress"]) as JsonObject;
        Publish(da, payload, points, selected, scale, state == "completed");
        Message = state;
        da.SetData(8, $"{state}: {status["steps"]}/{status["target"]} candidates. CPU experimental whole-body loads; no aerodynamic qualification. Field is a retained instantaneous capture; loads are window means.");
        if (state != "completed") { string expected = job!; HawaPollScheduler.Request(this, () =>
            job == expected
        ); }
        else HawaPollScheduler.Cancel(this);
    }

    private void Publish(IGH_DataAccess da, JsonObject? payload, JsonArray points, int selected, double scale, bool completed)
    {
        var rows = payload?["records"] as JsonArray;
        if (completed && rows == null) throw new InvalidOperationException("Completed study has no candidate records");
        if (rows != null && rows.Count != points.Count) throw new InvalidOperationException("Study candidate inventory mismatch");
        var cl = new object?[points.Count]; var cd = new object?[points.Count]; var cm = new object?[points.Count]; var labels = new string[points.Count];
        for (int i = 0; i < points.Count; i++)
        {
            var row = rows?[i]; string id = "study-" + i.ToString("D3"); string state = row?["state"]?.GetValue<string>() ?? "queued";
            if (row != null && (row["candidate"]?["candidate_id"]?.GetValue<string>() != id ||
                Number(row["candidate"]?["angle_deg"]) != Number(points[i]!["angle_deg"]) ||
                Number(row["candidate"]?["speed_m_s"]) != Number(points[i]!["speed_m_s"])))
                throw new InvalidOperationException("Study candidate ordering mismatch");
            labels[i] = $"{id}: {state}; {row?["reason"]}";
            if (state == "completed")
            {
                CheckIdentity(row!["result"]!["identity"]!, row["candidate"]!);
                cl[i] = Number(row["result"]!["coefficients"]!["CL"]); cd[i] = Number(row["result"]!["coefficients"]!["CD"]);
                if (completed && row["CM"] == null) throw new InvalidOperationException("Completed candidate has no pitching coefficient");
                if (row["CM"] != null) cm[i] = Number(row["CM"]);
            }
        }
        JsonObject? frame = null; Mesh? mesh = null; Vector3d force = default, moment = default; string? identity = null;
        var detail = payload?["selected"] as JsonObject;
        if (completed && rows?[selected]?["state"]?.GetValue<string>() == "completed")
        {
            if (detail == null || detail["frame"] is not JsonObject captured) throw new InvalidOperationException("Completed selected candidate has no retained capture");
            var candidate = rows[selected]!["candidate"]!;
            CheckIdentity(detail["identity"]!, candidate); CheckIdentity(captured["identity"]!, candidate);
            if (detail["session"]?.GetValue<string>() != captured["session"]?.GetValue<string>() || detail["phase"]?.GetValue<string>() != captured["phase"]?.GetValue<string>())
                throw new InvalidOperationException("Selected field and loads do not share a source");
            var stamp = captured["snapshot"]!;
            if (stamp["session"]?.GetValue<string>() != detail["session"]?.GetValue<string>() ||
                stamp["phase"]?.GetValue<string>() != detail["phase"]?.GetValue<string>() ||
                stamp["steps"]?.GetValue<int>() != captured["iteration"]?.GetValue<int>() ||
                Number(stamp["physical_time"]) != Number(captured["time"]))
                throw new InvalidOperationException("Selected capture stamp mismatch");
            var summary = detail["summary"]!;
            CheckIdentity(summary["identity"]!, candidate);
            if (summary["usable"]?.GetValue<bool>() != true || summary["bodies"]!.AsArray().Count != 1)
                throw new InvalidOperationException("Selected mean summary is unusable");
            var body = summary["bodies"]![0]!;
            if (body["body_id"]?.GetValue<string>() != "body" || body["usable"]?.GetValue<bool>() != true)
                throw new InvalidOperationException("Selected whole-body mean is unusable");
            if (Number(body["mean"]?["CL"]) != (double)cl[selected]! || Number(body["mean"]?["CD"]) != (double)cd[selected]! || Number(body["mean"]?["Cm"]) != (double)cm[selected]!)
                throw new InvalidOperationException("Selected window coefficients mismatch");
            var f = Triple(body["force_mean_world_n"]); var m = Triple(body["torque_mean_world_nm"]);
            force = new Vector3d(f[0], f[1], f[2]); moment = new Vector3d(m[0], m[1], m[2]);
            frame = captured.DeepClone().AsObject(); frame["kind"] = "Frame";
            var displayCase = frame["case"]!.AsObject(); displayCase["origin"] = Numbers(Triple(displayCase["origin"]).Select(v =>
                v / scale
            ));
            displayCase["spacing"] = Number(displayCase["dx"]) / scale;
            frame["display_metres_per_model_unit"] = scale;
            identity = new JsonObject { ["identity"] = detail["identity"]!.DeepClone(), ["session"] = detail["session"]!.DeepClone(),
                ["phase"] = detail["phase"]!.DeepClone(), ["capture"] = captured["snapshot"]!.DeepClone(), ["summary"] = detail["summary"]!.DeepClone() }.ToJsonString();
            var geometry = detail["geometry"]!; mesh = new Mesh();
            try
            {
                foreach (var node in geometry["vertices_m"]!.AsArray())
                {
                    var p = Triple(node); var point = new Point3d(p[0] / scale, p[1] / scale, p[2] / scale);
                    if (!point.IsValid) throw new InvalidOperationException("Selected mesh display coordinates overflow");
                    mesh.Vertices.Add(point);
                }
                foreach (var face in geometry["triangles"]!.AsArray())
                {
                    if (face is not JsonArray indices || indices.Count != 3) throw new InvalidOperationException("Selected mesh requires triangles");
                    var ids = indices.Select(n =>
                        n!.GetValue<int>()
                    ).ToArray();
                    if (ids.Any(i =>
                        i < 0 || i >= mesh.Vertices.Count
                    )) throw new InvalidOperationException("Selected mesh index outside vertices");
                    mesh.Faces.AddFace(ids[0], ids[1], ids[2]);
                }
                mesh.Normals.ComputeNormals();
            }
            catch { mesh.Dispose(); throw; }
        }
        da.SetDataList(4, cl); da.SetDataList(5, cd); da.SetDataList(6, cm); da.SetDataList(7, labels);
        da.SetDataList(10, points.Select(p =>
            Number(p!["angle_deg"])
        )); da.SetDataList(11, points.Select(p =>
            Number(p!["speed_m_s"])
        ));
        if (frame != null) { da.SetData(0, new HawaGoo(frame)); da.SetData(1, mesh); da.SetData(2, force); da.SetData(3, moment); da.SetData(9, identity); da.SetData(12, force.Z); da.SetData(13, force.X); }
    }

    private void CheckIdentity(JsonNode identity, JsonNode candidate)
    {
        if (identity["case_id"]?.GetValue<string>() != InstanceGuid.ToString() || identity["generation"]?.GetValue<int>() != generation ||
            new[] { "candidate_id", "case_hash", "geometry_hash" }.Any(k =>
                string.IsNullOrWhiteSpace(candidate[k]?.GetValue<string>()) || identity[k]?.ToJsonString() != candidate[k]?.ToJsonString()
            ))
            throw new InvalidOperationException("Stale or mixed stationary study result identity");
    }
    protected override void InputsMissing()
    {
        HawaPollScheduler.Cancel(this); var owned = job; job = signature = null; requireOff = true; Hawa.Shared.CaseHub.ReleaseJob(owned);
    }
    public override void RemovedFromDocument(GH_Document document) { InputsMissing(); base.RemovedFromDocument(document); }
}
