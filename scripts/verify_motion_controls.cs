using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using System.Reflection;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";
Grasshopper.Instances.ActiveCanvas.Document=null;foreach(var old in Grasshopper.Instances.DocumentServer.ToArray()){Grasshopper.Instances.DocumentServer.RemoveDocument(old);old.Dispose();}
var io=new GH_DocumentIO();io.Open(root+"/examples/grasshopper/20-motion-cycle-search.gh");var d=io.Document;Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;
var motion=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Oscillation");var eval=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Motion Evaluate");var search=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Search");var body=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Moving Body");
var amp=d.Objects.OfType<GH_NumberSlider>().First(s=>s.NickName=="Travel amplitude (m)");amp.Slider.Minimum=.005m;amp.Slider.Maximum=.02m;amp.SetSliderValue(.01m);
void Number(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);p.ExpireSolution(false);}
Number(motion,2,0);Number(motion,3,5);Number(eval,1,.2);var budget=(Param_Integer)search.Params.Input[5];budget.PersistentData.Clear();budget.SetPersistentData(2);budget.ExpireSolution(false);
var run=d.Objects.OfType<GH_BooleanToggle>().First(t=>t.NickName=="Run search");var pause=d.Objects.OfType<GH_BooleanToggle>().First(t=>t.NickName=="Pause search");
var report=new JsonObject();int phase=0;DateTime began=DateTime.UtcNow;var timer=new System.Windows.Forms.Timer{Interval=300};var jobField=eval.GetType().GetField("job",BindingFlags.Instance|BindingFlags.NonPublic);
long Set(GH_BooleanToggle t,bool v){var sw=System.Diagnostics.Stopwatch.StartNew();t.Value=v;t.ExpireSolution(false);d.NewSolution(false);return sw.ElapsedMilliseconds;}
void Save(string s){report["state"]=s;System.IO.File.WriteAllText(root+"/results/motion/native-controls.json",report.ToJsonString());}
d.NewSolution(false);timer.Tick+=(sender,e)=>{try{
 if((DateTime.UtcNow-began).TotalMinutes>10)throw new Exception("Timeout phase "+phase);
 var errors=d.Objects.OfType<GH_Component>().SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(x=>c.Name+": "+x)).ToArray();if(errors.Length>0)throw new Exception(string.Join(";",errors));
 switch(phase){
 case 0:if(body.Message!="ready")return;report["submit_ms"]=Set(run,true);phase++;break;
 case 1:if(jobField.GetValue(eval)==null)return;report["pause_ms"]=Set(pause,true);phase++;break;
 case 2:if(eval.Message!="paused")return;report["paused"]=true;report["resume_ms"]=Set(pause,false);phase++;break;
 case 3:report["cancel_ms"]=Set(run,false);if(jobField.GetValue(eval)!=null)throw new Exception("Cancel retained job");phase++;break;
 case 4:report["restart_ms"]=Set(run,true);phase++;break;
 case 5:if(search.Message!="completed")return;report["history"]=new JsonArray(search.Params.Output[2].VolatileData.AllData(true).Select(v=>(JsonNode)JsonValue.Create(v.ToString())).ToArray());var sw=System.Diagnostics.Stopwatch.StartNew();Grasshopper.Instances.ActiveCanvas.Document=null;Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();report["close_ms"]=sw.ElapsedMilliseconds;report["close_cleared"]=jobField.GetValue(eval)==null;phase++;break;
 case 6:var rt=eval.GetType().Assembly.GetType("Hawa.Grasshopper.EmbeddedRuntime");var flags=BindingFlags.NonPublic|BindingFlags.Static;var script=rt.GetField("script",flags).GetValue(null);var execute=(MethodInfo)rt.GetField("execute",flags).GetValue(null);string code="import json, threading\nfrom hawa.jobs import JOBS\nfrom hawa.plugin import SESSIONS\nfrom pathlib import Path\nPath('"+root+"/results/motion/native-cleanup.json').write_text(json.dumps(dict(jobs=len(JOBS),sessions=len(SESSIONS),workers=[t.name for t in threading.enumerate() if t.name.startswith('Hawa ')])))";execute.Invoke(script,new object[]{code});timer.Stop();timer.Dispose();Save("completed");return;
 }
 Save("running");
 }catch(Exception ex){timer.Stop();report["error"]=ex.ToString();Save("failed");}};timer.Start();Console.WriteLine("Motion controls and two-candidate cycle search queued");
