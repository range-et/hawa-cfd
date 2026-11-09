using Eto.Drawing;
namespace Hawa.Native;
internal static class NativeIcons
{
    private static readonly Dictionary<string, Bitmap> Images = new();
    internal static Bitmap Get(string name) {
        if (!Images.TryGetValue(name,out var image)) {
            using var stream = typeof(NativeIcons).Assembly.GetManifestResourceStream("Hawa.Rhino.Assets."+name+".png") ?? throw new InvalidOperationException("Missing Hawa icon: "+name);
            Images[name] = image = new Bitmap(stream);
        }
        return image;
    }
    internal static System.Drawing.Icon PanelIcon() {
        using var stream = typeof(NativeIcons).Assembly.GetManifestResourceStream("Hawa.Rhino.Assets.hawa.ico")!;
        using var icon = new System.Drawing.Icon(stream);
        return (System.Drawing.Icon)icon.Clone();
    }
}
