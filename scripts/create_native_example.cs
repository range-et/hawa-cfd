using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using System.Drawing;
var root="/Users/r2d2/Desktop/hawa-cfd";
var d=new GH_Document();
var a=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
var c=(GH_Component)Activator.CreateInstance(a.GetType("Hawa.Grasshopper.LinkedCaseComponent"));c.CreateAttributes();c.Attributes.Pivot=new PointF(610,400);d.AddObject(c,false);
string[] names={"Inlet speed (m/s)","Cell size (m)","Block width (m)"};decimal[] mins={.1m,.25m,.5m},maxs={3m,1m,2m},values={1m,.5m,1m};
for(int i=0;i<3;i++){var s=new GH_NumberSlider();s.CreateAttributes();s.NickName=names[i];s.Slider.Minimum=mins[i];s.Slider.Maximum=maxs[i];s.Slider.DecimalPlaces=2;s.SetSliderValue(values[i]);s.Attributes.Pivot=new PointF(300,360+i*60);d.AddObject(s,false);c.Params.Input[i].AddSource(s);}
var note=new GH_Panel();note.CreateAttributes();note.UserText="HAWA 0.5 / NATIVE LIVE SYNC\n\n1. Run Hawa in Rhino to open the dockable panel.\n2. These three sliders and the panel edit one shared case.\n3. Press Run in the panel. Edits mark the result outdated.\n4. Pause, resume or cancel from the panel.\n5. Save the Rhino file and this definition together.\n\nThe native panel owns the solver. Closing GH leaves the case running.\nThis example uses a fixed block domain. Use example 22 for selected Rhino bodies and editable domains.\nThe default field uses an automatic blue-green scale. Change palettes in View. Values are experimental.";note.Properties.Font=new Font("Helvetica",12);note.Properties.Wrap=true;note.Properties.Multiline=true;note.Properties.DrawIndices=false;note.Properties.DrawPaths=false;var alignment=note.Properties.GetType().GetProperty("Alignment");alignment.SetValue(note.Properties,Enum.Parse(alignment.PropertyType,"Left"));note.Properties.Colour=Color.FromArgb(226,242,237);note.Attributes.Pivot=new PointF(280,30);note.Attributes.Bounds=new RectangleF(280,30,640,260);d.AddObject(note,false);
var status=new GH_Panel();status.CreateAttributes();status.Attributes.Pivot=new PointF(1100,340);status.Attributes.Bounds=new RectangleF(1100,340,440,360);status.Properties.Font=new Font("Helvetica",11);status.Properties.Wrap=true;status.Properties.Multiline=true;status.Properties.DrawIndices=false;status.Properties.DrawPaths=false;alignment.SetValue(status.Properties,Enum.Parse(alignment.PropertyType,"Left"));status.Properties.Colour=Color.FromArgb(226,242,237);status.AddSource(c.Params.Output[2]);d.AddObject(status,false);
// Save an unbound template; it binds to the active Rhino case on first solution.
var io=new GH_DocumentIO();io.Document=d;if(!io.SaveQuiet(root+"/examples/native-prototype/21-native-live-sync.gh"))throw new Exception("Save failed");
Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;
d.NewSolution(false);Console.WriteLine("Created live sync example: "+string.Join(";",c.RuntimeMessages(GH_RuntimeMessageLevel.Error)));
