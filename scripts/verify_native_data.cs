// Run once through Rhino MCP after foreground Runtime initialization. Adjust root only.
// Creates/disposes only owned headless documents and one actual Eto panel; no private fields.
using System.IO;
using System.Text.Json.Nodes;
using Eto.Forms;
using Rhino;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-issue-35-complete";
var output=Path.Combine(root,"results","native-data-host",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(output);
var shared=AppDomain.CurrentDomain.GetAssemblies().Single(a=>a.GetName().Name=="Hawa.Shared");
var native=AppDomain.CurrentDomain.GetAssemblies().Single(a=>a.GetName().Name=="Hawa.Rhino");
var hub=shared.GetType("Hawa.Shared.CaseHub");
object Call(string name,params object[] args)=>hub.GetMethod(name).Invoke(null,args);
int Cleanup()=>(int)hub.GetProperty("PendingCleanupCount").GetValue(null);
int Refreshes(){var gh=AppDomain.CurrentDomain.GetAssemblies().SingleOrDefault(a=>a.GetName().Name=="Hawa.Grasshopper");return gh==null?0:(int)gh.GetType("Hawa.Grasshopper.HawaPollScheduler").GetProperty("PendingCount").GetValue(null);}
if(Cleanup()!=0||Refreshes()!=0)throw new Exception("Finish pre-existing cleanup before this check.");
var original=__rhino_doc__;uint originalSerial=original.RuntimeSerialNumber;
RhinoDoc owned=RhinoDoc.CreateHeadless(null);owned.ModelUnitSystem=UnitSystem.Millimeters;uint serial=owned.RuntimeSerialNumber;
Panel panel=(Panel)Activator.CreateInstance(native.GetType("Hawa.Native.HawaPanel"),serial);
dynamic c=null;
var report=new JsonObject{["state"]="running",["output"]=output,["preserved_document"]=originalSerial,["owned_document"]=serial,["backend"]="cpu",["shared_assembly"]=shared.Location};
var checks=new JsonArray();var artifacts=new JsonObject();int phase=0;DateTime began=DateTime.UtcNow;
string firstSession="",importedSession="",firstCase="",importedCase="";
JsonObject importedSource=null;
string saved=Path.Combine(output,"completed-6.npz"),resaved=Path.Combine(output,"imported-paused-6.npz"),continued=Path.Combine(output,"continued-12.npz"),probe=Path.Combine(output,"paused-probes.csv"),document=Path.Combine(output,"imported.3dm");
var timer=new UITimer{Interval=.2};string timerKey="Hawa.NativeDataAcceptance."+Guid.NewGuid().ToString("N");AppDomain.CurrentDomain.SetData(timerKey,timer);
void Check(bool good,string message){if(!good)throw new Exception(message);}
JsonObject Copy(JsonNode value)=>JsonNode.Parse(value.ToJsonString()).AsObject();
IEnumerable<Control> Walk(Control control){yield return control;if(control is Container container)foreach(var child in container.Controls)foreach(var next in Walk(child))yield return next;}
Button Button(string text)=>Walk(panel).OfType<Button>().Single(b=>b.Text==text);
void Click(string text){var button=Button(text);Check(button.Enabled,"Disabled action: "+text);button.PerformClick();}
T After<T>(string label)where T:Control{var controls=Walk(panel).ToArray();int index=Array.FindIndex(controls,v=>v is Label l&&l.Text==label);Check(index>=0,"Missing label: "+label);return controls.Skip(index+1).OfType<T>().First();}
DropDown Choice(string value)=>Walk(panel).OfType<DropDown>().Single(d=>d.ToolTip!="Backend for importing saved data"&&d.DataStore.Cast<object>().Any(v=>v.ToString()==value));
CheckBox Toggle(string text)=>Walk(panel).OfType<CheckBox>().Single(v=>v.Text==text);
void DataAction(string path,string action){Walk(panel).OfType<TextBox>().Single(t=>t.ToolTip!=null&&t.ToolTip.StartsWith("Hawa data")).Text=path;Click(action);}
void Save(string state){report["state"]=state;report["phase"]=phase;report["checks"]=JsonNode.Parse(checks.ToJsonString());report["artifacts"]=JsonNode.Parse(artifacts.ToJsonString());File.WriteAllText(Path.Combine(output,"rhino.json"),report.ToJsonString(new System.Text.Json.JsonSerializerOptions{WriteIndented=true}));}
void Pass(string text){checks.Add(text);phase++;began=DateTime.UtcNow;Save("running");}
void Stop(){timer.Stop();timer.Dispose();AppDomain.CurrentDomain.SetData(timerKey,null);}
void DisposeOwned(){panel?.Dispose();panel=null;if(owned!=null){Call("Close",owned.RuntimeSerialNumber);owned.Dispose();owned=null;}}
void Unchanged(string id,string session,int steps){Check(((Guid)c.Id).ToString()==id&&(string)c.Session==session&&(int)c.Steps==steps,"Accepted case/session/iteration changed unexpectedly");}
bool DataDone(string state,string key){if((string)c.DataState=="failed")throw new Exception((string)c.DataError);if((string)c.DataState!=state)return false;artifacts[key]=Copy((JsonObject)c.DataResult);return true;}
void Captured(string path,int steps,string state){var result=(JsonObject)c.DataResult;var meta=result["metadata"];Check(result["path"].GetValue<string>()==path&&File.Exists(path),"Missing/wrong saved path");Check(meta["iteration"].GetValue<int>()==steps&&meta["source_state"].GetValue<string>()==state&&meta["source_session"].GetValue<string>()==(string)c.Session,"Saved capture identity mismatch");}
void DynamicView(){Choice("YZ · X normal").SelectedIndex=0;Choice("spectrum").SelectedValue="spectrum";After<NumericStepper>("Slice position (0..1)").Value=.25;Toggle("Annotations and legend").Checked=false;var view=(JsonObject)c.View;Check(view["axis"].GetValue<int>()==0&&view["position"].GetValue<double>()==.25&&view["palette"].GetValue<string>()=="spectrum"&&!view["annotations"].GetValue<bool>(),"Dynamic view events did not commit");}
Save("running");
timer.Elapsed+=(_,_)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>120)throw new Exception("Timed out at phase "+phase);
 if(owned!=null)Call("Tick");
 switch(phase){
 case 0:
  Click("Block preset");c=Call("Find",serial);Check(c!=null,"Preset did not create case");
  Check(!Walk(panel).OfType<Button>().Any(b=>b.Text.StartsWith("Apply")),"Obsolete Apply control remains");
  After<DropDown>("Backend").SelectedValue="cpu";After<NumericStepper>("Total target iterations").Value=6;
  After<NumericStepper>("Kinematic viscosity (m²/s)").Value=.075;
  Check(((JsonObject)c.Setup)["viscosity"].GetValue<double>()==.075,"Fluid event did not commit");
  After<DropDown>("Y− boundary").SelectedValue="periodic";
  Check(((JsonObject)c.Setup)["boundaries"][2].GetValue<string>()=="periodic"&&((JsonObject)c.Setup)["boundaries"][3].GetValue<string>()=="periodic","Periodic side pair did not commit atomically");
  DynamicView();var accepted=Copy((JsonObject)c.View);var low=After<NumericStepper>("Lower limit (field units)");var high=After<NumericStepper>("Upper limit (field units)");low.Value=high.Value+1;
  Check(((JsonObject)c.View).ToJsonString()==accepted.ToJsonString(),"Invalid colour draft changed accepted view");Check(Walk(panel).OfType<Label>().Any(l=>l.Text.Contains("upper colour limit")),"Invalid colour draft has no visible feedback");
  high.Value=low.Value+1;Check(((JsonObject)c.View)["min"].GetValue<double>()==low.Value&&((JsonObject)c.View)["max"].GetValue<double>()==high.Value,"Valid colour pair did not commit");
  Check(c.Session==null&&(string)c.State=="idle","Dynamic setup/view implicitly started solver");Click("Run / Resume");Pass("Actual panel fluid, periodic-pair and view events accepted; invalid range retained; explicit CPU six-step run");break;
 case 1:
  if((string)c.State=="failed")throw new Exception((string)c.Error);if((string)c.State!="completed"||c.Result==null||(int)c.Steps!=6)return;
  firstSession=(string)c.Session;firstCase=((Guid)c.Id).ToString();artifacts["source6"]=Copy((JsonObject)c.Describe());
  Choice("spectrum").SelectedValue="diverging";After<NumericStepper>("Slice position (0..1)").Value=.5;Toggle("Body bounds").Checked=false;Unchanged(firstCase,firstSession,6);
  DataAction(saved,"Save data");Pass("Completed source unchanged by live view events; Save data button submitted");break;
 case 2:
  if(!DataDone("saved","saved6"))return;Captured(saved,6,"completed");string invalid=Path.Combine(output,"invalid.npz");File.WriteAllText(invalid,"not an archive");DataAction(invalid,"Import data");Pass("Six-step checkpoint saved; invalid import submitted through panel");break;
 case 3:
  if((string)c.DataState=="importing")return;Check((string)c.DataState=="failed"&&!string.IsNullOrWhiteSpace((string)c.DataError),"Invalid file import did not report failure");Unchanged(firstCase,firstSession,6);report["invalid_import_error"]=(string)c.DataError;
  DataAction(saved,"Import data");report["cancel_job"]=(string)c.DataJob;Click("Cancel data operation");Check((string)c.DataState=="cancelled"&&c.DataJob==null,"Immediate cancel retained import ownership");Unchanged(firstCase,firstSession,6);Pass("Invalid import and immediate cancellation preserved accepted case/session");break;
 case 4:
  if(Cleanup()!=0||(DateTime.UtcNow-began).TotalSeconds<1.2)return;Unchanged(firstCase,firstSession,6);DataAction(saved,"Import data");Pass("Cancelled import cleanup acknowledged; valid import explicitly submitted");break;
 case 5:
  if(!DataDone("imported","imported6"))return;importedSession=(string)c.Session;importedCase=((Guid)c.Id).ToString();Check(importedSession!=firstSession&&importedCase!=firstCase&&(bool)c.Imported&&(string)c.State=="paused"&&(int)c.Steps==6,"Import did not establish new local case and paused session");importedSource=Copy((JsonObject)c.ImportedSource);
  Check(!After<NumericStepper>("Kinematic viscosity (m²/s)").Enabled,"Imported physics controls remain editable");DynamicView();Pass("Successful import owns a new paused case/session; read-only physics and dynamic view verified");break;
 case 6:
  if((DateTime.UtcNow-began).TotalSeconds<1.2||c.Result==null)return;Unchanged(importedCase,importedSession,6);Check((string)c.State=="paused"&&(int)c.Result.Steps==6,"Viewing imported data advanced the solver");artifacts["paused_view"]=Copy((JsonObject)c.Describe());
  owned.ModelUnitSystem=UnitSystem.Meters;Call("Tick");Call("Export",serial,probe,"probes",new[]{new Point3d(1,1,1)});Pass("Imported view remained paused beyond one second; unit-change probe CSV submitted");break;
 case 7:
  if((string)c.ExportState=="failed")throw new Exception((string)c.ExportError);if((string)c.ExportState!="completed")return;var lines=File.ReadAllLines(probe);Check(lines.Length==3,"Expected one probe CSV row");var row=lines[2].Split(',');Check(row[1]=="2.0"||row[1]=="2","Metre probe did not map to lattice2");for(int i=1;i<4;i++)Check(double.Parse(row[i],System.Globalization.CultureInfo.InvariantCulture)==2,"Probe lattice coordinate mismatch");for(int i=4;i<7;i++)Check(double.Parse(row[i],System.Globalization.CultureInfo.InvariantCulture)==1,"Probe physical coordinate mismatch");Check(row[7]=="1","Probe is not valid");artifacts["paused_probe"]=Copy((JsonObject)c.ExportResult);Unchanged(importedCase,importedSession,6);
  DataAction(resaved,"Save data");Pass("Metres-after-import probe maps exactly lattice2/world1; paused resave submitted");break;
 case 8:
  if(!DataDone("saved","resaved6"))return;Captured(resaved,6,"paused");After<NumericStepper>("Total target iterations").Value=12;Unchanged(importedCase,importedSession,6);Check((string)c.State=="paused","Target edit implicitly resumed");Click("Run / Resume");Pass("Paused checkpoint resaved; target12 remains paused until explicit Run button");break;
 case 9:
  if((string)c.State=="failed")throw new Exception((string)c.Error);if((string)c.State!="completed"||(int)c.Steps!=12)return;Unchanged(importedCase,importedSession,12);DataAction(continued,"Save data");Pass("Imported session explicitly continued to12; continued checkpoint submitted");break;
 case 10:
  if(!DataDone("saved","continued12"))return;Captured(continued,12,"completed");artifacts["continued_source"]=Copy((JsonObject)c.Describe());
  Check(owned.WriteFile(document,new Rhino.FileIO.FileWriteOptions{WriteUserData=true,SuppressDialogBoxes=true}),"Owned 3dm save failed");DisposeOwned();Pass("Continued data saved; actual owned Rhino archive written and document closed");break;
 case 11:
  if(Cleanup()!=0)return;owned=RhinoDoc.OpenHeadless(document);Check(owned!=null,"Owned 3dm reopen failed");serial=owned.RuntimeSerialNumber;c=Call("Find",serial);Check(c!=null,"Actual plugin archive did not restore a case");Check((bool)c.Imported&&(string)c.State=="idle"&&c.Session==null&&c.Job==null&&((Guid)c.Id).ToString()==importedCase,"Reopened imported case lost identity or started runtime");Check(((JsonObject)c.ImportedSource).ToJsonString()==importedSource.ToJsonString(),"Reopened artifact identity changed");
  bool rejected=false;try{Call("Run",serial);}catch(Exception error){rejected=error.GetBaseException().Message.Contains("Import");report["reopen_run_error"]=error.GetBaseException().Message;}Check(rejected&&c.Session==null,"Reopened case did not require explicit re-import");artifacts["reopened"]=Copy((JsonObject)c.Describe());DisposeOwned();Pass("Actual 3dm reopen retains imported read-only identity, idle with no session; Run requires re-import");break;
 case 12:
  if(Cleanup()!=0||Refreshes()!=0||(DateTime.UtcNow-began).TotalSeconds<1.2)return;Check(RhinoDoc.FromRuntimeSerialNumber(originalSerial)==original,"Original Rhino document changed");Check(!Directory.GetFiles(output,".hawa-data.*.tmp").Any(),"Native data temporary leaked");report["pending_cleanup"]=Cleanup();report["pending_refreshes"]=Refreshes();report["limits"]="CPU owned headless document and actual Eto event/service workflow. No file-picker/docking acceptance, GPU or numerical-accuracy claim. Root must independently compare NPZ arrays, mean history and continuation; perform separate same-process worker/registry audit. Original Rhino/GH documents were not edited.";Stop();Save("passed");break;
 }
 }catch(Exception error){report["error"]=error.ToString();try{DisposeOwned();}catch(Exception cleanup){report["cleanup_error"]=cleanup.ToString();}Stop();Save("failed");}};
timer.Start();Console.WriteLine("Native data verification started: "+Path.Combine(output,"rhino.json"));
