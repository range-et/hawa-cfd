// At phases 4 and 5, use normal Rhino Undo and Redo commands through the UI.
// Nonblocking integration checks: run in an otherwise empty test document with example 21 open.
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
var root="/Users/r2d2/Desktop/hawa-cfd";
var hub=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Shared").GetType("Hawa.Shared.CaseHub");
uint serial=__rhino_doc__.RuntimeSerialNumber;
object Call(string name,params object[] args)=>hub.GetMethod(name).Invoke(null,args);
dynamic c=Call("Get",serial);
void Edit(JsonObject patch)=>Call("Edit",serial,patch,(long)c.Version,"panel",true);
var d=Grasshopper.Instances.ActiveCanvas.Document;var component=d.Objects.OfType<GH_Component>().First(x=>x.Name=="Hawa Linked Case");var sliders=d.Objects.OfType<GH_NumberSlider>().ToArray();
void Check(bool pass,string message){if(!pass)throw new Exception(message);}
var report=new JsonObject();var checks=new JsonArray();var timer=new System.Windows.Forms.Timer{Interval=300};int phase=0;DateTime began=DateTime.UtcNow;string session="",saved="";long revision=0;int pausedSteps=0;
void Save(string state){report["state"]=state;report["phase"]=phase;report["checks"]=JsonNode.Parse(checks.ToJsonString());System.IO.File.WriteAllText(root+"/results/v05/native-integration.json",report.ToJsonString());}
void Pass(string label){checks.Add(label);phase++;began=DateTime.UtcNow;Save("running");}
timer.Tick+=(_,e)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>90)throw new Exception("Timeout phase "+phase);
 var errors=component.RuntimeMessages(GH_RuntimeMessageLevel.Error);if(errors.Count>0)throw new Exception(string.Join(";",errors));
 switch(phase){
 case 0:Check(c.BindingOwner!=null,"binding missing");Check(AppDomain.CurrentDomain.GetAssemblies().Count(a=>a.GetName().Name=="Hawa.Shared")==1,"duplicate shared assembly");session=(string)c.Session;Edit(new(){["speed"]=1.2,["cell"]=.75,["width"]=1.5});Pass("one shared assembly and one binding");break;
 case 1:if(sliders[0].CurrentValue!=1.2m||sliders[1].CurrentValue!=.75m||sliders[2].CurrentValue!=1.5m)return;Check(c.Session==null,"edit retained old session");revision=(long)c.Version;Pass("panel changes reached all three GH sliders; old session closed");break;
 case 2:Check((long)c.Version==revision,"feedback loop changed revision");sliders[0].SetSliderValue(1.4m);sliders[0].ExpireSolution(false);d.NewSolution(false);Check((double)c.Speed==1.4,"GH speed not synced");Pass("GH slider updates shared case without feedback loop");break;
 case 3:Pass("waiting for normal Rhino Undo command");break;
 case 4:if((double)c.Speed!=1.2||sliders[0].CurrentValue!=1.2m)return;Pass("Rhino undo restored shared case and slider; waiting for normal Redo command");break;
 case 5:if((double)c.Speed!=1.4||sliders[0].CurrentValue!=1.4m)return;Edit(new(){["cell"]=.5,["target"]=100000});Call("Run",serial);Pass("Rhino redo restored shared case and slider");break;
 case 6:if(c.Session==null||(int)c.Steps<5)return;var sw=System.Diagnostics.Stopwatch.StartNew();Call("Pause",serial);report["pause_submit_ms"]=sw.ElapsedMilliseconds;Pass("run started; cooperative pause submitted");break;
 case 7:if((string)c.State!="paused")return;pausedSteps=(int)c.Steps;session=(string)c.Session;Pass("worker acknowledged pause");break;
 case 8:Check((int)c.Steps==pausedSteps,"paused worker advanced");Edit(new(){["field"]="pressure"});Check((string)c.Session==session,"display edit restarted solver");Edit(new(){["target"]=pausedSteps+25});Call("Run",serial);Pass("pause held; display edit reused session; resume submitted");break;
 case 9:if((string)c.State!="completed"||c.Slice==null)return;Check((int)c.Steps==pausedSteps+25,"resume target mismatch");Check((string)c.Session==session,"resume replaced session");Check(component.Params.Output[1].VolatileDataCount>0,"no GH shared mesh");Pass("resumed to target with same session and GH field output");break;
 case 10:Rhino.UI.Panels.ClosePanel(new Guid("34472112-31d7-4d1e-98f9-fb6130a50501"));Check((string)c.Session==session,"closing panel closed session");Rhino.UI.Panels.OpenPanel(new Guid("34472112-31d7-4d1e-98f9-fb6130a50501"));Pass("panel close/reopen kept case and result");break;
 case 11:Edit(new(){["speed"]=1.3});Check((bool)c.Describe()["outdated"].GetValue<bool>(),"old result not marked stale");Check(c.Session==null,"stale run remained live");Call("Run",serial);Pass("physical edit marks field outdated and closes old run");break;
 case 12:if(c.Session==null)return;var sw2=System.Diagnostics.Stopwatch.StartNew();Call("Cancel",serial);report["cancel_submit_ms"]=sw2.ElapsedMilliseconds;Check(c.Session==null&&c.Job==null,"cancel retained handles");Call("Reset",serial);Check(c.Slice==null&&(int)c.Steps==0,"reset retained result");Pass("cancel and reset release runtime handles");break;
 case 13:saved=(string)Call("Save",serial);var before=(long)c.Version;bool rejected=false;try{Call("Edit",serial,new JsonObject{["speed"]=2},before-1,"panel",true);}catch{rejected=true;}Check(rejected,"stale write accepted");bool ownerRejected=false;try{Call("Bind",(object)c,Guid.NewGuid(),Array.Empty<string>());}catch{ownerRejected=true;}Check(ownerRejected,"second writer accepted");Pass("stale revision and duplicate binding rejected");break;
 case 14:Grasshopper.Instances.ActiveCanvas.Document=null;Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();Check(c.BindingOwner==null,"GH close retained binding");Call("Restore",serial,saved);Check((string)c.State=="idle"&&c.Session==null,"restore auto-ran");Pass("GH close unbound and settings restore stayed idle");break;
 case 15:Edit(new(){["device"]="mps",["target"]=25});Call("Run",serial);Pass("native MPS run submitted");break;
 case 16:if((string)c.State!="completed"||c.Slice==null)return;Check((int)c.Steps==25,"MPS target mismatch");report["mps_status"]=JsonNode.Parse((string)c.Status.ToJsonString(null));Call("Close",serial);Check(Call("Find",serial)==null,"case retained after close");Pass("native MPS completed 25 steps; case closed");timer.Stop();timer.Dispose();Save("completed");break;
 }
 }catch(Exception ex){timer.Stop();report["error"]=ex.ToString();Save("failed");}};
timer.Start();Save("running");Console.WriteLine("Native integration checks queued");
