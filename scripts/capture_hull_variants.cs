using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Rhino.Geometry;
var d=Grasshopper.Instances.ActiveCanvas.Document;
var toggle=d.Objects.OfType<GH_BooleanToggle>().First();toggle.Value=false;toggle.ExpireSolution(false);
var genes=new[]{"Bow fullness","Stern fullness","Beam / draft"}.Select(n=>d.Objects.OfType<GH_NumberSlider>().First(s=>s.NickName==n)).ToArray();
var variants=new[]{new decimal[]{.8m,.8m,2m},new decimal[]{.4m,.4m,3m},new decimal[]{1.6m,1.6m,1m},new decimal[]{.896m,1.461m,2.586m}};
var view=__rhino_doc__.Views.ActiveView;
view.ActiveViewport.SetCameraLocation(new Point3d(-4,-6,11),false);view.ActiveViewport.SetCameraTarget(new Point3d(8,6,4.5),false);view.ActiveViewport.ZoomBoundingBox(new BoundingBox(3,4.5,3.5,13,7.5,5.5));
for(int k=0;k<variants.Length;k++){
for(int j=0;j<3;j++){genes[j].SetSliderValue(variants[k][j]);genes[j].ExpireSolution(false);}d.NewSolution(false);__rhino_doc__.Views.Redraw();
var cap=new Rhino.Display.ViewCapture{Width=1920,Height=1080,ScaleScreenItems=false,DrawAxes=false,DrawGrid=false,DrawGridAxes=false};using(var b=cap.CaptureToBitmap(view))b.Save($"/Users/r2d2/Desktop/hawa-cfd/docs/captures/hull-variant-{k+1}.jpg",System.Drawing.Imaging.ImageFormat.Jpeg);
}
Console.WriteLine("Captured four parametric hull shapes from the native Grasshopper preview.");
