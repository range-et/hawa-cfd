// Run saved recording/refinement definitions without changing their files.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";
Grasshopper.Instances.ActiveCanvas.Document=null;foreach(var old in Grasshopper.Instances.DocumentServer.ToArray()){Grasshopper.Instances.DocumentServer.RemoveDocument(old);old.Dispose();}
var names=new[]{"13-record-and-playback.gh","15-fixed-refinement.gh","16-cylinder-wake-recording.gh"};
var reports=new JsonArray();int index=0,phase=0;GH_Document doc=null;DateTime began=DateTime.UtcNow;
var timer=new System.Windows.Forms.Timer{Interval=300};
void Save(string state){System.IO.File.WriteAllText(root+"/results/v04/native-recording-examples.json",new JsonObject{["state"]=state,["results"]=reports.DeepClone()}.ToJsonString());}
void Close(){if(doc!=null){Grasshopper.Instances.ActiveCanvas.Document=null;Grasshopper.Instances.DocumentServer.RemoveDocument(doc);doc.Dispose();doc=null;}}
void Open(){Close();if(index==names.Length){timer.Stop();timer.Dispose();Save("completed");return;}var io=new GH_DocumentIO();if(!io.Open(root+"/examples/grasshopper/"+names[index]))throw new Exception("Cannot open definition");doc=io.Document;Grasshopper.Instances.DocumentServer.AddDocument(doc);Grasshopper.Instances.ActiveCanvas.Document=doc;
 var record=doc.Objects.OfType<GH_Component>().FirstOrDefault(c=>c.Name=="Hawa Record");
 if(record!=null){var panel=(GH_Panel)record.Params.Input[1].Sources.Single();panel.UserText=root+"/results/v04/hardening-recording-"+Guid.NewGuid().ToString("N");panel.ExpireSolution(false);}
 phase=0;began=DateTime.UtcNow;doc.NewSolution(false);Save("running");}
timer.Tick+=(sender,e)=>{try{
 if(doc==null)return;
 var cs=doc.Objects.OfType<GH_Component>().ToArray();
 var errors=cs.SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(x=>c.Name+": "+x)).ToArray();if(errors.Length>0)throw new Exception(string.Join(";",errors));
 if((DateTime.UtcNow-began).TotalMinutes>15)throw new Exception("Timeout");
 var solver=cs.First(c=>c.Name=="Hawa Record"||c.Name=="Hawa Refined Solve");
 if(phase==0){if(cs.Any(c=>c.Name=="Hawa Geometry"&&c.Message!="ready"))return;var run=doc.Objects.OfType<GH_BooleanToggle>().First(t=>t.NickName!="Pause");run.Value=true;run.ExpireSolution(false);doc.NewSolution(false);phase=1;return;}
 if(solver.Message!="completed")return;
 var playback=cs.FirstOrDefault(c=>c.Name=="Hawa Playback");
 if(playback!=null&&phase==1){var slider=doc.Objects.OfType<GH_NumberSlider>().First(s=>s.NickName=="Frame");slider.SetSliderValue(slider.Slider.Maximum);slider.ExpireSolution(false);doc.NewSolution(false);phase=2;return;}
 if(playback!=null&&playback.Message!="completed")return;
 var views=cs.Where(c=>c.Name=="Hawa Plane Field"||c.Name=="Hawa Isosurface"||c.Name=="Hawa Flow Display").ToArray();
 if(views.Any(c=>c.Message!="completed"))return;
 if(views.Where(c=>c.Name=="Hawa Plane Field").Any(c=>!c.Params.Output[0].VolatileData.AllData(true).OfType<GH_Mesh>().Any(m=>m.Value.IsValid&&m.Value.Faces.Count>0)))throw new Exception("Invalid plane mesh");
 reports.Add(new JsonObject{["file"]=names[index],["passed"]=true,["seconds"]=(DateTime.UtcNow-began).TotalSeconds,["last_frame"]=playback!=null,["views"]=views.Length});index++;Open();
 }catch(Exception ex){timer.Stop();reports.Add(new JsonObject{["file"]=names[index],["passed"]=false,["error"]=ex.ToString()});Save("failed");}};
Open();timer.Start();Console.WriteLine("Queued three full recording/refinement examples");
