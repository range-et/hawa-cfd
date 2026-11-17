using System.Text.Json.Nodes;
using Rhino;

namespace Hawa.Shared;
public static partial class CaseHub
{
    private static JsonObject DataContext(CaseState c) => new()
    {
        ["case_id"] = c.Id.ToString(), ["revision"] = c.Revision, ["generation"] = c.Generation, ["version"] = c.Version
    };

    public static void SaveData(uint document, string path)
    {
        UI();
        var c = Find(document) ?? throw new InvalidOperationException("Create or import a case before saving data.");
        Change(c, () =>
        {
            if (c.Session == null || c.State is not ("paused" or "completed") || c.Fault != null || c.RunRevision != c.Revision)
                throw new InvalidOperationException("Pause or complete a healthy case before saving data.");
            var request = new JsonObject
            {
                ["op"] = "data", ["action"] = "save", ["path"] = Path.GetFullPath(path), ["session"] = c.Session,
                ["expected"] = new JsonObject { ["case_hash"] = c.StatusData!["case_hash"]!.DeepClone(), ["iteration"] = c.Steps, ["state"] = c.State },
                ["native_settings"] = c.Settings(), ["attribution"] = DataContext(c)
            };
            StartData(c, new() { ["op"] = "evaluate_submit", ["kind"] = "query", ["request"] = request }, request);
        });
        Notify(c, "data");
    }

    public static void ImportData(uint document, string path, string device)
    {
        UI();
        bool empty = Find(document) == null;
        var c = Get(document);
        if (empty) c.ImportedSourceData = new JsonObject { ["placeholder"] = true };
        Change(c, () =>
        {
            if (string.IsNullOrWhiteSpace(path)) throw new ArgumentException("Choose a Hawa data file.");
            if (device is not ("cpu" or "auto" or "mps" or "cuda:0")) throw new ArgumentException("Choose an available backend.");
            var request = new JsonObject { ["op"] = "evaluate_submit", ["kind"] = "native_data_import", ["path"] = Path.GetFullPath(path), ["device"] = device, ["context"] = DataContext(c) };
            StartData(c, request.DeepClone().AsObject(), request);
        });
        Notify(c, "data");
    }

    private static void StartData(CaseState c, JsonObject submission, JsonObject request)
    {
        if (c.DataJob != null) throw new InvalidOperationException("A data operation is pending; wait or cancel it first.");
        c.DataError = ""; c.DataResultData = null; c.DataRequest = request;
        try
        {
            c.DataJob = Transport(submission)["job"]!.GetValue<string>();
            if (string.IsNullOrWhiteSpace(c.DataJob)) throw new InvalidOperationException("Data submission returned no job identity.");
            c.DataState = request["kind"]?.GetValue<string>() == "native_data_import" ? "importing" : "saving";
        }
        catch (Exception e) { CloseData(c); c.DataState = "failed"; c.DataError = e.GetBaseException().Message; }
    }

    public static void CancelData(uint document)
    {
        UI(); var c = Find(document); if (c == null) return;
        Change(c, () =>
        {
            CloseData(c);
        });
        Notify(c, "data");
    }

    private static void CloseData(CaseState c)
    {
        string? job = c.DataJob; c.DataJob = null; c.DataRequest = null;
        if (job == null) return;
        c.DataState = "cancelled"; ReleaseJob(job);
    }

    private static void CheckDataContext(JsonNode? actual, JsonObject expected)
    {
        var value = actual!.AsObject();
        if (value.Count != 4 || value["case_id"]?.GetValue<string>() != expected["case_id"]!.GetValue<string>())
            throw new InvalidOperationException("Data operation case identity changed.");
        foreach (string key in new[] { "revision", "generation", "version" })
            if (value[key]?.GetValue<long>() != expected[key]!.GetValue<long>())
                throw new InvalidOperationException("Data operation settings changed: " + key);
    }

    private static void ValidateImportedSource(JsonObject source)
    {
        if (source.Count == 1 && source["placeholder"]?.GetValue<bool>() == true) return;
        if (source["schema"]?.GetValue<string>() != "hawa-native-data-1" || string.IsNullOrWhiteSpace(source["artifact_id"]?.GetValue<string>()) || string.IsNullOrWhiteSpace(source["case_hash"]?.GetValue<string>()))
            throw new ArgumentException("Invalid imported data identity.");
        var geometry = source["geometry"]!.AsObject();
        var shape = geometry["shape"]!.AsArray();
        double dx = geometry["dx"]!.GetValue<double>();
        var origin = geometry["origin_m"]!.AsArray();
        if (shape.Count != 3 || shape.Any(v =>
            v!.GetValue<int>() < 4
        ) || shape.Aggregate(1d, (a, v) =>
            a * v!.GetValue<int>()
        ) > 2000000 || !double.IsFinite(dx) || dx <= 0 || origin.Count != 3 || origin.Any(v =>
            !double.IsFinite(v!.GetValue<double>())
        )) throw new ArgumentException("Invalid imported physical geometry.");
    }

    private static void PollData(CaseState c)
    {
        string? job = c.DataJob; if (job == null) return;
        var request = c.DataRequest!;
        try
        {
            var response = Transport(new() { ["op"] = "evaluate_poll", ["job"] = job });
            if (Find(c.Document) != c || c.DataJob != job) return;
            string state = response["state"]!.GetValue<string>();
            if (state is "failed" or "cancelled") throw new InvalidOperationException(response["error"]?.GetValue<string>() ?? "Data operation cancelled.");
            if (state != "completed") return;
            var result = response["result"]!.DeepClone().AsObject();
            bool importing = request["kind"]?.GetValue<string>() == "native_data_import";
            var context = (importing ? request["context"] : request["attribution"])!.AsObject();
            var current = DataContext(c);
            if (!importing) current["version"] = context["version"]!.DeepClone();
            CheckDataContext(context, current);
            var metadata = result["metadata"]!.AsObject();
            if (metadata["schema"]?.GetValue<string>() != "hawa-native-data-1" || string.IsNullOrWhiteSpace(metadata["artifact_id"]?.GetValue<string>()))
                throw new InvalidOperationException("Invalid data artifact identity.");
            foreach (var key in new[] { "local_time", "time_origin", "absolute_time" })
                if (!double.IsFinite(metadata[key]!.GetValue<double>()) || metadata[key]!.GetValue<double>() < 0)
                    throw new InvalidOperationException("Invalid data capture time.");
            if (metadata["absolute_time"]!.GetValue<double>() != metadata["local_time"]!.GetValue<double>() + metadata["time_origin"]!.GetValue<double>())
                throw new InvalidOperationException("Inconsistent data capture time.");
            if (importing) AdoptData(c, job, request, result);
            else
            {
                CheckDataContext(metadata["attribution"], context);
                if (result["path"]?.GetValue<string>() != request["path"]!.GetValue<string>() || result["format"]?.GetValue<string>() != "npz" || result["schema"]?.GetValue<string>() != "hawa-native-data-1" || metadata["source_session"]?.GetValue<string>() != c.Session || metadata["case_hash"]?.GetValue<string>() != request["expected"]!["case_hash"]!.GetValue<string>() || metadata["iteration"]?.GetValue<int>() != request["expected"]!["iteration"]!.GetValue<int>() || metadata["source_state"]?.GetValue<string>() != request["expected"]!["state"]!.GetValue<string>())
                    throw new InvalidOperationException("Saved data does not match its requested capture.");
                CloseData(c);
            }
            c.DataResultData = DataSummary(result, request["path"]!.GetValue<string>()); c.DataState = importing ? "imported" : "saved";
        }
        catch (Exception e) { CloseData(c); c.DataState = "failed"; c.DataError = e.GetBaseException().Message; }
    }

    private static JsonObject DataSummary(JsonObject result, string path)
    {
        var metadata = new JsonObject();
        foreach (var key in new[] { "schema", "artifact_id", "case_hash", "iteration", "local_time", "time_origin", "absolute_time", "source_state", "source_session", "attribution" })
            metadata[key] = result["metadata"]![key]?.DeepClone();
        return new JsonObject { ["path"] = path, ["metadata"] = metadata };
    }

    private static void AdoptData(CaseState c, string job, JsonObject request, JsonObject result)
    {
        CheckDataContext(result["context"], request["context"]!.AsObject());
        var metadata = result["metadata"]!.AsObject();
        var spec = result["case"]!.DeepClone().AsObject();
        var status = result["status"]!.DeepClone().AsObject();
        string session = status["session"]!.GetValue<string>();
        if (status["error"] != null || string.IsNullOrWhiteSpace(session) || session == c.Session || status["state"]?.GetValue<string>() != "paused" || status["steps"]?.GetValue<int>() != metadata["iteration"]!.GetValue<int>() || status["case_hash"]?.GetValue<string>() != metadata["case_hash"]!.GetValue<string>())
            throw new InvalidOperationException("Imported session does not match the paused artifact.");
        if (spec.ToJsonString() != metadata["case"]!.ToJsonString()) throw new InvalidOperationException("Imported case differs from artifact.");
        var presentation = metadata["native_settings"]!.AsObject();
        var settings = new CaseState().Settings();
        foreach (var key in new[] { "view", "target", "field" })
            if (presentation[key] != null) settings[key] = presentation[key]!.DeepClone();
        settings["id"] = Guid.NewGuid().ToString(); settings["device"] = request["device"]!.DeepClone();
        var geometry = ImportedGeometry(spec);
        var setup = NativeSettings.DefaultSetup();
        setup["mode"] = "selected"; setup["objects"] = new JsonArray();
        setup["origin"] = geometry["origin_m"]!.DeepClone();
        double dx = spec["dx"]!.GetValue<double>();
        setup["size"] = new JsonArray(spec["shape"]!.AsArray().Select(v =>
            JsonValue.Create((v!.GetValue<int>() - 1) * dx)
        ).ToArray());
        setup["viscosity"] = spec["viscosity"]!.DeepClone();
        setup["density"] = spec["density"]?.DeepClone() ?? JsonValue.Create(1.225);
        setup["mach"] = spec["mach"]?.DeepClone() ?? JsonValue.Create(.05);
        setup["collision"] = spec["collision"]?.DeepClone() ?? JsonValue.Create("regularized");
        setup["boundaries"] = spec["boundaries"]?.DeepClone() ?? NativeSettings.DefaultSetup()["boundaries"]!.DeepClone();
        setup["curved_walls"] = spec["wall_links"] is JsonArray links && links.Count > 0;
        settings["setup"] = setup; settings["cell"] = dx; settings["speed"] = spec["speed"]!.DeepClone();
        settings["width"] = spec["hawa_block_width"]?.DeepClone() ?? JsonValue.Create(1d);
        var source = new JsonObject { ["schema"] = "hawa-native-data-1", ["artifact_id"] = metadata["artifact_id"]!.DeepClone(), ["case_hash"] = metadata["case_hash"]!.DeepClone(), ["path"] = request["path"]!.DeepClone(), ["geometry"] = geometry };
        source["attribution"] = metadata["attribution"]?.DeepClone();
        source["iteration"] = metadata["iteration"]!.DeepClone();
        source["absolute_time"] = metadata["absolute_time"]!.DeepClone();
        source["source_session"] = metadata["source_session"]?.DeepClone();
        settings["imported_source"] = source; Validate(settings);
        // All untrusted metadata is checked before detaching the prior case.
        c.DataJob = null; c.DataRequest = null;
        Stop(c); Apply(c, settings); ClearResult(c);
        c.BindingOwner = null; c.BindingLease = null; c.BindingPrecision.Clear(); c.DrivenKeys.Clear();
        c.SpecData = spec; c.Job = job; c.Session = session; c.StatusData = status;
        c.RunRevision = c.Revision; c.Steps = status["steps"]!.GetValue<int>(); c.State = "paused";
        c.Error = c.ViewError = c.GeometryError = ""; c.Fault = null; c.ViewFailures = 0; c.LastQuery = DateTime.MinValue;
        RhinoDoc.FromRuntimeSerialNumber(c.Document)!.Strings.SetString("Hawa", "last-imported-data", source["artifact_id"]!.GetValue<string>());
    }

    private static JsonObject ImportedGeometry(JsonObject spec)
    {
        double dx = spec["dx"]!.GetValue<double>();
        double spacing = spec["spacing"]?.GetValue<double>() ?? dx;
        var origin = spec["origin_m"]?.DeepClone() ?? new JsonArray((spec["origin"]?.AsArray() ?? new JsonArray(0d, 0d, 0d)).Select(v =>
            JsonValue.Create(v!.GetValue<double>() * dx / spacing)
        ).ToArray());
        return new JsonObject { ["shape"] = spec["shape"]!.DeepClone(), ["dx"] = dx, ["origin_m"] = origin };
    }

    public static void UseBlockPreset(uint document)
    {
        var c = Get(document);
        if (c.Imported)
        {
            var settings = new CaseState().Settings(); settings["id"] = Guid.NewGuid().ToString();
            Restore(document, settings.ToJsonString());
        }
        else Edit(document, new() { ["setup"] = NativeSettings.DefaultSetup(), ["cell"] = .5, ["speed"] = 1d, ["width"] = 1d }, c.Version);
    }
}
