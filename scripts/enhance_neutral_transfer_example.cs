// Update only example 33. Preserve existing object IDs and solver wires.
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Special;
using Rhino.Geometry;
using System.Drawing;
var root="/Users/r2d2/Desktop/hawa-cfd";var source=root+"/examples/grasshopper/33-neutral-city-to-pond.gh";
var io=new GH_DocumentIO();if(!io.Open(source))throw new Exception("Read failed");var d=io.Document;
var before=d.Objects.Select(o=>o.InstanceGuid).ToHashSet();
var planes=d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Plane Field").OrderBy(c=>c.Attributes.Pivot.Y).ToArray();
var playback=d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Playback").OrderBy(c=>c.Attributes.Pivot.Y).ToArray();
foreach(var p in playback)if(!planes[0].Params.Input[0].Sources.Contains(p.Params.Output[0]))planes[0].Params.Input[0].AddSource(p.Params.Output[0]);
planes[0].NickName="Shared slice / finest domain";planes[1].Hidden=planes[2].Hidden=true;
void Number(GH_Component c,int i,double v){var p=(Param_Number)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
void Integer(GH_Component c,int i,int v){var p=(Param_Integer)c.Params.Input[i];p.PersistentData.Clear();p.SetPersistentData(v);}
var captures=d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Boundary Capture").OrderBy(c=>c.Attributes.Pivot.Y).ToArray();
Number(captures[1],4,.3695041722813605);Integer(d.Objects.OfType<GH_Component>().Single(c=>c.NickName=="C / pond / record"),2,1792);Integer(playback[2],1,56);
GH_Component Add(Guid guid,string label,float x,float y){var c=(GH_Component)Grasshopper.Instances.ComponentServer.EmitObjectProxy(guid).CreateInstance();c.CreateAttributes();c.NickName=label;c.Attributes.Pivot=new PointF(x,y);d.AddObject(c,false);return c;}
if(!d.Objects.Any(o=>o.NickName=="Shared slice height / m")){
 var slider=new GH_NumberSlider();slider.CreateAttributes();slider.NickName="Shared slice height / m";slider.Slider.Minimum=.5m;slider.Slider.Maximum=15.5m;slider.Slider.DecimalPlaces=2;slider.SetSliderValue(1.5m);slider.Attributes.Pivot=new PointF(2590,1110);d.AddObject(slider,false);
 var point=Add(new Guid("3581f42a-9592-4549-bd6b-1c0fc39d067b"),"Slice origin",2870,1110);Number(point,0,.5);Number(point,1,.5);point.Params.Input[2].AddSource(slider);point.Hidden=true;
 var xy=Add(new Guid("17b7152b-d30d-4d50-b9ef-c9fe25576fc2"),"Slice plane",3060,1110);xy.Params.Input[0].AddSource(point.Params.Output[0]);xy.Hidden=true;
 var rect=Add(new Guid("d93100b6-d50b-40b2-831a-814659dc38e3"),"Slice extent",3250,1110);rect.Params.Input[0].AddSource(xy.Params.Output[0]);((Param_Interval)rect.Params.Input[1]).PersistentData.Clear();((Param_Interval)rect.Params.Input[1]).SetPersistentData(new Interval(0,31));((Param_Interval)rect.Params.Input[2]).PersistentData.Clear();((Param_Interval)rect.Params.Input[2]).SetPersistentData(new Interval(0,23));rect.Hidden=true;planes[0].Params.Input[1].AddSource(rect.Params.Output[0]);
}
string[] labels={"CITY / 1 m cells","NEIGHBOURHOOD / 0.5 m cells","POND / 0.25 m cells"};var positions=new[]{new Point3d(.5,23.5,15.5),new Point3d(4.25,15.75,7.75),new Point3d(8.125,12.875,3.875)};
for(int i=0;i<3;i++)if(!d.Objects.Any(o=>o.NickName==labels[i])){
 var tag=Add(new Guid("5a41528b-12b9-40dc-a3f2-842034d267c4"),labels[i],650,680+1500*i);((Param_Plane)tag.Params.Input[0]).SetPersistentData(new Plane(positions[i],Vector3d.XAxis,Vector3d.YAxis));((Param_String)tag.Params.Input[1]).SetPersistentData(labels[i]);Number(tag,2,.35);((Param_Colour)tag.Params.Input[3]).SetPersistentData(Color.DarkSlateGray);
}
// Keep prior object IDs, but use screen-facing native GH text for legibility.
foreach(var tag in d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Text Tag 3D"))tag.Hidden=true;
for(int i=0;i<3;i++)if(!d.Objects.Any(o=>o.NickName=="Label / "+labels[i])){
 var tag=Add(new Guid("3b220754-4114-4170-b6c3-b286b86ed524"),"Label / "+labels[i],900,680+1500*i);((Param_Point)tag.Params.Input[0]).SetPersistentData(positions[i]);((Param_String)tag.Params.Input[1]).SetPersistentData(labels[i]);((Param_Colour)tag.Params.Input[2]).SetPersistentData(Color.FromArgb(20,35,40));
}
foreach(var stats in d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Flow Statistics"))stats.Hidden=true;
var labelPoints=new[]{new Point3d(.5,23.5,16.5),new Point3d(4.25,15.75,8.75),new Point3d(20,-5,0)};
for(int i=0;i<3;i++){var p=(Param_Point)d.Objects.OfType<GH_Component>().Single(c=>c.NickName=="Label / "+labels[i]).Params.Input[0];p.PersistentData.Clear();p.SetPersistentData(labelPoints[i]);}
if(!d.Objects.Any(o=>o.NickName=="Pond label leader")){
 var leader=new Param_Line();leader.CreateAttributes();leader.NickName="Pond label leader";leader.Attributes.Pivot=new PointF(1150,3680);leader.SetPersistentData(new Line(new Point3d(13.875,7.125,3.875),labelPoints[2]));d.AddObject(leader,false);
}
var leaderLine=(Param_Line)d.Objects.Single(o=>o.NickName=="Pond label leader");leaderLine.PersistentData.Clear();leaderLine.SetPersistentData(new Line(new Point3d(13.875,7.125,3.875),labelPoints[2]));
if(!d.Objects.Any(o=>o.NickName=="Shared speed legend")){
 var legend=Add(new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077136"),"Shared speed legend",2410,1110);legend.Params.Input[0].AddSource(d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Color Map").OrderBy(c=>c.Attributes.Pivot.Y).First().Params.Output[0]);((Param_Plane)legend.Params.Input[1]).SetPersistentData(new Plane(new Point3d(34,2,1.5),Vector3d.XAxis,Vector3d.YAxis));Number(legend,2,10);
}
// SetPersistentData appends to a default plane; explicitly replace that default.
var legendPlane=(Param_Plane)d.Objects.OfType<GH_Component>().Single(c=>c.NickName=="Shared speed legend").Params.Input[1];legendPlane.PersistentData.Clear();legendPlane.SetPersistentData(new Plane(new Point3d(34,2,1.5),Vector3d.XAxis,Vector3d.YAxis));
foreach(var panel in d.Objects.OfType<GH_Panel>()){
 if(panel.NickName=="Hawa guide / operation")panel.UserText="RUN / AUTOMATIC DEPENDENCIES\nSave a copy and choose five new absolute paths. Open with all Record and Capture controls off.\nEnable the five stage controls. Each waits for its upstream result; no UI waiting loop is used. Pause acts on the running Record. Disable to cancel.\nThe pond capture starts at neighbourhood t=0.369504 s to exclude its startup pressure transient. Its 1792 steps end at the same absolute time as the other cases. If physics or capture time changes, match the child duration and playback frame.";
 if(panel.NickName=="Hawa guide / mapping")panel.UserText="ONE VIEW / THREE DOMAINS\nAll three Playback frames feed Shared slice. The finest containing domain supplies each sample. Move the slice-height slider; above a child, the parent remains visible. Domain tags identify each grid.\nThe renderer trims faces at halfway building walls and reconstructs boundary colours. Raw sample validity stays unchanged. Curved-link fields keep conservative masking.\nTimes must agree. Hide an unrelated native case with its Domain, Body and Field checkboxes. Field 0 is not this recording.\nTransfer includes velocity, pressure, strain, initial fields, absolute time and source hashes. Matching wall-filter history is retained.";
}
foreach(var t in d.Objects.OfType<GH_BooleanToggle>())t.Value=false;
if(!before.IsSubsetOf(d.Objects.Select(o=>o.InstanceGuid)))throw new Exception("Existing object lost");
if(!new GH_DocumentIO{Document=d}.SaveQuiet(source))throw new Exception("Save failed");d.Dispose();Console.WriteLine("Updated shared slice, domain labels and startup window; source saved idle");
