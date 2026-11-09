// Run with the completed example 23 open. Validate all native slice axes/fields.
using System.Text.Json.Nodes;
using Rhino.Geometry;
var asm=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Shared");var hub=asm.GetType("Hawa.Shared.CaseHub");
uint serial=__rhino_doc__.RuntimeSerialNumber;dynamic c=hub.GetMethod("Get").Invoke(null,new object[]{serial});
if((string)c.State!="completed"||c.Result==null)throw new Exception("Complete example 23 first");
string session=(string)c.Session;int phase=0;var checks=new JsonArray();var report=new JsonObject{["state"]="running"};var began=DateTime.UtcNow;var timer=new System.Windows.Forms.Timer{Interval=200};
void Save(string state){report["state"]=state;report["checks"]=checks.DeepClone();System.IO.File.WriteAllText("/Users/r2d2/Desktop/hawa-cfd/results/v05/boundaries/slice-display.json",report.ToJsonString());}
void Set(){var view=(JsonObject)c.View;view["axis"]=phase%3;view["position"]=.57;hub.GetMethod("Edit").Invoke(null,new object[]{serial,new JsonObject{["view"]=view,["field"]=phase<3?"speed":"pressure"},(long)c.Version,"panel",true});began=DateTime.UtcNow;}
timer.Tick+=(_,_)=>{try{
 if((DateTime.UtcNow-began).TotalSeconds>30)throw new Exception("Field query timeout");
 if(c.Result==null)return;if((string)c.Session!=session)throw new Exception("Display restarted solver");
 string before=((JsonObject)c.Slice).ToJsonString();var clock=System.Diagnostics.Stopwatch.StartNew();using var mesh=(Mesh)asm.GetType("Hawa.Shared.CaseGeometry").GetMethod("ResultMesh").Invoke(null,new object[]{c});double elapsed=clock.Elapsed.TotalMilliseconds;
 if(mesh==null||!mesh.IsValid||mesh.Faces.Count==0||mesh.VertexColors.Count!=mesh.Vertices.Count)throw new Exception("Invalid clipped mesh");
 int fractional=0;double error=0;var center=new Point3d(.137,.219,.161);
 foreach(var vertex in mesh.Vertices){var p=(Point3d)vertex;double[] grid={(p.X+1.2)/.1,(p.Y+1.2)/.1,(p.Z+1.2)/.1};if(grid.Any(v=>Math.Abs(v-Math.Round(v))>1e-4)){fractional++;error=Math.Max(error,Math.Abs(p.DistanceTo(center)-.43));}}
 if(fractional<8||error>.003)throw new Exception("Missing or misplaced fractional boundary vertices: "+fractional+" / "+error);
 if(before!=((JsonObject)c.Slice).ToJsonString())throw new Exception("Display changed sampled data");
 checks.Add(new JsonObject{["axis"]=phase%3,["field"]=phase<3?"speed":"pressure",["fractional_vertices"]=fractional,["max_boundary_radial_error_m"]=error,["mesh_build_ms"]=elapsed});phase++;
 if(phase==6){timer.Stop();timer.Dispose();Save("completed");return;}Save("running");Set();
}catch(Exception e){timer.Stop();timer.Dispose();report["error"]=e.GetBaseException().Message;Save("failed");}};
Set();Save("running");timer.Start();Rhino.RhinoApp.WriteLine("Six clipped slice checks queued");
