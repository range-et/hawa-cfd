// Rhino MCP. Create only the new definition; never overwrite an existing example.
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd";
var path=root+"/examples/grasshopper/30-neutral-cropped-buildings.gh";
if(System.IO.File.Exists(path))throw new Exception("Preserve existing example");
var asm=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
var d=new GH_Document();
T Add<T>(T x,float a,float b) where T:IGH_DocumentObject{x.CreateAttributes();x.Attributes.Pivot=new PointF(a,b);d.AddObject(x,false);return x;}
GH_Component C(string name,float x,float y)=>Add((GH_Component)Activator.CreateInstance(asm.GetType("Hawa.Grasshopper."+name+"Component")),x,y);
void W(GH_Component a,int o,GH_Component b,int i)=>b.Params.Input[i].AddSource(a.Params.Output[o]);
void Num(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
void Text(GH_Component c,int i,string v){var p=(Param_String)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
void Int(GH_Component c,int i,int v){var p=(Param_Integer)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
var box=Add(new Param_Box(),0,50);box.NickName="Sample-centre domain [m]";box.SetPersistentData(new Box(Plane.WorldXY,new Interval(0,31),new Interval(0,17),new Interval(.5,15.5)));box.Hidden=true;
var domain=C("Domain",280,50);domain.Hidden=true;domain.Params.Input[0].AddSource(box);Num(domain,1,1);Text(domain,2,"meters");
var bodies=Add(new Param_Box(),0,300);bodies.NickName="Closed buildings / edit boxes";
bodies.SetPersistentData(new Box(Plane.WorldXY,new Interval(-3,4.4),new Interval(4.6,8.4),new Interval(-1,5.2)),new Box(Plane.WorldXY,new Interval(11.6,16.4),new Interval(9.6,12.4),new Interval(-1,7.2)));
var geometry=C("Geometry",550,250);W(domain,0,geometry,0);geometry.Params.Input[3].AddSource(bodies);
var physics=C("Physics",280,550);Num(physics,0,5);Num(physics,1,1.5e-5);Num(physics,4,.05);
var baseCase=C("Case",830,100);W(domain,0,baseCase,0);W(geometry,0,baseCase,1);W(physics,0,baseCase,2);
var flow=C("NeutralPrecursor",1110,140);W(baseCase,0,flow,0);Num(flow,1,6);Num(flow,2,.01);Int(flow,6,1);Num(flow,7,3);
((Param_Boolean)flow.Params.Input[5]).PersistentData.Clear();((Param_Boolean)flow.Params.Input[5]).SetPersistentData(true);
var z0=Add(new GH_NumberSlider(),830,600);z0.NickName="z0 [m]";z0.Slider.Minimum=.001m;z0.Slider.Maximum=.2m;z0.Slider.DecimalPlaces=3;z0.SetSliderValue(.01m);flow.Params.Input[2].AddSource(z0);
string[] faces={"x-","x+","y-","y+","z-","z+"};string[] kinds={"velocity","open","periodic","periodic","wall","open"};
for(int i=0;i<6;i++){
 var p=C("BoundaryPatch",550,800+170*i);p.NickName=faces[i]+" / "+kinds[i];Text(p,0,faces[i]);Text(p,1,kinds[i]);
 if(i<2){var v=(Param_Vector)p.Params.Input[2];v.PersistentData.Clear();v.SetPersistentData(new Vector3d(i==0?5:-5,0,0));Text(p,4,"neutral");}
 flow.Params.Input[8].AddSource(p.Params.Output[0]);
}
var solve=C("Solve",1390,160);W(flow,0,solve,0);Text(solve,1,"mps");Int(solve,2,1000);
var run=Add(new GH_BooleanToggle(),1110,520);run.NickName="Run";run.Value=false;solve.Params.Input[3].AddSource(run);
var reset=Add(new GH_BooleanToggle(),1110,600);reset.NickName="Reset";reset.Value=false;solve.Params.Input[4].AddSource(reset);
var quality=C("ResultQuality",1670,100);W(solve,0,quality,0);var panel=Add(new GH_Panel(),1950,60);panel.NickName="Quality + boundary budget";panel.AddSource(quality.Params.Output[2]);
var snap=C("Snapshot",1670,350);W(solve,0,snap,0);
var colors=C("ColorMap",1390,700);Num(colors,2,8);
var view=C("PlaneField",1950,430);W(snap,0,view,0);W(colors,0,view,4);
var rect=(Param_Rectangle)view.Params.Input[1];rect.PersistentData.Clear();rect.SetPersistentData(new Rectangle3d(new Plane(new Point3d(0,0,2.5),Vector3d.XAxis,Vector3d.YAxis),new Interval(0,31),new Interval(0,17)));
var legend=C("Legend",1950,780);W(colors,0,legend,0);Num(legend,2,5);var lp=(Param_Plane)legend.Params.Input[1];lp.PersistentData.Clear();lp.SetPersistentData(new Plane(new Point3d(34,0,2.5),Vector3d.XAxis,Vector3d.YAxis));
var preview=C("DomainPreview",830,750);W(domain,0,preview,0);
d.FilePath=path;if(!new GH_DocumentIO{Document=d}.SaveQuiet(path))throw new Exception("Save failed");d.Dispose();Console.WriteLine(path);
