using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using GH_IO.Serialization;
using Hawa.Shared;
namespace Hawa.Grasshopper;

public sealed class LinkedCaseComponent : HawaComponent
{
    private uint document;
    private Guid caseId, lease;
    private long seenVersion = -1, callbackGeneration;
    private bool subscribed, scheduled, pull;
    public LinkedCaseComponent() : base("Hawa Linked Case", "LiveCase", "Live native case binding. Direct sliders sync both ways; calculated inputs are read-only in the panel. The shared service owns the solver.", "00 Setup") { Hidden = true; }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077150");
    protected override void RegisterInputParams(GH_InputParamManager p) { foreach (var setting in CaseHub.Parameters) { p.AddNumberParameter(setting.Label, setting.Key, setting.Unit + "; connect a slider for bidirectional editing", GH_ParamAccess.item); p[p.ParamCount - 1].Optional = true; } }
    protected override void RegisterOutputParams(GH_OutputParamManager p)
    {
        p.AddGenericParameter("Solution", "S", "Live shared session, not an optimization fitness result", GH_ParamAccess.item);
        p.AddMeshParameter("Field preview", "M", "Current case field; withheld while outdated", GH_ParamAccess.item);
        p.AddTextParameter("Status", "R", "Case version, result provenance and failures", GH_ParamAccess.item);
        p.AddTextParameter("Case ID", "ID", "Persistent native case ID", GH_ParamAccess.item);
    }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        if (document == 0 || Rhino.RhinoDoc.FromRuntimeSerialNumber(document) == null) {
            var doc = Rhino.RhinoDoc.ActiveDoc ?? throw new Exception("Open a Rhino document"); document = doc.RuntimeSerialNumber;
        }
        var c = CaseHub.Get(document);
        if (caseId != Guid.Empty && caseId != c.Id) throw new Exception("This definition belongs to another native case. Reopen its Rhino file or place a new Linked Case component.");
        var parameters = NativeSettings.Parameters(c.SelectedGeometry);
        if (c.SelectedGeometry && Params.Input[2].Sources.Count > 0) throw new Exception("Block width applies to the block preset. Disconnect width for selected Rhino geometry.");
        bool savedBinding = caseId != Guid.Empty && seenVersion < 0;
        caseId = c.Id;
        if (!subscribed) { CaseHub.Changed += OnChanged; subscribed = true; }
        var precision = new Dictionary<string, int>();
        for (int i = 0; i < 3; i++) {
            var input = Params.Input[i];
            if (input.Sources.Count > 0 && (input.Sources.Count != 1 || input.VolatileDataCount != 1)) throw new Exception("Each linked input requires exactly one finite value from one source");
            if (input.Sources.Count == 1 && input.Sources[0] is GH_NumberSlider slider) {
                var p = parameters[i];
                if ((double)slider.Slider.Minimum > p.Minimum || (double)slider.Slider.Maximum < p.Maximum || slider.Slider.DecimalPlaces < 2)
                    throw new Exception($"{p.Label}: linked slider must cover {p.Minimum}..{p.Maximum} with at least two decimal places");
                precision[p.Key] = slider.Slider.DecimalPlaces;
            }
        }
        // Data access may already contain stale values when a scheduled pull is overtaken
        // by another GH solution. Defer slider writes to GH's pre-solution callback.
        if (pull || savedBinding || (seenVersion >= 0 && seenVersion != c.Version)) {
            pull = true; Schedule(c); Message = "syncing"; return;
        }
        var patch = new JsonObject();
        for (int i = 0; i < 3; i++) if (Params.Input[i].Sources.Count > 0) {
            double value = 0;
            if (!da.GetData(i, ref value) || !double.IsFinite(value)) throw new Exception("Linked input must be one finite number");
            var p = parameters[i];
            if (value < p.Minimum || value > p.Maximum) throw new Exception($"{p.Label}: {p.Minimum}..{p.Maximum} {p.Unit}");
            if (Math.Abs(value - c.Value(p.Key)) > 1e-9) patch[p.Key] = value;
        }
        var driven = Enumerable.Range(0, 3).Where(i => Params.Input[i].Sources.Count > 0 && Params.Input[i].Sources[0] is not GH_NumberSlider).Select(i => CaseHub.Parameters[i].Key);
        lease = CaseHub.Bind(c, InstanceGuid, driven);
        CaseHub.ConfigureBinding(c, InstanceGuid, lease, precision);
        if (patch.Count > 0) CaseHub.EditFromBinding(document, caseId, InstanceGuid, lease, patch, c.Version);
        seenVersion = c.Version;
        if (c.Session != null && c.Spec != null) da.SetData(0, new HawaGoo(new() {
            ["kind"] = "Solution", ["session"] = c.Session, ["revision"] = c.Steps, ["case"] = CaseGeometry.SpecInModelUnits(c),
            ["case_id"] = c.Id.ToString(), ["physics_revision"] = c.Revision, ["generation"] = c.Generation, ["completed"] = c.State == "completed"
        }));
        if (!c.Outdated) { var mesh = CaseGeometry.ResultMesh(c); if (mesh != null) da.SetData(1, mesh); }
        da.SetData(2, c.Describe().ToJsonString()); da.SetData(3, c.Id.ToString()); Message = c.State;
    }
    private void PullSliders(CaseState c)
    {
        var updates = new List<(GH_NumberSlider Slider, decimal Value)>();
        for (int i = 0; i < 3; i++) if (Params.Input[i].Sources.Count == 1 && Params.Input[i].Sources[0] is GH_NumberSlider slider) {
            decimal value = (decimal)c.Value(CaseHub.Parameters[i].Key);
            if (value < slider.Slider.Minimum || value > slider.Slider.Maximum || Math.Abs((double)(Math.Round(value, slider.Slider.DecimalPlaces) - value)) > 1e-9) throw new Exception("Linked slider cannot represent the native value; extend its range or precision");
            if (Math.Abs((double)(slider.CurrentValue - value)) > 1e-9) updates.Add((slider, value));
        }
        // Validate the whole pull before touching any slider.
        foreach (var update in updates) { update.Slider.SetSliderValue(update.Value); update.Slider.ExpireSolution(false); }
    }
    private void OnChanged(CaseState c, string origin)
    {
        if (c.Document != document) return;
        if (origin == "closed") { Detach(); return; }
        if (origin == "binding" || origin == InstanceGuid.ToString()) return;
        if (c.Version != seenVersion) pull = true; // Remember changes even while locked.
        if (Locked || (c.BindingOwner != InstanceGuid && origin == "progress")) return;
        Schedule(c);
    }
    private void Schedule(CaseState c)
    {
        if (scheduled) return;
        var doc = OnPingDocument(); if (doc == null) return;
        scheduled = true; long token = callbackGeneration;
        doc.ScheduleSolution(100, _ => {
            if (token != callbackGeneration) return;
            scheduled = false;
            if (!subscribed || Locked || OnPingDocument() != doc || CaseHub.Find(document) != c) return;
            try {
                if (c.Id != caseId || (c.BindingOwner != null && c.BindingOwner != InstanceGuid) ||
                    (lease != Guid.Empty && c.BindingLease != lease))
                    throw new InvalidOperationException("Native case binding changed; reconnect before syncing");
                if (pull || seenVersion != c.Version) {
                    long version = c.Version;
                    PullSliders(c); seenVersion = version; pull = c.Version != version;
                }
                ExpireSolution(false);
            } catch (Exception e) {
                InputsMissing(); Message = "sync failed";
                AddRuntimeMessage(GH_RuntimeMessageLevel.Error, e.Message);
            }
        });
    }
    protected override void InputsMissing()
    {
        var c = CaseHub.Find(document); if (c != null) CaseHub.Unbind(c, InstanceGuid, lease);
        lease = Guid.Empty; callbackGeneration++; scheduled = false;
    }
    private void Detach()
    {
        if (subscribed) CaseHub.Changed -= OnChanged; subscribed = false;
        InputsMissing(); pull = true;
    }
    public override void RemovedFromDocument(GH_Document d) { Detach(); base.RemovedFromDocument(d); }
    public override void DocumentContextChanged(GH_Document d, GH_DocumentContext context)
    {
        if (context is GH_DocumentContext.Close or GH_DocumentContext.Unloaded) Detach();
        if (context == GH_DocumentContext.Unlock) pull = true;
        base.DocumentContextChanged(d, context);
    }
    public override bool Write(GH_IWriter w) { w.SetString("native_case", caseId.ToString()); return base.Write(w); }
    public override bool Read(GH_IReader r) { if (r.ItemExists("native_case")) Guid.TryParse(r.GetString("native_case"), out caseId); document = 0; seenVersion = -1; return base.Read(r); }
}
