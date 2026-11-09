// Maintainer fault injection: real saved workflows, retained teardown, GH-only idle recovery.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using System.Reflection;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";
var output=root+"/results/v05/cleanup-20261108";
System.IO.Directory.CreateDirectory(output);
var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Shared");
var hub=assembly.GetType("Hawa.Shared.CaseHub");var runtime=assembly.GetType("Hawa.Shared.EmbeddedRuntime");
var flags=BindingFlags.Static|BindingFlags.NonPublic;
var transport=hub.GetField("Transport",flags);var original=(Func<JsonObject,JsonObject>)transport.GetValue(null);
int Pending()=> (int)hub.GetProperty("PendingCleanupCount").GetValue(null);
var native=Rhino.PlugIns.PlugIn.Find(new Guid("8a52c518-ad40-459c-8fb4-a745c5db0500"));
var nativeTimer=native?.GetType().GetField("timer",BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(native);
nativeTimer?.GetType().GetMethod("Stop").Invoke(nativeTimer,null);
FieldInfo Field(object c,string name){for(var t=c.GetType();t!=null;t=t.BaseType){var f=t.GetField(name,BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.DeclaredOnly);if(f!=null)return f;}return null;}
var files=new[]{"01-tgv3d-bgk.gh","10-responsive-hull-search.gh","13-record-and-playback.gh","15-fixed-refinement.gh","20-motion-cycle-search.gh"};
var names=new[]{"Hawa Solve","Hawa Evaluate","Hawa Record","Hawa Refined Solve","Hawa Motion Evaluate"};
var reports=new JsonArray();int index=0,phase=0,failed=0,retained=0;bool deny=false;GH_Document doc=null;GH_Component component=null;DateTime began=DateTime.UtcNow,released=began;
var timer=new System.Windows.Forms.Timer{Interval=250};
transport.SetValue(null,new Func<JsonObject,JsonObject>(request=>{if(deny){failed++;throw new Exception("Intentional cleanup transport failure");}return original(request);}));
void Save(string state,string error=null){System.IO.File.WriteAllText(output+"/legacy-cleanup.json",new JsonObject{["state"]=state,["native_timer_disabled"]=true,["pending"]=Pending(),["results"]=reports.DeepClone(),["error"]=error}.ToJsonString());}
void Close(){if(doc==null)return;Grasshopper.Instances.ActiveCanvas.Document=null;Grasshopper.Instances.DocumentServer.RemoveDocument(doc);doc.Dispose();doc=null;}
void Finish(){timer.Stop();deny=false;transport.SetValue(null,original);nativeTimer?.GetType().GetMethod("Start").Invoke(nativeTimer,null);timer.Dispose();}
void Open(){var io=new GH_DocumentIO();if(!io.Open(root+"/examples/grasshopper/"+files[index]))throw new Exception("Open failed");doc=io.Document;doc.Enabled=true;foreach(var t in doc.Objects.OfType<GH_BooleanToggle>())t.Value=false;Grasshopper.Instances.DocumentServer.AddDocument(doc);Grasshopper.Instances.ActiveCanvas.Document=doc;component=doc.Objects.OfType<GH_Component>().First(c=>c.Name==names[index]);if(index==0){var n=(Param_Integer)component.Params.Input[2];n.RemoveAllSources();n.PersistentData.Clear();n.SetPersistentData(100000);}if(index==2){var panel=(GH_Panel)component.Params.Input[1].Sources.Single();panel.UserText=output+"/fault-record-"+Guid.NewGuid().ToString("N");panel.ExpireSolution(false);}phase=0;began=DateTime.UtcNow;doc.NewSolution(false);Save("running");}
timer.Tick+=(sender,e)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>120)throw new Exception("Timeout: "+names[index]+" phase "+phase+" message "+component.Message);
 if(phase==0){if(doc.Objects.OfType<GH_Component>().Any(c=>(c.Name=="Hawa Geometry"||c.Name=="Hawa Moving Body")&&c.Message!="ready"))return;var toggle=doc.Objects.OfType<GH_BooleanToggle>().First(t=>t.NickName!="Pause"&&t.NickName!="Cancel");toggle.Value=true;toggle.ExpireSolution(false);doc.NewSolution(false);phase=1;return;}
 if(phase==1){var owned=Field(component,index==0?"creation":"job")?.GetValue(component) as string;if(owned==null)return;if(index==0&&(Field(component,"session").GetValue(component)==null||component.Message!="running"))return;
 // A real completed query fixture also exercises the shared HawaQueryComponent lifecycle.
 if(index==0){var queryType=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper").GetType("Hawa.Grasshopper.PlaneFieldComponent");var query=(GH_Component)Activator.CreateInstance(queryType);doc.AddObject(query,false);var job=original(new JsonObject{["op"]="evaluate_submit",["kind"]="query",["request"]=new JsonObject{["op"]="info"}});Field(query,"job").SetValue(query,job["job"].GetValue<string>());}
 deny=true;failed=0;Close();retained=Pending();if(retained==0)throw new Exception("Disposal lost cleanup ownership");if(Field(component,index==0?"creation":"job").GetValue(component)!=null)throw new Exception("Disposed component retained local handle");released=DateTime.UtcNow;phase=2;return;}
 if(phase==2){if((DateTime.UtcNow-released).TotalSeconds<3)return;if(Pending()!=retained)throw new Exception("Failed close was forgotten");deny=false;phase=3;return;}
 if(Pending()!=0)return;
 var script=runtime.GetField("script",flags).GetValue(null);var execute=(MethodInfo)runtime.GetField("execute",flags).GetValue(null);
 execute.Invoke(script,new object[]{"import json, threading\nfrom hawa.jobs import JOBS\nfrom hawa.plugin import SESSIONS\nfrom pathlib import Path\nPath('"+output+"/registry.json').write_text(json.dumps(dict(jobs=len(JOBS),sessions=len(SESSIONS),workers=[t.name for t in threading.enumerate() if t.name.startswith('Hawa ')])))"});
 var registry=JsonNode.Parse(System.IO.File.ReadAllText(output+"/registry.json"));if(registry["jobs"].GetValue<int>()!=0||registry["sessions"].GetValue<int>()!=0||registry["workers"].AsArray().Count!=0)return;
 reports.Add(new JsonObject{["file"]=files[index],["component"]=names[index],["query_fixture"]=index==0,["passed"]=true,["failed_close_attempts"]=failed,["retained_after_disposal"]=retained,["seconds_to_recovery"]= (DateTime.UtcNow-released).TotalSeconds,["registry"]=registry});index++;if(index==files.Length){Finish();Save("completed");}else Open();
 }catch(Exception ex){deny=false;try{Close();}finally{Finish();Save("failed",ex.ToString());}}};
try{Open();timer.Start();Console.WriteLine("Legacy cleanup fault injection queued");}catch(Exception ex){Finish();Save("failed",ex.ToString());throw;}
