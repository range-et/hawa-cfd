// Run through Rhino MCP on an isolated empty, unsaved test document after loading
// the candidate assemblies. Never run against a user's working document.
// This checks public panel/state operations, not .3dm archive IO or GH scheduling.
using System.Text.Json.Nodes;
using Eto.Forms;
using Rhino;
var doc = __rhino_doc__;
if (doc != RhinoDoc.ActiveDoc || doc.Modified || !string.IsNullOrEmpty(doc.Path) || doc.Objects.Any())
    throw new Exception("Use an active, empty, unmodified, unsaved test document");
RhinoApp.RunScript("_Hawa", false);
var shared = AppDomain.CurrentDomain.GetAssemblies().Single(a => a.GetName().Name == "Hawa.Shared");
var native = AppDomain.CurrentDomain.GetAssemblies().Single(a => a.GetName().Name == "Hawa.Rhino");
var hub = shared.GetType("Hawa.Shared.CaseHub");
var panelType = native.GetType("Hawa.Native.HawaPanel");
uint serial = doc.RuntimeSerialNumber;
object Call(string name, params object[] args) => hub.GetMethod(name).Invoke(null, args);
void Check(bool value, string message) { if (!value) throw new Exception(message); }
Check(Call("Find", serial) == null, "Hawa command created a case");
for (int i = 0; i < 2; i++) {
    using var panel = (Panel)Activator.CreateInstance(panelType, serial);
    Check(Call("Find", serial) == null && !doc.Modified, "Panel opening created or modified a case");
}
try {
    dynamic original = Call("Get", serial); // explicit creation remains supported
    Call("Edit", serial, new JsonObject { ["speed"] = 1.75 }, (long)original.Version, "panel", false);
    var saved = JsonNode.Parse((string)Call("Save", serial)).AsObject();
    foreach (int schema in new[] { 1, 2 }) {
        Call("Close", serial);
        var settings = JsonNode.Parse(saved.ToJsonString()).AsObject();
        settings["schema"] = schema;
        if (schema == 1) { settings.Remove("setup"); settings.Remove("view"); }
        using var waiting = (Panel)Activator.CreateInstance(panelType, serial);
        Check(Call("Find", serial) == null, "Waiting panel created case");
        Call("Restore", serial, settings.ToJsonString());
        dynamic restored = Call("Find", serial);
        string before = (string)Call("Save", serial);
        var owner = Guid.NewGuid();
        var lease = Call("Bind", restored, owner, new[] { "speed" });
        using var reopened = (Panel)Activator.CreateInstance(panelType, serial);
        Check((string)Call("Save", serial) == before && (Guid)restored.BindingOwner == owner,
            "Reopening overwrote saved settings or binding");
        Check((double)restored.Speed == 1.75 && (string)restored.State == "idle", "Restore lost settings or started work");
        Call("Unbind", restored, owner, lease);
    }
    Console.WriteLine("PASS command, empty/reopened panel, schema 1/2 state restore, binding preservation; zero solver steps");
    Console.WriteLine("Candidate: " + native.Location + " | " + shared.Location);
} finally { Call("Close", serial); }
