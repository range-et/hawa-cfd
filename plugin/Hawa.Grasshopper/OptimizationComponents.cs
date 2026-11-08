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
    private string? job, signature;
    private bool first = true, requireDisable, wasCancelled;
    public EvaluateComponent() : base("Hawa Evaluate", "Evaluate", "Cancellable background evaluation. Outputs fitness only for the completed current candidate. Use Hawa Search for asynchronous optimization.", "05 Solve") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077117");
    protected override void RegisterInputParams(GH_InputParamManager p) {
        p.AddGenericParameter("Case", "C", "Closed submerged-body case", GH_ParamAccess.item);
        p.AddTextParameter("Device", "D", "auto, cpu, mps or cuda:0", GH_ParamAccess.item, "auto");
        p.AddIntegerParameter("Iterations", "N", "Duration per candidate", GH_ParamAccess.item, 200);
        p.AddIntegerParameter("Average window", "W", "Final force averaging window", GH_ParamAccess.item, 20);
        p.AddNumberParameter("Reference volume", "V", "Fixed reference volume in m³", GH_ParamAccess.item, 6);
        p.AddBooleanParameter("Enable", "E", "False cancels and clears the current job", GH_ParamAccess.item, false);
        p.AddBooleanParameter("Pause", "P", "Pause at the next batch boundary", GH_ParamAccess.item, false);
        p.AddBooleanParameter("Cancel", "X", "Cancel. Disable and enable to restart", GH_ParamAccess.item, false);
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p) {
        p.AddNumberParameter("Fitness", "F", "Completed current fitness only", GH_ParamAccess.item);
        p.AddGenericParameter("Solution", "S", "Completed candidate", GH_ParamAccess.item);
        p.AddNumberParameter("Resistance", "Fx", "Mean X force in N", GH_ParamAccess.item);
        p.AddTextParameter("Report", "R", "Progress or final diagnostics", GH_ParamAccess.item);
        p.AddTextParameter("Candidate", "ID", "Completed unique job ID", GH_ParamAccess.item);
    }
    internal void RequestCandidate(){Close();ExpireSolution(false);}
    protected override void SolveHawa(IGH_DataAccess da) {
        bool enable=false,pause=false,cancel=false;
        da.GetData(5,ref enable);da.GetData(6,ref pause);da.GetData(7,ref cancel);
        if(first){first=false;requireDisable=enable;}
        if(!enable){requireDisable=false;wasCancelled=false;Close();Message="disabled";return;}
        if(requireDisable){Message="enable again";return;}
        if(cancel){wasCancelled=true;Close();}
        if(wasCancelled){Message="cancelled";da.SetData(3,"Disable and enable to restart.");return;}
        var doc=OnPingDocument();
        if(doc!=null && doc.Objects.Any(o=>o.GetType().Name=="GalapagosObject" && o.GetType().GetProperty("Output")?.GetValue(o) is Guid target && target==Params.Output[0].InstanceGuid))throw new InvalidOperationException("Use Hawa Search for background evaluation. The legacy Galapagos fitness connection cannot wait for an asynchronous result.");
        var spec=ReadObject(da,0);string device="auto";int steps=200,window=20;double volume=6;
        da.GetData(1,ref device);da.GetData(2,ref steps);da.GetData(3,ref window);da.GetData(4,ref volume);
        var request=new JsonObject{["op"]="evaluate_submit",["case"]=spec.DeepClone(),["device"]=device,["steps"]=steps,["window"]=window,["reference_volume"]=volume};
        string key=request.ToJsonString();
        if(key!=signature || job==null){Close();var submitted=EmbeddedRuntime.Call(request);job=submitted["job"]!.GetValue<string>();signature=key;}
        EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_control",["job"]=job,["action"]=pause?"pause":"resume"});
        var status=EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_poll",["job"]=job});
        string state=status["state"]!.GetValue<string>();Message=state;
        da.SetData(3,$"{state}: {status["steps"]} / {status["target"]} iterations\n{status["error"]}");
        if(state=="failed"){AddRuntimeMessage(GH_RuntimeMessageLevel.Error,status["error"]!.GetValue<string>());return;}
        if(state=="completed") {
            var result=status["result"]!;var runtime=result["status"]!;
            da.SetData(0,result["fitness"]!.GetValue<double>());
            da.SetData(1,new HawaGoo(new JsonObject{["kind"]="Solution",["session"]=runtime["session"]!.DeepClone(),["case"]=spec.DeepClone(),["candidate"]=job}));
            da.SetData(2,result["force_newtons"]![0]!.GetValue<double>());da.SetData(4,job);
            da.SetData(3,$"{runtime["backend"]!["selected"]} / completed\nIterations: {steps}\nFitness: {result["fitness"]}\nForce: {result["force_newtons"]} N\nSingle phase submerged body. No waves.");
        } else if(state!="cancelled") {
            string expected=job;
            OnPingDocument()?.ScheduleSolution(100,_=>{if(!Locked && job==expected)ExpireSolution(false);});
        }
    }
    public override void DocumentContextChanged(GH_Document document, GH_DocumentContext context){if(context==GH_DocumentContext.Close||context==GH_DocumentContext.Unloaded||context==GH_DocumentContext.Lock)requireDisable=true;base.DocumentContextChanged(document,context);}
    protected override void InputsMissing(){Close();}
    private void Close(){if(job!=null){try{EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_control",["job"]=job,["action"]="close"});}catch{}job=null;}signature=null;}
    public override void RemovedFromDocument(GH_Document document){Close();base.RemovedFromDocument(document);}
}
