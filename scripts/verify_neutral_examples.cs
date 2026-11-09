// Run one action per Rhino MCP call; never wait on the GH/UI thread.
// Change action/example in a temporary copy. Source definitions stay idle.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";
var action="report";
var example=28;
var path=System.IO.Directory.GetFiles(root+"/examples/grasshopper",example+"-*.gh").Single();
if(action=="open"){
 var io=new GH_DocumentIO();if(!io.Open(path))throw new Exception("Open failed");var doc=io.Document;
 if(doc.Objects.OfType<GH_BooleanToggle>().Any(t=>t.Value))throw new Exception("Shipped example is not idle");
 doc.FilePath=root+"/results/neutral-precursor/live-example-"+example+".gh";
 Grasshopper.Instances.DocumentServer.AddDocument(doc);Grasshopper.Instances.ActiveCanvas.Document=doc;doc.NewSolution(false);Console.WriteLine("Opened "+doc.DocumentID);
}else{
 var d=Grasshopper.Instances.ActiveCanvas.Document;if(!d.FilePath.Contains("live-example-"+example))throw new Exception("Wrong owned document");
 var components=d.Objects.OfType<GH_Component>().ToArray();var solve=components.Single(c=>c.Name=="Hawa Solve");
 var run=d.Objects.OfType<GH_BooleanToggle>().Single(t=>t.NickName=="Run");
 if(action=="run"||action=="pause"){run.Value=action=="run";run.ExpireSolution(false);d.NewSolution(false);Console.WriteLine(solve.Message);}
 else if(action=="long") {var target=(Param_Integer)solve.Params.Input[2];target.PersistentData.Clear();target.SetPersistentData(100000);target.ExpireSolution(false);run.Value=true;run.ExpireSolution(false);d.NewSolution(false);Console.WriteLine("Started long run for pause/close check");}
 else if(action=="invalid"||action=="repair"){
  var slider=d.Objects.OfType<GH_NumberSlider>().Single(t=>t.NickName=="z0 [m]");
  slider.Slider.Maximum=2;slider.SetSliderValue(action=="invalid"?1m:.01m);slider.ExpireSolution(false);d.NewSolution(false);Console.WriteLine(action);
 }
 else if(action=="reset") {run.Value=false;run.ExpireSolution(false);var reset=d.Objects.OfType<GH_BooleanToggle>().Single(t=>t.NickName=="Reset");reset.Value=true;reset.ExpireSolution(false);d.NewSolution(false);Console.WriteLine(solve.Message);}
 else if(action=="close") {Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();Console.WriteLine("Closed owned example");}
 else if(action=="report"||action=="state"){
  var errors=components.SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(e=>c.Name+": "+e)).ToArray();
  var meshes=components.Single(c=>c.Name=="Hawa Plane Field").Params.Output.SelectMany(p=>p.VolatileData.AllData(true)).OfType<GH_Mesh>().ToArray();
  var report=new JsonObject{["file"]=path,["state"]=solve.Message,["errors"]=new JsonArray(errors.Select(x=>JsonValue.Create(x)).ToArray()),["mesh_faces"]=meshes.Sum(x=>x.Value.Faces.Count),["mesh_valid"]=meshes.Length>0&&meshes.All(x=>x.Value.IsValid)};
  foreach(var c in components.Where(c=>c.Name=="Hawa Solve"||c.Name=="Hawa Result Quality"))report[c.Name]=new JsonArray(c.Params.Output.SelectMany(p=>p.VolatileData.AllData(true)).Select(x=>JsonValue.Create(x.ToString())).ToArray());
  if(action=="report"&&(errors.Length>0||!solve.Message.StartsWith("completed")||meshes.Length==0||meshes.Any(x=>!x.Value.IsValid)))throw new Exception(report.ToJsonString());
  var suffix=action=="report"?"final":"state-"+DateTime.UtcNow.ToString("HHmmss");
  System.IO.File.WriteAllText(root+"/results/neutral-precursor/live-"+example+"-"+suffix+".json",report.ToJsonString());Console.WriteLine(report["state"]+"; errors="+errors.Length+"; mesh faces="+report["mesh_faces"]);
 }
}
