using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Hawa.Grasshopper;
using Hawa.Shared;
using Rhino;

static class RefinementAdmissionContracts
{
    static JsonObject Coarse()=>JsonNode.Parse("""{"shape":[17,17,17],"dx":1.0,"spacing":1.0,"origin":[0.0,0.0,0.0]}""")!.AsObject();
    static JsonObject Fine()=>JsonNode.Parse("""{"shape":[13,13,13],"dx":0.5,"spacing":0.5,"origin":[5.0,5.0,5.0],"refinement_lower":[5,5,5],"refinement_upper":[11,11,11]}""")!.AsObject();
    static GhAccess Solve(RefinedSolveComponent c,bool run=true,bool pause=false,JsonObject? fine=null,int steps=2){var da=new GhAccess(c,new object?[]{new HawaGoo(Coarse()),new HawaGoo(fine??Fine()),steps,"cpu",run,pause});c.Compute(da);return da;}
    static GhAccess Complete(RefinedSolveComponent c,bool pause=false){for(int i=0;i<1000;i++){var da=Solve(c,true,pause);if(c.Message!="checking refinement")return da;Thread.Sleep(2);}throw new Exception("Submission timeout");}
    static JsonObject Status(string state)=>new(){["state"]=state,["steps"]=2,["target"]=2,["error"]="interface intersects solid",["result"]=new JsonObject{["coarse_frame"]=new JsonObject{["frame"]="coarse"},["fine_frame"]=new JsonObject{["frame"]="fine"},["report"]="experimental",["relative_mass_change"]=.001}};
    public static void Run(Action<string,Action> test,Action<bool,string> assert)
    {
        test("cold refinement rejects before background work and public Runtime establishes readiness",()=>{
            var wasReady=Hawa.Grasshopper.EmbeddedRuntime.IsReady;
            try{
                Hawa.Grasshopper.EmbeddedRuntime.IsReady=false;
                using var bridge=new GhBridge();bridge.Respond=r=>r["op"]!.GetValue<string>()=="info"?new JsonObject{["python"]="3.9"}:null;
                var c=new RefinedSolveComponent();Solve(c,false);Solve(c);
                assert(c.Errors.Single().Contains("Initialize Hawa Runtime first")&&!bridge.Calls.Any(),"Cold refinement entered bridge/worker");
                int hostThread=Environment.CurrentManagedThreadId;bool rejected=false;
                Task.Run(()=>{
                    RhinoApp.InvokeRequired=Environment.CurrentManagedThreadId!=hostThread;
                    assert(RhinoApp.InvokeRequired,"Guard probe did not run on worker");
                    try{Hawa.Grasshopper.EmbeddedRuntime.Call(new(){["op"]="info"});}catch(InvalidOperationException e){rejected=e.Message.Contains("on the host");}
                    finally{RhinoApp.InvokeRequired=false;}
                }).GetAwaiter().GetResult(); // Test process only; never host production code.
                assert(rejected&&!bridge.Calls.Any()&&!Hawa.Grasshopper.EmbeddedRuntime.IsReady,"Cold worker initialized host runtime");
                bridge.Respond=_=>throw new InvalidOperationException("setup failed");
                var runtime=new RuntimeComponent();runtime.Compute(new GhAccess(runtime,new object?[]{true}));
                assert(runtime.Errors.Single()=="setup failed"&&!Hawa.Grasshopper.EmbeddedRuntime.IsReady,"Failed setup marked ready");
                bridge.Respond=_=>new JsonObject{["python"]="3.9"};var report=new GhAccess(runtime,new object?[]{true});runtime.Compute(report);
                assert(Hawa.Grasshopper.EmbeddedRuntime.IsReady&&report.Out<string>(0).Contains("3.9"),"Public Runtime did not establish readiness");
                bridge.Respond=r=>r["op"]!.GetValue<string>() switch{"evaluate_submit"=>new JsonObject{["job"]="warmed"},"evaluate_poll"=>Status("completed"),_=>null};
                Complete(c);assert(c.Message=="completed"&&c.Errors.Count==0,"Cold rejection did not recover after explicit initialization");c.RemovedFromDocument(new GH_Document());
            }finally{RhinoApp.InvokeRequired=false;Hawa.Grasshopper.EmbeddedRuntime.IsReady=wasReady;}
        });
        test("refinement relationship admission rejects unsupported topology with fixed placement tolerance",()=>{
            RefinementAdmission.Require(Coarse(),Fine());
            void Reject(string key,JsonNode? value,string text){var f=Fine();f[key]=value;try{RefinementAdmission.Require(Coarse(),f);throw new Exception("Accepted "+key);}catch(ArgumentException e){assert(e.Message.Contains(text),e.Message);}}
            Reject("refinement_lower",null,"three");Reject("refinement_upper",new JsonArray(11,11),"three");
            Reject("refinement_lower",new JsonArray(5.5,5d,5d),"integer");Reject("refinement_upper",new JsonArray("11",11,11),"integer");
            foreach(int lo in new[]{0,12,16,18})Reject("refinement_lower",new JsonArray(lo,5,5),"clearance");
            Reject("refinement_upper",new JsonArray(15,11,11),"clearance");Reject("refinement_upper",new JsonArray(8,11,11),"clearance");
            Reject("shape",new JsonArray(12,13,13),"resolution");Reject("dx",JsonValue.Create(.6),"half");
            Reject("basis",JsonNode.Parse("[[1,0,0],[0,1,0],[0,0,1]]"),"axes");
            foreach(double shift in new[]{0d,1e6,-1e6})foreach(double offset in new[]{5e-8,2e-7}){
                var c=Coarse();var f=Fine();c["origin"]=new JsonArray(shift,shift,shift);f["origin"]=new JsonArray(shift+5+offset,shift+5,shift+5);
                if(offset<1e-7)RefinementAdmission.Require(c,f);else{bool failed=false;try{RefinementAdmission.Require(c,f);}catch(ArgumentException e){failed=e.Message.Contains("origin");}assert(failed,"Translation weakened origin bound");}
            }
            var coarse=Coarse();var fine=Fine();coarse["basis"]=JsonNode.Parse("[[0,1,0],[-1,0,0],[0,0,1]]");fine["basis"]=coarse["basis"]!.DeepClone();fine["origin"]=new JsonArray(-5d,5d,5d);RefinementAdmission.Require(coarse,fine);
            fine["basis"]=JsonNode.Parse("[[1,0,0],[0,1,0],[0,0,1]]");bool mismatch=false;try{RefinementAdmission.Require(coarse,fine);}catch(ArgumentException e){mismatch=e.Message.Contains("axes");}assert(mismatch,"Relative rotation accepted");
        });
        test("refined solve identifies invalid wired cases before bridge submission",()=>{
            using var bridge=new GhBridge();var c=new RefinedSolveComponent();
            assert(c.ComponentGuid==new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077138")&&c.Params.Input.Count==6&&c.Params.Output.Count==4,"Archive contract changed");
            Solve(c);assert(c.Message=="enable again"&&!bridge.Calls.Any(),"Saved true started work");Solve(c,false);
            var parent=new ProbeComponent{NickName="Parent flow"};c.Params.Input[0].Sources.Add(parent.Params.Output[0]);
            c.Params.Input[1].Sources.Add(new GH_TestParam("Local","Patch wire","",GH_ParamAccess.item,"generic",null));
            var fine=Fine();fine["origin"]=new JsonArray(6d,5d,5d);Solve(c,fine:fine);
            assert(c.Errors.Single().Contains(c.InstanceGuid.ToString())&&c.Errors.Single().Contains(parent.InstanceGuid.ToString())&&c.Errors.Single().Contains("Coarse case")&&c.Errors.Single().Contains("Patch wire"),"Missing host identity");
            assert(!bridge.Calls.Any(),"Invalid relationship initialized runtime");c.RemovedFromDocument(new GH_Document());
        });
        test("refined submission stays off solution thread and publishes completed frames",()=>{
            using var entered=new ManualResetEventSlim();using var release=new ManualResetEventSlim();using var bridge=new GhBridge();int ui=Environment.CurrentManagedThreadId;string state="running";
            bridge.Respond=r=>{if(r["op"]!.GetValue<string>()=="evaluate_submit"){assert(Environment.CurrentManagedThreadId!=ui,"Submission ran on solution thread");entered.Set();release.Wait();return new(){["job"]="refine-success"};}if(r["op"]!.GetValue<string>()=="evaluate_poll")return Status(state);return null;};
            var doc=new GH_Document();var c=new RefinedSolveComponent{Document=doc};global::Grasshopper.Instances.DocumentServer.Add(doc);Solve(c,false);Solve(c);assert(entered.Wait(2000)&&c.Message=="checking refinement","Submission did not return pending");
            RhinoApp.RaiseIdle();foreach(var timer in Eto.Forms.UITimer.Active.ToArray())timer.Pulse();assert(HawaPollScheduler.PendingCount==1,"Pending submission lost scheduled refresh");release.Set();var r=Complete(c,true);assert(c.Message=="running"&&r.Out<string>(2)=="running: 2/2","Running state missing");
            foreach(var timer in Eto.Forms.UITimer.Active.ToArray())timer.Pulse();assert(HawaPollScheduler.PendingCount==1,"Running job lost refresh");
            assert(bridge.Ops("evaluate_control").Last()["action"]!.GetValue<string>()=="pause","Pause not retained across admission");
            state="completed";r=Solve(c);assert(r.Out<HawaGoo>(0).Data["kind"]!.GetValue<string>()=="Frame"&&r.Out<HawaGoo>(1).Data["frame"]!.GetValue<string>()=="fine"&&r.Out<string>(3).Contains("0.001"),"Completed output contract changed");
            c.DocumentContextChanged(doc,GH_DocumentContext.Lock);Solve(c);assert(c.Message=="enable again","Lock did not require re-arm");Solve(c,false);c.RemovedFromDocument(doc);global::Grasshopper.Instances.DocumentServer.Remove(doc);
        });
        test("refined solve reports backend admission and worker failures with cleanup",()=>{
            using var bridge=new GhBridge();bridge.Respond=r=>{if(r["op"]!.GetValue<string>()=="evaluate_submit")throw new ArgumentException("Select BGK");return null;};var c=new RefinedSolveComponent();Solve(c,false);var r=Complete(c);assert(c.Errors.Single().Contains("Select BGK")&&c.Errors.Single().Contains("local input"),"Backend admission failure lost identity");
            bridge.Respond=r=>r["op"]!.GetValue<string>() switch{"evaluate_submit"=>new JsonObject{["job"]="failed-refine"},"evaluate_poll"=>Status("failed"),_=>null};r=Complete(c);assert(c.Errors.Single()=="interface intersects solid"&&bridge.Ops("evaluate_control").Last()["action"]!.GetValue<string>()=="close","Worker failure retained job");
            c.DocumentContextChanged(new GH_Document(),GH_DocumentContext.Loaded);c.RemovedFromDocument(new GH_Document());
        });
        test("removed or changed refinement input drains late success and observes late faults",()=>{
            for(int variant=0;variant<4;variant++){bool fail=variant==3;
                using var entered=new ManualResetEventSlim();using var release=new ManualResetEventSlim();using var done=new ManualResetEventSlim();using var bridge=new GhBridge();
                bridge.Respond=r=>{if(r["op"]!.GetValue<string>()=="evaluate_submit"){entered.Set();release.Wait();done.Set();if(fail)throw new ArgumentException("late admission rejection");return new(){["job"]="late-refine"};}return null;};
                var c=new RefinedSolveComponent();Solve(c,false);Solve(c);assert(entered.Wait(2000),"Submission not entered");
                if(variant==1||fail)c.RemovedFromDocument(new GH_Document());else if(variant==2)Solve(c,false);else{var invalid=Fine();invalid["dx"]=.8;Solve(c,fine:invalid);assert(c.Errors.Count==1,"Changed invalid input did not detach submission");}
                assert(RefinedSolveComponent.PendingSubmissions==1,"Detached submission has no process owner");foreach(var timer in Eto.Forms.UITimer.Active.ToArray())timer.Pulse();assert(!bridge.Ops("evaluate_control").Any(),"Pending submission prematurely closed");release.Set();assert(done.Wait(2000),"Release timed out");
                for(int i=0;i<1000&&Eto.Forms.UITimer.Active.Any();i++){Thread.Sleep(2);foreach(var timer in Eto.Forms.UITimer.Active.ToArray())timer.Pulse();}
                assert(!Eto.Forms.UITimer.Active.Any()&&RefinedSolveComponent.PendingSubmissions==0,"Pending cleanup retained timer/ownership");assert(bridge.Ops("evaluate_control").Count()==(fail?0:1),"Late successful job leaked or fault invented job");
            }
        });
    }
}
