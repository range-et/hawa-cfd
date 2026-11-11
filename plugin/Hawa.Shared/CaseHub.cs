using System.Text.Json.Nodes;
using Rhino;

namespace Hawa.Shared;
// Single UI-thread writer. Adapters submit commands; Python owns numerical work.
public static class CaseHub
{
    public static IReadOnlyList<Parameter> Parameters { get; } = Array.AsReadOnly(new[] { new Parameter("speed", "Inlet speed", .1, 3, 1, "m/s"), new Parameter("cell", "Cell size", .25, 1, .5, "m"), new Parameter("width", "Block width", .5, 2, 1, "m") });

    private static readonly Dictionary<uint, CaseState> Cases = new();
    private static readonly HashSet<uint> Closing = new();
    private static readonly HashSet<uint> PendingClose = new();
    private static readonly HashSet<CaseState> Busy = new();
    private static readonly HashSet<(uint Document, Guid Object)> PendingGeometry = new();
    private static readonly Dictionary<string, JsonObject> Cleanup = new();
    private static readonly Queue<string> CleanupOrder = new();
    private static DateTime cleanupAttempt;
    private static bool polling, cleaning, cleanupSubscribed;
    internal static Func<JsonObject, JsonObject> Transport = EmbeddedRuntime.Call;
    public static Func<CaseState, CancellationToken, Task<JsonObject>>? PrepareGeometry { get; set; }

    public static event Action<CaseState, string>? Changed;
    public static int PendingCleanupCount => Cleanup.Count;
    public static IEnumerable<CaseState> All => Cases.Values.ToArray();

    private static void UI()
    {
        if (RhinoApp.InvokeRequired)
            throw new InvalidOperationException("Hawa commands must run on Rhino's UI thread");
    }

    public static CaseState Get(uint document)
    {
        UI();
        if (Closing.Contains(document) || RhinoDoc.FromRuntimeSerialNumber(document) == null)
            throw new InvalidOperationException("Rhino document is closed");
        if (!Cases.TryGetValue(document, out var c))
        {
            Cases[document] = c = new()
            {
                Document = document,
                ModelUnits = RhinoDoc.FromRuntimeSerialNumber(document)!.ModelUnitSystem
            };
            Notify(c, "created");
        }

        return c;
    }

    public static CaseState? Find(uint document) => Cases.GetValueOrDefault(document);
    private static void Current(CaseState c)
    {
        UI();
        if (!ReferenceEquals(Find(c.Document), c))
            throw new InvalidOperationException("Case has been replaced or closed");
    }

    private static void Change(CaseState c, Action action)
    {
        Current(c);
        if (!Busy.Add(c))
            throw new InvalidOperationException("Case is applying another command; refresh and retry");
        try
        {
            action();
        }
        finally
        {
            Busy.Remove(c);
            Drain(c);
        }
    }

    private static void Drain(CaseState c)
    {
        if (PendingClose.Remove(c.Document))
            Close(c.Document);
        foreach (var item in PendingGeometry.Where(v =>
            v.Document == c.Document
        ).ToArray())
        {
            PendingGeometry.Remove(item);
            GeometryChanged(item.Document, item.Object);
        }
    }

    private static void Notify(CaseState c, string origin)
    {
        if (origin != "closed" && Find(c.Document) != c)
            return;
        // Views cannot turn a committed change into a solver failure or interrupt undo.
        bool added = Busy.Add(c);
        try
        {
            foreach (var handler in Changed?.GetInvocationList() ?? Array.Empty<Delegate>())
                try
                {
                    ((Action<CaseState, string>)handler)(c, origin);
                }
                catch (Exception e)
                {
                    RhinoApp.WriteLine("Hawa view update failed: " + e.GetBaseException().Message);
                }
        }
        finally
        {
            if (added)
            {
                Busy.Remove(c);
                Drain(c);
            }
        }
    }

    public static Guid Bind(CaseState c, Guid owner, IEnumerable<string> driven)
    {
        bool changed = false;
        Change(c, () =>
        {
            if (owner == Guid.Empty)
                throw new ArgumentException("Binding requires a component identity");
            if (c.BindingOwner != null && c.BindingOwner != owner)
                throw new InvalidOperationException("This case already has a live Grasshopper binding");
            var keys = new HashSet<string>(driven);
            if (keys.Any(k =>
                !Parameters.Any(p =>
                p.Key == k
            )
            ))
                throw new ArgumentException("Unknown driven parameter");
            changed = c.BindingOwner != owner || !c.DrivenKeys.SetEquals(keys);
            if (c.BindingOwner != owner)
            {
                c.BindingLease = Guid.NewGuid();
                c.BindingPrecision.Clear();
            }

            c.BindingOwner = owner;
            c.DrivenKeys = keys;
        });
        if (changed)
            Notify(c, "binding");
        return c.BindingLease!.Value;
    }

    public static void ConfigureBinding(CaseState c, Guid owner, Guid lease, IReadOnlyDictionary<string, int> precision)
    {
        Change(c, () =>
        {
            if (c.BindingOwner != owner || c.BindingLease != lease)
                throw new InvalidOperationException("Binding expired");
            if (precision.Any(p =>
                !Parameters.Any(k =>
                k.Key == p.Key
            ) || p.Value < 0 || p.Value > 12
            ))
                throw new ArgumentException("Invalid slider precision");
            c.BindingPrecision = precision.ToDictionary(p =>
                p.Key
            , p =>
                p.Value
            );
        });
    }

    public static void Unbind(CaseState c, Guid owner, Guid lease)
    {
        if (Find(c.Document) != c || c.BindingOwner != owner || c.BindingLease != lease)
            return;
        Change(c, () =>
        {
            c.BindingOwner = null;
            c.BindingLease = null;
            c.BindingPrecision.Clear();
            c.DrivenKeys.Clear();
        });
        Notify(c, "binding");
    }

    // Version covers every setting edit; Revision covers only physical changes.
    public static void Edit(uint document, JsonObject values, long expectedVersion, string origin = "panel", bool undo = true)
    {
        if (origin != "panel")
            throw new ArgumentException("Use EditFromBinding for a Grasshopper writer");
        EditCore(Get(document), values, expectedVersion, null, origin, undo);
    }

    public static void EditFromBinding(uint document, Guid caseId, Guid owner, Guid lease, JsonObject values, long expectedVersion)
    {
        var c = Get(document);
        if (caseId != c.Id || c.BindingOwner != owner || c.BindingLease != lease)
            throw new InvalidOperationException("Grasshopper binding is stale; reconnect before editing");
        EditCore(c, values, expectedVersion, owner, owner.ToString(), true);
    }

    private static void EditCore(CaseState c, JsonObject values, long expectedVersion, Guid? owner, string origin, bool undo)
    {
        bool changed = false;
        Change(c, () =>
        {
            if (c.Version != expectedVersion)
                throw new InvalidOperationException("Case changed; refresh before applying this edit");
            var next = c.Settings();
            foreach (var pair in values)
            {
                if (!new[]
                {
                    "speed",
                    "cell",
                    "width",
                    "target",
                    "device",
                    "field",
                    "setup",
                    "view"
                }.Contains(pair.Key))
                    throw new ArgumentException("Unknown setting: " + pair.Key);
                if (owner == null && c.DrivenKeys.Contains(pair.Key))
                    throw new InvalidOperationException(pair.Key + " is driven by Grasshopper");
                next[pair.Key] = pair.Value?.DeepClone();
            }

            next = JsonNode.Parse(next.ToJsonString())!.AsObject();
            Validate(next);
            if (owner == null)
                foreach (var p in c.BindingPrecision)
                {
                    double value = next[p.Key]!.GetValue<double>();
                    if (Math.Abs(value - Math.Round(value, p.Value)) > 1e-9)
                        throw new ArgumentException($"{p.Key}: linked slider supports {p.Value} decimal places");
                }

            if (next.ToJsonString() == c.Settings().ToJsonString())
                return;
            var doc = RhinoDoc.FromRuntimeSerialNumber(c.Document)!;
            string before = c.Settings().ToJsonString();
            uint record = undo ? doc.BeginUndoRecord("Hawa case edit") : 0;
            try
            {
                if (undo)
                    RegisterUndo(doc, c, before);
                Apply(c, next);
                doc.Modified = true;
                changed = true;
            }
            finally
            {
                if (record != 0)
                    doc.EndUndoRecord(record);
            }
        });
        if (changed)
            Notify(c, origin);
    }

    private static void RegisterUndo(RhinoDoc doc, CaseState expected, string settings)
    {
        var id = expected.Id;
        doc.AddCustomUndoEvent("Hawa case edit", (_, e) =>
        {
            var c = Find(e.Document.RuntimeSerialNumber);
            if (c != expected || c.Id != id)
                return; // An old undo record cannot resurrect a case.
            Change(c, () =>
            {
                RegisterUndo(e.Document, c, c.Settings().ToJsonString());
                Apply(c, JsonNode.Parse(settings)!.AsObject());
            });
            Notify(c, "undo");
        });
    }

    public static void Validate(JsonObject settings)
    {
        if (settings["schema"]?.GetValue<int>()is not (1 or 2) || !Guid.TryParse(settings["id"]?.GetValue<string>(), out var id) || id == Guid.Empty)
            throw new ArgumentException("Unsupported case schema or ID");
        var setup = settings["setup"]?.AsObject() ?? NativeSettings.DefaultSetup();
        var view = settings["view"]?.AsObject() ?? NativeSettings.DefaultView();
        foreach (var p in NativeSettings.Parameters(setup["mode"]?.GetValue<string>() == "selected"))
        {
            double value = settings[p.Key]?.GetValue<double>() ?? double.NaN;
            if (!double.IsFinite(value) || value < p.Minimum || value > p.Maximum)
                throw new ArgumentException($"{p.Label}: {p.Minimum}..{p.Maximum} {p.Unit}");
        }

        NativeSettings.Validate(setup, view, settings["cell"]!.GetValue<double>());
        int target = settings["target"]?.GetValue<int>() ?? 0;
        if (target < 1 || target > 100000)
            throw new ArgumentException("Target steps: 1..100000");
        if (!new[]
        {
            "cpu",
            "mps",
            "auto",
            "cuda:0"
        }.Contains(settings["device"]?.GetValue<string>()))
            throw new ArgumentException("Unknown backend");
        if (!new[]
        {
            "speed",
            "pressure",
            "density"
        }.Contains(settings["field"]?.GetValue<string>()))
            throw new ArgumentException("Unknown field");
    }

    private static void Apply(CaseState c, JsonObject n)
    {
        var setup = n["setup"]?.DeepClone().AsObject() ?? NativeSettings.DefaultSetup();
        var view = n["view"]?.DeepClone().AsObject() ?? NativeSettings.DefaultView();
        bool physical = c.SetupData.ToJsonString() != setup.ToJsonString() || c.Speed != n["speed"]!.GetValue<double>() || c.Cell != n["cell"]!.GetValue<double>() || c.Width != n["width"]!.GetValue<double>() || c.Device != n["device"]!.GetValue<string>();
        bool display = c.Field != n["field"]!.GetValue<string>() || c.ViewData["axis"]!.ToJsonString() != view["axis"]!.ToJsonString() || c.ViewData["position"]!.ToJsonString() != view["position"]!.ToJsonString();
        bool recolor = c.ViewData.ToJsonString() != view.ToJsonString();
        if (physical)
        {
            Stop(c);
            c.Revision++;
            c.State = c.SliceData == null ? "idle" : "outdated";
        }

        c.Id = Guid.Parse(n["id"]!.GetValue<string>());
        c.Speed = n["speed"]!.GetValue<double>();
        c.Cell = n["cell"]!.GetValue<double>();
        c.Width = n["width"]!.GetValue<double>();
        c.Target = n["target"]!.GetValue<int>();
        c.Device = n["device"]!.GetValue<string>();
        c.Field = n["field"]!.GetValue<string>();
        c.SetupData = setup;
        c.ViewData = view;
        if (recolor)
            c.ResultVersion++;
        c.Version++;
        c.Error = c.GeometryError = "";
        c.Fault = null;
        if (display)
        {
            CloseQuery(c);
            ClearResult(c);
            c.ViewError = "";
            c.ViewFailures = 0;
            c.LastQuery = DateTime.MinValue;
        }
    }

    public static string Save(uint doc) => Get(doc).Settings().ToJsonString();
    public static void Restore(uint doc, string settings)
    {
        var data = JsonNode.Parse(settings)!.AsObject();
        Validate(data);
        var c = Get(doc);
        Change(c, () =>
        {
            Stop(c);
            if (c.Id != Guid.Parse(data["id"]!.GetValue<string>()))
            {
                c.BindingOwner = null;
                c.BindingLease = null;
                c.BindingPrecision.Clear();
                c.DrivenKeys.Clear();
            }

            Apply(c, data);
            ClearResult(c);
            c.SpecData = null;
            c.Steps = 0;
            c.RunRevision = -1;
            c.State = "idle";
        });
        Notify(c, "restore"); // Publish exactly one coherent, idle snapshot.
    }

    private static void ClearResult(CaseState c)
    {
        c.SliceData = c.ResultSpecData = null;
        c.Result = null;
        c.SliceSteps = -1;
        c.ResultVersion++;
    }

    public static JsonObject BuildSpec(CaseState c)
    {
        if (c.SelectedGeometry)
        {
            var shape = NativeSettings.Shape(c.SetupData, c.Cell);
            double units = RhinoMath.UnitScale(UnitSystem.Meters, RhinoDoc.FromRuntimeSerialNumber(c.Document)!.ModelUnitSystem);
            return new()
            {
                ["kind"] = "Case",
                ["label"] = "Hawa selected geometry",
                ["shape"] = new JsonArray(shape.Select(v =>
                    JsonValue.Create(v)
                ).ToArray()),
                ["origin_m"] = c.SetupData["origin"]!.DeepClone(),
                ["origin"] = new JsonArray(c.SetupData["origin"]!.AsArray().Select(v =>
                    JsonValue.Create(v!.GetValue<double>() * units)
                ).ToArray()),
                ["spacing"] = c.Cell * units,
                ["dx"] = c.Cell,
                ["speed"] = c.Speed,
                ["viscosity"] = c.SetupData["viscosity"]!.DeepClone(),
                ["density"] = c.SetupData["density"]!.DeepClone(),
                ["mach"] = c.SetupData["mach"]!.DeepClone(),
                ["collision"] = c.SetupData["collision"]!.DeepClone(),
                ["boundaries"] = c.SetupData["boundaries"]!.DeepClone()
            };
        }

        var lengths = new[]
        {
            8d,
            6d,
            4d
        };
        var n = lengths.Select(x =>
            (int)Math.Floor(x / c.Cell) + 1
        ).ToArray();
        var solid = new JsonArray();
        for (int x = 0; x < n[0]; x++)
            for (int y = 0; y < n[1]; y++)
                for (int z = 0; z < n[2]; z++)
                    if (Math.Abs(x * c.Cell - 3) <= c.Width / 2 && Math.Abs(y * c.Cell - 3) <= c.Width / 2 && Math.Abs(z * c.Cell - 2) <= c.Width / 2)
                        solid.Add((x * n[1] + y) * n[2] + z);
        if (solid.Count == 0)
            throw new ArgumentException("The block is unresolved; reduce cell size or increase block width");
        double scale = RhinoMath.UnitScale(UnitSystem.Meters, RhinoDoc.FromRuntimeSerialNumber(c.Document)!.ModelUnitSystem);
        return new()
        {
            ["kind"] = "Case",
            ["label"] = "Hawa native block prototype",
            ["hawa_block_width"] = c.Width,
            ["shape"] = new JsonArray(n[0], n[1], n[2]),
            ["origin"] = new JsonArray(0d, 0d, 0d),
            ["spacing"] = c.Cell * scale,
            ["dx"] = c.Cell,
            ["speed"] = c.Speed,
            ["viscosity"] = c.SetupData["viscosity"]!.DeepClone(),
            ["density"] = c.SetupData["density"]!.DeepClone(),
            ["mach"] = c.SetupData["mach"]!.DeepClone(),
            ["collision"] = c.SetupData["collision"]!.DeepClone(),
            ["boundaries"] = c.SetupData["boundaries"]!.DeepClone(),
            ["solid"] = solid
        };
    }

    private static JsonObject Request(string op, string session) => Transport(new() { ["op"] = op, ["session"] = session });
    private static void Failure(CaseState c, string area, Exception error)
    {
        c.Error = error.GetBaseException().Message;
        c.Fault = new(area, c.Error, true);
        Stop(c);
        c.State = "failed";
    }

    public static void Run(uint doc)
    {
        var c = Get(doc);
        Change(c, () =>
        {
            try
            {
                c.Error = "";
                c.Fault = null;
                c.PauseRequested = false;
                if (c.Preparation != null)
                {
                    c.StartWhenReady = true;
                    return;
                }

                if (c.Job != null && c.Session == null)
                {
                    c.StartWhenReady = true;
                    return;
                }

                if (c.Session != null && c.RunRevision == c.Revision)
                {
                    var status = Transport(new() { ["op"] = "start", ["session"] = c.Session, ["steps"] = c.Target });
                    c.State = status["state"]?.GetValue<string>() ?? "running";
                    return;
                }

                Stop(c);
                c.Steps = 0;
                c.GeometryError = "";
                c.SpecData = BuildSpec(c);
                c.ViewFailures = 0;
                c.ViewError = "";
                if (c.SelectedGeometry)
                {
                    if (PrepareGeometry == null)
                        throw new InvalidOperationException("Native geometry service is unavailable");
                    c.PreparationCancel = new();
                    c.Preparation = PrepareGeometry(c, c.PreparationCancel.Token);
                    c.RunRevision = c.Revision;
                    c.StartWhenReady = true;
                    c.State = "voxelizing";
                    return;
                }

                Transport(new() { ["op"] = "check", ["case"] = c.SpecData.DeepClone() });
                var response = Transport(new() { ["op"] = "evaluate_submit", ["kind"] = "create", ["case"] = c.SpecData.DeepClone(), ["device"] = c.Device });
                c.Job = response["job"]!.GetValue<string>();
                c.RunRevision = c.Revision;
                c.StartWhenReady = true;
                c.State = "preparing";
            }
            catch (Exception e)
            {
                Failure(c, "solver", e);
            }
        });
        Notify(c, "run");
    }

    public static void Pause(uint doc)
    {
        var c = Get(doc);
        Change(c, () =>
        {
            c.StartWhenReady = false;
            c.PauseRequested = true;
            try
            {
                if (c.Session != null)
                    Request("pause_async", c.Session);
                c.State = c.Session == null && c.Preparation == null ? "paused" : "pausing";
            }
            catch (Exception e)
            {
                Failure(c, "control", e);
            }
        });
        Notify(c, "pause");
    }

    public static void Cancel(uint doc)
    {
        var c = Get(doc);
        Change(c, () =>
        {
            Stop(c);
            c.State = "cancelled";
        });
        Notify(c, "cancel");
    }

    public static void Reset(uint doc)
    {
        var c = Get(doc);
        Change(c, () =>
        {
            Stop(c);
            ClearResult(c);
            c.SpecData = null;
            c.Steps = 0;
            c.RunRevision = -1;
            c.State = "idle";
            c.Error = c.ViewError = "";
            c.Fault = null;
            c.ViewFailures = 0;
        });
        Notify(c, "reset");
    }

    public static void RefreshView(uint doc)
    {
        var c = Get(doc);
        Change(c, () =>
        {
            CloseQuery(c);
            c.ViewError = "";
            c.ViewFailures = 0;
            c.SliceSteps = -1;
            c.LastQuery = DateTime.MinValue;
        });
        Notify(c, "view");
    }

    /// <summary>Transfer a detached GH job to process-owned, retryable cleanup.</summary>
    public static void ReleaseJob(string? job)
    {
        UI();
        if (job != null)
            Release("job:" + job, new() { ["op"] = "evaluate_control", ["job"] = job, ["action"] = "close" });
    }

    /// <summary>Close cooperatively; acknowledgement does not imply worker exit.</summary>
    public static void ReleaseSession(string? session)
    {
        UI();
        if (session != null)
            Release("session:" + session, new() { ["op"] = "close_async", ["session"] = session });
    }

    private static void Release(string key, JsonObject request)
    {
        // Register ownership before crossing a bridge that can pump UI messages.
        // IDs are never reused. Repeated close requests share the same entry.
        if (!Cleanup.TryAdd(key, request))
            return;
        if (!cleanupSubscribed)
        {
            RhinoApp.Idle += CleanupIdle;
            cleanupSubscribed = true;
        }

        if (cleaning)
        {
            CleanupOrder.Enqueue(key);
            return;
        }

        cleaning = true;
        try
        {
            if (!AttemptCleanup(key, request))
                CleanupOrder.Enqueue(key);
        }
        finally
        {
            cleaning = false;
            StopCleanupWatchIfEmpty();
        }
    }

    private static bool AttemptCleanup(string key, JsonObject request)
    {
        try
        {
            Transport(request);
            Cleanup.Remove(key);
            return true;
        }
        catch (Exception e)
        {
            // Move failed work to the back so a persistent fault cannot starve
            // another owner's cleanup when a retry batch is bounded.
            RhinoApp.WriteLine("Hawa cleanup pending: " + e.GetBaseException().Message);
            return false;
        }
    }

    private static void StopCleanupWatchIfEmpty()
    {
        if (Cleanup.Count == 0 && cleanupSubscribed)
        {
            RhinoApp.Idle -= CleanupIdle;
            cleanupSubscribed = false;
        }
    }

    private static void CleanupIdle(object? sender, EventArgs e) => PollCleanup();
    private static void PollCleanup()
    {
        if (Cleanup.Count == 0 || cleaning || (DateTime.UtcNow - cleanupAttempt).TotalSeconds < 2)
            return;
        cleanupAttempt = DateTime.UtcNow;
        RetryCleanup();
    }

    private static void CloseQuery(CaseState c)
    {
        string? query = c.Query;
        c.Query = null;
        c.QueryStamp = null;
        if (query != null)
            Release("job:" + query, new() { ["op"] = "evaluate_control", ["job"] = query, ["action"] = "close" });
    }

    private static void Stop(CaseState c)
    {
        c.PreparationCancel?.Cancel();
        c.PreparationCancel?.Dispose();
        c.PreparationCancel = null;
        var preparation = c.Preparation;
        c.Preparation = null;
        if (preparation != null)
            _ = preparation.ContinueWith(t =>
            {
                _ = t.Exception;
            }, TaskContinuationOptions.OnlyOnFaulted);
        c.Generation++; // Invalidate replies before calling the bridge, which may pump UI messages.
        var job = c.Job;
        var session = c.Session;
        c.Job = c.Session = null;
        c.StartWhenReady = c.PauseRequested = false;
        c.StatusData = null;
        CloseQuery(c);
        if (job != null)
            Release("job:" + job, new() { ["op"] = "evaluate_control", ["job"] = job, ["action"] = "close" });
        else if (session != null)
            Release("session:" + session, new() { ["op"] = "close_async", ["session"] = session });
    }

    public static void GeometryChanged(uint doc, Guid objectId)
    {
        var c = Find(doc);
        if (c == null || !c.SelectedGeometry || !c.SetupData["objects"]!.AsArray().Any(v =>
            v!.GetValue<string>() == objectId.ToString()
        ))
            return;
        UI();
        if (Busy.Contains(c))
        {
            PendingGeometry.Add((doc, objectId));
            return;
        }

        Change(c, () =>
        {
            Stop(c);
            c.Version++;
            c.Revision++;
            c.GeometryError = "Selected geometry changed. Review it and run again; reselect any deleted objects.";
            c.State = c.Result == null ? "idle" : "outdated";
        });
        Notify(c, "geometry");
    }

    public static void Close(uint doc)
    {
        UI();
        if (!Cases.TryGetValue(doc, out var c))
            return;
        if (Busy.Contains(c))
        {
            PendingClose.Add(doc);
            return;
        }

        Change(c, () =>
            Stop(c)
        );
        Closing.Add(doc);
        try
        {
            Cases.Remove(doc);
            Notify(c, "closed");
        }
        finally
        {
            Closing.Remove(doc);
        }
    }

    public static void RetryCleanup()
    {
        UI();
        if (cleaning)
            return;
        cleaning = true;
        try
        {
            // Bound UI work. The Idle subscription survives GH document disposal
            // and works even when the native panel/plugin has never been opened.
            int count = Math.Min(8, CleanupOrder.Count);
            for (int i = 0; i < count; i++)
            {
                string key = CleanupOrder.Dequeue();
                if (Cleanup.TryGetValue(key, out var request) && !AttemptCleanup(key, request))
                    CleanupOrder.Enqueue(key);
            }
        }
        finally
        {
            cleaning = false;
            StopCleanupWatchIfEmpty();
        }
    }

    private static bool Matches(CaseState c, ResultStamp stamp) => Find(c.Document) == c && c.Id == stamp.CaseId && c.Generation == stamp.Generation && c.Revision == stamp.Revision && c.Session == stamp.Session && c.Field == stamp.Field;
    private static void ValidateSlice(JsonObject result)
    {
        var values = result["values"]!.AsArray();
        var valid = result["valid"]!.AsArray();
        var coordinates = result["coordinates"]!.AsArray();
        int nx = result["shape"]![0]!.GetValue<int>(), ny = result["shape"]![1]!.GetValue<int>();
        if (nx < 1 || ny < 1 || (long)nx * ny != values.Count || valid.Count != values.Count || coordinates.Count != values.Count)
            throw new InvalidOperationException("Invalid field snapshot dimensions");
        for (int i = 0; i < values.Count; i++)
        {
            if (!double.IsFinite(values[i]!.GetValue<double>()) || coordinates[i]!.AsArray().Count != 3 || coordinates[i]!.AsArray().Any(v =>
                !double.IsFinite(v!.GetValue<double>())
            ))
                throw new InvalidOperationException("Invalid field snapshot values");
            _ = valid[i]!.GetValue<bool>();
        }
    }

    private static void PollView(CaseState c)
    {
        try
        {
            if (c.Query != null)
            {
                var stamp = c.QueryStamp!;
                var query = c.Query;
                var response = Transport(new() { ["op"] = "evaluate_poll", ["job"] = query });
                if (!Matches(c, stamp) || c.Query != query)
                    return;
                string state = response["state"]!.GetValue<string>();
                if (state is "failed" or "cancelled")
                    throw new InvalidOperationException(response["error"]?.GetValue<string>() ?? "Field query cancelled");
                if (state == "completed")
                {
                    var result = response["result"]!.DeepClone().AsObject();
                    ValidateSlice(result);
                    if (result["session"]?.GetValue<string>() != stamp.Session || result["field"]?.GetValue<string>() != stamp.Field)
                        throw new InvalidOperationException("Field snapshot identity mismatch");
                    int steps = result["steps"]!.GetValue<int>();
                    if (steps < 0)
                        throw new InvalidOperationException("Invalid field snapshot step");
                    double time = result["physical_time"]!.GetValue<double>();
                    if (!double.IsFinite(time) || time < 0)
                        throw new InvalidOperationException("Invalid field snapshot time");
                    var resultStamp = stamp with
                    {
                        Steps = steps,
                        PhysicalTime = time
                    };
                    var resultSpec = c.SpecData?.DeepClone().AsObject();
                    c.SliceData = result;
                    c.ResultSpecData = resultSpec;
                    c.Result = resultStamp;
                    c.SliceSteps = steps;
                    c.ResultVersion++;
                    c.ViewError = "";
                    c.ViewFailures = 0;
                    CloseQuery(c);
                }
            }

            if (c.Query == null && c.ViewFailures < 3 && (DateTime.UtcNow - c.LastQuery).TotalSeconds > (c.ViewFailures == 0 ? .6 : 2) && (c.State == "running" || c.SliceData == null || c.SliceSteps != c.Steps))
            {
                var stamp = new ResultStamp(c.Id, c.Revision, c.Generation, c.Session!, c.Field, c.Steps);
                int axis = c.ViewData["axis"]!.GetValue<int>();
                int index = (int)Math.Round((c.SpecData!["shape"]![axis]!.GetValue<int>() - 1) * c.ViewData["position"]!.GetValue<double>());
                var request = new JsonObject
                {
                    ["op"] = "slice",
                    ["session"] = c.Session,
                    ["field"] = c.Field,
                    ["axis"] = axis,
                    ["index"] = index
                };
                c.Query = Transport(new() { ["op"] = "evaluate_submit", ["kind"] = "query", ["request"] = request })["job"]!.GetValue<string>();
                c.QueryStamp = stamp;
                c.LastQuery = DateTime.UtcNow;
            }
        }
        catch (Exception e)
        {
            CloseQuery(c);
            c.ViewError = e.GetBaseException().Message;
            c.ViewFailures++;
            c.LastQuery = DateTime.UtcNow;
        // A visualization failure leaves the solver and last good field available.
        }
    }

    public static void Tick()
    {
        UI();
        if (polling)
            return;
        polling = true;
        try
        {
            PollCleanup();
            foreach (var c in All)
            {
                if (Find(c.Document) != c || Busy.Contains(c))
                    continue;
                var doc = RhinoDoc.FromRuntimeSerialNumber(c.Document);
                if (doc == null)
                {
                    Close(c.Document);
                    continue;
                }

                if (c.ModelUnits != doc.ModelUnitSystem)
                {
                    c.ModelUnits = doc.ModelUnitSystem;
                    // Referenced geometry is reinterpreted by Rhino unit changes. Invalidate
                    // conservatively even if Rhino also scales the objects to preserve size.
                    if (c.SelectedGeometry && c.SetupData["objects"]!.AsArray().Count > 0)
                        GeometryChanged(c.Document, Guid.Parse(c.SetupData["objects"]![0]!.GetValue<string>()));
                    Notify(c, "units");
                }

                if (Find(c.Document) != c)
                    continue;
                var before = (c.State, c.Steps, c.ResultVersion, c.ViewError);
                Change(c, () =>
                {
                    try
                    {
                        if (c.Preparation != null)
                        {
                            if (!c.Preparation.IsCompleted)
                                return;
                            var preparation = c.Preparation;
                            c.Preparation = null;
                            c.PreparationCancel?.Dispose();
                            c.PreparationCancel = null;
                            if (preparation.IsCanceled)
                            {
                                c.State = "cancelled";
                                return;
                            }

                            if (preparation.IsFaulted)
                                throw preparation.Exception!.GetBaseException();
                            c.SpecData = preparation.Result;
                            Transport(new() { ["op"] = "check", ["case"] = c.SpecData.DeepClone() });
                            c.Job = Transport(new() { ["op"] = "evaluate_submit", ["kind"] = "create", ["case"] = c.SpecData.DeepClone(), ["device"] = c.Device })["job"]!.GetValue<string>();
                            c.State = "preparing";
                        }

                        if (c.Job != null && c.Session == null)
                        {
                            var response = Transport(new() { ["op"] = "evaluate_poll", ["job"] = c.Job });
                            string state = response["state"]!.GetValue<string>();
                            if (state is "failed" or "cancelled")
                                throw new InvalidOperationException(response["error"]?.GetValue<string>() ?? "Preparation cancelled");
                            if (state != "completed")
                            {
                                c.State = state == "queued" ? "queued" : "preparing";
                                return;
                            }

                            c.Session = response["result"]!["status"]!["session"]!.GetValue<string>();
                            if (c.StartWhenReady)
                                Transport(new() { ["op"] = "start", ["session"] = c.Session, ["steps"] = c.Target });
                        }

                        if (c.Session == null)
                            return;
                        c.StatusData = Request("status", c.Session);
                        c.Steps = c.StatusData["steps"]!.GetValue<int>();
                        c.State = c.StatusData["state"]!.GetValue<string>();
                        if (c.PauseRequested && c.State == "ready")
                            c.State = "paused";
                        if (c.StatusData["error"] != null)
                            throw new InvalidOperationException(c.StatusData["error"]!.GetValue<string>());
                        PollView(c);
                    }
                    catch (Exception e)
                    {
                        Failure(c, "solver", e);
                    }
                });
                if (before != (c.State, c.Steps, c.ResultVersion, c.ViewError))
                    Notify(c, "progress");
            }
        }
        finally
        {
            polling = false;
        }
    }
}
