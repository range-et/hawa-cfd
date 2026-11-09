using System.Drawing;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Hawa.Grasshopper;

internal static class FieldTools {
    internal static JsonObject Frames(IGH_DataAccess da,int index){
        var inputs=new List<global::Grasshopper.Kernel.Types.IGH_Goo>();da.GetDataList(index,inputs);
        var frames=new List<JsonObject>();
        foreach(var input in inputs.Where(v=>v!=null)){
            var h=input is HawaGoo value?value:(input as global::Grasshopper.Kernel.Types.GH_ObjectWrapper)?.Value as HawaGoo;
            if(h==null)throw new ArgumentException("Connect Field Snapshot or Playback frames");
            var f=h.Data;if(f["frame"]==null||f["case"]==null)throw new ArgumentException("Connect immutable field frames");frames.Add(f);
        }
        if(frames.Count<1||frames.Count>16)throw new ArgumentException("Use 1..16 field frames");
        var result=frames[0].DeepClone().AsObject();
        if(frames.Count>1)result["frames"]=new JsonArray(frames.Select(f=>f["frame"]!.DeepClone()).ToArray());
        return result;
    }
    internal static JsonObject Request(JsonObject frame,string action,string field="speed")=>new(){["op"]="field",["action"]=action,["frame"]=frame["frame"]!.DeepClone(),["frames"]=frame["frames"]?.DeepClone()??(action=="plane"&&frame["case"]?["shape"]?.AsArray().Count==3?new JsonArray(frame["frame"]!.DeepClone()):null),["field"]=field};
    internal static JsonObject World(JsonObject frame)=>new(){["case"]=frame["case"]!.DeepClone()};
    internal static Color ColorAt(double t,string palette){t=Math.Clamp(t,0,1);Color[] colors=palette.ToLowerInvariant() switch{"spectrum"=>new[]{Color.DarkBlue,Color.Cyan,Color.Lime,Color.Yellow,Color.Red},"diverging"=>new[]{Color.RoyalBlue,Color.White,Color.Firebrick},_=>new[]{Color.FromArgb(8,48,107),Color.FromArgb(0,160,180),Color.FromArgb(150,235,140)}};double u=t*(colors.Length-1);int i=Math.Min(colors.Length-2,(int)u);double f=u-i;return Color.FromArgb((int)(colors[i].R*(1-f)+colors[i+1].R*f),(int)(colors[i].G*(1-f)+colors[i+1].G*f),(int)(colors[i].B*(1-f)+colors[i+1].B*f));}
    internal static Mesh Mesh(JsonObject data,JsonObject frame){var m=new Mesh();foreach(var p in data["vertices"]!.AsArray())m.Vertices.Add(Coordinates.World(World(frame),p!));foreach(var f in data["faces"]!.AsArray())m.Faces.AddFace(f![0]!.GetValue<int>(),f[1]!.GetValue<int>(),f[2]!.GetValue<int>());m.Normals.ComputeNormals();return m;}
}

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

public sealed class PlaneFieldComponent:HawaQueryComponent {
    protected override void InputsMissing(){base.InputsMissing();Message="waiting for frames";}
    public PlaneFieldComponent():base("Hawa Plane Field","Plane","Sample an arbitrary rectangle with shared colors and equal-value contours","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077123");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Frames","F","One or more snapshots at the same absolute time. Finest containing domain supplies each sample.",GH_ParamAccess.list);p.AddRectangleParameter("Rectangle","R","Sampling plane and extents",GH_ParamAccess.item);p.AddIntegerParameter("Resolution","N","Samples per side, 2..100",GH_ParamAccess.item,30);p.AddTextParameter("Field","Q","speed, pressure, cp, vorticity, q, ux, uy, uz, density",GH_ParamAccess.item,"speed");p.AddGenericParameter("Colors","C","Color Map",GH_ParamAccess.item);p.AddNumberParameter("Contour levels","L","Optional levels",GH_ParamAccess.list);p[5].Optional=true;}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddMeshParameter("Mesh","M","Colored fluid slice",GH_ParamAccess.item);p.AddLineParameter("Contours","C","Equal-value segments",GH_ParamAccess.list);p.AddNumberParameter("Values","V","Scalar samples",GH_ParamAccess.list);}
    protected override void SolveHawa(IGH_DataAccess da){var frame=FieldTools.Frames(da,0);Rectangle3d rect=default;int n=30;string field="speed";da.GetData(1,ref rect);da.GetData(2,ref n);da.GetData(3,ref field);var colors=ReadObject(da,4);var levels=new List<double>();da.GetDataList(5,levels);if(n<2||n>100)throw new ArgumentException("Resolution 2..100");var world=FieldTools.World(frame);var points=new JsonArray();var mesh=new Mesh();for(int i=0;i<n;i++)for(int j=0;j<n;j++){var p=rect.PointAt(i/(double)(n-1),j/(double)(n-1));mesh.Vertices.Add(p);points.Add(Coordinates.Grid(world,p));}var req=FieldTools.Request(frame,"plane",field);req["points"]=points;req["shape"]=new JsonArray(n,n);req["levels"]=Numbers(levels);var data=View(req);if(data==null){mesh.Dispose();return;}var values=data["values"]!.AsArray().Select(x=>x!.GetValue<double>()).ToArray();var valid=data["valid"]!.AsArray().Select(x=>x!.GetValue<bool>()).ToArray();double lo=colors["min"]!.GetValue<double>(),hi=colors["max"]!.GetValue<double>();foreach(var v in values)mesh.VertexColors.Add(FieldTools.ColorAt((v-lo)/(hi-lo),colors["palette"]!.GetValue<string>()));for(int i=0;i<n-1;i++)for(int j=0;j<n-1;j++){int a=i*n+j;if(valid[a]&&valid[a+n]&&valid[a+n+1]&&valid[a+1])mesh.Faces.AddFace(a,a+n,a+n+1,a+1);}if(data["mesh_vertices"] is JsonArray clipped){mesh.Dispose();mesh=new Mesh();foreach(var point in clipped)mesh.Vertices.Add(Coordinates.World(world,point!));foreach(var face in data["mesh_faces"]!.AsArray())mesh.Faces.AddFace(face![0]!.GetValue<int>(),face[1]!.GetValue<int>(),face[2]!.GetValue<int>());foreach(var value in data["mesh_values"]!.AsArray())mesh.VertexColors.Add(FieldTools.ColorAt((value!.GetValue<double>()-lo)/(hi-lo),colors["palette"]!.GetValue<string>()));Message=$"domains: {data["collection"]!["domains"]}";}mesh.Normals.ComputeNormals();da.SetData(0,mesh);da.SetDataList(2,values);da.SetDataList(1,data["lines"]!.AsArray().Select(l=>new Line(Coordinates.World(world,l![0]!),Coordinates.World(world,l[1]!))));}

}

public sealed class IsosurfaceComponent:HawaQueryComponent {
    public IsosurfaceComponent():base("Hawa Isosurface","Iso","Equal-value surface. Solid cells are excluded.","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077124");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Frames","F","One or more snapshots at the same absolute time. Finest containing domain supplies each sample.",GH_ParamAccess.list);p.AddTextParameter("Field","Q","Scalar field",GH_ParamAccess.item,"speed");p.AddNumberParameter("Level","V","Surface value",GH_ParamAccess.item,.5);p.AddIntegerParameter("Stride","S","Extraction spacing, 1..16",GH_ParamAccess.item,2);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddMeshParameter("Surface","M","Isosurface mesh",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){var frame=FieldTools.Frames(da,0);string field="speed";double level=.5;int stride=2;da.GetData(1,ref field);da.GetData(2,ref level);da.GetData(3,ref stride);var req=FieldTools.Request(frame,"isosurface",field);req["level"]=level;req["stride"]=stride;var data=View(req);if(data==null)return;da.SetData(0,FieldTools.Mesh(data,frame));}
}

public sealed class FlowDisplayComponent:HawaQueryComponent {
    public FlowDisplayComponent():base("Hawa Flow Display","Flow","3D RK4 streamlines and colored tubes on a captured frame","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077129");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Frames","F","One or more snapshots at the same absolute time. Finest containing domain supplies each sample.",GH_ParamAccess.list);p.AddPointParameter("Seeds","P","Seed points",GH_ParamAccess.list);p.AddGenericParameter("Colors","C","Color Map",GH_ParamAccess.item);p.AddTextParameter("Field","Q","Color field",GH_ParamAccess.item,"speed");p.AddIntegerParameter("Steps","N","Maximum 2000",GH_ParamAccess.item,150);p.AddNumberParameter("Radius","R","Tube radius in model units",GH_ParamAccess.item,.03);p.AddBooleanParameter("Backward","B","Trace against the velocity",GH_ParamAccess.item,false);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddCurveParameter("Lines","C","3D streamlines",GH_ParamAccess.list);p.AddMeshParameter("Tubes","M","Colored stream tubes",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){var frame=FieldTools.Frames(da,0);var seeds=new List<Point3d>();da.GetDataList(1,seeds);var map=ReadObject(da,2);string field="speed";int steps=150;double radius=.03;bool backward=false;da.GetData(3,ref field);da.GetData(4,ref steps);da.GetData(5,ref radius);da.GetData(6,ref backward);if(!double.IsFinite(radius)||radius<0)throw new ArgumentException("Radius must be nonnegative");var world=FieldTools.World(frame);var req=FieldTools.Request(frame,"trace",field);req["seeds"]=new JsonArray(seeds.Select(p=>(JsonNode)Coordinates.Grid(world,p)).ToArray());req["steps"]=steps;req["direction"]=backward?-1:1;var data=View(req);if(data==null)return;var curves=new List<Curve>();var mesh=new Mesh();double lo=map["min"]!.GetValue<double>(),hi=map["max"]!.GetValue<double>();string palette=map["palette"]!.GetValue<string>();int pathIndex=0;foreach(var path in data["paths"]!.AsArray()){var points=path!.AsArray().Select(p=>Coordinates.World(world,p!)).ToArray();curves.Add(new PolylineCurve(points));if(radius>0){int start=mesh.Vertices.Count;for(int i=0;i<points.Length;i++){var tangent=points[Math.Min(i+1,points.Length-1)]-points[Math.Max(0,i-1)];var plane=new Plane(points[i],tangent);var color=FieldTools.ColorAt((data["values"]![pathIndex]![i]!.GetValue<double>()-lo)/(hi-lo),palette);for(int j=0;j<6;j++){double a=j*Math.PI/3;mesh.Vertices.Add(plane.PointAt(radius*Math.Cos(a),radius*Math.Sin(a)));mesh.VertexColors.Add(color);}if(i>0)for(int j=0;j<6;j++){int a=start+(i-1)*6+j,b=start+(i-1)*6+(j+1)%6;mesh.Faces.AddFace(a,b,b+6,a+6);}}}pathIndex++;}mesh.Normals.ComputeNormals();da.SetDataList(0,curves);da.SetData(1,mesh);}
}

public sealed class SurfaceFieldComponent:HawaQueryComponent {
    public SurfaceFieldComponent():base("Hawa Surface Field","Surface","Sample a scalar outside the surface along outward normals. Invalid samples are reported and faces omitted.","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077130");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Frames","F","One or more snapshots at the same absolute time. Finest containing domain supplies each sample.",GH_ParamAccess.list);p.AddMeshParameter("Surface","M","Outward oriented mesh",GH_ParamAccess.item);p.AddTextParameter("Field","Q","pressure or cp etc.",GH_ParamAccess.item,"pressure");p.AddNumberParameter("Offset","D","Sampling offset in model units. Use at least one cell.",GH_ParamAccess.item,1);p.AddGenericParameter("Colors","C","Color Map",GH_ParamAccess.item);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddMeshParameter("Colored surface","M","Approximate offset surface field",GH_ParamAccess.item);p.AddBooleanParameter("Valid","V","Sample validity",GH_ParamAccess.list);p.AddNumberParameter("Values","Q","Scalar values",GH_ParamAccess.list);}
    protected override void SolveHawa(IGH_DataAccess da){var f=FieldTools.Frames(da,0);Mesh input=null!;string field="pressure";double offset=1;da.GetData(1,ref input);da.GetData(2,ref field);da.GetData(3,ref offset);var colors=ReadObject(da,4);if(!double.IsFinite(offset)||offset<0)throw new ArgumentException("Offset must be nonnegative");var mesh=input.DuplicateMesh();mesh.Normals.ComputeNormals();var world=FieldTools.World(f);var points=new JsonArray();for(int i=0;i<mesh.Vertices.Count;i++)points.Add(Coordinates.Grid(world,(Point3d)mesh.Vertices[i]+offset*(Vector3d)mesh.Normals[i]));var req=FieldTools.Request(f,"sample",field);req["points"]=points;var r=View(req);if(r==null){mesh.Dispose();return;}var valid=r["valid"]!.AsArray().Select(x=>x!.GetValue<bool>()).ToArray();var values=r["values"]!.AsArray().Select(x=>x!.GetValue<double>()).ToArray();mesh.VertexColors.Clear();foreach(var v in values)mesh.VertexColors.Add(FieldTools.ColorAt((v-colors["min"]!.GetValue<double>())/(colors["max"]!.GetValue<double>()-colors["min"]!.GetValue<double>()),colors["palette"]!.GetValue<string>()));mesh.Faces.DeleteFaces(Enumerable.Range(0,mesh.Faces.Count).Where(i=>{var a=mesh.Faces[i];return !valid[a.A]||!valid[a.B]||!valid[a.C]||(a.IsQuad&&!valid[a.D]);}));da.SetData(0,mesh);da.SetDataList(1,valid);da.SetDataList(2,values);Message="offset sample";}
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
