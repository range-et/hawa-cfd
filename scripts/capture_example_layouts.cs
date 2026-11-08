// Render all supported example canvases without starting their solvers.
using System.Drawing;
using Grasshopper.Kernel;
var root="/Users/r2d2/Desktop/hawa-cfd";var output=root+"/results/motion/example-layouts";System.IO.Directory.CreateDirectory(output);
foreach(var file in System.IO.Directory.GetFiles(root+"/examples/grasshopper","*.gh").OrderBy(x=>x)){
 if(System.IO.Path.GetFileName(file).StartsWith("09-"))continue;
 var io=new GH_DocumentIO();if(!io.Open(file))throw new Exception("Open failed");var d=io.Document;
 foreach(var o in d.Objects){o.Attributes.ExpireLayout();o.Attributes.PerformLayout();}
 var bounds=d.Objects.Select(o=>o.Attributes.Bounds).Aggregate(RectangleF.Union);bounds.Inflate(45,45);var rect=Rectangle.Ceiling(bounds);
 using(var canvas=new Grasshopper.GUI.Canvas.GH_Canvas()){
  canvas.Document=d;var vp=new Grasshopper.GUI.Canvas.GH_Viewport(new Point(-rect.Left,-rect.Top),1f){Width=rect.Width,Height=rect.Height};
  using(var image=canvas.GenerateHiResImageTile(vp,Color.FromArgb(236,236,231)))image.Save(output+"/"+System.IO.Path.GetFileNameWithoutExtension(file)+".png",System.Drawing.Imaging.ImageFormat.Png);
  canvas.Document=null;
 }
 d.Dispose();
}
Console.WriteLine("Rendered 19 example layouts without solving");
