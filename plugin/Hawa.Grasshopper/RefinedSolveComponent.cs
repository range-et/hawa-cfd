using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Hawa.Shared;
using Eto.Forms;
namespace Hawa.Grasshopper;

public sealed class RefinedSolveComponent:HawaComponent {
    private string? job,key;private bool first=true,requireOff;
    private Task<string>? submission;
    public RefinedSolveComponent():base("Hawa Refined Solve","Refine","Experimental static two-level BGK solver. Run false cancels. Outputs two field frames on completion.","05 Solve"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077138");
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Coarse case","C","Parent case, BGK, voxel walls",GH_ParamAccess.item);p.AddGenericParameter("Fine case","F","Patch case, same physics, voxel walls",GH_ParamAccess.item);p.AddIntegerParameter("Steps","N","Coarse iterations",GH_ParamAccess.item,200);p.AddTextParameter("Device","GPU","auto, mps, cpu, cuda:0",GH_ParamAccess.item,"auto");p.AddBooleanParameter("Run","R","False cancels. Saved true opens idle.",GH_ParamAccess.item,false);p.AddBooleanParameter("Pause","P","Pause at a step boundary",GH_ParamAccess.item,false);}
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddGenericParameter("Coarse frame","C","Parent field, covered interior masked",GH_ParamAccess.item);p.AddGenericParameter("Fine frame","F","Patch field",GH_ParamAccess.item);p.AddTextParameter("State","S","State and progress",GH_ParamAccess.item);p.AddTextParameter("Report","R","Method limits and mass change",GH_ParamAccess.item);}
    protected override void SolveHawa(IGH_DataAccess da){bool run=false,pause=false;da.GetData(4,ref run);da.GetData(5,ref pause);if(first){first=false;requireOff=run;}if(!run){requireOff=false;InputsMissing();Message="stopped";return;}if(requireOff){Message="enable again";return;}var coarse=ReadObject(da,0);var fine=ReadObject(da,1);int steps=200;string device="auto";da.GetData(2,ref steps);da.GetData(3,ref device);
        var req=new JsonObject{["op"]="evaluate_submit",["kind"]="refine",["case"]=coarse.DeepClone(),["fine_case"]=fine.DeepClone(),["steps"]=steps,["device"]=device};string signature=req.ToJsonString();
        if(key!=signature){
            InputsMissing();
            try { RefinementAdmission.Require(coarse,fine); }
            catch(ArgumentException e) { throw new ArgumentException(Identity()+": "+e.Message); }
            key=signature;
            submission=Task.Run(()=>
                EmbeddedRuntime.Call(req)["job"]!.GetValue<string>()
            );
        }
        if(submission!=null){
            if(!submission.IsCompleted){Message="checking refinement";string expected=key!;HawaPollScheduler.Request(this,()=>
                key==expected
            );return;}
            var finished=submission;submission=null;
            if(finished.IsFaulted)throw new ArgumentException(Identity()+": "+finished.Exception!.GetBaseException().Message);
            job=finished.Result;
        }
        EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_control",["job"]=job,["action"]=pause?"pause":"resume"});var status=EmbeddedRuntime.Call(new JsonObject{["op"]="evaluate_poll",["job"]=job});string state=status["state"]!.GetValue<string>();Message=state;da.SetData(2,$"{state}: {status["steps"]}/{status["target"]}");if(state=="failed")throw new Exception(status["error"]!.GetValue<string>());
        if(state=="completed"){var r=status["result"]!;for(int i=0;i<2;i++){var f=r[i==0?"coarse_frame":"fine_frame"]!.DeepClone().AsObject();f["kind"]="Frame";da.SetData(i,new HawaGoo(f));}da.SetData(3,$"{r["report"]}\nRelative composite mass change: {r["relative_mass_change"]}");}else{string expected=job!;HawaPollScheduler.Request(this,()=>
            job==expected
        );}}
    public override void DocumentContextChanged(GH_Document document,GH_DocumentContext context){if(context==GH_DocumentContext.Close||context==GH_DocumentContext.Unloaded||context==GH_DocumentContext.Lock)requireOff=true;base.DocumentContextChanged(document,context);}
    private string Identity()
    {
        var parts=new List<string>{$"Refined Solve {InstanceGuid}"};
        for(int i=0;i<2;i++){
            var input=Params.Input[i];
            var sources=new List<string>();
            foreach(var source in input.Sources){
                var owner=source.Attributes?.GetTopLevel?.DocObject;
                sources.Add(owner==null ? source.NickName : $"{owner.NickName} ({owner.InstanceGuid})");
            }
            parts.Add(input.Name+": "+(sources.Count==0 ? "local input" : string.Join(", ",sources)));
        }
        return string.Join("; ",parts);
    }
    protected override void InputsMissing(){
        var owned=job;var pending=submission;job=key=null;submission=null;
        // The process owns late submissions after document removal. Drain on the
        // UI timer so a quiet/closed GH document cannot strand the reply and
        // CaseHub's single-writer cleanup contract is preserved.
        if(pending!=null){
            var timer=new UITimer { Interval=.1 };
            EventHandler<EventArgs>? drain=null;
            drain=(_,_)=>{
                if(!pending.IsCompleted)return;
                timer.Stop();timer.Elapsed-=drain;timer.Dispose();
                if(pending.IsCompletedSuccessfully)CaseHub.ReleaseJob(pending.Result);
                else _=pending.Exception;
            };
            timer.Elapsed+=drain;timer.Start();
        }
        CaseHub.ReleaseJob(owned);
    }
    public override void RemovedFromDocument(GH_Document doc){InputsMissing();base.RemovedFromDocument(doc);}
}
