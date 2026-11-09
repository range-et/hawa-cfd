// Migrate the supported example in place. Example geometry is an ordinary GH graph.
// Run in Rhino with Hawa loaded; never touches the user's legacy example 09.
// Preserves existing non-hull object IDs, values and solver/search connections.
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;
using Rhino.Geometry;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";
var path=root+"/examples/grasshopper/10-responsive-hull-search.gh";
var io=new GH_DocumentIO();if(!io.Open(path))throw new Exception("Missing supported example");var d=io.Document;d.Enabled=true;
var old=d.Objects.OfType<GH_Component>().SingleOrDefault(c=>c.ComponentGuid==new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077116"));
if(old==null){d.Dispose();Console.WriteLine("Example already uses native GH geometry");return;}
if(old.Params.Output[1].Recipients.Count>0)throw new Exception("Unexpected section consumer; migrate explicitly");
var oldIds=d.Objects.Where(o=>o!=old).Select(o=>o.InstanceGuid).OrderBy(x=>x).ToArray();
var added=new List<IGH_DocumentObject>();
T Add<T>(T item,float x,float y) where T:IGH_DocumentObject{item.CreateAttributes();item.Attributes.Pivot=new PointF(x,y);d.AddObject(item,false);added.Add(item);return item;}
GH_Component Node(string id,string label,float x,float y){var c=Add((GH_Component)Grasshopper.Instances.ComponentServer.EmitObjectProxy(new Guid(id)).CreateInstance(),x,y);c.NickName=label;c.Hidden=true;return c;}
void Wire(IGH_Param p,GH_Component c,int input)=>c.Params.Input[input].AddSource(p);
GH_Component Expr(string expression,string label,float x,float y,params IGH_Param[] inputs){var c=Node("9df5e896-552d-4c8c-b9ca-4fc147ffa022",label,x,y);var v=(IGH_VariableParameterComponent)c;while(c.Params.Input.Count<inputs.Length)c.Params.RegisterInputParam(v.CreateParameter(GH_ParameterSide.Input,c.Params.Input.Count));while(c.Params.Input.Count>inputs.Length)c.Params.UnregisterInputParameter(c.Params.Input.Last(),true);for(int i=0;i<inputs.Length;i++){c.Params.Input[i].Name=c.Params.Input[i].NickName=new[]{"x","y","z"}[i];Wire(inputs[i],c,i);}c.Params.OnParametersChanged();c.GetType().GetProperty("Expression").SetValue(c,expression);return c;}
var inputs=old.Params.Input.Take(5).Select(p=>p.Sources.Single()).ToArray();
var center=((Param_Point)old.Params.Input[5]).PersistentData.AllData(true).OfType<GH_Point>().Single().Value;
// Fixed station topology is example data, not a Hawa primitive. Shape math is visible.
const int stations=40, ring=25;
var ts=Add(new Param_Number(),-1900,20);ts.NickName="Station t / example topology";
var cs=Add(new Param_Number(),-1900,120);cs.NickName="Ring cos / example topology";
var ss=Add(new Param_Number(),-1900,220);ss.NickName="Ring sin / example topology";
for(int i=1;i<stations;i++)for(int j=0;j<ring;j++){ts.PersistentData.Append(new GH_Number((double)i/stations));cs.PersistentData.Append(new GH_Number(Math.Cos(Math.PI*j/(ring-1))));ss.PersistentData.Append(new GH_Number(Math.Sin(Math.PI*j/(ring-1))));}
foreach(double t in new[]{0d,1d}){ts.PersistentData.Append(new GH_Number(t));cs.PersistentData.Append(new GH_Number(0));ss.PersistentData.Append(new GH_Number(0));}
var faces=Add(new Param_MeshFace(),-1050,400);faces.NickName="Closed hull topology / example data";
for(int i=0;i<stations-2;i++)for(int j=0;j<ring;j++){int a=i*ring+j,b=i*ring+(j+1)%ring;faces.PersistentData.Append(new GH_MeshFace(new MeshFace(a,a+ring,b+ring,b)));}
int nose=(stations-1)*ring,tail=nose+1;
for(int j=0;j<ring;j++){faces.PersistentData.Append(new GH_MeshFace(new MeshFace(nose,j,(j+1)%ring)));int a=(stations-2)*ring+j,b=(stations-2)*ring+(j+1)%ring;faces.PersistentData.Append(new GH_MeshFace(new MeshFace(tail,b,a)));}
var fullness=Expr("Sin(pi*x)^if(x<0.5,y,z)","Bow / stern taper",-1630,20,ts,inputs[2],inputs[3]);
var xcoord=Expr("x*(y-0.5)","Longitudinal coordinate",-1350,120,inputs[0],ts);
var yunit=Expr("x*y", "Section half-width",-1350,220,fullness.Params.Output[0],cs);
var ycoord=Expr("x*y*0.5","Beam / draft ratio",-1100,220,yunit.Params.Output[0],inputs[4]);
var zcoord=Expr("-x*y","Section depth",-1350,320,fullness.Params.Output[0],ss);
var points=Node("3581f42a-9592-4549-bd6b-1c0fc39d067b","Hull vertices",-850,140);Wire(xcoord.Params.Output[0],points,0);Wire(ycoord.Params.Output[0],points,1);Wire(zcoord.Params.Output[0],points,2);
var mesh=Node("e2c0f9db-a862-4bd9-810c-ef2610e7a56f","Close station mesh",-600,160);Wire(points.Params.Output[0],mesh,0);Wire(faces,mesh,1);
var rawVolume=Node("a8395a34-6153-4357-b4d5-76e68364b9d8","Measure raw volume",-360,60);Wire(mesh.Params.Output[0],rawVolume,0);
var factor=Expr("Sqrt(x/Abs(y))","Match target volume",-120,60,inputs[1],rawVolume.Params.Output[0]);
var scale=Node("290f418a-65ee-406a-a9d0-35699815b512","Scale section YZ",120,160);Wire(mesh.Params.Output[0],scale,0);Wire(factor.Params.Output[0],scale,3);Wire(factor.Params.Output[0],scale,4);
var origin=Add(new Param_Vector(),120,330);origin.NickName="Deck center (m)";origin.SetPersistentData((Vector3d)center);
var move=Node("e9eb1dcf-92f6-4d4d-84ae-96222d60f56b","Position example hull",360,160);Wire(scale.Params.Output[0],move,0);Wire(origin,move,1);
var volume=Node("a8395a34-6153-4357-b4d5-76e68364b9d8","Closed mesh volume (m³)",600,160);Wire(move.Params.Output[0],volume,0);
// Compare the ordinary GH graph with the archived generator before removing it.
// Disable evaluation on this copy; no solver is started by this migration.
foreach(var t in d.Objects.OfType<GH_BooleanToggle>())t.Value=false;
Grasshopper.Instances.DocumentServer.AddDocument(d);
var checks=new JsonArray();var genes=inputs.Select(p=>(GH_NumberSlider)p).ToArray();var saved=genes.Select(s=>s.CurrentValue).ToArray();
foreach(var shape in new[]{new[]{8m,6m,.8m,.8m,2m},new[]{8m,6m,.4m,1.6m,1m},new[]{8m,6m,1.6m,.4m,3m}}){for(int i=0;i<5;i++){genes[i].SetSliderValue(shape[i]);genes[i].ExpireSolution(false);}d.NewSolution(false);var errors=added.OfType<GH_Component>().SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(e=>c.NickName+": "+e)).ToArray();if(errors.Length>0)throw new Exception(string.Join(";",errors));var a=old.Params.Output[0].VolatileData.AllData(true).OfType<GH_Mesh>().Single().Value;var b=move.Params.Output[0].VolatileData.AllData(true).OfType<GH_Mesh>().Single().Value;if(!b.IsValid||!b.IsClosed||b.SolidOrientation()!=1||a.Vertices.Count!=b.Vertices.Count)throw new Exception("Invalid native hull mesh");double error=Enumerable.Range(0,a.Vertices.Count).Max(i=>((Point3d)a.Vertices[i]).DistanceTo((Point3d)b.Vertices[i]));double actual=VolumeMassProperties.Compute(b).Volume;if(error>2e-5||Math.Abs(actual-6)>2e-5)throw new Exception("Native construction differs: "+error+" / "+actual);checks.Add(new JsonObject{["bow"]=(double)shape[2],["stern"]=(double)shape[3],["ratio"]=(double)shape[4],["max_vertex_error_m"]=error,["volume_m3"]=actual,["closed"]=true});}
for(int i=0;i<5;i++){genes[i].SetSliderValue(saved[i]);genes[i].ExpireSolution(false);}
for(int i=0;i<old.Params.Output.Count;i++)foreach(var recipient in old.Params.Output[i].Recipients.ToArray()){recipient.RemoveSource(old.Params.Output[i]);recipient.AddSource(i==0?move.Params.Output[0]:volume.Params.Output[0]);if(i==3&&recipient is GH_Panel panel)panel.NickName="Measured mesh volume (m³)";}
foreach(var g in d.Objects.OfType<GH_Group>())if(g.ObjectIDs.Contains(old.InstanceGuid))g.RemoveObject(old.InstanceGuid);
d.RemoveObject(old,false);
var group=Add(new GH_Group{NickName="EXAMPLE GEOMETRY / ordinary GH mesh and volume operations",Colour=Color.FromArgb(55,40,155,140)},0,0);foreach(var item in added.Where(x=>x!=group))group.AddObject(item.InstanceGuid);
var note=Add(new GH_Panel(),-1900,-330);note.NickName="Hawa guide / example geometry";note.UserText="EXAMPLE GEOMETRY, NOT A HAWA NODE\n\nThis editable GH assembly constructs a closed mesh from station coordinates and face indices. Expressions set bow/stern taper and beam/draft ratio. Native Mesh Volume and Scale NU keep the target volume. Move places it in the domain.\n\nThe fixed 40-station, 25-point ring topology is local example data. Replace this construction with your own geometry; the Hawa case, evaluator and search remain separate.\n\nSingle fluid and fully submerged. No waves or buoyancy. All dimensions here are metres.";note.Properties.Font=new Font("Helvetica",12);note.Properties.Wrap=true;note.Properties.Multiline=true;note.Properties.DrawIndices=false;note.Properties.DrawPaths=false;note.Properties.Alignment=GH_Panel.Alignment.Left;note.Properties.Colour=Color.FromArgb(226,242,237);note.Attributes.Bounds=new RectangleF(-1900,-330,650,300);
if(!oldIds.All(id=>d.Objects.Any(o=>o.InstanceGuid==id)))throw new Exception("An unrelated object was removed");
d.NewSolution(false);
var backup=root+"/results/v05/release/10-before-native-geometry.gh";if(!System.IO.File.Exists(backup))System.IO.File.Copy(path,backup);
if(!new GH_DocumentIO{Document=d}.SaveQuiet(path))throw new Exception("Cannot save migrated example");
System.IO.File.WriteAllText(root+"/results/v05/release/hull-native-graph.json",new JsonObject{["state"]="completed",["checks"]=checks,["non_hull_ids_preserved"]=true,["hawa_hull_instances"]=0,["native_geometry_objects"]=added.Count}.ToJsonString());
Grasshopper.Instances.DocumentServer.RemoveDocument(d);d.Dispose();Console.WriteLine("Migrated hull construction to native GH; three shapes verified");
