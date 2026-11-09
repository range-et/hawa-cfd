using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Rhino.Geometry;
try{
var root="/Users/r2d2/Desktop/hawa-cfd/examples/grasshopper";var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");var d=new GH_Document();
T Add<T>(T c,float x,float y)where T:IGH_DocumentObject{c.CreateAttributes();c.Attributes.Pivot=new PointF(x,y);d.AddObject(c,false);return c;}
GH_Component C(string n,float x,float y)=>Add((GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper."+n+"Component")),x,y);
void W(GH_Component a,int o,GH_Component b,int i)=>b.Params.Input[i].AddSource(a.Params.Output[o]);
void Text(GH_Component c,int i,string v){var p=(Param_String)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
void Num(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
var note=Add(new GH_Panel(),0,-200);note.UserText="HAWA / CYLINDER WAKE\nSet a new absolute recording directory. Run records 8000 steps; Pause suspends the worker.\nAfter completion move Frame from 0 to 80. The plane shows speed; tubes follow that snapshot.\nTransverse and spanwise faces are periodic. This is a thin computational strip.\nRe = 100 based on the 2 m diameter. Validate grid and domain size before using engineering results.\nThe video uses an analytical cylinder mask and a small seed perturbation. This mesh example is a separate editable run.";note.Attributes.Bounds=new RectangleF(0,-200,1500,180);
var box=Add(new Param_Box(),0,50);box.Hidden=true;box.SetPersistentData(new Box(Plane.WorldXY,new Interval(0,24),new Interval(0,12),new Interval(0,.45)));var domain=C("Domain",300,50);domain.Hidden=true;domain.Params.Input[0].AddSource(box);Num(domain,1,.15);Text(domain,2,"meters");
var mesh=Add(new Param_Mesh(),0,280);var cylinder=new Cylinder(new Circle(new Plane(new Point3d(6,6.045,-1),Vector3d.ZAxis),1),3);mesh.SetPersistentData(Mesh.CreateFromCylinder(cylinder,2,64));
var geometry=C("Geometry",650,100);geometry.Hidden=true;W(domain,0,geometry,0);geometry.Params.Input[1].AddSource(mesh);
var physics=C("Physics",650,370);Num(physics,1,.02);Text(physics,3,"bgk");Num(physics,4,.1);
var boundary=C("Boundaries",650,650);for(int i=2;i<6;i++)Text(boundary,i,"periodic");
var spec=C("Case",1000,180);W(domain,0,spec,0);W(geometry,0,spec,1);W(physics,0,spec,2);W(boundary,0,spec,3);
var record=C("Record",1350,180);W(spec,0,record,0);((Param_Integer)record.Params.Input[2]).PersistentData.Clear();((Param_Integer)record.Params.Input[2]).SetPersistentData(8000);((Param_Integer)record.Params.Input[3]).PersistentData.Clear();((Param_Integer)record.Params.Input[3]).SetPersistentData(100);
var path=Add(new GH_Panel(),1000,430);path.UserText="Choose a new absolute recording directory";path.Attributes.Bounds=new RectangleF(1000,430,290,90);record.Params.Input[1].AddSource(path);var run=Add(new GH_BooleanToggle(),1000,570);run.NickName="Record / Cancel";record.Params.Input[5].AddSource(run);var pause=Add(new GH_BooleanToggle(),1000,630);pause.NickName="Pause";record.Params.Input[6].AddSource(pause);
var playback=C("Playback",1700,180);W(record,0,playback,0);var index=Add(new GH_NumberSlider(),1400,440);index.NickName="Frame";index.Slider.Minimum=0;index.Slider.Maximum=80;index.Slider.DecimalPlaces=0;index.SetSliderValue(0);playback.Params.Input[1].AddSource(index);
var colors=C("ColorMap",1700,470);Num(colors,2,1.6);var rect=Add(new Param_Rectangle(),1700,650);rect.Hidden=true;rect.SetPersistentData(new Rectangle3d(new Plane(new Point3d(0,0,.15),Vector3d.ZAxis),new Interval(0,24),new Interval(0,12)));var plane=C("PlaneField",2050,180);W(playback,0,plane,0);plane.Params.Input[1].AddSource(rect);W(colors,0,plane,4);((Param_Integer)plane.Params.Input[2]).PersistentData.Clear();((Param_Integer)plane.Params.Input[2]).SetPersistentData(80);
var bounds=C("DomainPreview",1000,820);W(domain,0,bounds,0);
var seedsBox=Add(new Param_Box(),1700,900);seedsBox.Hidden=true;seedsBox.SetPersistentData(new Box(Plane.WorldXY,new Interval(1,2),new Interval(1,11),new Interval(.1,.3)));var seeds=C("Seeds",2050,650);seeds.Params.Input[0].AddSource(seedsBox);seeds.Hidden=true;var flow=C("FlowDisplay",2400,350);W(playback,0,flow,0);W(seeds,0,flow,1);W(colors,0,flow,2);
d.FilePath=root+"/16-cylinder-wake-recording.gh";new GH_DocumentIO{Document=d}.SaveQuiet(d.FilePath);Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;d.NewSolution(false);Console.WriteLine(d.FilePath);

}catch(Exception e){Console.WriteLine(e.ToString());}
