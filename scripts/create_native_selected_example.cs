// Create the v0.5 native example in an isolated empty Rhino document.
using System.Text.Json.Nodes;
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd";
if(__rhino_doc__.Objects.Count!=0)throw new Exception("Use an empty document");
__rhino_doc__.ModelUnitSystem=Rhino.UnitSystem.Meters;
var hub=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Shared").GetType("Hawa.Shared.CaseHub");
object Call(string method,params object[] args)=>hub.GetMethod(method).Invoke(null,args);
uint serial=__rhino_doc__.RuntimeSerialNumber;dynamic c=Call("Get",serial);
var body=Mesh.CreateFromSphere(new Sphere(Point3d.Origin,1),32,20);body.Transform(Transform.Scale(Plane.WorldXY,.4,.15,.125));
var attributes=new Rhino.DocObjects.ObjectAttributes{Name="Hawa canopy · editable closed mesh"};var id=__rhino_doc__.Objects.AddMesh(body,attributes);body.Dispose();
var native=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Rhino").GetType("Hawa.Native.NativeGeometry");
native.GetMethod("SelectObjects").Invoke(null,new object[]{serial,new[]{id},true});
Call("Edit",serial,new JsonObject{["cell"]=.05,["target"]=200},(long)c.Version,"panel",true);
native.GetMethod("FitDomain").Invoke(null,new object[]{serial});
var ioPath=root+"/examples/native-prototype/22-selected-canopy.3dm";
if(!__rhino_doc__.WriteFile(ioPath,new Rhino.FileIO.FileWriteOptions{WriteUserData=true,SuppressDialogBoxes=true}))throw new Exception("Cannot save Rhino example");
var d=new GH_Document();var assembly=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");
var linked=(GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper.LinkedCaseComponent"));linked.CreateAttributes();linked.Attributes.Pivot=new PointF(720,390);d.AddObject(linked,false);
string[] names={"Inlet speed (m/s)","Cell size (m)"};decimal[] minima={.001m,.00001m},maxima={300m,100m},values={1m,.05m};
var inputs=new List<Guid>();
for(int i=0;i<2;i++){var slider=new GH_NumberSlider();slider.CreateAttributes();slider.NickName=names[i];slider.Slider.Minimum=minima[i];slider.Slider.Maximum=maxima[i];slider.Slider.DecimalPlaces=6;slider.SetSliderValue(values[i]);slider.Attributes.Pivot=new PointF(360,360+i*70);d.AddObject(slider,false);linked.Params.Input[i].AddSource(slider);inputs.Add(slider.InstanceGuid);}
void Note(string text,float x,float y,float width,float height){var panel=new GH_Panel();panel.CreateAttributes();panel.UserText=text;panel.Properties.Font=new Font("Helvetica",12);panel.Properties.Wrap=true;panel.Properties.Multiline=true;panel.Properties.DrawIndices=false;panel.Properties.DrawPaths=false;var alignment=panel.Properties.GetType().GetProperty("Alignment");alignment.SetValue(panel.Properties,Enum.Parse(alignment.PropertyType,"Left"));panel.Properties.Colour=Color.FromArgb(226,242,237);panel.Attributes.Pivot=new PointF(x,y);panel.Attributes.Bounds=new RectangleF(x,y,width,height);d.AddObject(panel,false);}
Note("HAWA 0.5 / SELECTED RHINO GEOMETRY\n\nOpen 22-selected-canopy.3dm first, then run Hawa.\nThis definition binds to that document's native case.\nTwo sliders control speed and cell size. Leave block width disconnected.\nRight-click a slider to enter a precise physical value.",300,30,550,210);
Note("1 / EDIT AND RUN\n\nSetup: select closed bodies, edit domain/fluid and Apply setup.\nSolve: set backend and target; Run, Pause or Cancel.\nView: choose field, slice and palette; Apply display.\nEdit the Rhino mesh to invalidate the old run.\nSave your 3dm and bound GH definition together.",900,30,540,210);
Note("2 / CHECK THE RESULT\n\nExpected: visible domain, coloured field and a capture step/time.\nThe field output is withheld while outdated. Missing/deleted bodies fail explicitly.\nCoarse stationary single-fluid demonstration; viscosity 0.1 m²/s.\nNo RC aerodynamic accuracy, moving body, free surface or force claim.\nCompare equal physical time and fixed colour limits.",300,580,750,210);
var report=new GH_Panel();report.CreateAttributes();report.Attributes.Pivot=new PointF(1100,340);report.Attributes.Bounds=new RectangleF(1100,340,440,360);report.Properties.Font=new Font("Helvetica",11);report.Properties.Wrap=true;report.Properties.Multiline=true;report.Properties.DrawIndices=false;report.Properties.DrawPaths=false;var reportAlignment=report.Properties.GetType().GetProperty("Alignment");reportAlignment.SetValue(report.Properties,Enum.Parse(reportAlignment.PropertyType,"Left"));report.Properties.Colour=Color.FromArgb(226,242,237);report.AddSource(linked.Params.Output[2]);d.AddObject(report,false);
void Group(string name,IEnumerable<Guid> objects){var group=new GH_Group{NickName=name,Colour=Color.FromArgb(40,20,157,172)};group.CreateAttributes();foreach(var item in objects)group.AddObject(item);d.AddObject(group,false);}
Group("01 / Physical controls · SI",inputs);Group("02 / Native case and field",new[]{linked.InstanceGuid});Group("03 / State and capture provenance",new[]{report.InstanceGuid});
// Save before canvas activation so the distributable remains unbound.
var io=new GH_DocumentIO{Document=d};if(!io.SaveQuiet(root+"/examples/native-prototype/22-native-selected-geometry.gh"))throw new Exception("Cannot save GH example");
Grasshopper.Instances.DocumentServer.AddDocument(d);Grasshopper.Instances.ActiveCanvas.Document=d;d.NewSolution(false);
Console.WriteLine("Native example 22 created, body="+id+" case="+c.Id);
