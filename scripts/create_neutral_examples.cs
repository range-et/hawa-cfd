// Rhino MCP; creates new research examples without overwriting prior definitions.
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd";
var asm=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
foreach(int number in new[]{28,29}){
 string name=number==28?"28-neutral-rough-floor":"29-neutral-roughness-sensitivity";
 string path=root+"/examples/grasshopper/"+name+".gh";
 if(System.IO.File.Exists(path))throw new Exception("Preserve existing example "+path);
 var d=new GH_Document();
 T Add<T>(T x,float a,float b) where T:IGH_DocumentObject{x.CreateAttributes();x.Attributes.Pivot=new PointF(a,b);d.AddObject(x,false);return x;}
 GH_Component C(string name,float x,float y)=>Add((GH_Component)Activator.CreateInstance(asm.GetType("Hawa.Grasshopper."+name+"Component")),x,y);
 void W(GH_Component a,int o,GH_Component b,int i)=>b.Params.Input[i].AddSource(a.Params.Output[o]);
 void Num(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
 void Text(GH_Component c,int i,string v){var p=(Param_String)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
 GH_Panel Note(string title,string text,float x,float y){var p=Add(new GH_Panel(),x,y);p.NickName=title;p.UserText=title+"\n\n"+text;p.Properties.Font=new Font("Helvetica",12);p.Properties.Wrap=true;p.Properties.DrawIndices=false;p.Properties.DrawPaths=false;p.Attributes.Bounds=new RectangleF(x,y,410,260);return p;}
 Note("HAWA / "+number+" / NEUTRAL RESEARCH","Experimental high-Re precursor. Air viscosity stays at 1.5e-5 m2/s. The new engine stores population deviations and uses a planar rough-floor stress operator.\n\nThis is NOT a validated atmospheric or city-to-pond result. Boundary transfer is disabled.",0,-330);
 Note("01 / PREPARE","The box marks lattice sample locations, not the halfway walls. Ground is half a cell below Z-; the free-slip lid is half a cell above Z+. X and Y are periodic.\n\nSpeed is measured at the reference height. Roughness and reference height use metres, not Rhino document units.",440,-330);
 Note("02 / OPERATE","Wait for preparation. Turn Run on; turn it off to pause. Reset clears the case.\n\nChange z0 to compare wall traction and mean profiles. Keep z0 below half a cell. Compare equal physical time. Use CPU or MPS; CUDA is untested.\n\nSaved Run is false.",880,-330);
 Note("03 / VERIFY","Read Quality: numerical health and atmospheric validation are separate. The development profile test failed its 5% drift gate on the finest grid. See docs/neutral-precursor-review.md.\n\nThe small grid and deterministic disturbance do not establish developed turbulence. No buildings, waves, thermal stability or pond currents.",1320,-330);
 var box=Add(new Param_Box(),0,50);box.SetPersistentData(new Box(Plane.WorldXY,new Interval(0,15),new Interval(0,15),new Interval(.5,15.5)));box.Hidden=true;
 var domain=C("Domain",250,50);domain.Hidden=true;domain.Params.Input[0].AddSource(box);Num(domain,1,1);Text(domain,2,"meters");
 var physics=C("Physics",250,300);Num(physics,0,5);Num(physics,1,1.5e-5);Num(physics,4,.05);
 var baseCase=C("Case",520,100);W(domain,0,baseCase,0);W(physics,0,baseCase,2);
 var precursor=C("NeutralPrecursor",800,140);W(baseCase,0,precursor,0);Num(precursor,1,6);Num(precursor,2,number==28?.01:.1);
 ((Param_Boolean)precursor.Params.Input[5]).PersistentData.Clear();((Param_Boolean)precursor.Params.Input[5]).SetPersistentData(true);
 var z0=Add(new GH_NumberSlider(),510,520);z0.NickName="z0 [m]";z0.Slider.Minimum=.001m;z0.Slider.Maximum=.2m;z0.Slider.DecimalPlaces=3;z0.SetSliderValue(number==28?.01m:.1m);precursor.Params.Input[2].AddSource(z0);
 var solve=C("Solve",1100,160);W(precursor,0,solve,0);Text(solve,1,"mps");((Param_Integer)solve.Params.Input[2]).PersistentData.Clear();((Param_Integer)solve.Params.Input[2]).SetPersistentData(400);
 var run=Add(new GH_BooleanToggle(),820,520);run.NickName="Run";run.Value=false;solve.Params.Input[3].AddSource(run);
 var reset=Add(new GH_BooleanToggle(),820,600);reset.NickName="Reset";reset.Value=false;solve.Params.Input[4].AddSource(reset);
 var quality=C("ResultQuality",1390,100);W(solve,0,quality,0);var panel=Note("Quality report","",1700,80);panel.AddSource(quality.Params.Output[2]);
 var snap=C("Snapshot",1390,350);W(solve,0,snap,0);
 var colors=C("ColorMap",1100,700);Num(colors,2,7);
 var view=C("PlaneField",1700,430);W(snap,0,view,0);W(colors,0,view,4);
 var rect=(Param_Rectangle)view.Params.Input[1];rect.PersistentData.Clear();rect.SetPersistentData(new Rectangle3d(new Plane(new Point3d(0,7.5,.5),Vector3d.XAxis,Vector3d.ZAxis),new Interval(0,15),new Interval(0,15)));
 var legend=C("Legend",1700,780);W(colors,0,legend,0);Num(legend,2,5);var plane=(Param_Plane)legend.Params.Input[1];plane.PersistentData.Clear();plane.SetPersistentData(new Plane(new Point3d(17,7.5,.5),Vector3d.XAxis,Vector3d.ZAxis));
 var preview=C("DomainPreview",520,750);W(domain,0,preview,0);
 foreach(var row in new[]{(new[]{domain,physics,baseCase},"01 / Domain + air"),(new[]{precursor,solve,quality},"02 / Research model + worker"),(new[]{snap,colors,view,legend,preview},"03 / Captured field + quality")}){var g=new GH_Group();g.CreateAttributes();g.NickName=row.Item2;g.Colour=Color.FromArgb(55,50,170,155);d.AddObject(g,false);foreach(var c in row.Item1)g.AddObject(c.InstanceGuid);}
 d.FilePath=path;if(!new GH_DocumentIO{Document=d}.SaveQuiet(path))throw new Exception("Save failed");d.Dispose();Console.WriteLine(path);
}
