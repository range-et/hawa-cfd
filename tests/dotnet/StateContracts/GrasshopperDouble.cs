using System.Collections;
// Grasshopper SDK doubles: the subset of GH_Component, parameter, data-access,
// goo and archive APIs that the linked Hawa.Grasshopper sources call. They model
// documented SDK contracts (runtime messages clear per solution, Message persists,
// AllData(true) skips nulls, the constructor registers parameters). They make no
// claim about real GH solution ordering, canvas drawing or scheduling.
namespace System.Drawing { public sealed class Bitmap(string name) { public string Name { get; } = name; } }
namespace GH_IO.Serialization {
    public interface GH_IReader { bool ChunkExists(string name, int index); string GetString(string name); }
    public interface GH_IWriter { void SetString(string name, string value); }
}
namespace Grasshopper {
    public static class Instances { public static List<Kernel.GH_Document> DocumentServer = new(); }
}
namespace Grasshopper.Kernel.Types {
    public interface IGH_Goo { bool IsValid { get; } string TypeName { get; } }
    public abstract class GH_Goo<T> : IGH_Goo {
        public T Value { get; set; } = default!;
        public abstract bool IsValid { get; }
        public abstract string TypeName { get; }
        public abstract string TypeDescription { get; }
        public abstract IGH_Goo Duplicate();
        public abstract override string ToString();
        public virtual bool CastTo<Q>(ref Q target) => false;
        public virtual bool Write(GH_IO.Serialization.GH_IWriter writer) => true;
        public virtual bool Read(GH_IO.Serialization.GH_IReader reader) => true;
    }
    public sealed class GH_ObjectWrapper(object? value) : IGH_Goo { public object? Value { get; } = value; public bool IsValid => Value != null; public string TypeName => "Generic Data"; }
    public sealed class GH_String(string value) : IGH_Goo { public string Value { get; } = value; public bool IsValid => true; public string TypeName => "Text"; }
}
namespace Grasshopper.Kernel {
    using Grasshopper.Kernel.Types;
    public enum GH_RuntimeMessageLevel { Blank, Remark, Warning, Error }
    public enum GH_DocumentContext { Unknown, None, Loaded, Unloaded, Open, Close, Lock, Unlock }
    public enum GH_ParamAccess { item, list, tree }
    public enum GH_Exposure { primary, secondary, tertiary, hidden }
    public sealed class GH_Document {
        public static bool EnableSolutions = true;
        public bool Enabled = true;
        public int SolutionDepth, Solutions;
        public string? FilePath;
        public Action? DuringSolution;
        public void NewSolution(bool expireAll) { Solutions++;DuringSolution?.Invoke(); }
    }
    public abstract class GH_AssemblyInfo {
        public virtual string Name => "";
        public virtual string Description => "";
        public virtual Guid Id => Guid.Empty;
        public virtual string AuthorName => "";
        public virtual string AuthorContact => "";
        public virtual System.Drawing.Bitmap? Icon => null;
    }
    public interface IGH_DocumentObject { string NickName { get; } }
    public interface IGH_Attributes { IGH_Attributes GetTopLevel { get; } IGH_DocumentObject DocObject { get; } }
    public sealed class GH_Structure {
        public readonly List<IGH_Goo?> Items = new();
        public IEnumerable<IGH_Goo?> AllData(bool skipNulls) => skipNulls ? Items.Where(v => v != null) : Items;
    }
    public interface IGH_Param {
        string Name { get; }
        string NickName { get; }
        bool Optional { get; set; }
        GH_ParamAccess Access { get; set; }
        GH_Structure VolatileData { get; }
        IList<IGH_Param> Sources { get; }
        IGH_Attributes? Attributes { get; }
    }
    // One parameter; Owner models Attributes.GetTopLevel.DocObject (the component that owns an output).
    public sealed class GH_TestParam(string name, string nick, string description, GH_ParamAccess access, string kind, object? fallback) : IGH_Param, IGH_Attributes, IGH_DocumentObject {
        public string Name { get; } = name;
        public string NickName { get; set; } = nick;
        public string Description { get; } = description;
        public string Kind { get; } = kind;
        public object? Default { get; } = fallback;
        public bool Optional { get; set; }
        public GH_ParamAccess Access { get; set; } = access;
        public GH_Structure VolatileData { get; } = new();
        public IList<IGH_Param> Sources { get; } = new List<IGH_Param>();
        public IGH_DocumentObject? Owner;
        public IGH_Attributes? Attributes => Owner == null ? null : this;
        IGH_Attributes IGH_Attributes.GetTopLevel => this;
        IGH_DocumentObject IGH_Attributes.DocObject => Owner!;
    }
    public sealed class GH_ComponentParamServer {
        public List<IGH_Param> Input { get; } = new();
        public List<IGH_Param> Output { get; } = new();
        public int ParameterChanges;
        public bool UnregisterInputParameter(IGH_Param p, bool isolate) => Input.Remove(p);
        public bool UnregisterOutputParameter(IGH_Param p, bool isolate) => Output.Remove(p);
        public bool RegisterInputParam(IGH_Param p) { Input.Add(p); return true; }
        public bool RegisterOutputParam(IGH_Param p) { Output.Add(p); return true; }
        public void OnParametersChanged() => ParameterChanges++;
    }
    public abstract class GH_ParamManager(List<IGH_Param> target) {
        public IGH_Param this[int index] => target[index];
        protected int Add(string name, string nick, string description, GH_ParamAccess access, string kind, object? fallback) { target.Add(new GH_TestParam(name, nick, description, access, kind, fallback)); return target.Count - 1; }
        public int AddGenericParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Generic", null);
        public int AddTextParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Text", null);
        public int AddTextParameter(string n, string k, string d, GH_ParamAccess a, string v) => Add(n, k, d, a, "Text", v);
        public int AddIntegerParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Integer", null);
        public int AddIntegerParameter(string n, string k, string d, GH_ParamAccess a, int v) => Add(n, k, d, a, "Integer", v);
        public int AddBooleanParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Boolean", null);
        public int AddBooleanParameter(string n, string k, string d, GH_ParamAccess a, bool v) => Add(n, k, d, a, "Boolean", v);
        public int AddNumberParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Number", null);
        public int AddNumberParameter(string n, string k, string d, GH_ParamAccess a, double v) => Add(n, k, d, a, "Number", v);
        public int AddPointParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Point", null);
        public int AddVectorParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Vector", null);
        public int AddMeshParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Mesh", null);
        public int AddLineParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Line", null);
        public int AddCurveParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Curve", null);
        public int AddRectangleParameter(string n, string k, string d, GH_ParamAccess a) => Add(n, k, d, a, "Rectangle", null);
    }
    public sealed class GH_InputParamManager(GH_Component owner) : GH_ParamManager(owner.Params.Input);
    public sealed class GH_OutputParamManager(GH_Component owner) : GH_ParamManager(owner.Params.Output);
    public interface IGH_DataAccess {
        bool GetData<T>(int index, ref T destination);
        bool GetDataList<T>(int index, List<T> list);
        bool SetData(int index, object? data);
        bool SetDataList(int index, IEnumerable data);
    }
    public class GH_Component : IGH_DocumentObject {
        public GH_Document? Document;
        public bool Locked;
        public string Message { get; set; } = null!;
        public int Expirations, BaseReads, BaseContextChanges, BaseRemovals;
        public bool BaseReadResult = true;
        public Action? DuringExpire;
        public readonly List<(GH_RuntimeMessageLevel Level, string Text)> RuntimeMessages = new();
        public List<string> Errors => RuntimeMessages.Where(m => m.Level == GH_RuntimeMessageLevel.Error).Select(m => m.Text).ToList();
        public GH_ComponentParamServer Params { get; } = new();
        public string Name { get; } = "";
        public string NickName { get; set; } = "";
        public string Description { get; } = "";
        public string Category { get; } = "";
        public string SubCategory { get; } = "";
        public GH_Component() { }
        // GH registers parameters while constructing a component.
        protected GH_Component(string name, string nick, string description, string category, string subCategory) {
            (Name, NickName, Description, Category, SubCategory) = (name, nick, description, category, subCategory);
            RegisterInputParams(new GH_InputParamManager(this));
            RegisterOutputParams(new GH_OutputParamManager(this));
            foreach (var p in Params.Output.OfType<GH_TestParam>()) p.Owner = this;
        }
        public virtual Guid ComponentGuid => Guid.Empty;
        public virtual GH_Exposure Exposure => GH_Exposure.primary;
        protected virtual System.Drawing.Bitmap? Icon => null;
        public System.Drawing.Bitmap? IconForTest => Icon;
        protected virtual void RegisterInputParams(GH_InputParamManager pManager) { }
        protected virtual void RegisterOutputParams(GH_OutputParamManager pManager) { }
        protected virtual void SolveInstance(IGH_DataAccess da) { }
        public int InputsAtBaseRead = -1, OutputsAtBaseRead = -1;
        public virtual bool Read(GH_IO.Serialization.GH_IReader reader) { BaseReads++; (InputsAtBaseRead, OutputsAtBaseRead) = (Params.Input.Count, Params.Output.Count); return BaseReadResult; }
        public virtual void DocumentContextChanged(GH_Document document, GH_DocumentContext context) => BaseContextChanges++;
        public virtual void RemovedFromDocument(GH_Document document) => BaseRemovals++;
        public GH_Document? OnPingDocument() => Document;
        public void ExpireSolution(bool recompute) { Expirations++;DuringExpire?.Invoke(); }
        public void AddRuntimeMessage(GH_RuntimeMessageLevel level,string message) => RuntimeMessages.Add((level, message));
        // One GH solution of this component: runtime messages clear, Message persists.
        public void Compute(IGH_DataAccess da) { RuntimeMessages.Clear(); SolveInstance(da); }
    }
}
