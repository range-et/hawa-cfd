using Eto.Forms;
using Hawa.Shared;
using Rhino;
using Rhino.Geometry;

namespace Hawa.Native;
public sealed partial class HawaPanel
{
    private readonly TextBox exportPath = new() { ToolTip = "CSV destination; existing file is replaced only after successful publication." };
    private readonly DropDown exportTable = Choice("fields", "probes");
    private readonly Label exportStatus = Text(), probeCount = Text("Select Rhino point objects, then capture probes.");
    private Point3d[] exportProbes = Array.Empty<Point3d>();
    private UnitSystem probeUnits;
    private Button exportStart = null!, exportCancel = null!;

    private DynamicLayout ExportControls()
    {
        var layout = Layout();
        exportTable.SelectedIndex = 0;
        layout.AddSeparateRow(Text("Export a healthy completed run. Fields contain all lattice nodes; probes sample captured Rhino point locations. Values are experimental, not convergence evidence."));
        layout.AddSeparateRow(exportTable);
        layout.AddSeparateRow(exportPath, Action("Browse CSV", "field", "Choose the CSV destination.", BrowseExport));
        layout.AddSeparateRow(Action("Capture selected probes", "geometry", "Capture selected point objects in this Rhino document. Later selection changes do not change this list.", CaptureProbes), probeCount);
        exportStart = Action("Export CSV", "field", "Capture and publish in the background. Keep the case completed until capture finishes.", StartExport);
        exportCancel = Action("Cancel export", "cancel", "Cooperatively cancel this export. A file already published cannot be undone.", () =>
        {
            CaseHub.CancelExport(document);
        });
        layout.AddSeparateRow(exportStart, exportCancel);
        layout.AddSeparateRow(exportStatus);
        layout.AddSeparateRow(Text("Load CSV requires the Grasshopper moving-body workflow. Native cases are stationary and do not provide moving-body loads."));
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
        exportStart.Enabled = c != null && c.State == "completed" && c.Session != null && c.ExportJob == null;
        exportCancel.Enabled = c?.ExportJob != null;
        if (c == null) { exportStatus.Text = "No case."; return; }
        var result = c.ExportResult;
        exportStatus.Text = result == null ? $"Export: {c.ExportState}. {c.ExportError}" :
            $"Completed {result["table"]}: {result["rows"]} rows\n{result["path"]}\nArtifact: {result["artifact_id"]}\nCase: {result["attribution"]!["case_id"]}, revision {result["attribution"]!["revision"]}, generation {result["attribution"]!["generation"]}\nCaptured iteration {result["iteration"]}, time {result["absolute_time"]} s\nSession: {result["session"]}";
    }
}
