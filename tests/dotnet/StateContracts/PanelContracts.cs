using System.Text.Json.Nodes;
using Eto.Forms;
using Hawa.Native;
using Hawa.Shared;
using Rhino;

static class PanelContracts {
    static IEnumerable<Control> Walk(Control c) => new[] { c }.Concat(c.Children.SelectMany(Walk));
    public static void Run(Action<string, Action> test, Action<bool, string> assert) {
        test("Hawa command opens panel without creating or replacing cases", () => {
            var doc=new RhinoDoc(3100);var command=new HawaCommand();
            assert(command.EnglishName=="Hawa","Command renamed");
            foreach(var scenario in new[]{0,1,2}) {
                Rhino.UI.Panels.HawaBar=scenario==0?Guid.NewGuid():Guid.Empty;
                Rhino.UI.Panels.LayersBar=scenario==1?Guid.NewGuid():Guid.Empty;
                Rhino.UI.Panels.Panel=scenario==2?null:new Panel { ParentWindow=new FloatingWindow { Width=200 } };
                assert(command.Execute(doc)==Rhino.Commands.Result.Success,"Open failed");
                assert(CaseHub.Find(3100)==null && !doc.Modified,"Command created default case");
                assert(Rhino.UI.Panels.OpenedBar==(scenario==0?Rhino.UI.Panels.HawaBar:Rhino.UI.Panels.LayersBar),"Wrong dock target");
                if(Rhino.UI.Panels.Panel!=null)assert(Rhino.UI.Panels.Panel.ParentWindow!.Size!.Width==380,"Floating panel not resized");
            }
            var c=CaseHub.Get(3100);CaseHub.Edit(3100,new(){["speed"]=1.7},c.Version);
            var saved=c.Settings().ToJsonString();
            Rhino.UI.Panels.Panel=new Panel { ParentWindow=new Window { Width=500 } };
            command.Execute(doc);
            assert(ReferenceEquals(c,CaseHub.Find(3100)) && c.Settings().ToJsonString()==saved,"Command changed existing case");
            CaseHub.Close(3100);
        });
        test("panel startup and reopen leave a fresh document without a case or preview", () => {
            var doc = new RhinoDoc(3101);
            for (int i=0;i<2;i++) {
                using var panel = new HawaPanel(doc.RuntimeSerialNumber);
                var controls=Walk(panel).ToArray();
                assert(CaseHub.Find(3101)==null && !doc.Modified,"Opening panel created/modified a case");
                assert(controls.OfType<Label>().Any(x=>x.Text=="NO CASE"),"Empty state not shown");
                assert(!controls.OfType<TabControl>().Single().Visible,"Case controls shown without a case");
                assert(!controls.OfType<Button>().Single(x=>x.Text=="Run / Resume").Enabled,"Empty case can run");
                controls.OfType<Button>().Single(x=>x.Text=="Select bodies").PerformClick(); // cancelled picker
                assert(CaseHub.Find(3101)==null,"Cancelled picker created a case");
                using var preview=new NativePreview();var draw=new Rhino.Display.DisplayPipeline();
                preview.RaisePostDraw(new(doc,draw));var bounds=new Rhino.Display.CalculateBoundingBoxEventArgs(doc);preview.RaiseBoundingBox(bounds);
                assert(draw.Calls.Count==0 && bounds.Included.Count==0,"Empty panel adds preview/bounds");
                // Programmatic control events while empty must not synthesize a case.
                foreach(var n in controls.OfType<NumericStepper>())n.Value+=.1;
                foreach(var d in controls.OfType<DropDown>())d.SelectedIndex=0;
                assert(CaseHub.Find(3101)==null,"Empty controls created a case");
            }
        });
        test("explicit block preset, edits, undo and panel reopen preserve case identity", () => {
            var doc = new RhinoDoc(3102);
            using(var panel = new HawaPanel(3102)) {
                var controls=Walk(panel).ToArray();
                Button Button(string name)=>controls.OfType<Button>().Single(x=>x.Text==name);
                Button("Block preset").PerformClick();var c=CaseHub.Find(3102)!;
                assert(c!=null && c.State=="idle" && c.Session==null && c.Job==null,"Preset did not create idle case");
                assert(controls.OfType<TabControl>().Single().Visible && Button("Run / Resume").Enabled,"Case controls not enabled");
                var id=c!.Id;var owner=Guid.NewGuid();var lease=CaseHub.Bind(c,owner,new[]{"speed"});
                assert(!controls.OfType<NumericStepper>().Single(x=>x.ToolTip.StartsWith("Inlet speed")).Enabled,"Driven input enabled");
                CaseHub.Unbind(c,owner,lease);
                var speed=controls.OfType<NumericStepper>().Single(x=>x.ToolTip.StartsWith("Inlet speed"));speed.Value=1.5;
                assert(c.Speed==1.5,"Panel edit failed");doc.Undo();assert(c.Speed==1,"Undo failed");
                controls.OfType<NumericStepper>().Single(x=>x.MaxValue==100000).Value=25;
                assert(c.Target==25,"Target edit failed");
                var device=controls.OfType<DropDown>().Single(x=>x.DataStore.Contains("cuda:0"));device.SelectedValue="auto";device.SelectedIndex=-1;
                assert(c.Device=="auto","Device edit failed");
                var field=controls.OfType<DropDown>().Single(x=>x.DataStore.Contains("pressure"));field.SelectedValue="pressure";field.SelectedIndex=-1;
                assert(c.Field=="pressure","Field edit failed");field.SelectedValue="speed";
                Button("Apply setup").PerformClick();Button("Apply display").PerformClick();Button("Zoom domain").PerformClick();
                assert(doc.Views.ActiveView.ActiveViewport.Zoomed!=null,"Zoom failed");
                Button("Fit domain").PerformClick();assert(controls.OfType<Label>().Any(x=>x.Text.Contains("Select Rhino geometry first")),"Error not shown");
                Button("Block preset").PerformClick();assert(c.Id==id,"Preset replaced identity");
                Button("Run / Resume").PerformClick();assert(c.State=="preparing","Run did not submit");
                Button("Pause").PerformClick();Button("Cancel").PerformClick();Button("Reset").PerformClick();
                assert(c.State=="idle" && c.Job==null,"Controls retained work");
                Button("Run / Resume").PerformClick();CaseHub.Tick();CaseHub.Tick();
                assert(c.Session!=null && Button("Refresh field").Enabled,"Ready session missing");
                Button("Refresh field").PerformClick();Button("Cancel").PerformClick();
                assert(c.Session==null && c.State=="cancelled","Cancel kept active session");
                Button("Reset").PerformClick();
            }
            var saved=CaseHub.Find(3102)!.Settings().ToJsonString();
            using(var reopened=new HawaPanel(3102))assert(CaseHub.Find(3102)!.Settings().ToJsonString()==saved,"Panel reopen overwrote case");
            CaseHub.Close(3102);
        });
        test("saved schema 1 and selected schema 2 restore before or after panel opens", () => {
            foreach(var schema in new[]{1,2})foreach(var restoreFirst in new[]{false,true}) {
                var doc=new RhinoDoc((uint)(3110+schema*2+(restoreFirst?1:0)));
                var saved=new CaseState().Settings();saved["schema"]=schema;saved["speed"]=1.75;
                if(schema==1){saved.Remove("setup");saved.Remove("view");}
                else {saved["setup"]!["mode"]="selected";saved["setup"]!["origin"]=new JsonArray(2d,3d,4d);saved["setup"]!["objects"]=new JsonArray(Guid.NewGuid().ToString());}
                var serial=doc.RuntimeSerialNumber;
                if(restoreFirst)CaseHub.Restore(serial,saved.ToJsonString());
                using var panel=new HawaPanel(serial);
                if(!restoreFirst)CaseHub.Restore(serial,saved.ToJsonString());
                var c=CaseHub.Find(serial)!;var expected=c.Settings().ToJsonString();
                assert(c.Id==Guid.Parse(saved["id"]!.GetValue<string>()) && c.Speed==1.75 && c.SelectedGeometry==(schema==2),"Restoration lost saved values");
                assert(c.State=="idle" && c.Job==null && c.Session==null,"Restoration started work");
                var owner=Guid.NewGuid();var lease=CaseHub.Bind(c,owner,new[]{"cell"});
                using(var second=new HawaPanel(serial))assert(c.Settings().ToJsonString()==expected && c.BindingOwner==owner && c.BindingLease==lease,"Opening panel changed saved settings/binding");
                var other=new RhinoDoc(serial+100);CaseHub.Get(other.RuntimeSerialNumber); // unrelated notification
                CaseHub.Close(other.RuntimeSerialNumber);CaseHub.Close(serial);
                assert(Walk(panel).OfType<Label>().Any(x=>x.Text=="CASE CLOSED"),"Close notification ignored");
            }
            using var closed=new HawaPanel(99999); // disposed document: no case creation
            assert(CaseHub.Find(99999)==null,"Closed document recreated");
        });
    }
}
