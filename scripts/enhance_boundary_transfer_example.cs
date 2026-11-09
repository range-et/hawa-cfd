using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using System.Drawing;
using Rhino.Geometry;
var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
void Enhance(GH_Document d){
 if(d.Objects.OfType<GH_Component>().Any(c=>c.Name=="Hawa Plane Field"))return;
 GH_Component C(string name,float x,float y){var c=(GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper."+name+"Component"));c.CreateAttributes();c.Attributes.Pivot=new PointF(x,y);d.AddObject(c,false);return c;}
 var parent=d.Objects.OfType<GH_Component>().Single(c=>c.Name=="Hawa Record");var child=d.Objects.OfType<GH_Component>().Single(c=>c.Name=="Hawa Solve");
 foreach(var c in d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Slice"))c.Hidden=true;
 var colors=d.Objects.OfType<GH_Component>().FirstOrDefault(c=>c.Name=="Hawa Color Map")??C("ColorMap",2300,1100);((Param_Number)colors.Params.Input[2]).PersistentData.Clear();((Param_Number)colors.Params.Input[2]).SetPersistentData(1.5);
 var i=0;
 foreach(var source in new[]{parent,child}){
  var snap=C("Snapshot",2300+i*350,1300);snap.Params.Input[0].AddSource(source.Params.Output[i==0?2:0]);var plane=C("PlaneField",2700+i*350,1500);plane.Params.Input[0].AddSource(snap.Params.Output[0]);plane.Params.Input[4].AddSource(colors.Params.Output[0]);
  var r=new Rectangle3d(new Plane(new Point3d(i==0?0:1.2,i==0?0:.2,.8),Vector3d.ZAxis),new Interval(0,i==0?3.2:1.2),new Interval(0,i==0?1.6:1.2));((Param_Rectangle)plane.Params.Input[1]).SetPersistentData(r);plane.Hidden=i==0;i++;
 }
 var legend=C("Legend",3100,1100);legend.Params.Input[0].AddSource(colors.Params.Output[0]);((Param_Number)legend.Params.Input[2]).PersistentData.Clear();((Param_Number)legend.Params.Input[2]).SetPersistentData(1.0);((Param_Plane)legend.Params.Input[1]).PersistentData.Clear();((Param_Plane)legend.Params.Input[1]).SetPersistentData(new Plane(new Point3d(3.4,0,0),Vector3d.ZAxis));
}
var live=Grasshopper.Instances.ActiveCanvas.Document;Enhance(live);live.NewSolution(false);
var io=new GH_DocumentIO();var path="/Users/r2d2/Desktop/hawa-cfd/examples/grasshopper/24-boundary-flow-transfer.gh";if(!io.Open(path))throw new Exception("open failed");Enhance(io.Document);if(!io.SaveQuiet(path))throw new Exception("save failed");io.Document.Dispose();Console.WriteLine("Added shared fixed 0–1.5 m/s field views and legend; original IDs and wires preserved");
