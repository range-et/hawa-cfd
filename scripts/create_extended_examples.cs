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
// New visual workflow based on the editable block example.
var io=new GH_DocumentIO();if(!io.Open(System.IO.Path.Combine(root,"08-wind-around-block.gh")))throw new Exception("Block example missing");doc=io.Document;
var solve=doc.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Solve");
var domain=doc.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Domain");domain.Hidden=true;
foreach(var c in doc.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Slice"||c.Name=="Hawa Streamlines").ToArray())doc.RemoveObject(c,false);
foreach(var unused in doc.Objects.Where(o=>o is Param_Point || o.NickName=="Horizontal slice index"||o.NickName=="Speed color range (m/s)").ToArray())doc.RemoveObject(unused,false);
var bounds=C("DomainPreview",1400,50);W(domain,0,bounds,0);
var frame=C("Snapshot",1400,180);W(solve,0,frame,0);
var map=C("ColorMap",1400,450);((Param_Number)map.Params.Input[2]).PersistentData.Clear();((Param_Number)map.Params.Input[2]).PersistentData.Clear();((Param_Number)map.Params.Input[2]).SetPersistentData(1.6);
var region=Add(new Param_Box(),1400,650);region.Hidden=true;region.SetPersistentData(new Box(Plane.WorldXY,new Interval(1,2),new Interval(1,7),new Interval(1,6)));
var seeds=C("Seeds",1700,650);Wire(region,seeds,0);seeds.Hidden=true;
var flow=C("FlowDisplay",2000,400);W(frame,0,flow,0);W(seeds,0,flow,1);W(map,0,flow,2);
var rectangle=Add(new Param_Rectangle(),1700,150);rectangle.Hidden=true;rectangle.SetPersistentData(new Rectangle3d(new Plane(new Point3d(0,0,2),Vector3d.ZAxis),new Interval(0,18),new Interval(0,8)));
var plane=C("PlaneField",2000,160);W(frame,0,plane,0);Wire(rectangle,plane,1);W(map,0,plane,4);((Param_Number)plane.Params.Input[5]).PersistentData.Clear();((Param_Number)plane.Params.Input[5]).SetPersistentData(new[]{.4,.8,1.2});
var iso=C("Isosurface",2000,650);W(frame,0,iso,0);iso.Hidden=true;
Panel("HAWA / 3D FLOW VISUALIZATION\nRun the solver. A shared snapshot supplies the plane, tubes and isosurface.\nChange the Color Map to spectrum or blue-green. Use fixed limits for comparisons.\nEnable Isosurface preview to inspect equal-value surfaces.",1400,-180,900,150);
var legend=C("Legend",2300,430);W(map,0,legend,0);((Param_Plane)legend.Params.Input[1]).PersistentData.Clear();((Param_Plane)legend.Params.Input[1]).SetPersistentData(new Plane(new Point3d(18,1,0),Vector3d.XAxis,Vector3d.YAxis));
Save("11-block-3d-visualization");
// Airfoil generation and wing geometry use only local computation.
doc=new GH_Document();
Panel("HAWA / LOCAL AIRFOIL AND RC WING\nEnter a NACA four-digit code, or load your own local coordinate file.\nWing analysis uses linear lifting-line theory for attached flow. CDi is induced drag only.\nUse a measured zero-lift angle from matching section data. No stall prediction.",0,-180,1200,130);
var code=Panel("data/naca0012.dat",0,0,200,50);var foil=C("Airfoil",300,50);Wire(code,foil,0);foil.Hidden=true;
var span=Slider("Span",2,1,4,0,150,false);var cr=Slider("Root chord",.3m,.1m,.8m,0,200,false);var ct=Slider("Tip chord",.15m,.05m,.6m,0,250,false);var twist=Slider("Tip twist",-2,-8,4,0,300,false);
var wing=C("Wing",650,100);W(foil,1,wing,0);Wire(span,wing,1);Wire(cr,wing,2);Wire(ct,wing,3);Wire(twist,wing,4);
var alpha=Slider("Angle of attack",4,-6,10,0,400,false);var analysis=C("WingAnalysis",650,380);Wire(span,analysis,0);Wire(cr,analysis,1);Wire(ct,analysis,2);Wire(alpha,analysis,3);Wire(twist,analysis,4);
var lift=Panel("",950,100,270,80);lift.NickName="CL";lift.AddSource(analysis.Params.Output[0]);var drag=Panel("",950,220,270,80);drag.NickName="CDi";drag.AddSource(analysis.Params.Output[1]);var scope=Panel("",950,380,300,120);scope.AddSource(analysis.Params.Output[3]);
var polarFile=Panel("data/polar-format.csv",0,530,260,60);var polar=C("Polar",350,600);Wire(polarFile,polar,0);Wire(alpha,polar,3);var polarNote=Panel("SYNTHETIC FORMAT EXAMPLE\nThe sample polar demonstrates the file format only. Replace it with your own measured or computed data. Enter matching Re and Mach. Connect Polar to LLT only after checking these conditions.",650,600,600,130);
var cm=Panel("",950,780,280,60);cm.NickName="Section Cm";cm.AddSource(polar.Params.Output[6]);
Save("12-local-airfoil-rc-wing");
// Recording is disabled on open and requires an explicit new output directory.
doc=new GH_Document();Panel("HAWA / RECORD AND PLAYBACK\nSet a new directory on your computer. Run records timed 3D velocity fields.\nAfter completion connect Manifest to Playback and change the frame index.\nUse Field Snapshot tools to view each frame. Pause stops at a batch boundary.",0,-180,1200,130);
var example=C("Example",300,0);var record=C("Record",700,100);W(example,0,record,0);var directory=Panel("Choose a new recording directory",0,100,250,60);Wire(directory,record,1);var run=Toggle("Record",300,200);Wire(run,record,5);var pause=Toggle("Pause",300,250);Wire(pause,record,6);var report=Panel("",1000,100,300,120);report.AddSource(record.Params.Output[1]);var playback=C("Playback",1000,350);W(record,0,playback,0);var index=Slider("Frame",0,0,20,700,400);Wire(index,playback,1);var iso2=C("Isosurface",1300,350);W(playback,0,iso2,0);Save("13-record-and-playback");
Grasshopper.Instances.DocumentServer.AddDocument(doc);Grasshopper.Instances.ActiveCanvas.Document=doc;doc.NewSolution(false);
