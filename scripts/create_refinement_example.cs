using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd/examples/grasshopper";
var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");var d=new GH_Document();
T Add<T>(T item,float x,float y) where T:IGH_DocumentObject{item.CreateAttributes();item.Attributes.Pivot=new PointF(x,y);d.AddObject(item,false);return item;}
GH_Component C(string name,float x,float y)=>Add((GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper."+name+"Component")),x,y);
void W(GH_Component a,int output,GH_Component b,int input)=>b.Params.Input[input].AddSource(a.Params.Output[output]);
void Text(GH_Component c,int i,string v){var p=(Param_String)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
void Number(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
var note=Add(new GH_Panel(),0,-220);note.UserText="HAWA / EXPERIMENTAL FIXED REFINEMENT\nOne 2:1 patch around a sphere. Both grids solve the same physical case with BGK.\nRun starts a fresh simulation. Pause holds at a coarse step boundary. Set Run false to cancel.\nThe coarse display masks the covered interior. Two field planes show the two resolutions.\nKeep the patch interface at least two coarse cells from geometry. Compare uniform fine grids before using forces.\nThis example tests coupling. It does not establish engineering accuracy.";note.Attributes.Bounds=new RectangleF(0,-220,1400,180);
var box=Add(new Param_Box(),0,20);box.SetPersistentData(new Box(Plane.WorldXY,new Interval(0,16),new Interval(0,16),new Interval(0,16)));box.Hidden=true;
var domain=C("Domain",300,50);domain.Hidden=true;domain.Params.Input[0].AddSource(box);Text(domain,2,"meters");
var roi=Add(new Param_Box(),0,220);roi.SetPersistentData(new Box(Plane.WorldXY,new Interval(4,12),new Interval(4,12),new Interval(4,12)));roi.Hidden=true;
var patch=C("RefinementDomain",600,200);W(domain,0,patch,0);patch.Params.Input[1].AddSource(roi);patch.Hidden=true;
var mesh=Add(new Param_Mesh(),0,450);mesh.SetPersistentData(Mesh.CreateFromSphere(new Sphere(new Point3d(8,8,8),1),24,16));
var cg=C("Geometry",600,30);cg.Hidden=true;W(domain,0,cg,0);cg.Params.Input[1].AddSource(mesh);
var fg=C("Geometry",850,230);fg.Hidden=true;W(patch,0,fg,0);fg.Params.Input[1].AddSource(mesh);
var physics=C("Physics",600,500);Number(physics,1,1);Text(physics,3,"bgk");
var coarse=C("Case",1100,30);W(domain,0,coarse,0);W(cg,0,coarse,1);W(physics,0,coarse,2);
var fine=C("Case",1100,240);W(patch,0,fine,0);W(fg,0,fine,1);W(physics,0,fine,2);
var solve=C("RefinedSolve",1450,180);W(coarse,0,solve,0);W(fine,0,solve,1);
var run=Add(new GH_BooleanToggle(),1150,470);run.NickName="Run / Cancel";solve.Params.Input[4].AddSource(run);var pause=Add(new GH_BooleanToggle(),1150,530);pause.NickName="Pause";solve.Params.Input[5].AddSource(pause);
var bounds=C("DomainPreview",850,650);W(domain,0,bounds,0);var fineBounds=C("DomainPreview",1100,650);W(patch,0,fineBounds,0);
var colors=C("ColorMap",1450,500);Number(colors,2,1.6);
var rect=Add(new Param_Rectangle(),1450,700);rect.SetPersistentData(new Rectangle3d(new Plane(new Point3d(0,0,8),Vector3d.ZAxis),new Interval(0,16),new Interval(0,16)));rect.Hidden=true;
var detail=Add(new Param_Rectangle(),1700,700);detail.SetPersistentData(new Rectangle3d(new Plane(new Point3d(4,4,8),Vector3d.ZAxis),new Interval(0,8),new Interval(0,8)));detail.Hidden=true;
var cp=C("PlaneField",1850,80);W(solve,0,cp,0);cp.Params.Input[1].AddSource(rect);W(colors,0,cp,4);
var fp=C("PlaneField",1850,330);W(solve,1,fp,0);fp.Params.Input[1].AddSource(detail);W(colors,0,fp,4);
var report=Add(new GH_Panel(),2150,180);report.AddSource(solve.Params.Output[3]);report.Attributes.Bounds=new RectangleF(2150,180,550,220);
d.FilePath=root+"/15-fixed-refinement.gh";new GH_DocumentIO{Document=d}.SaveQuiet(d.FilePath);Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;d.NewSolution(false);Console.WriteLine(d.FilePath);
