using System.Text.Json.Nodes;
namespace Rhino {
    public enum UnitSystem { Meters, Millimeters }
    public static class RhinoMath { public static double UnitScale(UnitSystem a, UnitSystem b) => a == b ? 1 : b == UnitSystem.Millimeters ? 1000 : .001; }
    public static class RhinoApp { public static bool InvokeRequired; public static event EventHandler? Idle; public static void RaiseIdle() => Idle?.Invoke(null, EventArgs.Empty); public static int IdleSubscribers => Idle?.GetInvocationList().Length ?? 0; public static List<string> Log = new(); public static void WriteLine(string s) => Log.Add(s); }
    public sealed class RhinoDoc {
        static readonly Dictionary<uint, RhinoDoc> docs = new();
        public RhinoDoc(uint id) { RuntimeSerialNumber = id; docs[id] = this; }
        public uint RuntimeSerialNumber { get; }
        public UnitSystem ModelUnitSystem { get; set; } = UnitSystem.Meters;
        public bool Modified { get; set; }
        public int OpenUndoRecords, EndedUndoRecords;
        public List<EventHandler<Commands.CustomUndoEventArgs>> UndoEvents = new();
        public static RhinoDoc? FromRuntimeSerialNumber(uint id) => docs.GetValueOrDefault(id);
        public uint BeginUndoRecord(string name) { OpenUndoRecords++; return 1; }
        public void EndUndoRecord(uint id) { OpenUndoRecords--; EndedUndoRecords++; }
        public void AddCustomUndoEvent(string name, EventHandler<Commands.CustomUndoEventArgs> action) => UndoEvents.Add(action);
        public void Undo() { var a = UndoEvents.Last(); UndoEvents.RemoveAt(UndoEvents.Count - 1); a(this, new(this)); }
    }
}
namespace Rhino.Commands { public sealed class CustomUndoEventArgs(Rhino.RhinoDoc document) : EventArgs { public Rhino.RhinoDoc Document { get; } = document; } }
namespace Hawa.Shared { public static class EmbeddedRuntime { public static JsonObject Call(JsonObject request) => throw new Exception("Test transport not configured"); } }
