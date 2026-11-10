// Read old/new schemas without modal IO dialogs. Source archives stay unchanged.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using System.Text.Json.Nodes;
using System.Xml.Linq;
var root="/Users/r2d2/Desktop/hawa-cfd";var report=new JsonArray();
foreach(int number in new[]{28,29,30}){
 var path=System.IO.Directory.GetFiles(root+"/examples/grasshopper",number+"-*.gh").Single();
 var archive=new GH_IO.Serialization.GH_Archive();if(!archive.ReadFromFile(path))throw new Exception("Read failed");
 var xml=XDocument.Parse(archive.Serialize_Xml());
 var container=xml.Descendants("chunk").First(c=>c.Attribute("name")?.Value=="Object"&&c.Element("items")?.Elements("item").Any(x=>x.Attribute("name")?.Value=="GUID"&&x.Value=="3c7b9535-cfa0-473e-8dbb-61c984374f15")==true).Element("chunks").Elements("chunk").Single();
 var d=new GH_Document();if(!archive.ExtractObject(d,"Definition"))throw new Exception("Extract failed");
 var errors=archive.Messages.Where(m=>m.Type.ToString().ToLowerInvariant().Contains("error")||m.Message.Contains("missing")||m.Message.Contains("corrupt")).Select(m=>m.Message).ToArray();
 if(errors.Length>0)throw new Exception(string.Join(" | ",errors));
 var c=d.Objects.OfType<GH_Component>().Single(x=>x.ComponentGuid==new Guid("3c7b9535-cfa0-473e-8dbb-61c984374f15"));
 var archived=container.Element("chunks").Elements("chunk").Where(x=>x.Attribute("name")?.Value=="param_input").OrderBy(x=>int.Parse(x.Attribute("index").Value)).ToArray();
 for(int i=0;i<archived.Length;i++){
  var items=archived[i].Element("items").Elements("item").ToArray();var id=items.Single(x=>x.Attribute("name")?.Value=="InstanceGuid").Value;
  if(c.Params.Input[i].InstanceGuid.ToString()!=id)throw new Exception("Parameter GUID changed");
  var sources=items.Where(x=>x.Attribute("name")?.Value=="Source").Select(x=>x.Value).OrderBy(x=>x).ToArray();
  if(!sources.SequenceEqual(c.Params.Input[i].Sources.Select(x=>x.InstanceGuid.ToString()).OrderBy(x=>x)))throw new Exception("Wires changed");
 }
 if(c.Params.Input.Count!=9||c.Params.Output.Count!=2)throw new Exception("Wrong modern layout");
 if(number<30&&(((Param_Integer)c.Params.Input[6]).PersistentData.AllData(true).Cast<Grasshopper.Kernel.Types.GH_Integer>().Single().Value!=0||((Param_Number)c.Params.Input[7]).PersistentData.AllData(true).Cast<Grasshopper.Kernel.Types.GH_Number>().Single().Value!=0||!c.Params.Input[8].Optional||c.Params.Input[8].SourceCount!=0))throw new Exception("Wrong appended defaults");
 string copy=root+"/results/atmosphere-coupling/archive-roundtrip-"+number+".gh";if(!new GH_DocumentIO{Document=d}.SaveQuiet(copy))throw new Exception("Save failed");d.Dispose();
 var saved=new GH_IO.Serialization.GH_Archive();var reopened=new GH_Document();if(!saved.ReadFromFile(copy)||!saved.ExtractObject(reopened,"Definition"))throw new Exception("Reopen failed");
 if(saved.Messages.Any(m=>m.Message.Contains("missing")||m.Message.Contains("corrupt")))throw new Exception("Roundtrip archive warnings");reopened.Dispose();
 report.Add(new JsonObject{["example"]=number,["archived_inputs"]=archived.Length,["loaded_inputs"]=9,["guid_and_wires_preserved"]=true,["read_warnings"]=errors.Length,["roundtrip"]=true});
}
System.IO.File.WriteAllText(root+"/results/atmosphere-coupling/archives.json",report.ToJsonString());Console.WriteLine(report.ToJsonString());
