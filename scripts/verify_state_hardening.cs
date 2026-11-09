// Run through Rhino MCP in an isolated document. Opens its own unbound GH template.
// Nonblocking timer; no forced quit, sleeps or synchronous solver waits.
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Types;
var root = "/Users/r2d2/Desktop/hawa-cfd";
var hub = AppDomain.CurrentDomain.GetAssemblies().First(a => a.GetName().Name == "Hawa.Shared").GetType("Hawa.Shared.CaseHub");
object Call(string method, params object[] args) => hub.GetMethod(method).Invoke(null, args);
uint serial = __rhino_doc__.RuntimeSerialNumber;
dynamic c = Call("Get", serial);
void Edit(JsonObject patch) => Call("Edit", serial, patch, (long)c.Version, "panel", true);
var io = new GH_DocumentIO();
if (!io.Open(root + "/examples/native-prototype/21-native-live-sync.gh")) throw new Exception("Cannot open template");
var d = io.Document;
Grasshopper.Instances.DocumentServer.AddDocument(d); Grasshopper.Instances.ActiveCanvas.Document = d;
d.NewSolution(false);
var component = d.Objects.OfType<GH_Component>().Single(x => x.Name == "Hawa Linked Case");
var slider = (GH_NumberSlider)component.Params.Input[0].Sources.Single();
var number = new Grasshopper.Kernel.Parameters.Param_Number(); number.CreateAttributes();
var report = new JsonObject { ["rhino"] = Rhino.RhinoApp.Version.ToString(), ["host"] = "macOS Rhino 8 embedded Python" };
var checks = new JsonArray();
var timer = new System.Windows.Forms.Timer { Interval = 200 };
int phase = 0, paused = 0; long version = 0; string session = ""; double size = 0;
DateTime began = DateTime.UtcNow, requested = DateTime.UtcNow;
void Check(bool ok, string message) { if (!ok) throw new Exception(message); }
void Save(string state) { report["state"] = state; report["phase"] = phase; report["checks"] = checks.DeepClone(); System.IO.File.WriteAllText(root + "/results/v05/hardening/rhino.json", report.ToJsonString()); }
void Pass(string message) { checks.Add(message); phase++; began = DateTime.UtcNow; Save("running"); }
void Solve() { component.ExpireSolution(false); d.NewSolution(false); }
timer.Tick += (_, _) => { try {
 if ((DateTime.UtcNow - began).TotalSeconds > 90) throw new Exception("Timeout at " + phase);
 switch (phase) {
 case 0:
  Check(c.BindingOwner != null, "No binding");
  Edit(new() { ["speed"] = 1.23 }); Solve();
  Check((double)c.Speed == 1.23, "Intervening GH solution overwrote panel edit");
  Pass("pending panel pull survives an intervening GH solution"); break;
 case 1:
  if (slider.CurrentValue != 1.23m) return;
  component.Locked = true; Edit(new() { ["speed"] = 1.42 }); component.Locked = false; Solve();
  Pass("locked component retains native change for unlock"); break;
 case 2:
  if (slider.CurrentValue != 1.42m) return;
  Check((double)c.Speed == 1.42, "Unlock overwrote native value");
  d.AddObject(number, false); component.Params.Input[0].RemoveAllSources(); component.Params.Input[0].AddSource(number);
  number.PersistentData.Append(new GH_Number(double.NaN)); number.ExpireSolution(false); Solve();
  Check(c.BindingOwner == null, "NaN retained binding"); Check((double)c.Speed == 1.42, "NaN mutated case");
  Pass("non-finite input releases binding and preserves case"); break;
 case 3:
  number.PersistentData.Clear(); number.PersistentData.Append(new GH_Number(1.1)); number.PersistentData.Append(new GH_Number(1.2)); number.ExpireSolution(false); Solve();
  Check(c.BindingOwner == null, "List retained binding");
  Pass("multi-value input cannot produce several competing edits"); break;
 case 4:
  number.PersistentData.Clear(); number.PersistentData.Append(new GH_Number(1.1)); number.ExpireSolution(false); Solve();
  Check(c.BindingOwner != null && (double)c.Speed == 1.1, "Computed input failed");
  bool rejected = false; try { Edit(new() { ["speed"] = 1.3 }); } catch { rejected = true; }
  Check(rejected, "Panel changed computed input");
  component.Params.Input[0].RemoveAllSources(); component.Params.Input[0].AddSource(slider); d.RemoveObject(number, false); Solve();
  Pass("computed input owns its parameter; panel write rejected"); break;
 case 5:
  version = (long)c.Version; long revision = (long)c.Revision;
  Edit(new() { ["field"] = "pressure", ["target"] = 100000 });
  Check((long)c.Revision == revision && (long)c.Version > version, "Wrong version scope");
  bool stale = false; try { Call("Edit", serial, new JsonObject { ["target"] = 20 }, version, "panel", true); } catch { stale = true; }
  Check(stale, "Stale settings accepted");
  var sw = System.Diagnostics.Stopwatch.StartNew(); Call("Run", serial); report["run_submit_ms"] = sw.Elapsed.TotalMilliseconds;
  Pass("display and target edits are versioned; CPU run submitted"); break;
 case 6:
  if (c.Session == null || (int)c.Steps < 10) return;
  var pause = System.Diagnostics.Stopwatch.StartNew(); Call("Pause", serial); report["pause_submit_ms"] = pause.Elapsed.TotalMilliseconds; requested = DateTime.UtcNow;
  Pass("cooperative pause submitted"); break;
 case 7:
  if ((string)c.State != "paused") return;
  report["pause_observed_ack_ms"] = (DateTime.UtcNow - requested).TotalMilliseconds;
  paused = (int)c.Steps; session = (string)c.Session; Pass("worker acknowledged pause"); break;
 case 8:
  Check((int)c.Steps == paused, "Paused worker advanced");
  Edit(new() { ["target"] = paused + 25 }); Call("Run", serial); Pass("pause held and resume retained run"); break;
 case 9:
  if ((string)c.State != "completed" || c.Result == null || (int)c.Result.Steps != (int)c.Steps) return;
  Check((string)c.Session == session, "Resume replaced session");
  Check((double)c.Result.PhysicalTime > 0 && (string)c.Result.Field == "pressure", "Missing snapshot provenance");
  Solve(); Check(component.Params.Output[1].VolatileDataCount == 1, "Missing current GH mesh");
  var mesh = component.Params.Output[1].VolatileData.AllData(true).OfType<GH_Mesh>().Single().Value;
  size = mesh.GetBoundingBox(false).Diagonal.Length;
  __rhino_doc__.ModelUnitSystem = Rhino.UnitSystem.Meters; Call("Tick"); Solve();
  Pass("CPU completion publishes capture step and physical time"); break;
 case 10:
  Check((string)c.Session == session, "Units restarted simulation");
  var mesh2 = component.Params.Output[1].VolatileData.AllData(true).OfType<GH_Mesh>().Single().Value;
  report["field_size_before_unit_change"] = size; report["field_size_meters"] = mesh2.GetBoundingBox(false).Diagonal.Length;
  Check(Math.Abs(mesh2.GetBoundingBox(false).Diagonal.Length - 10) < .001, "Field units wrong");
  Edit(new() { ["speed"] = 1.37 }); Solve();
  Check((bool)c.Outdated && !component.Params.Output[1].VolatileData.AllData(true).OfType<GH_Mesh>().Any(m => m.Value != null), "Stale field escaped GH");
  Pass("unit change rescales preview; physical edit withholds outdated GH field"); break;
 case 11:
  Edit(new() { ["device"] = "mps", ["target"] = 25 }); Call("Run", serial); Pass("MPS run submitted"); break;
 case 12:
  if ((string)c.State != "completed" || c.Result == null || (int)c.Result.Steps != 25) return;
  report["mps_result"] = c.Describe();
  var cancel = System.Diagnostics.Stopwatch.StartNew(); Call("Cancel", serial); report["cancel_submit_ms"] = cancel.Elapsed.TotalMilliseconds;
  Call("Reset", serial);
  Check(c.Session == null && c.Job == null && c.Slice == null, "Runtime retained after reset");
  Grasshopper.Instances.ActiveCanvas.Document = null; Grasshopper.Instances.DocumentServer.RemoveDocument(d); d.Dispose();
  Check(c.BindingOwner == null, "Closed GH retained lease"); Call("Close", serial);
  Check((int)hub.GetProperty("PendingCleanupCount").GetValue(null) == 0, "Cleanup pending");
  Pass("MPS snapshot verified; cancel/reset/GH close release runtime and binding"); timer.Stop(); timer.Dispose(); Save("completed"); break;
 }
 } catch (Exception e) { timer.Stop(); report["error"] = e.ToString(); Save("failed"); }
};
timer.Start(); Save("running"); Console.WriteLine("Hardening verification queued");
