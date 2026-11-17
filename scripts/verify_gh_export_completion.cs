// Execute once through Rhino MCP after foreground Runtime initialization.
// Operates unique copies of examples 31 and 17 sequentially; never saves sources.
// Adjust root only. Poll the printed rhino.json; no waits on the GH solution thread.
using System.IO;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Types;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-issue-35-complete";
var output=Path.Combine(root,"results","gh-export-host",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(output);
var assembly=AppDomain.CurrentDomain.GetAssemblies().Single(a=>a.GetName().Name=="Hawa.Grasshopper");
var runtime=assembly.GetType("Hawa.Grasshopper.EmbeddedRuntime");
if(!(bool)runtime.GetProperty("IsReady").GetValue(null))throw new Exception("Initialize Hawa Runtime on the foreground host thread first.");
JsonObject Call(JsonObject request)=>(JsonObject)runtime.GetMethod("Call").Invoke(null,new object[]{request});
var hub=AppDomain.CurrentDomain.GetAssemblies().Single(a=>a.GetName().Name=="Hawa.Shared").GetType("Hawa.Shared.CaseHub");
int Cleanup()=>(int)hub.GetProperty("PendingCleanupCount").GetValue(null);
int Refreshes()=>(int)assembly.GetType("Hawa.Grasshopper.HawaPollScheduler").GetProperty("PendingCount").GetValue(null);
if(Cleanup()!=0||Refreshes()!=0)throw new Exception("Finish pre-existing host work before this isolated check.");
var sources=new[]{Path.Combine(root,"examples/grasshopper/31-tunnel-probes-checkpoint.gh"),Path.Combine(root,"examples/grasshopper/17-oscillating-cylinder.gh")};
string Hash(string path)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
var sourceHashes=sources.ToDictionary(p=>p,p=>Hash(p));
var previous=Grasshopper.Instances.ActiveCanvas.Document;
GH_Document owned=null;GH_Component solve=null,checkpoint=null;
Dictionary<Guid,string> originalWires=null;HashSet<Guid> originalIds=null;
JsonObject source=null;Point3d[] probes=null;int example=31,phase=0;
var checks=new JsonArray();var artifacts=new JsonObject();
var report=new JsonObject{["state"]="running",["backend"]="cpu",["assembly"]=assembly.Location,["assembly_sha256"]=Hash(assembly.Location),["rhino"]=Rhino.RhinoApp.Version.ToString(),["preserved_gh"]=previous?.DocumentID.ToString(),["output"]=output};
DateTime began=DateTime.UtcNow;
var timer=new Eto.Forms.UITimer{Interval=.1};string timerKey="Hawa.GHExportAcceptance."+Guid.NewGuid().ToString("N");AppDomain.CurrentDomain.SetData(timerKey,timer);
void Check(bool good,string message){if(!good)throw new Exception(message);}
void Save(string state){report["state"]=state;report["phase"]=phase;report["example"]=example;report["checks"]=JsonNode.Parse(checks.ToJsonString());report["artifacts"]=JsonNode.Parse(artifacts.ToJsonString());File.WriteAllText(Path.Combine(output,"rhino.json"),report.ToJsonString(new System.Text.Json.JsonSerializerOptions{WriteIndented=true}));}
void Pass(string text){checks.Add(text);phase++;began=DateTime.UtcNow;Save("running");}
void Stop(){timer.Stop();timer.Dispose();AppDomain.CurrentDomain.SetData(timerKey,null);}
string Wires(GH_Component c)=>string.Join(";",c.Params.Input.SelectMany((p,i)=>p.Sources.Select(s=>i+":"+s.InstanceGuid.ToString())));
void VerifyPreserved(){Check(originalIds.IsSubsetOf(owned.Objects.Select(o=>o.InstanceGuid).ToHashSet()),"Original object identity disappeared");foreach(var c in owned.Objects.OfType<GH_Component>())if(originalWires.TryGetValue(c.InstanceGuid,out var wires))Check(Wires(c)==wires,"Original wires changed: "+c.InstanceGuid);foreach(var p in sourceHashes)Check(Hash(p.Key)==p.Value,"Source archive changed: "+p.Key);}
void DisposeOwned(){if(owned==null)return;VerifyPreserved();if(Grasshopper.Instances.ActiveCanvas.Document==owned)Grasshopper.Instances.ActiveCanvas.Document=previous;Grasshopper.Instances.DocumentServer.RemoveDocument(owned);owned.Dispose();owned=null;}
void Solution(){Check(owned!=null&&Grasshopper.Instances.ActiveCanvas.Document==owned,"Owned canvas is no longer active; preserving user selection");owned.NewSolution(false);}
void Bool(GH_Component c,int index,bool value){var p=c.Params.Input[index];if(p.Sources.Count==0){var q=(Param_Boolean)p;q.PersistentData.Clear();q.SetPersistentData(value);}else{Check(p.Sources.Count==1&&p.Sources[0] is GH_BooleanToggle,"Expected a single Boolean control");var toggle=(GH_BooleanToggle)p.Sources[0];toggle.Value=value;toggle.ExpireSolution(false);}p.ExpireSolution(false);c.ExpireSolution(false);}
void Text(GH_Component c,int index,string value){var p=c.Params.Input[index];if(p.Sources.Count==0){var q=(Param_String)p;q.PersistentData.Clear();q.SetPersistentData(value);}else if(p.Sources.Count==1&&p.Sources[0] is GH_Panel panel){panel.UserText=value;panel.ExpireSolution(false);}else if(p.Sources.Count==1&&p.Sources[0] is GH_ValueList choices){bool found=false;foreach(var item in choices.ListItems){item.Selected=item.Expression.Trim('"')==value;found|=item.Selected;}Check(found,"Missing value-list choice "+value);choices.ExpireSolution(false);}else throw new Exception("Unsupported text control; refusing to remove wires");p.ExpireSolution(false);c.ExpireSolution(false);}
void Steps(int count){var p=solve.Params.Input[2];if(p.Sources.Count==0){var q=(Param_Integer)p;q.PersistentData.Clear();q.SetPersistentData(count);}else{Check(p.Sources.Count==1&&p.Sources[0] is GH_NumberSlider,"Expected one step slider");var slider=(GH_NumberSlider)p.Sources[0];slider.Slider.Minimum=Math.Min(slider.Slider.Minimum,count);slider.SetSliderValue(count);slider.ExpireSolution(false);}p.ExpireSolution(false);solve.ExpireSolution(false);}
void Points(Point3d[] values){var p=(Param_Point)checkpoint.Params.Input[4];Check(p.Sources.Count==0,"Do not replace probe wires");p.PersistentData.Clear();foreach(var value in values)p.PersistentData.Append(new GH_Point(value));p.ExpireSolution(false);checkpoint.ExpireSolution(false);}
JsonObject Output(GH_Component c,int index){var values=c.Params.Output[index].VolatileData.AllData(true).Where(v=>v!=null).ToArray();if(values.Length==0)return null;Check(values.Length==1,"Unexpected output count");string text="";Check(values[0].CastTo(out text),"Output is not JSON");return JsonNode.Parse(text).AsObject();}
string Errors(GH_Component c)=>string.Join("; ",c.RuntimeMessages(GH_RuntimeMessageLevel.Error));
string PathFor(string name)=>Path.Combine(output,example+"-"+name);
void Action(string name,string op){Bool(checkpoint,3,false);Text(checkpoint,1,PathFor(name));Text(checkpoint,2,op);Solution();Bool(checkpoint,3,true);Solution();}
JsonObject Finished(string name,string table=null){Check(Errors(checkpoint)=="",Errors(checkpoint));var result=Output(checkpoint,0);if(result==null)return null;Check(result["path"].GetValue<string>()==PathFor(name)&&File.Exists(PathFor(name)),"Wrong or missing export destination");if(table!=null){Check(result["table"].GetValue<string>()==table&&result["session"].GetValue<string>()==source["session"].GetValue<string>(),"Export attribution does not match completed source");Check(result["iteration"].GetValue<int>()==(example==31?2:6),"Unexpected capture iteration");}artifacts[example+"-"+name]=JsonNode.Parse(result.ToJsonString());return result;}
void Open(int number){example=number;var sourcePath=sources[number==31?0:1];var copy=PathFor("source.gh");File.Copy(sourcePath,copy,false);var io=new GH_DocumentIO();Check(io.Open(copy),"Cannot open owned copy");owned=io.Document;originalIds=owned.Objects.Select(o=>o.InstanceGuid).ToHashSet();originalWires=owned.Objects.OfType<GH_Component>().ToDictionary(c=>c.InstanceGuid,c=>Wires(c));foreach(var toggle in owned.Objects.OfType<GH_BooleanToggle>()){toggle.Value=false;toggle.ExpireSolution(false);}solve=owned.Objects.OfType<GH_Component>().Single(c=>c.ComponentGuid==new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077109"));checkpoint=owned.Objects.OfType<GH_Component>().SingleOrDefault(c=>c.ComponentGuid==new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077110"));if(checkpoint==null){Check(number==17,"Example 31 lost its Checkpoint");checkpoint=(GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper.CheckpointComponent"));checkpoint.CreateAttributes();owned.AddObject(checkpoint,false);checkpoint.Params.Input[0].AddSource(solve.Params.Output[0]);}Check(checkpoint.Params.Input.Count==5&&checkpoint.Params.Input[4].Optional,"Old archive did not acquire optional probe port");Text(solve,1,"cpu");Steps(number==31?2:6);Bool(solve,3,false);Bool(checkpoint,3,false);Text(checkpoint,1,PathFor("initial.npz"));Grasshopper.Instances.DocumentServer.AddDocument(owned);Grasshopper.Instances.ActiveCanvas.Document=owned;Solution();artifacts[number+"-archive"]=new JsonObject{["source"]=sourcePath,["source_sha256"]=sourceHashes[sourcePath],["copy"]=copy,["document"]=owned.DocumentID.ToString(),["solve"]=solve.InstanceGuid.ToString(),["checkpoint"]=checkpoint.InstanceGuid.ToString(),["original_objects"]=originalIds.Count};VerifyPreserved();}
bool Completed(){Check(Errors(solve)=="",Errors(solve));var value=Output(solve,0);if(value==null)return false;var status=Call(new JsonObject{["op"]="status",["session"]=value["session"].DeepClone()});if(status["state"].GetValue<string>()!="completed")return false;Check(status["steps"].GetValue<int>()==(example==31?2:6),"Wrong solve steps");source=value;File.WriteAllText(PathFor("source.json"),new JsonObject{["solution"]=JsonNode.Parse(value.ToJsonString()),["status"]=status}.ToJsonString());return true;}
Point3d World(double x,double y,double z){var c=source["case"];var origin=c["origin"].AsArray().Select(n=>n.GetValue<double>()).ToArray();double spacing=c["spacing"].GetValue<double>();double[] index={x,y,z};var result=(double[])origin.Clone();for(int a=0;a<3;a++)for(int b=0;b<3;b++)result[b]+=index[a]*(c["basis"]?[a]?[b]?.GetValue<double>()??(a==b?1d:0d))*spacing;return new Point3d(result[0],result[1],result[2]);}
Save("running");
timer.Elapsed+=(_,_)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>120)throw new Exception("Timed out at phase "+phase+"; "+(checkpoint==null?"":Errors(checkpoint)));
 switch(phase){
 case 0:Open(31);Pass("31 owned copy opened idle; IDs and original wires preserved");break;
 case 1:Bool(solve,3,true);Solution();Pass("31 CPU two-step solve submitted");break;
 case 2:if(!Completed())return;probes=new[]{World(2,2,2),World(-1000,-1000,-1000),World(2,2,2)};Points(probes);Action("fields.csv","export csv");Pass("31 completed source frozen; field CSV submitted");break;
 case 3:if(Finished("fields.csv","fields")==null)return;Text(checkpoint,1,PathFor("probes.csv"));Text(checkpoint,2,"export probes csv");Solution();Check(Output(checkpoint,0)==null&&!File.Exists(PathFor("probes.csv")),"High Execute silently exported changed input or retained stale report");Action("probes.csv","export probes csv");Pass("31 changed operation withheld stale report; probe CSV explicitly rearmed");break;
 case 4:if(Finished("probes.csv","probes")==null)return;Action("reference.npz","export");Pass("31 probe CSV complete; unchanged NPZ action submitted");break;
 case 5:if(Finished("reference.npz")==null)return;File.WriteAllText(PathFor("cancel.csv"),"previous complete destination");Bool(checkpoint,3,false);Points(Enumerable.Repeat(probes[0],10000).ToArray());Text(checkpoint,1,PathFor("cancel.csv"));Text(checkpoint,2,"export probes csv");Solution();Bool(checkpoint,3,true);Solution();report["cancel_submit_state"]=checkpoint.Message;Bool(checkpoint,3,false);Solution();Pass("31 pending export immediately cancelled through Execute false");break;
 case 6:if((DateTime.UtcNow-began).TotalSeconds<2)return;Check(File.ReadAllText(PathFor("cancel.csv"))=="previous complete destination"&&Output(checkpoint,0)==null,"Export published before cancellation or retained report; cancellation-before-publication not established");Points(probes);File.WriteAllText(PathFor("blocked-parent"),"unchanged blocker");Action("blocked-parent/failed.csv","export csv");Pass("31 cancellation preserved prior bytes; deliberate IO failure submitted");break;
 case 7:if(Errors(checkpoint)=="")return;report["expected_io_failure"]=Errors(checkpoint);Check(File.ReadAllText(PathFor("blocked-parent"))=="unchanged blocker"&&!File.Exists(PathFor("blocked-parent/failed.csv")),"Failed export mutated destination");Action("recovery.csv","export csv");Pass("31 IO failure surfaced without publication; recovery rearmed");break;
 case 8:if(Finished("recovery.csv","fields")==null)return;DisposeOwned();Pass("31 recovery complete and owned document disposed");break;
 case 9:if(Cleanup()!=0||Refreshes()!=0||(DateTime.UtcNow-began).TotalSeconds<2)return;Open(17);Pass("17 owned copy opened idle; existing Checkpoint type added without altering original wires");break;
 case 10:Bool(solve,3,true);Solution();Pass("17 CPU six-step solve submitted");break;
 case 11:if(!Completed())return;var raw=Call(new JsonObject{["op"]="body_loads",["session"]=source["session"].DeepClone()});Check(raw["history"].AsArray().Count==6,"Unexpected raw retained load history");File.WriteAllText(PathFor("raw-loads.json"),raw.ToJsonString());Action("loads.csv","export loads csv");Pass("17 raw public load history captured; load CSV submitted");break;
 case 12:if(Finished("loads.csv","loads")==null)return;Action("reference.npz","export");Pass("17 load CSV complete; raw NPZ reference submitted");break;
 case 13:if(Finished("reference.npz")==null)return;DisposeOwned();Pass("17 owned document disposed; source archives unchanged");break;
 case 14:if(Cleanup()!=0||Refreshes()!=0||(DateTime.UtcNow-began).TotalSeconds<2)return;foreach(var item in sourceHashes)Check(Hash(item.Key)==item.Value,"Source archive changed");report["pending_cleanup"]=Cleanup();report["pending_refreshes"]=Refreshes();report["limits"]="CPU public GH workflow only. Root must independently compare CSV with raw NPZ/load JSON and inspect UI. Public cleanup counters are not private worker enumeration; no physics or other-device qualification.";Stop();Save("passed");break;
 }
 }catch(Exception e){report["error"]=e.ToString();Stop();try{DisposeOwned();}catch(Exception cleanup){report["cleanup_error"]=cleanup.ToString();}Save("failed");}};
timer.Start();Console.WriteLine("GH export verification started: "+Path.Combine(output,"rhino.json"));
