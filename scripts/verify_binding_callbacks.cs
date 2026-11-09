// Run in an isolated Rhino test document with Grasshopper loaded.
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
var root = "/Users/r2d2/Desktop/hawa-cfd";
var hub = AppDomain.CurrentDomain.GetAssemblies().First(a => a.GetName().Name == "Hawa.Shared").GetType("Hawa.Shared.CaseHub");
object Call(string method, params object[] args) => hub.GetMethod(method).Invoke(null, args);
uint serial = __rhino_doc__.RuntimeSerialNumber;
dynamic c = Call("Get", serial);
GH_Document Open() { var io = new GH_DocumentIO(); io.Open(root + "/examples/native-prototype/21-native-live-sync.gh"); Grasshopper.Instances.DocumentServer.AddDocument(io.Document); Grasshopper.Instances.ActiveCanvas.Document = io.Document; io.Document.NewSolution(false); return io.Document; }
var d = Open(); var first = d.Objects.OfType<GH_Component>().Single(); var firstSlider = (GH_NumberSlider)first.Params.Input[0].Sources.Single();
var duplicate = (GH_Component)Activator.CreateInstance(first.GetType()); duplicate.CreateAttributes();
var duplicateSlider = new GH_NumberSlider(); duplicateSlider.CreateAttributes(); duplicateSlider.Slider.Minimum = .1m; duplicateSlider.Slider.Maximum = 3; duplicateSlider.Slider.DecimalPlaces = 2; duplicateSlider.SetSliderValue(1.77m);
d.AddObject(duplicateSlider, false); d.AddObject(duplicate, false); duplicate.Params.Input[0].AddSource(duplicateSlider); d.NewSolution(false);
var report = new JsonObject(); var checks = new JsonArray(); int phase = 0; DateTime began = DateTime.UtcNow;
var timer = new System.Windows.Forms.Timer { Interval = 250 };
void Check(bool ok, string message) { if (!ok) throw new Exception(message); }
void Save(string state) { report["state"] = state; report["phase"] = phase; report["checks"] = checks.DeepClone(); System.IO.File.WriteAllText(root + "/results/v05/hardening/binding-callbacks.json", report.ToJsonString()); }
void Pass(string message) { checks.Add(message); phase++; began = DateTime.UtcNow; Save("running"); }
timer.Tick += (_, _) => { try {
 if ((DateTime.UtcNow - began).TotalSeconds > 30) throw new Exception("Timed out");
 switch (phase) {
 case 0:
  Check((Guid)c.BindingOwner == first.InstanceGuid, "Duplicate took binding");
  Call("Edit", serial, new JsonObject { ["speed"] = 1.25 }, (long)c.Version, "panel", true);
  Pass("native edit queued while duplicate component has no lease"); break;
 case 1:
  if (firstSlider.CurrentValue != 1.25m) return;
  Check(duplicateSlider.CurrentValue == 1.77m, "Losing component's slider was changed");
  Check((Guid)c.BindingOwner == first.InstanceGuid, "Losing callback released winning lease");
  Call("Edit", serial, new JsonObject { ["speed"] = 1.35 }, (long)c.Version, "panel", true);
  var settings = JsonNode.Parse((string)Call("Save", serial))!.AsObject(); settings["id"] = Guid.NewGuid().ToString(); settings["speed"] = 2.2;
  Call("Restore", serial, settings.ToJsonString());
  Pass("duplicate callback leaves its sliders and current owner unchanged"); break;
 case 2:
  Check(firstSlider.CurrentValue == 1.25m && duplicateSlider.CurrentValue == 1.77m, "Replacement case leaked into old sliders");
  Check((double)c.Speed == 2.2 && c.BindingOwner == null, "Old callback changed replacement case");
  Check(first.RuntimeMessages(GH_RuntimeMessageLevel.Error).Count > 0, "Case mismatch was silent");
  Grasshopper.Instances.ActiveCanvas.Document = null; Grasshopper.Instances.DocumentServer.RemoveDocument(d); d.Dispose(); Call("Close", serial);
  Pass("case replacement invalidates queued pull without rewriting old definition"); timer.Stop(); timer.Dispose(); Save("completed"); break;
 }
 } catch (Exception e) { timer.Stop(); report["error"] = e.ToString(); Save("failed"); }
};
timer.Start(); Save("running"); Console.WriteLine("Binding callback checks queued");
