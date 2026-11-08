// Run inside Rhino 8 after Hawa is installed. Creates native, editable GH files.
using System.Drawing;
using System.Reflection;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;
using Rhino.Geometry;

var root = "/Users/r2d2/Desktop/hawa-cfd/examples/grasshopper";
System.IO.Directory.CreateDirectory(root);
var assembly = AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
GH_Document doc = null;
T Add<T>(T item, float x, float y) where T:IGH_DocumentObject { item.CreateAttributes(); item.Attributes.Pivot=new PointF(x,y); doc.AddObject(item,false); return item; }
GH_Component C(string type,float x,float y) => Add((GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper."+type+"Component")),x,y);
GH_Panel Panel(string text,float x,float y,float w=240,float h=100) {var p=Add(new GH_Panel(),x,y);p.UserText=text;p.Properties.Colour=Color.FromArgb(224,242,240);p.Properties.Font=new Font("Arial",11);p.Properties.Alignment=GH_Panel.Alignment.Left;p.Properties.DrawPaths=false;p.Properties.DrawIndices=false;p.Attributes.Bounds=new RectangleF(x,y,w,h);return p;}
GH_NumberSlider Slider(string name,decimal value,decimal min,decimal max,float x,float y,bool integer=true) {var s=Add(new GH_NumberSlider(),x,y);s.NickName=name;s.Slider.Minimum=min;s.Slider.Maximum=max;s.Slider.DecimalPlaces=integer?0:3;s.SetSliderValue(value);s.Attributes.Bounds=new RectangleF(x,y,210,20);return s;}
GH_BooleanToggle Toggle(string name,float x,float y) {var t=Add(new GH_BooleanToggle(),x,y);t.NickName=name;t.Value=false;return t;}
GH_ValueList Choices(string name,string[] values,string selected,float x,float y) {var v=Add(new GH_ValueList(),x,y);v.NickName=name;v.ListItems.Clear();foreach(var s in values) v.ListItems.Add(new GH_ValueListItem(s,"\""+s+"\""){Selected=s==selected});return v;}
void Wire(IGH_Param from,GH_Component to,int input) {to.Params.Input[input].RemoveAllSources();to.Params.Input[input].AddSource(from);}
void W(GH_Component from,int output,GH_Component to,int input)=>Wire(from.Params.Output[output],to,input);
void Group(string title,Color color,params IGH_DocumentObject[] items) {var g=Add(new GH_Group(),0,0);g.NickName=title;g.Colour=color;foreach(var i in items)g.AddObject(i.InstanceGuid);}
void Save(string name) {doc.Enabled=true;doc.FilePath=System.IO.Path.Combine(root,name+".gh");var io=new GH_DocumentIO{Document=doc};if(!io.SaveQuiet(doc.FilePath))throw new Exception("Cannot save "+name);Console.WriteLine(name+".gh");}
doc=new GH_Document();
Panel("HAWA / RESPONSIVE HULL SEARCH\nA closed canoe hull in single phase flow. Length = 8 m; mesh volume = 6 m³. No waves, free surface, buoyancy or boat motion.\n1 Change the three shape sliders.  2 Enable evaluation.  3 Enable Search. Pause and cancel remain available.\nEach candidate starts fresh and completes the same iteration count. Fitness is mean X momentum exchange / (0.5 rho U² V^(2/3)).\nThe coarse grid and viscous fluid keep this example small. Refine the grid and check duration before comparing engineering designs.",0,-150,1670,110);
var bow=Slider("Bow fullness",.8m,.4m,1.6m,0,60,false);
var stern=Slider("Stern fullness",.8m,.4m,1.6m,0,110,false);
var ratio=Slider("Beam / draft",2,1,3,0,160,false);
var length=Slider("Fixed length (m)",8,6,10,0,230,false);
var volume=Slider("Fixed volume (m³)",6,4,8,0,280,false);
var hull=C("Hull",310,140);Wire(length,hull,0);Wire(volume,hull,1);Wire(bow,hull,2);Wire(stern,hull,3);Wire(ratio,hull,4);((Param_Point)hull.Params.Input[5]).PersistentData.Clear();((Param_Point)hull.Params.Input[5]).SetPersistentData(new Point3d(8,6.1,5.1));
hull.Hidden=true;
var material=Add(new GH_ColourSwatch(),0,330);material.NickName="Hull color";material.SwatchColour=Color.FromArgb(174,202,207);
var preview=Add((GH_Component)Grasshopper.Instances.ComponentServer.EmitObjectProxy(new Guid("537b0419-bbc2-4ff4-bf08-afe526367b2c")).CreateInstance(),310,300);W(hull,0,preview,0);Wire(material,preview,1);
var dimensions=Panel("",0,370,270,150);dimensions.AddSource(hull.Params.Output[3]);
var box=Add(new Param_Box(),400,60);box.NickName="Fixed tank (meters)";box.SetPersistentData(new Box(Plane.WorldXY,new Interval(0,24),new Interval(0,12),new Interval(0,10)));box.Hidden=true;
var spacing=Slider("Cell size (m)",.4m,.25m,1,400,120,false);
var domain=C("Domain",680,90);domain.Hidden=true;Wire(box,domain,0);Wire(spacing,domain,1);((Param_String)domain.Params.Input[2]).PersistentData.Clear();((Param_String)domain.Params.Input[2]).SetPersistentData("meters");
var geometry=C("Geometry",680,240);geometry.Hidden=true;W(domain,0,geometry,0);W(hull,0,geometry,1);
var speed=Slider("Flow speed (m/s)",1,.5m,2,400,360,false);
var nu=Slider("Viscosity (m²/s)",.1m,.05m,.2m,400,410,false);
var physics=C("Physics",680,390);Wire(speed,physics,0);Wire(nu,physics,1);((Param_Number)physics.Params.Input[2]).PersistentData.Clear();((Param_Number)physics.Params.Input[2]).SetPersistentData(1000);
var bc=C("Boundaries",680,520);for(int i=2;i<6;i++){((Param_String)bc.Params.Input[i]).PersistentData.Clear();((Param_String)bc.Params.Input[i]).SetPersistentData("slip");}
var ca=C("Case",900,250);W(domain,0,ca,0);W(geometry,0,ca,1);W(physics,0,ca,2);W(bc,0,ca,3);
var backend=Choices("Backend",new[]{"auto","mps","cuda:0","cpu"},"auto",950,40);
var steps=Slider("Iterations per candidate",200,40,2000,950,100);
var window=Slider("Final averaging window",20,5,100,950,150);
var enable=Toggle("Run search",950,200);var pause=Toggle("Pause",950,240);var cancel=Toggle("Cancel evaluation",950,280);
var ev=C("Evaluate",1250,250);W(ca,0,ev,0);Wire(backend,ev,1);Wire(steps,ev,2);Wire(window,ev,3);Wire(volume,ev,4);Wire(enable,ev,5);Wire(pause,ev,6);Wire(cancel,ev,7);
var score=Panel("",1390,60,270,90);score.NickName="FITNESS / MINIMIZE";score.AddSource(ev.Params.Output[0]);
var report=Panel("",950,430,420,200);report.AddSource(ev.Params.Output[3]);
var slice=C("Slice",1580,260);W(ev,1,slice,0);((Param_Integer)slice.Params.Input[2]).PersistentData.Clear();((Param_Integer)slice.Params.Input[2]).SetPersistentData(8);
var seeds=Add(new Param_Point(),1390,410);seeds.Hidden=true;seeds.NickName="Upstream seeds";foreach(double y in new[]{4d,4.5,5,5.5,6,6.5,7,7.5,8})seeds.SetPersistentData(new Point3d(2,y,4));
var lines=C("Streamlines",1580,410);W(ev,1,lines,0);Wire(seeds,lines,1);
var search=C("Search",310,610);search.Params.Input[0].AddSource(bow);search.Params.Input[0].AddSource(stern);search.Params.Input[0].AddSource(ratio);W(ev,0,search,1);W(ev,4,search,2);Wire(enable,search,3);Wire(pause,search,4);
var budget=Slider("Candidate budget",5,2,20,0,600);Wire(budget,search,5);
var history=Panel("",0,850,1000,180);history.AddSource(search.Params.Output[2]);
var guide=Panel("RESPONSIVE SEARCH\nThe search changes the three sliders only after a completed result.\nPause controls the search and the active evaluation.\nRun false cancels evaluation. Re-enable to start a new search.\nBest fitness and genes remain available after the candidate budget completes.",0,680,650,120);
var bounds=C("DomainPreview",850,700);W(domain,0,bounds,0);
Group("01 / SHAPE GENES + FIXED VOLUME",Color.FromArgb(60,20,157,172),bow,stern,ratio,length,volume,hull,material,preview,dimensions);
Group("02 / FIXED TANK + FLUID",Color.FromArgb(60,100,175,110),box,spacing,domain,geometry,speed,nu,physics,bc,ca);
Group("03 / COMPLETE EACH CANDIDATE",Color.FromArgb(60,75,140,220),backend,steps,window,enable,ev,report);
Group("04 / FITNESS + FLOW",Color.FromArgb(60,160,110,210),score,slice,seeds,lines);
Group("05 / SEARCH THE SHAPE",Color.FromArgb(60,210,100,150),search,guide,budget,history);
Save("10-responsive-hull-search");
Grasshopper.Instances.DocumentServer.AddDocument(doc);Grasshopper.Instances.ActiveCanvas.Document=doc;doc.NewSolution(false);
