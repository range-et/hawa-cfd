using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Types;
using Grasshopper.Kernel.Parameters;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";var files=System.IO.Directory.GetFiles(root+"/examples/grasshopper","*.gh").Where(f=>int.Parse(System.IO.Path.GetFileName(f).Substring(0,2))>=17&&int.Parse(System.IO.Path.GetFileName(f).Substring(0,2))<=19).OrderBy(f=>f).ToArray();
var reports=new JsonArray();int index=0;GH_Document d=null;bool started=false;DateTime began=DateTime.UtcNow;var timer=new System.Windows.Forms.Timer{Interval=300};
void Save(string state){System.IO.File.WriteAllText(root+"/results/motion/native-examples.json",new JsonObject{["state"]=state,["results"]=JsonNode.Parse(reports.ToJsonString())}.ToJsonString());}
void Close(){if(d!=null){Grasshopper.Instances.ActiveCanvas.Document=null;Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();d=null;}}
void Open(){Close();if(index==files.Length){timer.Stop();timer.Dispose();Save("completed");return;}var io=new GH_DocumentIO();if(!io.Open(files[index]))throw new Exception("Cannot open motion example");d=io.Document;var target=(Param_Integer)d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Solve").Params.Input[2];target.PersistentData.Clear();target.SetPersistentData(80);target.ExpireSolution(false);Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;started=false;began=DateTime.UtcNow;d.NewSolution(false);Save("running");}
timer.Tick+=(sender,e)=>{try{
 if(d==null)return;var cs=d.Objects.OfType<GH_Component>().ToArray();var errors=cs.SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(x=>c.Name+": "+x)).ToArray();if(errors.Length>0)throw new Exception(string.Join(";",errors));if((DateTime.UtcNow-began).TotalMinutes>10)throw new Exception("Timeout");
 var solve=cs.First(c=>c.Name=="Hawa Solve");if(!started){if(solve.Params.Output[0].VolatileDataCount==0)return;var run=d.Objects.OfType<GH_BooleanToggle>().First(t=>t.NickName=="Run / Pause");run.Value=true;run.ExpireSolution(false);d.NewSolution(false);started=true;return;}
 if(solve.Message!="completed")return;var plane=cs.First(c=>c.Name=="Hawa Plane Field");var loads=cs.First(c=>c.Name=="Hawa Body Loads");var body=cs.First(c=>c.Name=="Hawa Body Preview");if(plane.Message!="completed"||(loads.Message!="completed"&&loads.Message!="snapshot")||body.Params.Output[0].VolatileDataCount==0)return;
 var mesh=body.Params.Output[0].VolatileData.AllData(true).OfType<GH_Mesh>().First().Value;if(!mesh.IsValid||!mesh.IsClosed)throw new Exception("Moved body mesh is invalid");
 var frame=plane.Params.Output[0].VolatileData.AllData(true).OfType<GH_Mesh>().FirstOrDefault()?.Value;if(frame==null)return;if(!frame.IsValid||frame.Faces.Count==0)throw new Exception("Missing field mesh");
 reports.Add(new JsonObject{["file"]=System.IO.Path.GetFileName(files[index]),["passed"]=true,["steps"]=80,["seconds"]=(DateTime.UtcNow-began).TotalSeconds,["field_faces"]=frame.Faces.Count,["body_closed"]=true,["force"]=string.Join(";",loads.Params.Output[0].VolatileData.AllData(true))});index++;Open();
 }catch(Exception ex){timer.Stop();reports.Add(new JsonObject{["file"]=System.IO.Path.GetFileName(files[index]),["passed"]=false,["error"]=ex.ToString()});Save("failed");}};
Open();timer.Start();Console.WriteLine("Queued "+files.Length+" motion examples");
