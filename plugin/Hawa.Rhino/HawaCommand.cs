using Eto.Forms;
using Rhino;
using Rhino.Commands;
namespace Hawa.Native;

public sealed class HawaCommand : Rhino.Commands.Command
{
    public override string EnglishName => "Hawa";
    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
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
