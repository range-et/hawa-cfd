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
                assert(controls.OfType<TabControl>().Single().Pages.Where(p=>p.Text!="Save / Import").All(p=>!p.Enabled) && controls.OfType<Button>().Single(b=>b.Text=="Import data").Enabled,"Empty document must offer import without enabling case controls");
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
                assert(doc.Modified,"First explicit preset must trigger the save prompt");
                doc.Modified=false;Button("Block preset").PerformClick();
                assert(!doc.Modified,"Unchanged existing preset should remain clean");
                assert(c!=null && c.State=="idle" && c.Session==null && c.Job==null,"Preset did not create idle case");
                assert(controls.OfType<TabControl>().Single().Visible && Button("Run / Resume").Enabled,"Case controls not enabled");
                var id=c!.Id;var owner=Guid.NewGuid();var lease=CaseHub.Bind(c,owner,new[]{"speed"});
                assert(!controls.OfType<NumericStepper>().Single(x=>x.ToolTip.StartsWith("Inlet speed")).Enabled,"Driven input enabled");
                CaseHub.Unbind(c,owner,lease);
                var speed=controls.OfType<NumericStepper>().Single(x=>x.ToolTip.StartsWith("Inlet speed"));speed.Value=1.5;
                assert(c.Speed==1.5,"Panel edit failed");doc.Undo();assert(c.Speed==1,"Undo failed");
                controls.OfType<NumericStepper>().Single(x=>x.MaxValue==100000).Value=25;
                assert(c.Target==25,"Target edit failed");
                var device=controls.OfType<DropDown>().Single(x=>x.DataStore.Contains("cuda:0") && !x.ToolTip.StartsWith("Backend for importing"));device.SelectedValue="auto";device.SelectedIndex=-1;
                assert(c.Device=="auto","Device edit failed");
                var field=controls.OfType<DropDown>().Single(x=>x.DataStore.Contains("pressure"));field.SelectedValue="pressure";field.SelectedIndex=-1;
                assert(c.Field=="pressure","Field edit failed");field.SelectedValue="speed";
                Button("Zoom domain").PerformClick();
                assert(doc.Views.ActiveView.ActiveViewport.Zoomed!=null,"Zoom failed");
                Button("Fit domain").PerformClick();assert(controls.OfType<Label>().Any(x=>x.Text.Contains("Use Select bodies") && x.Text.Contains("Adding geometry to Rhino does not assign it")),"Selection guidance not shown");
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
        test("panel displays quality trigger reasons and tolerates legacy missing or malformed reasons", () => {
            var doc=new RhinoDoc(3203);var c=CaseHub.Get(3203);
            foreach(var reasons in new JsonNode?[]{null, new JsonArray(), new JsonArray("Sampled density deviation 8% > 5% at step 5 (t=1.25 s)",null,12)}) {
                c.StatusData=new JsonObject{["quality"]=new JsonObject{["status"]="warning",["reasons"]=reasons}};
                using var panel=new HawaPanel(3203);
                var label=Walk(panel).OfType<Label>().Single(x=>x.Text.Contains("Quality: warning"));
                assert(label.Text.Contains("Sampled density deviation")== (reasons is JsonArray a && a.Count>0),"Trigger omitted or invented");
                assert(!label.Text.Contains("12"),"Malformed legacy reason displayed");
            }
            CaseHub.Close(3203);
        });
        test("first preset persists a native change even when the Modified setter is ignored", () => {
            var doc=new RhinoDoc(3199){IgnoreModifiedWrites=true};
            doc.Modified=true;assert(!doc.Modified,"Mac-like fixture did not ignore setter");
            using var panel=new HawaPanel(3199);
            assert(!doc.Modified && doc.Strings.GetValue("Hawa","last-created-case")==null,"Opening panel wrote document metadata");
            Walk(panel).OfType<Button>().Single(x=>x.Text=="Block preset").PerformClick();
            var c=CaseHub.Find(3199)!;
            assert(doc.Modified && doc.Strings.GetValue("Hawa","last-created-case")==c.Id.ToString(),"Explicit case not registered as a native document change");
            assert(c.Session==null && c.Job==null,"Creation started solver");CaseHub.Close(3199);
        });
        test("quick preview controls hide saved cases without changing physics, geometry or binding", () => {
            var doc=new RhinoDoc(3202){IgnoreModifiedWrites=true};
            var c=CaseHub.Get(3202);var view=c.View;view["palette"]="spectrum";view["position"]=.3;
            CaseHub.Edit(3202,new(){["view"]=view},c.Version);
            using var panel=new HawaPanel(3202);
            Button Button(string text)=>Walk(panel).OfType<Button>().Single(b=>b.Text==text);
            var owner=Guid.NewGuid();var lease=CaseHub.Bind(c,owner,new[]{"speed"});
            CaseHub.Run(3202);CaseHub.Tick();CaseHub.Tick();
            var session=c.Session;var job=c.Job;var revision=c.Revision;var setup=c.Setup.ToJsonString();var id=c.Id;
            assert(session!=null && !doc.Modified,"Fixture should have a session and clean Mac-like document");
            assert(!Button("Show preview").Enabled && Button("Hide preview").Enabled,"Visible state buttons wrong");
            var version=c.Version;Button("Show preview").Enabled=true;Button("Show preview").PerformClick();
            assert(c.Version==version && !doc.Modified,"Repeated visibility action dirtied an unchanged case");
            Button("Hide preview").PerformClick();
            assert(!c.View["annotations"]!.GetValue<bool>(),"Hide left annotations enabled");
            assert(doc.Modified && c.View["domain"]!.GetValue<bool>()==false && c.View["body"]!.GetValue<bool>()==false && c.View["field"]!.GetValue<bool>()==false,"Hide did not persist all overlays");
            assert(c.Id==id && c.Revision==revision && c.Session==session && c.Job==job && c.BindingLease==lease && c.Setup.ToJsonString()==setup,"Visibility changed physics, identity or binding");
            assert(c.View["palette"]!.GetValue<string>()=="spectrum" && c.View["position"]!.GetValue<double>()==.3,"Visibility reset other display settings");
            assert(Button("Show preview").Enabled && !Button("Hide preview").Enabled,"Hidden state buttons wrong");
            using var preview=new NativePreview();var draw=new Rhino.Display.DisplayPipeline();preview.RaisePostDraw(new(doc,draw));preview.RaiseForeground(new(doc,draw));var bounds=new Rhino.Display.CalculateBoundingBoxEventArgs(doc);preview.RaiseBoundingBox(bounds);
            assert(draw.Calls.Count==0 && bounds.Included.Count==0,"Hidden preview still draws or affects zoom extents");
            var saved=CaseHub.Save(3202);using(var reopened=new HawaPanel(3202))assert(CaseHub.Save(3202)==saved,"Reopening showed a hidden saved case");
            Button("Show preview").PerformClick();
            preview.RaisePostDraw(new(doc,draw));preview.RaiseBoundingBox(bounds);
            assert(draw.Calls.Count>0 && bounds.Included.Count==1 && c.Session==session && c.Revision==revision,"Show failed or restarted physics");
            CaseHub.Close(3202);CaseHub.Restore(3202,saved);
            c=CaseHub.Find(3202)!;
            assert(c.View["domain"]!.GetValue<bool>()==false && c.Session==null,"Saved hidden state did not restore idle");
            CaseHub.Close(3202);
            // Even a programmatic click must not resurrect an absent case.
            Button("Hide preview").Enabled=true;Button("Hide preview").PerformClick();
            assert(CaseHub.Find(3202)==null,"Visibility created an absent case");
        });
        test("annotation control supports legacy views and persists independently of field visibility", () => {
            var doc=new RhinoDoc(3203){IgnoreModifiedWrites=true};var c=CaseHub.Get(3203);
            var legacy=c.Settings();legacy["view"]!.AsObject().Remove("annotations");CaseHub.Restore(3203,legacy.ToJsonString());
            using var panel=new HawaPanel(3203);
            var toggle=Walk(panel).OfType<CheckBox>().Single(x=>x.Text=="Annotations and legend");

            assert(toggle.Checked==true,"Legacy view lost annotations");
            toggle.Checked=false;
            assert(doc.Modified && !c.View["annotations"]!.GetValue<bool>() && c.View["field"]!.GetValue<bool>(),"Annotation toggle failed or hid field");
            var saved=CaseHub.Save(3203);CaseHub.Close(3203);CaseHub.Restore(3203,saved);c=CaseHub.Find(3203)!;
            assert(toggle.Checked==false && !c.View["annotations"]!.GetValue<bool>(),"Annotation choice did not survive restore");
            var invalid=c.View;invalid["annotations"]="yes";bool rejected=false;
            try{CaseHub.Edit(3203,new(){["view"]=invalid},c.Version);}catch(InvalidOperationException){rejected=true;}
            assert(rejected && !c.View["annotations"]!.GetValue<bool>(),"Invalid annotation flag accepted");
            CaseHub.Close(3203);
        });
        test("rejected geometry and invalid fitted domains leave the empty panel empty", () => {
            var doc=new RhinoDoc(3200);
            using var panel=new HawaPanel(3200);
            var button=Walk(panel).OfType<Button>().Single(x=>x.Text=="Select bodies");
            var invalid=new Rhino.Geometry.GeometryBase[]{
                new Rhino.Geometry.Mesh { IsClosed=false },new Rhino.Geometry.Mesh { IsValid=false },
                new Rhino.Geometry.Brep { IsSolid=false },new Rhino.Geometry.Brep { IsValid=false },
                new Rhino.Geometry.GeometryBase(),
                new Rhino.Geometry.Mesh { Bounds=new(new(0,0,0),new(10000,10000,10000)) }
            };
            try {
                foreach(var geometry in invalid){
                    var id=Guid.NewGuid();doc.Objects.Items[id]=new(geometry);
                    NativeGeometry.PickAction=serial=>NativeGeometry.SelectObjects(serial,new[]{id},true);
                    button.PerformClick();
                    assert(CaseHub.Find(3200)==null && !doc.Modified,"Rejected selection published/modified a case");
                    assert(Walk(panel).OfType<Label>().Any(x=>x.Text=="NO CASE"),"Rejected selection replaced empty state");
                    assert(Walk(panel).OfType<TabControl>().Single().Pages.Where(p=>p.Text!="Save / Import").All(p=>!p.Enabled),"Rejected selection exposed case controls");
                }
            } finally { NativeGeometry.PickAction=null; }
            void Reject(Action action){bool rejected=false;try{action();}catch(InvalidOperationException){rejected=true;}catch(ArgumentException){rejected=true;}assert(rejected,"Invalid selection accepted");}
            Reject(()=>NativeGeometry.SelectObjects(3200,Array.Empty<Guid>(),true));
            Reject(()=>NativeGeometry.SelectObjects(3200,Enumerable.Range(0,101).Select(_=>Guid.NewGuid()),true));
            Reject(()=>NativeGeometry.SelectObjects(3200,new[]{Guid.NewGuid()},true));
            Reject(()=>NativeGeometry.SelectObjects(99998,new[]{Guid.NewGuid()},true));
            Reject(()=>NativeGeometry.FitDomain(3200));
            try { RhinoApp.InvokeRequired=true;Reject(()=>NativeGeometry.SelectObjects(3200,new[]{Guid.NewGuid()},true)); }
            finally { RhinoApp.InvokeRequired=false; }
            assert(CaseHub.Find(3200)==null && !doc.Modified,"Rejected preflight created case");
        });
        test("valid geometry commits fitted metres and rejected edits preserve the existing case", () => {
            var doc=new RhinoDoc(3201){ModelUnitSystem=UnitSystem.Millimeters};
            var mesh=Guid.NewGuid();var brep=Guid.NewGuid();
            doc.Objects.Items[mesh]=new(new Rhino.Geometry.Mesh{Bounds=new(new(0,0,0),new(1000,1000,1000))});
            doc.Objects.Items[brep]=new(new Rhino.Geometry.Brep{Bounds=new(new(1000,0,0),new(2000,1000,1000))});
            NativeGeometry.SelectObjects(3201,new[]{mesh,mesh,brep},true);
            var c=CaseHub.Find(3201)!;
            assert(doc.Modified && c.SelectedGeometry && c.Setup["objects"]!.AsArray().Count==2,"Valid selection not committed/deduplicated");
            assert(c.Setup["origin"]!.ToJsonString()=="[-2,-1,-1]" && c.Setup["size"]!.ToJsonString()=="[8,3,3]","Fitted domain units/bounds incorrect");
            NativeGeometry.FitDomain(3201);
            NativeGeometry.SelectObjects(3201,new[]{mesh},false);
            assert(c.Setup["size"]!.ToJsonString()=="[8,3,3]","Unfitted selection changed domain");
            var owner=Guid.NewGuid();var lease=CaseHub.Bind(c,owner,new[]{"speed"});var before=c.Settings().ToJsonString();doc.Modified=false;
            bool rejected=false;try{NativeGeometry.SelectObjects(3201,new[]{Guid.NewGuid()},true);}catch(ArgumentException){rejected=true;}
            assert(rejected && ReferenceEquals(c,CaseHub.Find(3201)) && c.Settings().ToJsonString()==before && !doc.Modified && c.BindingLease==lease,"Rejected edit changed saved case/binding");
            CaseHub.Close(3201);
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
