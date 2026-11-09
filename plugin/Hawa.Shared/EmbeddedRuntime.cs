using System.Reflection;
using System.Text;
using System.Text.Json.Nodes;
namespace Hawa.Shared;

public static class EmbeddedRuntime
{
    private static readonly object Gate = new();
    private static object? script;
    private static MethodInfo? execute;
    private static bool initialized;
    public static string Root => Path.GetDirectoryName(typeof(EmbeddedRuntime).Assembly.Location)!;

    public static JsonObject Call(JsonObject request)
    {
        lock (Gate)
        {
            if (script == null)
            {
                // Use Rhino's own CPython integration. No Python.NET copy and no subprocess.
                var assembly = AppDomain.CurrentDomain.GetAssemblies().FirstOrDefault(a => a.GetName().Name == "RhinoCodePlatform.Rhino3D")
                    ?? Assembly.Load("RhinoCodePlatform.Rhino3D");
                var type = assembly.GetType("RhinoCodePlatform.Rhino3D.Languages.Python3Script", true)!;
                // The compatibility PythonScript facade does not initialize CPython on a
                // native-only startup. Load the Python language through RhinoCode first.
                var codeAssembly = AppDomain.CurrentDomain.GetAssemblies().FirstOrDefault(a => a.GetType("Rhino.Runtime.Code.RhinoCode") != null) ?? Assembly.Load("Rhino.Runtime.Code");
                var registry = codeAssembly.GetType("Rhino.Runtime.Code.RhinoCode")!.GetProperty("Languages")!.GetValue(null)!;
                var specType = codeAssembly.GetType("Rhino.Runtime.Code.Languages.LanguageSpec")!;
                var spec = specType.GetProperty("Python3")!.GetValue(null)!;
                var reporter = Activator.CreateInstance(assembly.GetType("RhinoCodePlatform.Rhino3D.Languages.RhinoProgressBarLanguageLoadReporter", true)!)!;
                // Rhino's own progress reporter handles first-use runtime loading.
                registry.GetType().GetMethods().First(m => m.Name == "WaitLoadComplete" && m.GetParameters().Length == 2).Invoke(registry, new[] { spec, reporter });
                script = Activator.CreateInstance(type)!;
                type.GetProperty("Output")!.SetValue(script, (Action<string>)(text => Rhino.RhinoApp.WriteLine(text)));
                execute = type.GetMethod("ExecuteScript", new[] { typeof(string) })!;
            }
            if (!initialized)
            {
                var bootstrap = Path.Combine(Root, "Bootstrap.py");
                var directory = Convert.ToBase64String(Encoding.UTF8.GetBytes(Root));
                var code = File.ReadAllText(bootstrap).Replace("# hawa-bootstrap-root", $"import base64\nHAWA_PACKAGE_DIR = base64.b64decode('{directory}').decode()");
                var ok = (bool)execute!.Invoke(script, new object[] { code })!;
                if (!ok) throw new InvalidOperationException("Hawa dependency setup failed. See Rhino script output; a restart may be required after dependency changes.");
                initialized = true;
            }
            var folder = Path.Combine(Path.GetTempPath(), "hawa", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            var reply = Path.Combine(folder, "reply.json");
            var payload = Convert.ToBase64String(Encoding.UTF8.GetBytes(request.ToJsonString()));
            var destination = Convert.ToBase64String(Encoding.UTF8.GetBytes(reply));
            var python = $"import base64, pathlib\nfrom hawa.plugin import dispatch_json\npathlib.Path(base64.b64decode('{destination}').decode()).write_text(dispatch_json(base64.b64decode('{payload}').decode()))";
            try
            {
                var ok = (bool)execute!.Invoke(script, new object[] { python })!;
                if (!ok || !File.Exists(reply)) throw new InvalidOperationException("Embedded Python did not return a result. Check the Rhino script output.");
                var result = JsonNode.Parse(File.ReadAllText(reply))!.AsObject();
                if (result["ok"]?.GetValue<bool>() != true) throw new InvalidOperationException(result["error"]?.GetValue<string>() ?? "Solver error");
                return JsonNode.Parse(result["result"]!.ToJsonString())!.AsObject();
            }
            finally { Directory.Delete(folder, true); }
        }
    }
}

