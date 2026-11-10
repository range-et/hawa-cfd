// One action per MCP call. Never poll or wait on the Rhino UI thread.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";var action="open";var control="A / city / Record";
var source=root+"/examples/grasshopper/33-neutral-city-to-pond.gh";var run=root+"/results/atmosphere-nesting/live-33-1";
if(action=="open"){
 System.IO.Directory.CreateDirectory(run);var archive=new GH_IO.Serialization.GH_Archive();var d=new GH_Document();if(!archive.ReadFromFile(source)||!archive.ExtractObject(d,"Definition"))throw new Exception("Read failed");
 if(archive.Messages.Any(m=>m.Message.Contains("missing")||m.Message.Contains("corrupt")))throw new Exception("Archive migration failed");
 if(d.Objects.OfType<GH_BooleanToggle>().Any(t=>t.Value))throw new Exception("Shipped source is enabled");
 // New pressure-backflow option; appended-port migration preserves old IDs/wires.
 foreach(var patch in d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Boundary Patch"&&c.NickName.EndsWith("/ open"))){((Param_Vector)patch.Params.Input[2]).PersistentData.Clear();((Param_Vector)patch.Params.Input[2]).SetPersistentData(Rhino.Geometry.Vector3d.Zero);((Param_String)patch.Params.Input[6]).PersistentData.Clear();((Param_String)patch.Params.Input[6]).SetPersistentData("pressure");}
 foreach(var c in d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Neutral Flow")){((Param_Boolean)c.Params.Input[5]).PersistentData.Clear();((Param_Boolean)c.Params.Input[5]).SetPersistentData(true);}
 foreach(var patch in d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Boundary Patch"&&c.NickName.StartsWith("x- / velocity"))){((Param_Vector)patch.Params.Input[2]).PersistentData.Clear();((Param_Vector)patch.Params.Input[2]).SetPersistentData(new Rhino.Geometry.Vector3d(5,0,0));}
 // Never write the distributed source while operating an owned test copy.
 foreach(var panel in d.Objects.OfType<GH_Panel>().Where(p=>p.NickName.Contains("NEW"))){string name=panel.NickName.StartsWith("A")?"city":panel.NickName.StartsWith("B")?"neighbourhood":"pond";panel.UserText=run+"/"+name+(panel.NickName.Contains("boundary")?"-boundary.npz":"-recording");}
 d.FilePath=run+"/owned.gh";__rhino_doc__.AdjustModelUnitSystem(Rhino.UnitSystem.Meters,true);Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;d.NewSolution(false);Console.WriteLine(d.DocumentID);
}else{
 var d=Grasshopper.Instances.ActiveCanvas.Document;if(d==null||d.FilePath!=run+"/owned.gh")throw new Exception("Wrong document");
 if(action=="enable"||action=="disable"){
  var toggle=d.Objects.OfType<GH_BooleanToggle>().Single(t=>t.NickName==control);toggle.Value=action=="enable";toggle.ExpireSolution(false);d.NewSolution(false);Console.WriteLine(control+"="+toggle.Value);
 }else if(action=="close"){Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();Console.WriteLine("Closed owned example");}
 else if(action=="state"||action=="report"){
  var components=d.Objects.OfType<GH_Component>().ToArray();var errors=components.SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(e=>c.NickName+": "+e)).ToArray();
  var report=new JsonObject{["errors"]=new JsonArray(errors.Select(e=>JsonValue.Create(e)).ToArray()),["components"]=new JsonArray(components.Where(c=>new[]{"Hawa Record","Hawa Boundary Capture","Hawa Boundary Data","Hawa Flow Statistics","Hawa Result Quality"}.Contains(c.Name)).Select(c=>(JsonNode)new JsonObject{["name"]=c.Name,["nick"]=c.NickName,["state"]=c.Message,["outputs"]=new JsonArray(c.Params.Output.Select(p=>(JsonNode)new JsonObject{["port"]=p.Name,["non_null"]=p.VolatileData.AllData(true).Count(v=>v!=null),["values"]=new JsonArray(p.VolatileData.AllData(true).Where(v=>v!=null).Take(1).Select(v=>JsonValue.Create(v is GH_String s?s.Value:v.ToString())).ToArray())}).ToArray())}).ToArray())};
  var meshes=components.Where(c=>c.Name=="Hawa Plane Field").SelectMany(c=>c.Params.Output.SelectMany(p=>p.VolatileData.AllData(true))).OfType<GH_Mesh>().ToArray();report["mesh_count"]=meshes.Length;report["valid_meshes"]=meshes.Length==3&&meshes.All(m=>m.Value.IsValid&&m.Value.Faces.Count>0);
  if(action=="report"&&(errors.Length>0||!report["valid_meshes"].GetValue<bool>()||components.Where(c=>c.Name=="Hawa Record").Any(c=>c.Message!="completed")||components.Where(c=>c.Name=="Hawa Flow Statistics").Any(c=>c.Params.Output[0].VolatileDataCount==0)))throw new Exception(report.ToJsonString());
  System.IO.File.WriteAllText(run+"/"+action+".json",report.ToJsonString(new System.Text.Json.JsonSerializerOptions{WriteIndented=true}));Console.WriteLine(report.ToJsonString());
 }
}
