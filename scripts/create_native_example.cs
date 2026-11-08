using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using System.Drawing;
var root="/Users/r2d2/Desktop/hawa-cfd";
var d=new GH_Document();
var a=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
var c=(GH_Component)Activator.CreateInstance(a.GetType("Hawa.Grasshopper.LinkedCaseComponent"));c.CreateAttributes();c.Attributes.Pivot=new PointF(610,300);d.AddObject(c,false);
string[] names={"Inlet speed (m/s)","Cell size (m)","Block width (m)"};decimal[] mins={.1m,.25m,.5m},maxs={3m,1m,2m},values={1m,.5m,1m};
for(int i=0;i<3;i++){var s=new GH_NumberSlider();s.CreateAttributes();s.NickName=names[i];s.Slider.Minimum=mins[i];s.Slider.Maximum=maxs[i];s.Slider.DecimalPlaces=2;s.SetSliderValue(values[i]);s.Attributes.Pivot=new PointF(300,260+i*60);d.AddObject(s,false);c.Params.Input[i].AddSource(s);}
var note=new GH_Panel();note.CreateAttributes();note.UserText="HAWA 0.5 / NATIVE LIVE SYNC\n\n1. Run Hawa in Rhino to open the dockable panel.\n2. These three sliders and the panel edit one shared case.\n3. Press Run in the panel. Edits mark the result outdated.\n4. Pause, resume or cancel from the panel.\n5. Save the Rhino file and this definition together.\n\nThe native panel owns the solver. Closing GH leaves the case running.\nThis example uses a fixed block domain. It is a prototype, not a general case editor.\nThe field uses an automatic blue-green scale. Values are experimental.";note.Attributes.Pivot=new PointF(280,30);note.Attributes.Bounds=new RectangleF(280,30,640,190);d.AddObject(note,false);
var status=new GH_Panel();status.CreateAttributes();status.Attributes.Pivot=new PointF(820,270);status.Attributes.Bounds=new RectangleF(820,270,390,350);status.AddSource(c.Params.Output[2]);d.AddObject(status,false);
Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;
// Save an unbound template; it binds to the active Rhino case on first solution.
var io=new GH_DocumentIO();io.Document=d;if(!io.SaveQuiet(root+"/examples/native-prototype/21-native-live-sync.gh"))throw new Exception("Save failed");
d.NewSolution(false);Console.WriteLine("Created live sync example: "+string.Join(";",c.RuntimeMessages(GH_RuntimeMessageLevel.Error)));
