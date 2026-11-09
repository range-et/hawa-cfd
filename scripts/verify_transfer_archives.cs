// Verify appended ports without modifying the original archived examples.
using Grasshopper.Kernel;
using System.Xml.Linq;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";var output=root+"/results/atmosphere-nesting/archives";System.IO.Directory.CreateDirectory(output);var report=new JsonArray();
var layouts=new Dictionary<string,int>{{"3c7b9535-cfa0-473e-8dbb-61c984374f10",6},{"3c7b9535-cfa0-473e-8dbb-61c984374f13",7},{"3c7b9535-cfa0-473e-8dbb-61c984374f15",9},{"a7bb3b0a-ae4f-42ae-9301-a3c55f077123",6},{"a7bb3b0a-ae4f-42ae-9301-a3c55f077124",4},{"a7bb3b0a-ae4f-42ae-9301-a3c55f077129",7},{"a7bb3b0a-ae4f-42ae-9301-a3c55f077130",5}};
foreach(var path in System.IO.Directory.GetFiles(root+"/examples","*.gh",System.IO.SearchOption.AllDirectories).Where(p=>!System.IO.Path.GetFileName(p).StartsWith("09-"))){
 var a=new GH_IO.Serialization.GH_Archive();if(!a.ReadFromFile(path))throw new Exception("Read failed");var xml=XDocument.Parse(a.Serialize_Xml());var d=new GH_Document();if(!a.ExtractObject(d,"Definition"))throw new Exception("Extract failed");
 if(a.Messages.Any(m=>m.Type.ToString().ToLowerInvariant().Contains("error")||m.Message.Contains("missing")||m.Message.Contains("corrupt")))throw new Exception("Archive diagnostics: "+path);
 int checkedPorts=0;
 foreach(var obj in xml.Descendants("chunk").Where(c=>c.Attribute("name")?.Value=="Object")){
  var guid=obj.Element("items")?.Elements("item").FirstOrDefault(i=>i.Attribute("name")?.Value=="GUID")?.Value;if(guid==null||!layouts.ContainsKey(guid))continue;
  var data=obj.Element("chunks").Elements("chunk").Single();var ident=data.Element("items").Elements("item").Single(i=>i.Attribute("name")?.Value=="InstanceGuid").Value;
  var c=d.Objects.OfType<GH_Component>().Single(o=>o.InstanceGuid.ToString()==ident);if(c.Params.Input.Count!=layouts[guid])throw new Exception("Modern port count mismatch");
  if(new[]{"Hawa Plane Field","Hawa Isosurface","Hawa Flow Display","Hawa Surface Field"}.Contains(c.Name)&&c.Params.Input[0].Access!=GH_ParamAccess.list)throw new Exception("Frame list migration failed");
  foreach(var p in data.Element("chunks").Elements("chunk").Where(c=>c.Attribute("name")?.Value=="param_input")){
   int i=int.Parse(p.Attribute("index").Value);var items=p.Element("items").Elements("item").ToArray();var id=items.Single(v=>v.Attribute("name")?.Value=="InstanceGuid").Value;
   if(c.Params.Input[i].InstanceGuid.ToString()!=id)throw new Exception("Port identity changed");var wires=items.Where(v=>v.Attribute("name")?.Value=="Source").Select(v=>v.Value).OrderBy(v=>v).ToArray();if(!wires.SequenceEqual(c.Params.Input[i].Sources.Select(v=>v.InstanceGuid.ToString()).OrderBy(v=>v)))throw new Exception("Wire changed");checkedPorts++;
  }
 }
 var copy=output+"/"+System.IO.Path.GetFileName(path);if(!new GH_DocumentIO{Document=d}.SaveQuiet(copy))throw new Exception("Roundtrip save failed");d.Dispose();var b=new GH_IO.Serialization.GH_Archive();var again=new GH_Document();if(!b.ReadFromFile(copy)||!b.ExtractObject(again,"Definition"))throw new Exception("Roundtrip read failed");again.Dispose();report.Add(new JsonObject{["file"]=System.IO.Path.GetFileName(path),["checked_original_ports"]=checkedPorts,["roundtrip"]=true});
}
System.IO.File.WriteAllText(output+"/report.json",report.ToJsonString());Console.WriteLine(report.ToJsonString());
