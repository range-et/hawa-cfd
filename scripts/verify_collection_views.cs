// Owned test document only. One action per call; all expensive queries are async.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Special;
using Rhino.Geometry;
using System.Text.Json.Nodes;
var action="add";var root="/Users/r2d2/Desktop/hawa-cfd";
var d=Grasshopper.Instances.ActiveCanvas.Document;
if(!d.FilePath.EndsWith("live-33-5/owned.gh"))throw new Exception("Wrong document");
if(action=="add"){
 var play=d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Playback").OrderBy(c=>c.Attributes.Pivot.Y).ToArray();var map=d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Color Map").OrderBy(c=>c.Attributes.Pivot.Y).First();
 GH_Component Add(string id,string nick,float x){var c=(GH_Component)Grasshopper.Instances.ComponentServer.EmitObjectProxy(new Guid(id)).CreateInstance();c.CreateAttributes();c.NickName=nick;c.Attributes.Pivot=new System.Drawing.PointF(x,5500);d.AddObject(c,false);foreach(var f in play)c.Params.Input[0].AddSource(f.Params.Output[0]);return c;}
 var flow=Add("a7bb3b0a-ae4f-42ae-9301-a3c55f077129","TEST shared 3D flow",500);flow.Params.Input[2].AddSource(map.Params.Output[0]);var points=(Param_Point)flow.Params.Input[1];points.PersistentData.Clear();foreach(var y in new[]{6d,7d,8d,9d,10d,11d,12d})points.SetPersistentData(new Point3d(1,y,1.5));var n=(Param_Integer)flow.Params.Input[4];n.PersistentData.Clear();n.SetPersistentData(300);
 var iso=Add("a7bb3b0a-ae4f-42ae-9301-a3c55f077124","TEST shared pressure iso",1000);var field=(Param_String)iso.Params.Input[1];field.PersistentData.Clear();field.SetPersistentData("pressure");var level=(Param_Number)iso.Params.Input[2];level.PersistentData.Clear();level.SetPersistentData(-1d);iso.Hidden=true;
 var height=d.Objects.OfType<GH_NumberSlider>().Single(t=>t.NickName=="Shared slice height / m");height.SetSliderValue(1.5m);height.ExpireSolution(false);
 d.NewSolution(false);Console.WriteLine("Submitted multiple-frame consumers");
}else{
 var rows=new JsonArray();
 foreach(var c in d.Objects.OfType<GH_Component>().Where(c=>c.NickName.StartsWith("TEST shared"))){
  var errors=c.RuntimeMessages(GH_RuntimeMessageLevel.Error);var meshes=c.Params.Output.SelectMany(p=>p.VolatileData.AllData(true)).OfType<Grasshopper.Kernel.Types.GH_Mesh>().ToArray();var curves=c.Params.Output.SelectMany(p=>p.VolatileData.AllData(true)).OfType<Grasshopper.Kernel.Types.GH_Curve>().ToArray();
  if(errors.Count>0||meshes.Length==0||meshes.Any(m=>!m.Value.IsValid||m.Value.Faces.Count==0))throw new Exception(c.NickName+": "+string.Join(";",errors));
  rows.Add(new JsonObject{["node"]=c.Name,["state"]=c.Message,["valid_meshes"]=meshes.Length,["curves"]=curves.Length,["faces"]=meshes.Sum(m=>m.Value.Faces.Count)});
 }
 System.IO.File.WriteAllText(root+"/results/atmosphere-nesting/live-33-5/shared-views.json",rows.ToJsonString());Console.WriteLine(rows.ToJsonString());
}
