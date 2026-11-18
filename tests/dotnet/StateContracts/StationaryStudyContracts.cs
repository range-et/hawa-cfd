using System.Text.Json.Nodes;
using Eto.Forms;
using Grasshopper.Kernel;
using Hawa.Grasshopper;
using Hawa.Shared;
using Rhino.Geometry;

static class StationaryStudyContracts
{
    public static void Run(Action<string, Action> test, Action<bool, string> assert)
    {
        var doc = new GH_Document();
        void Reset() { global::Grasshopper.Instances.DocumentServer.Clear(); foreach(var t in UITimer.Active.ToArray()) t.Pulse(); global::Grasshopper.Instances.DocumentServer.Add(doc); }
        Mesh Tetra() { var m = new Mesh(); foreach(var p in new[]{new Point3d(1000,2000,3000),new Point3d(1100,2000,3000),new Point3d(1000,2100,3000),new Point3d(1000,2000,3100)})m.Vertices.Add(p);m.Faces.AddFace(0,2,1);m.Faces.AddFace(0,1,3);m.Faces.AddFace(0,3,2);m.Faces.AddFace(1,2,3);return m; }
        HawaGoo Case()=>new(JsonNode.Parse("""{"kind":"Case","label":"test","shape":[12,12,12],"dx":0.5,"spacing":500.0,"origin":[1000.0,2000.0,3000.0],"collision":"bgk","solid":[],"speed":1.0,"density":1.0,"viscosity":0.01}""")!.AsObject());
        object?[] Inputs(bool run=false)=>new object?[]{Case(),Tetra(),new[]{-3d,3d},new[]{1d,2d},2d,1d,new Point3d(1000,2000,3000),new[]{new Point3d(1100,2100,3100)},3000,201,.05,0,run,false,false};
        GhAccess Solve(StationaryStudyComponent c, object?[] input){var da=new GhAccess(c,input);c.Compute(da);return da;}
        StationaryStudyComponent Start(GhBridge bridge,object?[]? input=null){var c=new StationaryStudyComponent{Document=doc};input??=Inputs();Solve(c,input);input[12]=true;Solve(c,input);return c;}
        JsonObject? request=null; string state="running", job="j"; Action<JsonObject>? corrupt=null;
        JsonObject Identity(JsonNode candidate)=>new(){["case_id"]=request!["case_id"]!.DeepClone(),["generation"]=request["generation"]!.DeepClone(),["revision"]=0,["candidate_id"]=candidate["candidate_id"]!.DeepClone(),["case_hash"]=candidate["case_hash"]!.DeepClone(),["geometry_hash"]=candidate["geometry_hash"]!.DeepClone()};
        JsonObject Reply(JsonObject r)
        {
            if(r["op"]!.GetValue<string>()=="evaluate_submit"){request=r.DeepClone().AsObject();return new(){["job"]=job};}
            if(r["op"]!.GetValue<string>()!="evaluate_poll")return new(){["closed"]=true};
            var rows=new JsonArray();var points=request!["operating_points"]!.AsArray();
            for(int i=0;i<points.Count;i++){
                var candidate=new JsonObject{["candidate_id"]="study-"+i.ToString("D3"),["case_hash"]="case-"+i,["geometry_hash"]="mesh-"+i,["angle_deg"]=points[i]!["angle_deg"]!.DeepClone(),["speed_m_s"]=points[i]!["speed_m_s"]!.DeepClone()};
                rows.Add(new JsonObject{["candidate"]=candidate,["state"]=i==1?"rejected":"completed",["reason"]=i==1?"stationarity":"",["generation"]=request["generation"]!.DeepClone(),["CM"]=state=="completed"&&i!=1?JsonValue.Create(.3+i):null,
                    ["result"]=new JsonObject{["identity"]=Identity(candidate),["coefficients"]=new JsonObject{["CL"]=(double)i+.1,["CD"]=(double)i+.2}}});
            }
            int selected=r["selected_candidate"]!.GetValue<int>();var candidateSelected=rows[selected]!["candidate"]!;
            var stamp=new JsonObject{["steps"]=9,["physical_time"]=.5,["session"]="session-"+selected,["phase"]="pre-reflection"};
            var detail=new JsonObject{["candidate"]=candidateSelected.DeepClone(),["identity"]=Identity(candidateSelected),["session"]="session-"+selected,["phase"]="pre-reflection",["geometry"]=request["geometry"]!.DeepClone(),
                ["summary"]=new JsonObject{["identity"]=Identity(candidateSelected),["usable"]=true,["bodies"]=new JsonArray(new JsonObject{["body_id"]="body",["usable"]=true,["force_mean_world_n"]=new JsonArray(2d,3d,4d),["torque_mean_world_nm"]=new JsonArray(5d,6d,7d),["mean"]=new JsonObject{["CL"]=selected+.1,["CD"]=selected+.2,["Cm"]=selected+.3}})},
                ["frame"]=new JsonObject{["frame"]="frame-"+selected,["iteration"]=9,["time"]=.5,["identity"]=Identity(candidateSelected),["session"]="session-"+selected,["phase"]="pre-reflection",["snapshot"]=stamp,["case"]=request["case"]!.DeepClone()}};
            var data=new JsonObject{["records"]=rows,["selected"]=detail};
            var status=new JsonObject{["job"]=job,["state"]=state,["steps"]=2,["target"]=points.Count,["error"]="backend failure",["result"]=state=="completed"?data:null,["progress"]=state=="completed"?null:data};
            corrupt?.Invoke(status);return status;
        }

        test("stationary study ports, saved true guard, explicit CPU and SI request",()=>{
            Reset();using var bridge=new GhBridge{Respond=Reply};state="running";corrupt=null;
            var c=new StationaryStudyComponent{Document=doc};var input=Inputs(true);Solve(c,input);
            assert(c.ComponentGuid==new Guid("4823e5ad-f4fb-4b62-96e3-127989a184b5")&&c.Params.Input.Count==15&&c.Params.Output.Count==14&&c.Params.Input[7].Optional,"Public ports drifted");
            assert(!bridge.Ops("evaluate_submit").Any()&&c.Message=="set Run off/on","Saved true started a worker");
            input[12]=false;Solve(c,input);input[12]=true;var output=Solve(c,input);
            var sent=bridge.Ops("evaluate_submit").Single();
            assert(sent["kind"]!.GetValue<string>()=="stationary_study"&&sent["device"]!.GetValue<string>()=="cpu","Wrong backend");
            assert(sent["case"]!["spacing"]!.GetValue<double>()==.5&&sent["case"]!["origin"]!.ToJsonString()=="[1,2,3]"&&sent["case"]!["kind"]==null,"Case not normalized to SI");
            assert(sent["geometry"]!["vertices_m"]![0]!.ToJsonString()=="[1,2,3]"&&sent["pivot_world_m"]!.ToJsonString()=="[1,2,3]"&&sent["probes"]![0]!["position_world_m"]!.ToJsonString()=="[1.1,2.1,3.1]","Mesh/pivot/probes units differ");
            assert(sent["operating_points"]!.ToJsonString()=="[{\"angle_deg\":-3,\"speed_m_s\":1},{\"angle_deg\":-3,\"speed_m_s\":2},{\"angle_deg\":3,\"speed_m_s\":1},{\"angle_deg\":3,\"speed_m_s\":2}]","Crossproduct order wrong");
            assert(output.List(4).Count==4&&output.List(4)[1]==null&&output.List(6).All(v=>v==null)&&!output.Outputs.ContainsKey(0)&&HawaPollScheduler.PendingCount==1,"Running outputs invented selected capture");
            foreach(var timer in UITimer.Active.ToArray())timer.Pulse();
            c.RemovedFromDocument(doc);assert(HawaPollScheduler.PendingCount==0,"Removal retained poll");Reset();
        });
        test("stationary study preserves double precision for translated mesh submission",()=>{
            Reset();using var bridge=new GhBridge{Respond=Reply};state="running";corrupt=null;
            var input=Inputs();var mesh=(Mesh)input[1]!;
            var expected=new[]{new Point3d(1e9,1e9,1e9),new Point3d(1e9+.25,1e9,1e9),new Point3d(1e9,1e9+.25,1e9),new Point3d(1e9,1e9,1e9+.25)};
            for(int i=0;i<expected.Length;i++)mesh.Vertices[i]=expected[i];
            mesh.Vertices.Add(expected[0]);mesh.Faces[0]=new MeshFace(4,2,1);
            mesh.Vertices.FloatIndex=true;
            assert(mesh.Vertices[0]==mesh.Vertices[1],"Fixture does not expose float precision loss");
            var c=Start(bridge,input);var sent=bridge.Ops("evaluate_submit").Single()["geometry"]!["vertices_m"]!.AsArray();
            assert(c.Errors.Count==0&&sent.Count==4,"Translated mesh was rejected or collapsed");
            for(int i=0;i<expected.Length;i++){
                var p=expected[i];var coords=new[]{p.X*.001,p.Y*.001,p.Z*.001};
                for(int axis=0;axis<3;axis++)assert(sent[i]![axis]!.GetValue<double>()==coords[axis],"Translated mesh lost double precision before SI conversion");
                assert(mesh.Vertices.Point3dAt(i)==p,"Submission mutated the original mesh");
            }
            assert(request!["geometry"]!["triangles"]!.ToJsonString()=="[[0,2,1],[0,1,3],[0,3,2],[1,2,3]]"&&mesh.Vertices.Count==5&&mesh.Faces[0].A==4,"Exact seam remap changed winding or original topology");
            c.RemovedFromDocument(doc);Reset();
        });
        test("stationary mesh serializer triangulates quads and rejects invalid coordinates and face counts",()=>{
            var method=typeof(StationaryStudyComponent).GetMethod("SerializeMesh",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static)!;
            JsonObject Serialize(Mesh mesh)=>(JsonObject)method.Invoke(null,new object[]{mesh,.001})!;
            using var cube=new Mesh();
            foreach(var p in new[]{new Point3d(0,0,0),new Point3d(1,0,0),new Point3d(1,1,0),new Point3d(0,1,0),new Point3d(0,0,1),new Point3d(1,0,1),new Point3d(1,1,1),new Point3d(0,1,1)})cube.Vertices.Add(p);
            foreach(var f in new[]{new[]{0,3,2,1},new[]{4,5,6,7},new[]{0,1,5,4},new[]{1,2,6,5},new[]{2,3,7,6},new[]{3,0,4,7}})cube.Faces.AddFace(f[0],f[1],f[2],f[3]);
            var result=Serialize(cube);
            assert(result["vertices_m"]!.AsArray().Count==8&&result["triangles"]!.ToJsonString()=="[[0,3,2],[0,2,1],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]]"&&cube.Faces.Count==6,"Quad triangulation changed winding, order or source");
            foreach(bool badCoordinate in new[]{true,false}){
                using var mesh=Tetra();if(badCoordinate)mesh.Vertices[0]=new Point3d(double.NaN,0,0);else mesh.Faces.RemoveAt(0);
                bool rejected=false;try{Serialize(mesh);}catch(System.Reflection.TargetInvocationException e){rejected=e.InnerException is ArgumentException;}
                assert(rejected,"Invalid mesh serializer input was accepted");
            }
        });
        test("stationary study queued startup retains the job and polls through preparation",()=>{
            Reset();using var bridge=new GhBridge{Respond=Reply};state="queued";
            corrupt=status=>{status["progress"]=null;status["steps"]=0;status["error"]=null;};
            var input=Inputs();var c=Start(bridge,input);
            foreach(var phase in new[]{"queued","preparing"}){
                state=phase;var output=Solve(c,input);
                assert(c.Errors.Count==0&&c.Message==phase,"Valid startup state was treated as a failure");
                assert(HawaPollScheduler.PendingCount==1&&bridge.Ops("evaluate_submit").Count()==1,"Startup lost its poll or resubmitted the job");
                assert(!bridge.Ops("evaluate_control").Any(r=>r["action"]!.GetValue<string>()=="close"),"Startup closed the queued worker");
                assert(!output.Outputs.ContainsKey(0)&&!output.Outputs.ContainsKey(2)&&output.List(4).Count==4&&output.List(4).All(v=>v==null),"Pending startup invented field, loads or coefficients");
            }
            state="running";corrupt=null;Solve(c,input);
            assert(c.Errors.Count==0&&c.Message=="running"&&bridge.Ops("evaluate_submit").Count()==1&&HawaPollScheduler.PendingCount==1,"Prepared worker did not continue under its original ownership");
            input[12]=false;Solve(c,input);
            assert(bridge.Ops("evaluate_control").Count(r=>r["action"]!.GetValue<string>()=="close")==1&&HawaPollScheduler.PendingCount==0,"Explicit stop did not release the original startup job exactly once");Reset();
        });
        test("stationary study selected field mesh loads and nullable coefficient slots share identity",()=>{
            Reset();using var bridge=new GhBridge{Respond=Reply};state="completed";corrupt=null;var input=Inputs();var c=Start(bridge,input);var output=Solve(c,input);
            assert(output.List(4).Select(v=>v?.ToString()).SequenceEqual(new[]{"0.1",null,"2.1","3.1"})&&output.List(6).Select(v=>v?.ToString()).SequenceEqual(new[]{"0.3",null,"2.3","3.3"}),"Rejected coefficient slots compressed or CM absent");
            assert(output.Out<Vector3d>(2)==new Vector3d(2,3,4)&&output.Out<Vector3d>(3)==new Vector3d(5,6,7)&&output.Out<double>(12)==4&&output.Out<double>(13)==2,"Mean force/moment projections changed");
            var frame=output.Out<HawaGoo>(0).Data;assert(frame["case"]!["origin"]!.ToJsonString()=="[1000,2000,3000]"&&frame["case"]!["spacing"]!.GetValue<double>()==500&&frame["case"]!["dx"]!.GetValue<double>()==.5,"Frame display units incorrect");
            var world=new JsonObject{["case"]=frame["case"]!.DeepClone()};
            assert(Coordinates.World(world,JsonNode.Parse("[0,0,0]")!)==output.Out<Mesh>(1).Vertices[0]&&Coordinates.Grid(world,new Point3d(1100,2100,3100)).ToJsonString()=="[0.2,0.2,0.2]","mm field/mesh/probe mapping inconsistent");
            assert(frame["identity"]!["case_hash"]!.GetValue<string>()=="case-0"&&output.Out<string>(9).Contains("pre-reflection"),"Physical identity lost in display descriptor");
            int submits=bridge.Ops("evaluate_submit").Count();input[11]=2;output=Solve(c,input);assert(bridge.Ops("evaluate_submit").Count()==submits&&output.Out<HawaGoo>(0).Data["frame"]!.GetValue<string>()=="frame-2","Selection restarted study or retained old field");
            input[11]=1;output=Solve(c,input);assert(!output.Outputs.ContainsKey(0)&&!output.Outputs.ContainsKey(2)&&output.List(7)[1]!.ToString()!.Contains("rejected"),"Rejected selected case published usable loads");
            input[12]=false;output=Solve(c,input);assert(output.Outputs.Count==0&&bridge.Ops("evaluate_control").Any(r=>r["action"]!.GetValue<string>()=="close"),"Run false did not release retained frames");Reset();
        });
        test("stationary study edits missing inputs cancel document transitions and require explicit rearm",()=>{
            Reset();using var bridge=new GhBridge{Respond=Reply};state="running";corrupt=null;var input=Inputs();var c=Start(bridge,input);
            input[13]=true;Solve(c,input);assert(bridge.Ops("evaluate_control").Last()["action"]!.GetValue<string>()=="pause","Pause not cooperative");
            input[4]=3d;var output=Solve(c,input);assert(output.Outputs.Count==0&&c.Message!.StartsWith("inputs changed"),"Input edit published stale result");
            int count=bridge.Ops("evaluate_submit").Count();Solve(c,input);assert(bridge.Ops("evaluate_submit").Count()==count,"Edited running input restarted silently");
            input[12]=false;Solve(c,input);input[12]=true;Solve(c,input);assert(bridge.Ops("evaluate_submit").Count()==count+1,"Off/on did not rearm");
            input[14]=true;Solve(c,input);assert(c.Message!.StartsWith("cancelled")&&HawaPollScheduler.PendingCount==0,"Cancel did not clear pending views");
            input[14]=false;Solve(c,input);assert(bridge.Ops("evaluate_submit").Count()==count+1,"Cancel restarted while Run remained true");
            foreach(var context in new[]{GH_DocumentContext.Close,GH_DocumentContext.Lock,GH_DocumentContext.Unloaded}){
                input[12]=false;Solve(c,input);input[12]=true;Solve(c,input);int before=bridge.Ops("evaluate_submit").Count();c.DocumentContextChanged(doc,context);Solve(c,input);assert(bridge.Ops("evaluate_submit").Count()==before&&HawaPollScheduler.PendingCount==0,"Document context revived study");}
            input[12]=false;Solve(c,input);input[12]=true;Solve(c,input);input[1]=null;output=Solve(c,input);assert(output.Outputs.Count==0&&HawaPollScheduler.PendingCount==0,"Missing mesh retained owned resources");Reset();
        });
        test("stationary study errors and malformed identities withhold complete selected output",()=>{
            foreach(string failure in new[]{"job","failed","cancelled","count","order","caseid","generation","hash","frame","session","phase","number","triple","unknown","missingrecords","cm","stamp","coefficients","missinghash","summaryid","summaryusable","bodies","bodyid","bodyusable","snapshot-time","triangles","indices","overflow"}){
                Reset();using var bridge=new GhBridge{Respond=Reply};state="completed";corrupt=s=>{
                    var data=s["result"]!;var row=data["records"]![0]!;var selected=data["selected"]!;
                    if(failure=="job")s["job"]="other";if(failure=="failed")s["state"]="failed";if(failure=="cancelled")s["state"]="cancelled";
                    if(failure=="count")data["records"]!.AsArray().RemoveAt(3);if(failure=="order")row["candidate"]!["angle_deg"]=9d;
                    if(failure=="caseid")row["result"]!["identity"]!["case_id"]="other";if(failure=="generation")selected["identity"]!["generation"]=99;
                    if(failure=="hash")selected["frame"]!["identity"]!["case_hash"]="wrong";if(failure=="frame")selected["frame"]=null;
                    if(failure=="session")selected["frame"]!["session"]="other";if(failure=="phase")selected["frame"]!["phase"]="other";
                    if(failure=="unknown")s["state"]="wrong";if(failure=="missingrecords")data["records"]=null;
                    if(failure=="cm")row["CM"]=null;if(failure=="stamp")selected["frame"]!["snapshot"]!["steps"]=8;
                    if(failure=="coefficients")selected["summary"]!["bodies"]![0]!["mean"]!["CL"]=99d;
                    if(failure=="missinghash")row["candidate"]!["case_hash"]=null;
                    if(failure=="summaryid")selected["summary"]!["identity"]!["case_id"]="other";
                    if(failure=="summaryusable")selected["summary"]!["usable"]=false;if(failure=="bodies")selected["summary"]!["bodies"]!.AsArray().Add(new JsonObject());
                    if(failure=="bodyid")selected["summary"]!["bodies"]![0]!["body_id"]="other";if(failure=="bodyusable")selected["summary"]!["bodies"]![0]!["usable"]=false;
                    if(failure=="snapshot-time")selected["frame"]!["snapshot"]!["physical_time"]=.6;
                    if(failure=="triangles")selected["geometry"]!["triangles"]![0]=new JsonArray(0,1);
                    if(failure=="indices")selected["geometry"]!["triangles"]![0]=new JsonArray(0,1,99);
                    if(failure=="overflow")selected["geometry"]!["vertices_m"]![0]=new JsonArray(1d,0d,0d);
                    if(failure=="number")row["result"]!["coefficients"]!["CL"]=null;if(failure=="triple")selected["summary"]!["bodies"]![0]!["force_mean_world_n"]=new JsonArray(1d,2d);
                };
                var input=Inputs();if(failure=="overflow"){var small=((HawaGoo)input[0]!).Data;small["dx"]=1e-309;small["spacing"]=1d;input[0]=new HawaGoo(small);}
                var c=new StationaryStudyComponent{Document=doc};Solve(c,input);input[12]=true;var output=Solve(c,input);
                assert(output.Outputs.Count==0&&HawaPollScheduler.PendingCount==0,failure+" published stale/partial output");
                if(failure is "triangles" or "indices" or "overflow")assert(Mesh.Created.Last().Disposed,"Malformed result leaked provisional mesh");
                assert(failure=="cancelled"?c.Message!.StartsWith("cancelled"):c.Errors.Count==1,failure+" did not report failure");Reset();
            }corrupt=null;
        });
        test("stationary study bounds input values before submission and preserves source mesh",()=>{
            Reset();using var bridge=new GhBridge{Respond=Reply};state="running";corrupt=null;
            foreach(int index in new[]{0,1,2,3,4,5,6,8,9,10,11}){
                var input=Inputs();var c=new StationaryStudyComponent{Document=doc};Solve(c,input);input[12]=true;
                input[index]=index switch{0=>new HawaGoo(new JsonObject{["dx"]=0d,["spacing"]=1d}),1=>new Mesh{IsClosed=false},2=>new[]{double.NaN},3=>new[]{0d},4 or 5=>-1d,6=>new Point3d(double.NaN,0,0),8=>-1,9=>3,10=>-1d,11=>99,_=>null};
                var output=Solve(c,input);assert(c.Errors.Count==1&&output.Outputs.Count==0,"Bad input "+index+" accepted");
            }
            assert(!bridge.Ops("evaluate_submit").Any(),"Invalid input allocated background work");
            var valid=Inputs();var original=(Mesh)valid[1]!;original.Vertices.Add(original.Vertices[0]);original.Faces[0]=new MeshFace(4,2,1);int vertices=original.Vertices.Count;
            var study=Start(bridge,valid);assert(request!["geometry"]!["vertices_m"]!.AsArray().Count==4&&original.Vertices.Count==vertices&&original.Faces[0].A==4&&!original.Disposed,"Normalization mutated source mesh or left seams");
            study.RemovedFromDocument(doc);Reset();
        });
        test("stationary study participates in background multiplicity guard and failed cleanup retry",()=>{
            Reset();using var bridge=new GhBridge{Respond=Reply};state="running";corrupt=null;var input=Inputs();var c=Start(bridge,input);
            input[0]=new GhMany(Case(),Case());var output=Solve(c,input);assert(c.Errors.Single().StartsWith("Use one value per item input")&&output.Outputs.Count==0,"Background item multiplicity ignored");
            input=Inputs();c=Start(bridge,input);bool fail=true;bridge.Respond=r=>r["op"]!.GetValue<string>()=="evaluate_control"&&r["action"]!.GetValue<string>()=="close"&&fail?throw new Exception("lost reply"):Reply(r);
            c.RemovedFromDocument(doc);assert(CaseHub.PendingCleanupCount>0,"Lost cleanup reply discarded ownership");fail=false;CaseHub.RetryCleanup();assert(CaseHub.PendingCleanupCount==0&&HawaPollScheduler.PendingCount==0,"Cleanup retry failed");Reset();
        });
    }
}
