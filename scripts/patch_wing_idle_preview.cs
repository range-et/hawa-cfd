// Rhino MCP only; close source example 35 first. No solution or active-canvas change.
// Preserves every original ID/wire. Adds NOT Run -> keep-pattern mesh preview.
using System.IO;
using System.Drawing;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Special;
var root="/Users/r2d2/Desktop/hawa-parametric-wing-example";
var path=Path.Combine(root,"examples/grasshopper/35-parametric-wing-study.gh");
if(Grasshopper.Instances.DocumentServer.Any(d=>string.Equals(d.FilePath,path,StringComparison.OrdinalIgnoreCase)))throw new Exception("Close source example 35 first.");
var output=Path.Combine(root,"results","wing-idle-preview-patch",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(output);
string Hash(string p)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p))).ToLowerInvariant();
var beforeHash=Hash(path);File.Copy(path,Path.Combine(output,"35-before.gh"),false);
var io=new GH_DocumentIO();if(!io.Open(path))throw new Exception("Cannot read example");var doc=io.Document;
string Wires(GH_Component c)=>string.Join(";",c.Params.Input.SelectMany((p,i)=>p.Sources.Select(s=>i+":"+s.InstanceGuid)));
var ids=doc.Objects.Select(o=>o.InstanceGuid).ToHashSet();var before=doc.Objects.OfType<GH_Component>().ToDictionary(c=>c.InstanceGuid,Wires);
GH_Component Stock(string id,string name,float x,float y){var c=(GH_Component)Grasshopper.Instances.ComponentServer.EmitObjectProxy(new Guid(id)).CreateInstance();c.CreateAttributes();c.Attributes.Pivot=new PointF(x,y);c.NickName=name;c.Hidden=true;doc.AddObject(c,false);return c;}
try{
 if(doc.Objects.Any(o=>o.NickName=="Idle wing preview / NOT Run"))throw new Exception("Idle preview gate already exists");
 var wing=doc.Objects.OfType<Param_Mesh>().Single(p=>p.NickName=="Actual closed wing mesh / study input");
 var study=doc.Objects.OfType<GH_Component>().Single(c=>c.ComponentGuid==new Guid("4823e5ad-f4fb-4b62-96e3-127989a184b5"));
 var run=study.Params.Input.Single(p=>p.Name=="Run").Sources.Single() as GH_BooleanToggle;if(run==null)throw new Exception("Expected Run toggle");
 var idle=Stock("cb2c7d3c-41b4-4c6d-a6bd-9235bd2851bb","Idle wing preview / NOT Run",3420,340);idle.Params.Input[0].AddSource(run);
 var preview=Stock("008e9a6f-478a-4813-8c8a-546273bc3a6b","Editable wing preview / Run off only",3680,340);preview.Params.Input[0].AddSource(wing);preview.Params.Input[1].AddSource(idle.Params.Output[0]);preview.Hidden=false;wing.Hidden=true;
 if(!ids.IsSubsetOf(doc.Objects.Select(o=>o.InstanceGuid))||doc.Objects.Count!=ids.Count+2)throw new Exception("Original ID/inventory changed");
 foreach(var c in doc.Objects.OfType<GH_Component>())if(before.ContainsKey(c.InstanceGuid)&&before[c.InstanceGuid]!=Wires(c))throw new Exception("Original component wire changed");
 var staged=Path.Combine(output,"35-patched.gh");if(!new GH_DocumentIO{Document=doc}.SaveQuiet(staged))throw new Exception("Cannot save staged archive");if(Hash(path)!=beforeHash)throw new Exception("Source changed concurrently");File.Copy(staged,path,true);
 File.WriteAllText(Path.Combine(output,"audit.json"),new JsonObject{["source_before_sha256"]=beforeHash,["source_after_sha256"]=Hash(path),["preserved_original_ids"]=ids.Count,["added_objects"]=2,["changed_original_wires"]=0,["hidden_original_mesh"]=wing.InstanceGuid.ToString(),["preview_component"]=preview.InstanceGuid.ToString()}.ToJsonString());
 Console.WriteLine("Idle wing preview patched; backup/audit: "+output);
}finally{doc.Dispose();}
