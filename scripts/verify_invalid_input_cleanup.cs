// Start a solver, invalidate its input, then check worker and registry cleanup.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using System.Reflection;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";
var io=new GH_DocumentIO();if(!io.Open(root+"/examples/grasshopper/01-tgv3d-bgk.gh"))throw new Exception("Cannot open example");
var d=io.Document;Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;
var solve=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Solve");var run=d.Objects.OfType<GH_BooleanToggle>().First(t=>t.NickName=="Run / Pause");
var count=(Param_Integer)solve.Params.Input[2];count.RemoveAllSources();count.PersistentData.Clear();count.SetPersistentData(100000);
d.NewSolution(false);int phase=0;DateTime began=DateTime.UtcNow;var timer=new System.Windows.Forms.Timer{Interval=300};
timer.Tick+=(sender,e)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>60)throw new Exception("Timeout");
 if(phase==0){if(solve.Params.Output[0].VolatileDataCount==0)return;run.Value=true;run.ExpireSolution(false);d.NewSolution(false);phase=1;return;}
 if(phase==1){if(solve.Message!="running")return;count.PersistentData.Clear();count.SetPersistentData(-1);count.ExpireSolution(false);d.NewSolution(false);phase=2;return;}
 var flags=BindingFlags.NonPublic|BindingFlags.Instance;
 if(solve.GetType().GetField("session",flags).GetValue(solve)!=null||solve.GetType().GetField("creation",flags).GetValue(solve)!=null)throw new Exception("Invalid input retained solver ownership");
 if(!solve.RuntimeMessages(GH_RuntimeMessageLevel.Error).Any())throw new Exception("Missing input diagnostic");
 Grasshopper.Instances.ActiveCanvas.Document=null;Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();
 var runtime=solve.GetType().Assembly.GetType("Hawa.Grasshopper.EmbeddedRuntime");var staticFlags=BindingFlags.NonPublic|BindingFlags.Static;
 var script=runtime.GetField("script",staticFlags).GetValue(null);var execute=(MethodInfo)runtime.GetField("execute",staticFlags).GetValue(null);
 string code="import json, threading\nfrom hawa.jobs import JOBS\nfrom hawa.plugin import SESSIONS\nfrom pathlib import Path\nPath('"+root+"/results/v04/native-invalid-input.json').write_text(json.dumps(dict(passed=not JOBS and not SESSIONS and not any(t.name.startswith('Hawa ') for t in threading.enumerate()), jobs=len(JOBS), sessions=len(SESSIONS), workers=[t.name for t in threading.enumerate() if t.name.startswith('Hawa ')])))";
 execute.Invoke(script,new object[]{code});timer.Stop();timer.Dispose();
 }catch(Exception ex){timer.Stop();System.IO.File.WriteAllText(root+"/results/v04/native-invalid-input.json",new JsonObject{["passed"]=false,["error"]=ex.ToString()}.ToJsonString());}};
timer.Start();Console.WriteLine("Invalid-input cleanup check queued");
