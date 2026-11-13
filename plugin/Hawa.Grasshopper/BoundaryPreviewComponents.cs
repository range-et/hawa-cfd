using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rhino.Display;
using Rhino.Geometry;
using Hawa.Shared;
namespace Hawa.Grasshopper;

// Components whose accepted case output has a selected-only boundary preview.
// The preview reads the component's own output, so it shows only a case that
// passed SolveHawa (and, for Boundary Set, the worker check). Display only.
internal static class BoundaryPreview
{
    // Case can emit several cases through GH list matching; draw each and bound them all.
    internal static IEnumerable<BoundaryAnnotationSet> Accepted(GH_Component c) => c.Params.Output[0].VolatileData.AllData(true).OfType<HawaGoo>().Select(g =>
        BoundaryAnnotations.ForCase(g.Value)
    ).Where(a =>
        a.Marks.Count > 0
    );
    internal static BoundingBox Bounds(GH_Component c)
    {
        var corners = Accepted(c).SelectMany(a =>
            new[] { a.Bounds.Min, a.Bounds.Max }
        ).ToList();
        return corners.Count == 0 ? BoundingBox.Empty : new BoundingBox(corners);
    }
    internal static void Draw(GH_Component c, IGH_PreviewArgs args)
    {
        if (c.Attributes.Selected)
            foreach (var a in Accepted(c))
                BoundaryOverlay.Instance.Queue(args.Viewport.Id, a);
    }
}

// GH draws every component's wires and then every preview mesh in one pass, so a
// later field mesh covered labels drawn in DrawViewportWires. Selected previews
// queue here and draw in Rhino's foreground channel, after GH's preview meshes.
internal sealed class BoundaryOverlay : DisplayConduit
{
    internal static readonly BoundaryOverlay Instance = new();
    // Keyed by viewport Id: RhinoCommon wraps each draw event's pipeline in a new object.
    readonly Dictionary<Guid, List<BoundaryAnnotationSet>> queued = new();
    internal void Queue(Guid viewport, BoundaryAnnotationSet set)
    {
        if (!queued.TryGetValue(viewport, out var list))
            queued[viewport] = list = new();
        // A pipeline whose foreground never ran must not grow without bound. Like GH's
        // own 16,384 text-dot overlay cap, the bound is far above one frame's previews.
        if (list.Count >= 4096)
            list.Clear();
        list.Add(set);
        Enabled = true;
    }
    protected override void DrawForeground(DrawEventArgs e)
    {
        if (!queued.Remove(e.Viewport.Id, out var list))
            return;
        foreach (var set in list)
            BoundaryAnnotations.Draw(e.Display, set);
    }
}

public sealed class CaseComponent : HawaComponent
{
    public CaseComponent() : base("Hawa Case", "Case", "Combine domain, geometry, physics and boundary assignments", "04 Case") { }
    public override Guid ComponentGuid => new("a7bb3b0a-ae4f-42ae-9301-a3c55f077105");
    protected override void RegisterInputParams(GH_InputParamManager p) { p.AddGenericParameter("Domain", "D", "Hawa Domain", GH_ParamAccess.item); p.AddGenericParameter("Geometry", "G", "Optional voxelized obstacles", GH_ParamAccess.item); p[1].Optional = true; p.AddGenericParameter("Physics", "P", "Hawa Physics", GH_ParamAccess.item); p.AddGenericParameter("Boundaries", "B", "Optional face settings", GH_ParamAccess.item); p[3].Optional = true; }
    protected override void RegisterOutputParams(GH_OutputParamManager p) { p.AddGenericParameter("Case", "C", "Serializable Hawa case", GH_ParamAccess.item); }
    protected override void SolveHawa(IGH_DataAccess da)
    {
        if(new[]{1,3}.Any(i=>
            Params.Input[i].Sources.Count>0 && !Params.Input[i].VolatileData.AllData(true).Any(v=>
                v!=null
            )
        ))return;
        var domain = ReadObject(da, 0); var physics = ReadObject(da, 2); var result = domain.DeepClone().AsObject();
        foreach (var pair in physics.Where(p =>
            p.Key != "kind" && p.Key != "label"
        )) result[pair.Key] = pair.Value?.DeepClone();
        if (Params.Input[1].VolatileDataCount > 0) { var geometry = ReadObject(da, 1); if (domain.ToJsonString() != geometry["domain"]!.ToJsonString()) throw new ArgumentException("Geometry was voxelized on a different domain"); result["solid"] = geometry["solid"]!.DeepClone(); if(geometry["solid_halo"]!=null)result["solid_halo"]=geometry["solid_halo"]!.DeepClone(); if(geometry["wall_links"]!=null)result["wall_links"]=geometry["wall_links"]!.DeepClone(); }
        if (Params.Input[3].VolatileDataCount > 0) result["boundaries"] = ReadObject(da, 3)["boundaries"]!.DeepClone();
        result["kind"] = "Case"; result["label"] = "Hawa wind case";
        da.SetData(0, new HawaGoo(result));
    }
    public override bool IsPreviewCapable => true;
    public override BoundingBox ClippingBox => BoundaryPreview.Bounds(this);
    public override void DrawViewportWires(IGH_PreviewArgs args) => BoundaryPreview.Draw(this, args);
}

public sealed class BoundarySetComponent : HawaQueryComponent
{
    public BoundarySetComponent():base("Hawa Boundary Set","Boundary Set","Compile six physical patches for stationary uniform-grid NEE. Supports one opposite flow-face pair and compatible wall/slip edges. Validation runs in a worker.","03 Physics"){}
    public override Guid ComponentGuid=>new("3c7b9535-cfa0-473e-8dbb-61c984374f14");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Case","C","Base or mapped case; legacy face strings are replaced explicitly",GH_ParamAccess.item);p.AddGenericParameter("Patches","B","Exactly six named Boundary Patch objects",GH_ParamAccess.list);p.AddVectorParameter("Initial velocity","U0","Domain-axis m/s at t=0; default starts from rest",GH_ParamAccess.item,Rhino.Geometry.Vector3d.Zero);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Case","C","Validated NEE case; connect to Solve",GH_ParamAccess.item);p.AddTextParameter("Plan","P","Ownership, scaling and supported limits",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){
        var spec=ReadObject(da,0);var inputs=new List<global::Grasshopper.Kernel.Types.IGH_Goo>();da.GetDataList(1,inputs);var patches=new JsonArray();
        foreach(var input in inputs){var value=input is HawaGoo h?h:(input as global::Grasshopper.Kernel.Types.GH_ObjectWrapper)?.Value as HawaGoo;if(value==null)throw new ArgumentException("Use Boundary Patch objects");var p=value.Data;p.Remove("kind");p.Remove("label");patches.Add(p);}
        var initial=Rhino.Geometry.Vector3d.Zero;da.GetData(2,ref initial);if(!initial.IsValid)throw new ArgumentException("Finite initial velocity required");
        spec["boundary_set"]=new JsonObject{["schema"]=1,["patches"]=patches};spec["boundary_method"]="hawa-nee-v1";spec["initial_velocity"]=Numbers(new[]{initial.X,initial.Y,initial.Z});
        var report=View(new JsonObject{["op"]="check",["case"]=spec});if(report==null)return;
        da.SetData(0,new HawaGoo(spec));da.SetData(1,report.ToJsonString());
    }
    public override bool IsPreviewCapable => true;
    public override BoundingBox ClippingBox => BoundaryPreview.Bounds(this);
    public override void DrawViewportWires(IGH_PreviewArgs args) => BoundaryPreview.Draw(this, args);
}
