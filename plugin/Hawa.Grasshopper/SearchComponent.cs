using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;

namespace Hawa.Grasshopper;

public sealed class SearchComponent : HawaComponent
{
    private bool first=true, previousRun, requireOff, previousRestore;
    private int generation;
    private decimal[]? pending;
    private bool scheduled;
    private string? seen;
    private int count;
    private double best=double.PositiveInfinity;
    private decimal[]? bestGenes;
    private readonly Random random=new(7331);
    public SearchComponent():base("Hawa Search","Search","Completion-driven bounded mutation search. Connect gene sliders directly, and completed fitness and candidate ID from Evaluate. Minimize. Run and Evaluate Enable should share a toggle.","05 Solve"){}
    public override Guid ComponentGuid=>new("a7bb3b0a-ae4f-42ae-9301-a3c55f077118");
    protected override void RegisterInputParams(GH_InputParamManager p){
        p.AddNumberParameter("Genes","G","Connect number sliders directly",GH_ParamAccess.list);p[0].Optional=true;
        p.AddNumberParameter("Fitness","F","Completed fitness from Evaluate",GH_ParamAccess.item);p[1].Optional=true;
        p.AddTextParameter("Candidate","ID","Completed candidate ID from Evaluate",GH_ParamAccess.item);p[2].Optional=true;
        p.AddBooleanParameter("Run","R","True advances search after completed results",GH_ParamAccess.item,false);
        p.AddBooleanParameter("Pause","P","Pause candidate changes; connect the same toggle to Evaluate Pause",GH_ParamAccess.item,false);
        p.AddIntegerParameter("Budget","N","Maximum completed candidates",GH_ParamAccess.item,10);
        p.AddNumberParameter("Mutation","M","Fraction of slider range",GH_ParamAccess.item,.15);
        p.AddBooleanParameter("Restore best","B","Restore best genes while stopped",GH_ParamAccess.item,false);
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddNumberParameter("Best fitness","F","Lowest completed fitness",GH_ParamAccess.item);p.AddNumberParameter("Best genes","G","Gene values in source order",GH_ParamAccess.list);p.AddTextParameter("History","H","Candidate, fitness and genes",GH_ParamAccess.list);p.AddTextParameter("State","S","Search state",GH_ParamAccess.item);}
    private readonly List<string> history=new();
    protected override void SolveHawa(IGH_DataAccess da){
        bool run=false,pause=false,restore=false;int budget=10;double mutation=.15,fitness=0;string id="";
        da.GetData(3,ref run);da.GetData(4,ref pause);da.GetData(5,ref budget);da.GetData(6,ref mutation);da.GetData(7,ref restore);
        var sliders=Params.Input[0].Sources.OfType<GH_NumberSlider>().ToArray();
        if(sliders.Length==0 || sliders.Length!=Params.Input[0].Sources.Count)throw new ArgumentException("Connect gene sliders directly to Genes");
        if(budget<1 || !double.IsFinite(mutation)||mutation<=0||mutation>1)throw new ArgumentException("Budget >= 1; mutation > 0 and <= 1");
        if(first){first=false;requireOff=run;previousRun=run;}
        if(!run)requireOff=false;
        if(run&&!previousRun){count=0;best=double.PositiveInfinity;bestGenes=null;seen=null;history.Clear();}
        if(!run || pause){generation++;scheduled=false;}
        if(!run)pending=null;
        previousRun=run;
        if(restore&&!previousRestore&&!run&&bestGenes!=null){var values=(decimal[])bestGenes.Clone();Schedule(sliders,values);}
        previousRestore=restore;
        string state=!run?"stopped":requireOff?"enable again":pause?"paused":count>=budget?"completed":"waiting";
        if(run&&!requireOff&&!pause&&count<budget&&da.GetData(1,ref fitness)&&da.GetData(2,ref id)&&id!=seen){
            if(!double.IsFinite(fitness))throw new ArgumentException("Fitness must be finite");
            seen=id;count++;var genes=sliders.Select(s=>s.CurrentValue).ToArray();
            history.Add($"{count}: {fitness:g9}; genes {string.Join(", ",genes)}; candidate {id}");
            if(fitness<best){best=fitness;bestGenes=genes;}
            if(count<budget){
                var next=sliders.Select((s,i)=>Math.Clamp(bestGenes![i]+(decimal)((random.NextDouble()*2-1)*mutation)*(s.Slider.Maximum-s.Slider.Minimum),s.Slider.Minimum,s.Slider.Maximum)).ToArray();
                pending=next;state="next candidate";
            }else state="completed";
        }
        if(run&&!pause&&!requireOff&&pending!=null&&!scheduled)Schedule(sliders,pending,true);
        if(bestGenes!=null){da.SetData(0,best);da.SetDataList(1,bestGenes.Select(x=>(double)x));}
        da.SetDataList(2,history);da.SetData(3,$"{state}: {count}/{budget}");Message=state;
    }
    protected override void InputsMissing(){generation++;scheduled=false;pending=null;requireOff=true;}
    private void Schedule(GH_NumberSlider[] sliders,decimal[] values,bool candidate=false){
        var document=OnPingDocument();int expected=generation;scheduled=true;
        document?.ScheduleSolution(100,_=>{
            if(Locked||OnPingDocument()!=document||generation!=expected)return;
            scheduled=false;
            var old=sliders.Select(s=>s.CurrentValue).ToArray();
            for(int i=0;i<sliders.Length;i++)sliders[i].SetSliderValue(values[i]);
            if(candidate && sliders.Select(s=>s.CurrentValue).SequenceEqual(old)){
                // Rounding or a bound can erase a mutation. Move by one slider tick.
                for(int i=0;i<sliders.Length;i++){
                    decimal tick=(decimal)Math.Pow(10,-sliders[i].Slider.DecimalPlaces);
                    decimal next=old[i]+tick<=sliders[i].Slider.Maximum?old[i]+tick:old[i]-tick;
                    if(next>=sliders[i].Slider.Minimum&&next<=sliders[i].Slider.Maximum){sliders[i].SetSliderValue(next);break;}
                }
            }
            if(candidate){
                pending=null;
                // Distinct genes can share the same voxel mask. Force a fresh candidate ID.
                foreach(var source in Params.Input[1].Sources)
                    if(source.Attributes.GetTopLevel.DocObject is EvaluateComponent evaluation)evaluation.RequestCandidate();
                ExpireSolution(false);
            }
        });
    }
}
