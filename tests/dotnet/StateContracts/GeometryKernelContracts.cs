using Hawa.Shared;
using Rhino.Geometry;

// These exercise Hawa's decisions around scripted kernel answers. They do not
// claim Rhino intersection/meshing accuracy or qualify real user geometry.
static class GeometryKernelContracts
{
    public static void Run(Action<string,Action> test,Action<bool,string> assert)
    {
        void Reject(Action action){bool rejected=false;try{action();}catch(ArgumentException){rejected=true;}assert(rejected,"Invalid geometry contract accepted");}
        test("containment rejects bounds misses and merges coincident seam hits",()=>{
            var bounds=new BoundingBox(new(-1,-1,-1),new(1,1,1));var mesh=new Mesh();int queries=0;
            mesh.Hits=line=>{queries++;assert(Math.Abs((line.To-line.From).Length-(3*bounds.Diagonal.Length+1e-6))<1e-10,"Parity ray reach changed");return new[]{new Point3d(.25,0,0),new Point3d(.25+1e-9,0,0)};};
            assert(!MeshContainment.Contains(mesh,bounds,new(2,0,0),1e-6)&&queries==0,"Bounds miss called native intersection");
            assert(MeshContainment.Contains(mesh,bounds,new(0,0,0),1e-6)&&queries==3,"Duplicate seam hits changed parity");
            mesh.Hits=line=>new[]{new Point3d(.25,0,0),new Point3d(.5,0,0)};
            assert(!MeshContainment.Contains(mesh,bounds,new(0,0,0),1e-6),"Even intersections became interior");
            mesh.Closest=(p,t)=>new MeshPoint(p);
            assert(MeshContainment.Contains(mesh,bounds,new(0,0,0),1e-6),"Surface point lost");
        });
        test("wall fractions choose nearest valid intersection and preserve misses",()=>{
            var mesh=new Mesh();var start=new Point3d(0,0,0);var segment=new Vector3d(2,0,0);
            mesh.Hits=_=>new[]{new Point3d(1.5,0,0),new Point3d(.5,0,0),new Point3d(3,0,0),new Point3d(-1,0,0)};
            assert(WallLinks.Fraction(mesh,start,segment)==.25,"Nearest in-segment crossing not selected");
            Reject(()=>WallLinks.Fraction(mesh,start,new Vector3d(0,0,0)));
            Reject(()=>WallLinks.Fraction(mesh,new Point3d(double.NaN,0,0),segment));
            mesh.Hits=_=>Array.Empty<Point3d>();mesh.Closest=(p,t)=>new MeshPoint(p);
            assert(WallLinks.Fraction(mesh,start,segment)==1,"Exact endpoint fallback lost");
            mesh.Closest=(_,_)=>null;mesh.Bounds=new(new(10,10,10),new(11,11,11));
            assert(double.IsPositiveInfinity(WallLinks.Fraction(mesh,start,segment)),"Miss became invented wall");
        });
        test("triangle fallback resolves a seam only when endpoint is classified inside",()=>{
            var mesh=new Mesh();mesh.Vertices.Add(new(.25,-1,-1));mesh.Vertices.Add(new(.25,1,-1));mesh.Vertices.Add(new(.25,1,1));mesh.Vertices.Add(new(.25,-1,1));mesh.Faces.Add(new(0,1,2,3));
            mesh.Hits=line=>(line.To-line.From).Length>2?new[]{line.From+new Vector3d(.1,0,0)}:Array.Empty<Point3d>();
            assert(WallLinks.Fraction(mesh,new(0,0,0),new(1,0,0))==.25,"Quad seam fallback did not choose actual triangle crossing");
        });
        test("wall link assembly preserves D3Q19 order and clearance cancellation",()=>{
            var mesh=new Mesh{Hits=line=>new[]{line.From+.5*(line.To-line.From)}};
            var links=WallLinks.Build(new[]{mesh},new[]{5,5,5},new[]{62},new(0,0,0),new(1,0,0),new(0,1,0),new(0,0,1),CancellationToken.None);
            assert(links.Count==18&&links[0]![0]!.GetValue<int>()==1&&links[0]![1]!.GetValue<int>()==37&&links.All(r=>r![2]!.GetValue<double>()==.5),"Wrong direction/site/fraction mapping");
            Reject(()=>WallLinks.Build(new[]{mesh},new[]{5,5,5},new[]{0},new(0,0,0),new(1,0,0),new(0,1,0),new(0,0,1),CancellationToken.None));
            using var cancel=new CancellationTokenSource();cancel.Cancel();bool cancelled=false;
            try{WallLinks.Build(new[]{mesh},new[]{5,5,5},new[]{62},new(0,0,0),new(1,0,0),new(0,1,0),new(0,0,1),cancel.Token);}catch(OperationCanceledException){cancelled=true;}
            assert(cancelled,"Cancelled geometry work continued");
            mesh.Hits=line=>new[]{line.From+.25*(line.To-line.From)};
            Reject(()=>WallLinks.Build(new[]{mesh},new[]{9,9,9},new[]{2*81+4*9+4,4*81+4*9+4},new(0,0,0),new(1,0,0),new(0,1,0),new(0,0,1),CancellationToken.None));
        });
        test("wall assembly skips internal solid edges and rejects unresolved intersections",()=>{
            var mesh=new Mesh{Hits=line=>new[]{line.From+.5*(line.To-line.From)}};
            var links=WallLinks.Build(new[]{mesh},new[]{7,7,7},new[]{171,220},new(0,0,0),new(1,0,0),new(0,1,0),new(0,0,1),CancellationToken.None);
            assert(links.Count==34,"Internal solid edge emitted wall links");
            Reject(()=>WallLinks.Build(Array.Empty<Mesh>(),new[]{5,5,5},new[]{62},new(0,0,0),new(1,0,0),new(0,1,0),new(0,0,1),CancellationToken.None));
        });
        test("triangle fallback excludes crossings outside barycentric and segment bounds",()=>{
            foreach(var triangle in new[]{new[]{new Point3d(0,1,0),new Point3d(1,1,0),new Point3d(1,1,1)},new[]{new Point3d(.25,1,1),new Point3d(.25,2,1),new Point3d(.25,1,2)},new[]{new Point3d(.25,-1,1),new Point3d(.25,1,1),new Point3d(.25,0,2)},new[]{new Point3d(2,-1,-1),new Point3d(2,1,-1),new Point3d(2,0,1)}}){
                var mesh=new Mesh();foreach(var point in triangle)mesh.Vertices.Add(point);mesh.Faces.AddFace(0,1,2);
                mesh.Hits=line=>(line.To-line.From).Length>2?new[]{line.From+new Vector3d(.1,0,0)}:Array.Empty<Point3d>();
                assert(double.IsPositiveInfinity(WallLinks.Fraction(mesh,new(0,0,0),new(1,0,0))),"Outside triangle/segment became wall");
            }
        });
        test("surface meshing budgets tolerance and disposes input parts",()=>{
            var part=new Mesh();part.Vertices.Add(new(0,0,0));part.Vertices.Add(new(1,0,0));part.Vertices.Add(new(0,1,0));part.Faces.AddFace(0,1,2);
            MeshingParameters? parameters=null;Mesh.Factory=(b,p)=>{parameters=p;return new[]{part};};
            using var mesh=SurfaceMeshing.Create(new Brep(),1);
            assert(part.Disposed&&parameters!.Disposed&&parameters.Tolerance==.001&&parameters.MaximumEdgeLength==.5&&parameters.DoublePrecision,"Tolerance scaling or resource disposal changed");
            assert(mesh.Faces.Count==1&&!mesh.Disposed,"Result mesh was lost or disposed");
        });
        test("surface meshing rejects invalid inputs and disposes failed result",()=>{
            Reject(()=>SurfaceMeshing.Create(new Brep{IsSolid=false},1));Reject(()=>SurfaceMeshing.Create(new Brep(),0));
            var part=new Mesh{IsClosed=false};Mesh.Factory=(_,_)=>new[]{part};
            Reject(()=>SurfaceMeshing.Create(new Brep(),1));assert(part.Disposed&&Mesh.Created.Last().Disposed,"Failed meshing leaked result or part");
            part=new Mesh();part.Faces.ReportedCount=2_000_001;Mesh.Factory=(_,_)=>new[]{part};
            Reject(()=>SurfaceMeshing.Create(new Brep(),1));assert(part.Disposed&&Mesh.Created.Last().Disposed,"Oversized mesh leaked result or part");
            Mesh.Factory=(_,_)=>Array.Empty<Mesh>();
        });
    }
}
