// Rhino MCP. Creates new idle examples 25–27, never rewrites existing files.
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd";
var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
foreach(int example in new[]{25,26,27}){
 var name=example==25?"25-channel-boundaries":example==26?"26-bidirectional-open-faces":"27-cropped-solid-boundary";
 var path=root+"/examples/grasshopper/"+name+".gh";if(System.IO.File.Exists(path))throw new Exception("Preserve existing example: "+path);
 var d=new GH_Document();
 T Add<T>(T item,float x,float y) where T:IGH_DocumentObject{item.CreateAttributes();item.Attributes.Pivot=new PointF(x,y);d.AddObject(item,false);return item;}
 GH_Component C(string type,float x,float y)=>Add((GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper."+type+"Component")),x,y);
 void W(GH_Component a,int o,GH_Component b,int i)=>b.Params.Input[i].AddSource(a.Params.Output[o]);
 void Text(GH_Component c,int i,string v){var p=(Param_String)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
 void Num(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
 void Int(GH_Component c,int i,int v){var p=(Param_Integer)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
 void Vec(GH_Component c,int i,Vector3d v){var p=(Param_Vector)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
 GH_Panel Note(string text,float x,float y){var p=Add(new GH_Panel(),x,y);p.UserText=text;p.Properties.Font=new Font("Helvetica",12);p.Properties.Wrap=true;p.Properties.DrawIndices=false;p.Properties.DrawPaths=false;p.Attributes.Bounds=new RectangleF(x,y,440,230);return p;}
 Note("HAWA / "+example+" — "+(example==25?"WALLS + PROFILE INFLOW":example==26?"BIDIRECTIONAL OPEN FACES":"CROPPED CLOSED SOLID")+"\n\n"+(example==25?"A parabolic X- velocity profile meets stationary Y walls. X+ uses an approximate open boundary. Z is periodic. Peak speed is 1 m/s.":example==26?"Y- and Y+ are open faces. Each supplies an incoming exterior velocity when local flow reverses. Other faces are periodic. Initial flow points toward Y-.":"A closed box extends beyond X-. Hawa retains the full body and classifies occupied sites inside the domain. Only the remaining fluid face gets inlet velocity."),0,-330);
 Note("OPERATE\nWait for Boundary Set and Solve to become ready. Enable Run. Disable Run to pause; Reset clears the simulation.\n\nEdit the six Patch components, cell size or physics. Invalid edges and solid reconstruction donors produce an error before solving.\n\nAll speeds use domain axes and m/s. Pressure is gauge Pa.",480,-330);
 Note("INSPECT\nView the domain wireframe, fixed blue-green colour scale and Quality report. Read the boundary method and mass accounting in the report.\n\n"+(example==26?"To reverse the demonstration, change Initial velocity on Boundary Set from (0,-0.2,0) to (0,0.2,0). Edit while paused; the changed case starts afresh.":"Change grid spacing and target steps to compare at the same physical time. Finite output alone does not establish accuracy."),960,-330);
 Note("LIMITS\nStationary uniform lattice; complete faces; one opposite flow-face pair. The open sign switch can reflect disturbances.\n\nNo atmospheric LES, rough-wall model, thermal stability or free water surface. Cropped curved-wall stencils and adjacent open faces are rejected.\n\nThis is a workflow demonstration. Analytic benchmark evidence is in docs/general-boundaries.md.",1440,-330);
 var box=Add(new Param_Box(),0,80);box.SetPersistentData(new Box(Plane.WorldXY,new Interval(0,2),new Interval(0,1),new Interval(0,.8)));box.Hidden=true;
 var domain=C("Domain",250,80);domain.Hidden=true;domain.Params.Input[0].AddSource(box);Num(domain,1,.1);Text(domain,2,"meters");
 var physics=C("Physics",250,300);Num(physics,1,.1);Num(physics,4,.03);Text(physics,3,"smagorinsky-v1");
 var baseCase=C("Case",520,100);W(domain,0,baseCase,0);W(physics,0,baseCase,2);
 var set=C("BoundarySet",1100,200);W(baseCase,0,set,0);
 if(example==26)Vec(set,2,new Vector3d(0,-.2,0));
 var patches=new List<GH_Component>();var faces=new[]{"x-","x+","y-","y+","z-","z+"};
 for(int face=0;face<6;face++){
  var patch=C("BoundaryPatch",780,50+face*190);patch.NickName=faces[face];Text(patch,0,faces[face]);string kind="periodic";
  if(example==26){if(face==2||face==3){kind="open";Vec(patch,2,new Vector3d(0,face==2?.2:-.2,0));}}
  else {if(face==0){kind="velocity";Vec(patch,2,Vector3d.XAxis);if(example==25){Text(patch,4,"parabolic");Int(patch,5,1);}}if(face==1)kind="open";if(example==25&&(face==2||face==3))kind="wall";}
  Text(patch,1,kind);W(patch,0,set,1);patches.Add(patch);
 }
 if(example==27){
  var mesh=Add(new Param_Mesh(),0,580);mesh.SetPersistentData(Mesh.CreateFromBox(new BoundingBox(new Point3d(-.3,.3,.3),new Point3d(.6,.6,.6)),1,1,1));
  var geo=C("Geometry",300,600);geo.Hidden=true;W(domain,0,geo,0);geo.Params.Input[1].AddSource(mesh);W(geo,0,baseCase,1);
 }
 var solve=C("Solve",1400,200);W(set,0,solve,0);Text(solve,1,"mps");Int(solve,2,400);
 var run=Add(new GH_BooleanToggle(),1130,500);run.NickName="Run";run.Value=false;solve.Params.Input[3].AddSource(run);
 var reset=Add(new GH_BooleanToggle(),1130,580);reset.NickName="Reset";reset.Value=false;solve.Params.Input[4].AddSource(reset);
 var quality=C("ResultQuality",1700,100);W(solve,0,quality,0);var report=Note("",1960,70);report.AddSource(quality.Params.Output[2]);
 var snap=C("Snapshot",1700,420);W(solve,0,snap,0);
 var colors=C("ColorMap",1400,780);Num(colors,2,example==26?.3:1.2);
 var view=C("PlaneField",1960,500);W(snap,0,view,0);W(colors,0,view,4);((Param_Rectangle)view.Params.Input[1]).SetPersistentData(new Rectangle3d(new Plane(new Point3d(0,0,.4),Vector3d.ZAxis),new Interval(0,2),new Interval(0,1)));
 var legend=C("Legend",1960,850);W(colors,0,legend,0);Num(legend,2,.7);((Param_Plane)legend.Params.Input[1]).PersistentData.Clear();((Param_Plane)legend.Params.Input[1]).SetPersistentData(new Plane(new Point3d(2.2,0,0),Vector3d.ZAxis));
 var preview=C("DomainPreview",520,760);W(domain,0,preview,0);
 foreach(var row in new[]{(new[]{domain,physics,baseCase},"01 / Physical case"),(patches.ToArray(),"02 / Six physical patches"),(new[]{set,solve,quality},"03 / Compile, run and inspect"),(new[]{snap,colors,view,legend,preview},"04 / View one captured field")}){var g=new GH_Group();g.CreateAttributes();g.NickName=row.Item2;g.Colour=Color.FromArgb(55,50,170,155);d.AddObject(g,false);foreach(var c in row.Item1)g.AddObject(c.InstanceGuid);}
 d.FilePath=path;if(!new GH_DocumentIO{Document=d}.SaveQuiet(path))throw new Exception("Save failed");d.Dispose();Console.WriteLine(path);
}
