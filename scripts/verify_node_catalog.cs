// Read the installed catalogue and every supported distributable definition.
using Grasshopper.Kernel;
using System.Text.Json.Nodes;
var root="/Users/r2d2/Desktop/hawa-cfd";
var legacy=new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077116");
var proxies=Grasshopper.Instances.ComponentServer.ObjectProxies.Where(p=>p.Desc.Category=="Hawa").ToArray();
var rows=new JsonArray();int visible=0,hidden=0;
foreach(var proxy in proxies){var c=(GH_Component)proxy.CreateInstance();bool archive=c.Exposure==GH_Exposure.hidden;if(archive)hidden++;else visible++;if(c.Icon_24x24==null)throw new Exception("Missing icon: "+c.Name);if(c.ComponentGuid==legacy&&!archive)throw new Exception("Hull remains public");rows.Add(new JsonObject{["name"]=c.Name,["id"]=c.ComponentGuid.ToString(),["category"]=c.SubCategory,["archive_only"]=archive});}
if(visible!=46||hidden!=1)throw new Exception("Unexpected public/legacy inventory: "+visible+" / "+hidden);
var files=System.IO.Directory.GetFiles(root+"/examples/grasshopper","*.gh").Where(p=>!System.IO.Path.GetFileName(p).StartsWith("09-")).Concat(System.IO.Directory.GetFiles(root+"/examples/native-prototype","*.gh")).ToArray();
if(files.Length!=21)throw new Exception("Missing supported definitions");
var examples=new JsonArray();foreach(var file in files){var io=new GH_DocumentIO();if(!io.Open(file))throw new Exception("Cannot open "+file);if(io.Document.Objects.OfType<GH_Component>().Any(c=>c.ComponentGuid==legacy))throw new Exception("Supported definition still depends on Hull: "+file);examples.Add(System.IO.Path.GetFileName(file));io.Document.Dispose();}
System.IO.File.WriteAllText(root+"/results/v05/release/node-catalog.json",new JsonObject{["state"]="completed",["public_components"]=visible,["archive_readers"]=hidden,["components"]=rows,["supported_definitions_without_hull"]=examples}.ToJsonString());Console.WriteLine("46 public components; one hidden archive reader; 21 supported files have no Hull dependency");
