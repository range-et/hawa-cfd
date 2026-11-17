using Eto.Forms;
using Hawa.Shared;
using Rhino;
using Rhino.Geometry;

namespace Hawa.Native;
public sealed partial class HawaPanel
{
    private readonly TextBox exportPath = new() { Width = 240, ToolTip = "CSV destination; existing file is replaced only after successful publication." };
    private readonly DropDown exportTable = Choice("fields", "probes");
    private readonly Label exportStatus = ExportText(), probeCount = ExportText("Select Rhino point objects, then capture probes.");
    private Point3d[] exportProbes = Array.Empty<Point3d>();
    private UnitSystem probeUnits;
    private Button exportStart = null!, exportCancel = null!;

    private static Label ExportText(string text = "")
    {
        var label = Text(text);
        label.Width = 240;
        return label;
    }

    private static string ExportAbbreviation(string value) => value.Length <= 16 ? value : value.Substring(0, 13) + "…";

    private DynamicLayout ExportControls()
    {
        var layout = Layout();
        exportTable.SelectedIndex = 0;
        layout.AddSeparateRow(ExportText("Export a healthy paused or completed run. Fields contain all lattice nodes; probes sample captured Rhino point locations. Values are experimental, not convergence evidence."));
        layout.AddSeparateRow(exportTable);
        layout.AddSeparateRow(exportPath);
        layout.AddSeparateRow(Action("Browse CSV", "field", "Choose the CSV destination.", BrowseExport));
        layout.AddSeparateRow(Action("Capture selected probes", "geometry", "Capture selected point objects in this Rhino document. Later selection changes do not change this list.", CaptureProbes));
        layout.AddSeparateRow(probeCount);
        exportStart = Action("Export CSV", "field", "Capture and publish in the background. Keep the case paused or completed until capture finishes.", StartExport);
        exportCancel = Action("Cancel export", "cancel", "Cooperatively cancel this export. A file already published cannot be undone.", () =>
        {
            CaseHub.CancelExport(document);
        });
        layout.AddSeparateRow(exportStart);
        layout.AddSeparateRow(exportCancel);
        layout.AddSeparateRow(exportStatus);
        layout.AddSeparateRow(ExportText("Load CSV requires the Grasshopper moving-body workflow. Native cases are stationary and do not provide moving-body loads."));
        return layout;
    }

    private void BrowseExport()
    {
        using var dialog = new SaveFileDialog { Title = "Export Hawa CSV", FileName = exportPath.Text };
        dialog.Filters.Add(new FileFilter("CSV files", ".csv"));
        if (dialog.ShowDialog(this) == DialogResult.Ok)
            exportPath.Text = dialog.FileName;
    }

    private void CaptureProbes()
    {
        var doc = RhinoDoc.FromRuntimeSerialNumber(document) ?? throw new InvalidOperationException("Document closed.");
        var points = doc.Objects.GetSelectedObjects(false, false).Select(o =>
            o.Geometry
        ).OfType<Rhino.Geometry.Point>().Take(10001).ToArray();
        if (points.Length == 0 || points.Length > 10000)
            throw new ArgumentException("Select 1..10000 Rhino point objects in this document.");
        exportProbes = points.Select(p =>
            p.Location
        ).ToArray();
        probeUnits = doc.ModelUnitSystem;
        probeCount.Text = $"Captured probes: {exportProbes.Length} ({probeUnits})";
    }

    private void StartExport()
    {
        string table = exportTable.SelectedValue.ToString()!;
        if (table == "probes" && RhinoDoc.FromRuntimeSerialNumber(document)!.ModelUnitSystem != probeUnits)
            throw new InvalidOperationException("Document units changed. Capture probe points again.");
        CaseHub.Export(document, exportPath.Text, table, exportProbes);
    }

    private void RefreshExport(CaseState? c)
    {
        exportStart.Enabled = c != null && c.State is "paused" or "completed" && c.Session != null && c.ExportJob == null;
        exportCancel.Enabled = c?.ExportJob != null;
        if (c == null) { exportStatus.Text = "No case."; exportStatus.ToolTip = ""; return; }
        var result = c.ExportResult;
        exportStatus.ToolTip = result == null ? c.ExportError :
            $"Completed {result["table"]}: {result["rows"]} rows\n{result["path"]}\nArtifact: {result["artifact_id"]}\nCase: {result["attribution"]!["case_id"]}, revision {result["attribution"]!["revision"]}, generation {result["attribution"]!["generation"]}\nCaptured iteration {result["iteration"]}, time {result["absolute_time"]} s\nSession: {result["session"]}";
        exportStatus.Text = result == null ? $"Export: {c.ExportState}." + (c.ExportError.Length == 0 ? "" : "\nHover for error details.") :
            $"Completed {result["table"]}: {result["rows"]} rows\n{ExportAbbreviation(System.IO.Path.GetFileName(result["path"]!.GetValue<string>()))}\nArtifact: {ExportAbbreviation(result["artifact_id"]!.GetValue<string>())}\nRevision {result["attribution"]!["revision"]}\nGeneration {result["attribution"]!["generation"]}\nIteration {result["iteration"]}\nHover for full path and capture identity.";
    }
}
