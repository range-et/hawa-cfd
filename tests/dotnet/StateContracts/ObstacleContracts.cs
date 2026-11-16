using Hawa.Shared;
using Rhino.Geometry;

static class ObstacleContracts
{
    internal static Mesh Box(double x=0,double y=0,double z=0,double size=1)
    {
        var m=new Mesh();
        m.Vertices.AddRange(new[]{new Point3d(x,y,z),new Point3d(x+size,y,z),new Point3d(x+size,y+size,z),new Point3d(x,y+size,z),new Point3d(x,y,z+size),new Point3d(x+size,y,z+size),new Point3d(x+size,y+size,z+size),new Point3d(x,y+size,z+size)});
        m.Faces.AddFace(0,3,2,1);m.Faces.AddFace(4,5,6,7);m.Faces.AddFace(0,1,5,4);m.Faces.AddFace(1,2,6,5);m.Faces.AddFace(2,3,7,6);m.Faces.AddFace(3,0,4,7);
        m.Bounds=new(new(x,y,z),new(x+size,y+size,z+size));
        m.Closest=(p,t)=>{
            double[] lo={x,y,z},hi={x+size,y+size,z+size},v={p.X,p.Y,p.Z};
            var q=new[]{Math.Clamp(p.X,x,x+size),Math.Clamp(p.Y,y,y+size),Math.Clamp(p.Z,z,z+size)};
            if(v.Where((a,i)=>a>lo[i]&&a<hi[i]).Count()==3){double gap=double.PositiveInfinity;for(int a=0;a<3;a++)foreach(var f in new[]{lo[a],hi[a]})if(Math.Abs(v[a]-f)<gap){gap=Math.Abs(v[a]-f);q=(double[])v.Clone();q[a]=f;}}
            var point=new Point3d(q[0],q[1],q[2]);return point.DistanceTo(p)<=t?new MeshPoint(point):null;
        };
        m.Hits=line=>{
            double[] lo={x,y,z},hi={x+size,y+size,z+size},o={line.From.X,line.From.Y,line.From.Z},d={line.To.X-line.From.X,line.To.Y-line.From.Y,line.To.Z-line.From.Z};double enter=double.NegativeInfinity,leave=double.PositiveInfinity;
            for(int i=0;i<3;i++){if(d[i]==0){if(o[i]<lo[i]||o[i]>hi[i])return Array.Empty<Point3d>();continue;}double a=(lo[i]-o[i])/d[i],b=(hi[i]-o[i])/d[i];enter=Math.Max(enter,Math.Min(a,b));leave=Math.Min(leave,Math.Max(a,b));}
            return enter<=leave?new[]{enter,leave}.Where(t=>t>=0&&t<=1).Select(t=>line.From+t*(line.To-line.From)).ToArray():Array.Empty<Point3d>();
        };
        m.Nearest=p=>m.Closest(p,double.MaxValue)!.Point;
        return m;
    }
    public static void Run(Action<string,Action> test,Action<bool,string> assert)
    {
        void Error(Mesh mesh,string expected) { var e=ObstaclePreflight.Error(mesh,"Obstacle 7");assert(e!=null&&e.Contains("Obstacle 7")&&e.Contains(expected),$"Expected {expected}, got {e}");bool threw=false;try{ObstaclePreflight.Require(mesh,"Obstacle 7");}catch(ArgumentException ex){threw=ex.Message==e;}assert(threw,"Require lost diagnostic"); }
        test("obstacle topology reports actionable invalid/open/non-manifold/degenerate input",()=>{
            Error(new Mesh(),"empty");Error(new Mesh{IsValid=false},"invalid");Error(null!,"invalid");
            var m=Box();m.Vertices[0]=new(double.NaN,0,0);Error(m,"non-finite vertex 0");
            m=Box();m.Faces[0]=new(0,1,999);Error(m,"face 0");
            m=Box();m.Faces.RemoveAt(0);Error(m,"4 naked edges; 0 non-manifold");
            m=Box();m.Vertices.Add(new(.5,-.5,0));m.Faces.AddFace(0,1,8);Error(m,"2 naked edges; 1 non-manifold");
            m=Box();m.IsValid=false;m.Faces.AddFace(0,0,1);Error(m,"1 degenerate/zero-area faces");
            m=Box();m.Vertices.Add(new(.5,0,0));m.Faces.AddFace(0,8,1);Error(m,"degenerate");
            m=Box();m.IsValid=false;Error(m,"invalid mesh data");
            m=Box();m.IsClosed=false;Error(m,"Rhino reports an open mesh");
            m=Box();m.Vertices[1]=new(double.MaxValue,0,0);Error(m,"degenerate");
            m=Box();m.Vertices[0]=new(0,0,0);m.Vertices[1]=new(0,0,0);m.Vertices[2]=new(0,0,0);Error(m,"degenerate");
            using var cancel=new CancellationTokenSource();cancel.Cancel();bool cancelled=false;try{ObstaclePreflight.Require(Box(),"body",cancel.Token);}catch(OperationCanceledException){cancelled=true;}assert(cancelled,"Cancellation ignored");
        });
        test("obstacle admission preserves seam duplicates, triangles, scale, hollow and separate bodies",()=>{
            foreach(double size in new[]{1e-9,1d,1e9}){var m=Box(size:size);var before=m.Vertices.ToArray();ObstaclePreflight.Require(m,"box");assert(before.SequenceEqual(m.Vertices),"Validator mutated vertices");}
            var distant=Box(1e9,1e9,1e9);distant.Vertices.FloatIndex=true;ObstaclePreflight.Require(distant,"double-precision distant box");
            var seam=new Mesh();var source=Box();foreach(var f in source.Faces){int o=seam.Vertices.Count;foreach(int i in new[]{f.A,f.B,f.C,f.D})seam.Vertices.Add(source.Vertices[i]);seam.Faces.AddFace(o,o+1,o+2,o+3);}ObstaclePreflight.Require(seam,"unwelded box");
            var mixed=Box();mixed.Faces.RemoveAt(0);mixed.Faces.AddFace(0,3,2);mixed.Faces.AddFace(0,2,1);ObstaclePreflight.Require(mixed,"mixed");
            var hollow=Box(2,2,2,3);var inner=Box(3,3,3);var outerHits=hollow.Hits;var outerClosest=hollow.Closest;hollow.Append(inner);hollow.Hits=line=>outerHits(line).Concat(inner.Hits(line)).ToArray();hollow.Closest=(p,t)=>outerClosest(p,t)??inner.Closest(p,t);ObstaclePreflight.Require(hollow,"hollow");
            assert(MeshContainment.Contains(hollow,hollow.Bounds,new(2.5,3.5,3.5),.5e-5)&&!MeshContainment.Contains(hollow,hollow.Bounds,new(3.5,3.5,3.5),.5e-5)&&MeshContainment.Contains(hollow,hollow.Bounds,new(3,3.5,3.5),.5e-5),"Hollow shell lost material/cavity/surface parity (analytic kernel double)");
            foreach(var child in new[]{Box(.3,.2,.1),Box(1,0,0),Box(3,0,0)}){ObstaclePreflight.Require(source,"first");ObstaclePreflight.Require(child,"second");}
            // Broad-phase regression: many separate boxes share X extent, but do not overlap Y/Z.
            var many=Box();for(int i=1;i<250;i++)many.Append(Box(0,3*i,0));ObstaclePreflight.Require(many,"many disjoint shells");
            assert(ObstaclePreflight.Limits.Contains("Coplanar")&&ObstaclePreflight.Limits.Contains("unsupported"),"Unsupported geometry limit absent");
        });
        test("self-intersection admission bounds dense ambiguous candidate work",()=>{
            var m=new Mesh();for(int i=0;i<1600;i++){double size=1+i*.001;m.Append(Box(-size/2,-size/2,-size,size));}
            Error(m,"2,000,000 overlapping candidate pairs");
        });
        test("transverse self intersections reject combined shells including triangle seam crossings",()=>{
            foreach(var offset in new[]{new Point3d(.3,.2,.1),new Point3d(.5,.5,.5)}){var m=Box();m.Append(Box(offset.X,offset.Y,offset.Z));Error(m,"self-intersection between faces");}
            var rotated=Box(.2,.2,.2);for(int i=0;i<rotated.Vertices.Count;i++){var p=rotated.Vertices[i];rotated.Vertices[i]=new(p.X*Math.Cos(.4)-p.Y*Math.Sin(.4),p.X*Math.Sin(.4)+p.Y*Math.Cos(.4),p.Z);}
            var merged=Box();merged.Append(rotated);Error(merged,"self-intersection between faces");
        });
    }
}
