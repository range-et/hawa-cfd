using System.Text.Json.Nodes;
namespace Hawa.Shared;

// Persist physical coordinates in metres, independently of Rhino display units.
public static class NativeSettings
{
    public static JsonObject DefaultSetup() => new() {
        ["mode"] = "block", ["curved_walls"] = false, ["objects"] = new JsonArray(),
        ["origin"] = new JsonArray(0d, 0d, 0d), ["size"] = new JsonArray(8d, 6d, 4d),
        ["viscosity"] = .1, ["density"] = 1.225, ["mach"] = .04, ["collision"] = "bgk",
        ["boundaries"] = new JsonArray("inlet", "outlet", "periodic", "periodic", "wall", "slip") };
    public static JsonObject DefaultView() => new() { ["axis"] = 2, ["position"] = .5, ["palette"] = "blue-green",
        ["auto_range"] = true, ["min"] = 0d, ["max"] = 1d, ["domain"] = true, ["body"] = true, ["field"] = true };
    public static Parameter[] Parameters(bool selected) => selected ? new[] {
        new Parameter("speed", "Inlet speed", .001, 300, 1, "m/s"),
        new Parameter("cell", "Cell size", .00001, 100, .01, "m"),
        new Parameter("width", "Block width", .5, 2, 1, "m") } : CaseHub.Parameters.ToArray();
    public static int[] Shape(JsonObject setup, double cell) {
        var shape = setup["size"]!.AsArray().Select(v => Math.Ceiling(v!.GetValue<double>() / cell) + 1).ToArray();
        if (shape.Any(v => !double.IsFinite(v) || v < 4 || v > 2000000) || shape.Aggregate(1d, (a,b) => a*b) > 2000000)
            throw new ArgumentException("Domain needs at least four cells per axis and at most 2,000,000 cells. Adjust cell size or domain.");
        return shape.Select(v => (int)v).ToArray();
    }
    public static void Validate(JsonObject setup, JsonObject view, double cell) {
        if (setup["mode"]?.GetValue<string>() is not ("block" or "selected")) throw new ArgumentException("Choose block or selected geometry");
        foreach (string key in new[] { "origin", "size" }) {
            var a = setup[key]!.AsArray();
            if (a.Count != 3 || a.Any(v => !double.IsFinite(v!.GetValue<double>()) || (key == "size" && v.GetValue<double>() <= 0))) throw new ArgumentException("Domain needs three finite coordinates and positive lengths");
        }
        foreach (string key in new[] { "viscosity", "density", "mach" })
            if (!double.IsFinite(setup[key]!.GetValue<double>()) || setup[key]!.GetValue<double>() <= 0) throw new ArgumentException(key + " must be finite and positive");
        if (setup["mach"]!.GetValue<double>() > .2) throw new ArgumentException("Lattice Mach must be at most 0.2");
        if (!new[] { "bgk", "trt", "regularized", "smagorinsky" }.Contains(setup["collision"]!.GetValue<string>())) throw new ArgumentException("Unsupported collision model");
        _ = setup["curved_walls"]?.GetValue<bool>();
        if ((setup["curved_walls"]?.GetValue<bool>() ?? false) && setup["mode"]!.GetValue<string>() != "selected")
            throw new ArgumentException("Interpolated walls require selected stationary geometry");
        var faces = setup["boundaries"]!.AsArray().Select(v => v!.GetValue<string>()).ToArray();
        if (faces.Length != 6 || faces.Any(v => !new[] { "inlet", "outlet", "wall", "slip", "periodic" }.Contains(v))) throw new ArgumentException("Assign all six domain boundaries");
        if (faces[0] != "inlet" || faces[1] != "outlet" || faces.Skip(2).Any(v => v is "inlet" or "outlet")) throw new ArgumentException("Native wind cases use +X flow: X− inlet and X+ outlet");
        for (int i = 2; i < 6; i += 2) if ((faces[i] == "periodic") != (faces[i+1] == "periodic")) throw new ArgumentException("Periodic faces must be paired");
        var ids = setup["objects"]!.AsArray();
        if (ids.Count > 100 || ids.Any(v => !Guid.TryParse(v?.GetValue<string>(), out var id) || id == Guid.Empty) || ids.Select(v => v!.GetValue<string>()).Distinct().Count() != ids.Count) throw new ArgumentException("Select up to 100 distinct Rhino objects");
        if (setup["mode"]!.GetValue<string>() == "selected") Shape(setup, cell);
        int axis = view["axis"]!.GetValue<int>(); double position = view["position"]!.GetValue<double>();
        if (axis < 0 || axis > 2 || !double.IsFinite(position) || position < 0 || position > 1) throw new ArgumentException("Slice axis 0..2 and position 0..1 required");
        if (setup["mode"]!.GetValue<string>() == "selected") { var shape = Shape(setup, cell); if ((long)shape[(axis+1)%3] * shape[(axis+2)%3] > 65536) throw new ArgumentException("Preview plane exceeds 65,536 samples. Choose another slice axis or increase cell size."); }
        if (!new[] { "blue-green", "spectrum", "diverging" }.Contains(view["palette"]!.GetValue<string>())) throw new ArgumentException("Unknown colour palette");
        double lo = view["min"]!.GetValue<double>(), hi = view["max"]!.GetValue<double>();
        if (!double.IsFinite(lo) || !double.IsFinite(hi) || hi <= lo) throw new ArgumentException("Colour limits must be finite and increasing");
        foreach (string key in new[] { "auto_range", "domain", "body", "field" }) _ = view[key]!.GetValue<bool>();
    }
}
