using System.Reflection;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Types;
var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
var bridge=assembly.GetType("Hawa.Grasshopper.EmbeddedRuntime");
JsonObject Call(JsonObject r)=>(JsonObject)bridge.GetMethod("Call").Invoke(null,new object[]{r});
var results=new JsonArray();
foreach(var file in System.IO.Directory.GetFiles("/Users/r2d2/Desktop/hawa-cfd/examples/grasshopper","*.gh").OrderBy(x=>x)) {
 var io=new GH_DocumentIO();if(!io.Open(file))throw new Exception("Cannot open "+file);var d=io.Document; string session=null;
 try {
 Console.WriteLine("Checking "+file); d.Enabled=true;
 var solver=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Solve");
 var toggle=d.Objects.OfType<GH_BooleanToggle>().First(t=>t.NickName=="Run / Pause");
 var target=d.Objects.OfType<GH_NumberSlider>().First(t=>t.NickName=="Target iterations");target.SetSliderValue(25);
 var backend=d.Objects.OfType<GH_ValueList>().First(t=>t.NickName=="Backend");foreach(var item in backend.ListItems)item.Selected=item.Name=="mps";
 d.NewSolution(false); foreach(var c in d.Objects.OfType<GH_Component>()) { var err=c.RuntimeMessages(GH_RuntimeMessageLevel.Error); if(err.Count>0)Console.WriteLine(c.Name+": "+string.Join(";",err)); } var goo=solver.Params.Output[0].VolatileData.AllData(true).First();
 var value=(string)goo.GetType().GetProperty("Value").GetValue(goo);session=JsonNode.Parse(value)["session"].GetValue<string>();
 toggle.Value=true;toggle.ExpireSolution(false);d.NewSolution(false);
 var timer=System.Diagnostics.Stopwatch.StartNew();JsonObject status;
 do {System.Threading.Thread.Sleep(20);status=Call(new JsonObject{["op"]="status",["session"]=session});}while(status["state"].GetValue<string>()=="running" && timer.ElapsedMilliseconds<20000);
 solver.ExpireSolution(false);d.NewSolution(false);
 var errors=d.Objects.OfType<GH_Component>().SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(m=>c.Name+": "+m)).ToArray();
 var slice=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Slice");var mesh=((GH_Mesh)slice.Params.Output[0].VolatileData.AllData(true).First()).Value;
 if(errors.Length>0||status["steps"].GetValue<int>()!=25||!mesh.IsValid)throw new Exception(System.IO.Path.GetFileName(file)+": "+string.Join(";",errors)+" / "+status);
 results.Add(new JsonObject{["file"]=System.IO.Path.GetFileName(file),["passed"]=true,["steps"]=25,["vertices"]=mesh.Vertices.Count,["faces"]=mesh.Faces.Count,["backend"]=status["backend"]["selected"].GetValue<string>()});
 }catch(Exception ex) { throw new Exception(System.IO.Path.GetFileName(file)+" / "+string.Join(";",d.Objects.OfType<GH_Component>().SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(m=>c.Name+": "+m)))+" / "+ex.Message); }finally {if(session!=null)Call(new JsonObject{["op"]="close",["session"]=session});d.Enabled=false;d.Dispose();}
}
var report=new JsonObject{["passed"]=true,["definitions"]=results};
System.IO.Directory.CreateDirectory("/Users/r2d2/Desktop/hawa-cfd/results/plugin");System.IO.File.WriteAllText("/Users/r2d2/Desktop/hawa-cfd/results/plugin/definitions.json",report.ToJsonString());Console.WriteLine(report.ToJsonString());
