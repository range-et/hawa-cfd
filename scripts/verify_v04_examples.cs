// Nonblocking native graph verification. Read results/v04/native-examples.json for completion.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Types;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";
var files=System.IO.Directory.GetFiles(root+"/examples/grasshopper","*.gh").Where(f=>{int n=int.Parse(System.IO.Path.GetFileName(f).Substring(0,2));return n<=8||n==11||n==12||n==14;}).OrderBy(f=>f).ToArray();
var reports=new JsonArray();int index=0;GH_Document current=null;bool started=false;DateTime began=DateTime.UtcNow;
var timer=new System.Windows.Forms.Timer{Interval=300};
void Save(string state){System.IO.File.WriteAllText(root+"/results/v04/native-examples.json",new JsonObject{["state"]=state,["results"]=JsonNode.Parse(reports.ToJsonString())}.ToJsonString());}
void Close(){if(current!=null){Grasshopper.Instances.ActiveCanvas.Document=null;Grasshopper.Instances.DocumentServer.RemoveDocument(current);current.Dispose();current=null;}}
void Open(){Close();if(index>=files.Length){timer.Stop();timer.Dispose();Save("completed");return;}var io=new GH_DocumentIO();if(!io.Open(files[index]))throw new Exception("Open failed");current=io.Document;current.Enabled=true;Grasshopper.Instances.DocumentServer.AddDocument(current);Grasshopper.Instances.ActiveCanvas.Document=current;foreach(var s in current.Objects.OfType<GH_NumberSlider>().Where(s=>s.NickName=="Target iterations"))s.SetSliderValue(25);started=false;began=DateTime.UtcNow;current.NewSolution(false);Save("running");}
timer.Tick+=(sender,e)=>{try{
 if(current==null)return;
 var components=current.Objects.OfType<GH_Component>().ToArray();
 var errors=components.SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(x=>c.Name+": "+x)).ToArray();
 if(errors.Length>0)throw new Exception(string.Join(";",errors));
 if((DateTime.UtcNow-began).TotalSeconds>120)throw new Exception("Timeout: "+string.Join(";",components.Select(c=>c.Name+"="+c.Message)));
 var solve=components.FirstOrDefault(c=>c.Name=="Hawa Solve");
 if(solve!=null){
  if(!started&&solve.Params.Output[0].VolatileDataCount>0){var run=current.Objects.OfType<GH_BooleanToggle>().First(t=>t.NickName=="Run / Pause");run.Value=true;run.ExpireSolution(false);started=true;current.NewSolution(false);return;}
  if(solve.Message!="completed")return;
  var view=components.FirstOrDefault(c=>c.Name=="Hawa Slice")??components.First(c=>c.Name=="Hawa Plane Field");
  var mesh=view.Params.Output[0].VolatileData.AllData(true).OfType<GH_Mesh>().FirstOrDefault()?.Value;
  if(mesh==null)return;if(!mesh.IsValid||mesh.Faces.Count==0)throw new Exception("Invalid field mesh");
  if(components.Any(c=>c.Name=="Hawa Flow Display"&&c.Message!="completed"))return;
  reports.Add(new JsonObject{["file"]=System.IO.Path.GetFileName(files[index]),["passed"]=true,["steps"]=25,["faces"]=mesh.Faces.Count});
 }else{
  var wing=components.First(c=>c.Name=="Hawa Wing");var mesh=wing.Params.Output[0].VolatileData.AllData(true).OfType<GH_Mesh>().FirstOrDefault()?.Value;
  if(mesh==null||!mesh.IsValid||!mesh.IsClosed)throw new Exception("Invalid wing mesh");
  var polar=components.First(c=>c.Name=="Hawa Polar Data");if(polar.Params.Output[6].VolatileDataCount==0)throw new Exception("Missing moment coefficient");
  reports.Add(new JsonObject{["file"]=System.IO.Path.GetFileName(files[index]),["passed"]=true,["wing_closed"]=true,["local_polar"]=true});
 }
 index++;Open();
}catch(Exception ex){reports.Add(new JsonObject{["file"]=System.IO.Path.GetFileName(files[index]),["passed"]=false,["error"]=ex.Message});timer.Stop();Save("failed");}};
Open();timer.Start();Console.WriteLine("Queued "+files.Length+" graph checks");
