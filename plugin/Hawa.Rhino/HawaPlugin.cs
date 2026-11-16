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
        Rhino.UI.Panels.RegisterPanel(this, typeof(HawaPanel), "Hawa", NativeIcons.PanelIcon());
        CaseHub.PrepareGeometry = NativeGeometry.Prepare;
        RhinoDoc.DeleteRhinoObject += GeometryDeleted;
        RhinoDoc.ReplaceRhinoObject += GeometryReplaced;
        RhinoDoc.UndeleteRhinoObject += GeometryDeleted;
        preview = new NativePreview { Enabled = true };
        timer = new UITimer { Interval = .2 }; timer.Elapsed += (_, _) => CaseHub.Tick(); timer.Start();
        RhinoDoc.CloseDocument += Closed;
        CaseHub.Changed += Redraw;
        return LoadReturnCode.Success;
    }
    private static void GeometryDeleted(object? sender, Rhino.DocObjects.RhinoObjectEventArgs e) { try { CaseHub.GeometryChanged(e.TheObject.Document.RuntimeSerialNumber,e.ObjectId); } catch (Exception error) { RhinoApp.WriteLine("Hawa geometry update: "+error.Message); } }
    private static void GeometryReplaced(object? sender, Rhino.DocObjects.RhinoReplaceObjectEventArgs e) { try { CaseHub.GeometryChanged(e.Document.RuntimeSerialNumber,e.ObjectId); } catch (Exception error) { RhinoApp.WriteLine("Hawa geometry update: "+error.Message); } }
    private static void Closed(object? sender, DocumentEventArgs e) => CaseHub.Close(e.Document.RuntimeSerialNumber);
    private static void Redraw(CaseState c, string origin) => RhinoDoc.FromRuntimeSerialNumber(c.Document)?.Views.Redraw();
    protected override void OnShutdown() { timer?.Stop(); RhinoDoc.DeleteRhinoObject -= GeometryDeleted; RhinoDoc.ReplaceRhinoObject -= GeometryReplaced; RhinoDoc.UndeleteRhinoObject -= GeometryDeleted; CaseHub.PrepareGeometry = null; foreach (var c in CaseHub.All) CaseHub.Close(c.Document); preview?.Dispose(); RhinoDoc.CloseDocument -= Closed; CaseHub.Changed -= Redraw; base.OnShutdown(); }
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
