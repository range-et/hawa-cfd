// Run through Rhino MCP run_csharp after installing Hawa. Does not solve graphs.
// Preserves functional object IDs, connections and values. Example 09 is excluded.
using System.Drawing;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
var root="/Users/r2d2/Desktop/hawa-cfd";
var notes=JsonNode.Parse(System.IO.File.ReadAllText(root+"/examples/grasshopper/annotations.json"));
var report=new JsonArray();
foreach(var file in System.IO.Directory.GetFiles(root+"/examples/grasshopper","*.gh").OrderBy(x=>x)){
 int number=int.Parse(System.IO.Path.GetFileName(file).Substring(0,2));if(number==9)continue;
 var io=new GH_DocumentIO();if(!io.Open(file))throw new Exception("Cannot open "+file);var d=io.Document;
 IEnumerable<IGH_Param> Inputs(IGH_DocumentObject o)=>o is GH_Component c?c.Params.Input:o is IGH_Param p?new[]{p}:Array.Empty<IGH_Param>();
 string[] Wires()=>d.Objects.SelectMany(o=>Inputs(o).SelectMany(p=>p.Sources.Select(s=>s.InstanceGuid+">"+p.InstanceGuid))).OrderBy(x=>x).ToArray();
 var before=Wires();
 // Replace old presentation notes, including notes from a previous cleanup run.
 foreach(var o in d.Objects.Where(o=>o is GH_Group||o is GH_Panel p&&p.Sources.Count==0&&p.Recipients.Count==0&&(p.UserText.Length>80||p.NickName.StartsWith("Hawa guide"))).ToArray())d.RemoveObject(o,false);
 var objects=d.Objects.ToArray();var rank=objects.ToDictionary(o=>o.InstanceGuid,o=>0);
 for(int pass=0;pass<objects.Length;pass++){
  bool changed=false;
  foreach(var o in objects){int next=0;foreach(var p in Inputs(o))foreach(var source in p.Sources){var owner=source.Attributes.GetTopLevel.DocObject;if(owner!=null&&rank.ContainsKey(owner.InstanceGuid))next=Math.Max(next,rank[owner.InstanceGuid]+1);}if(next!=rank[o.InstanceGuid]){rank[o.InstanceGuid]=next;changed=true;}}
  if(!changed)break;if(pass==objects.Length-1)throw new Exception("Cyclic graph requires manual layout: "+file);
 }
 // Place independent controls beside their first consumer, reducing long crossing wires.
 for(int level=rank.Values.Max();level>=0;level--)foreach(var o in objects.Where(o=>rank[o.InstanceGuid]==level)){
  var consumers=objects.Where(other=>Inputs(other).Any(p=>p.Sources.Any(source=>source.Attributes.GetTopLevel.DocObject?.InstanceGuid==o.InstanceGuid))).ToArray();
  if(consumers.Length>0)rank[o.InstanceGuid]=Math.Max(rank[o.InstanceGuid],consumers.Min(c=>rank[c.InstanceGuid])-1);
 }
 float bottom=0;
 foreach(var column in objects.GroupBy(o=>rank[o.InstanceGuid]).OrderBy(g=>g.Key)){
  float x=column.Key*350,y=0;var group=new GH_Group();group.CreateAttributes();var names=string.Join(" ",column.Select(o=>o.Name));string stage=names.Contains("Body Preview")?"BODY / OUTPUT":names.Contains("Body Loads")?"FIELDS / LOADS":names.Contains("Snapshot")||names.Contains("Playback")?"CAPTURE / PLAYBACK":names.Contains("Solve")||names.Contains("Evaluate")||names.Contains("Record")?"RUN / CONTROL":names.Contains("Moving Body")?"PREPARE BODY":names.Contains("Case")?"BUILD CASE":names.Contains("Geometry")||names.Contains("Wing")?"GEOMETRY":names.Contains("Domain")||names.Contains("Physics")?"DOMAIN / PHYSICS":column.Key==0?"INPUTS":"RESULTS / CONTROLS";group.NickName=$"{column.Key+1:00} / {stage}";
  group.Colour=Color.FromArgb(65,column.Key%2==0?47:61,173,151);d.AddObject(group,false);
  foreach(var o in column.OrderBy(o=>o.Attributes.Pivot.Y)){
   o.Attributes.Pivot=new PointF(x+70,y+70);o.Attributes.ExpireLayout();o.Attributes.PerformLayout();
   if(o is GH_Panel panel){panel.Attributes.Bounds=new RectangleF(x+20,y+20,280,140);panel.Properties.Font=new Font("Helvetica",11);panel.Properties.Wrap=true;}
   else if(o is GH_NumberSlider slider){var b=slider.Attributes.Bounds;slider.Attributes.Bounds=new RectangleF(b.X,b.Y,260,b.Height);}
   group.AddObject(o.InstanceGuid);y+=Math.Max(145,o.Attributes.Bounds.Height+65);
  }
  bottom=Math.Max(bottom,y);group.Attributes.ExpireLayout();group.Attributes.PerformLayout();
 }
 var n=notes[number.ToString()]!;
 void Note(string label,string text,float x){var p=new GH_Panel();p.CreateAttributes();p.NickName="Hawa guide / "+label;p.UserText=text;p.Properties.Font=new Font("Helvetica",12);p.Properties.Wrap=true;p.Properties.Multiline=true;p.Properties.DrawIndices=false;p.Properties.DrawPaths=false;var alignment=p.Properties.GetType().GetProperty("Alignment");alignment.SetValue(p.Properties,Enum.Parse(alignment.PropertyType,"Left"));p.Properties.Colour=Color.FromArgb(226,242,237);p.Attributes.Pivot=new PointF(x,-420);p.Attributes.Bounds=new RectangleF(x,-420,410,340);d.AddObject(p,false);}
 Note("purpose",$"HAWA / {number:00}\n{n["title"]}\n\n{n["explore"]}",0);
 Note("operation","START / PAUSE / RESET\nRead left to right. Inputs and controls are at the left; results are at the right.\n\nSave a copy before editing. Wait for preparation. Enable Run only when ready. Solve: Run false pauses; Reset clears state. Evaluate/Search/Record: disabling cancels.\n\nFor recordings, set a new absolute directory before starting.",440);
 Note("limits",$"CHECK THE RESULT\n{n["limits"]}\n\nUse the case report and component messages. Compare physical time and fixed colour ranges.\n\nExamples and MCP instructions: README.md and ../../docs/agents/rhino-mcp.md",880);
 if(!before.SequenceEqual(Wires()))throw new Exception("Connection changed during layout: "+file);
 string backup=root+"/results/motion/example-backups/"+System.IO.Path.GetFileName(file);System.IO.Directory.CreateDirectory(System.IO.Path.GetDirectoryName(backup));if(!System.IO.File.Exists(backup))System.IO.File.Copy(file,backup);
 if(!new GH_DocumentIO{Document=d}.SaveQuiet(file))throw new Exception("Save failed: "+file);
 report.Add(new JsonObject{["file"]=System.IO.Path.GetFileName(file),["wires"]=before.Length,["functional_objects"]=objects.Length,["columns"]=rank.Values.Max()+1,["connections_preserved"]=true});d.Dispose();
}
System.IO.File.WriteAllText(root+"/results/motion/annotation-report.json",report.ToJsonString());
Console.WriteLine("Annotated "+report.Count+" supported definitions; legacy 09 preserved");
