// Generate editable definitions with standard GH sliders and native Hawa nodes.
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd/examples/grasshopper";var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
foreach(int which in new[]{17,18,19}){
var d=new GH_Document();
T Add<T>(T item,float x,float y) where T:IGH_DocumentObject{item.CreateAttributes();item.Attributes.Pivot=new PointF(x,y);d.AddObject(item,false);return item;}
GH_Component C(string n,float x,float y)=>Add((GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper."+n+"Component")),x,y);
void W(IGH_Param a,GH_Component b,int i)=>b.Params.Input[i].AddSource(a);
void Connect(GH_Component a,int o,GH_Component b,int i)=>W(a.Params.Output[o],b,i);
void Number(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
void Text(GH_Component c,int i,string v){var p=(Param_String)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
GH_NumberSlider Slider(string name,decimal v,decimal lo,decimal hi,float x,float y){var s=Add(new GH_NumberSlider(),x,y);s.NickName=name;s.Slider.Minimum=lo;s.Slider.Maximum=hi;s.Slider.DecimalPlaces=3;s.SetSliderValue(v);return s;}
var title=Add(new GH_Panel(),0,-250);title.UserText=which==17?"HAWA / OSCILLATING CYLINDER":which==18?"HAWA / PITCHING NACA FOIL":"HAWA / ROTATING PADDLE";title.UserText+="\nSet Run true after preparation. Change motion sliders to start a fresh case.\nUse a new absolute directory for Record. Move Frame after recording completes.\nBody Loads returns signed fluid force, torque and power. Motion is prescribed.\nUniform BGK, single fluid, experimental moving walls. Refine the grid and check cycle convergence.\nThe body must remain clear of domain faces. No free surface, buoyancy or free-body dynamics.";title.Attributes.Bounds=new RectangleF(0,-250,1650,210);
var box=Add(new Param_Box(),0,0);box.SetPersistentData(new Box(Plane.WorldXY,new Interval(0,8),new Interval(0,6),new Interval(0,4)));box.Hidden=true;
var domain=C("Domain",270,0);W(box,domain,0);Number(domain,1,which==18?.2:.25);Text(domain,2,"meters");domain.Hidden=true;
var physics=C("Physics",270,260);Number(physics,1,.05);Text(physics,3,"bgk");Number(physics,4,which==18?.025:.04);
var spec=C("Case",550,50);Connect(domain,0,spec,0);Connect(physics,0,spec,2);
var pivot=Add(new Param_Point(),550,500);pivot.SetPersistentData(new Point3d(3,3,2));pivot.Hidden=true;
IGH_Param reference;
if(which==18){
 var airfoil=C("Airfoil",0,600);Text(airfoil,0,"0024");airfoil.Hidden=true;var wing=C("Wing",270,650);Connect(airfoil,1,wing,0);Number(wing,1,2);Number(wing,2,3);Number(wing,3,3);Number(wing,4,0);wing.Hidden=true;
 var proxy=Grasshopper.Instances.ComponentServer.ObjectProxies.First(p=>p.Desc.Name=="Move"&&p.Desc.Category=="Transform");var move=Add((GH_Component)proxy.CreateInstance(),550,700);Connect(wing,0,move,0);var shift=Add(new Param_Vector(),270,850);shift.SetPersistentData(new Vector3d(3,3,2));W(shift,move,1);move.Hidden=true;reference=move.Params.Output[0];
}else{
 var mesh=Add(new Param_Mesh(),0,600);mesh.Hidden=true;Mesh m;
 if(which==17)m=Mesh.CreateFromCylinder(new Cylinder(new Circle(new Plane(new Point3d(3,3,1),Vector3d.ZAxis),.5),2),4,48);
 else m=Mesh.CreateFromBox(new BoundingBox(new Point3d(2,2.8,1.7),new Point3d(4,3.2,2.3)),8,2,2);
 if(!m.IsClosed)throw new Exception("Reference mesh is open");mesh.SetPersistentData(m);reference=mesh;
}
var motion=C(which==19?"Rotation":"Oscillation",830,600);((Param_Vector)motion.Params.Input[0]).PersistentData.Clear();((Param_Vector)motion.Params.Input[0]).SetPersistentData(which==17?Vector3d.YAxis:which==18?Vector3d.YAxis:Vector3d.ZAxis);
var amplitude=Slider(which==19?"RPM":which==18?"Pitch amplitude (radians)":"Travel amplitude (m)",which==19?10m:which==18?.15m:.25m,which==19?1m:.02m,which==19?15m:.3m,550,350);W(amplitude,motion,1);Number(motion,2,.5);
if(which!=19){Number(motion,3,.5);if(which==18){var p=(Param_Boolean)motion.Params.Input[4];p.PersistentData.Clear();p.SetPersistentData(true);}}
var body=C("MovingBody",1100,200);Connect(spec,0,body,0);W(reference,body,1);Connect(motion,0,body,2);W(pivot,body,3);
var moving=C("MotionCase",1400,50);Connect(spec,0,moving,0);Connect(body,0,moving,1);
var check=C("Check",1650,-20);Connect(moving,0,check,0);
var solve=C("Solve",1650,150);Connect(moving,0,solve,0);var target=(Param_Integer)solve.Params.Input[2];target.PersistentData.Clear();target.SetPersistentData(300);var run=Add(new GH_BooleanToggle(),1400,320);run.NickName="Run / Pause";W(run,solve,3);
var snapshot=C("Snapshot",1900,150);Connect(solve,0,snapshot,0);
var loads=C("BodyLoads",1900,450);Connect(snapshot,0,loads,0);var preview=C("BodyPreview",2200,500);W(reference,preview,0);Connect(loads,4,preview,1);
var bounds=C("DomainPreview",1400,540);Connect(domain,0,bounds,0);
var map=C("ColorMap",1900,750);Number(map,2,1.8);var rect=Add(new Param_Rectangle(),1650,760);rect.SetPersistentData(new Rectangle3d(which==18?new Plane(new Point3d(0,3,0),Vector3d.XAxis,Vector3d.ZAxis):new Plane(new Point3d(0,0,2),Vector3d.ZAxis),new Interval(0,8),new Interval(0,which==18?4:6)));rect.Hidden=true;
var plane=C("PlaneField",2200,120);Connect(snapshot,0,plane,0);W(rect,plane,1);Connect(map,0,plane,4);
var record=C("Record",1650,1100);Connect(moving,0,record,0);var path=Add(new GH_Panel(),1300,1050);path.UserText="Choose a new absolute recording directory";W(path,record,1);var recRun=Add(new GH_BooleanToggle(),1400,1250);recRun.NickName="Record / Cancel";W(recRun,record,5);
var playback=C("Playback",1900,1100);Connect(record,0,playback,0);var frame=Slider("Frame",0,0,20,1650,1320);frame.Slider.DecimalPlaces=0;W(frame,playback,1);var recLoads=C("BodyLoads",2200,1100);Connect(playback,0,recLoads,0);var recBody=C("BodyPreview",2500,1100);W(reference,recBody,0);Connect(recLoads,4,recBody,1);recBody.Hidden=true;
var info=Add(new GH_Panel(),2500,350);info.AddSource(loads.Params.Output[2]);info.NickName="Fluid power (W)";
d.FilePath=root+"/"+which+(which==17?"-oscillating-cylinder":which==18?"-pitching-airfoil":"-rotating-paddle")+".gh";new GH_DocumentIO{Document=d}.SaveQuiet(d.FilePath);d.Dispose();Console.WriteLine(d.FilePath);
}
