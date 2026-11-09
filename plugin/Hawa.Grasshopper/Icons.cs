using System.Drawing;
using System.Drawing.Drawing2D;
using Grasshopper.Kernel;

namespace Hawa.Grasshopper;

// Original Hawa artwork. Drawn at native GH toolbar size, with distinct silhouettes.
internal static class HawaIcons
{
    private static readonly Dictionary<string, Bitmap> Cache = new();
    internal static Bitmap Get(string name)
    {
        if (Cache.TryGetValue(name, out var found)) return found;
        var b = new Bitmap(24, 24);
        using var g = Graphics.FromImage(b);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        using var p = new Pen(Color.FromArgb(20, 157, 172), 1.8f);
        using var light = new Pen(Color.FromArgb(205, 242, 239), 1.4f);
        using var fill = new SolidBrush(Color.FromArgb(22, 49, 66));
        g.FillEllipse(fill, 1, 1, 22, 22);
        if (name.Contains("Linked Case")) {
            g.DrawEllipse(p,3,6,11,11); g.DrawEllipse(light,10,6,11,11); g.DrawLine(light,8,12,16,12);
        } else if(name.Contains("Rotation") || name.Contains("Oscillation") || name.Contains("Translation")) {
            g.DrawArc(p,4,4,16,16,30,290);g.DrawLines(light,new[]{new Point(17,3),new Point(21,7),new Point(16,8)});
        } else if(name.Contains("Body") || name.Contains("Motion")) {
            g.DrawRectangle(p,5,8,10,10);g.DrawLine(light,11,5,21,5);g.DrawLines(light,new[]{new Point(17,2),new Point(21,5),new Point(17,8)});
        } else if(name.Contains("Refinement")) {
            g.DrawRectangle(p,3,4,18,16);g.DrawRectangle(light,9,9,9,8);g.DrawLine(light,13,9,13,17);g.DrawLine(light,9,13,18,13);
        } else if (name.Contains("Domain") || name.Contains("Tunnel")) {
            g.DrawRectangle(p, 5, 6, 14, 13); g.DrawLine(light, 5, 6, 9, 3); g.DrawLine(light, 19, 6, 22, 3); g.DrawLine(light, 9, 3, 22, 3); g.DrawLine(p, 10, 7, 10, 18); g.DrawLine(p, 15, 7, 15, 18); g.DrawLine(p, 6, 12, 18, 12);
        } else if (name.Contains("Hull")) {
            g.DrawPolygon(p,new[]{new Point(3,10),new Point(20,10),new Point(17,17),new Point(8,17)});g.DrawLine(light,12,4,12,10);g.DrawLines(light,new[]{new Point(5,20),new Point(10,19),new Point(16,20),new Point(21,19)});
        } else if (name.Contains("Evaluate") || name.Contains("Search") || name.Contains("Polar")) {
            g.DrawLines(p,new[]{new Point(4,5),new Point(4,20),new Point(21,20)});g.DrawLines(light,new[]{new Point(6,8),new Point(10,12),new Point(14,15),new Point(20,16)});
        } else if (name.Contains("Geometry") || name.Contains("Grid")) {
            g.FillRectangle(Brushes.LightSeaGreen, 5, 11, 6, 8); g.FillRectangle(Brushes.PaleTurquoise, 12, 5, 6, 14);
        } else if (name.Contains("Physics")) {
            g.DrawEllipse(p, 4, 8, 16, 8); g.DrawEllipse(light, 8, 4, 8, 16); g.FillEllipse(Brushes.White, 10, 10, 4, 4);
        } else if (name.Contains("Boundaries")) {
            g.DrawRectangle(p, 6, 5, 12, 14); g.DrawLine(light, 2, 12, 12, 12); g.DrawLines(light, new[] {new Point(8,8),new Point(12,12),new Point(8,16)});
        } else if (name.Contains("Checkpoint")) {
            g.DrawRectangle(p, 5, 4, 14, 16); g.DrawRectangle(light, 8, 4, 8, 6); g.DrawRectangle(light, 8, 14, 8, 6);
        } else if (name.Contains("Check")) {
            g.DrawLines(p, new[] {new Point(5,12),new Point(10,17),new Point(19,6)});
        } else if (name.Contains("Solve")) {
            g.FillPolygon(Brushes.PaleTurquoise, new[] {new Point(8,5),new Point(19,12),new Point(8,19)});
        } else if (name.Contains("Slice") || name.Contains("Plane")) {
            g.FillPolygon(Brushes.Teal, new[] {new Point(3,16),new Point(10,6),new Point(22,8),new Point(15,20)}); g.DrawLine(light, 7, 17, 14, 7); g.DrawLine(light, 11, 18, 18, 8);
        } else if (name.Contains("Streamlines") || name.Contains("Vectors") || name.Contains("Flow") || name.Contains("Particles")) {
            for(int y=6;y<=18;y+=6) { g.DrawBezier(p, 3,y, 9,y-5, 13,y+5, 21,y); } g.DrawLines(light, new[] {new Point(17,9),new Point(21,12),new Point(17,15)});
        } else if (name.Contains("Airfoil") || name.Contains("Wing")) {
            g.DrawBezier(p,3,13,6,4,15,7,22,13);g.DrawBezier(light,3,13,9,16,15,14,22,13);
        } else if (name.Contains("Color") || name.Contains("Legend")) {
            g.FillRectangle(Brushes.DarkBlue,5,5,5,14);g.FillRectangle(Brushes.Teal,10,5,5,14);g.FillRectangle(Brushes.PaleGreen,15,5,5,14);
        } else if (name.Contains("Isosurface")) {
            g.DrawEllipse(p,4,5,16,14);g.DrawEllipse(light,7,5,10,14);g.DrawLine(light,4,12,20,12);
        } else if (name.Contains("Record") || name.Contains("Playback") || name.Contains("Snapshot")) {
            g.DrawRectangle(p,3,5,18,14);g.FillEllipse(Brushes.PaleTurquoise,8,8,8,8);g.DrawLine(light,5,3,10,3);
        } else if (name.Contains("Seed")) {
            for(int x=6;x<=18;x+=6)for(int y=6;y<=18;y+=6)g.FillEllipse(Brushes.PaleTurquoise,x-1,y-1,3,3);
        } else if (name.Contains("Sample")) {
            g.DrawEllipse(p, 6, 6, 12, 12); g.DrawLine(light, 12, 3, 12, 21); g.DrawLine(light, 3, 12, 21, 12);
        } else if (name.Contains("Runtime")) {
            g.DrawRectangle(p, 6, 6, 12, 12); for(int i=8;i<=16;i+=4) {g.DrawLine(light,i,3,i,6);g.DrawLine(light,i,18,i,21);} g.DrawRectangle(light,9,9,6,6);
        } else if (name.Contains("Example")) {
            g.DrawRectangle(p, 5, 4, 14, 16); g.DrawLine(light, 9, 4, 9, 20); g.DrawLine(light, 12, 9, 17, 9); g.DrawLine(light, 12, 14, 17, 14);
        } else {
            g.DrawLine(p, 4, 6, 4, 18); g.DrawLine(p, 20, 6, 20, 18); g.DrawBezier(light, 4,12, 10,3, 14,21, 20,12);
        }
        Cache[name] = b;
        return b;
    }
}

public sealed class HawaPriority : GH_AssemblyPriority
{
    public override GH_LoadingInstruction PriorityLoad()
    {
        global::Grasshopper.Instances.ComponentServer.AddCategoryIcon("Hawa", HawaIcons.Get("Hawa"));
        global::Grasshopper.Instances.ComponentServer.AddCategoryShortName("Hawa", "HW");
        global::Grasshopper.Instances.ComponentServer.AddCategorySymbolName("Hawa", 'H');
        return GH_LoadingInstruction.Proceed;
    }
}
