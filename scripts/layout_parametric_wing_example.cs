// Rhino MCP only. Layout existing example 35 AFTER generic annotation; never regenerate.
// No solution/canvas activation. Functional IDs, wires and non-attribute serialization
// must match before editing, after editing, and after staged save/reopen.
using System.Drawing;
using System.IO;
using System.Text;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using System.Xml.Linq;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using GH_IO.Serialization;
var root="/Users/r2d2/Desktop/hawa-wing-wrapup-integration";
var path=Path.Combine(root,"examples/grasshopper/35-parametric-wing-study.gh");
if(Grasshopper.Instances.DocumentServer.Any(d=>string.Equals(d.FilePath,path,StringComparison.OrdinalIgnoreCase)))throw new Exception("Close source example 35 before its layout patch.");
var output=Path.Combine(root,"results","wing-canvas-layout",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(output);
string Digest(byte[] data)=>Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();
string FileHash(string file)=>Digest(File.ReadAllBytes(file));
string Payload(IGH_DocumentObject item){
 var archive=new GH_Archive();if(!archive.AppendObject(item,"Object"))throw new Exception("Cannot serialize "+item.NickName);
 var xml=XDocument.Parse(archive.Serialize_Xml());var chunk=new XElement(xml.Descendants("chunk").First(e=>(string?)e.Attribute("name")=="Object"));
 // Remove only presentation attributes. All parameter data, expressions, toggle
 // values, names, flags, object/port GUIDs and wire serialization remain hashed.
 foreach(var attributes in chunk.Descendants("chunk").Where(e=>(string?)e.Attribute("name")=="Attributes").ToArray())attributes.Remove();
 return Digest(Encoding.UTF8.GetBytes(chunk.ToString(SaveOptions.DisableFormatting)));
}
Dictionary<Guid,string> Values(GH_Document d)=>d.Objects.Where(o=>!(o is GH_Group)).ToDictionary(o=>o.InstanceGuid,Payload);
IEnumerable<IGH_Param> Inputs(IGH_DocumentObject o)=>o is GH_Component c?c.Params.Input:o is IGH_Param p?new[]{p}:Array.Empty<IGH_Param>();
string[] Wires(GH_Document d)=>d.Objects.SelectMany(o=>Inputs(o).SelectMany(p=>p.Sources.Select(s=>s.InstanceGuid+">"+p.InstanceGuid))).OrderBy(x=>x).ToArray();
void Equal(Dictionary<Guid,string> expected,GH_Document d){var actual=Values(d);if(expected.Count!=actual.Count||expected.Any(p=>!actual.TryGetValue(p.Key,out var value)||value!=p.Value))throw new Exception("Functional ID or serialized parameter data changed during layout: "+string.Join(", ",expected.Where(p=>!actual.TryGetValue(p.Key,out var value)||value!=p.Value).Select(p=>d.FindObject(p.Key,false)?.NickName??p.Key.ToString())));}
var sourceHash=FileHash(path);File.Copy(path,Path.Combine(output,"35-before.gh"),false);
var io=new GH_DocumentIO();if(!io.Open(path))throw new Exception("Cannot read example35");var doc=io.Document;
var before=Values(doc);var wires=Wires(doc);var assigned=new HashSet<Guid>();var groups=new Dictionary<string,List<Guid>>();
void Move(IGH_DocumentObject o,string group,float x,float y,float width=0,float height=0){
 if(!assigned.Add(o.InstanceGuid))throw new Exception("Duplicate layout assignment: "+o.NickName);
 o.Attributes.Pivot=new PointF(x,y);o.Attributes.ExpireLayout();o.Attributes.PerformLayout();
 if(o is GH_Panel&&width>0)o.Attributes.Bounds=new RectangleF(x,y,width,height);
 else if(o is GH_NumberSlider){var b=o.Attributes.Bounds;o.Attributes.Bounds=new RectangleF(b.X,b.Y,width>0?width:250,b.Height);}
 if(!groups.ContainsKey(group))groups[group]=new List<Guid>();groups[group].Add(o.InstanceGuid);
}
void Place(string nick,string group,float x,float y,float width=0,float height=0)=>Move(doc.Objects.Single(o=>!(o is GH_Group)&&o.NickName==nick),group,x,y,width,height);
void Hawa(string name,string group,float x,float y)=>Move(doc.Objects.OfType<GH_Component>().Single(o=>o.Name=="Hawa "+name),group,x,y);
try{
 // Existing presentation groups are replaced; every non-group object is retained.
 int removedGroups=doc.Objects.OfType<GH_Group>().Count();foreach(var group in doc.Objects.OfType<GH_Group>().ToArray())doc.RemoveObject(group,false);
 Place("Hawa guide / purpose","00 / READ FIRST",0,-430,410,340);Place("Hawa guide / operation","00 / READ FIRST",450,-430,410,340);Place("Hawa guide / limits","00 / READ FIRST",900,-430,410,340);
 const string a="01 / EDIT SECTIONS AND DIMENSIONS";
 Place("Root NACA",a,0,0,210,80);Place("Tip NACA",a,0,120,210,80);Place("Root chord (m)",a,0,250);Place("Tip chord (m)",a,0,320);Place("Full span (m)",a,0,390);Place("Sections / XZ plane",a,300,490);
 Place("Root / separate airfoil",a,470,60);Place("Tip / separate airfoil",a,470,260);
 const string b="02 / PLACE SECTIONS AND LOFT";
 Place("Quarter-chord alignment",b,750,100);Place("Positive half span",b,750,240);Place("Negative half span",b,750,360);
 Place("Tip + placement",b,1000,240);Place("Tip − placement",b,1000,410);Place("Place positive tip",b,1210,160);Place("Place negative tip",b,1210,350);
 Place("Ordered tip− / root / tip+ profiles",b,1430,180);Place("Loft distinct sections",b,1610,180);
 Place("Fixed planform area (m²)",b,750,550);Place("Mean aerodynamic chord (m)",b,1000,550);Place("Root quarter-chord pivot X",b,750,680);Place("Study pivot (m)",b,1210,680);
 const string c="03 / CLOSED SOLID AND EXPLICIT MESH";
 Place("Cap / closed solid",c,1830,180);Place("Closed loft solid / preview before Run",c,2040,40);Place("Loft solid?",c,2240,0,260,100);
 Place("Fixed wing tessellation / independent of document mesh",c,1830,530);Place("Mesh the actual loft",c,2050,240);Place("Join loft and cap meshes",c,2260,240);Place("Weld mesh seams",c,2440,240);Place("Unify mesh normals",c,2620,240);
 Place("Actual closed wing mesh / study input",c,2820,240);Hawa("Geometry Check",c,2820,460);Place("Mesh admission and resolution",c,3050,400,350,210);
 Place("Idle wing preview / NOT Run",c,2620,650);Place("Editable wing preview / Run off only",c,2840,650);
 const string d="04 / DOMAIN, FLUID AND RUNTIME";
 Place("Initialize runtime",d,0,930);Hawa("Runtime",d,340,930);Place("Embedded runtime",d,580,850,370,160);
 Place("Fixed tunnel / edit bounds (m)",d,0,1130);Place("Cell size (m)",d,0,1220);Hawa("Domain",d,340,1130);Place("Requested grid / CPU limit 500000 cells",d,580,1060,370,140);Hawa("Domain Preview",d,580,1270);
 Place("Synthetic viscosity (m²/s)",d,0,1400);Hawa("Physics",d,340,1400);Hawa("Boundaries",d,600,1460);Hawa("Case",d,1020,1240);
 const string e="05 / RUN AND SELECT A STUDY";
 Place("First angle (deg)",e,1300,880);Place("Second angle (deg)",e,1300,950);Place("Study speed (m/s)",e,1300,1040);
 Place("Angle cases (deg) / ordered sources",e,1650,920);Place("Speed cases (m/s) / cross product",e,1650,1040);Place("Fluid pressure probes (m)",e,1650,1160);
 Place("Settling steps",e,1300,1190);Place("Sample steps",e,1300,1260);Place("Stationarity tolerance (absolute coefficient)",e,1300,1330,300);
 Place("Selected case index",e,1650,1280);Place("Run / explicit re-arm",e,1650,1390);Place("Pause study",e,1650,1460);Place("Cancel study",e,1650,1530);Hawa("Stationary Study",e,2090,1190);
 const string f="06 / READ ACCEPTED WHOLE-BODY LOADS";
 Place("Study progress / failures",f,2330,850,350,170);Place("Ordered case results / rejected slots stay empty",f,2730,850,350,170);Place("Selected capture identity",f,2330,1090,350,180);
 Place("Total selected-body fluid force",f,2760,1160);Place("Total side force +Y (N)",f,2990,1100,300,110);Place("Total drag +X (N) / selected window mean",f,2730,1300,350,100);Place("Total lift +Z (N) / selected window mean",f,2730,1430,350,100);Place("Moment about pivot (N m) / world axes",f,2330,1430,350,100);
 const string g="07 / SELECTED PRESSURE COLOURS";
 Place("Pressure colour lower (Pa)",g,2330,1690);Place("Pressure colour upper (Pa)",g,2330,1760);Place("Pressure sample offset (m)",g,2330,1860);Hawa("Color Map",g,2700,1730);Hawa("Surface Field",g,2920,1730);Hawa("Legend",g,2920,1890);
 Place("Local sampled pressure validity / not local force",g,3140,1660,300,110);Place("Sampled surface pressure (Pa)",g,3140,1810,300,130);
 int plot=0;foreach(string title in new[]{"CL versus angle","CD versus angle","CL versus CD"}){
  float x=plot*1200,y=2250;string group=(8+plot).ToString("00")+" / "+title.ToUpperInvariant()+" — DISPLAY ONLY";plot++;
  Place(title+" / missing X",group,x,y);Place(title+" / missing Y",group,x,y+120);Place(title+" / both coordinates present",group,x+140,y+240);
  Place(title+" / paired X",group,x+280,y);Place(title+" / paired Y",group,x+280,y+120);Place(title+" / display X scale",group,x+280,y+320);Place(title+" / display Y scale",group,x+280,y+390);
  Place(title+" / scale X",group,x+480,y);Place(title+" / scale Y",group,x+480,y+120);Place(title+" / offset X",group,x+660,y);Place(title+" / offset Y",group,x+660,y+120);Place(title+" / scatter only",group,x+890,y+50);
  Place(title+" / axes",group,x+650,y+280);Place(title+" / numeric axes",group,x+450,y+480);Place(title+" / label positions",group,x+650,y+430);Place(title+" / labels",group,x+890,y+410);
 }
 var missing=doc.Objects.Where(o=>!(o is GH_Group)&&!assigned.Contains(o.InstanceGuid)).Select(o=>o.Name+" / "+o.NickName).ToArray();if(missing.Length>0)throw new Exception("Unassigned objects; do not silently scatter them: "+string.Join(" | ",missing));
 foreach(var pair in groups){var group=new GH_Group();group.CreateAttributes();group.NickName="HAWA35 / "+pair.Key;group.Colour=Color.FromArgb(40,54,160,151);doc.AddObject(group,false);foreach(var id in pair.Value)group.AddObject(id);group.Attributes.ExpireLayout();group.Attributes.PerformLayout();}
 Equal(before,doc);if(!wires.SequenceEqual(Wires(doc)))throw new Exception("Wire changed during layout");
 var staged=Path.Combine(output,"35-layout.gh");if(!new GH_DocumentIO{Document=doc}.SaveQuiet(staged))throw new Exception("Cannot save staged layout");
 var check=new GH_DocumentIO();if(!check.Open(staged))throw new Exception("Cannot reopen staged layout");try{Equal(before,check.Document);if(!wires.SequenceEqual(Wires(check.Document)))throw new Exception("Wire changed on roundtrip");}finally{check.Document.Dispose();}
 if(FileHash(path)!=sourceHash)throw new Exception("Source changed concurrently; refusing replacement");File.Copy(staged,path,true);
 var crops=new JsonArray();void Crop(string name,float x,float y,float w,float h)=>crops.Add(new JsonObject{["name"]=name,["x"]=x,["y"]=y,["width"]=w,["height"]=h});
 Crop("guide-and-sections",-90,-480,1800,1260);Crop("loft-and-meshing",1710,-100,1810,900);Crop("domain-and-controls",-90,790,2310,900);Crop("loads-and-pressure",2240,780,1280,1240);for(int i=0;i<3;i++)Crop("plot-"+i,i*1200-80,2150,1190,660);
 var payloads=new JsonObject();foreach(var value in before.OrderBy(p=>p.Key))payloads[value.Key.ToString()]=value.Value;
 File.WriteAllText(Path.Combine(output,"audit.json"),new JsonObject{["source_before_sha256"]=sourceHash,["source_after_sha256"]=FileHash(path),["functional_objects_preserved"]=before.Count,["wires_preserved"]=wires.Length,["old_presentation_groups"]=removedGroups,["new_presentation_groups"]=groups.Count,["non_attribute_serialization_sha256"]=payloads,["staged_roundtrip_checked"]=true,["recommended_canvas_crops"]=crops}.ToJsonString());
 Console.WriteLine("Presentation-only wing layout saved. Backup, identity/value audit and crop bounds: "+output);
}finally{doc.Dispose();}
