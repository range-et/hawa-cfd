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
        public static void Remove(uint id) => docs.Remove(id);
        public uint BeginUndoRecord(string name) { OpenUndoRecords++; return 1; }
        public void EndUndoRecord(uint id) { OpenUndoRecords--; EndedUndoRecords++; }
        public void AddCustomUndoEvent(string name, EventHandler<Commands.CustomUndoEventArgs> action) => UndoEvents.Add(action);
        public void Undo() { var a = UndoEvents.Last(); UndoEvents.RemoveAt(UndoEvents.Count - 1); a(this, new(this)); }
    }
}
namespace Rhino.Commands { public sealed class CustomUndoEventArgs(Rhino.RhinoDoc document) : EventArgs { public Rhino.RhinoDoc Document { get; } = document; } }
namespace Hawa.Shared {
    // Components reach the bridge through Hawa.Grasshopper.EmbeddedRuntime; tests script it per case.
    public static class EmbeddedRuntime {
        public static Func<JsonObject, JsonObject>? Handler;
        public static string Root => "/hawa-test-root";
        public static JsonObject Call(JsonObject request) => (Handler ?? throw new Exception("Test transport not configured"))(request);
    }
}
// Storage and scheduling doubles only: no claim about Rhino mesh kernels,
// viewport rendering, Eto event-loop timing or real GH solution ordering.
namespace Rhino.Geometry {
    public record struct Vector3d(double X, double Y, double Z) {
        // RhinoCommon's unset sentinel (RhinoMath.UnsetValue) is finite but invalid.
        public const double UnsetValue = -1.23432101234321e+308;
        public static Vector3d XAxis => new(1,0,0);
        public static Vector3d YAxis => new(0,1,0);
        public static Vector3d ZAxis => new(0,0,1);
        public static Vector3d Unset => new(UnsetValue,UnsetValue,UnsetValue);
        public bool IsValid => double.IsFinite(X)&&double.IsFinite(Y)&&double.IsFinite(Z)&&X!=UnsetValue&&Y!=UnsetValue&&Z!=UnsetValue;
        public static Vector3d operator *(Vector3d v,double n)=>n*v;
        public double SquareLength => X*X+Y*Y+Z*Z;
        public double Length => Math.Sqrt(SquareLength);
        public static Vector3d operator *(double n,Vector3d v)=>new(n*v.X,n*v.Y,n*v.Z);
        public static Vector3d operator +(Vector3d a,Vector3d b)=>new(a.X+b.X,a.Y+b.Y,a.Z+b.Z);
        public static double operator *(Vector3d a,Vector3d b)=>a.X*b.X+a.Y*b.Y+a.Z*b.Z;
        public static Vector3d CrossProduct(Vector3d a,Vector3d b)=>new(a.Y*b.Z-a.Z*b.Y,a.Z*b.X-a.X*b.Z,a.X*b.Y-a.Y*b.X);
        public void Unitize() { double n=Length;X/=n;Y/=n;Z/=n; }
    }
    public readonly record struct Point3d(double X, double Y, double Z) {
        public bool IsValid => double.IsFinite(X)&&double.IsFinite(Y)&&double.IsFinite(Z);
        public static Point3d operator +(Point3d p, Vector3d v) => new(p.X+v.X,p.Y+v.Y,p.Z+v.Z);
        public static Vector3d operator -(Point3d a,Point3d b)=>new(a.X-b.X,a.Y-b.Y,a.Z-b.Z);
        public double DistanceTo(Point3d other)=>(this-other).Length;
    }
    public readonly record struct BoundingBox(Point3d Min, Point3d Max) {
        public Vector3d Diagonal=>Max-Min;
        public bool Contains(Point3d p)=>p.X>=Min.X&&p.X<=Max.X&&p.Y>=Min.Y&&p.Y<=Max.Y&&p.Z>=Min.Z&&p.Z<=Max.Z;
    }
    public readonly record struct Line(Point3d From,Point3d To);
    public abstract class Curve { }
    public sealed class PolylineCurve(IEnumerable<Point3d> points) : Curve { public List<Point3d> Points { get; } = points.ToList(); }
    public readonly record struct MeshFace(int A,int B,int C,int D=-1) { public bool IsQuad=>D>=0; }
    public sealed record MeshPoint(Point3d Point);
    public sealed class Brep {
        public bool IsValid=true,IsSolid=true;
        public BoundingBox Bounds=new(new(0,0,0),new(10,0,0));
        public BoundingBox GetBoundingBox(bool accurate)=>Bounds;
    }
    public sealed class MeshingParameters : IDisposable {
        public double Tolerance,MinimumTolerance,RelativeTolerance,MinimumEdgeLength,MaximumEdgeLength;
        public bool RefineGrid,SimplePlanes,JaggedSeams,DoublePrecision,Disposed;
        public void Dispose()=>Disposed=true;
    }
    public sealed class Mesh : IDisposable {
        public sealed class VertexList : List<Point3d> { public new int Add(Point3d point) { base.Add(point); return Count-1; } }
        public sealed class FaceList : List<MeshFace> {
            public int? ReportedCount;
            public new int Count=>ReportedCount??base.Count;
            public void AddFace(int a,int b,int c)=>Add(new(a,b,c));
        }
        public sealed class NormalList { public int Calls; public void ComputeNormals() => Calls++; }
        public static List<Mesh> Created=new();
        public static Func<Brep,MeshingParameters,Mesh[]> Factory=(_,_)=>Array.Empty<Mesh>();
        public Mesh(){Created.Add(this);}
        public VertexList Vertices { get; } = new();
        public List<System.Drawing.Color> VertexColors { get; } = new();
        public FaceList Faces { get; } = new();
        public NormalList Normals { get; } = new();
        public bool IsValid=true,IsClosed=true,Disposed;
        public BoundingBox Bounds=new(new(-10,-10,-10),new(10,10,10));
        public Func<Line,Point3d[]> Hits=_=>Array.Empty<Point3d>();
        public Func<Point3d,double,MeshPoint?> Closest=(_,_)=>null;
        public MeshPoint? ClosestMeshPoint(Point3d p,double tolerance)=>Closest(p,tolerance);
        public BoundingBox GetBoundingBox(bool accurate)=>Bounds;
        public static Mesh[] CreateFromBrep(Brep b,MeshingParameters p)=>Factory(b,p);
        public void Append(Mesh part){Vertices.AddRange(part.Vertices);Faces.AddRange(part.Faces);Faces.ReportedCount=part.Faces.ReportedCount;IsValid&=part.IsValid;IsClosed&=part.IsClosed;}
        public void Dispose()=>Disposed=true;
    }
}
namespace Rhino.Geometry.Intersect {
    public static class Intersection { public static Rhino.Geometry.Point3d[] MeshLine(Rhino.Geometry.Mesh mesh,Rhino.Geometry.Line line)=>mesh.Hits(line); }
}
namespace Eto.Forms {
    public sealed class UITimer : IDisposable {
        public static List<UITimer> Active = new();
        public double Interval { get; set; }
        public event EventHandler? Elapsed;
        public bool Disposed;
        public void Start() => Active.Add(this);
        public void Stop() => Active.Remove(this);
        public void Dispose() { Disposed=true;Active.Remove(this); }
        public void Pulse() => Elapsed?.Invoke(this,EventArgs.Empty);
    }
}
