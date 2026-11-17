// Rhino MCP only; close source example 35 first. No solution or active-canvas change.
// Preserves original IDs, values and wires, adding only explicit stock mesh settings.
// Source tessellation changes: rerun the study. The CFD grid remains unchanged.
using System.IO;
using System.Drawing;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Special;
var root="/Users/r2d2/Desktop/hawa-wing-wrapup-integration";
var path=Path.Combine(root,"examples/grasshopper/35-parametric-wing-study.gh");
if(Grasshopper.Instances.DocumentServer.Any(d=>string.Equals(d.FilePath,path,StringComparison.OrdinalIgnoreCase)))throw new Exception("Close source example 35 first.");
var output=Path.Combine(root,"results","wing-meshing-settings-patch",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(output);
string Hash(string p)=>Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p))).ToLowerInvariant();
var beforeHash=Hash(path);File.Copy(path,Path.Combine(output,"35-before.gh"),false);
var io=new GH_DocumentIO();if(!io.Open(path))throw new Exception("Cannot read example");var doc=io.Document;
string Wires(GH_Component c)=>string.Join(";",c.Params.Input.SelectMany((p,i)=>p.Sources.Select(s=>i+":"+s.InstanceGuid)));
var ids=doc.Objects.Select(o=>o.InstanceGuid).ToHashSet();var before=doc.Objects.OfType<GH_Component>().ToDictionary(c=>c.InstanceGuid,Wires);
try{
 const string label="Fixed wing tessellation / independent of document mesh";
 if(doc.Objects.Any(o=>o.NickName==label))throw new Exception("Explicit meshing settings already exist");
 var mesh=doc.Objects.OfType<GH_Component>().Single(c=>c.ComponentGuid==new Guid("60e7defa-8b21-4ee1-99aa-a9223d6134ff"));
 if(mesh.Params.Input.Count!=2||mesh.Params.Input[1].Sources.Count!=0)throw new Exception("Expected one Mesh Brep with unwired settings input");
 var proxy=Grasshopper.Instances.ComponentServer.EmitObjectProxy(new Guid("4a0180e5-d8f9-46e7-bd34-ced804601462"));
 if(proxy==null)throw new Exception("Stock Custom Settings component is unavailable");
 var settings=(GH_Component)proxy.CreateInstance();settings.CreateAttributes();settings.Attributes.Pivot=new PointF(1980,650);settings.NickName=label;settings.Hidden=true;
 if(settings.Params.Input.Count!=10||settings.Params.Output.Count!=1)throw new Exception("Unexpected stock Custom Settings ports");
 for(int i=0;i<3;i++){var parameter=(Param_Boolean)settings.Params.Input[i];parameter.PersistentData.Clear();parameter.SetPersistentData(true);}
 for(int i=3;i<5;i++){var parameter=(Param_Integer)settings.Params.Input[i];parameter.PersistentData.Clear();parameter.SetPersistentData(0);}
 var values=new[]{0d,.0005,10d,.005,.02};
 for(int i=5;i<10;i++){var parameter=(Param_Number)settings.Params.Input[i];parameter.PersistentData.Clear();parameter.SetPersistentData(values[i-5]);}
 doc.AddObject(settings,false);mesh.Params.Input[1].AddSource(settings.Params.Output[0]);
 var group=doc.Objects.OfType<GH_Group>().Single(g=>g.NickName=="03 / Ordinary GH loft, caps and closed mesh");group.AddObject(settings.InstanceGuid);
 if(!ids.IsSubsetOf(doc.Objects.Select(o=>o.InstanceGuid))||doc.Objects.Count!=ids.Count+1)throw new Exception("Original ID/inventory changed");
 foreach(var c in doc.Objects.OfType<GH_Component>())if(before.ContainsKey(c.InstanceGuid)){
  var after=Wires(c);
  if(c==mesh){mesh.Params.Input[1].RemoveSource(settings.Params.Output[0]);if(before[c.InstanceGuid]!=Wires(c))throw new Exception("Unexpected original Mesh Brep wire change");mesh.Params.Input[1].AddSource(settings.Params.Output[0]);}
  else if(before[c.InstanceGuid]!=after)throw new Exception("Original component wire changed");
 }
 var staged=Path.Combine(output,"35-patched.gh");if(!new GH_DocumentIO{Document=doc}.SaveQuiet(staged))throw new Exception("Cannot save staged archive");if(Hash(path)!=beforeHash)throw new Exception("Source changed concurrently");File.Copy(staged,path,true);
 File.WriteAllText(Path.Combine(output,"audit.json"),new JsonObject{["source_before_sha256"]=beforeHash,["source_after_sha256"]=Hash(path),["preserved_original_ids"]=ids.Count,["added_objects"]=1,["added_wires"]=1,["changed_original_wires"]=0,["settings_component"]=settings.InstanceGuid.ToString(),["source_mesh_changed"]=true,["requires_new_study"]=true,["cfd_grid_changed"]=false}.ToJsonString());
 Console.WriteLine("Explicit wing tessellation patched; rerun geometry and study. Backup/audit: "+output);
}finally{doc.Dispose();}
