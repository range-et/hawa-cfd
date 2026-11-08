using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Hawa.Grasshopper;

public sealed class HullComponent : HawaComponent
{
    public HullComponent() : base("Hawa Parametric Hull", "Hull", "Closed canoe hull with a flat deck. Length and mesh volume stay fixed while bow, stern and beam/draft ratio change. Model units: meters.", "02 Geometry") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077116");
    protected override void RegisterInputParams(GH_InputParamManager p) {
        p.AddNumberParameter("Length", "L", "Fixed hull length in meters", GH_ParamAccess.item, 8);
        p.AddNumberParameter("Volume", "V", "Fixed closed mesh volume in cubic meters", GH_ParamAccess.item, 6);
        p.AddNumberParameter("Bow fullness", "Bow", "Upstream taper exponent: 0.4 to 1.6", GH_ParamAccess.item, 0.8);
        p.AddNumberParameter("Stern fullness", "Stern", "Downstream taper exponent: 0.4 to 1.6", GH_ParamAccess.item, 0.8);
        p.AddNumberParameter("Beam / draft", "B/D", "Width to depth ratio: 1 to 3", GH_ParamAccess.item, 2);
        p.AddPointParameter("Deck center", "O", "Center of the flat deck in meters", GH_ParamAccess.item, new Point3d(8,6,5));
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p) {
        p.AddMeshParameter("Hull", "H", "Closed hull for Hawa Geometry", GH_ParamAccess.item);
        p.AddCurveParameter("Sections", "S", "Editable-preview station polylines", GH_ParamAccess.list);
        p.AddNumberParameter("Volume", "V", "Actual closed mesh volume in cubic meters", GH_ParamAccess.item);
        p.AddTextParameter("Dimensions", "D", "Hull dimensions and physical scope", GH_ParamAccess.item);
    }
    protected override void SolveHawa(IGH_DataAccess da) {
        double length=8, volume=6, bow=.8, stern=.8, ratio=2; var origin=new Point3d(8,6,5);
        da.GetData(0,ref length); da.GetData(1,ref volume); da.GetData(2,ref bow); da.GetData(3,ref stern); da.GetData(4,ref ratio); da.GetData(5,ref origin);
        if(new[]{length,volume,bow,stern,ratio}.Any(v=>!double.IsFinite(v)||v<=0)|| !origin.IsValid || bow<.4 || bow>1.6 || stern<.4 || stern>1.6 || ratio<1 || ratio>3) throw new ArgumentException("Positive length/volume; bow/stern 0.4–1.6; beam/draft 1–3");
        const int stations=40, ring=25;
        var mesh=new Mesh();
        // Each ring runs across the underwater half ellipse. Its closing edge is the deck.
        for(int i=1;i<stations;i++) {
            double t=(double)i/stations;
            double fullness=Math.Pow(Math.Sin(Math.PI*t),t<.5?bow:stern);
            for(int j=0;j<ring;j++) {double angle=Math.PI*j/(ring-1);mesh.Vertices.Add(length*(t-.5),ratio*.5*fullness*Math.Cos(angle),-fullness*Math.Sin(angle));}
        }
        for(int i=0;i<stations-2;i++) for(int j=0;j<ring;j++) {int a=i*ring+j,b=i*ring+(j+1)%ring;mesh.Faces.AddFace(a,b,b+ring,a+ring);}
        int nose=mesh.Vertices.Add(-length*.5,0,0), tail=mesh.Vertices.Add(length*.5,0,0);
        for(int j=0;j<ring;j++){mesh.Faces.AddFace(nose,(j+1)%ring,j);int a=(stations-2)*ring+j,b=(stations-2)*ring+(j+1)%ring;mesh.Faces.AddFace(tail,a,b);}
        mesh.UnifyNormals(); if(mesh.SolidOrientation()<0)mesh.Flip(true,true,true);
        double raw=Math.Abs(VolumeMassProperties.Compute(mesh)?.Volume??0);if(raw<=0)throw new Exception("Hull volume failed");
        double scale=Math.Sqrt(volume/raw); mesh.Transform(Transform.Scale(Plane.WorldXY,1,scale,scale));mesh.Transform(Transform.Translation((Vector3d)origin));mesh.Normals.ComputeNormals();mesh.Compact();
        if(!mesh.IsValid||!mesh.IsClosed)throw new Exception("Hull must be a valid closed mesh");
        var sections=new List<Curve>();for(int i=3;i<stations-1;i+=4){var points=Enumerable.Range(0,ring).Select(j=>(Point3d)mesh.Vertices[(i-1)*ring+j]).ToList();points.Add(points[0]);sections.Add(new PolylineCurve(points));}
        double actual=Math.Abs(VolumeMassProperties.Compute(mesh)!.Volume); var bounds=mesh.GetBoundingBox(true);
        da.SetData(0,mesh);da.SetDataList(1,sections);da.SetData(2,actual);da.SetData(3,$"Length: {length:g4} m\nBeam: {bounds.Max.Y-bounds.Min.Y:g4} m\nDraft: {bounds.Max.Z-bounds.Min.Z:g4} m\nVolume: {actual:g6} m³\nSingle phase: fully submerged hull. No waves or buoyancy.");
    }
}

public sealed class EvaluateComponent : HawaComponent
{
    private string? session, signature;
    private JsonObject? result;
    private bool first = true, requireDisable;
    public EvaluateComponent() : base("Hawa Evaluate", "Evaluate", "Complete a fresh fixed-duration CFD run before emitting fitness. Suitable for Galapagos. Blocks the GH solution until complete; last candidate only is cached. Enable after opening.", "05 Solve") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077117");
    protected override void RegisterInputParams(GH_InputParamManager p) {
        p.AddGenericParameter("Case", "C", "Closed submerged-body case", GH_ParamAccess.item);
        p.AddTextParameter("Device", "D", "auto, cpu, mps or cuda:0", GH_ParamAccess.item, "auto");
        p.AddIntegerParameter("Iterations", "N", "Same total duration for each candidate", GH_ParamAccess.item, 200);
        p.AddIntegerParameter("Average window", "W", "Mean force over the final W iterations", GH_ParamAccess.item, 20);
        p.AddNumberParameter("Reference volume", "V", "Fixed reference volume in cubic meters", GH_ParamAccess.item, 6);
        p.AddBooleanParameter("Enable", "E", "True evaluates each changed candidate; false emits no fitness", GH_ParamAccess.item, false);
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p) {
        p.AddNumberParameter("Fitness", "F", "Minimize mean X resistance / (0.5 rho U² V_ref^(2/3))", GH_ParamAccess.item);
        p.AddGenericParameter("Solution", "S", "Completed candidate for Slice and Streamlines", GH_ParamAccess.item);
        p.AddNumberParameter("Resistance", "Fx", "Mean X momentum-exchange force in newtons", GH_ParamAccess.item);
        p.AddTextParameter("Report", "R", "Backend, duration, force and volume diagnostics", GH_ParamAccess.item);
    }
    protected override void SolveHawa(IGH_DataAccess da) {
        bool enable=false;da.GetData(5,ref enable);
        if(first){first=false;requireDisable=enable;}
        if(!enable)requireDisable=false;
        if(requireDisable){Message="enable again";da.SetData(3,"Set Enable false, then true to evaluate this opened definition.");return;}
        if(!enable){Message="disabled";da.SetData(3,"Enable to evaluate. Fitness stays empty while disabled.");return;}
        var spec=ReadObject(da,0);string device="auto";int steps=200,window=20;double volume=6;
        da.GetData(1,ref device);da.GetData(2,ref steps);da.GetData(3,ref window);da.GetData(4,ref volume);
        var request=new JsonObject{["op"]="evaluate",["case"]=spec.DeepClone(),["device"]=device,["steps"]=steps,["window"]=window,["reference_volume"]=volume};
        string key=request.ToJsonString();if(key!=signature||result==null){Close();result=EmbeddedRuntime.Call(request);session=result["status"]!["session"]!.GetValue<string>();signature=key;}
        var status=result["status"]!;Message=status["backend"]!["selected"]!.GetValue<string>()+" / completed";
        da.SetData(0,result["fitness"]!.GetValue<double>());da.SetData(1,new HawaGoo(new JsonObject{["kind"]="Solution",["label"]="Hawa evaluated hull",["session"]=session,["case"]=spec.DeepClone()}));da.SetData(2,result["force_newtons"]![0]!.GetValue<double>());
        double fx=result["force_newtons"]![0]!.GetValue<double>();
        double spread=result["force_std_newtons"]![0]!.GetValue<double>();
        double voxels=result["voxel_volume"]!.GetValue<double>();
        double fitness=result["fitness"]!.GetValue<double>();
        da.SetData(3,$"Backend: {status["backend"]!["selected"]}\nIterations: {steps}; final window: {window}\nFitness (minimize): {fitness:g8}\nMean X force: {fx:g7} N\nX force std: {spread:g5} N\nVoxel volume: {voxels:g5} m³\nFixed-duration submerged hull. No free surface.");
    }
    private void Close(){if(session!=null){try{EmbeddedRuntime.Call(Request("close",session));}catch{}session=null;}result=null;signature=null;}
    public override void RemovedFromDocument(GH_Document document){Close();base.RemovedFromDocument(document);}
}
