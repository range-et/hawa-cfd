// Execute in Rhino's C# ScriptEditor or via the Rhino MCP C# tool.
using System.Reflection;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;

var assembly = Assembly.LoadFile("/Users/r2d2/Desktop/hawa-cfd/dist/Hawa/Hawa.Grasshopper.gha");
var bridge = assembly.GetType("Hawa.Grasshopper.EmbeddedRuntime")!;
JsonObject Call(JsonObject request) { try { return (JsonObject)bridge.GetMethod("Call")!.Invoke(null, new object[] { request })!; } catch (Exception e) { throw new Exception(request.ToJsonString() + " :: " + e.GetBaseException().ToString()); } }
GH_Component Component(string name) => (GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper." + name)!)!;
var document = new GH_Document();
document.Enabled = true;
var example = Component("ExampleComponent");
var solve = Component("SolveComponent");
var slice = Component("SliceComponent");
foreach (var component in new[] { example, solve, slice }) { component.CreateAttributes(); document.AddObject(component, false); component.ExpireSolution(false); }
((Param_String)solve.Params.Input[1]).PersistentData.Clear();
((Param_String)solve.Params.Input[1]).SetPersistentData("mps");
((Param_Integer)solve.Params.Input[2]).PersistentData.Clear();
((Param_Integer)solve.Params.Input[2]).SetPersistentData(25);
solve.Params.Input[0].AddSource(example.Params.Output[0]);
slice.Params.Input[0].AddSource(solve.Params.Output[0]);
document.NewSolution(false);
((Param_Boolean)solve.Params.Input[3]).PersistentData.Clear();
((Param_Boolean)solve.Params.Input[3]).SetPersistentData(true);
solve.ExpireSolution(false);
document.NewSolution(false);
var goo = solve.Params.Output[0].VolatileData.AllData(true).FirstOrDefault();
if (goo == null) { Console.WriteLine($"No session. global={GH_Document.EnableSolutions}, enabled={document.Enabled}, phase={solve.Phase}, example={example.Params.Output[0].VolatileDataCount}, state={document.SolutionState}"); Console.WriteLine(string.Join(";", solve.RuntimeMessages(GH_RuntimeMessageLevel.Error))); return; }
var value = (string)goo.GetType().GetProperty("Value")!.GetValue(goo)!;
var solution = JsonNode.Parse(value)!;
var session = solution["session"]!.GetValue<string>();
try
{
    var timer = System.Diagnostics.Stopwatch.StartNew();
    JsonObject status;
    do
    {
        System.Threading.Thread.Sleep(20);
        status = Call(new JsonObject { ["op"] = "status", ["session"] = session });
    } while (status["state"]!.GetValue<string>() == "running" && timer.ElapsedMilliseconds < 10000);
    if (status["steps"]!.GetValue<int>() != 25) throw new Exception("Solver did not reach 25 steps: " + status);
    solve.ExpireSolution(false);
    document.NewSolution(false);
    var mesh = (GH_Mesh)slice.Params.Output[0].VolatileData.AllData(true).First();
    if (!mesh.Value.IsValid || mesh.Value.Vertices.Count != 256) throw new Exception("Invalid slice mesh");
    var output = new JsonObject { ["passed"] = true, ["components"] = assembly.GetTypes().Count(t => !t.IsAbstract && typeof(GH_Component).IsAssignableFrom(t)), ["steps"] = 25, ["slice_vertices"] = mesh.Value.Vertices.Count, ["runtime"] = JsonNode.Parse(Call(new JsonObject { ["op"] = "info" }).ToJsonString()) };
    System.IO.Directory.CreateDirectory("/Users/r2d2/Desktop/hawa-cfd/results/plugin");
    System.IO.File.WriteAllText("/Users/r2d2/Desktop/hawa-cfd/results/plugin/grasshopper.json", output.ToJsonString());
    Console.WriteLine(output.ToJsonString());
}
finally
{
    try { Call(new JsonObject { ["op"] = "close", ["session"] = session }); } catch(Exception e) { Console.WriteLine(e.Message); }
    document.Enabled = false;
    document.Dispose();
}
