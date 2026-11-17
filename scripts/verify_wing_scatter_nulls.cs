// Rhino MCP only, transient stock-GH test. No Rhino geometry or files are changed.
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;
var doc=new GH_Document();doc.Enabled=true;var report=new JsonArray();
GH_Component Stock(string id){var c=(GH_Component)Grasshopper.Instances.ComponentServer.EmitObjectProxy(new Guid(id)).CreateInstance();c.CreateAttributes();doc.AddObject(c,false);return c;}
void Wire(IGH_Param p,GH_Component c,int i)=>c.Params.Input[i].AddSource(p);
var x=new Param_Number();x.CreateAttributes();doc.AddObject(x,false);
var y=new Param_Number();y.CreateAttributes();doc.AddObject(y,false);
var nx=Stock("c74efd0e-7fe3-4c2d-8c9d-295c5672fb13");Wire(x,nx,0);
var ny=Stock("c74efd0e-7fe3-4c2d-8c9d-295c5672fb13");Wire(y,ny,0);
var mask=Stock("548177c2-d1db-4172-b667-bec979e2d38b");Wire(nx.Params.Output[0],mask,0);Wire(ny.Params.Output[0],mask,1);
var cx=Stock("008e9a6f-478a-4813-8c8a-546273bc3a6b");Wire(x,cx,0);Wire(mask.Params.Output[0],cx,1);
var cy=Stock("008e9a6f-478a-4813-8c8a-546273bc3a6b");Wire(y,cy,0);Wire(mask.Params.Output[0],cy,1);
GH_Component Scale(GH_Component source){
 var scale=Stock("9df5e896-552d-4c8c-b9ca-4fc147ffa022");while(scale.Params.Input.Count>0)scale.Params.UnregisterInputParameter(scale.Params.Input.Last(),true);scale.Params.OnParametersChanged();scale.GetType().GetProperty("Expression").SetValue(scale,"2");
 var c=Stock("2f643ab6-b9a4-4923-b3da-f9d52b0cba14");Wire(source.Params.Output[0],c,0);Wire(scale.Params.Output[0],c,1);
 var add=Stock("58669268-a825-4688-8072-7d3508fcf91c");Wire(c.Params.Output[0],add,0);((Param_Number)add.Params.Input[1]).SetPersistentData(0d);return add;
}
var sx=Scale(cx);var sy=Scale(cy);
void Set(Param_Number p,double?[] values){p.PersistentData.Clear();foreach(var v in values)p.PersistentData.Append(v.HasValue?new GH_Number(v.Value):null,new GH_Path(0));p.ExpireSolution(false);}
double[] Numbers(GH_Component c)=>c.Params.Output[0].VolatileData.AllData(true).Select(v=>{double n=0;if(v==null||!v.CastTo(out n))throw new Exception("Unexpected null/non-number after paired culling");return n;}).ToArray();
void Run(string name,double?[] xv,double?[] yv,double[] expectedX,double[] expectedY){Set(x,xv);Set(y,yv);doc.NewSolution(false);foreach(var c in doc.Objects.OfType<GH_Component>())if(c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Count!=0)throw new Exception(name+": "+c.Name+": "+string.Join(";",c.RuntimeMessages(GH_RuntimeMessageLevel.Error)));var actualX=Numbers(sx);var actualY=Numbers(sy);if(!actualX.SequenceEqual(expectedX)||!actualY.SequenceEqual(expectedY))throw new Exception(name+": paired cull mismatched X/Y");report.Add(new JsonObject{["case"]=name,["pairs"]=actualX.Length,["x"]=new JsonArray(actualX.Select(n=>(JsonNode)JsonValue.Create(n)).ToArray()),["y"]=new JsonArray(actualY.Select(n=>(JsonNode)JsonValue.Create(n)).ToArray())});}
try{
 Run("mixed missing coordinates",new double?[]{1,2,null,4,5},new double?[]{10,null,30,40,50},new double[]{2,8,10},new double[]{20,80,100});
 Run("pending coefficients",new double?[]{-3,3},new double?[]{null,null},Array.Empty<double>(),Array.Empty<double>());
 Run("both pending",new double?[]{null,null},new double?[]{null,null},Array.Empty<double>(),Array.Empty<double>());
 Run("valid paired values",new double?[]{-3,3},new double?[]{.1,.2},new double[]{-6,6},new double[]{.2,.4});
 Console.WriteLine(new JsonObject{["state"]="passed",["tests"]=report}.ToJsonString());
}finally{doc.Dispose();}
