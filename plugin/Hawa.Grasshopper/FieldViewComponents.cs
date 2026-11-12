using System.Drawing;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Geometry;

namespace Hawa.Grasshopper;

// Field views that draw what was not simulated instead of dropping it (#81, #82).
// Linked in full into the StateContracts host (tests/dotnet/StateContracts/ComponentContracts.cs).

public sealed class PlaneFieldComponent:HawaQueryComponent {
    protected override void InputsMissing(){base.InputsMissing();Message="waiting for frames";}
    public PlaneFieldComponent():base("Hawa Plane Field","Plane","Sample an arbitrary rectangle with shared colors and equal-value contours","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077123");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Frames","F","One or more snapshots at the same absolute time. Finest containing domain supplies each sample.",GH_ParamAccess.list);p.AddRectangleParameter("Rectangle","R","Sampling plane and extents",GH_ParamAccess.item);p.AddIntegerParameter("Resolution","N","Samples per side, 2..100",GH_ParamAccess.item,30);p.AddTextParameter("Field","Q","speed, pressure, cp, vorticity, q, ux, uy, uz, density",GH_ParamAccess.item,"speed");p.AddGenericParameter("Colors","C","Color Map",GH_ParamAccess.item);p.AddNumberParameter("Contour levels","L","Optional levels",GH_ParamAccess.list);p[5].Optional=true;}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddMeshParameter("Mesh","M","Colored slice tiling the rectangle. Black = not simulated: solid, invalid (no defined colour) or no-data pieces.",GH_ParamAccess.item);p.AddLineParameter("Contours","C","Equal-value segments",GH_ParamAccess.list);p.AddNumberParameter("Values","V","Scalar samples",GH_ParamAccess.list);}
    protected override void SolveHawa(IGH_DataAccess da){
        var frame=FieldTools.Frames(da,0);Rectangle3d rect=default;int n=30;string field="speed";da.GetData(1,ref rect);da.GetData(2,ref n);da.GetData(3,ref field);var colors=ReadObject(da,4);var levels=new List<double>();da.GetDataList(5,levels);
        if(n<2||n>100)throw new ArgumentException("Resolution 2..100");
        var world=FieldTools.World(frame);var points=new JsonArray();
        for(int i=0;i<n;i++)for(int j=0;j<n;j++)points.Add(Coordinates.Grid(world,rect.PointAt(i/(double)(n-1),j/(double)(n-1))));
        var req=FieldTools.Request(frame,"plane",field);req["points"]=points;req["shape"]=new JsonArray(n,n);req["levels"]=Numbers(levels);
        var data=View(req);if(data==null)return;
        double lo=colors["min"]!.GetValue<double>(),hi=colors["max"]!.GetValue<double>();string palette=colors["palette"]!.GetValue<string>();
        var mesh=new Mesh();
        foreach(var point in data["mesh_vertices"]!.AsArray())mesh.Vertices.Add(Coordinates.World(world,point!));
        foreach(var value in data["mesh_values"]!.AsArray())mesh.VertexColors.Add(FieldTools.ColorAt((value!.GetValue<double>()-lo)/(hi-lo),palette));
        foreach(var face in data["mesh_faces"]!.AsArray())mesh.Faces.AddFace(face![0]!.GetValue<int>(),face[1]!.GetValue<int>(),face[2]!.GetValue<int>());
        // Solid, invalid and no-data pieces are black, as on Slice, on their own
        // vertex copies so no fluid colour bleeds across a class boundary.
        var black=new Dictionary<int,int>();
        foreach(var key in new[]{"solid_faces","invalid_faces","no_data_faces"})foreach(var face in data[key]!.AsArray()){
            var corners=new int[3];
            for(int k=0;k<3;k++){int v=face![k]!.GetValue<int>();if(!black.TryGetValue(v,out int copy)){copy=mesh.Vertices.Add(mesh.Vertices[v]);mesh.VertexColors.Add(Color.Black);black[v]=copy;}corners[k]=copy;}
            mesh.Faces.AddFace(corners[0],corners[1],corners[2]);
        }
        Message=$"domains: {data["collection"]!["domains"]}";mesh.Normals.ComputeNormals();da.SetData(0,mesh);
        da.SetDataList(2,data["values"]!.AsArray().Select(x=>
            x!.GetValue<double>()
        ));
        da.SetDataList(1,data["lines"]!.AsArray().Select(l=>
            new Line(Coordinates.World(world,l![0]!),Coordinates.World(world,l[1]!))
        ));
    }
}

public sealed class FlowDisplayComponent:HawaQueryComponent {
    public FlowDisplayComponent():base("Hawa Flow Display","Flow","3D RK4 streamlines and colored tubes on a captured frame","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077129");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Frames","F","One or more snapshots at the same absolute time. Finest containing domain supplies each sample.",GH_ParamAccess.list);p.AddPointParameter("Seeds","P","Seed points",GH_ParamAccess.list);p.AddGenericParameter("Colors","C","Color Map",GH_ParamAccess.item);p.AddTextParameter("Field","Q","Color field",GH_ParamAccess.item,"speed");p.AddIntegerParameter("Steps","N","Maximum 2000",GH_ParamAccess.item,150);p.AddNumberParameter("Radius","R","Tube radius in model units",GH_ParamAccess.item,.03);p.AddBooleanParameter("Backward","B","Trace against the velocity",GH_ParamAccess.item,false);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddCurveParameter("Lines","C","3D streamlines; seeds with fewer than two traced points are skipped",GH_ParamAccess.list);p.AddMeshParameter("Tubes","M","Colored stream tubes; black where the colour field is not simulated",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){
        var frame=FieldTools.Frames(da,0);var seeds=new List<Point3d>();da.GetDataList(1,seeds);var map=ReadObject(da,2);string field="speed";int steps=150;double radius=.03;bool backward=false;da.GetData(3,ref field);da.GetData(4,ref steps);da.GetData(5,ref radius);da.GetData(6,ref backward);
        if(!double.IsFinite(radius)||radius<0)throw new ArgumentException("Radius must be nonnegative");
        var world=FieldTools.World(frame);var req=FieldTools.Request(frame,"trace",field);req["seeds"]=new JsonArray(seeds.Select(p=>
            (JsonNode)Coordinates.Grid(world,p)
        ).ToArray());req["steps"]=steps;req["direction"]=backward?-1:1;
        var data=View(req);if(data==null)return;
        var curves=new List<Curve>();var mesh=new Mesh();double lo=map["min"]!.GetValue<double>(),hi=map["max"]!.GetValue<double>();string palette=map["palette"]!.GetValue<string>();
        // One entry per seed: a seed that is not in the flow or stalls at once has no line to draw.
        var paths=data["paths"]!.AsArray();
        for(int pathIndex=0;pathIndex<paths.Count;pathIndex++){
            var points=paths[pathIndex]!.AsArray().Select(p=>
                Coordinates.World(world,p!)
            ).ToArray();
            if(points.Length<2)continue;
            curves.Add(new PolylineCurve(points));
            if(radius==0)continue;
            int start=mesh.Vertices.Count;
            for(int i=0;i<points.Length;i++){
                var tangent=points[Math.Min(i+1,points.Length-1)]-points[Math.Max(0,i-1)];var plane=new Plane(points[i],tangent);
                var color=data["valid"]![pathIndex]![i]!.GetValue<bool>()?FieldTools.ColorAt((data["values"]![pathIndex]![i]!.GetValue<double>()-lo)/(hi-lo),palette):Color.Black;
                for(int j=0;j<6;j++){double a=j*Math.PI/3;mesh.Vertices.Add(plane.PointAt(radius*Math.Cos(a),radius*Math.Sin(a)));mesh.VertexColors.Add(color);}
                if(i>0)for(int j=0;j<6;j++){int a=start+(i-1)*6+j,b=start+(i-1)*6+(j+1)%6;mesh.Faces.AddFace(a,b,b+6,a+6);}
            }
        }
        mesh.Normals.ComputeNormals();da.SetDataList(0,curves);da.SetData(1,mesh);
    }
}

public sealed class SurfaceFieldComponent:HawaQueryComponent {
    public SurfaceFieldComponent():base("Hawa Surface Field","Surface","Sample a scalar outside the surface along outward normals. Every face is kept; faces with an invalid sample are black.","07 Visualize"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077130");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Frames","F","One or more snapshots at the same absolute time. Finest containing domain supplies each sample.",GH_ParamAccess.list);p.AddMeshParameter("Surface","M","Outward oriented mesh",GH_ParamAccess.item);p.AddTextParameter("Field","Q","pressure or cp etc.",GH_ParamAccess.item,"pressure");p.AddNumberParameter("Offset","D","Sampling offset in model units. Use at least one cell.",GH_ParamAccess.item,1);p.AddGenericParameter("Colors","C","Color Map",GH_ParamAccess.item);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddMeshParameter("Colored surface","M","Approximate offset surface field; black = not simulated",GH_ParamAccess.item);p.AddBooleanParameter("Valid","V","Sample validity",GH_ParamAccess.list);p.AddNumberParameter("Values","Q","Scalar values",GH_ParamAccess.list);}
    protected override void SolveHawa(IGH_DataAccess da){
        var f=FieldTools.Frames(da,0);Mesh input=null!;string field="pressure";double offset=1;da.GetData(1,ref input);da.GetData(2,ref field);da.GetData(3,ref offset);var colors=ReadObject(da,4);
        if(!double.IsFinite(offset)||offset<0)throw new ArgumentException("Offset must be nonnegative");
        var mesh=input.DuplicateMesh();mesh.Normals.ComputeNormals();var world=FieldTools.World(f);var points=new JsonArray();
        for(int i=0;i<mesh.Vertices.Count;i++)points.Add(Coordinates.Grid(world,(Point3d)mesh.Vertices[i]+offset*(Vector3d)mesh.Normals[i]));
        var req=FieldTools.Request(f,"sample",field);req["points"]=points;var r=View(req);if(r==null){mesh.Dispose();return;}
        var valid=r["valid"]!.AsArray().Select(x=>
            x!.GetValue<bool>()
        ).ToArray();
        var values=r["values"]!.AsArray().Select(x=>
            x!.GetValue<double>()
        ).ToArray();
        double lo=colors["min"]!.GetValue<double>(),hi=colors["max"]!.GetValue<double>();string palette=colors["palette"]!.GetValue<string>();
        mesh.VertexColors.Clear();
        for(int i=0;i<values.Length;i++)mesh.VertexColors.Add(valid[i]?FieldTools.ColorAt((values[i]-lo)/(hi-lo),palette):Color.Black);
        // Keep every face. A face with an invalid corner is black on its own vertex
        // copies; an invalid vertex is only ever used by such faces.
        var black=new Dictionary<int,int>();int marked=0;
        // A copied vertex extends every per-vertex array (#100): texture coordinates are copied;
        // surface parameters and curvatures cannot be, so they are cleared before the first copy.
        int Black(int v){if(!valid[v])return v;if(!black.TryGetValue(v,out int copy)){if(black.Count==0)mesh.ClearSurfaceData();copy=mesh.Vertices.Add(mesh.Vertices[v]);mesh.VertexColors.Add(Color.Black);if(mesh.TextureCoordinates.Count>0)mesh.TextureCoordinates.Add(mesh.TextureCoordinates[v]);black[v]=copy;}return copy;}
        for(int i=0;i<mesh.Faces.Count;i++){
            var a=mesh.Faces[i];
            if(valid[a.A]&&valid[a.B]&&valid[a.C]&&(!a.IsQuad||valid[a.D]))continue;
            marked++;
            if(a.IsQuad)mesh.Faces.SetFace(i,Black(a.A),Black(a.B),Black(a.C),Black(a.D));
            else mesh.Faces.SetFace(i,Black(a.A),Black(a.B),Black(a.C));
        }
        mesh.Normals.ComputeNormals();da.SetData(0,mesh);da.SetDataList(1,valid);da.SetDataList(2,values);
        Message=marked==0?"offset sample":$"offset sample; {marked} of {mesh.Faces.Count} faces not simulated";
    }
}
