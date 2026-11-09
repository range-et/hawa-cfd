using System.Runtime.InteropServices;
using Eto.Forms;
using Rhino;
using Rhino.Commands;
using Rhino.FileIO;
using Rhino.PlugIns;
using Hawa.Shared;

namespace Hawa.Native;

[Guid("8a52c518-ad40-459c-8fb4-a745c5db0500")]
public sealed class HawaPlugin : PlugIn
{
    private UITimer? timer;
    private NativePreview? preview;
    protected override LoadReturnCode OnLoad(ref string errorMessage)
    {
        Rhino.UI.Panels.RegisterPanel(this, typeof(HawaPanel), "Hawa", null);
        preview = new NativePreview { Enabled = true };
        timer = new UITimer { Interval = .2 }; timer.Elapsed += (_, _) => CaseHub.Tick(); timer.Start();
        RhinoDoc.CloseDocument += Closed;
        CaseHub.Changed += Redraw;
        return LoadReturnCode.Success;
    }
    private static void Closed(object? sender, DocumentEventArgs e) => CaseHub.Close(e.Document.RuntimeSerialNumber);
    private static void Redraw(CaseState c, string origin) => RhinoDoc.FromRuntimeSerialNumber(c.Document)?.Views.Redraw();
    protected override void OnShutdown() { timer?.Stop(); foreach (var c in CaseHub.All) CaseHub.Close(c.Document); preview?.Dispose(); RhinoDoc.CloseDocument -= Closed; CaseHub.Changed -= Redraw; base.OnShutdown(); }
    protected override bool ShouldCallWriteDocument(FileWriteOptions options) => true;
    protected override void WriteDocument(RhinoDoc doc, BinaryArchiveWriter archive, FileWriteOptions options)
    {
        var c = CaseHub.Find(doc.RuntimeSerialNumber); archive.WriteString(c == null ? "" : c.Settings().ToJsonString());
    }
    protected override void ReadDocument(RhinoDoc doc, BinaryArchiveReader archive, FileReadOptions options)
    {
        string json = archive.ReadString(); if (json.Length > 0) try { CaseHub.Restore(doc.RuntimeSerialNumber, json); } catch (Exception e) { RhinoApp.WriteLine("Hawa case was not restored: " + e.Message); }
    }
}

public sealed class HawaCommand : Rhino.Commands.Command
{
    public override string EnglishName => "Hawa";
    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        CaseHub.Get(doc.RuntimeSerialNumber);
        var id = typeof(HawaPanel).GUID;
        var bar = Rhino.UI.Panels.PanelDockBar(id);
        if (bar == Guid.Empty) bar = Rhino.UI.Panels.PanelDockBar(Rhino.UI.PanelIds.Layers);
        if (bar != Guid.Empty) Rhino.UI.Panels.OpenPanel(bar, id, true); else Rhino.UI.Panels.OpenPanel(id);
        var panel = Rhino.UI.Panels.GetPanel(typeof(HawaPanel).GUID, doc) as Control;
        var window = panel?.ParentWindow;
        if (window != null && window.GetType().Name.Contains("Floating") && window.Width < 340) { window.Size = new Eto.Drawing.Size(380, 680); window.Location = new Eto.Drawing.Point(120, 120); }
        return Result.Success;
    }
}
