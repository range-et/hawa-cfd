// Run through Rhino MCP ONLY after foreground Runtime initialization; root is the sole Rhino owner.
// Adjust root. Reads example 35, works on unique copies, preserves the prior canvas and source bytes.
// Timer-driven CPU lifecycle acceptance, NOT numerical or fine-grid pressure qualification.
using System.IO;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Types;
var root="/Users/r2d2/Desktop/hawa-parametric-wing-example";
if(Rhino.RhinoDoc.ActiveDoc==null||Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem!=Rhino.UnitSystem.Meters)throw new Exception("Use an owned metre-unit Rhino test document.");
var assembly=AppDomain.CurrentDomain.GetAssemblies().Single(a=>a.GetName().Name=="Hawa.Grasshopper");
var runtime=assembly.GetType("Hawa.Grasshopper.EmbeddedRuntime");
if(!(bool)runtime.GetProperty("IsReady").GetValue(null))throw new Exception("Initialize Runtime first on the foreground host thread.");
var hub=AppDomain.CurrentDomain.GetAssemblies().Single(a=>a.GetName().Name=="Hawa.Shared").GetType("Hawa.Shared.CaseHub");
int Cleanup()=>(int)hub.GetProperty("PendingCleanupCount").GetValue(null);
int Refreshes()=>(int)assembly.GetType("Hawa.Grasshopper.HawaPollScheduler").GetProperty("PendingCount").GetValue(null);
if(Cleanup()!=0||Refreshes()!=0)throw new Exception("Finish pre-existing jobs before isolated verification.");
var output=Path.Combine(root,"results","stationary-study-host",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(output);
var source=Path.Combine(root,"examples/grasshopper/35-parametric-wing-study.gh");
string Hash(string path)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
var sourceHash=Hash(source);var copy=Path.Combine(output,"owned.gh");File.Copy(source,copy,false);
var previous=Grasshopper.Instances.ActiveCanvas.Document;
GH_Document owned=null;GH_Component study=null;int phase=0;DateTime began=DateTime.UtcNow;
Dictionary<Guid,string> wires=null;HashSet<Guid> ids=null;string[] cases=null;string[] captures=new string[2];
var checks=new JsonArray();var report=new JsonObject{["state"]="running",["device"]="cpu",["source_sha256"]=sourceHash,["assembly_sha256"]=Hash(assembly.Location),["dx_m"]=.025,["settling_steps"]=1200,["sample_steps"]=81,["tolerance"]=.05,["preserved_document"]=previous?.DocumentID.ToString()};
var timer=new Eto.Forms.UITimer{Interval=.1};var timerKey="Hawa.StationaryStudyAcceptance."+Guid.NewGuid().ToString("N");AppDomain.CurrentDomain.SetData(timerKey,timer);
void Check(bool ok,string message){if(!ok)throw new Exception(message);}
void Save(string state){report["state"]=state;report["phase"]=phase;report["checks"]=checks.DeepClone();File.WriteAllText(Path.Combine(output,"rhino.json"),report.ToJsonString(new System.Text.Json.JsonSerializerOptions{WriteIndented=true}));}
void Pass(string message){checks.Add(message);phase++;began=DateTime.UtcNow;Save("running");}
string Wires(GH_Component c)=>string.Join(";",c.Params.Input.SelectMany((p,i)=>p.Sources.Select(s=>i+":"+s.InstanceGuid)));
void Preserved(){Check(Hash(source)==sourceHash,"Source archive bytes changed");if(owned==null)return;Check(ids.SetEquals(owned.Objects.Select(o=>o.InstanceGuid)),"Archive object IDs changed");foreach(var c in owned.Objects.OfType<GH_Component>())Check(wires[c.InstanceGuid]==Wires(c),"Archive wires changed");}
void Close(){if(owned==null)return;var closing=owned;owned=null;try{if(Grasshopper.Instances.ActiveCanvas.Document==closing)Grasshopper.Instances.ActiveCanvas.Document=previous;Grasshopper.Instances.DocumentServer.RemoveDocument(closing);}finally{closing.Dispose();}}
void Stop(){timer.Stop();timer.Dispose();AppDomain.CurrentDomain.SetData(timerKey,null);}
void Solution(){Check(Grasshopper.Instances.ActiveCanvas.Document==owned,"User changed active canvas; stopping owned work");owned.NewSolution(false);}
void Bool(int index,bool value){var t=study.Params.Input[index].Sources.Single() as GH_BooleanToggle;Check(t!=null,"Expected Boolean source");t.Value=value;t.ExpireSolution(false);}
void Number(string name,decimal value){var s=owned.Objects.OfType<GH_NumberSlider>().Single(s=>s.NickName==name);Check(value>=s.Slider.Minimum&&value<=s.Slider.Maximum,"Slider range mismatch: "+name);s.SetSliderValue(value);s.ExpireSolution(false);}
IGH_Goo[] Values(int index)=>study.Params.Output[index].VolatileData.AllData(true).ToArray();
string Text(int index){var data=Values(index).Where(v=>v!=null).ToArray();if(data.Length==0)return null;Check(data.Length==1,"Expected one output value");string value="";Check(data[0].CastTo(out value),"Expected text output");return value;}
string[] CaseTexts()=>Values(7).Select(v=>{string text="";Check(v!=null&&v.CastTo(out text),"Expected candidate record");return text;}).ToArray();
void NoField(){foreach(int i in new[]{0,1,2,3,9,12,13})Check(!Values(i).Any(v=>v!=null),"Stale selected output "+i);}
void Errors(){var errors=study.RuntimeMessages(GH_RuntimeMessageLevel.Error);Check(errors.Count==0,string.Join("; ",errors));}
void Open(string path){var io=new GH_DocumentIO();Check(io.Open(path),"Cannot open owned archive");owned=io.Document;ids=owned.Objects.Select(o=>o.InstanceGuid).ToHashSet();wires=owned.Objects.OfType<GH_Component>().ToDictionary(c=>c.InstanceGuid,Wires);study=owned.Objects.OfType<GH_Component>().Single(c=>c.ComponentGuid==new Guid("4823e5ad-f4fb-4b62-96e3-127989a184b5"));Check(study.Params.Input.Count==15&&study.Params.Output.Count==14,"Study contract mismatch");Grasshopper.Instances.DocumentServer.AddDocument(owned);Grasshopper.Instances.ActiveCanvas.Document=owned;owned.Enabled=true;}
void VerifySelection(int selected){Errors();Check(study.Message=="completed","Selection restarted completed study");Check(CaseTexts().SequenceEqual(cases),"Selection changed candidate records");bool accepted=cases[selected].StartsWith("study-"+selected.ToString("D3")+": completed;");
 foreach(int i in new[]{4,5,6}){var values=Values(i);Check(values.Length==2,"Coefficient slots lost alignment");for(int j=0;j<2;j++)if(!cases[j].Contains(": completed;"))Check(values[j]==null,"Rejected candidate has coefficient");}
 if(!accepted){NoField();return;}
 var identity=JsonNode.Parse(Text(9)).AsObject();Check(identity["identity"]?["candidate_id"]?.GetValue<string>()=="study-"+selected.ToString("D3"),"Wrong selected identity");
 var field=Values(0).Single(v=>v!=null);var frame=JsonNode.Parse((string)field.GetType().GetProperty("Value").GetValue(field)).AsObject();
 Check(frame["identity"].ToJsonString()==identity["identity"].ToJsonString()&&frame["session"].ToJsonString()==identity["session"].ToJsonString()&&frame["snapshot"].ToJsonString()==identity["capture"].ToJsonString(),"Field, loads and capture provenance differ");
 var capture=identity.ToJsonString();if(captures[selected]!=null)Check(captures[selected]==capture,"Re-selecting advanced or changed retained capture");else captures[selected]=capture;
 File.WriteAllText(Path.Combine(output,"selected-"+selected+".json"),capture);
}
Save("running");
timer.Elapsed+=(_,_)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>600)throw new Exception("Timed out phase "+phase+"; "+study?.Message);
 switch(phase){
 case 0:Open(copy);foreach(var t in owned.Objects.OfType<GH_BooleanToggle>()){t.Value=false;t.ExpireSolution(false);}Number("Cell size (m)",.025m);Number("Settling steps",1200);Number("Sample steps",81);Solution();NoField();Bool(12,true);Solution();Pass("Owned coarse study explicitly started; original IDs and wires preserved");break;
 case 1:Errors();if(study.Message!="completed")return;cases=CaseTexts();Check(cases.Length==2,"Expected two candidates");Check(cases.All(c=>c.Contains(": completed;")||c.Contains(": rejected;")),"Nonterminal candidate inventory");report["cases"]=new JsonArray(cases.Select(c=>(JsonNode)JsonValue.Create(c)).ToArray());report["accepted_candidates"]=cases.Count(c=>c.Contains(": completed;"));VerifySelection(0);Number("Selected case index",1);Solution();Pass("Study completed through automatic polling without manual solution updates");break;
 case 2:VerifySelection(1);Number("Selected case index",0);Solution();Pass("Selection switched without restarting; accepted identities or rejected withholding checked");break;
 case 3:VerifySelection(0);Number("Root chord (m)",.31m);Solution();Check(study.Message.Contains("off/on"),"Input edit did not require rearm");NoField();Pass("Retained capture unchanged on re-selection; geometry edit invalidated selected data");break;
 case 4:if(Cleanup()!=0||Refreshes()!=0)return;Bool(12,false);Number("Root chord (m)",.3m);Number("Settling steps",20000);Solution();Bool(13,true);Bool(12,true);Solution();Pass("Long lifecycle-only job rearmed with pause requested");break;
 case 5:Errors();if(study.Message!="paused")return;NoField();report["paused_report"]=Text(8);Pass("Cooperative pause acknowledged without publishing a selected result");break;
 case 6:if((DateTime.UtcNow-began).TotalSeconds<1)return;Check(study.Message=="paused"&&Text(8)==report["paused_report"].GetValue<string>(),"Paused progress changed");Bool(14,true);Solution();Check(study.Message.Contains("cancelled"),"Cancel not acknowledged");NoField();Pass("Pause remained stable; Cancel cleared public selected outputs");break;
 case 7:if(Cleanup()!=0||Refreshes()!=0)return;Bool(14,false);Bool(13,false);Bool(12,false);Solution();Bool(12,true);Preserved();Check(new GH_DocumentIO{Document=owned}.SaveQuiet(Path.Combine(output,"saved-true.gh")),"Cannot save owned true-control copy");Close();Pass("Cancelled job drained; owned saved-Run-true archive created without solving");break;
 case 8:if(Cleanup()!=0||Refreshes()!=0)return;Open(Path.Combine(output,"saved-true.gh"));Solution();Check(study.Message.Contains("off/on"),"Saved true unexpectedly started");NoField();Pass("Saved Run=true reopened idle and requires explicit off/on");break;
 case 9:if((DateTime.UtcNow-began).TotalSeconds<2)return;Check(study.Message.Contains("off/on")&&Refreshes()==0,"Saved true scheduled a job");NoField();Preserved();Close();Pass("Saved-true guard remained idle; owned document disposed and previous canvas restored");break;
 case 10:if(Cleanup()!=0||Refreshes()!=0||(DateTime.UtcNow-began).TotalSeconds<2)return;Preserved();report["pending_cleanup"]=Cleanup();report["pending_refreshes"]=Refreshes();report["limits"]="CPU coarse lifecycle only. Rejected candidates may leave no pressure display; fine 3000+201 at .05 and visual pressure acceptance are separate. Public cleanup counters do not enumerate private backend workers. No convergence/aerodynamic or CUDA qualification.";Stop();Save("passed");break;
 }
 }catch(Exception error){report["error"]=error.ToString();Stop();try{Close();}catch(Exception cleanup){report["cleanup_error"]=cleanup.ToString();}Save("failed");}};
timer.Start();Console.WriteLine("Stationary study verification started: "+Path.Combine(output,"rhino.json"));
