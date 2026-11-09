// Isolated native example 22: open its 3dm, then the unbound GH definition.
// Leaves the owned example open for visual inspection; never saves over templates.
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Types;
var root="/Users/r2d2/Desktop/hawa-cfd";
if(Grasshopper.Instances.DocumentServer.DocumentCount!=0)throw new Exception("Close owned test definitions first");
bool already;var doc=Rhino.RhinoDoc.Open(root+"/examples/native-prototype/22-selected-canopy.3dm",out already);
if(doc==null||already)throw new Exception("Use a fresh example document");
var serial=doc.RuntimeSerialNumber;
var hub=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Shared").GetType("Hawa.Shared.CaseHub");
object Call(string name,params object[] args)=>hub.GetMethod(name).Invoke(null,args);
dynamic c=Call("Get",serial);
var io=new GH_DocumentIO();if(!io.Open(root+"/examples/native-prototype/22-native-selected-geometry.gh"))throw new Exception("Missing example");
var d=io.Document;var component=d.Objects.OfType<GH_Component>().Single();
var caseId=component.GetType().GetField("caseId",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance);
if((Guid)caseId.GetValue(component)!=Guid.Empty)throw new Exception("Distributable template was bound");
Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;d.NewSolution(false);
var speed=(GH_NumberSlider)component.Params.Input[0].Sources.Single();var cell=(GH_NumberSlider)component.Params.Input[1].Sources.Single();
var report=new JsonObject{["document"]=serial,["case_id"]=c.Id.ToString(),["template_unbound"]=true};var checks=new JsonArray();int phase=0;string session="";var began=DateTime.UtcNow;
var timer=new System.Windows.Forms.Timer{Interval=250};
void Check(bool ok,string message){if(!ok)throw new Exception(message);}
void Save(string state){report["state"]=state;report["phase"]=phase;report["checks"]=checks.DeepClone();System.IO.File.WriteAllText(root+"/results/v05/release/selected-sync.json",report.ToJsonString());}
void Edit(JsonObject patch)=>Call("Edit",serial,patch,(long)c.Version,"panel",true);
void Pass(string message){checks.Add(message);phase++;began=DateTime.UtcNow;Save("running");}
timer.Tick+=(_,_)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>120)throw new Exception("Timeout phase "+phase);
 var errors=component.RuntimeMessages(GH_RuntimeMessageLevel.Error);Check(errors.Count==0,string.Join(";",errors));Check(string.IsNullOrEmpty((string)c.Error),(string)c.Error);
 switch(phase){
 case 0:Check(c.SelectedGeometry&&c.BindingOwner!=null,"Selected case binding missing");Check(component.Params.Input[2].Sources.Count==0,"Width connected");Edit(new(){["speed"]=1.2,["cell"]=.05,["target"]=200,["device"]="mps"});Pass("saved selected case reopened idle; two-input binding acquired");break;
 case 1:if(speed.CurrentValue!=1.2m||cell.CurrentValue!=.05m)return;speed.SetSliderValue(1.3m);speed.ExpireSolution(false);d.NewSolution(false);Check((double)c.Speed==1.3,"GH edit not accepted");Call("Run",serial);Pass("panel-to-GH and GH-to-panel physical edits; MPS run submitted");break;
 case 2:if(c.State!="completed"||c.Result==null||(int)c.Result.Steps!=200)return;var mesh=component.Params.Output[1].VolatileData.AllData(true).OfType<GH_Mesh>().FirstOrDefault()?.Value;if(mesh==null)return;Check(mesh.IsValid&&mesh.Faces.Count>0,"Invalid shared field");Check(mesh.GetBoundingBox(true).Min.X<0,"Physical origin was lost");session=(string)c.Session;report["result"]=JsonNode.Parse((string)c.Describe().ToJsonString());var view=c.View;view["palette"]="spectrum";view["axis"]=1;Edit(new(){["view"]=view});Check((string)c.Session==session,"Display edit restarted session");Pass("200-step MPS field and physical origin verified; slice display edit reuses session");break;
 case 3:if(c.Slice==null||c.Result==null||(int)c.Result.Steps!=200)return;Check((string)c.Session==session,"Query replaced session");report["gh_document"]=d.DocumentID.ToString();Pass("replacement slice captured; example remains open for UI inspection");timer.Stop();timer.Dispose();Save("completed");break;
 }
 }catch(Exception e){timer.Stop();report["error"]=e.ToString();Save("failed");}};
timer.Start();Save("running");Console.WriteLine("Selected native sync queued for document "+serial);
