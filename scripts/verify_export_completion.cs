// Run through Rhino MCP after installing this candidate. Adjust root only.
// Creates one owned headless Rhino document; preserves every existing Rhino/GH document.
// Public native service acceptance, not docking/file-dialog acceptance or numerical qualification.
// No busy waiting: each timer callback performs one bounded phase and returns.
using System.Text;
using System.Text.Json.Nodes;
using System.Globalization;
using Rhino;
using Rhino.Geometry;
var root = "/Users/r2d2/Desktop/hawa-issue-35-complete";
var output = System.IO.Path.Combine(root, "results", "native-export-host", DateTime.UtcNow.ToString("yyyyMMdd-HHmmss") + "-" + Guid.NewGuid().ToString("N"));
System.IO.Directory.CreateDirectory(output);
var assembly = AppDomain.CurrentDomain.GetAssemblies().Single(a => a.GetName().Name == "Hawa.Shared");
var hub = assembly.GetType("Hawa.Shared.CaseHub");
object Call(string name, params object[] args) => hub.GetMethod(name).Invoke(null, args);
int Cleanup() => (int)hub.GetProperty("PendingCleanupCount").GetValue(null);
if (Cleanup() != 0) throw new Exception("Pending pre-existing cleanup: finish it before isolated acceptance.");
var original = __rhino_doc__;
uint originalSerial = original.RuntimeSerialNumber;
var owned = RhinoDoc.CreateHeadless(null);
if (owned == null) throw new Exception("Could not create isolated Rhino document.");
owned.ModelUnitSystem = UnitSystem.Millimeters;
uint serial = owned.RuntimeSerialNumber;
dynamic c = Call("Get", serial);
var report = new JsonObject { ["state"] = "running", ["document"] = serial, ["preserved_document"] = originalSerial, ["backend"] = "cpu", ["target"] = 2, ["model_units"] = "millimetres", ["shared_assembly"] = assembly.Location };
var checks = new JsonArray();
var timer = new Eto.Forms.UITimer { Interval = .2 };
string timerKey = "Hawa.NativeExportVerification." + Guid.NewGuid().ToString("N");
// Strong process-owned root until stop, including pending cancellation/disposal phases.
AppDomain.CurrentDomain.SetData(timerKey, timer);
int phase = 0;
DateTime began = DateTime.UtcNow;
bool disposed = false;
string fieldPath = System.IO.Path.Combine(output, "fields.csv"), probePath = System.IO.Path.Combine(output, "probes.csv"), cancelPath = System.IO.Path.Combine(output, "cancel.csv"), recoveryPath = System.IO.Path.Combine(output, "recovery.csv"), closePath = System.IO.Path.Combine(output, "close.csv");
string session = "", cancelJob = "", closeJob = "";
JsonObject captured = null;
List<string[]> fields = null;
void Check(bool pass, string message) { if (!pass) throw new Exception(message); }
JsonObject Copy(JsonNode node) => JsonNode.Parse(node.ToJsonString()).AsObject();
void Save(string state) { report["state"] = state; report["phase"] = phase; report["checks"] = JsonNode.Parse(checks.ToJsonString()); System.IO.File.WriteAllText(System.IO.Path.Combine(output, "rhino.json"), report.ToJsonString()); }
void Pass(string text) { checks.Add(text); phase++; began = DateTime.UtcNow; Save("running"); }
void Edit(JsonObject patch) => Call("Edit", serial, patch, (long)c.Version, "panel", true);
void Export(string path, string table, Point3d[] points = null) => Call("Export", serial, path, table, points);
void DisposeOwned() { if (disposed) return; Call("Close", serial); owned.Dispose(); disposed = true; }
void Stop() { timer.Stop(); timer.Dispose(); AppDomain.CurrentDomain.SetData(timerKey, null); }
double Number(string value) => double.Parse(value, CultureInfo.InvariantCulture);
List<string[]> ReadCsv(string path)
{
    // RFC-style quoted records; JSON preambles may contain embedded quotes/newlines.
    string text = System.IO.File.ReadAllText(path);
    var records = new List<string[]>(); var record = new List<string>(); var cell = new StringBuilder(); bool quoted = false;
    for (int i = 0; i < text.Length; i++)
    {
        char ch = text[i];
        if (ch == '"') { if (quoted && i + 1 < text.Length && text[i + 1] == '"') { cell.Append('"'); i++; } else quoted = !quoted; }
        else if (!quoted && ch == ',') { record.Add(cell.ToString()); cell.Clear(); }
        else if (!quoted && (ch == '\r' || ch == '\n')) { if (ch == '\r' && i + 1 < text.Length && text[i + 1] == '\n') i++; record.Add(cell.ToString()); cell.Clear(); records.Add(record.ToArray()); record.Clear(); }
        else cell.Append(ch);
    }
    Check(!quoted && cell.Length == 0 && record.Count == 0, "CSV is truncated or has an unterminated record.");
    Check(records.Count >= 3 && records[0].Length == 2, "Missing CSV preamble/header/data.");
    var metadata = JsonNode.Parse(records[0][1]);
    Check(metadata["columns"].AsArray().Select(v => v.GetValue<string>()).SequenceEqual(records[1]), "CSV header differs from declared columns.");
    Check(records.Count == metadata["rows"].GetValue<int>() + 2, "CSV row count differs from preamble.");
    Check(records.Skip(2).All(r => r.Length == records[1].Length), "CSV row width differs from header.");
    return records;
}
void Identity(JsonObject result, string path, string table)
{
    Check(result["path"].GetValue<string>() == path && result["table"].GetValue<string>() == table, "Completed export path/table mismatch.");
    Check(result["session"].GetValue<string>() == session && result["iteration"].GetValue<int>() == 2 && result["source_state"].GetValue<string>() == "completed", "Completed export capture mismatch.");
    Check(result["attribution"]["case_id"].GetValue<string>() == ((Guid)c.Id).ToString() && result["attribution"]["revision"].GetValue<long>() == (long)c.Revision, "Completed export attribution mismatch.");
    Check(result["case_hash"].GetValue<string>() == ((JsonObject)c.Status)["case_hash"].GetValue<string>(), "Completed export case hash mismatch.");
}
timer.Elapsed += (_, e) =>
{
    try
    {
        if ((DateTime.UtcNow - began).TotalSeconds > 120) throw new Exception("Timeout at phase " + phase);
        if (!disposed && (string)c.State == "failed") throw new Exception("Native solver failed: " + (string)c.Error);
        switch (phase)
        {
            case 0:
                Edit(new JsonObject { ["device"] = "cpu", ["cell"] = .5, ["target"] = 2 });
                var watch = System.Diagnostics.Stopwatch.StartNew(); Call("Run", serial); report["run_submit_ms"] = watch.Elapsed.TotalMilliseconds;
                Pass("isolated millimetre native CPU case submitted for two steps"); break;
            case 1:
                if ((string)c.State != "completed" || c.Result == null || (int)c.Result.Steps != 2) return;
                session = (string)c.Session; report["session"] = session; report["before_export"] = Copy((JsonObject)c.Describe());
                Check(((JsonObject)c.Spec)["spacing"].GetValue<double>() == 500, "Native millimetre mapping is not 500 model units per cell.");
                watch = System.Diagnostics.Stopwatch.StartNew(); Export(fieldPath, "fields"); report["export_submit_ms"] = watch.Elapsed.TotalMilliseconds;
                Check(c.ExportJob != null, "Export did not retain a pending job."); Pass("completed field export submitted independently of preview"); break;
            case 2:
                if ((string)c.ExportState == "failed") throw new Exception((string)c.ExportError);
                if ((string)c.ExportState != "completed") return;
                captured = Copy((JsonObject)c.ExportResult); Identity(captured, fieldPath, "fields"); fields = ReadCsv(fieldPath); Check(fields[0][0] == "hawa-field-csv-1", "Wrong field schema marker.");
                var metadata = JsonNode.Parse(fields[0][1]); Check(metadata["artifact_id"].GetValue<string>() == captured["artifact_id"].GetValue<string>(), "File artifact differs from completed result.");
                Check(metadata["rows"].GetValue<int>() == 17 * 13 * 9, "Unexpected field shape/rows."); report["field_result"] = captured;
                // Capture actual owned Rhino point object geometry, not live references. Solid and out-of-domain probes remain explicit.
                var ids = new[] { owned.Objects.AddPoint(new Point3d(1000, 1000, 1000)), owned.Objects.AddPoint(new Point3d(3000, 3000, 2000)), owned.Objects.AddPoint(new Point3d(-500, 0, 0)) };
                var points = ids.Select(id => ((Rhino.Geometry.Point)owned.Objects.FindId(id).Geometry).Location).ToArray();
                Export(probePath, "probes", points); Edit(new JsonObject { ["field"] = "pressure" });
                Pass("field CSV read back; probes submitted while independent preview field changes"); break;
            case 3:
                if ((string)c.ExportState == "failed") throw new Exception((string)c.ExportError);
                if ((string)c.ExportState != "completed" || c.Result == null || (string)c.Result.Field != "pressure") return;
                var result = Copy((JsonObject)c.ExportResult); Identity(result, probePath, "probes"); var probes = ReadCsv(probePath); Check(probes[0][0] == "hawa-probe-csv-1", "Wrong probe schema marker."); Check(probes.Count == 5, "Expected three probe rows.");
                var fluid = probes[2]; Check(fluid[7] == "1" && Number(fluid[1]) == 2 && Number(fluid[4]) == 1 && Number(fluid[5]) == 1 && Number(fluid[6]) == 1, "Millimetre probe did not map to lattice2/world1 metre.");
                var node = fields.Skip(2).Single(row => row[0] == "2" && row[1] == "2" && row[2] == "2");
                Check(node[8] == "1", "Chosen comparison node is not valid.");
                for (int q = 0; q < 5; q++) Check(Number(fluid[8 + q]) == Number(node[9 + q]), "Raw integer-node probe differs from field quantity " + q);
                Check(probes[3][7] == "0" && probes[4][7] == "0" && probes.Skip(3).All(row => row.Skip(8).All(string.IsNullOrEmpty)), "Invalid probes lost validity/blanks.");
                Check((string)c.Session == session && (int)c.Steps == 2 && (string)c.Field == "pressure", "Export changed solver/preview ownership."); report["probe_result"] = result; report["raw_integer_probe_comparison"] = "5/5 values exact";
                Export(cancelPath, "fields"); cancelJob = (string)c.ExportJob; Call("CancelExport", serial); Check(c.ExportJob == null && (string)c.ExportState == "cancelled", "Immediate cancel retained export ownership."); report["cancel_job"] = cancelJob;
                Pass("probe values, units, validity and preview independence verified; immediate cancel submitted"); break;
            case 4:
                if (Cleanup() != 0 || (DateTime.UtcNow - began).TotalSeconds < 2) return;
                // Cancellation can race atomic publication; inspect rather than claim deterministic pre-publication cancellation.
                if (System.IO.File.Exists(cancelPath)) { ReadCsv(cancelPath); report["cancel_publication"] = "complete file published before cancellation; no rollback claimed"; }
                else report["cancel_publication"] = "no file published";
                var directoryTarget = System.IO.Path.Combine(output, "directory-is-not-a-file.csv"); System.IO.Directory.CreateDirectory(directoryTarget); Export(directoryTarget, "fields");
                Pass("cancel cleanup acknowledged; destination failure submitted"); break;
            case 5:
                if ((string)c.ExportState == "pending") return;
                Check((string)c.ExportState == "failed" && !string.IsNullOrWhiteSpace((string)c.ExportError), "Directory destination did not fail visibly.");
                Check((string)c.State == "completed" && (string)c.Session == session && string.IsNullOrEmpty((string)c.ViewError), "Export IO failure damaged solver/preview."); report["expected_io_error"] = (string)c.ExportError;
                Export(recoveryPath, "fields"); Pass("destination failure isolated; recovery export submitted"); break;
            case 6:
                if ((string)c.ExportState == "failed") throw new Exception((string)c.ExportError);
                if ((string)c.ExportState != "completed") return;
                Identity((JsonObject)c.ExportResult, recoveryPath, "fields"); ReadCsv(recoveryPath); report["recovery_result"] = Copy((JsonObject)c.ExportResult);
                Export(closePath, "fields"); closeJob = (string)c.ExportJob; report["close_job"] = closeJob; DisposeOwned(); Check(Call("Find", serial) == null, "Disposed case remains registered.");
                Pass("IO failure recovered; owned document closed with pending export"); break;
            case 7:
                if (Cleanup() != 0 || (DateTime.UtcNow - began).TotalSeconds < 2) return;
                Check(RhinoDoc.FromRuntimeSerialNumber(originalSerial) == original, "Original Rhino document changed.");
                if (System.IO.File.Exists(closePath)) { ReadCsv(closePath); report["close_publication"] = "complete file published before close; no rollback claimed"; } else report["close_publication"] = "no file published";
                Check(!System.IO.Directory.GetFiles(output, ".hawa-export.*.tmp").Any(), "Export temporary leaked.");
                report["pending_cleanup"] = Cleanup();
                report["limits"] = "Public native service and file readback on CPU only. No file-dialog/docking or GH load-export check here. Cancellation timing is a real race, not deterministic pre-publication injection. Cleanup0 is acknowledgement, not worker exit: perform a separate same-process jobs/sessions/workers audit for recorded session/job IDs. No convergence/engineering accuracy claim.";
                Stop(); Save("passed"); break;
        }
    }
    catch (Exception error)
    {
        report["error"] = error.ToString();
        try { DisposeOwned(); } catch (Exception cleanupError) { report["cleanup_error"] = cleanupError.ToString(); }
        Stop(); Save("failed");
    }
};
Save("running"); timer.Start(); Console.WriteLine("Native export check queued: " + output + "/rhino.json; owned headless document " + serial);
