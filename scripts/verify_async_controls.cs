using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using System.Text.Json.Nodes;
using System.Reflection;
var root="/Users/r2d2/Desktop/hawa-cfd";
Grasshopper.Instances.ActiveCanvas.Document=null;foreach(var old in Grasshopper.Instances.DocumentServer.ToArray()){Grasshopper.Instances.DocumentServer.RemoveDocument(old);old.Dispose();}
var io=new GH_DocumentIO();io.Open(root+"/examples/grasshopper/10-responsive-hull-search.gh");var d=io.Document;Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;d.NewSolution(false);
var ev=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Evaluate");var search=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Search");var geo=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Geometry");var run=d.Objects.OfType<GH_BooleanToggle>().First(t=>t.NickName=="Run search");var pause=d.Objects.OfType<GH_BooleanToggle>().First(t=>t.NickName=="Pause");
var report=new JsonObject();var began=DateTime.UtcNow;var timer=new System.Windows.Forms.Timer{Interval=400};int phase=0;string oldJob=null;var jobField=ev.GetType().GetField("job",BindingFlags.NonPublic|BindingFlags.Instance);
long Set(GH_BooleanToggle toggle,bool value){var sw=System.Diagnostics.Stopwatch.StartNew();toggle.Value=value;toggle.ExpireSolution(false);d.NewSolution(false);return sw.ElapsedMilliseconds;}
void Save(string state){report["state"]=state;System.IO.File.WriteAllText(root+"/results/v04/native-controls.json",report.ToJsonString());}
timer.Tick+=(sender,e)=>{try{
 if((DateTime.UtcNow-began).TotalMinutes>5)throw new Exception("Timeout phase "+phase);
 var errors=d.Objects.OfType<GH_Component>().SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error)).ToArray();if(errors.Length>0)throw new Exception(string.Join(";",errors));
 switch(phase){
 case 0:if(geo.Message!="ready")return;report["submit_ms"]=Set(run,true);phase++;break;
 case 1:if(jobField.GetValue(ev)==null)return;report["pause_ms"]=Set(pause,true);phase++;break;
 case 2:if(ev.Message!="paused")return;report["paused"]=true;report["resume_ms"]=Set(pause,false);phase++;break;
 case 3:oldJob=(string)jobField.GetValue(ev);report["cancel_ms"]=Set(run,false);if(jobField.GetValue(ev)!=null)throw new Exception("Cancel retained job");report["cancel_cleared"]=true;phase++;break;
 case 4:report["restart_ms"]=Set(run,true);phase++;break;
 case 5:if(jobField.GetValue(ev)==null)return;var bow=d.Objects.OfType<GH_NumberSlider>().First(s=>s.NickName=="Bow fullness");bow.SetSliderValue(.81m);bow.ExpireSolution(false);d.NewSolution(false);phase++;break;
 case 6:if(search.Message!="completed")return;report["history"]=new JsonArray(search.Params.Output[2].VolatileData.AllData(true).Select(v=>(JsonNode)JsonValue.Create(v.ToString())).ToArray());oldJob=(string)jobField.GetValue(ev);report["input_change_completed"]=true;var before=System.Diagnostics.Stopwatch.StartNew();Grasshopper.Instances.ActiveCanvas.Document=null;Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();report["close_ms"]=before.ElapsedMilliseconds;report["close_cleared_job"]=jobField.GetValue(ev)==null;if(!(bool)report["close_cleared_job"])throw new Exception("Close retained job");timer.Stop();timer.Dispose();Save("completed");return;
 }
 Save("running");
 }catch(Exception ex){timer.Stop();report["error"]=ex.ToString();Save("failed");}};
timer.Start();Console.WriteLine("Async native controls queued");
