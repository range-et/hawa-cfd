// Execute one action per MCP call. No waits on Rhino's UI thread; no source archive writes.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";var example=31;var action="open";
var output=root+"/results/compatibility-v1/host";System.IO.Directory.CreateDirectory(output);
if(action=="open"){
 if(__rhino_doc__.Objects.Count!=0)throw new Exception("Use an empty test model");__rhino_doc__.ModelUnitSystem=Rhino.UnitSystem.Meters;
 var path=System.IO.Directory.GetFiles(root+"/examples/grasshopper",example+"-*.gh").Single();
 var archive=new GH_IO.Serialization.GH_Archive();var d=new GH_Document();if(!archive.ReadFromFile(path)||!archive.ExtractObject(d,"Definition"))throw new Exception("Read failed");
 if(d.Objects.OfType<GH_BooleanToggle>().Any(t=>t.Value))throw new Exception("Source not idle");
 d.FilePath=output+"/owned-"+example+".gh";Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;d.NewSolution(false);Console.WriteLine("Opened owned "+example);
}else{
 var d=Grasshopper.Instances.ActiveCanvas.Document;if(d==null||d.FilePath!=output+"/owned-"+example+".gh")throw new Exception("Wrong owned document");
 var components=d.Objects.OfType<GH_Component>().ToArray();GH_Component C(string type)=>components.Single(c=>c.GetType().Name==type+"Component");
 void Toggle(string name,bool on){var t=d.Objects.OfType<GH_BooleanToggle>().Single(t=>t.NickName==name);t.Value=on;t.ExpireSolution(false);}
 if(action=="run"){
  if(example==31){Toggle("Initialize runtime",true);Toggle("Run",true);}else{
   var panel=d.Objects.OfType<GH_Panel>().Single(p=>p.NickName=="Recording directory");panel.UserText=output+"/recording-32";panel.ExpireSolution(false);Toggle("Record",true);
  }d.NewSolution(false);Console.WriteLine("Submitted "+example);
 }else if(new[]{"save","load","export"}.Contains(action)){
  Toggle("Run",false);Toggle("Execute file action",false);var c=C("Checkpoint");var op=(Param_String)c.Params.Input[2];op.PersistentData.Clear();op.SetPersistentData(action);op.ExpireSolution(false);
  var panel=d.Objects.OfType<GH_Panel>().Single(p=>p.NickName=="Checkpoint path");panel.UserText=output+(action=="export"?"/fields-31.npz":"/checkpoint-31.npz");panel.ExpireSolution(false);d.NewSolution(false);Console.WriteLine("Armed "+action+"; execute in next call");
 }else if(action=="execute"){Toggle("Execute file action",true);d.NewSolution(false);Console.WriteLine("Executed file action");}
 else if(action=="close"){Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();Console.WriteLine("Closed owned "+example);}
 else if(action=="report"||action=="state"){
  var errors=components.SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(e=>c.Name+": "+e)).ToArray();
  var report=new JsonObject{["example"]=example,["errors"]=new JsonArray(errors.Select(s=>JsonValue.Create(s)).ToArray())};
  foreach(var c in components)report[c.GetType().Name]=new JsonObject{["state"]=c.Message,["outputs"]=new JsonArray(c.Params.Output.Select(p=>(JsonNode)new JsonObject{["name"]=p.Name,["count"]=p.VolatileDataCount,["values"]=new JsonArray(p.VolatileData.AllData(true).Select(v=>JsonValue.Create(v.ToString())).ToArray())}).ToArray())};
  if(action=="report"){
   if(errors.Length>0)throw new Exception(string.Join(" | ",errors));
   if(example==31){if(C("Sample").Params.Output[0].VolatileDataCount!=3||C("Vectors").Params.Output[0].VolatileDataCount!=3)throw new Exception("Missing probes/vectors");}
   else if(C("Playback").Params.Output[0].VolatileDataCount!=1||C("BodyPreview").Params.Output[0].VolatileDataCount!=1)throw new Exception("Missing playback frame/body pose");
  }
  System.IO.File.WriteAllText(output+"/example-"+example+"-"+action+".json",report.ToJsonString());Console.WriteLine("Example "+example+"; errors="+errors.Length+"; "+(example==31?C("Solve").Message:C("Record").Message));
 }
}
