// Nonblocking selected-geometry integration test. Use an isolated empty document.
using System.Text.Json.Nodes;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd";
var hub=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Shared").GetType("Hawa.Shared.CaseHub");
var geometry=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Rhino").GetType("Hawa.Native.NativeGeometry");
object Call(string method,params object[] args)=>hub.GetMethod(method).Invoke(null,args);
uint serial=__rhino_doc__.RuntimeSerialNumber;dynamic c=Call("Get",serial);
void Edit(JsonObject patch)=>Call("Edit",serial,patch,(long)c.Version,"panel",true);
void Select(params Guid[] ids)=>geometry.GetMethod("SelectObjects").Invoke(null,new object[]{serial,ids,true});
if(__rhino_doc__.Objects.Where(o=>!o.IsDeleted).Any())throw new Exception("Use an empty isolated document");
__rhino_doc__.ModelUnitSystem=Rhino.UnitSystem.Meters;
var mesh=Mesh.CreateFromBox(new BoundingBox(Point3d.Origin,new Point3d(1,1,1)),1,1,1);
var first=__rhino_doc__.Objects.AddMesh(mesh);mesh.Dispose();
var brep=new Sphere(new Point3d(2,.5,.5),.4).ToBrep();var second=__rhino_doc__.Objects.AddBrep(brep);brep.Dispose();
Select(first,second);var curvedSetup=(JsonObject)c.Setup;curvedSetup["curved_walls"]=true;Edit(new(){["setup"]=curvedSetup});Edit(new(){["cell"]=.25,["target"]=30,["field"]="pressure"});
var report=new JsonObject{["rhino"]=Rhino.RhinoApp.Version.ToString()};var checks=new JsonArray();int phase=0;string session="",saved="";long revision=0;
var timer=new System.Windows.Forms.Timer{Interval=250};DateTime began=DateTime.UtcNow;
void Check(bool ok,string message){if(!ok)throw new Exception(message);}
void Save(string state){report["state"]=state;report["phase"]=phase;report["checks"]=checks.DeepClone();System.IO.File.WriteAllText(root+"/results/v05/boundaries/native-geometry.json",report.ToJsonString());}
void Pass(string text){checks.Add(text);phase++;began=DateTime.UtcNow;Save("running");}
timer.Tick+=(_,_)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>120)throw new Exception("Timeout at phase "+phase+": "+c.Describe());
 switch(phase){
 case 0:
  var clock=System.Diagnostics.Stopwatch.StartNew();Call("Run",serial);report["geometry_submit_ms"]=clock.Elapsed.TotalMilliseconds;
  Check((string)c.State=="voxelizing","Preparation not asynchronous");Pass("mesh and solid Brep capture returns with background preparation");break;
 case 1:
  if((string)c.State=="failed")throw new Exception((string)c.Error);
  if((string)c.State!="completed"||c.Result==null||(int)c.Result.Steps!=30)return;
  Check((int)c.Spec["solid"].AsArray().Count>0,"No solid cells");Check((int)c.Spec["wall_links"].AsArray().Count>0,"No curved wall links");report["wall_links"]=(int)c.Spec["wall_links"].AsArray().Count;session=(string)c.Session;revision=(long)c.Revision;
  report["cpu"]=c.Describe();var view=(JsonObject)c.View;view["axis"]=0;view["position"]=.4;view["palette"]="spectrum";view["auto_range"]=false;view["min"]=-2d;view["max"]=2d;Edit(new(){["view"]=view});
  Check((string)c.Session==session&&(long)c.Revision==revision,"View restarted physical run");Pass("CPU field completed with selected geometry; display edit retains session");break;
 case 2:
  if(c.Result==null)return;
  var slice=(JsonObject)c.Slice;var xs=slice["coordinates"].AsArray().Select(p=>p[0].GetValue<double>()).Distinct().Count();Check(xs==1,"Wrong slice orientation");
  var setup=(JsonObject)c.Setup;setup["size"][0]=setup["size"][0].GetValue<double>()+1;Edit(new(){["setup"]=setup,["device"]="mps"});
  Check(c.Session==null&&(bool)c.Outdated,"Domain edit retained old run");Call("Run",serial);Pass("slice axis/position and fixed spectrum work; domain edit invalidates run");break;
 case 3:
  if((string)c.State=="failed")throw new Exception((string)c.Error);
  if((string)c.State!="completed"||c.Result==null||(int)c.Result.Steps!=30)return;
  report["mps"]=c.Describe();__rhino_doc__.Objects.Delete(first,true);
  Check(c.Session==null&&(bool)c.Outdated&&(string)c.GeometryError!="","Deletion did not invalidate run");Call("Run",serial);
  Check((string)c.State=="failed"&&((string)c.Error).Contains("missing"),"Missing reference silently accepted");
  Pass("MPS completed; deleting a referenced body invalidates and reports missing geometry");break;
 case 4:
  Select(second);Edit(new(){["device"]="cpu",["target"]=20});Call("Run",serial);
  var replacement=new Sphere(new Point3d(2.1,.5,.5),.4).ToBrep();__rhino_doc__.Objects.Replace(second,replacement);replacement.Dispose();
  Check(c.Session==null&&(string)c.GeometryError!="","Replacement did not invalidate preparation");
  Call("Run",serial);Call("Cancel",serial);Pass("replacement invalidates pending geometry; cooperative cancellation submitted");break;
 case 5:
  Check(c.Session==null&&(string)c.State=="cancelled","Late geometry escaped cancellation");
  Call("Run",serial);Pass("retry after geometry replacement and cancellation");break;
 case 6:
  if((string)c.State=="failed")throw new Exception((string)c.Error);
  if((string)c.State!="completed"||c.Result==null||(int)c.Result.Steps!=20)return;
  saved=(string)Call("Save",serial);string path=root+"/results/v05/boundaries/selected-persistence.3dm";
  Check(__rhino_doc__.WriteFile(path,new Rhino.FileIO.FileWriteOptions{WriteUserData=true,SuppressDialogBoxes=true}),"Save failed");
  using(var reopened=Rhino.RhinoDoc.OpenHeadless(path)){
    dynamic other=Call("Get",reopened.RuntimeSerialNumber);Check((Guid)other.Id==(Guid)c.Id&&(string)other.State=="idle"&&other.Session==null,"Reopen lost settings or auto-ran");
    Check(reopened.Objects.FindId(second)!=null&&((JsonObject)other.Setup)["objects"].AsArray().Count==1,"Reopen lost object reference");Call("Close",reopened.RuntimeSerialNumber);
  }
  Pass("schema 2 and object references survive 3dm reopen without auto-run");break;
 case 7:
  var open=new Mesh();open.Vertices.Add(0,0,0);open.Vertices.Add(1,0,0);open.Vertices.Add(0,1,0);open.Faces.AddFace(0,1,2);var invalid=__rhino_doc__.Objects.AddMesh(open);open.Dispose();
  bool rejected=false;try{Select(invalid);}catch{rejected=true;}Check(rejected&&(string)Call("Save",serial)==saved,"Invalid selection mutated accepted case");__rhino_doc__.Objects.Delete(invalid,true);
  __rhino_doc__.ModelUnitSystem=Rhino.UnitSystem.Millimeters;Call("Tick");
  Check(c.Session==null&&(string)c.GeometryError!="","Unit change silently reinterpreted selected geometry");
  __rhino_doc__.ModelUnitSystem=Rhino.UnitSystem.Meters;Call("Tick");
  Call("Close",serial);__rhino_doc__.Objects.Delete(second,true);
  Check((int)hub.GetProperty("PendingCleanupCount").GetValue(null)==0,"Cleanup requests remain");
  Pass("open mesh rejected atomically; units invalidate geometry; selected case cleanup completed");timer.Stop();timer.Dispose();Save("completed");break;
 }
 }catch(Exception e){timer.Stop();report["error"]=e.ToString();Save("failed");}};
timer.Start();Save("running");Console.WriteLine("Native selected-geometry checks queued");
