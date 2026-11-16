// Minimal event-capable Eto doubles. Tests invoke production panel callbacks;
// docking, native event timing and drawing require live Rhino acceptance.
namespace Eto.Drawing {
    public record Size(int Width, int Height);
    public record Point(int X, int Y);
    public record Padding(int All);
    public record Font(SystemFont Kind, int Size);
    public enum SystemFont { Bold }
    public static class Colors { public static object DarkRed => new(); }
}
namespace Eto.Forms {
    using Eto.Drawing;
    public enum WrapMode { Word }
    public enum TextAlignment { Left }
    public enum ButtonImagePosition { Left }
    public class Control : IDisposable {
        public Window? ParentWindow { get; set; }
        public bool Enabled { get; set; } = true;
        public bool Visible { get; set; } = true;
        public int Width { get; set; }
        public string ToolTip { get; set; } = "";
        public Size? MinimumSize { get; set; }
        public virtual IEnumerable<Control> Children => Array.Empty<Control>();
        protected virtual void Dispose(bool disposing) { }
        public void Dispose() => Dispose(true);
    }
    public class Panel : Control {
        public Control? Content { get; set; }
        public override IEnumerable<Control> Children => Content == null ? Array.Empty<Control>() : new[] { Content };
    }
    public class Label : Control { public string Text { get; set; } = ""; public WrapMode Wrap { get; set; } public TextAlignment TextAlignment { get; set; } public object? TextColor { get; set; } public Font? Font { get; set; } }
    public class Button : Control {
        public string Text { get; set; } = ""; public object? Image { get; set; } public ButtonImagePosition ImagePosition { get; set; }
        public event EventHandler? Click;
        public void PerformClick() { if (Enabled) Click?.Invoke(this, EventArgs.Empty); }
    }
    public class NumericStepper : Control {
        double value;
        public double MinValue { get; set; } public double MaxValue { get; set; } public int DecimalPlaces { get; set; } public double Increment { get; set; }
        public double Value { get => value; set { if (this.value == value) return; this.value=value; ValueChanged?.Invoke(this, EventArgs.Empty); } }
        public event EventHandler? ValueChanged;
    }
    public class DropDown : Control {
        int index = -1;
        public string[] DataStore { get; set; } = Array.Empty<string>();
        public int SelectedIndex { get => index; set { if(index==value)return; index=value; SelectedIndexChanged?.Invoke(this,EventArgs.Empty); } }
        public object SelectedValue { get => index < 0 ? "" : DataStore[index]; set => SelectedIndex=Array.IndexOf(DataStore,value); }
        public event EventHandler? SelectedIndexChanged;
    }
    public class CheckBox : Control { public string Text { get; set; } = ""; public bool? Checked { get; set; } }
    public class ProgressBar : Control { public int MinValue { get; set; } public int MaxValue { get; set; } public int Value { get; set; } }
    public class ImageView : Control { public object? Image { get; set; } }
    public class DynamicLayout : Control {
        public Padding? Padding { get; set; } public Size? Spacing { get; set; }
        readonly List<Control> children = new();
        public override IEnumerable<Control> Children => children;
        public void AddSeparateRow(params Control?[] controls) => children.AddRange(controls.OfType<Control>());
        public void Add(Control? control, bool xscale=false, bool yscale=false) { if(control!=null)children.Add(control); }
    }
    public class TabControl : Control { public List<TabPage> Pages { get; } = new(); public override IEnumerable<Control> Children => Pages; }
    public class TabPage : Panel { public string Text { get; set; } = ""; }
    public class Scrollable : Panel { }
}
namespace Hawa.Native {
    public static class NativeIcons { public static object Get(string name) => name; }
    public static class NativeGeometry {
        public static Action<uint>? PickAction;
        public static void Pick(uint document) => PickAction?.Invoke(document);
        public static void FitDomain(uint document) { if (!Hawa.Shared.CaseHub.Get(document).SelectedGeometry) throw new ArgumentException("Select Rhino geometry first"); }
    }
}
namespace Rhino.Display {
    public sealed class TestViews { public TestView ActiveView { get; } = new(); public int Redraws; public void Redraw() => Redraws++; }
    public sealed class TestView { public TestViewport ActiveViewport { get; } = new(); }
    public sealed class TestViewport { public Rhino.Geometry.BoundingBox? Zoomed; public void ZoomBoundingBox(Rhino.Geometry.BoundingBox box) => Zoomed=box; }
}

namespace Eto.Forms {
    public class Window { public int Width { get; set; } public Eto.Drawing.Size? Size { get; set; } public Eto.Drawing.Point? Location { get; set; } }
    public class FloatingWindow : Window { }
}
namespace Rhino.Commands {
    public enum Result { Success }
    public enum RunMode { Interactive }
    public abstract class Command {
        public abstract string EnglishName { get; }
        protected abstract Result RunCommand(Rhino.RhinoDoc doc, RunMode mode);
        public Result Execute(Rhino.RhinoDoc doc) => RunCommand(doc,RunMode.Interactive);
    }
}
namespace Rhino.UI {
    public static class PanelIds { public static Guid Layers { get; } = Guid.NewGuid(); }
    public static class Panels {
        public static Guid HawaBar, LayersBar, OpenedBar;
        public static int Opened;
        public static Eto.Forms.Control? Panel;
        public static Guid PanelDockBar(Guid id) => id==PanelIds.Layers?LayersBar:HawaBar;
        public static void OpenPanel(Guid id) { Opened++;OpenedBar=Guid.Empty; }
        public static void OpenPanel(Guid bar,Guid id,bool selected) { Opened++;OpenedBar=bar; }
        public static object? GetPanel(Guid id,Rhino.RhinoDoc doc) => Panel;
    }
}
