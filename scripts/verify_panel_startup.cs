// Run one phase per Rhino MCP call in an owned empty test document.
// Use run_command for Hawa and Save/SaveAs BETWEEN calls: nested RunScript saves
// do not establish a clean checkpoint inside the MCP script command on Mac.
// empty -> reject -> Save -> preset -> SaveAs -> unchanged -> restore.
// On the preview-controls build: Save, then preview (writes an owned hidden copy).
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
}else if(phase=="preview"){
    dynamic c=Call("Find",serial);
    Check(c!=null && !doc.Modified,"Save owned case before preview phase");
    var id=(Guid)c.Id;var revision=(long)c.Revision;var session=(string)c.Session;
    var setup=((JsonObject)c.Setup).ToJsonString();
    using var panel=(Panel)Activator.CreateInstance(panelType,serial);
    var hide=Walk(panel).OfType<Button>().Single(x=>x.Text=="Hide preview");
    var show=Walk(panel).OfType<Button>().Single(x=>x.Text=="Show preview");
    Walk(panel).OfType<Button>().Single(x=>x.Text=="Zoom domain").PerformClick();
    hide.PerformClick();
    Check(doc.Modified && !hide.Enabled && show.Enabled,"Hide state/save prompt missing");
    Check(new[]{"domain","body","field","annotations"}.All(key=>!((JsonObject)c.View)[key].GetValue<bool>()),"Some overlays still visible");
    string path=evidence+"/hidden-preview.3dm";
    Check(doc.WriteFile(path,new Rhino.FileIO.FileWriteOptions{WriteUserData=true,SuppressDialogBoxes=true}),"Hidden copy save failed");
    using(var reopened=RhinoDoc.OpenHeadless(path)){
        dynamic restored=Call("Find",reopened.RuntimeSerialNumber);
        Check(restored!=null && (Guid)restored.Id==id && (string)restored.State=="idle","Hidden case not restored");
        Check(new[]{"domain","body","field","annotations"}.All(key=>!((JsonObject)restored.View)[key].GetValue<bool>()),"Reopen reset hidden flags");
        Call("Close",reopened.RuntimeSerialNumber);
    }
    doc.Views.Redraw();
    var capture=new Rhino.Display.ViewCapture{Width=1200,Height=800,ScaleScreenItems=true,DrawAxes=false,DrawGrid=false,DrawGridAxes=false};
    using(var bitmap=capture.CaptureToBitmap(doc.Views.ActiveView))bitmap.Save(evidence+"/preview-hidden.png",System.Drawing.Imaging.ImageFormat.Png);
    show.PerformClick();
    Check(!show.Enabled && hide.Enabled && new[]{"domain","body","field","annotations"}.All(key=>((JsonObject)c.View)[key].GetValue<bool>()),"Show did not restore overlays");
    Check((Guid)c.Id==id && (long)c.Revision==revision && (string)c.Session==session && ((JsonObject)c.Setup).ToJsonString()==setup,"Visibility changed case/physics");
    doc.Views.Redraw();
    using(var bitmap=capture.CaptureToBitmap(doc.Views.ActiveView))bitmap.Save(evidence+"/preview-shown.png",System.Drawing.Imaging.ImageFormat.Png);
    checks.Add("quick hide/show preserves case/physics and hidden flags survive 3dm reopen");
}else if(phase=="annotations"){
    dynamic c=Call("Find",serial);
    Check(c!=null && c.Result!=null && ((JsonObject)c.View)["field"].GetValue<bool>(),"Run a small owned case to a field result first");
    var revision=(long)c.Revision;var session=(string)c.Session;
    using var panel=(Panel)Activator.CreateInstance(panelType,serial);
    var toggle=Walk(panel).OfType<CheckBox>().Single(x=>x.Text=="Annotations and legend");
    var apply=Walk(panel).OfType<Button>().Single(x=>x.Text=="Apply display");
    var capture=new Rhino.Display.ViewCapture{Width=1200,Height=800,ScaleScreenItems=true,DrawAxes=false,DrawGrid=false,DrawGridAxes=false};
    Walk(panel).OfType<Button>().Single(x=>x.Text=="Zoom domain").PerformClick();
    foreach(bool visible in new[]{false,true}){
        toggle.Checked=visible;apply.PerformClick();
        Check(((JsonObject)c.View)["annotations"].GetValue<bool>()==visible && ((JsonObject)c.View)["field"].GetValue<bool>() && c.Result!=null,"Annotation switch lost the field");
        Check((long)c.Revision==revision && (string)c.Session==session,"Annotation switch restarted physics");
        doc.Views.Redraw();
        using(var bitmap=capture.CaptureToBitmap(doc.Views.ActiveView))bitmap.Save(evidence+"/annotations-"+(visible?"shown":"hidden")+".png",System.Drawing.Imaging.ImageFormat.Png);
    }
    checks.Add("annotation switch preserves field and solver; paired captures require visual review");
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
