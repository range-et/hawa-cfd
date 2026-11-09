using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino;
using Rhino.Geometry;

namespace Hawa.Grasshopper;

public sealed class DomainComponent : HawaComponent
{
    public DomainComponent() : base("Hawa Domain", "Domain", "Uniform oriented lattice from a box. Flow follows the box's X axis; spacing is in model units.", "01 Domain") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077101");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddBoxParameter("Box", "B", "Domain bounds; lattice axes follow the box frame", GH_ParamAccess.item); p.AddNumberParameter("Cell size", "dx", "Uniform spacing in model units", GH_ParamAccess.item, 1); p.AddTextParameter("Length units", "Units", "model (Rhino document), meters or millimeters", GH_ParamAccess.item, "model"); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddGenericParameter("Domain", "D", "Hawa lattice domain", GH_ParamAccess.item); p.AddBoxParameter("Bounds", "B", "Actual expanded lattice bounds", GH_ParamAccess.item); p.AddTextParameter("Grid", "G", "Resolution and cell count", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        Box box = default; double dx = 1;
        if (!da.GetData(0, ref box) || !da.GetData(1, ref dx)) return;
        if (!box.IsValid || !double.IsFinite(dx) || dx <= 0) throw new ArgumentException("Provide a valid box and positive cell size");
        string units = "model"; da.GetData(2, ref units);
        double? scale = units.ToLowerInvariant() switch { "model" => null, "meters" => 1d, "millimeters" => .001d, _ => throw new ArgumentException("Length units: model, meters or millimeters") };
        var data = MakeDomain(box, dx, scale);
        var shape = data["shape"]!.AsArray().Select(v => v!.GetValue<int>()).ToArray();
        var cells = (long)shape[0] * shape[1] * shape[2];
        da.SetData(0, new HawaGoo(data));
        da.SetData(1, new Box(box.Plane, new Interval(box.X.T0, box.X.T0 + (shape[0] - 1) * dx), new Interval(box.Y.T0, box.Y.T0 + (shape[1] - 1) * dx), new Interval(box.Z.T0, box.Z.T0 + (shape[2] - 1) * dx)));
        da.SetData(2, $"{shape[0]} × {shape[1]} × {shape[2]} = {cells:N0} cells");
    }
    internal static JsonObject MakeDomain(Box box, double dx, double? metersPerUnit = null)
    {
        if (!box.IsValid || !double.IsFinite(dx) || dx <= 0) throw new ArgumentException("Provide a valid box and positive spacing");
        var n = new[] { box.X.Length, box.Y.Length, box.Z.Length }.Select(v => Math.Max(4, (int)Math.Ceiling(v / dx) + 1)).ToArray();
        if ((long)n[0] * n[1] * n[2] > 2_000_000) throw new ArgumentException("Dense grid exceeds two million cells; increase spacing");
        var o = box.PointAt(0, 0, 0);
        var axes = new[] { box.Plane.XAxis, box.Plane.YAxis, box.Plane.ZAxis };
        var meters = metersPerUnit ?? RhinoMath.UnitScale(RhinoDoc.ActiveDoc?.ModelUnitSystem ?? UnitSystem.Meters, UnitSystem.Meters);
        return new JsonObject { ["kind"] = "Domain", ["label"] = $"Hawa {n[0]} × {n[1]} × {n[2]}", ["shape"] = new JsonArray(n.Select(v => JsonValue.Create(v)).ToArray()), ["origin"] = Numbers(new[] { o.X, o.Y, o.Z }), ["basis"] = new JsonArray(axes.Select(v => (JsonNode)Numbers(new[] { v.X, v.Y, v.Z })).ToArray()), ["spacing"] = dx, ["dx"] = dx * meters };
    }
}

public sealed class WindTunnelComponent : HawaComponent
{
    public WindTunnelComponent() : base("Hawa Wind Tunnel", "Tunnel", "Create an oriented domain around closed geometry. Wind vector direction sets domain X; magnitude is m/s. Clearance is a geometry-relative setup aid.", "01 Domain") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077115");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddMeshParameter("Geometry", "G", "Obstacle meshes", GH_ParamAccess.list); p.AddVectorParameter("Wind", "W", "Direction and physical speed in m/s", GH_ParamAccess.item, Vector3d.XAxis); p.AddNumberParameter("Cell size", "dx", "Model units", GH_ParamAccess.item, 1); p.AddNumberParameter("Clearance", "C", "Padding in obstacle heights; downstream gets twice this amount", GH_ParamAccess.item, 3); p.AddBooleanParameter("Ground mounted", "Gnd", "False adds clearance below the object", GH_ParamAccess.item, true); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddGenericParameter("Domain", "D", "Wind-oriented domain; connect to Geometry and Case", GH_ParamAccess.item); p.AddBoxParameter("Bounds", "B", "Suggested wind tunnel", GH_ParamAccess.item); p.AddNumberParameter("Speed", "U", "Connect to Hawa Physics", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        var meshes = new List<Mesh>(); Vector3d wind = Vector3d.XAxis; double dx = 1, clearance = 3;
        da.GetDataList(0, meshes); da.GetData(1, ref wind); da.GetData(2, ref dx); da.GetData(3, ref clearance); bool ground=true; da.GetData(4,ref ground);
        if (meshes.Count == 0 || !wind.IsValid || wind.Length < 1e-12 || !double.IsFinite(clearance) || clearance <= 0) throw new ArgumentException("Provide meshes, nonzero wind and positive clearance");
        var speed = wind.Length; var x = wind; x.Unitize();
        var up = Math.Abs(x.Z) > .99 ? Vector3d.YAxis : Vector3d.ZAxis;
        var y = Vector3d.CrossProduct(up, x); y.Unitize(); var frame = new Plane(Point3d.Origin, x, y);
        var local = meshes.SelectMany(m => m.Vertices.Select(v => new Point3d((Vector3d)(Point3d)v * frame.XAxis, (Vector3d)(Point3d)v * frame.YAxis, (Vector3d)(Point3d)v * frame.ZAxis))).ToArray();
        var b = new BoundingBox(local); var h = Math.Max(dx, b.Max.Z - b.Min.Z); var pad = clearance * h;
        var box = new Box(frame, new Interval(b.Min.X - pad, b.Max.X + 2 * pad), new Interval(b.Min.Y - pad, b.Max.Y + pad), new Interval(b.Min.Z-(ground?0:pad), b.Max.Z + pad));
        var domain=DomainComponent.MakeDomain(box,dx);var n=domain["shape"]!.AsArray().Select(v=>v!.GetValue<int>()).ToArray();
        da.SetData(0,new HawaGoo(domain));da.SetData(1,new Box(frame,new Interval(box.X.T0,box.X.T0+(n[0]-1)*dx),new Interval(box.Y.T0,box.Y.T0+(n[1]-1)*dx),new Interval(box.Z.T0,box.Z.T0+(n[2]-1)*dx)));da.SetData(2,speed);
    }
}

public sealed class GeometryComponent : HawaComponent
{
    private Task<JsonObject>? task;
    private CancellationTokenSource? cancellation;
    private string? signature;
    public GeometryComponent() : base("Hawa Geometry", "Geometry", "Cancellable background voxelization of closed meshes. Results are cached by geometry and domain.", "02 Geometry") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077102");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddGenericParameter("Domain", "D", "Hawa Domain", GH_ParamAccess.item); p.AddMeshParameter("Obstacles", "M", "Closed solid meshes", GH_ParamAccess.list); p[1].Optional = true; p.AddBooleanParameter("Curved walls","W","Compute link/surface intersections for interpolated bounce-back",GH_ParamAccess.item,false); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddGenericParameter("Geometry", "G", "Voxelized obstacles", GH_ParamAccess.item); p.AddIntegerParameter("Solid cells", "N", "Occupied lattice sites", GH_ParamAccess.item); }
    internal static bool Contains(Mesh mesh, BoundingBox bounds, Point3d point, double tolerance) => Hawa.Shared.MeshContainment.Contains(mesh, bounds, point, tolerance);
    internal static double LinkFraction(Mesh mesh,Point3d origin,Vector3d segment){
        double nearest=double.PositiveInfinity;
        foreach(var face in mesh.Faces){
            Test((Point3d)mesh.Vertices[face.A],(Point3d)mesh.Vertices[face.B],(Point3d)mesh.Vertices[face.C]);
            if(face.IsQuad)Test((Point3d)mesh.Vertices[face.A],(Point3d)mesh.Vertices[face.C],(Point3d)mesh.Vertices[face.D]);
        }
        return nearest;
        void Test(Point3d a,Point3d b,Point3d c){
            var e1=b-a;var e2=c-a;var h=Vector3d.CrossProduct(segment,e2);double det=e1*h;
            if(Math.Abs(det)<=1e-12*e1.Length*e2.Length*segment.Length)return;
            double inv=1/det;var s=origin-a;double u=inv*(s*h);
            if(u < -1e-8||u>1+1e-8)return;
            var q=Vector3d.CrossProduct(s,e1);double v=inv*(segment*q);
            if(v < -1e-8||u+v>1+1e-8)return;
            double t=inv*(e2*q);if(t>=-1e-8&&t<=1+1e-8)nearest=Math.Min(nearest,Math.Clamp(t,0,1));
        }
    }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        var domain=ReadObject(da,0);var meshes=new List<Mesh>();da.GetDataList(1,meshes);
        if(meshes.Any(m=>!m.IsValid||!m.IsClosed))throw new ArgumentException("Obstacle meshes must be valid and closed");
        bool curved=false;da.GetData(2,ref curved);
        string key=curved+domain.ToJsonString()+string.Join(",",meshes.Select(m=>m.DataCRC(0)));
        if(key!=signature || task==null){
            cancellation?.Cancel();cancellation=new CancellationTokenSource();var token=cancellation.Token;
            var copies=meshes.Select(m=>m.DuplicateMesh()).ToArray();signature=key;
            task=Task.Run(()=>{
                try {
                    var n=domain["shape"]!.AsArray().Select(v=>v!.GetValue<int>()).ToArray();
                    var solution=new JsonObject{["case"]=domain.DeepClone()};var bounds=copies.Select(m=>m.GetBoundingBox(false)).ToArray();double dx=domain["spacing"]!.GetValue<double>();
                    var o=Coordinates.Origin(solution);var origin=new Point3d(o[0],o[1],o[2]);var ax=Coordinates.Axis(solution,0)*dx;var ay=Coordinates.Axis(solution,1)*dx;var az=Coordinates.Axis(solution,2)*dx;
                    var solid=new JsonArray();
                    for(int x=0;x<n[0];x++){token.ThrowIfCancellationRequested();for(int y=0;y<n[1];y++)for(int z=0;z<n[2];z++){
                        var point=origin+x*ax+y*ay+z*az;
                        for(int m=0;m<copies.Length;m++)if(Contains(copies[m],bounds[m],point,dx*1e-5)){solid.Add((x*n[1]+y)*n[2]+z);break;}
                    }}
                    var data=new JsonObject{["kind"]="Geometry",["label"]=$"Hawa geometry: {solid.Count} solid cells",["domain"]=domain.DeepClone(),["solid"]=solid};
                    if(curved){
                        // Direction order matches Lettuce D3Q19 exactly.
                        int[][] directions={new[]{0,0,0},new[]{1,0,0},new[]{-1,0,0},new[]{0,1,0},new[]{0,-1,0},new[]{0,0,1},new[]{0,0,-1},new[]{0,1,1},new[]{0,-1,-1},new[]{0,1,-1},new[]{0,-1,1},new[]{1,0,1},new[]{-1,0,-1},new[]{1,0,-1},new[]{-1,0,1},new[]{1,1,0},new[]{-1,-1,0},new[]{1,-1,0},new[]{-1,1,0}};
                        var occupied=solid.Select(v=>v!.GetValue<int>()).ToHashSet();var links=new JsonArray();
                        foreach(int site in occupied){token.ThrowIfCancellationRequested();int[] c={site/(n[1]*n[2]),site/n[2]%n[1],site%n[2]};if(Enumerable.Range(0,3).Any(a=>c[a]<2||c[a]>=n[a]-2))throw new ArgumentException("Curved walls require two-cell domain clearance");for(int dir=1;dir<directions.Length;dir++){
                            var e=directions[dir];var f=Enumerable.Range(0,3).Select(a=>c[a]-e[a]).ToArray();if(Enumerable.Range(0,3).Any(a=>f[a]<1||f[a]>=n[a]-1))continue;
                            int index=(f[0]*n[1]+f[1])*n[2]+f[2];if(occupied.Contains(index))continue;
                            var point=origin+f[0]*ax+f[1]*ay+f[2]*az;var segment=e[0]*ax+e[1]*ay+e[2]*az;double fraction=double.PositiveInfinity;
                            foreach(var m in copies)fraction=Math.Min(fraction,LinkFraction(m,point,segment));
                            if(!double.IsFinite(fraction))throw new ArgumentException("Cannot locate wall intersection. Check geometry and spacing.");
                            links.Add(new JsonArray(dir,index,Math.Clamp(fraction,1e-6,1)));
                        }}data["wall_links"]=links;
                    }
                    return data;
                } finally {foreach(var m in copies)m.Dispose();}
            });
        }
        if(!task.IsCompleted){Message="voxelizing";string expected=signature!;OnPingDocument()?.ScheduleSolution(100,_=>{if(!Locked&&signature==expected)ExpireSolution(false);});return;}
        if(task.IsCanceled){Message="cancelled";return;}
        if(task.IsFaulted)throw task.Exception!.GetBaseException();
        var data=task.Result;Message="ready";da.SetData(0,new HawaGoo(data));da.SetData(1,data["solid"]!.AsArray().Count);
    }
    protected override void InputsMissing(){cancellation?.Cancel();task=null;signature=null;}
    public override void RemovedFromDocument(GH_Document document){InputsMissing();base.RemovedFromDocument(document);}
}

public sealed class PhysicsComponent : HawaComponent
{
    public PhysicsComponent() : base("Hawa Physics", "Physics", "Physical inlet speed, kinematic viscosity, density and collision model. Flow follows +X.", "03 Physics") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077103");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddNumberParameter("Speed", "U", "Inlet speed in m/s along +X", GH_ParamAccess.item, 1); p.AddNumberParameter("Viscosity", "nu", "Physical kinematic viscosity in m²/s", GH_ParamAccess.item, 1.5e-5); p.AddNumberParameter("Density", "rho", "Reference density in kg/m³", GH_ParamAccess.item, 1.225); p.AddTextParameter("Collision", "C", "bgk, trt, regularized or smagorinsky", GH_ParamAccess.item, "regularized"); p.AddNumberParameter("Lattice Mach", "Ma", "Low-Mach lattice scaling", GH_ParamAccess.item, .05); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddGenericParameter("Physics", "P", "Hawa physical settings", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        double u = 1, nu = 1.5e-5, rho = 1.225, ma = .05; string model = "regularized";
        da.GetData(0, ref u); da.GetData(1, ref nu); da.GetData(2, ref rho); da.GetData(3, ref model); da.GetData(4, ref ma);
        if (new[] { u, nu, rho, ma }.Any(v => !double.IsFinite(v) || v <= 0)) throw new ArgumentException("Physical parameters must be finite and positive");
        da.SetData(0, new HawaGoo(new JsonObject { ["kind"] = "Physics", ["label"] = $"{model}, U={u:g3} m/s", ["speed"] = u, ["viscosity"] = nu, ["density"] = rho, ["mach"] = ma, ["collision"] = model.ToLowerInvariant() }));
    }
}

public sealed class BoundariesComponent : HawaComponent
{
    public BoundariesComponent() : base("Hawa Boundaries", "Boundary", "Six domain-face boundaries. Periodic faces must be paired; flow is +X.", "03 Physics") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077104");
    protected override void RegisterInputParams(GH_InputParamManager p) { var names = new[] { "X-", "X+", "Y-", "Y+", "Z-", "Z+" }; var defaults = new[] { "inlet", "outlet", "periodic", "periodic", "wall", "slip" }; for (int i = 0; i < 6; i++) p.AddTextParameter(names[i], names[i], "inlet, outlet, wall, slip or periodic", GH_ParamAccess.item, defaults[i]); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddGenericParameter("Boundaries", "B", "Face assignments", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da) { var types = new JsonArray(); for (int i = 0; i < 6; i++) { string t = ""; da.GetData(i, ref t); types.Add(t.ToLowerInvariant()); } da.SetData(0, new HawaGoo(new JsonObject { ["kind"] = "Boundaries", ["label"] = "Hawa boundary faces", ["boundaries"] = types })); }
}

public sealed class CaseComponent : HawaComponent
{
    public CaseComponent() : base("Hawa Case", "Case", "Combine domain, geometry, physics and boundary assignments", "04 Case") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077105");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddGenericParameter("Domain", "D", "Hawa Domain", GH_ParamAccess.item); p.AddGenericParameter("Geometry", "G", "Optional voxelized obstacles", GH_ParamAccess.item); p[1].Optional = true; p.AddGenericParameter("Physics", "P", "Hawa Physics", GH_ParamAccess.item); p.AddGenericParameter("Boundaries", "B", "Optional face settings", GH_ParamAccess.item); p[3].Optional = true; }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddGenericParameter("Case", "C", "Serializable Hawa case", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        if(new[]{1,3}.Any(i=>Params.Input[i].Sources.Count>0 && !Params.Input[i].VolatileData.AllData(true).Any(v=>v!=null)))return;
        var domain = ReadObject(da, 0); var physics = ReadObject(da, 2); var result = domain.DeepClone().AsObject();
        foreach (var pair in physics.Where(p => p.Key != "kind" && p.Key != "label")) result[pair.Key] = pair.Value?.DeepClone();
        if (Params.Input[1].VolatileDataCount > 0) { var geometry = ReadObject(da, 1); if (domain.ToJsonString() != geometry["domain"]!.ToJsonString()) throw new ArgumentException("Geometry was voxelized on a different domain"); result["solid"] = geometry["solid"]!.DeepClone(); if(geometry["wall_links"]!=null)result["wall_links"]=geometry["wall_links"]!.DeepClone(); }
        if (Params.Input[3].VolatileDataCount > 0) result["boundaries"] = ReadObject(da, 3)["boundaries"]!.DeepClone();
        result["kind"] = "Case"; result["label"] = "Hawa wind case";
        da.SetData(0, new HawaGoo(result));
    }
}

public sealed class ExampleComponent : HawaComponent
{
    public ExampleComponent() : base("Hawa Example", "Example", "Numerical verification case: tgv2d-bgk, tgv3d-bgk, tgv2d-trt, tgv2d-smagorinsky, tgv3d-smagorinsky, cavity2d-bgk or poiseuille2d-guo", "04 Case") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077106");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddTextParameter("Example", "E", "Case name", GH_ParamAccess.item, "tgv3d-bgk"); p.AddIntegerParameter("Size", "N", "Sites per axis", GH_ParamAccess.item, 16); }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddGenericParameter("Case", "C", "Example case", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da) { string name = "tgv3d-bgk"; int n = 16; da.GetData(0, ref name); da.GetData(1, ref n); if (n < 8 || n > 128) throw new ArgumentException("Example size must be 8–128"); da.SetData(0, new HawaGoo(new JsonObject { ["kind"] = "Case", ["label"] = name, ["example"] = name, ["size"] = n, ["origin"] = Numbers(new[] { 0d, 0d, 0d }), ["spacing"] = 1d })); }
}
