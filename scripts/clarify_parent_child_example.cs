// Run through Rhino MCP. Edit presentation only, then verify the saved archive.
using System.IO;
using System.Drawing;
using System.Xml.Linq;
using System.Text.Json;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
var root="/Users/r2d2/Desktop/hawa-canvas-36";
var source=root+"/examples/grasshopper/33-neutral-city-to-pond.gh";
var output=root+"/results/issue36";Directory.CreateDirectory(output);
var backup=output+"/original-33.gh";if(!File.Exists(backup))File.Copy(source,backup);
var archive=new GH_IO.Serialization.GH_Archive();if(!archive.ReadFromFile(source))throw new Exception("Cannot read example 33");
var before=XDocument.Parse(archive.Serialize_Xml());var d=new GH_Document();
if(!archive.ExtractObject(d,"Definition"))throw new Exception("Cannot load example 33");
try{
 if(d.Objects.OfType<GH_BooleanToggle>().Any(t=>t.Value))throw new Exception("Source must remain idle");
 var panels=d.Objects.OfType<GH_Panel>().Where(p=>p.NickName.StartsWith("Hawa guide / ")).ToDictionary(p=>p.NickName);
 var groups=d.Objects.OfType<GH_Group>().ToArray();
 if(groups.Length!=3 || panels.Count!=7)throw new Exception("Unexpected presentation inventory");
 foreach(var p in panels.Values)if(p.Sources.Count!=0||p.Recipients.Count!=0)throw new Exception("Guide is connected to functional data");
 var allowed=panels.Values.Select(p=>p.InstanceGuid.ToString()).Concat(groups.Select(g=>g.InstanceGuid.ToString())).ToHashSet();
 panels["Hawa guide / purpose"].UserText="HAWA / 33\nPARENT -> CHILD -> FINER CHILD\n\nA supplies B. B consumes A and supplies C. Each stage is a separate air simulation and recording; data flows one way.\n\nA / city: outer parent, 1 m cells.\nB / neighbourhood: local child and next parent, 0.5 m cells.\nC / pond: finer child, 0.25 m cells.\n\nGeographic names are examples, not domain types. Pond means air over low-roughness ground, not water or a free surface.";
 panels["Hawa guide / operation"].UserText="RUN / FIVE STAGE CONTROLS\nSave a copy; choose three NEW recording directories and two NEW boundary files. Open with all controls off.\n\nEnable A Record, B Capture, B Record, C Capture and C Record. Each waits for upstream data. A child does not update its parent. Pause acts on its own Record; disable Record to cancel.\n\nC capture starts at B time 0.369504 s, excluding startup pressure. C uses 1792 steps. Keep supplied durations and playback frames when testing these defaults.";
 panels["Hawa guide / mapping"].UserText="ONE VIEW / THREE SEPARATE CASES\nAll three Playback outputs feed Shared slice at the same absolute time. The finest containing frame owns each sample, including its solid or invalid mask. A parent does not fill through a child mask.\n\nMove Shared slice height / m. Above a child, the parent remains visible. This combines views; it does not couple grids or rerun a solver.\n\nOffline boundary transfer here differs from coupled 2:1 refinement (example 15). See docs/parent-child-domains.md. Hide unrelated native previews before comparing results.";
 string[] prefixes={"A / city","B / neighbourhood","C / pond"};
 string[] roles={"A / OUTER PARENT (city)","B / LOCAL CHILD + PARENT OF C (neighbourhood)","C / FINER CHILD (pond)"};
 string[] counts={"32 x 24 x 16","24 x 24 x 16","24 x 24 x 16"};
 string[] spacing={"1","0.5","0.25"};
 string[] flow={"Produces the recording used by B Capture.\nStart: A / city / Record.","Consumes A's captured boundary data.\nProduces the recording used by C Capture.\nStart: B / neighbourhood / Capture, then Record (automatic waiting).","Consumes B's captured boundary data.\nNo feedback to A or B.\nStart: C / pond / Capture, then Record (automatic waiting)."};
 for(int i=0;i<3;i++){
  var group=groups.Single(g=>g.NickName==prefixes[i]||g.NickName==roles[i]);group.NickName=roles[i];
  var panel=panels["Hawa guide / stage "+i];
  panel.UserText=roles[i]+"\n\n"+flow[i]+"\n\n"+counts[i]+" sample centres; "+spacing[i]+" m cell spacing. These counts are not metres.\nShared closed buildings are reclassified on this grid. The floor is half a cell below its first centre.\n\nA finished recording is not atmospheric qualification.";
 }
 foreach(var panel in panels.Values){panel.Properties.Wrap=true;panel.Properties.Font=new Font("Helvetica",12);}
 var candidate=output+"/annotated-33.gh";
 if(!new GH_DocumentIO{Document=d}.SaveQuiet(candidate))throw new Exception("Save failed");
 var reopened=new GH_IO.Serialization.GH_Archive();if(!reopened.ReadFromFile(candidate))throw new Exception("Reopen failed");
 var after=XDocument.Parse(reopened.Serialize_Xml());
 Dictionary<string,XElement> Objects(XDocument xml)=>xml.Descendants("chunk").Where(c=>c.Attribute("name")?.Value=="Object").ToDictionary(c=>c.Element("chunks").Elements("chunk").Single().Element("items").Elements("item").Single(v=>v.Attribute("name")?.Value=="InstanceGuid").Value,c=>c);
 var a=Objects(before);var b=Objects(after);
 if(!a.Keys.OrderBy(x=>x).SequenceEqual(b.Keys.OrderBy(x=>x)))throw new Exception("Object identities changed");
 foreach(var id in a.Keys.Except(allowed))if(!XNode.DeepEquals(a[id],b[id]))throw new Exception("Functional archive changed: "+id);
 foreach(var id in allowed){
  var oldData=a[id].Element("chunks").Elements("chunk").Single();var newData=b[id].Element("chunks").Elements("chunk").Single();
  if(oldData.Element("items").Elements("item").Where(v=>v.Attribute("name")?.Value=="InstanceGuid").Single().Value!=newData.Element("items").Elements("item").Where(v=>v.Attribute("name")?.Value=="InstanceGuid").Single().Value)throw new Exception("Presentation identity changed");
  var oldMembers=oldData.Descendants("item").Where(v=>v.Attribute("name")?.Value=="ID").Select(v=>v.ToString()).ToArray();
  var newMembers=newData.Descendants("item").Where(v=>v.Attribute("name")?.Value=="ID").Select(v=>v.ToString()).ToArray();
  if(!oldMembers.SequenceEqual(newMembers))throw new Exception("Group membership changed");
 }
 File.WriteAllText(output+"/after.xml",reopened.Serialize_Xml());
 File.Copy(candidate,source,true);
 var report=new {objects=a.Count,presentation_objects=allowed.Count,unchanged_functional_objects=a.Count-allowed.Count,object_ids_preserved=true,functional_archives_identical=true,group_memberships_preserved=true,source_idle=true};
 File.WriteAllText(output+"/preservation.json",JsonSerializer.Serialize(report,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine(JsonSerializer.Serialize(report));
}finally{d.Dispose();}
