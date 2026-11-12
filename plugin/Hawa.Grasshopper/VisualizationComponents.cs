using System.Drawing;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Hawa.Grasshopper;

public sealed class DomainPreviewComponent:HawaComponent {
    private List<Line> edges=new();
    protected override void InputsMissing(){edges.Clear();}
    public override void DrawViewportWires(IGH_PreviewArgs args){foreach(var edge in Params.Output[0].VolatileData.AllData(true).OfType<global::Grasshopper.Kernel.Types.GH_Line>().Select(v=>v.Value))args.Display.DrawLine(edge,Color.FromArgb(65,85,95),1);}
    public DomainPreviewComponent():base("Hawa Domain Preview","Bounds","Actual lattice wireframe and face centers","01 Domain"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077119");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Domain","D","Hawa domain",GH_ParamAccess.item);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddLineParameter("Edges","E","Domain wireframe",GH_ParamAccess.list);p.AddPointParameter("Face centers","P","Label locations",GH_ParamAccess.list);p.AddTextParameter("Labels","L","Boundary names",GH_ParamAccess.list);}
    protected override void SolveHawa(IGH_DataAccess da){var d=ReadObject(da,0);var s=new JsonObject{["case"]=d};var n=d["shape"]!.AsArray().Select(x=>x!.GetValue<int>()-1).ToArray();Point3d P(double x,double y,double z)=>Coordinates.World(s,new JsonArray(x,y,z));var lines=new List<Line>();for(int a=0;a<3;a++)for(int b=0;b<2;b++)for(int c=0;c<2;c++){var lo=new double[3];lo[(a+1)%3]=b*n[(a+1)%3];lo[(a+2)%3]=c*n[(a+2)%3];var hi=(double[])lo.Clone();hi[a]=n[a];lines.Add(new Line(P(lo[0],lo[1],lo[2]),P(hi[0],hi[1],hi[2])));}edges=lines;da.SetDataList(0,lines);var centers=new List<Point3d>();for(int a=0;a<3;a++)for(int side=0;side<2;side++){var q=n.Select(x=>x*.5).ToArray();q[a]=side*n[a];centers.Add(P(q[0],q[1],q[2]));}da.SetDataList(1,centers);da.SetDataList(2,new[]{"X-","X+","Y-","Y+","Z-","Z+"});}
}

public sealed class SeedsComponent:HawaComponent {
    public SeedsComponent():base("Hawa Seed Points","Seeds","Uniform 3D seeds inside a Rhino box. Flatten one dimension for a seed plane.","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077120");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddBoxParameter("Box","B","Seed region",GH_ParamAccess.item);p.AddIntegerParameter("X count","X","Count",GH_ParamAccess.item,2);p.AddIntegerParameter("Y count","Y","Count",GH_ParamAccess.item,8);p.AddIntegerParameter("Z count","Z","Count",GH_ParamAccess.item,8);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddPointParameter("Seeds","P","Seed points",GH_ParamAccess.list);}
    protected override void SolveHawa(IGH_DataAccess da){Box box=default;int nx=2,ny=8,nz=8;da.GetData(0,ref box);da.GetData(1,ref nx);da.GetData(2,ref ny);da.GetData(3,ref nz);if(Math.Min(nx,Math.Min(ny,nz))<1||(long)nx*ny*nz>2000)throw new ArgumentException("Seed count must be 1..2000");var points=new List<Point3d>();for(int i=0;i<nx;i++)for(int j=0;j<ny;j++)for(int k=0;k<nz;k++)points.Add(box.PointAt((i+.5)/nx,(j+.5)/ny,(k+.5)/nz));da.SetDataList(0,points);}
}

public sealed class SnapshotComponent:HawaQueryComponent {
    private JsonObject? previous;
    private string? previousKey;
    public SnapshotComponent():base("Hawa Field Snapshot","Frame","Capture an immutable field frame. Keep the last completed frame visible while the next capture runs.","06 Results"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077121");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Solution","S","Solution",GH_ParamAccess.item);p.AddBooleanParameter("Mean","M","Mean sampled every five iterations",GH_ParamAccess.item,false);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Frame","F","Last completed immutable frame",GH_ParamAccess.item);p.AddNumberParameter("Time","T","Physical time of the displayed frame",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){
        var s=ReadObject(da,0);bool mean=false;da.GetData(1,ref mean);
        string identity=s["session"]!.GetValue<string>()+":"+mean;
        var last=identity==previousKey?previous:null;
        var frame=View(new JsonObject{["op"]="field",["action"]="capture",["session"]=s["session"]!.DeepClone(),["mean"]=mean,["revision"]=s["revision"]?.DeepClone()},true);
        previous=frame??last;previousKey=identity;
        if(previous==null)return;
        var output=previous.DeepClone().AsObject();output["kind"]="Frame";
        da.SetData(0,new HawaGoo(output));da.SetData(1,output["time"]!.GetValue<double>());
    }
    protected override void InputsMissing(){previous=null;previousKey=null;base.InputsMissing();}
}

public sealed class ColorMapComponent:HawaComponent {
    public ColorMapComponent():base("Hawa Color Map","Colors","Shared fixed color range and legend","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077122");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddTextParameter("Palette","P","blue-green, spectrum or diverging",GH_ParamAccess.item,"blue-green");p.AddNumberParameter("Minimum","L","Lower limit",GH_ParamAccess.item,0);p.AddNumberParameter("Maximum","H","Upper limit",GH_ParamAccess.item,1);p.AddTextParameter("Units","U","Legend units",GH_ParamAccess.item,"m/s");}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Map","M","Shared display settings",GH_ParamAccess.item);p.AddColourParameter("Colors","C","Legend colors",GH_ParamAccess.list);p.AddTextParameter("Labels","L","Legend labels",GH_ParamAccess.list);}
    protected override void SolveHawa(IGH_DataAccess da){string palette="blue-green",units="m/s";double lo=0,hi=1;da.GetData(0,ref palette);da.GetData(1,ref lo);da.GetData(2,ref hi);da.GetData(3,ref units);if(!new[]{"blue-green","spectrum","diverging"}.Contains(palette)||!double.IsFinite(lo)||!double.IsFinite(hi)||hi<=lo)throw new ArgumentException("Select a palette and finite increasing limits");da.SetData(0,new HawaGoo(new JsonObject{["kind"]="ColorMap",["palette"]=palette,["min"]=lo,["max"]=hi,["units"]=units}));da.SetDataList(1,Enumerable.Range(0,9).Select(i=>FieldTools.ColorAt(i/8d,palette)));da.SetDataList(2,Enumerable.Range(0,9).Select(i=>$"{lo+(hi-lo)*i/8:g4} {units}"));}
}

public sealed class IsosurfaceComponent:HawaQueryComponent {
    public IsosurfaceComponent():base("Hawa Isosurface","Iso","Equal-value surface. Solid cells are excluded.","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077124");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Frames","F","One or more snapshots at the same absolute time. Finest containing domain supplies each sample.",GH_ParamAccess.list);p.AddTextParameter("Field","Q","Scalar field",GH_ParamAccess.item,"speed");p.AddNumberParameter("Level","V","Surface value",GH_ParamAccess.item,.5);p.AddIntegerParameter("Stride","S","Extraction spacing, 1..16",GH_ParamAccess.item,2);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddMeshParameter("Surface","M","Isosurface mesh",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){var frame=FieldTools.Frames(da,0);string field="speed";double level=.5;int stride=2;da.GetData(1,ref field);da.GetData(2,ref level);da.GetData(3,ref stride);var req=FieldTools.Request(frame,"isosurface",field);req["level"]=level;req["stride"]=stride;var data=View(req);if(data==null)return;da.SetData(0,FieldTools.Mesh(data,frame));}
}

public sealed class LegendComponent:HawaComponent {
    private readonly List<(Point3d point,string text)> labels=new();
    public LegendComponent():base("Hawa Legend","Legend","Colored legend with fixed range, units and viewport labels","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077136");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Map","M","Hawa Color Map",GH_ParamAccess.item);p.AddPlaneParameter("Plane","P","Legend origin and orientation",GH_ParamAccess.item,Plane.WorldXY);p.AddNumberParameter("Height","H","Legend height in model units",GH_ParamAccess.item,4);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddMeshParameter("Legend","L","Colored legend mesh",GH_ParamAccess.item);p.AddTextParameter("Labels","T","Range labels",GH_ParamAccess.list);p.AddPointParameter("Locations","P","Label locations",GH_ParamAccess.list);}
    protected override void InputsMissing(){labels.Clear();}
    protected override void SolveHawa(IGH_DataAccess da){labels.Clear();var map=ReadObject(da,0);Plane plane=Plane.WorldXY;double height=4;da.GetData(1,ref plane);da.GetData(2,ref height);if(!plane.IsValid||!double.IsFinite(height)||height<=0)throw new ArgumentException("Valid plane and positive height required");var mesh=new Mesh();string palette=map["palette"]!.GetValue<string>(),units=map["units"]!.GetValue<string>();double lo=map["min"]!.GetValue<double>(),hi=map["max"]!.GetValue<double>();for(int i=0;i<=32;i++){double t=i/32d;mesh.Vertices.Add(plane.PointAt(0,height*t));mesh.Vertices.Add(plane.PointAt(height*.08,height*t));mesh.VertexColors.Add(FieldTools.ColorAt(t,palette));mesh.VertexColors.Add(FieldTools.ColorAt(t,palette));if(i>0)mesh.Faces.AddFace(2*i-2,2*i-1,2*i+1,2*i);}mesh.Normals.ComputeNormals();for(int i=0;i<=4;i++)labels.Add((plane.PointAt(height*.18,height*i/4),$"{lo+(hi-lo)*i/4:g4} {units}"));da.SetData(0,mesh);da.SetDataList(1,labels.Select(x=>x.text));da.SetDataList(2,labels.Select(x=>x.point));}
    public override void DrawViewportWires(IGH_PreviewArgs args){var text=Params.Output[1].VolatileData.AllData(true).OfType<global::Grasshopper.Kernel.Types.GH_String>().Select(v=>v.Value).ToArray();var points=Params.Output[2].VolatileData.AllData(true).OfType<global::Grasshopper.Kernel.Types.GH_Point>().Select(v=>v.Value).ToArray();for(int i=0;i<Math.Min(text.Length,points.Length);i++)args.Display.Draw2dText(text[i],Color.FromArgb(15,17,19),points[i],false,12);}
}
