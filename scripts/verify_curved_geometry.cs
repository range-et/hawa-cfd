// Background geometric verification through actual RhinoCommon. No UI-thread wait.
using Rhino.Geometry;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
var root="/Users/r2d2/Desktop/hawa-cfd/results/v05/boundaries";
var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Shared");
var mesher=assembly.GetType("Hawa.Shared.SurfaceMeshing");var walls=assembly.GetType("Hawa.Shared.WallLinks");var containment=assembly.GetType("Hawa.Shared.MeshContainment");
System.IO.File.WriteAllText(root+"/geometry.json","{\"state\":\"running\"}");
_ = Task.Run(()=>{try{
 var rows=new JsonArray();double previous=double.PositiveInfinity;
 foreach(double dx in new[]{.2,.1,.05}){
  var center=new Point3d(.137,.219,.161);double radius=.43;
  using var brep=new Sphere(center,radius).ToBrep();using var mesh=(Mesh)mesher.GetMethod("Create").Invoke(null,new object[]{brep,dx});
  double error=0;int samples=0;
  foreach(var f in mesh.Faces){var vertices=new[]{(Point3d)mesh.Vertices[f.A],(Point3d)mesh.Vertices[f.B],(Point3d)mesh.Vertices[f.C],(Point3d)mesh.Vertices[f.D]};int count=f.IsQuad?4:3;
   var sum=Point3d.Origin;for(int i=0;i<count;i++){sum+=vertices[i];var midpoint=(vertices[i]+vertices[(i+1)%count])*.5;error=Math.Max(error,Math.Abs(midpoint.DistanceTo(center)-radius));samples++;}
   var centroid=sum/count;error=Math.Max(error,Math.Abs(centroid.DistanceTo(center)-radius));samples++;
  }
  if(error>dx*.03||error>=previous)throw new Exception("Surface approximation error "+error+" at dx="+dx);previous=error;
  int countAxis=(int)Math.Round(2.4/dx)+1;int[] n={countAxis,countAxis,countAxis};var origin=new Point3d(-1.2,-1.2,-1.2);var solid=new List<int>();var bounds=mesh.GetBoundingBox(false);
  for(int x=0;x<n[0];x++)for(int y=0;y<n[1];y++)for(int z=0;z<n[2];z++)if((bool)containment.GetMethod("Contains").Invoke(null,new object[]{mesh,bounds,origin+new Vector3d(x*dx,y*dx,z*dx),dx*1e-5}))solid.Add((x*n[1]+y)*n[2]+z);
  var links=(JsonArray)walls.GetMethod("Build").Invoke(null,new object[]{new[]{mesh},n,solid,origin,Vector3d.XAxis*dx,Vector3d.YAxis*dx,Vector3d.ZAxis*dx,CancellationToken.None});
  int[][] directions={new[]{0,0,0},new[]{1,0,0},new[]{-1,0,0},new[]{0,1,0},new[]{0,-1,0},new[]{0,0,1},new[]{0,0,-1},new[]{0,1,1},new[]{0,-1,-1},new[]{0,1,-1},new[]{0,-1,1},new[]{1,0,1},new[]{-1,0,-1},new[]{1,0,-1},new[]{-1,0,1},new[]{1,1,0},new[]{-1,-1,0},new[]{1,-1,0},new[]{-1,1,0}};
  double maxWall=0;int below=0,above=0;
  foreach(var row in links){int dir=row[0].GetValue<int>(),index=row[1].GetValue<int>();double q=row[2].GetValue<double>();var e=directions[dir];var v=new Vector3d(e[0]*dx,e[1]*dx,e[2]*dx);var p=origin+new Vector3d(index/(n[1]*n[2])*dx,index/n[2]%n[1]*dx,index%n[2]*dx);var offset=p-center;
   double b=2*(offset*v),a=v.SquareLength,c=offset.SquareLength-radius*radius,disc=b*b-4*a*c;
   if(disc<0)throw new Exception("Mesh wall link misses analytic sphere");double exact=(-b-Math.Sqrt(disc))/(2*a);maxWall=Math.Max(maxWall,Math.Abs(q-exact)*v.Length);if(q<.5)below++;else above++;
  }
  if(maxWall>dx*.03||below==0||above==0)throw new Exception("Wall placement error "+maxWall+" at dx="+dx);
  var rowOut=new JsonObject{["cell"]=dx,["faces"]=mesh.Faces.Count,["samples"]=samples,["surface_error_max"]=error,["wall_error_max"]=maxWall,["solid"]=solid.Count,["links"]=links.Count,["q_below_half"]=below,["q_above_half"]=above};rows.Add(rowOut);
  var spec=new JsonObject{["shape"]=new JsonArray(n.Select(v=>JsonValue.Create(v)).ToArray()),["dx"]=dx,["speed"]=.1,["viscosity"]=.1,["density"]=1d,["mach"]=.04,["collision"]="bgk",["boundaries"]=new JsonArray("inlet","outlet","periodic","periodic","periodic","periodic"),["solid"]=new JsonArray(solid.Select(v=>JsonValue.Create(v)).ToArray()),["wall_links"]=links};
  System.IO.File.WriteAllText(root+"/sphere-"+countAxis+".json",spec.ToJsonString());
 }
 System.IO.File.WriteAllText(root+"/geometry.json",new JsonObject{["state"]="completed",["rows"]=rows}.ToJsonString());
}catch(Exception e){System.IO.File.WriteAllText(root+"/geometry.json",new JsonObject{["state"]="failed",["error"]=e.GetBaseException().ToString()}.ToJsonString());}});
Rhino.RhinoApp.WriteLine("Curved geometry checks running in background");
