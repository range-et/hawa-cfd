using System.Runtime.InteropServices;
using System.Text.Json.Nodes;
using Eto.Forms;
using Eto.Drawing;
using Rhino;
using Hawa.Shared;

namespace Hawa.Native;

[Guid("34472112-31d7-4d1e-98f9-fb6130a50501")]
public sealed class HawaPanel : Panel
{
    private readonly uint document;
    private readonly Dictionary<string, NumericStepper> numbers = new();
    private readonly NumericStepper target = new() { MinValue = 1, MaxValue = 100000, Increment = 25, DecimalPlaces = 0 };
    private readonly DropDown device = new() { DataStore = new[] { "cpu", "mps", "auto", "cuda:0" } };
    private readonly DropDown field = new() { DataStore = new[] { "speed", "pressure", "density" } };
    private readonly Label state = new() { Width = 300, Wrap = WrapMode.Word };
    private readonly Label link = new() { Width = 300, Wrap = WrapMode.Word };
    private readonly Label error = new() { Width = 300, Wrap = WrapMode.Word, TextColor = Colors.DarkRed };
    private bool refreshing;
    private long displayedVersion;
    public HawaPanel(uint documentSerialNumber)
    {
        document = documentSerialNumber;
        MinimumSize = new Size(340, 540);
        var layout = new DynamicLayout { Padding = new Padding(12), Spacing = new Size(8, 8) };
        layout.AddSeparateRow(new Label { Text = "Hawa / native prototype", Font = new Font(SystemFont.Bold, 15) });
        layout.AddSeparateRow(new Label { Text = "Block flow · 8 × 6 × 4 m domain\nFixed demonstration fluid: ν = 0.1 m²/s", Width = 300, Wrap = WrapMode.Word });
        layout.AddSeparateRow(new Label { Text = "Case settings", Font = new Font(SystemFont.Bold) });
        foreach (var p in CaseHub.Parameters) { var input = new NumericStepper { Width = 100, MinValue = p.Minimum, MaxValue = p.Maximum, Increment = p.Key == "cell" ? .25 : .1, DecimalPlaces = 2 }; numbers[p.Key] = input; input.ValueChanged += (_, _) => Edit(new() { [p.Key] = input.Value }); layout.AddSeparateRow(new Label { Width = 190, TextAlignment = TextAlignment.Left, Text = p.Label + " (" + p.Unit + ")" }, input); }
        target.ValueChanged += (_, _) => Edit(new() { ["target"] = (int)target.Value }); device.SelectedIndexChanged += (_, _) => { if (device.SelectedIndex >= 0) Edit(new() { ["device"] = device.SelectedValue.ToString() }); }; field.SelectedIndexChanged += (_, _) => { if (field.SelectedIndex >= 0) Edit(new() { ["field"] = field.SelectedValue.ToString() }); };
        layout.AddSeparateRow(new Label { Text = "Target iterations" }, target); layout.AddSeparateRow(new Label { Text = "Backend" }, device); layout.AddSeparateRow(new Label { Text = "Display field" }, field);
        Button Button(string title, Action action) { var b = new Button { Text = title }; b.Click += (_, _) => Safe(action); return b; }
        layout.AddSeparateRow(Button("Run / Resume", () => CaseHub.Run(document)), Button("Pause", () => CaseHub.Pause(document)));
        layout.AddSeparateRow(Button("Cancel", () => CaseHub.Cancel(document)), Button("Reset", () => CaseHub.Reset(document)));
        layout.AddSeparateRow(Button("Fit domain", () => { var doc = RhinoDoc.FromRuntimeSerialNumber(document)!; double s = RhinoMath.UnitScale(UnitSystem.Meters, doc.ModelUnitSystem); doc.Views.ActiveView.ActiveViewport.ZoomBoundingBox(new Rhino.Geometry.BoundingBox(Rhino.Geometry.Point3d.Origin, new Rhino.Geometry.Point3d(8 * s, 6 * s, 4 * s))); doc.Views.Redraw(); }));
        layout.AddSeparateRow(Button("Refresh field", () => CaseHub.RefreshView(document)));
        layout.AddSeparateRow(state); layout.AddSeparateRow(link); layout.AddSeparateRow(error);
        layout.AddSeparateRow(new Label { Text = "Live sync uses Hawa Linked Case in Grasshopper.\nEdits stop the previous run; press Run for the new revision.\nClosing this panel keeps the case. Reopening a file never auto-runs.\nFirst dependency setup may take time. CPU is the small-case default.", Width = 300, Wrap = WrapMode.Word });
        layout.Add(null); Content = new Scrollable { Content = layout };
        CaseHub.Changed += OnChanged; RefreshState();
    }
    protected override void Dispose(bool disposing) { if (disposing) CaseHub.Changed -= OnChanged; base.Dispose(disposing); }
    private void Safe(Action action) { try { error.Text = ""; action(); RefreshState(); } catch (Exception e) { RefreshState(); error.Text = e.GetBaseException().Message; } }
    private void Edit(JsonObject patch) { if (refreshing) return; Safe(() => CaseHub.Edit(document, patch, displayedVersion)); }
    private void OnChanged(CaseState c, string origin) { if (c.Document != document) return; if (origin == "closed") { state.Text = "CASE CLOSED"; link.Text = "Grasshopper: unlinked"; error.Text = ""; } else RefreshState(); }
    private void RefreshState()
    {
        if (RhinoDoc.FromRuntimeSerialNumber(document) == null) return;
        var c = CaseHub.Get(document); displayedVersion = c.Version; refreshing = true;
        try
        {
            foreach (var p in CaseHub.Parameters) { numbers[p.Key].Value = c.Value(p.Key); numbers[p.Key].Enabled = !c.Driven.Contains(p.Key); }
            target.Value = c.Target; device.SelectedValue = c.Device; field.SelectedValue = c.Field;
            state.Text = $"{c.State.ToUpperInvariant()} · {c.Steps} / {c.Target} steps\nCase {c.Id.ToString()[..8]} · revision {c.Revision}\nResult revision: {(c.ResultRevision < 0 ? "none" : c.ResultRevision.ToString())}";
            link.Text = c.BindingOwner == null ? "Grasshopper: unlinked" : c.Driven.Count == 0 ? "Grasshopper: live · three editable controls" : "Grasshopper: live · driven: " + string.Join(", ", c.Driven);
            error.Text = c.Error + (c.ViewError.Length > 0 ? "\nField unavailable: " + c.ViewError + ". Use Refresh field." : "") + (CaseHub.PendingCleanupCount > 0 ? "\nCleanup pending; Hawa will retry." : "");
        }
        finally { refreshing = false; }
    }
}
