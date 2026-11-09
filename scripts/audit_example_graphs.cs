// Read-only graph/capability inventory. No solver starts or source file writes.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";
var asm=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
var nodes=new JsonArray();var examples=new JsonArray();var used=new HashSet<string>();
JsonArray Ports(IEnumerable<IGH_Param> ps)=>new JsonArray(ps.Select(p=>(JsonNode)new JsonObject{["name"]=p.Name,["description"]=p.Description,["access"]=p.Access.ToString(),["optional"]=p.Optional,["parameter_type"]=p.GetType().Name}).ToArray());
foreach(var t in asm.GetTypes().Where(t=>!t.IsAbstract&&typeof(GH_Component).IsAssignableFrom(t)).OrderBy(t=>t.Name)){
 var c=(GH_Component)Activator.CreateInstance(t);if(c.Exposure==GH_Exposure.hidden)continue;
 nodes.Add(new JsonObject{["type"]=t.Name,["guid"]=c.ComponentGuid.ToString(),["name"]=c.Name,["category"]=c.SubCategory,["inputs"]=Ports(c.Params.Input),["outputs"]=Ports(c.Params.Output)});
}
foreach(var file in System.IO.Directory.GetFiles(root+"/examples","*.gh",System.IO.SearchOption.AllDirectories).OrderBy(f=>f)){
 if(System.IO.Path.GetFileName(file).StartsWith("09-"))continue;
 var archive=new GH_IO.Serialization.GH_Archive();var d=new GH_Document();if(!archive.ReadFromFile(file)||!archive.ExtractObject(d,"Definition"))throw new Exception("Cannot read "+file);
 var warnings=archive.Messages.Where(m=>m.Type.ToString().ToLowerInvariant().Contains("error")||m.Message.Contains("missing")||m.Message.Contains("corrupt")).Select(m=>m.Message).ToArray();if(warnings.Length>0)throw new Exception(file+": "+string.Join(" | ",warnings));
 var objects=d.Objects.ToDictionary(o=>o.InstanceGuid,o=>o);var types=new HashSet<string>();var edges=new JsonArray();
 foreach(var c in d.Objects.OfType<GH_Component>()){
  if(c.GetType().Assembly==asm){types.Add(c.GetType().Name);used.Add(c.GetType().Name);}
  for(int i=0;i<c.Params.Input.Count;i++)foreach(var source in c.Params.Input[i].Sources){
   var owner=source.Attributes.GetTopLevel.DocObject;if(owner==null)continue;
   int port=owner is GH_Component producer?producer.Params.Output.IndexOf(source):0;
   edges.Add(new JsonObject{["from_type"]=owner.GetType().Name,["from_port"]=port,["to_type"]=c.GetType().Name,["to_port"]=i});
  }
 }
 string name=System.IO.Path.GetRelativePath(root,file);
 examples.Add(new JsonObject{["file"]=name,["archive_errors"]=warnings.Length,["sha256"]=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.IO.File.ReadAllBytes(file))).ToLowerInvariant(),["nodes"]=new JsonArray(types.OrderBy(x=>x).Select(x=>JsonValue.Create(x)).ToArray()),["edges"]=edges,["guide_panels"]=d.Objects.OfType<GH_Panel>().Count(p=>p.Sources.Count==0&&p.UserText.Length>80),["true_toggles"]=new JsonArray(d.Objects.OfType<GH_BooleanToggle>().Where(t=>t.Value).Select(t=>JsonValue.Create(t.NickName)).ToArray())});
 d.Dispose();
}
var missing=nodes.Select(n=>n["type"].GetValue<string>()).Where(t=>!used.Contains(t)).ToArray();
var report=new JsonObject{["schema"]=1,["scope"]="Public component and shipped graph inventory; no numerical or host-run claim",["nodes"]=nodes,["examples"]=examples,["nodes_without_example"]=new JsonArray(missing.Select(x=>JsonValue.Create(x)).ToArray())};
System.IO.File.WriteAllText(root+"/docs/coverage-example-graphs.json",report.ToJsonString(new System.Text.Json.JsonSerializerOptions{WriteIndented=true}));
Console.WriteLine("Public nodes="+nodes.Count+" examples="+examples.Count+" missing="+string.Join(",",missing));
