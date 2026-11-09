// Run through Rhino MCP after installing the development build. Saves an idle definition.
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd";
var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
var d=new GH_Document();
T Add<T>(T item,float x,float y) where T:IGH_DocumentObject{item.CreateAttributes();item.Attributes.Pivot=new PointF(x,y);d.AddObject(item,false);return item;}
GH_Component C(string name,float x,float y)=>Add((GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper."+name+"Component")),x,y);
void W(GH_Component a,int output,GH_Component b,int input)=>b.Params.Input[input].AddSource(a.Params.Output[output]);
void Text(GH_Component c,int i,string v){var p=(Param_String)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
void Number(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
void Integer(GH_Component c,int i,int v){var p=(Param_Integer)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
GH_Panel Note(string text,float x,float y,int width=440,int height=250){var p=Add(new GH_Panel(),x,y);p.UserText=text;p.Properties.Font=new Font("Helvetica",12);p.Properties.Wrap=true;p.Properties.DrawIndices=false;p.Properties.DrawPaths=false;p.Attributes.Bounds=new RectangleF(x,y,width,height);return p;}
GH_BooleanToggle Toggle(string name,GH_Component c,int input,float x,float y){var t=Add(new GH_BooleanToggle(),x,y);t.NickName=name;t.Value=false;c.Params.Input[input].AddSource(t);return t;}
Note("HAWA / 24 — FLOW TRANSFER\nA coarse parent records a developing block wake. A finer child imports velocity at X=1.2 m. Both use periodic transverse faces.\n\nThis verifies a transfer workflow with demonstration viscosity. It is not an atmospheric or pond model.",0,-360);
Note("1 / RECORD THE PARENT\nSet new absolute paths in both path panels. Enable Record parent and wait for completed.\n\n2 / CAPTURE THE CHILD INLET\nEnable Capture inlet. Wait for its mapped case and report. Existing files are never overwritten.",480,-360);
Note("3 / RUN THE CHILD\nWait for ready, then enable Run child. Parent: 60 steps at dx=0.2 m. Child: 120 steps at dx=0.1 m. Physical duration matches.\n\nRun false pauses Solve. Reset clears it. Capture/Record false cancels. Reopen stays idle.",960,-360);
Note("CHECK / LIMITS\nInspect both Quality reports and fixed colour scales. Boundary Data reuses the saved inlet with a matching case.\n\nImported data has no extrapolation. Solids, missing coverage, backflow and insufficient time are rejected. Use a new file after edits. Parent capture begins at t=0; startup is included.",1440,-360);
var parentBox=Add(new Param_Box(),0,50);parentBox.SetPersistentData(new Box(Plane.WorldXY,new Interval(0,3.2),new Interval(0,1.6),new Interval(0,1.6)));parentBox.Hidden=true;
var pd=C("Domain",300,50);pd.Hidden=true;pd.Params.Input[0].AddSource(parentBox);Number(pd,1,.2);Text(pd,2,"meters");
var childBox=Add(new Param_Box(),0,520);childBox.SetPersistentData(new Box(Plane.WorldXY,new Interval(1.2,2.4),new Interval(.2,1.4),new Interval(.2,1.4)));childBox.Hidden=true;
var cd=C("Domain",300,520);cd.Hidden=true;cd.Params.Input[0].AddSource(childBox);Number(cd,1,.1);Text(cd,2,"meters");
var mesh=Add(new Param_Mesh(),0,260);mesh.SetPersistentData(Mesh.CreateFromBox(new BoundingBox(new Point3d(.6,.6,.6),new Point3d(.8,1,1)),1,1,1));
var geo=C("Geometry",530,100);geo.Hidden=true;W(pd,0,geo,0);geo.Params.Input[1].AddSource(mesh);
var physics=C("Physics",300,310);Number(physics,1,.1);Number(physics,4,.03);
var bc=C("Boundaries",530,400);for(int i=2;i<6;i++)Text(bc,i,"periodic");
var pc=C("Case",780,100);W(pd,0,pc,0);W(geo,0,pc,1);W(physics,0,pc,2);W(bc,0,pc,3);
var cc=C("Case",780,520);W(cd,0,cc,0);W(physics,0,cc,2);W(bc,0,cc,3);
var recorder=C("Record",1080,100);W(pc,0,recorder,0);Integer(recorder,2,60);Integer(recorder,3,5);Text(recorder,4,"mps");
var folder=Note("SET_NEW_ABSOLUTE_PARENT_DIRECTORY",800,280,340,90);recorder.Params.Input[1].AddSource(folder);Toggle("1 Record parent",recorder,5,800,400);
var capture=C("BoundaryCapture",1370,400);W(recorder,0,capture,0);W(cc,0,capture,1);
var file=Note("SET_NEW_ABSOLUTE_BOUNDARY_FILE.npz",1080,620,360,90);capture.Params.Input[2].AddSource(file);Toggle("2 Capture inlet",capture,3,1100,750);
var read=C("BoundaryData",1640,430);W(capture,1,read,0);W(cc,0,read,1);
var solve=C("Solve",1900,450);W(read,0,solve,0);Text(solve,1,"mps");Integer(solve,2,120);Toggle("3 Run child",solve,3,1660,700);Toggle("Reset child",solve,4,1660,780);
var pq=C("ResultQuality",1370,50);W(recorder,2,pq,0);var cq=C("ResultQuality",2160,450);W(solve,0,cq,0);
var pr=Note("",1640,40,480,260);pr.AddSource(pq.Params.Output[2]);var cr=Note("",2430,400,480,260);cr.AddSource(cq.Params.Output[2]);
var parentView=C("Slice",1370,250);parentView.Hidden=true;W(recorder,2,parentView,0);Integer(parentView,1,2);Integer(parentView,2,4);
var childView=C("Slice",2160,750);W(solve,0,childView,0);Integer(childView,1,2);Integer(childView,2,6);
var pb=C("DomainPreview",530,700);W(pd,0,pb,0);var cb=C("DomainPreview",780,750);W(cd,0,cb,0);
foreach(var row in new[]{(new[]{pd,geo,physics,bc,pc,recorder},"01 / Parent recording"),(new[]{cd,cc,capture,read},"02 / Boundary mapping"),(new[]{solve,cq,childView},"03 / Child simulation")}){var g=new GH_Group();g.CreateAttributes();g.NickName=row.Item2;g.Colour=Color.FromArgb(60,50,170,155);d.AddObject(g,false);foreach(var c in row.Item1)g.AddObject(c.InstanceGuid);}
d.FilePath=root+"/examples/grasshopper/24-boundary-flow-transfer.gh";if(!new GH_DocumentIO{Document=d}.SaveQuiet(d.FilePath))throw new Exception("Save failed");Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;d.NewSolution(false);Console.WriteLine(d.FilePath+" ID="+d.DocumentID);
