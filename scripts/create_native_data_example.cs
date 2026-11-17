// Run through Rhino MCP after initializing the installed runtime. Adjust root.
// Creates only owned headless documents; polls asynchronously and preserves user tabs.
// Writes a fresh result folder, never overwriting distributed examples or user data.
using System.IO;
using System.Text.Json.Nodes;
using Rhino;
using Rhino.Geometry;
using Eto.Forms;
var root="/Users/r2d2/Desktop/hawa-workflow-examples";
var output=Path.Combine(root,"results/native-data-example",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(output);
var folder=Path.Combine(output,"example");Directory.CreateDirectory(folder);
var template=Path.Combine(folder,"34-save-import-resume.3dm");
var checkpoint=Path.Combine(folder,"34-block-at-60.npz");
if(File.Exists(template)||File.Exists(checkpoint))throw new Exception("Example exists; use a fresh output checkout, never overwrite user data.");
var hub=AppDomain.CurrentDomain.GetAssemblies().Single(a=>a.GetName().Name=="Hawa.Shared").GetType("Hawa.Shared.CaseHub");
object Call(string name,params object[] args)=>hub.GetMethod(name).Invoke(null,args);
if((int)hub.GetProperty("PendingCleanupCount").GetValue(null)!=0)throw new Exception("Wait for existing cleanup.");
RhinoDoc owned=null;uint serial=0;dynamic c=null;
var report=new JsonObject{["state"]="running",["backend"]="cpu",["original_document"]=__rhino_doc__.RuntimeSerialNumber,["template"]=template,["checkpoint"]=checkpoint};
int phase=0;DateTime began=DateTime.UtcNow;var timer=new UITimer{Interval=.25};
string key="Hawa.NativeExample34."+Guid.NewGuid().ToString("N");AppDomain.CurrentDomain.SetData(key,timer);
void Save(){report["phase"]=phase;File.WriteAllText(Path.Combine(output,"report.json"),report.ToJsonString(new System.Text.Json.JsonSerializerOptions{WriteIndented=true}));}
void Next(){phase++;began=DateTime.UtcNow;Save();}
void Check(bool good,string message){if(!good)throw new Exception(message);}
void Stop(){timer.Stop();timer.Dispose();AppDomain.CurrentDomain.SetData(key,null);}
void DisposeOwned(){if(owned!=null){Call("Close",serial);owned.Dispose();owned=null;}}
try{
owned=RhinoDoc.CreateHeadless(null);owned.ModelUnitSystem=UnitSystem.Meters;
serial=owned.RuntimeSerialNumber;c=Call("Get",serial);
Call("Edit",serial,new JsonObject{["target"]=60,["device"]="cpu"},(long)c.Version,"panel",false);
owned.Strings.SetString("Hawa example","34 / Save data, import paused, export CSV, resume. Read 34-save-import-resume.md. Synthetic block flow, not aerodynamic qualification.");
if(!owned.WriteFile(template,new Rhino.FileIO.FileWriteOptions{WriteUserData=true,SuppressDialogBoxes=true}))throw new Exception("Cannot save idle template");
Call("Run",serial);Save();
timer.Elapsed+=(_,_)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>120)throw new Exception("Example timeout at phase "+phase);
 if(owned!=null)Call("Tick");
 if(owned!=null&&((string)c.State=="failed"||(string)c.DataState=="failed"||(string)c.ExportState=="failed"))throw new Exception(c.Describe().ToJsonString());
 switch(phase){
 case 0:
  if((string)c.State!="completed"||c.Result==null||(int)c.Result.Steps!=60)return;
  Check((int)c.Steps==60,"Wrong source step");report["source"]=JsonNode.Parse(c.Describe().ToJsonString());Call("SaveData",serial,checkpoint);Next();break;
 case 1:
  if((string)c.DataState!="saved")return;
  report["saved"]=JsonNode.Parse(c.DataResult.ToJsonString());Call("ImportData",serial,checkpoint,"cpu");Next();break;
 case 2:
  if((string)c.DataState!="imported"||c.Result==null)return;
  Check((string)c.State=="paused"&&(int)c.Steps==60,"Import must remain paused at60");
  var view=(JsonObject)c.View;view["axis"]=0;view["position"]=.35;view["palette"]="spectrum";
  Call("Edit",serial,new JsonObject{["view"]=view},(long)c.Version,"panel",false);Next();break;
 case 3:
  if((DateTime.UtcNow-began).TotalSeconds<1.5||c.Result==null)return;
  Check((string)c.State=="paused"&&(int)c.Steps==60&&(int)c.Result.Steps==60,"Dynamic viewing advanced state");report["paused_view"]=JsonNode.Parse(c.Describe().ToJsonString());
  Call("Export",serial,Path.Combine(output,"fields-60.csv"),"fields",null);Next();break;
 case 4:
  if((string)c.ExportState!="completed")return;report["fields"]=JsonNode.Parse(c.ExportResult.ToJsonString());
  Call("Export",serial,Path.Combine(output,"probes-60.csv"),"probes",new[]{new Point3d(1,1,1),new Point3d(1,2,1),new Point3d(-1,1,1)});Next();break;
 case 5:
  if((string)c.ExportState!="completed")return;report["probes"]=JsonNode.Parse(c.ExportResult.ToJsonString());
  Call("Edit",serial,new JsonObject{["target"]=120},(long)c.Version,"panel",false);
  Check((string)c.State=="paused"&&(int)c.Steps==60,"Target edit advanced state");Call("Run",serial);Next();break;
 case 6:
  if((string)c.State!="completed")return;Check((int)c.Steps==120,"Continuation did not reach120");report["continued"]=JsonNode.Parse(c.Describe().ToJsonString());
  Call("SaveData",serial,Path.Combine(output,"continued-120.npz"));Next();break;
 case 7:
  if((string)c.DataState!="saved")return;DisposeOwned();Next();break;
 case 8:
  if((int)hub.GetProperty("PendingCleanupCount").GetValue(null)!=0)return;
  owned=RhinoDoc.OpenHeadless(template);serial=owned.RuntimeSerialNumber;c=Call("Find",serial);
  Check(c!=null&&(string)c.State=="idle"&&c.Session==null&&(int)c.Target==60,"Distributed template must reopen idle");
  report["reopened_template"]=JsonNode.Parse(c.Describe().ToJsonString());DisposeOwned();Next();break;
 case 9:
  if((int)hub.GetProperty("PendingCleanupCount").GetValue(null)!=0)return;
  report["state"]="passed";report["pending_cleanup"]=0;Stop();Save();break;
 }
 }catch(Exception error){report["state"]="failed";report["error"]=error.ToString();try{DisposeOwned();}catch(Exception cleanup){report["cleanup_error"]=cleanup.ToString();}Stop();Save();}};
timer.Start();Console.WriteLine("Started example34: "+Path.Combine(output,"report.json"));

}catch{Stop();DisposeOwned();throw;}
