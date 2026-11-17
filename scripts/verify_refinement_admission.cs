// Run through Rhino MCP after installing this candidate, using public GH APIs.
// Creates/removes only its own document, returns immediately, polls by UI timer.
// No user geometry, example archive, runtime internals or assembly is modified.
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Types;
var root="/Users/r2d2/Desktop/hawa-domain-30";
var output=root+"/results/refinement-admission-host";
System.IO.Directory.CreateDirectory(output);
var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
var shared=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Shared");
var hub=shared.GetType("Hawa.Shared.CaseHub");
var scheduler=assembly.GetType("Hawa.Grasshopper.HawaPollScheduler");
int Pending()=> (int)scheduler.GetProperty("PendingCount").GetValue(null);
int Cleanup()=> (int)hub.GetProperty("PendingCleanupCount").GetValue(null);
var previous=Grasshopper.Instances.ActiveCanvas.Document;
var doc=new GH_Document();
T Add<T>(T item) where T:IGH_DocumentObject {item.CreateAttributes();doc.AddObject(item,false);return item;}
var solve=Add((GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper.RefinedSolveComponent")));
var coarse=Add(new Param_GenericObject {NickName="Admission parent"});
var fine=Add(new Param_GenericObject {NickName="Admission patch"});
var run=Add(new GH_BooleanToggle {Value=false});var pause=Add(new GH_BooleanToggle {Value=false});
solve.Params.Input[0].AddSource(coarse);solve.Params.Input[1].AddSource(fine);solve.Params.Input[4].AddSource(run);solve.Params.Input[5].AddSource(pause);
((Param_String)solve.Params.Input[3]).SetPersistentData("cpu");
JsonObject Parent()=>JsonNode.Parse("""{"shape":[17,17,17],"dx":1.0,"spacing":1.0,"origin":[0.0,0.0,0.0],"speed":1.0,"viscosity":1.0,"density":1.225,"mach":0.05,"collision":"bgk","solid":[],"boundaries":["inlet","outlet","periodic","periodic","periodic","periodic"]}""")!.AsObject();
JsonObject Patch(){var f=Parent();f["shape"]=new JsonArray(13,13,13);f["dx"]=.5;f["spacing"]=.5;f["origin"]=new JsonArray(5d,5d,5d);f["refinement_lower"]=new JsonArray(5,5,5);f["refinement_upper"]=new JsonArray(11,11,11);return f;}
void Data(Param_GenericObject p,JsonObject value){p.PersistentData.Clear();p.PersistentData.Append(new GH_String(value.ToJsonString()));p.ExpireSolution(false);}
void Steps(int n){var p=(Param_Integer)solve.Params.Input[2];p.PersistentData.Clear();p.SetPersistentData(n);p.ExpireSolution(false);}
void Solve(){run.ExpireSolution(false);pause.ExpireSolution(false);solve.ExpireSolution(false);doc.NewSolution(false);}
string State()=>solve.Params.Output[2].VolatileData.AllData(true).FirstOrDefault()?.ToString()??"";
string Errors()=>string.Join("; ",solve.RuntimeMessages(GH_RuntimeMessageLevel.Error));
void Check(bool condition,string message){if(!condition)throw new Exception(message);}
Data(coarse,Parent());Data(fine,Patch());Steps(2);
Grasshopper.Instances.DocumentServer.AddDocument(doc);Grasshopper.Instances.ActiveCanvas.Document=doc;doc.NewSolution(false);
var checks=new JsonArray();var report=new JsonObject { ["rhino"]=Rhino.RhinoApp.Version.ToString(),["device"]="cpu",["document"]=doc.DocumentID.ToString(),["solve"]=solve.InstanceGuid.ToString(),["parent"]=coarse.InstanceGuid.ToString(),["patch"]=fine.InstanceGuid.ToString(),["assembly"]=assembly.Location,["sha256"]=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.IO.File.ReadAllBytes(assembly.Location))).ToLowerInvariant() };
int phase=0;DateTime began=DateTime.UtcNow;var timer=new Eto.Forms.UITimer{Interval=.1};
void Save(string state){report["state"]=state;report["phase"]=phase;report["checks"]=JsonNode.Parse(checks.ToJsonString());report["component_state"]=State();System.IO.File.WriteAllText(output+"/rhino.json",report.ToJsonString(new System.Text.Json.JsonSerializerOptions{WriteIndented=true}));}
void Pass(string message){checks.Add(message);phase++;began=DateTime.UtcNow;Save("running");}
void DisposeOwned(){if(Grasshopper.Instances.ActiveCanvas.Document==doc)Grasshopper.Instances.ActiveCanvas.Document=previous;Grasshopper.Instances.DocumentServer.RemoveDocument(doc);doc.Dispose();}
timer.Elapsed+=(_,_)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>120)throw new Exception("Timed out at phase "+phase+"; "+Errors());
 switch(phase){
 case 0:
  var bad=Patch();bad["origin"]=new JsonArray(6d,5d,5d);Data(fine,bad);run.Value=true;var watch=System.Diagnostics.Stopwatch.StartNew();Solve();report["invalid_submit_ms"]=watch.Elapsed.TotalMilliseconds;
  Check(Errors().Contains("origin")&&Errors().Contains(solve.InstanceGuid.ToString())&&Errors().Contains(coarse.InstanceGuid.ToString())&&Errors().Contains(fine.InstanceGuid.ToString()),"Invalid patch lacks actionable source/component identity: "+Errors());
  Check(solve.Params.Output.All(p=>p.VolatileDataCount==0),"Invalid patch published output");Pass("misaligned patch rejected synchronously with input and component IDs");break;
 case 1:
  Data(fine,Patch());Steps(10000);pause.Value=true;watch=System.Diagnostics.Stopwatch.StartNew();Solve();report["valid_submit_ms"]=watch.Elapsed.TotalMilliseconds;Pass("valid submission returned to host; pause requested");break;
 case 2:
  Check(Errors()=="",Errors());if(!State().StartsWith("paused:"))return;report["paused_state"]=State();
  bad=Patch();bad["refinement_lower"]=new JsonArray(0,5,5);Data(fine,bad);Solve();Check(Errors().Contains("clearance"),"Replacement was not rejected");Pass("paused run replaced by invalid patch without stale frames");break;
 case 3:
  Check(solve.Params.Output.All(p=>p.VolatileDataCount==0),"Replaced run retained frames");Data(fine,Patch());Steps(2);pause.Value=false;Solve();Pass("valid two-step recovery submitted");break;
 case 4:
  Check(Errors()=="",Errors());if(!State().StartsWith("completed: 2/2"))return;
  for(int i=0;i<2;i++){string json="";Check(solve.Params.Output[i].VolatileData.AllData(true).Single().CastTo(ref json),"Missing frame JSON");var frame=JsonNode.Parse(json);Check(frame["kind"].GetValue<string>()=="Frame","Wrong output kind");report[i==0?"coarse_frame":"fine_frame"]=frame;}
  Pass("valid case recovered and published both completed frame handles");break;
 case 5:
  run.Value=false;Solve();Steps(10000);run.Value=true;Solve();report["cancel_before_state"]=solve.Message;run.Value=false;Solve();Check(solve.Message=="stopped"&&solve.Params.Output.All(p=>p.VolatileDataCount==0),"Immediate cancel retained output");Pass("immediate submit/cancel clears owned output");break;
 case 6:
  run.Value=true;Solve();report["remove_before_state"]=solve.Message;DisposeOwned();Pass("document removed immediately after submission");break;
 case 7:
  if(Pending()!=0||Cleanup()!=0||(DateTime.UtcNow-began).TotalSeconds<2)return;
  report["pending_refreshes"]=Pending();report["pending_cleanup"]=Cleanup();report["limits"]="Public GH lifecycle/cleanup diagnostics only; no private worker enumeration. Headless barriers prove deterministic late-result races. No numerical accuracy claim.";timer.Stop();timer.Dispose();Save("passed");break;
 }
 }catch(Exception e){report["error"]=e.ToString();timer.Stop();timer.Dispose();try{if(Grasshopper.Instances.DocumentServer.Contains(doc)){run.Value=false;Solve();DisposeOwned();}}catch(Exception cleanup){report["cleanup_error"]=cleanup.ToString();}Save("failed");}};
Save("running");timer.Start();Console.WriteLine("Started refinement admission check: "+output+"/rhino.json; document "+doc.DocumentID);
