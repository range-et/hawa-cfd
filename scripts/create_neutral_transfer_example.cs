// Rhino MCP; ordinary GH geometry plus reusable Hawa data/solver components.
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd";
var path=root+"/examples/grasshopper/33-neutral-city-to-pond.gh";
if(System.IO.File.Exists(path))throw new Exception("Preserve existing example");
var asm=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");var d=new GH_Document();
T Add<T>(T x,float a,float b) where T:IGH_DocumentObject{x.CreateAttributes();x.Attributes.Pivot=new PointF(a,b);d.AddObject(x,false);return x;}
GH_Component C(string name,float x,float y)=>Add((GH_Component)Activator.CreateInstance(asm.GetType("Hawa.Grasshopper."+name+"Component")),x,y);
void W(GH_Component a,int o,GH_Component b,int i)=>b.Params.Input[i].AddSource(a.Params.Output[o]);
void N(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
void T(GH_Component c,int i,string v){var p=(Param_String)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
void I(GH_Component c,int i,int v){var p=(Param_Integer)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
GH_Panel Note(string label,string text,float x,float y,int width=470,int height=260){var p=Add(new GH_Panel(),x,y);p.NickName="Hawa guide / "+label;p.UserText=text;p.Properties.Font=new Font("Helvetica",12);p.Properties.Multiline=true;p.Properties.Wrap=true;p.Properties.DrawIndices=false;p.Properties.DrawPaths=false;p.Properties.Colour=Color.FromArgb(226,242,237);p.Attributes.Bounds=new RectangleF(x,y,width,height);return p;}
GH_BooleanToggle Toggle(string label,float x,float y,GH_Component c,int input){var p=Add(new GH_BooleanToggle(),x,y);p.NickName=label;p.Value=false;c.Params.Input[input].AddSource(p);return p;}
GH_Panel PathInput(string label,string value,float x,float y,GH_Component c,int input){var p=Add(new GH_Panel(),x,y);p.NickName=label;p.UserText=value;p.Properties.Wrap=true;p.Attributes.Bounds=new RectangleF(x,y,320,80);c.Params.Input[input].AddSource(p);return p;}
Note("purpose","HAWA / 33\nCity → neighbourhood → pond\n\nThree uniform air grids at 1 m, 0.5 m and 0.25 m. Timed velocity and pressure pass between cases on every open face. Each child starts from the parent field.\n\nThe boxes are ordinary GH geometry. They cross the child boundaries. The pond is a low-roughness ground region; there is no water/free-surface solver.",0,-620);
Note("operation","RUN THE FIVE STAGES\n1. Save a copy; choose new absolute paths in the five white path panels.\n2. Prepare all cases with controls off.\n3. Enable A Record. Wait for completed.\n4. Enable B Capture, then B Record after mapping completes.\n5. Enable C Capture, then C Record.\n\nIf a control opened enabled, switch it off then on. Record Pause is cooperative. Run/Capture false cancels. Existing output files are preserved.",510,-620);
Note("limits","CHECK BEFORE INTERPRETING\nThe defaults are a short transfer demonstration. They do not establish settled wind or turbulent statistics. Read Result Quality and Flow Statistics separately.\n\nFor a study: record a longer parent, discard startup with Capture Start/End, match child duration to that window, increase averaging and compare grid/domain/time sensitivity. Buildings need closed full geometry. Parent fluid must cover every child fluid sample.",1020,-620);
Note("mapping","DATA AND RECOVERY\nTransfer includes velocity, gauge pressure, a starting field, physical time and source hashes. The floor uses each case's local wall model. Boundaries switch direction using the parent data.\n\nChanging a child grid/body needs a new boundary capture. Changing files needs Boundary Data Reload. Never reuse an old recording directory. Errors withhold downstream outputs.\n\nGuide: README.md and docs/agents/rhino-mcp.md",1530,-620);
var bodies=Add(new Param_Box(),0,80);bodies.NickName="Closed buildings / shared full geometry";bodies.SetPersistentData(new Box(Plane.WorldXY,new Interval(3,6),new Interval(7,10),new Interval(-1,4)),new Box(Plane.WorldXY,new Interval(10,12),new Interval(6,9),new Interval(-1,5)));bodies.Hidden=false;
var physics=C("Physics",350,-180);N(physics,0,5);N(physics,1,1.5e-5);N(physics,4,.05);
var names=new[]{"A / city","B / neighbourhood","C / pond"};var dxs=new[]{1d,.5,.25};var origins=new[]{new Point3d(.5,.5,.5),new Point3d(4.25,4.25,.25),new Point3d(8.125,7.125,.125)};var shapes=new[]{new[]{32,24,16},new[]{24,24,16},new[]{24,24,16}};
GH_Component previousRecord=null;
for(int stage=0;stage<3;stage++){
 float y=stage*1500;var original=d.Objects.Select(o=>o.InstanceGuid).ToHashSet();double dx=dxs[stage];var o=origins[stage];var n=shapes[stage];
 Note("stage "+stage,names[stage]+"\nCell width = "+dx+" m\nAir: Uref = 5 m/s, ν = 1.5e-5 m²/s\nClosed buildings are reclassified on this grid. The floor is half a cell below its first sample centre.\n\nStart Capture and Record only after their input data is ready.",0,y+300,300,260);
 var box=Add(new Param_Box(),0,y+160);box.NickName=names[stage]+" / domain centres";box.SetPersistentData(new Box(Plane.WorldXY,new Interval(o.X,o.X+(n[0]-1)*dx),new Interval(o.Y,o.Y+(n[1]-1)*dx),new Interval(o.Z,o.Z+(n[2]-1)*dx)));box.Hidden=true;
 var domain=C("Domain",350,y+160);domain.Hidden=true;domain.Params.Input[0].AddSource(box);N(domain,1,dx);T(domain,2,"meters");
 var geom=C("Geometry",650,y+200);W(domain,0,geom,0);geom.Params.Input[3].AddSource(bodies);
 var setup=C("Case",900,y+160);W(domain,0,setup,0);W(geom,0,setup,1);W(physics,0,setup,2);
 var neutral=C("NeutralPrecursor",1170,y+160);W(setup,0,neutral,0);N(neutral,1,stage==0?6:stage==1?4:2);N(neutral,2,.01);N(neutral,7,.1);((Param_Boolean)neutral.Params.Input[5]).PersistentData.Clear();((Param_Boolean)neutral.Params.Input[5]).SetPersistentData(true);
 string[] faces={"x-","x+","y-","y+","z-","z+"};string[] kinds=stage==0?new[]{"velocity","open","periodic","periodic","wall","slip"}:new[]{"open","open","open","open","wall","open"};
 for(int j=0;j<6;j++){var patch=C("BoundaryPatch",900,y+420+j*140);patch.NickName=faces[j]+" / "+kinds[j];T(patch,0,faces[j]);T(patch,1,kinds[j]);if(stage==0&&j<2){((Param_Vector)patch.Params.Input[2]).PersistentData.Clear();((Param_Vector)patch.Params.Input[2]).SetPersistentData(new Vector3d(j==0?5:0,0,0));T(patch,4,"neutral");}if(kinds[j]=="open")T(patch,6,"pressure");W(patch,0,neutral,8);}
 GH_Component prepared=neutral;
 if(stage==2){var material=C("WallRoughness",1430,y+180);W(neutral,0,material,0);((Param_Rectangle)material.Params.Input[1]).SetPersistentData(new Rectangle3d(Plane.WorldXY,new Interval(10,14),new Interval(9,13)));N(material,2,.0002);prepared=material;}
 var record=C("Record",2350,y+170);record.NickName=names[stage]+" / record";I(record,2,512*(1<<stage));I(record,3,8*(1<<stage));T(record,4,"cpu");
 PathInput(names[stage]+" / NEW directory","/choose/a/new/"+(stage==0?"city":stage==1?"neighbourhood":"pond")+"-recording",1940,y+400,record,1);
 Toggle(names[stage]+" / Record",2030,y+590,record,5);Toggle(names[stage]+" / Pause",2030,y+680,record,6);
 if(stage>0){var capture=C("BoundaryCapture",1700,y+180);W(previousRecord,0,capture,0);W(prepared,0,capture,1);PathInput(names[stage]+" / NEW boundary file","/choose/a/new/"+(stage==1?"neighbourhood":"pond")+"-boundary.npz",1330,y+440,capture,2);Toggle(names[stage]+" / Capture",1400,y+650,capture,3);var attach=C("BoundaryData",2020,y+150);W(capture,1,attach,0);W(prepared,0,attach,1);W(attach,0,record,0);}else W(prepared,0,record,0);
 var playback=C("Playback",2630,y+180);W(record,0,playback,0);I(playback,1,64);
 var quality=C("ResultQuality",2630,y+480);W(record,2,quality,0);var qp=Add(new GH_Panel(),2920,y+420);qp.NickName=names[stage]+" / numerical quality";qp.Attributes.Bounds=new RectangleF(2920,y+420,340,160);qp.AddSource(quality.Params.Output[2]);
 var stats=C("FlowStatistics",3250,y+170);W(record,0,stats,0);W(playback,0,stats,1);((Param_Point)stats.Params.Input[2]).SetPersistentData(new Point3d(stage==2?13:stage==1?14:20,stage==2?11:14,stage==2?1.5:2.5));var sp=Add(new GH_Panel(),3560,y+160);sp.NickName=names[stage]+" / sampling quality";sp.Attributes.Bounds=new RectangleF(3560,y+160,370,250);sp.AddSource(stats.Params.Output[3]);
 var color=C("ColorMap",2620,y+800);N(color,2,8);var plane=C("PlaneField",2930,y+200);W(playback,0,plane,0);W(color,0,plane,4);((Param_Rectangle)plane.Params.Input[1]).SetPersistentData(new Rectangle3d(new Plane(new Point3d(o.X,o.Y,stage==2?1.5:2.5),Vector3d.XAxis,Vector3d.YAxis),new Interval(0,(n[0]-1)*dx),new Interval(0,(n[1]-1)*dx)));
 var preview=C("DomainPreview",650,y+500);W(domain,0,preview,0);
 var group=Add(new GH_Group(),0,y);group.NickName=names[stage];group.Colour=Color.FromArgb(45,47,173,151);foreach(var obj in d.Objects.Where(z=>!original.Contains(z.InstanceGuid)&&z!=group))group.AddObject(obj.InstanceGuid);
 previousRecord=record;
}
d.FilePath=path;if(!new GH_DocumentIO{Document=d}.SaveQuiet(path))throw new Exception("Save failed");d.Dispose();Console.WriteLine(path);
