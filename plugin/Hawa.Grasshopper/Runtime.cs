using System.Reflection;
using System.Text;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using GH_IO.Serialization;

namespace Hawa.Grasshopper;

internal static class JsonCompatibility
{
    public static JsonNode DeepClone(this JsonNode node) => JsonNode.Parse(node.ToJsonString())!;
}

public sealed class HawaInfo : GH_AssemblyInfo
{
    public override string Name => "Hawa";
    public override string Description => "Embedded Python 3.9 GPU LBM. Lettuce numerical engine (MIT); Butterfly workflow reference.";
    public override Guid Id => new("e8e18bc1-cb70-4d66-9969-6fd9ec6d152e");
    public override string AuthorName => "Hawa contributors";
    public override string AuthorContact => "See THIRD_PARTY_NOTICES.md in the package";
    public override System.Drawing.Bitmap? Icon => HawaIcons.Get("Hawa");
}

public sealed class HawaGoo : GH_Goo<string>
{
    public HawaGoo() { Value = "{}"; }
    public HawaGoo(JsonObject value) { Value = value.ToJsonString(); }
    public JsonObject Data => JsonNode.Parse(Value)!.AsObject();
    public override bool IsValid => !string.IsNullOrEmpty(Value);
    public override string TypeName => "Hawa " + (Data["kind"]?.GetValue<string>() ?? "Object");
    public override string TypeDescription => "Hawa case data; numerical state stays in the embedded runtime";
    public override IGH_Goo Duplicate() => new HawaGoo(Data.DeepClone().AsObject());
    public override string ToString() => Data["label"]?.GetValue<string>() ?? TypeName;
    public override bool CastTo<Q>(ref Q target)
    {
        if (typeof(Q) == typeof(string)) { target = (Q)(object)Value; return true; }
        return base.CastTo(ref target);
    }
    public override bool Write(GH_IWriter writer) { writer.SetString("json", Value); return true; }
    public override bool Read(GH_IReader reader) { Value = reader.GetString("json"); return true; }
}

public static class EmbeddedRuntime
{
    private static readonly object Gate = new();
    private static object? script;
    private static MethodInfo? execute;
    private static bool initialized;
    public static string Root => Path.GetDirectoryName(typeof(HawaInfo).Assembly.Location)!;

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
                script = Activator.CreateInstance(type)!;
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

public abstract class HawaComponent : GH_Component
{
    protected HawaComponent(string name, string nick, string description, string group)
        : base(name, nick, description, "Hawa", group) { }
    protected override System.Drawing.Bitmap? Icon => HawaIcons.Get(Name);
    protected static JsonObject ReadObject(IGH_DataAccess da, int index)
    {
        IGH_Goo? goo = null;
        if (!da.GetData(index, ref goo)) throw new ArgumentException("Missing Hawa input");
        if (goo is HawaGoo hawa) return hawa.Data;
        if (goo is GH_ObjectWrapper wrapper && wrapper.Value is HawaGoo nested) return nested.Data;
        if (goo is GH_ObjectWrapper objectWrapper && objectWrapper.Value is string text) return JsonNode.Parse(text)!.AsObject();
        if (goo is GH_String s) return JsonNode.Parse(s.Value)!.AsObject();
        throw new ArgumentException("Connect a compatible Hawa object");
    }
    protected override void SolveInstance(IGH_DataAccess da)
    {
        try { SolveHawa(da); }
        catch (Exception ex) { AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.GetBaseException().Message); }
    }
    protected abstract void SolveHawa(IGH_DataAccess da);
    protected static JsonArray Numbers(IEnumerable<double> values) => new(values.Select(v => JsonValue.Create(v)).ToArray());
    protected static JsonObject Request(string op, string session) => new() { ["op"] = op, ["session"] = session };
}
