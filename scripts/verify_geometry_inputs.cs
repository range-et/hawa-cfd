// Check absent, unresolved, open and valid solid inputs without blocking GH.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;
using Grasshopper.Kernel.Data;
using Rhino.Geometry;
using System.Text.Json.Nodes;
var asm=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
var d=new GH_Document{Enabled=true};var c=(GH_Component)Activator.CreateInstance(asm.GetType("Hawa.Grasshopper.GeometryComponent"));c.CreateAttributes();d.AddObject(c,false);
var domain=(JsonObject)asm.GetType("Hawa.Grasshopper.DomainComponent").GetMethod("MakeDomain",System.Reflection.BindingFlags.Static|System.Reflection.BindingFlags.NonPublic).Invoke(null,new object[]{new Box(new BoundingBox(new Point3d(-4,-4,-4),new Point3d(4,4,4))),1d,(double?)1d});
var datum=(IGH_Goo)Activator.CreateInstance(asm.GetType("Hawa.Grasshopper.HawaGoo"),domain);((Param_GenericObject)c.Params.Input[0]).PersistentData.Append(datum,new GH_Path(0));
var source=new Param_Brep();source.CreateAttributes();d.AddObject(source,false);c.Params.Input[3].AddSource(source);Grasshopper.Instances.DocumentServer.AddDocument(d);
var report=new JsonObject{["state"]="running"};var checks=new JsonArray();int phase=0;var began=DateTime.UtcNow;var timer=new System.Windows.Forms.Timer{Interval=150};
void Save(string state){report["state"]=state;report["checks"]=checks.DeepClone();System.IO.File.WriteAllText("/Users/r2d2/Desktop/hawa-cfd/results/v05/boundaries/geometry-inputs.json",report.ToJsonString());}
void Set(Brep value){source.PersistentData.Clear();if(value!=null)source.SetPersistentData(new GH_Brep(value));source.ExpireSolution(false);d.NewSolution(false);began=DateTime.UtcNow;}
void Pass(string s){checks.Add(s);phase++;Save("running");}
timer.Tick+=(_,_)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>30)throw new Exception("Timeout "+phase+": "+c.Message);
 var errors=c.RuntimeMessages(GH_RuntimeMessageLevel.Error);
 switch(phase){
 case 0:if(c.Params.Output[0].VolatileData.AllData(true).Any(v=>v!=null&&v.IsValid)||c.Message!="waiting for geometry")throw new Exception("Empty connected solid became an empty-flow case");Pass("Connected empty Brep withholds output");Set(new Sphere(new Point3d(.45,.45,.45),.1).ToBrep());break;
 case 1:if(errors.Count==0)return;if(!errors.Any(s=>s.Contains("no solid cells")))throw new Exception(string.Join(";",errors));Pass("Subcell body is rejected explicitly");Set(new PlaneSurface(Plane.WorldXY,new Interval(0,1),new Interval(0,1)).ToBrep());break;
 case 2:if(!errors.Any(s=>s.Contains("closed solids")))throw new Exception("Open Brep accepted");Pass("Open Brep rejected");Set(new Sphere(new Point3d(.13,.21,.17),.8).ToBrep());break;
 case 3:if(errors.Count>0)throw new Exception(string.Join(";",errors));if(!c.Params.Output[0].VolatileData.AllData(true).Any(v=>v!=null&&v.IsValid))return;Pass("Valid solid prepares successfully after errors");Set(null);break;
 case 4:if(c.Params.Output[0].VolatileData.AllData(true).Any(v=>v!=null&&v.IsValid)||c.Message!="waiting for geometry")throw new Exception("Old solid result survived source becoming empty");Pass("Clearing a connected source withholds stale geometry");timer.Stop();Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();timer.Dispose();Save("completed");break;
 }
}catch(Exception e){timer.Stop();report["error"]=e.GetBaseException().Message;Save("failed");Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();timer.Dispose();}};
d.NewSolution(false);Save("running");timer.Start();

Rhino.RhinoApp.WriteLine("Input checks queued");
