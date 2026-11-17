// Rhino MCP only. Close example 35 first. Patches plot inputs in an owned archive copy,
// preserves every existing ID and all other wires, and writes a timestamped source backup.
using System.IO;
using System.Drawing;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
var root="/Users/r2d2/Desktop/hawa-parametric-wing-example";
var path=Path.Combine(root,"examples/grasshopper/35-parametric-wing-study.gh");
if(Grasshopper.Instances.DocumentServer.Any(d=>string.Equals(d.FilePath,path,StringComparison.OrdinalIgnoreCase)))throw new Exception("Close the source example before patching its archive.");
var output=Path.Combine(root,"results","wing-scatter-patch",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(output);
string Hash(string p)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p))).ToLowerInvariant();
var beforeHash=Hash(path);File.Copy(path,Path.Combine(output,"35-before.gh"),false);
var io=new GH_DocumentIO();if(!io.Open(path))throw new Exception("Cannot read example");var doc=io.Document;
string Wires(GH_Component c)=>string.Join(";",c.Params.Input.SelectMany((p,i)=>p.Sources.Select(s=>i+":"+s.InstanceGuid)));
var ids=doc.Objects.Select(o=>o.InstanceGuid).ToHashSet();var before=doc.Objects.OfType<GH_Component>().ToDictionary(c=>c.InstanceGuid,Wires);var edited=new HashSet<Guid>();var records=new JsonArray();
GH_Component Stock(string id,string label,float x,float y){var c=(GH_Component)Grasshopper.Instances.ComponentServer.EmitObjectProxy(new Guid(id)).CreateInstance();c.CreateAttributes();c.Attributes.Pivot=new PointF(x,y);c.NickName=label;c.Hidden=true;doc.AddObject(c,false);return c;}
void Wire(IGH_Param p,GH_Component c,int i)=>c.Params.Input[i].AddSource(p);
try{
 foreach(string title in new[]{"CL versus angle","CD versus angle","CL versus CD"}){
  var px=doc.Objects.OfType<GH_Component>().Single(c=>c.NickName==title+" / display X");var py=doc.Objects.OfType<GH_Component>().Single(c=>c.NickName==title+" / display Y");
  var xs=px.Params.Input[0].Sources.Single();var ys=py.Params.Input[0].Sources.Single();
  if(doc.Objects.OfType<GH_Component>().Any(c=>c.NickName==title+" / paired X"))throw new Exception("Plot already patched");
  float x=px.Attributes.Pivot.X,y=px.Attributes.Pivot.Y;
  var group=doc.Objects.OfType<GH_Group>().Single(g=>g.NickName.StartsWith(title+" / display scaling"));
  foreach(var oldId in group.ObjectIDs){var item=doc.FindObject(oldId,false);if(item!=null){var p=item.Attributes.Pivot;item.Attributes.Pivot=new PointF(p.X+650,p.Y);item.Attributes.ExpireLayout();}}
  var nx=Stock("c74efd0e-7fe3-4c2d-8c9d-295c5672fb13",title+" / missing X",x,y);Wire(xs,nx,0);
  var ny=Stock("c74efd0e-7fe3-4c2d-8c9d-295c5672fb13",title+" / missing Y",x,y+110);Wire(ys,ny,0);
  var mask=Stock("5cad70f9-5a53-4c5c-a782-54a479b4abe3",title+" / missing either coordinate",x+230,y+220);Wire(nx.Params.Output[0],mask,0);Wire(ny.Params.Output[0],mask,1);
  var cx=Stock("008e9a6f-478a-4813-8c8a-546273bc3a6b",title+" / paired X",x+300,y);Wire(xs,cx,0);Wire(mask.Params.Output[0],cx,1);
  var cy=Stock("008e9a6f-478a-4813-8c8a-546273bc3a6b",title+" / paired Y",x+300,y+110);Wire(ys,cy,0);Wire(mask.Params.Output[0],cy,1);
  px.Params.Input[0].RemoveSource(xs);Wire(cx.Params.Output[0],px,0);py.Params.Input[0].RemoveSource(ys);Wire(cy.Params.Output[0],py,0);edited.Add(px.InstanceGuid);edited.Add(py.InstanceGuid);
  foreach(var c in new[]{nx,ny,mask,cx,cy})group.AddObject(c.InstanceGuid);group.Attributes.ExpireLayout();
  records.Add(new JsonObject{["plot"]=title,["x_expression"]=px.InstanceGuid.ToString(),["y_expression"]=py.InstanceGuid.ToString(),["original_x_source"]=xs.InstanceGuid.ToString(),["original_y_source"]=ys.InstanceGuid.ToString()});
 }
 if(!ids.IsSubsetOf(doc.Objects.Select(o=>o.InstanceGuid)))throw new Exception("Original ID lost");
 foreach(var c in doc.Objects.OfType<GH_Component>())if(before.ContainsKey(c.InstanceGuid)&&!edited.Contains(c.InstanceGuid)&&before[c.InstanceGuid]!=Wires(c))throw new Exception("Unrelated wire changed");
 if(edited.Count!=6||doc.Objects.Count!=ids.Count+15)throw new Exception("Unexpected edit inventory");
 var staged=Path.Combine(output,"35-patched.gh");if(!new GH_DocumentIO{Document=doc}.SaveQuiet(staged))throw new Exception("Cannot save staged archive");
 if(Hash(path)!=beforeHash)throw new Exception("Source changed concurrently; refusing replacement");
 File.Copy(staged,path,true);
 File.WriteAllText(Path.Combine(output,"audit.json"),new JsonObject{["source_before_sha256"]=beforeHash,["source_after_sha256"]=Hash(path),["preserved_original_ids"]=ids.Count,["added_objects"]=15,["intentional_input_rewires"]=6,["plots"]=records}.ToJsonString());
 Console.WriteLine("Patched paired-null filtering; backup/audit: "+output);
}finally{doc.Dispose();}
