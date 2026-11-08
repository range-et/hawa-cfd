using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using GH_IO.Serialization;
using Hawa.Shared;
namespace Hawa.Grasshopper;

public sealed class LinkedCaseComponent : HawaComponent
{
    private uint document;
    private Guid caseId;
    private bool subscribed,scheduled,pull;
    public LinkedCaseComponent():base("Hawa Linked Case","LiveCase","Live native block-case binding. Direct sliders sync both ways; calculated inputs are read-only in the panel. The shared service owns the solver.","00 Setup"){Hidden=true;}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077150");
    protected override void RegisterInputParams(GH_InputParamManager p){foreach(var setting in CaseHub.Parameters){p.AddNumberParameter(setting.Label,setting.Key,setting.Unit+"; connect a slider for bidirectional editing",GH_ParamAccess.item);p[p.ParamCount-1].Optional=true;}}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Solution","S","Shared session; use existing result components",GH_ParamAccess.item);p.AddMeshParameter("Field preview","M","Shared native field result",GH_ParamAccess.item);p.AddTextParameter("Status","R","Case revision, state and job",GH_ParamAccess.item);p.AddTextParameter("Case ID","ID","Persistent native case ID",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da)
    {
        scheduled=false;
        if(document==0||Rhino.RhinoDoc.FromRuntimeSerialNumber(document)==null){var doc=Rhino.RhinoDoc.ActiveDoc??throw new Exception("Open a Rhino document");document=doc.RuntimeSerialNumber;}
        var c=CaseHub.Get(document);if(caseId!=Guid.Empty&&caseId!=c.Id)throw new Exception("This definition belongs to another native case. Reopen its Rhino file or place a new Linked Case component.");caseId=c.Id;
        if(!subscribed){CaseHub.Changed+=OnChanged;subscribed=true;}
        for(int i=0;i<3;i++)if(Params.Input[i].Sources.Count==1&&Params.Input[i].Sources[0] is GH_NumberSlider slider){
            var p=CaseHub.Parameters[i];
            if((double)slider.Slider.Minimum>p.Minimum||(double)slider.Slider.Maximum<p.Maximum||slider.Slider.DecimalPlaces<2)
                {Detach();throw new Exception($"{p.Label}: linked slider must cover {p.Minimum}..{p.Maximum} with at least two decimal places");}
        }
        var driven=Enumerable.Range(0,3).Where(i=>Params.Input[i].Sources.Count>0&&(Params.Input[i].Sources.Count!=1||Params.Input[i].Sources[0] is not GH_NumberSlider)).Select(i=>CaseHub.Parameters[i].Key);
        CaseHub.Bind(c,InstanceGuid,driven);
        var patch=new JsonObject();for(int i=0;i<3;i++)if(Params.Input[i].Sources.Count>0){double value=0;if(!da.GetData(i,ref value))throw new Exception("Linked input is missing");if(Math.Abs(value-c.Value(CaseHub.Parameters[i].Key))>1e-9)patch[CaseHub.Parameters[i].Key]=value;}
        if(patch.Count>0)CaseHub.Edit(document,patch,c.Revision,InstanceGuid.ToString());
        if(c.Session!=null&&c.Spec!=null)da.SetData(0,new HawaGoo(new(){["kind"]="Solution",["session"]=c.Session,["revision"]=c.Steps,["case"]=c.Spec.DeepClone()}));
        var mesh=CaseGeometry.ResultMesh(c);if(mesh!=null)da.SetData(1,mesh);
        da.SetData(2,c.Describe().ToJsonString());da.SetData(3,c.Id.ToString());Message=c.State;
    }
    private void OnChanged(CaseState c,string origin)
    {
        if(c.Document!=document||origin=="binding"||origin==InstanceGuid.ToString()||Locked)return;
        if(origin=="closed"){Detach();return;}
        pull|=origin is "panel" or "undo" or "restore";
        if(scheduled)return;var doc=OnPingDocument();if(doc==null)return;scheduled=true;
        doc.ScheduleSolution(100,_=>{
            scheduled=false;if(!subscribed||Locked||OnPingDocument()!=doc||CaseHub.Find(document)!=c)return;
            if(pull){pull=false;for(int i=0;i<3;i++)if(Params.Input[i].Sources.Count==1&&Params.Input[i].Sources[0] is GH_NumberSlider slider){decimal value=(decimal)c.Value(CaseHub.Parameters[i].Key);if(value<slider.Slider.Minimum||value>slider.Slider.Maximum){AddRuntimeMessage(GH_RuntimeMessageLevel.Error,"Linked slider range excludes the native value");continue;}slider.SetSliderValue(value);slider.ExpireSolution(false);}}
            ExpireSolution(false);
        });
    }
    private void Detach(){if(subscribed)CaseHub.Changed-=OnChanged;subscribed=false;var c=CaseHub.Find(document);if(c!=null)CaseHub.Unbind(c,InstanceGuid);scheduled=false;}
    public override void RemovedFromDocument(GH_Document d){Detach();base.RemovedFromDocument(d);}
    public override void DocumentContextChanged(GH_Document d,GH_DocumentContext context){if(context is GH_DocumentContext.Close or GH_DocumentContext.Unloaded)Detach();base.DocumentContextChanged(d,context);}
    public override bool Write(GH_IWriter w){w.SetString("native_case",caseId.ToString());return base.Write(w);}
    public override bool Read(GH_IReader r){if(r.ItemExists("native_case"))Guid.TryParse(r.GetString("native_case"),out caseId);document=0;return base.Read(r);}
}
