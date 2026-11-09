using System.Text.Json.Nodes;
namespace Hawa.Shared;

public sealed record Parameter(string Key, string Label, double Minimum, double Maximum, double Default, string Unit);
public sealed record ResultStamp(Guid CaseId, long Revision, long Generation, string Session, string Field, int Steps, double PhysicalTime = 0);
public sealed record CaseFault(string Area, string Message, bool Retryable);

// Only CaseHub mutates live state. JSON returned to adapters is a detached copy.
public sealed class CaseState
{
    public uint Document { get; internal init; }
    public Guid Id { get; internal set; } = Guid.NewGuid();
    public long Version { get; internal set; }
    public long Revision { get; internal set; }
    public long Generation { get; internal set; }
    public long ResultVersion { get; internal set; }
    public double Speed { get; internal set; } = 1;
    public double Cell { get; internal set; } = .5;
    public double Width { get; internal set; } = 1;
    public int Target { get; internal set; } = 200;
    public string Device { get; internal set; } = "cpu";
    public string Field { get; internal set; } = "speed";
    internal JsonObject SetupData = NativeSettings.DefaultSetup(), ViewData = NativeSettings.DefaultView();
    public JsonObject Setup => Copy(SetupData)!;
    public JsonObject View => Copy(ViewData)!;
    public bool SelectedGeometry => SetupData["mode"]!.GetValue<string>() == "selected";
    internal Task<JsonObject>? Preparation;
    internal CancellationTokenSource? PreparationCancel;
    public string GeometryError { get; internal set; } = "";
    public string State { get; internal set; } = "idle";
    public string Error { get; internal set; } = "";
    public CaseFault? Fault { get; internal set; }
    public string ViewError { get; internal set; } = "";
    public string? Job { get; internal set; }
    public string? Session { get; internal set; }
    public string? Query { get; internal set; }
    public int Steps { get; internal set; }
    public long RunRevision { get; internal set; } = -1;
    public long ResultRevision => Result?.Revision ?? -1;
    public ResultStamp? Result { get; internal set; }
    public bool StartWhenReady { get; internal set; }
    public bool PauseRequested { get; internal set; }
    internal JsonObject? SpecData, SliceData, StatusData, ResultSpecData;
    public JsonObject? Spec => Copy(SpecData);
    public JsonObject? Slice => Copy(SliceData);
    public JsonObject? Status => Copy(StatusData);
    public JsonObject? ResultSpec => Copy(ResultSpecData);
    internal Rhino.UnitSystem ModelUnits;
    internal int SliceSteps = -1;
    internal int ViewFailures;
    internal ResultStamp? QueryStamp;
    internal DateTime LastQuery;
    internal HashSet<string> DrivenKeys = new();
    public IReadOnlyCollection<string> Driven => Array.AsReadOnly(DrivenKeys.ToArray());
    public Guid? BindingOwner { get; internal set; }
    public Guid? BindingLease { get; internal set; }
    internal Dictionary<string, int> BindingPrecision = new();
    public bool Outdated => Result != null && (Result.CaseId != Id || Result.Revision != Revision || Result.Generation != Generation || Result.Field != Field);
    private static JsonObject? Copy(JsonObject? value) => value?.DeepClone().AsObject();
    public double Value(string key) => key switch { "speed" => Speed, "cell" => Cell, "width" => Width, _ => throw new ArgumentException("Unknown parameter") };
    public JsonObject Settings() => new() { ["schema"] = 2, ["setup"] = Setup, ["view"] = View, ["id"] = Id.ToString(), ["speed"] = Speed, ["cell"] = Cell, ["width"] = Width, ["target"] = Target, ["device"] = Device, ["field"] = Field };
    public JsonObject Describe() => new() {
        ["id"] = Id.ToString(), ["version"] = Version, ["revision"] = Revision, ["generation"] = Generation,
        ["run_revision"] = RunRevision, ["result_revision"] = ResultRevision, ["result_version"] = ResultVersion,
        ["result_steps"] = Result?.Steps, ["result_time_seconds"] = Result?.PhysicalTime, ["result_field"] = Result?.Field, ["state"] = State, ["steps"] = Steps,
        ["session"] = Session, ["job"] = Job, ["error"] = Error, ["view_error"] = ViewError,
        ["geometry_error"] = GeometryError, ["fault_area"] = Fault?.Area, ["retryable"] = Fault?.Retryable,
        ["settings"] = Settings(), ["linked"] = BindingOwner != null, ["outdated"] = Outdated
    };
}
