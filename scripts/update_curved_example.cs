// Migrate example 14 without replacing existing object IDs or view wiring.
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-cfd";var path=root+"/examples/grasshopper/14-curved-sphere-pressure.gh";
var io=new GH_DocumentIO();if(!io.Open(path))throw new Exception("Cannot open example 14");var d=io.Document;
var geo=d.Objects.OfType<GH_Component>().Single(c=>c.Name=="Hawa Geometry");
if(geo.Params.Input.Count!=4)throw new Exception("Updated Geometry component not loaded");
var source=d.Objects.OfType<Param_Brep>().SingleOrDefault(p=>p.NickName=="Exact sphere / replace with closed solid");
if(source==null){source=new Param_Brep();source.CreateAttributes();source.NickName="Exact sphere / replace with closed solid";source.Attributes.Pivot=new PointF(geo.Attributes.Pivot.X-300,geo.Attributes.Pivot.Y+180);using var b=new Sphere(new Point3d(6,4,4),1.4).ToBrep();source.SetPersistentData(new GH_Brep(b.DuplicateBrep()));source.Hidden=true;d.AddObject(source,false);}
geo.Params.Input[1].RemoveAllSources();geo.Params.Input[3].RemoveAllSources();geo.Params.Input[3].AddSource(source);
foreach(var p in d.Objects.OfType<Param_Mesh>())p.NickName="Display and surface-sampling mesh";
var clipped=d.Objects.OfType<GH_Component>().FirstOrDefault(c=>c.Name=="Hawa Slice");
if(clipped==null){var asm=AppDomain.CurrentDomain.GetAssemblies().First(a=>a.GetName().Name=="Hawa.Grasshopper");clipped=(GH_Component)Activator.CreateInstance(asm.GetType("Hawa.Grasshopper.SliceComponent"));clipped.CreateAttributes();clipped.Attributes.Pivot=new PointF(2400,1000);clipped.NickName="Pressure / wall-clipped";d.AddObject(clipped,false);clipped.Params.Input[0].AddSource(d.Objects.OfType<GH_Component>().Single(c=>c.Name=="Hawa Solve").Params.Output[0]);((Param_String)clipped.Params.Input[3]).SetPersistentData("pressure");}
((Param_String)clipped.Params.Input[3]).PersistentData.Clear();((Param_String)clipped.Params.Input[3]).SetPersistentData("pressure");
foreach(var oldPlane in d.Objects.OfType<GH_Component>().Where(c=>c.Name=="Hawa Plane Field"))oldPlane.Hidden=true;
foreach(var t in d.Objects.OfType<Grasshopper.Kernel.Special.GH_BooleanToggle>())t.Value=false;
if(!System.IO.File.Exists(root+"/results/v05/boundaries/14-before-brep-input.gh"))System.IO.File.Copy(path,root+"/results/v05/boundaries/14-before-brep-input.gh");
if(!new GH_DocumentIO{Document=d}.SaveQuiet(path))throw new Exception("Save failed");d.Dispose();
Rhino.RhinoApp.WriteLine("Example 14 now uses the optional solid-Brep input; original view mesh/wires retained");
