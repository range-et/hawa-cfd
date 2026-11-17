using Eto.Forms;
using Hawa.Shared;

namespace Hawa.Native;
public sealed partial class HawaPanel
{
    private readonly TextBox dataPath = new() { Width = 240, ToolTip = "Hawa data NPZ file: accepted physics, populations and capture provenance." };
    private readonly DropDown importDevice = Choice("cpu", "auto", "mps", "cuda:0");
    private readonly Label dataStatus = ExportText();
    private Button saveData = null!, importData = null!, cancelData = null!;

    private DynamicLayout DataControls()
    {
        var layout = Layout(); importDevice.SelectedIndex = 0; importDevice.ToolTip = "Backend for importing saved data";
        layout.AddSeparateRow(ExportText("Save data keeps a complete native checkpoint. Import opens its result paused for viewing. Set a higher total target and choose Run / Resume to advance it."));
        layout.AddSeparateRow(dataPath);
        layout.AddSeparateRow(Action("Choose save file", "field", "Choose a self-contained Hawa data NPZ destination.", () =>
        {
            using var dialog = new SaveFileDialog { Title = "Save Hawa data", FileName = dataPath.Text };
            dialog.Filters.Add(new FileFilter("Hawa data", ".npz"));
            if (dialog.ShowDialog(this) == DialogResult.Ok) dataPath.Text = dialog.FileName;
        }));
        layout.AddSeparateRow(Action("Choose import file", "field", "Choose Hawa data. CSV is interchange data and cannot resume a solver.", () =>
        {
            using var dialog = new OpenFileDialog { Title = "Import Hawa data", FileName = dataPath.Text };
            dialog.Filters.Add(new FileFilter("Hawa data", ".npz"));
            if (dialog.ShowDialog(this) == DialogResult.Ok) dataPath.Text = dialog.FileName;
        }));
        layout.AddSeparateRow(ExportText("Backend for import")); layout.AddSeparateRow(importDevice);
        saveData = Action("Save data", "field", "Save a paused or completed run in the background. Existing files change only after complete publication.", () =>
        {
            CaseHub.SaveData(document, dataPath.Text);
        });
        importData = Action("Import data", "field", "Validate and restore paused in the background. Only a successful import replaces this document's case; Rhino geometry is preserved.", () =>
        {
            CaseHub.ImportData(document, dataPath.Text, importDevice.SelectedValue.ToString()!);
        });
        cancelData = Action("Cancel data operation", "cancel", "Cancel pending save/import; leave the accepted case intact.", () =>
        {
            CaseHub.CancelData(document);
        });
        layout.AddSeparateRow(saveData); layout.AddSeparateRow(importData); layout.AddSeparateRow(cancelData); layout.AddSeparateRow(dataStatus);
        layout.AddSeparateRow(ExportText("Imported physics is read-only and does not require original Rhino objects. A saved Rhino document stores the source identity only: import its NPZ again after reopening."));
        return layout;
    }

    private void RefreshData(CaseState? c)
    {
        saveData.Enabled = c != null && c.Session != null && c.State is "paused" or "completed" && c.DataJob == null;
        importData.Enabled = c?.DataJob == null;
        cancelData.Enabled = c?.DataJob != null;
        dataStatus.Text = c == null ? "Choose data to import." : $"Data: {c.DataState}." + (c.DataError.Length > 0 ? "\nHover for error details." : c.Imported && c.Session == null ? "\nImport the saved NPZ again to view or resume." : "");
        dataStatus.ToolTip = c?.DataError ?? "";
        if (c?.DataResult is System.Text.Json.Nodes.JsonObject result)
        {
            dataStatus.Text += "\nArtifact: " + ExportAbbreviation(result["metadata"]!["artifact_id"]!.GetValue<string>()) + "\nHover for capture details.";
            dataStatus.ToolTip = result["path"]!.GetValue<string>() + "\n" + result["metadata"]!.ToJsonString();
        }
    }
}
