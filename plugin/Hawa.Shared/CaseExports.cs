using System.Text.Json.Nodes;
using Rhino;
using Rhino.Geometry;

namespace Hawa.Shared;
public static partial class CaseHub
{
    // Points are captured document coordinates, never live references to geometry.
    public static void Export(uint document, string path, string table, IEnumerable<Point3d>? points = null)
    {
        UI();
        var c = Find(document) ?? throw new InvalidOperationException("Create and complete a case before exporting.");
        Change(c, () =>
        {
            if (c.ExportJob != null)
                throw new InvalidOperationException("An export is already pending. Cancel it or wait for completion.");
            if (c.State != "completed" || c.Session == null || c.SpecData == null || c.RunRevision != c.Revision || c.Fault != null)
                throw new InvalidOperationException("Export requires a healthy completed run.");
            if (table is not ("fields" or "probes"))
                throw new ArgumentException("Native export supports fields and probes. Use the Grasshopper moving-body workflow for loads.");
            if (string.IsNullOrWhiteSpace(path))
                throw new ArgumentException("Choose a CSV destination.");
            if (c.ModelUnits != RhinoDoc.FromRuntimeSerialNumber(document)!.ModelUnitSystem)
                throw new InvalidOperationException("Document units changed. Review and rerun the case before exporting.");
            string hash = c.StatusData?["case_hash"]?.GetValue<string>() ?? throw new InvalidOperationException("Completed case identity is unavailable.");
            var request = new JsonObject
            {
                ["op"] = "export", ["format"] = "csv", ["table"] = table,
                ["session"] = c.Session, ["path"] = Path.GetFullPath(path),
                ["expected"] = new JsonObject { ["case_hash"] = hash, ["iteration"] = c.Steps, ["state"] = "completed" },
                ["attribution"] = new JsonObject { ["case_id"] = c.Id.ToString(), ["revision"] = c.Revision, ["generation"] = c.Generation, ["version"] = c.Version }
            };
            if (table == "probes")
                request["points"] = ExportPoints(CaseGeometry.SpecInModelUnits(c)!, points);
            c.ExportError = "";
            c.ExportResultData = null;
            c.ExportRequest = request;
            try
            {
                c.ExportJob = Transport(new() { ["op"] = "evaluate_submit", ["kind"] = "query", ["request"] = request.DeepClone() })["job"]!.GetValue<string>();
                if (string.IsNullOrWhiteSpace(c.ExportJob))
                    throw new InvalidOperationException("Export submission returned no job identity.");
                c.ExportState = "pending";
            }
            catch (Exception e)
            {
                CloseExport(c);
                c.ExportState = "failed";
                c.ExportError = e.GetBaseException().Message;
            }
        });
        Notify(c, "export");
    }

    private static JsonArray ExportPoints(JsonObject spec, IEnumerable<Point3d>? points)
    {
        var captured = points?.Take(10001).ToArray() ?? Array.Empty<Point3d>();
        if (captured.Length == 0 || captured.Length > 10000)
            throw new ArgumentException("Select 1..10000 Rhino point objects for probe export.");
        var origin = spec["origin"]!.AsArray();
        double spacing = spec["spacing"]!.GetValue<double>();
        var result = new JsonArray();
        foreach (var p in captured)
        {
            if (!double.IsFinite(p.X) || !double.IsFinite(p.Y) || !double.IsFinite(p.Z))
                throw new ArgumentException("Probe coordinates must be finite.");
            result.Add(new JsonArray((p.X-origin[0]!.GetValue<double>())/spacing,
                (p.Y-origin[1]!.GetValue<double>())/spacing, (p.Z-origin[2]!.GetValue<double>())/spacing));
        }
        return result;
    }

    public static void CancelExport(uint document)
    {
        UI();
        var c = Find(document);
        if (c == null) return;
        Change(c, () =>
        {
            CloseExport(c);
        });
        Notify(c, "export");
    }

    private static void CloseExport(CaseState c)
    {
        var job = c.ExportJob;
        c.ExportJob = null;
        c.ExportRequest = null;
        if (job == null) return;
        c.ExportState = "cancelled";
        ReleaseJob(job);
    }

    private static void PollExport(CaseState c)
    {
        var job = c.ExportJob;
        if (job == null) return;
        var request = c.ExportRequest!;
        try
        {
            var response = Transport(new() { ["op"] = "evaluate_poll", ["job"] = job });
            if (Find(c.Document) != c || c.ExportJob != job) return;
            string state = response["state"]!.GetValue<string>();
            if (state is "failed" or "cancelled")
                throw new InvalidOperationException(response["error"]?.GetValue<string>() ?? "Export cancelled.");
            if (state != "completed") return;
            var result = response["result"]!.DeepClone().AsObject();
            var attribution = request["attribution"]!;
            if (c.Id.ToString() != attribution["case_id"]!.GetValue<string>() || c.Revision != attribution["revision"]!.GetValue<long>() || c.Generation != attribution["generation"]!.GetValue<long>() || c.Session != request["session"]!.GetValue<string>())
                throw new InvalidOperationException("Export belongs to a replaced run.");
            foreach (var key in new[] { "session", "path", "format", "table" })
                if (result[key]?.GetValue<string>() != request[key]!.GetValue<string>())
                    throw new InvalidOperationException("Export capture identity mismatch: " + key);
            if (result["case_hash"]?.GetValue<string>() != request["expected"]!["case_hash"]!.GetValue<string>() || result["iteration"]?.GetValue<int>() != request["expected"]!["iteration"]!.GetValue<int>() || result["source_state"]?.GetValue<string>() != "completed")
                throw new InvalidOperationException("Export capture does not match the completed run.");
            var returnedAttribution = result["attribution"]!.AsObject();
            if (returnedAttribution.Count != 4 || returnedAttribution["case_id"]?.GetValue<string>() != attribution["case_id"]!.GetValue<string>())
                throw new InvalidOperationException("Export attribution mismatch.");
            foreach (var key in new[] { "revision", "generation", "version" })
                if (returnedAttribution[key]?.GetValue<long>() != attribution[key]!.GetValue<long>())
                    throw new InvalidOperationException("Export attribution mismatch: " + key);
            if (string.IsNullOrWhiteSpace(result["artifact_id"]!.GetValue<string>()) || result["rows"]!.GetValue<int>() < 1)
                throw new InvalidOperationException("Export artifact is incomplete.");
            foreach (var key in new[] { "local_time", "time_origin", "absolute_time" })
                if (!double.IsFinite(result[key]!.GetValue<double>()) || result[key]!.GetValue<double>() < 0)
                    throw new InvalidOperationException("Invalid export capture time.");
            if (result["absolute_time"]!.GetValue<double>() != result["local_time"]!.GetValue<double>() + result["time_origin"]!.GetValue<double>())
                throw new InvalidOperationException("Inconsistent export capture time.");
            CloseExport(c);
            c.ExportResultData = result;
            c.ExportState = "completed";
        }
        catch (Exception e)
        {
            CloseExport(c);
            c.ExportState = "failed";
            c.ExportError = e.GetBaseException().Message;
        }
    }
}
