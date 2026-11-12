using System.Drawing;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;

// Stand-ins for Hawa.Grasshopper types that the linked production sources name
// (type checks in HawaComponent, the archive table, icons) but that this host
// does not link. They are test classes, not production behaviour: unlinked
// components remain unmeasured in the function matrix. Probe subclasses expose
// protected base members so the tests can assert them directly.
namespace Hawa.Grasshopper;

internal static class HawaIcons
{
    public static readonly List<string> Requests = new();
    internal static Bitmap Get(string name) { Requests.Add(name); return new Bitmap(name); }
}

public abstract class StandInComponent : HawaComponent
{
    protected StandInComponent(string name) : base(name, name, "stand-in", "test") { }
    protected virtual int Inputs => 1;
    protected virtual int Outputs => 1;
    protected override void RegisterInputParams(GH_InputParamManager p) { for (int i = 0; i < Inputs; i++) p.AddGenericParameter("In" + i, "I" + i, "", GH_ParamAccess.item); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { for (int i = 0; i < Outputs; i++) p.AddGenericParameter("Out" + i, "O" + i, "", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da) => da.SetData(0, "solved");
}
public sealed class GeometryComponent() : StandInComponent("Geometry") { protected override int Inputs => 3; protected override int Outputs => 3; }
public sealed class EvaluateComponent() : StandInComponent("Evaluate") { protected override int Inputs => 7; protected override int Outputs => 4; }
public sealed class BoundaryPatchComponent() : StandInComponent("BoundaryPatch") { protected override int Inputs => 6; }
public sealed class RefinedSolveComponent() : StandInComponent("RefinedSolve");
public sealed class SearchComponent() : StandInComponent("Search");
public sealed class MovingBodyComponent() : StandInComponent("MovingBody");
public sealed class MotionEvaluateComponent() : StandInComponent("MotionEvaluate");

public abstract class StandInQuery : HawaQueryComponent
{
    protected StandInQuery(string name) : base(name, name, "stand-in", "test") { }
    protected virtual int Inputs => 1;
    protected virtual int Outputs => 1;
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddGenericParameter("Frames", "F", "", GH_ParamAccess.item); for (int i = 1; i < Inputs; i++) p.AddGenericParameter("In" + i, "I" + i, "", GH_ParamAccess.item); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { for (int i = 0; i < Outputs; i++) p.AddGenericParameter("Out" + i, "O" + i, "", GH_ParamAccess.item); }
    // Composing views read their frames through the production FieldTools.
    protected override void SolveHawa(IGH_DataAccess da) => da.SetData(0, FieldTools.Frames(da, 0));
}
public sealed class BoundaryCaptureComponent() : StandInQuery("BoundaryCapture") { protected override int Inputs => 4; protected override int Outputs => 3; }
public sealed class IsosurfaceComponent() : StandInQuery("Isosurface");

public sealed class ProbeComponent() : StandInComponent("Probe")
{
    public static JsonObject Object(IGH_DataAccess da, int index) => ReadObject(da, index);
    public static JsonArray NumberArray(IEnumerable<double> values) => Numbers(values);
    public static JsonObject Operation(string op, string session) => Request(op, session);
    public string Path(string path) => LocalPath(path);
}
public sealed class ProbeQuery() : StandInQuery("ProbeQuery")
{
    public JsonObject? Query(JsonObject request, bool finishPending = false) => View(request, finishPending);
    public void Release() => InputsMissing();
}
