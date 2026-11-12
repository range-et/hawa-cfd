// Add ordinary GH recipes for previously uncovered public operations. Never overwrite.
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd";
var asm=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
foreach(int number in new[]{31,32}){
 var path=root+"/examples/grasshopper/"+number+(number==31?"-tunnel-probes-checkpoint":"-translation-particle-recording")+".gh";
 if(System.IO.File.Exists(path))throw new Exception("Preserve existing example "+path);
 var d=new GH_Document();
 T Add<T>(T x,float a,float b) where T:IGH_DocumentObject{x.CreateAttributes();x.Attributes.Pivot=new PointF(a,b);d.AddObject(x,false);return x;}
 GH_Component C(string name,float x,float y)=>Add((GH_Component)Activator.CreateInstance(asm.GetType("Hawa.Grasshopper."+name+"Component")),x,y);
 void W(GH_Component a,int o,GH_Component b,int i)=>b.Params.Input[i].AddSource(a.Params.Output[o]);
 void Num(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
 void Text(GH_Component c,int i,string v){var p=(Param_String)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
 void Int(GH_Component c,int i,int v){var p=(Param_Integer)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
 GH_BooleanToggle Toggle(string name,GH_Component c,int i,float x,float y){var t=Add(new GH_BooleanToggle(),x,y);t.NickName=name;t.Value=false;c.Params.Input[i].AddSource(t);return t;}
 var mesh=Add(new Param_Mesh(),0,200);mesh.NickName="Closed body mesh / replace";mesh.SetPersistentData(Mesh.CreateFromBox(new BoundingBox(new Point3d(4.1,4.1,4.1),new Point3d(6.9,6.9,6.9)),2,2,2));
 var physics=C("Physics",300,500);Num(physics,0,1);Num(physics,1,.1);Text(physics,3,number==31?"regularized":"bgk");Num(physics,4,.05);
 var spec=C("Case",900,200);W(physics,0,spec,2);
 var points=Add(new Param_Point(),1200,900);points.NickName="Fluid probes / seeds";points.SetPersistentData(new Point3d(2,3,5),new Point3d(2,8,5),new Point3d(3,7,7));points.Hidden=true;
 if(number==31){
  var tunnel=C("WindTunnel",300,150);tunnel.Params.Input[0].AddSource(mesh);Num(tunnel,2,1);Num(tunnel,3,2);((Param_Boolean)tunnel.Params.Input[4]).PersistentData.Clear();((Param_Boolean)tunnel.Params.Input[4]).SetPersistentData(false);tunnel.Hidden=true;
  W(tunnel,2,physics,0);W(tunnel,0,spec,0);var geo=C("Geometry",600,200);W(tunnel,0,geo,0);geo.Params.Input[1].AddSource(mesh);W(geo,0,spec,1);
  var bounds=C("DomainPreview",600,500);W(tunnel,0,bounds,0);
  var runtime=C("Runtime",0,700);Toggle("Initialize runtime",runtime,0,0,1000);var info=Add(new GH_Panel(),300,800);info.AddSource(runtime.Params.Output[0]);
  var solve=C("Solve",1200,200);W(spec,0,solve,0);Text(solve,1,"cpu");Int(solve,2,60);Toggle("Run",solve,3,900,550);
  var sample=C("Sample",1500,500);W(solve,0,sample,0);sample.Params.Input[1].AddSource(points);
  var vectors=C("Vectors",1800,500);vectors.Params.Input[0].AddSource(points);W(sample,0,vectors,1);Num(vectors,2,2);
  var values=Add(new GH_Panel(),2100,550);values.NickName="Pressure [Pa]";values.AddSource(sample.Params.Output[1]);
  var checkpoint=C("Checkpoint",1500,800);W(solve,0,checkpoint,0);var output=Add(new GH_Panel(),1200,1100);output.NickName="Checkpoint path";output.UserText="Choose an absolute path ending in .npz";checkpoint.Params.Input[1].AddSource(output);Toggle("Execute file action",checkpoint,3,1200,1250);var status=Add(new GH_Panel(),1800,850);status.AddSource(checkpoint.Params.Output[0]);
  var quality=C("ResultQuality",1500,100);W(solve,0,quality,0);var report=Add(new GH_Panel(),1800,100);report.AddSource(quality.Params.Output[2]);
 }else{
  var box=Add(new Param_Box(),0,0);box.SetPersistentData(new Box(Plane.WorldXY,new Interval(0,11),new Interval(0,11),new Interval(0,11)));box.Hidden=true;var domain=C("Domain",300,0);domain.Params.Input[0].AddSource(box);Num(domain,1,1);Text(domain,2,"meters");domain.Hidden=true;W(domain,0,spec,0);var bounds=C("DomainPreview",600,500);W(domain,0,bounds,0);
  var motion=C("Translation",600,800);((Param_Vector)motion.Params.Input[0]).PersistentData.Clear();((Param_Vector)motion.Params.Input[0]).SetPersistentData(Vector3d.YAxis);Num(motion,1,.05);Num(motion,2,.1);
  var body=C("MovingBody",1200,200);W(spec,0,body,0);body.Params.Input[1].AddSource(mesh);W(motion,0,body,2);((Param_Point)body.Params.Input[3]).SetPersistentData(new Point3d(5.5,5.5,5.5));
  var moving=C("MotionCase",1500,200);W(spec,0,moving,0);W(body,0,moving,1);
  var record=C("Record",1800,200);W(moving,0,record,0);Int(record,2,40);Int(record,3,10);Text(record,4,"cpu");Toggle("Record",record,5,1500,550);Toggle("Pause recording",record,6,1500,650);var directory=Add(new GH_Panel(),1500,850);directory.NickName="Recording directory";directory.UserText="Choose a new absolute recording directory";record.Params.Input[1].AddSource(directory);
  var playback=C("Playback",2100,200);W(record,0,playback,0);var index=Add(new GH_NumberSlider(),1800,800);index.NickName="Frame index";index.Slider.Minimum=0;index.Slider.Maximum=4;index.Slider.DecimalPlaces=0;index.SetSliderValue(4);playback.Params.Input[1].AddSource(index);
  var loads=C("BodyLoads",2400,500);W(playback,0,loads,0);var pose=C("BodyPreview",2700,500);pose.Params.Input[0].AddSource(mesh);W(loads,4,pose,1);mesh.Hidden=true;
  var state=Add(new GH_Panel(),2100,800);state.AddSource(record.Params.Output[1]);
 }
 d.FilePath=path;if(!new GH_DocumentIO{Document=d}.SaveQuiet(path))throw new Exception("Save failed");d.Dispose();Console.WriteLine(path);
}
