using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Types;
using System.Text.Json.Nodes;
var file="/Users/r2d2/Desktop/hawa-cfd/examples/grasshopper/09-parametric-hull-galapagos.gh";
var io=new GH_DocumentIO();if(!io.Open(file))throw new Exception("Cannot reopen hull definition");var d=io.Document;d.Enabled=true;
var hull=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Parametric Hull");var ev=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Evaluate");var toggle=d.Objects.OfType<GH_BooleanToggle>().First();
var gal=d.Objects.First(o=>o.GetType().Name=="GalapagosObject");var gt=gal.GetType();var inputs=(List<Guid>)gt.GetProperty("Inputs").GetValue(gal);if(inputs.Count!=3 || (Guid)gt.GetProperty("Output").GetValue(gal)!=ev.Params.Output[0].InstanceGuid)throw new Exception("Broken Galapagos links");
var genes=new[]{"Bow fullness","Stern fullness","Beam / draft"}.Select(n=>d.Objects.OfType<GH_NumberSlider>().First(s=>s.NickName==n)).ToArray();if(genes.Any(g=>!inputs.Contains(g.InstanceGuid)))throw new Exception("Wrong genome");
d.NewSolution(false);if(toggle.Value||ev.Params.Output[0].VolatileData.AllData(true).Any(v=>v!=null))throw new Exception("Saved example must open disabled");
var variants=new[]{new decimal[]{.4m,.4m,1},new decimal[]{1.6m,1.6m,3},new decimal[]{.896m,1.461m,2.586m}};
foreach(var v in variants){for(int i=0;i<3;i++){genes[i].SetSliderValue(v[i]);genes[i].ExpireSolution(false);}d.NewSolution(false);var mesh=((GH_Mesh)hull.Params.Output[0].VolatileData.AllData(true).First()).Value;double volume=((GH_Number)hull.Params.Output[2].VolatileData.AllData(true).First()).Value;if(!mesh.IsValid||!mesh.IsClosed||Math.Abs(volume-6)>1e-5)throw new Exception("Hull closure or volume constraint failed");}
toggle.Value=true;toggle.ExpireSolution(false);d.NewSolution(false);
var fitness=((GH_Number)ev.Params.Output[0].VolatileData.AllData(true).First()).Value;var report=ev.Params.Output[3].VolatileData.AllData(true).First().ToString();
if(!double.IsFinite(fitness)||fitness<=0||!report.Contains("mps"))throw new Exception("MPS evaluation failed");
var sl=d.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Slice");var field=((GH_Mesh)sl.Params.Output[0].VolatileData.AllData(true).First()).Value;if(!field.IsValid||field.Faces.Count==0)throw new Exception("Empty result mesh");
var errors=d.Objects.OfType<GH_Component>().SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error)).ToArray();if(errors.Length>0)throw new Exception(string.Join(";",errors));
// A saved enabled value must not start a computation when reopened.
var temp="/Users/r2d2/Desktop/hawa-cfd/results/hull/enabled-roundtrip.gh";new GH_DocumentIO{Document=d}.SaveQuiet(temp);var opened=new GH_DocumentIO();opened.Open(temp);opened.Document.Enabled=true;opened.Document.NewSolution(false);var reopened=opened.Document.Objects.OfType<GH_Component>().First(c=>c.Name=="Hawa Evaluate");if(reopened.Params.Output[0].VolatileData.AllData(true).Any(v=>v!=null))throw new Exception("Enabled reopen computed unexpectedly");opened.Document.Dispose();
toggle.Value=false;toggle.ExpireSolution(false);d.NewSolution(false);if(ev.Params.Output[0].VolatileData.AllData(true).Any(v=>v!=null)||sl.Params.Output[0].VolatileData.AllData(true).Any(v=>v!=null))throw new Exception("Disabled data is stale");
var summary=new JsonObject{["passed"]=true,["galapagos_genes"]=3,["closed_fixed_volume_variants"]=3,["mesh_volume"]=6,["fitness"]=fitness,["backend"]="mps",["iterations"]=200,["field_faces"]=field.Faces.Count,["enabled_reopen_idle"]=true,["disabled_outputs_empty"]=true};System.IO.File.WriteAllText("/Users/r2d2/Desktop/hawa-cfd/results/hull/verification.json",summary.ToJsonString());Console.WriteLine(summary.ToJsonString());d.Dispose();
