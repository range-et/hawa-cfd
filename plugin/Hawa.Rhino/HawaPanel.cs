using System.Runtime.InteropServices;
using System.Text.Json.Nodes;
using Eto.Forms;
using Eto.Drawing;
using Rhino;
using Hawa.Shared;
namespace Hawa.Native;

[Guid("34472112-31d7-4d1e-98f9-fb6130a50501")]
public sealed class HawaPanel : Panel
{
    private readonly uint document;
    private readonly Dictionary<string,NumericStepper> numbers = new();
    private readonly NumericStepper[] origin = Enumerable.Range(0,3).Select(_=>Number(-1e7,1e7,6,.1)).ToArray();
    private readonly NumericStepper[] size = Enumerable.Range(0,3).Select(_=>Number(.00001,1e7,6,.1)).ToArray();
    private readonly NumericStepper viscosity = Number(1e-9,100,9,.00001), density = Number(.000001,1e6,6,.1), mach = Number(.001,.2,3,.01);
    private readonly NumericStepper target = Number(1,100000,0,25), position = Number(0,1,3,.05), low = Number(-1e12,1e12,6,.1), high = Number(-1e12,1e12,6,.1);
    private readonly DropDown device = Choice("cpu","mps","auto","cuda:0"), field = Choice("speed","pressure","density"), collision = Choice("bgk","trt","regularized","smagorinsky"), axis = Choice("YZ · X normal","XZ · Y normal","XY · Z normal"), palette = Choice("blue-green","spectrum","diverging");
    private readonly DropDown[] boundaries = Enumerable.Range(0,6).Select(_=>Choice("inlet","outlet","wall","slip","periodic")).ToArray();
    private readonly CheckBox autoRange = new() { Text="Automatic colour limits" }, showDomain = new() { Text="Domain wireframe" }, showBody = new() { Text="Body bounds" }, showField = new() { Text="Field plane and legend" };
    private readonly Label state = Text(), link = Text(), error = Text(), geometry = Text(), grid = Text(), captured = Text();
    private readonly ProgressBar progress = new() { MinValue=0, MaxValue=100 };
    private readonly Button run, pause, cancel, reset, refresh;
    private bool refreshing;
    private long displayedVersion = -1;
    private static Label Text(string text="") => new() { Text=text, Width=300, Wrap=WrapMode.Word, TextAlignment=TextAlignment.Left };
    private static NumericStepper Number(double min,double max,int decimals,double increment) => new() { MinValue=min,MaxValue=max,DecimalPlaces=decimals,Increment=increment,Width=115 };
    private static DropDown Choice(params string[] values) => new() { DataStore=values,Width=150 };
    private static DynamicLayout Layout() => new() { Padding=new Padding(10),Spacing=new Size(8,8) };
    private Button Action(string text,string icon,string hint,System.Action action) {
        var button = new Button { Text=text, Image=NativeIcons.Get(icon), ImagePosition=ButtonImagePosition.Left, ToolTip=hint, MinimumSize=new Size(145,30) };
        button.Click += (_,_)=>Safe(action); return button;
    }
    public HawaPanel(uint documentSerialNumber) {
        document=documentSerialNumber; MinimumSize=new Size(350,570);
        error.TextColor=Colors.DarkRed;
        var root=Layout(); root.AddSeparateRow(new ImageView { Image=NativeIcons.Get("hawa") },new Label { Text="Hawa 0.5",Font=new Font(SystemFont.Bold,17),TextAlignment=TextAlignment.Left },null);
        root.AddSeparateRow(state);root.AddSeparateRow(progress);
        run=Action("Run / Resume","run","Run the accepted physical case to its total target. First runtime initialization can take time.",()=>CaseHub.Run(document));
        pause=Action("Pause","pause","Request a cooperative pause. Wait for PAUSED before inspecting a stationary result.",()=>CaseHub.Pause(document));
        cancel=Action("Cancel","cancel","Stop this run and release its runtime resources. Retained results are marked outdated.",()=>CaseHub.Cancel(document));
        reset=Action("Reset","reset","Stop the run and clear its results; preserve geometry and settings.",()=>CaseHub.Reset(document));
        root.AddSeparateRow(run,pause);root.AddSeparateRow(cancel,reset);
        var tabs=new TabControl();
        var setup=Layout();
        setup.AddSeparateRow(Text("1 / Geometry and domain · global +X flow"));
        setup.AddSeparateRow(Action("Select bodies","geometry","Select closed Rhino meshes or solid Breps. The suggested domain is a starting point; study domain sensitivity.",()=>NativeGeometry.Pick(document)),Action("Fit domain","domain","Rebuild domain padding around the current selection.",()=>NativeGeometry.FitDomain(document)));
        setup.AddSeparateRow(geometry);
        setup.AddSeparateRow(Action("Block preset","reset","Return to the original demonstration. Geometry in Rhino is preserved.",()=> {
            var c=CaseHub.Get(document);CaseHub.Edit(document,new(){["setup"]=NativeSettings.DefaultSetup(),["cell"]=.5,["speed"]=1d,["width"]=1d},displayedVersion);
        }));
        for(int i=0;i<3;i++){setup.AddSeparateRow(new Label{Text="Origin "+"XYZ"[i]+" (m)"},origin[i]);setup.AddSeparateRow(new Label{Text="Length "+"XYZ"[i]+" (m)"},size[i]);}
        setup.AddSeparateRow(Text("2 / Fluid · SI units"));
        setup.AddSeparateRow(Text("Defaults use demonstration viscosity. Enter the physical properties of your fluid before interpreting a design."));
        setup.AddSeparateRow(new Label{Text="Kinematic viscosity (m²/s)"},viscosity);setup.AddSeparateRow(new Label{Text="Density (kg/m³)"},density);setup.AddSeparateRow(new Label{Text="Lattice Mach"},mach);setup.AddSeparateRow(new Label{Text="Collision model"},collision);
        string[] faces={"X−","X+","Y−","Y+","Z−","Z+"};
        for(int i=0;i<6;i++) setup.AddSeparateRow(new Label{Text=faces[i]+" boundary"},boundaries[i]);
        setup.AddSeparateRow(Text("Native cases use an X− inlet and X+ outlet. Pair periodic side faces. Moving bodies and refinement remain available through their GH workflows."));
        setup.AddSeparateRow(Action("Apply setup","apply","Validate and apply the complete domain/fluid/boundary edit. A physical change stops the previous run.",ApplySetup));setup.Add(null);
        var solve=Layout();solve.AddSeparateRow(Text("3 / Resolution and run"));
        foreach(var p in CaseHub.Parameters){var input=Number(p.Minimum,p.Maximum,6,p.Key=="cell"?.01:.1);numbers[p.Key]=input;input.ToolTip=p.Label+" in "+p.Unit+". Changes stop the old physical run.";input.ValueChanged+=(_,_)=>Edit(new(){[p.Key]=input.Value});solve.AddSeparateRow(new Label{Text=p.Label+" ("+p.Unit+")"},input);}
        target.ValueChanged+=(_,_)=>Edit(new(){["target"]=(int)target.Value});device.SelectedIndexChanged+=(_,_)=>{if(device.SelectedIndex>=0)Edit(new(){["device"]=device.SelectedValue.ToString()});};
        solve.AddSeparateRow(new Label{Text="Total target iterations"},target);solve.AddSeparateRow(new Label{Text="Backend"},device);solve.AddSeparateRow(grid);solve.AddSeparateRow(link);
        solve.AddSeparateRow(Text("Use Linked Case for GH control. Direct sliders sync both ways; calculated values are read-only here. Disconnect block width when using selected bodies. Save the Rhino file and linked GH definition together. Reopening stays idle."));solve.Add(null);
        var view=Layout();view.AddSeparateRow(Text("4 / Field display"));
        field.SelectedIndexChanged+=(_,_)=>{if(field.SelectedIndex>=0)Edit(new(){["field"]=field.SelectedValue.ToString()});};
        view.AddSeparateRow(new Label{Text="Scalar field"},field);view.AddSeparateRow(new Label{Text="Slice orientation"},axis);view.AddSeparateRow(new Label{Text="Slice position (0..1)"},position);view.AddSeparateRow(new Label{Text="Colour palette"},palette);view.AddSeparateRow(autoRange);view.AddSeparateRow(new Label{Text="Lower limit (field units)"},low);view.AddSeparateRow(new Label{Text="Upper limit (field units)"},high);view.AddSeparateRow(showDomain);view.AddSeparateRow(showBody);view.AddSeparateRow(showField);
        view.AddSeparateRow(Action("Apply display","field","Change the slice and colour settings without restarting the solver. Use fixed limits for comparisons.",ApplyView));
        refresh=Action("Refresh field","reset","Retry a failed or stale field query while preserving a healthy run.",()=>CaseHub.RefreshView(document));view.AddSeparateRow(refresh,Action("Zoom domain","fit","Frame the physical domain in this Rhino document.",()=>{var doc=RhinoDoc.FromRuntimeSerialNumber(document)!;doc.Views.ActiveView.ActiveViewport.ZoomBoundingBox(CaseGeometry.Bounds(CaseHub.Get(document)));doc.Views.Redraw();}));
        view.AddSeparateRow(captured);view.AddSeparateRow(Text("Pressure is physical pressure from the LBM conversion. Colours use the displayed frame. A completed run does not establish convergence or engineering accuracy."));view.Add(null);
        tabs.Pages.Add(new TabPage{Text="Setup",Content=new Scrollable{Content=setup}});tabs.Pages.Add(new TabPage{Text="Solve",Content=new Scrollable{Content=solve}});tabs.Pages.Add(new TabPage{Text="View",Content=new Scrollable{Content=view}});
        root.Add(tabs,true,true);root.AddSeparateRow(error);Content=root;
        CaseHub.Changed+=OnChanged;RefreshState(true);
    }
    private void ApplySetup(){var c=CaseHub.Get(document);var setup=c.Setup;setup["origin"]=new JsonArray(origin.Select(v=>JsonValue.Create(v.Value)).ToArray());setup["size"]=new JsonArray(size.Select(v=>JsonValue.Create(v.Value)).ToArray());setup["viscosity"]=viscosity.Value;setup["density"]=density.Value;setup["mach"]=mach.Value;setup["collision"]=collision.SelectedValue.ToString();setup["boundaries"]=new JsonArray(boundaries.Select(v=>JsonValue.Create(v.SelectedValue.ToString())).ToArray());CaseHub.Edit(document,new(){["setup"]=setup},displayedVersion);}
    private void ApplyView(){var view=new JsonObject{["axis"]=axis.SelectedIndex,["position"]=position.Value,["palette"]=palette.SelectedValue.ToString(),["auto_range"]=autoRange.Checked==true,["min"]=low.Value,["max"]=high.Value,["domain"]=showDomain.Checked==true,["body"]=showBody.Checked==true,["field"]=showField.Checked==true};CaseHub.Edit(document,new(){["view"]=view},displayedVersion);}
    protected override void Dispose(bool disposing){if(disposing)CaseHub.Changed-=OnChanged;base.Dispose(disposing);}
    private void Safe(System.Action action){try{error.Text="";action();RefreshState();}catch(Exception e){RefreshState(true);error.Text=e.GetBaseException().Message;}}
    private void Edit(JsonObject patch){if(!refreshing)Safe(()=>CaseHub.Edit(document,patch,displayedVersion));}
    private void OnChanged(CaseState c,string origin){if(c.Document!=document)return;if(origin=="closed"){state.Text="CASE CLOSED";link.Text="Grasshopper: unlinked";run.Enabled=pause.Enabled=cancel.Enabled=reset.Enabled=refresh.Enabled=false;}else RefreshState();}
    private void RefreshState(bool force=false){
        if(RhinoDoc.FromRuntimeSerialNumber(document)==null)return;
        var c=CaseHub.Get(document);refreshing=true;
        try{
            if(force||displayedVersion!=c.Version){
                foreach(var p in NativeSettings.Parameters(c.SelectedGeometry)){var input=numbers[p.Key];input.MinValue=p.Minimum;input.MaxValue=p.Maximum;input.Value=c.Value(p.Key);input.Enabled=!c.Driven.Contains(p.Key)&&(!c.SelectedGeometry||p.Key!="width");}
                var setup=c.Setup;var view=c.View;
                for(int i=0;i<3;i++){origin[i].Value=setup["origin"]![i]!.GetValue<double>();size[i].Value=setup["size"]![i]!.GetValue<double>();origin[i].Enabled=size[i].Enabled=c.SelectedGeometry;}
                viscosity.Value=setup["viscosity"]!.GetValue<double>();density.Value=setup["density"]!.GetValue<double>();mach.Value=setup["mach"]!.GetValue<double>();collision.SelectedValue=setup["collision"]!.GetValue<string>();for(int i=0;i<6;i++){boundaries[i].SelectedValue=setup["boundaries"]![i]!.GetValue<string>();boundaries[i].Enabled=i>=2;}
                target.Value=c.Target;device.SelectedValue=c.Device;field.SelectedValue=c.Field;axis.SelectedIndex=view["axis"]!.GetValue<int>();position.Value=view["position"]!.GetValue<double>();palette.SelectedValue=view["palette"]!.GetValue<string>();autoRange.Checked=view["auto_range"]!.GetValue<bool>();low.Value=view["min"]!.GetValue<double>();high.Value=view["max"]!.GetValue<double>();showDomain.Checked=view["domain"]!.GetValue<bool>();showBody.Checked=view["body"]!.GetValue<bool>();showField.Checked=view["field"]!.GetValue<bool>();displayedVersion=c.Version;
            }
            // Ownership changes do not require a settings version change.
            foreach(var p in CaseHub.Parameters)numbers[p.Key].Enabled=!c.Driven.Contains(p.Key)&&(!c.SelectedGeometry||p.Key!="width");
            state.Text=$"{c.State.ToUpperInvariant()} · {c.Steps:N0} / {c.Target:N0} steps";progress.Value=(int)Math.Clamp(100d*c.Steps/c.Target,0,100);
            geometry.Text=c.SelectedGeometry?$"{c.Setup["objects"]!.AsArray().Count} referenced Rhino bodies · coordinates in metres":"Block starter · 8 × 6 × 4 m · demonstration viscosity";
            var shape=CaseGeometry.GridShape(c);long cells=(long)shape[0]*shape[1]*shape[2];grid.Text=$"{shape[0]} × {shape[1]} × {shape[2]} · {cells:N0} cells\nD3Q19 FP32 populations alone: {cells*19*4/1048576d:F1} MiB; solver needs additional memory.";
            link.Text=c.BindingOwner==null?"Grasshopper: unlinked":c.Driven.Count==0?"Grasshopper: linked sliders":"Grasshopper drives: "+string.Join(", ",c.Driven);
            captured.Text=c.Result==null?"No field captured":$"Field {c.Result.Field} · {CaseGeometry.FieldUnits(c.Result.Field)}\nCaptured step {c.Result.Steps}, t={c.Result.PhysicalTime:g5} s"+(c.Outdated?"\nOUTDATED · run the changed case":"");
            bool working=c.State is "running" or "preparing" or "voxelizing" or "pausing";
            run.Enabled=!working;pause.Enabled=c.State is "running" or "preparing" or "voxelizing";cancel.Enabled=working||c.Session!=null;reset.Enabled=true;refresh.Enabled=c.Session!=null;
            error.Text=c.Error+(c.GeometryError.Length>0?"\n"+c.GeometryError:"")+(c.ViewError.Length>0?"\nField: "+c.ViewError+". Use Refresh field.":"")+(CaseHub.PendingCleanupCount>0?"\nCleanup pending; Hawa will retry.":"");
        }finally{refreshing=false;}
    }
}
