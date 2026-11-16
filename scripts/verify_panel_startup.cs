// Run one phase per Rhino MCP call in an owned empty test document.
// Use run_command for Hawa and Save/SaveAs BETWEEN calls: nested RunScript saves
// do not establish a clean checkpoint inside the MCP script command on Mac.
// empty -> reject -> Save -> preset -> SaveAs -> unchanged -> restore.
// Never run this against a user document. Adjust the evidence root for checkout.
using System.Text.Json.Nodes;
using Eto.Forms;
using Rhino;
using Rhino.Geometry;
var phase = "empty";
var evidence = "/Users/r2d2/Desktop/hawa-issue-31/results/issue31-host";
var doc = __rhino_doc__;
if(doc!=RhinoDoc.ActiveDoc || doc.Objects.Any(o=>!o.IsDeleted) ||
   (!string.IsNullOrEmpty(doc.Path) && !doc.Path.StartsWith(evidence+"/",StringComparison.Ordinal)))
    throw new Exception("Use an active empty owned test document");
var shared=AppDomain.CurrentDomain.GetAssemblies().Single(a=>a.GetName().Name=="Hawa.Shared");
var native=AppDomain.CurrentDomain.GetAssemblies().Single(a=>a.GetName().Name=="Hawa.Rhino");
var hub=shared.GetType("Hawa.Shared.CaseHub");
var panelType=native.GetType("Hawa.Native.HawaPanel");
uint serial=doc.RuntimeSerialNumber;
object Call(string name,params object[] args)=>hub.GetMethod(name).Invoke(null,args);
void Check(bool value,string message){if(!value)throw new Exception(message);}
IEnumerable<Control> Walk(Control control){
    yield return control;
    if(control is Container container)
        foreach(var child in container.Controls)
            foreach(var nested in Walk(child))yield return nested;
}
var checks=new JsonArray();
if(phase=="empty"){
    Check(Call("Find",serial)==null && !doc.Modified,"Hawa command created/modified case");
    for(int i=0;i<2;i++){
        using var panel=(Panel)Activator.CreateInstance(panelType,serial);
        Check(Call("Find",serial)==null && !doc.Modified,"Panel created/modified case");
        Check(Walk(panel).OfType<Label>().Any(x=>x.Text=="NO CASE"),"Missing empty prompt");
        Check(!Walk(panel).OfType<TabControl>().Single().Visible,"Case controls visible while empty");
    }
    checks.Add("command and repeated panel opening stay empty and clean");
}else if(phase=="reject"){
    Check(Call("Find",serial)==null,"Use an empty case registry");
    var selection=native.GetType("Hawa.Native.NativeGeometry").GetMethod("SelectObjects");
    var ids=new List<Guid>();
    try{
        using var mesh=new Mesh();mesh.Vertices.Add(0,0,0);mesh.Vertices.Add(1,0,0);mesh.Vertices.Add(0,1,0);mesh.Faces.AddFace(0,1,2);
        ids.Add(doc.Objects.AddMesh(mesh));
        using var solid=Brep.CreateFromBox(new BoundingBox(Point3d.Origin,new Point3d(1,1,1)));
        using var face=solid.Faces[0].DuplicateFace(false);ids.Add(doc.Objects.AddBrep(face));
        foreach(var id in ids){
            bool dirty=doc.Modified,rejected=false;
            try{selection.Invoke(null,new object[]{serial,new[]{id},true});}
            catch(System.Reflection.TargetInvocationException e)when(e.InnerException is ArgumentException){rejected=true;}
            Check(rejected && Call("Find",serial)==null && doc.Modified==dirty,"Invalid body created/modified a case");
        }
        checks.Add("open mesh and non-solid Brep rejected without a case");
    }finally{foreach(var id in ids)doc.Objects.Delete(id,true);}
}else if(phase=="preset"){
    Check(Call("Find",serial)==null && !doc.Modified,"Save clean fixture before preset phase");
    using var panel=(Panel)Activator.CreateInstance(panelType,serial);
    Walk(panel).OfType<Button>().Single(x=>x.Text=="Block preset").PerformClick();
    dynamic c=Call("Find",serial);
    Check(c!=null && doc.Modified,"First preset omitted native save prompt");
    Check(doc.Strings.GetValue("Hawa","last-created-case")==((Guid)c.Id).ToString(),"Creation record missing");
    Check((string)c.State=="idle" && c.Session==null && c.Job==null,"Creation started work");
    checks.Add("explicit first preset marks native document changed and stays idle");
}else if(phase=="unchanged"){
    Check(Call("Find",serial)!=null && !doc.Modified,"Save case before unchanged phase");
    var before=(string)Call("Save",serial);
    using var panel=(Panel)Activator.CreateInstance(panelType,serial);
    Walk(panel).OfType<Button>().Single(x=>x.Text=="Block preset").PerformClick();
    Check(!doc.Modified && (string)Call("Save",serial)==before,"Unchanged preset dirtied or reset case");
    checks.Add("saved preset and panel reopen preserve settings and clean flag");
}else if(phase=="restore"){
    var saved=JsonNode.Parse((string)Call("Save",serial)).AsObject();saved["speed"]=1.75;
    foreach(int schema in new[]{1,2}){
        Call("Close",serial);var settings=JsonNode.Parse(saved.ToJsonString()).AsObject();settings["schema"]=schema;
        if(schema==1){settings.Remove("setup");settings.Remove("view");}
        using var waiting=(Panel)Activator.CreateInstance(panelType,serial);
        Check(Call("Find",serial)==null,"Waiting panel created a case");
        Call("Restore",serial,settings.ToJsonString());dynamic c=Call("Find",serial);
        var before=(string)Call("Save",serial);var owner=Guid.NewGuid();var lease=Call("Bind",(object)c,owner,new[]{"speed"});
        using var reopened=(Panel)Activator.CreateInstance(panelType,serial);
        Check((string)Call("Save",serial)==before && (Guid)c.BindingOwner==owner,"Reopen altered settings/binding");
        Check((double)c.Speed==1.75 && (string)c.State=="idle" && c.Session==null,"Restore lost settings or auto-ran");
        Call("Unbind",(object)c,owner,lease);
        checks.Add("schema "+schema+" idle restore and binding preserved");
    }
}else throw new Exception("Unknown phase");
var report=new JsonObject{["phase"]=phase,["state"]="passed",["checks"]=checks,["rhino"]=RhinoApp.Version.ToString(),["document"]=(long)serial,["path"]=doc.Path,["modified"]=doc.Modified,["native_sha256"]=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.IO.File.ReadAllBytes(native.Location))),["shared_sha256"]=Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(System.IO.File.ReadAllBytes(shared.Location)))};
System.IO.File.WriteAllText(evidence+"/startup-"+phase+".json",report.ToJsonString(new System.Text.Json.JsonSerializerOptions{WriteIndented=true}));
Console.WriteLine(report.ToJsonString());
