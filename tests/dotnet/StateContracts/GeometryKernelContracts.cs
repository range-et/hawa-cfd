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
        // Analytic box: exact closest point and segment/box crossings, as Rhino reports them.
        Mesh Box(Point3d lo,Point3d hi){
            var mesh=new Mesh();double[] l={lo.X,lo.Y,lo.Z},h={hi.X,hi.Y,hi.Z};
            mesh.Closest=(p,t)=>{double[] q={p.X,p.Y,p.Z},c=new double[3];bool inside=true;
                for(int a=0;a<3;a++){c[a]=Math.Clamp(q[a],l[a],h[a]);inside&=q[a]>l[a]&&q[a]<h[a];}
                if(inside){double gap=double.PositiveInfinity;for(int a=0;a<3;a++)foreach(double f in new[]{l[a],h[a]})if(Math.Abs(q[a]-f)<gap){gap=Math.Abs(q[a]-f);c=(double[])q.Clone();c[a]=f;}}
                var near=new Point3d(c[0],c[1],c[2]);return near.DistanceTo(p)<=t?new MeshPoint(near):null;};
            mesh.Hits=line=>{double[] o={line.From.X,line.From.Y,line.From.Z},d={line.To.X-o[0],line.To.Y-o[1],line.To.Z-o[2]};double t0=0,t1=1;
                for(int a=0;a<3;a++){double u=(l[a]-o[a])/d[a],v=(h[a]-o[a])/d[a];t0=Math.Max(t0,Math.Min(u,v));t1=Math.Min(t1,Math.Max(u,v));}
                if(t0>t1)return Array.Empty<Point3d>();
                return new[]{t0,t1}.Where(t=>t>0&&t<1).Select(t=>new Point3d(o[0]+t*d[0],o[1]+t*d[1],o[2]+t*d[2])).ToArray();};
            return mesh;}
        test("containment keeps faces on lattice planes on both sides of an axis box",()=>{
            int Count(double dx,double origin,int a,int b,double shift){
                var lo=new Point3d(origin+a*dx+shift,origin+a*dx+shift,origin+a*dx+shift);var hi=new Point3d(origin+b*dx+shift,origin+b*dx+shift,origin+b*dx+shift);
                var mesh=Box(lo,hi);var bounds=new BoundingBox(lo,hi);int n=0;
                for(int i=a-2;i<=b+2;i++)for(int j=a-2;j<=b+2;j++)for(int k=a-2;k<=b+2;k++)
                    if(MeshContainment.Contains(mesh,bounds,new Point3d(origin+i*dx,origin+j*dx,origin+k*dx),dx*1e-5))n++;
                return n;}
            // Faces on node planes: both face layers are solid (surface counts as inside) at every spacing,
            // origin and sub-tolerance shift; 0.7 = 7*0.1 is one case the unpadded bounds lost.
            foreach(double dx in new[]{.5,.25,.2,.1,.3})foreach(double origin in new[]{0,.1,1000.1})foreach(double shift in new[]{0,1e-6*dx,-1e-6*dx}){
                int got=Count(dx,origin,3,7,shift);assert(got==125,$"dx {dx} origin {origin} shift {shift}: {got} of 125 nodes");}
            // Literal CAD coordinates against computed node positions: 7*0.1 = 0.7000000000000001.
            var cad=Box(new(.3,.3,.3),new(.7,.7,.7));int literal=0;
            for(int i=1;i<=9;i++)for(int j=1;j<=9;j++)for(int k=1;k<=9;k++)
                if(MeshContainment.Contains(cad,new BoundingBox(new(.3,.3,.3),new(.7,.7,.7)),new Point3d(i*.1,j*.1,k*.1),.1*1e-5))literal++;
            assert(literal==125,$"Literal 0.3..0.7 cube at dx 0.1: {literal} of 125 nodes");
            // Shifted beyond the tolerance, the high layer correctly leaves the box.
            assert(Count(.5,0,3,7,-1e-3)==64,"A face beyond the tolerance stayed solid");
        });
        test("a node solid within the surface tolerance resolves its wall link",()=>{
            // The node at 1.75 lies 2.5e-7 outside the face, inside containment's dx*1e-5.
            double face=1.75-2.5e-7;var mesh=Box(new(1,1,1),new(face,face,face));var start=new Point3d(2,1.5,1.5);var segment=new Vector3d(-.25,0,0);
            assert(MeshContainment.Contains(mesh,new BoundingBox(new(1,1,1),new(face,face,face)),start+segment,.25*1e-5),"Tolerance case is not solid");
            assert(WallLinks.Fraction(mesh,start,segment)==1,"Solid node within the surface tolerance has no wall link");
            // Beyond the tolerance the node is fluid and the link stays a miss.
            mesh=Box(new(1,1,1),new(1.75-1e-3,1.75,1.75));
            assert(double.IsPositiveInfinity(WallLinks.Fraction(mesh,start,segment)),"A face beyond the tolerance became a wall");
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
