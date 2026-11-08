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
void Save(string name) {doc.Enabled=true;doc.FilePath=System.IO.Path.Combine(root,name+".gh");var io=new GH_DocumentIO{Document=doc};if(!io.SaveQuiet(doc.FilePath))throw new Exception("Cannot save "+name);doc.Dispose();Console.WriteLine(name+".gh");}
var names=new[]{"tgv3d-bgk","tgv2d-bgk","tgv2d-trt","tgv2d-smagorinsky","tgv3d-smagorinsky","cavity2d-bgk","poiseuille2d-guo"};
for(int k=0;k<names.Length;k++) {
    var name=names[k];doc=new GH_Document();
    var title=Panel("HAWA / "+name+"\nEmbedded GPU LBM • editable numerical example\n1 Choose grid + backend.  2 Double-click Run.  3 Inspect Rhino preview.\nRun false pauses. Reset true → false clears state; Run false → true resumes.\nChange Field and Slice index to explore. Save your copy before experimenting.",0,-130,1120,110);
    var choice=Choices("Verification case",names,name,0,80);var size=Slider("Grid sites per axis",16,8,64,0,140);var example=C("Example",280,110);Wire(choice,example,0);Wire(size,example,1);
    var device=Choices("Backend",new[]{"auto","mps","cuda:0","cpu"},"auto",380,60);var steps=Slider("Target iterations",200,25,2000,380,120);var run=Toggle("Run / Pause",380,180);var reset=Toggle("Reset",380,230);var solver=C("Solve",690,140);W(example,0,solver,0);Wire(device,solver,1);Wire(steps,solver,2);Wire(run,solver,3);Wire(reset,solver,4);
    var field=Choices("Display field",new[]{"speed","pressure","density"},"speed",820,60);var index=Slider("Slice index (-1 = middle)",-1,-1,63,820,120);var slice=C("Slice",1100,180);W(solver,0,slice,0);Wire(field,slice,3);Wire(index,slice,2);
    var state=Panel("",820,320,280,70);state.AddSource(solver.Params.Output[1]);var monitor=Panel("",380,350,370,160);monitor.AddSource(solver.Params.Output[3]);
    var range=Panel("",820,420,280,75);range.NickName="Color range (min / max)";range.AddSource(slice.Params.Output[2]);
    var tips=Panel("READ THE RESULT\nBlue = low, red = high. Auto range updates each frame.\nNumerical examples use Lettuce reference units.\nOpening stays idle until Run is toggled.\nCPU works everywhere; MPS is Apple GPU; CUDA is NVIDIA.",0,340,285,165);
    Group("01 / CHOOSE A CASE",Color.FromArgb(60,20,157,172),choice,size,example,tips);
    Group("02 / RUN IN RHINO",Color.FromArgb(60,75,140,220),device,steps,run,reset,solver,monitor);
    Group("03 / EXPLORE THE FIELD",Color.FromArgb(60,160,110,210),field,index,slice,state,range);
    Save($"{k+1:00}-{name}");
}
// Physical 3D obstacle case: all geometry is stored inside the GH definition.
doc=new GH_Document();
Panel("HAWA / WIND AROUND A BLOCK\nAn editable 3D setup: Domain → voxelized Geometry + Physics + Boundaries → Case → Solve → Slice / Streamlines.\nThe block and domain are internalized. No Rhino model or external files are needed. Model units: METERS.\nStart with the supplied viscous demonstration fluid (nu = 0.1 m²/s). This is a setup demonstration, not a validated atmospheric wind model.\nDouble-click Run to start. Change target steps, slice index, or viscosity; false pauses; Reset clears state.",0,-180,1370,130);
var box=Add(new Param_Box(),0,70);box.NickName="Domain (meters)";box.SetPersistentData(new Box(Plane.WorldXY,new Interval(0,16),new Interval(0,8),new Interval(0,8)));
var spacing=Slider("Cell size (model units)",.5m,.25m,1,0,140,false);
box.Hidden=true;
var domain=C("Domain",300,100);domain.Hidden=true;Wire(box,domain,0);Wire(spacing,domain,1);
var units=Choices("Length units",new[]{"model","meters","millimeters"},"meters",0,200);Wire(units,domain,2);
var mesh=Add(new Param_Mesh(),0,260);mesh.NickName="Closed block obstacle";mesh.SetPersistentData(Mesh.CreateFromBox(new BoundingBox(4,3,0,6,5,4),1,1,1));
var geometry=C("Geometry",460,190);W(domain,0,geometry,0);Wire(mesh,geometry,1);
var viscosity=Slider("Viscosity (m²/s)",.1m,.01m,.5m,0,350,false);var physics=C("Physics",310,370);Wire(viscosity,physics,1);
var bc=C("Boundaries",460,440);var ca=C("Case",650,240);W(domain,0,ca,0);W(geometry,0,ca,1);W(physics,0,ca,2);W(bc,0,ca,3);
var backend=Choices("Backend",new[]{"auto","mps","cuda:0","cpu"},"auto",720,80);var target=Slider("Target iterations",300,25,2000,720,140);var play=Toggle("Run / Pause",720,210);var clear=Toggle("Reset",720,270);var so=C("Solve",1010,210);W(ca,0,so,0);Wire(backend,so,1);Wire(target,so,2);Wire(play,so,3);Wire(clear,so,4);
var sl=C("Slice",1330,110);W(so,0,sl,0);var ix=Slider("Horizontal slice index",4,0,16,1090,30);Wire(ix,sl,2);
var seeds=Add(new Param_Point(),1100,350);seeds.Hidden=true;seeds.NickName="Streamline seeds (edit points)";foreach(var y in new[]{1d,2d,3d,4d,5d,6d,7d})seeds.SetPersistentData(new Point3d(1,y,2));
var lines=C("Streamlines",1340,300);W(so,0,lines,0);Wire(seeds,lines,1);
var report=Panel("",720,410,330,150);report.AddSource(so.Params.Output[3]);var legend=Panel("",1120,440,235,70);legend.NickName="Speed color range (m/s)";legend.AddSource(sl.Params.Output[2]);
Group("01 / DOMAIN + OBSTACLE",Color.FromArgb(60,20,157,172),box,spacing,units,domain,mesh,geometry);
Group("02 / PHYSICS + CASE",Color.FromArgb(60,100,175,110),viscosity,physics,bc,ca);
Group("03 / RUN ON GPU OR CPU",Color.FromArgb(60,75,140,220),backend,target,play,clear,so,report);
Group("04 / RESULTS IN RHINO",Color.FromArgb(60,160,110,210),sl,ix,seeds,lines,legend);
Save("08-wind-around-block");
