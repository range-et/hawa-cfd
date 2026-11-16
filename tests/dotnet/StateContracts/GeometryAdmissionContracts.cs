using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Hawa.Grasshopper;
using Hawa.Shared;
using Hawa.Native;
using Rhino;
using Rhino.Geometry;

static class GeometryAdmissionContracts
{
    static JsonObject Domain()=>new(){["kind"]="Domain",["shape"]=new JsonArray(5,5,5),["spacing"]=1d,["dx"]=1d,["origin"]=new JsonArray(0d,0d,0d)};
    static HawaGoo Goo(JsonObject data)=>new(data);
    static GhAccess Solve(GH_Component c,params object?[] inputs){var da=new GhAccess(c,inputs);c.Compute(da);return da;}
    static GhAccess Complete(GH_Component c,params object?[] inputs)
    {
        for(int i=0;i<1000;i++){var da=Solve(c,inputs);if(da.Outputs.Count>0||c.Errors.Count>0||c.Message=="cancelled")return da;Thread.Sleep(2);}
        throw new Exception("Geometry test timed out: "+c.Message);
    }
    public static void Run(Action<string,Action> test,Action<bool,string> assert)
    {
        void Reject(JsonObject domain,string text){bool rejected=false;try{GeometryDomain.Require(domain);}catch(ArgumentException e){rejected=e.Message.Contains(text);}assert(rejected,"Domain rejection missing: "+text);}
        test("domain structural admission rejects malformed payloads before geometry allocation",()=>{
            GeometryDomain.Require(Domain());
            var d=Domain();d.Remove("shape");Reject(d,"three lattice");d=Domain();d["shape"]=new JsonArray(4,4);Reject(d,"three lattice");
            foreach(var shape in new[]{new JsonArray(3,4,4),new JsonArray(4,"4",4),new JsonArray(4,null,4),new JsonArray(2000001,4,4),new JsonArray(200,200,200)}){d=Domain();d["shape"]=shape;Reject(d,"cells");}
            foreach(var key in new[]{"spacing","dx"})foreach(var value in new JsonNode?[]{null,JsonValue.Create("x"),JsonValue.Create(0d),JsonValue.Create(double.NaN)}){d=Domain();d[key]=value?.DeepClone();Reject(d,"positive");}
            foreach(var origin in new JsonNode?[]{null,new JsonArray(0,0),new JsonArray(0d,double.NaN,0d),new JsonArray(0d,"x",0d)}){d=Domain();d["origin"]=origin;Reject(d,"coordinates");}
            foreach(var basis in new JsonNode?[]{JsonValue.Create(1),new JsonArray(),new JsonArray(new JsonArray(1,0),new JsonArray(0,1,0),new JsonArray(0,0,1)),new JsonArray(new JsonArray(1d,0d,double.NaN),new JsonArray(0d,1d,0d),new JsonArray(0d,0d,1d)),new JsonArray(new JsonArray(2d,0d,0d),new JsonArray(0d,1d,0d),new JsonArray(0d,0d,1d)),new JsonArray(new JsonArray(1d,0d,0d),new JsonArray(1d,0d,0d),new JsonArray(0d,0d,1d))}){d=Domain();d["basis"]=basis;Reject(d,"basis");}
            d=Domain();d["basis"]=new JsonArray(new JsonArray(0d,1d,0d),new JsonArray(-1d,0d,0d),new JsonArray(0d,0d,1d));GeometryDomain.Require(d);
        });
        test("GH Geometry rejects invalid obstacles and retains valid union/halo outputs",()=>{
            var c=new GeometryComponent();assert(c.ComponentGuid==new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077102")&&c.Params.Input.Count==4,"Geometry archive identity changed");
            var bad=ObstacleContracts.Box();bad.Faces.RemoveAt(0);var result=Complete(c,Goo(Domain()),new[]{bad},false,Array.Empty<Brep>());assert(c.Errors.Count==1&&c.Errors[0].Contains("Obstacle 1: 4 naked"),"Invalid obstacle reached voxelizer");
            var valid=ObstacleContracts.Box(1,1,1);var outside=ObstacleContracts.Box(20,20,20);
            result=Complete(c,Goo(Domain()),new[]{valid,ObstacleContracts.Box(2,1,1),outside},false,Array.Empty<Brep>());
            assert(c.Errors.Count==0&&result.Out<int>(1)==12,"Separate touching union solid set incorrect");
            var data=result.Out<HawaGoo>(0).Data;assert(data["ignored_outside_bodies"]!.GetValue<int>()==1&&c.RuntimeMessages.Any(p=>p.Item2.Contains("wholly outside")),"Disjoint body incorrectly invalidated cropped input");
            result=Complete(c,Goo(Domain()),new[]{ObstacleContracts.Box(-.5,1,1)},false,Array.Empty<Brep>());assert(c.Errors.Count==0&&result.Out<int>(1)==4,"Closed cropped body was refused");
            var unresolved=ObstacleContracts.Box(.1,.1,.1,.1);result=Complete(c,Goo(Domain()),new[]{unresolved},false,Array.Empty<Brep>());assert(c.Errors.Single().Contains("no solid or halo"),"Unrepresented body accepted");
            int queries=0;var tooClose=ObstacleContracts.Box(1,1,1);tooClose.Closest=(p,t)=>{queries++;return new MeshPoint(p);};result=Complete(c,Goo(Domain()),new[]{tooClose},true,Array.Empty<Brep>());assert(c.Errors.Single().Contains("clearance")&&queries==0,"Curved clearance rejected after voxelization");
            var invalid=Domain();invalid["spacing"]=0d;int before=Mesh.Created.Count;result=Solve(c,Goo(invalid),new[]{valid},false,Array.Empty<Brep>());assert(c.Errors.Single().Contains("spacing")&&Mesh.Created.Count==before,"Invalid domain duplicated/voxelized meshes");
            result=Solve(c,Goo(Domain()),Array.Empty<Mesh>(),false,new[]{new Brep{IsSolid=false}});assert(c.Errors.Single().Contains("Brep"),"Open Brep accepted");
            Mesh.Factory=(_,_)=>new[]{ObstacleContracts.Box(1,1,1)};result=Complete(c,Goo(Domain()),Array.Empty<Mesh>(),false,new[]{new Brep()});assert(result.Out<int>(1)==8,"Valid meshed solid not voxelized");Mesh.Factory=(_,_)=>Array.Empty<Mesh>();
            c.Params.Input[1].Sources.Add(new ProbeComponent().Params.Output[0]);result=Solve(c,Goo(Domain()),Array.Empty<Mesh>(),false,Array.Empty<Brep>());assert(c.Message=="waiting for geometry","Pending upstream became empty obstacles");
            c.RemovedFromDocument(new GH_Document());
        });
        test("Moving Body applies obstacle admission before SDF sampling and preserves body identity",()=>{
            var c=new MovingBodyComponent();assert(c.ComponentGuid==new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077142"),"Moving body GUID changed");
            var motion=Goo(new(){["axis"]=new JsonArray(1d,0d,0d),["type"]="translation",["speed"]=1d});
            var bad=ObstacleContracts.Box();bad.Faces.RemoveAt(0);var r=Complete(c,Goo(Domain()),bad,motion,Point3d.Origin,"fin");assert(c.Errors.Single().Contains("Moving body fin: 4 naked"),"Invalid moving body sampled");
            var good=ObstacleContracts.Box(1,1,1);r=Complete(c,Goo(Domain()),good,motion,new Point3d(1,1,1),"fin");assert(c.Errors.Count==0,"Valid body failed: "+string.Join(";",c.Errors));
            var body=r.Out<HawaGoo>(0).Data;assert(body["id"]!.GetValue<string>()=="fin"&&body["pivot"]!.ToJsonString()=="[1,1,1]"&&body["geometry"]!["values"]!.AsArray().Count==343,"SDF/body metadata wrong");
            var values=body["geometry"]!["values"]!.AsArray().Select(v=>v!.GetValue<double>()).ToArray();assert(values.Any(v=>v<0)&&values.Any(v=>v>0),"SDF lost inside/outside signs");
            r=Solve(c,Goo(Domain()),good,motion,new Point3d(double.NaN,0,0),"fin");assert(c.Errors.Single().Contains("pivot"),"Invalid pivot accepted");
            r=Complete(c,Goo(Domain()),ObstacleContracts.Box(size:100),motion,Point3d.Origin,"large");assert(c.Errors.Single().Contains("200000"),"SDF budget ignored");
            c.RemovedFromDocument(new GH_Document());
        });
        test("native preparation rejects topology, missing objects and clearance before voxelization",()=>{
            var doc=new RhinoDoc(8300);var id=Guid.NewGuid();var source=ObstacleContracts.Box(3,3,3);doc.Objects.Items[id]=new(source);
            var c=new CaseState{Document=8300,Cell=1};c.SetupData["mode"]="selected";c.SetupData["size"]=new JsonArray(8d,8d,8d);c.SetupData["objects"]=new JsonArray(id.ToString());
            JsonObject Prepare()=>NativeGeometry.Prepare(c,CancellationToken.None).GetAwaiter().GetResult();
            void Fail(string text){bool rejected=false;try{Prepare();}catch(ArgumentException e){rejected=e.Message.Contains(text);}assert(rejected,"Native preflight missing: "+text);}
            var result=Prepare();assert(result["solid"]!.AsArray().Count==8&&!source.Disposed,"Native solid count/disposal wrong");
            c.SetupData["curved_walls"]=true;result=Prepare();assert(result["wall_links"]!.AsArray().Count>0,"Native curved walls missing");c.SetupData["curved_walls"]=false;
            doc.Objects.Items[id]=new(new Brep());Mesh.Factory=(_,_)=>new[]{ObstacleContracts.Box(3,3,3)};assert(Prepare()["solid"]!.AsArray().Count==8,"Brep path wrong");Mesh.Factory=(_,_)=>Array.Empty<Mesh>();
            var invalid=ObstacleContracts.Box(3,3,3);invalid.Faces.RemoveAt(0);doc.Objects.Items[id]=new(invalid);Fail(id+": 4 naked");
            doc.Objects.Items[id]=new(ObstacleContracts.Box(0,0,0));Fail("two cells");
            doc.Objects.Items[id]=new(ObstacleContracts.Box(3.1,3.1,3.1,.1));Fail("no solid cells");
            doc.Objects.Items[id]=new(source);c.SetupData["objects"]=new JsonArray(id.ToString(),Guid.NewGuid().ToString());int before=Mesh.Created.Count;Fail("missing");assert(Mesh.Created.Skip(before).All(m=>m.Disposed),"Failed capture leaked duplicates");
            c.SetupData["objects"]=new JsonArray();Fail("Select closed");
            c.SetupData["objects"]=new JsonArray(id.ToString());using var token=new CancellationTokenSource();token.Cancel();before=Mesh.Created.Count;bool cancelled=false;try{NativeGeometry.Prepare(c,token.Token).GetAwaiter().GetResult();}catch(OperationCanceledException){cancelled=true;}assert(cancelled&&Mesh.Created.Skip(before).All(m=>m.Disposed),"Cancelled preparation leaked capture");
        });
        test("native case budget check precedes geometry preparation",()=>{
            var doc=new RhinoDoc(8301);var c=CaseHub.Get(8301);c.SetupData["mode"]="selected";c.SetupData["objects"]=new JsonArray(Guid.NewGuid().ToString());
            var old=CaseHub.Transport;var prepare=CaseHub.PrepareGeometry;var calls=new List<string>();
            try{CaseHub.Transport=r=>{calls.Add(r["op"]!.GetValue<string>());throw new ArgumentException("budget rejected");};CaseHub.PrepareGeometry=(c,t)=>{calls.Add("voxelize");return Task.FromResult(CaseHub.BuildSpec(c));};CaseHub.Run(8301);assert(calls.SequenceEqual(new[]{"check"})&&c.State=="failed"&&c.Error.Contains("budget rejected"),"Budget rejection allocated geometry");}
            finally{CaseHub.Transport=old;CaseHub.PrepareGeometry=prepare;CaseHub.Close(8301);}
        });
        test("geometry workers retain polling, propagate cancellation and release on removal",()=>{
            var doc=new GH_Document();global::Grasshopper.Instances.DocumentServer.Clear();foreach(var t in Eto.Forms.UITimer.Active.ToArray())t.Pulse();global::Grasshopper.Instances.DocumentServer.Add(doc);
            var mesh=ObstacleContracts.Box(1,1,1);var c=new GeometryComponent{Document=doc};c.Params.Input[1].Sources.Add(new ProbeComponent().Params.Output[0]);
            var curvedDomain=Domain();curvedDomain["shape"]=new JsonArray(9,9,9);
            var r=Complete(c,Goo(curvedDomain),new[]{ObstacleContracts.Box(3,3,3)},true,Array.Empty<Brep>());assert(c.Errors.Count==0&&r.Out<HawaGoo>(0).Data["wall_links"]!.AsArray().Count>0,"GH curved wall output missing: "+string.Join(";",c.Errors));
            assert(Math.Abs(GeometryComponent.LinkFraction(mesh,new Point3d(0,1.5,1.5),new Vector3d(2,0,0))-.5)<1e-10,"Link wrapper changed fraction");
            using var entered=new ManualResetEventSlim();using var release=new ManualResetEventSlim();var held=ObstacleContracts.Box(1,1,1);held.Closest=(p,t)=>{entered.Set();release.Wait();return new MeshPoint(p);};
            Solve(c,Goo(Domain()),new[]{held},false,Array.Empty<Brep>());assert(entered.Wait(2000),"Geometry did not enter worker");foreach(var t in Eto.Forms.UITimer.Active.ToArray())t.Pulse();assert(HawaPollScheduler.PendingCount>0,"Geometry poll not retained");release.Set();Complete(c,Goo(Domain()),new[]{held},false,Array.Empty<Brep>());
            var cancelled=ObstacleContracts.Box(1,1,1);cancelled.Closest=(p,t)=>throw new OperationCanceledException();r=Complete(c,Goo(Domain()),new[]{cancelled},false,Array.Empty<Brep>());assert(c.Errors.Single().Contains("canceled")&&r.Outputs.Count==0,"Cancelled geometry published output: "+c.Message+"/"+string.Join(";",c.Errors)+"/"+r.Outputs.Count);c.RemovedFromDocument(doc);
            var motion=Goo(new(){["axis"]=new JsonArray(1d,0d,0d)});var body=new MovingBodyComponent{Document=doc};using var bodyEntered=new ManualResetEventSlim();using var bodyRelease=new ManualResetEventSlim();var heldBody=ObstacleContracts.Box(1,1,1);heldBody.Nearest=p=>{bodyEntered.Set();bodyRelease.Wait();return p;};
            Solve(body,Goo(Domain()),heldBody,motion,Point3d.Origin,"held");assert(bodyEntered.Wait(2000),"Body did not enter worker");foreach(var t in Eto.Forms.UITimer.Active.ToArray())t.Pulse();bodyRelease.Set();Complete(body,Goo(Domain()),heldBody,motion,Point3d.Origin,"held");
            var cancelledBody=ObstacleContracts.Box();cancelledBody.Nearest=p=>throw new OperationCanceledException();Solve(body,Goo(Domain()),cancelledBody,motion,Point3d.Origin,"cancelled");Thread.Sleep(30);r=Solve(body,Goo(Domain()),cancelledBody,motion,Point3d.Origin,"cancelled");assert(r.Outputs.Count==0&&body.Errors.Single().Contains("canceled"),"Cancelled body published/error");body.RemovedFromDocument(doc);
            var check=new GeometryCheckComponent{Document=doc};using var checkEntered=new ManualResetEventSlim();using var checkRelease=new ManualResetEventSlim();var heldCheck=ObstacleContracts.Box();heldCheck.NakedProvider=()=>{checkEntered.Set();checkRelease.Wait();return null;};Solve(check,new[]{heldCheck},1d);assert(checkEntered.Wait(2000),"Checker did not enter worker");foreach(var t in Eto.Forms.UITimer.Active.ToArray())t.Pulse();checkRelease.Set();Complete(check,new[]{heldCheck},1d);
            var cancelledCheck=ObstacleContracts.Box();cancelledCheck.NakedProvider=()=>throw new OperationCanceledException();r=Complete(check,new[]{cancelledCheck},1d);assert(check.Errors.Single().Contains("canceled")&&r.Outputs.Count==0,"Cancelled check published output");
            var failedCheck=ObstacleContracts.Box();failedCheck.NakedProvider=()=>throw new InvalidOperationException("kernel query failed");Complete(check,new[]{failedCheck},1d);assert(check.Errors.Single()=="kernel query failed","Kernel exception swallowed");check.RemovedFromDocument(doc);global::Grasshopper.Instances.DocumentServer.Clear();foreach(var t in Eto.Forms.UITimer.Active.ToArray())t.Pulse();
        });
        test("removed/replaced geometry workers dispose captures and cannot publish stale outputs",()=>{
            var doc=new GH_Document();global::Grasshopper.Instances.DocumentServer.Add(doc);
            Task Worker(GH_Component c)=>(Task)c.GetType().GetField("task",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic)!.GetValue(c)!;
            void Finish(Task t){try{t.GetAwaiter().GetResult();}catch(OperationCanceledException){}}
            using var entered=new ManualResetEventSlim();using var release=new ManualResetEventSlim();var source=ObstacleContracts.Box(1,1,1);source.Closest=(p,t)=>{entered.Set();release.Wait();return new MeshPoint(p);};var c=new GeometryComponent{Document=doc};int before=Mesh.Created.Count;Solve(c,Goo(Domain()),new[]{source},false,Array.Empty<Brep>());assert(entered.Wait(2000),"Old geometry not running");var old=Worker(c);var owned=Mesh.Created.Skip(before).ToArray();
            var replacement=Complete(c,Goo(Domain()),new[]{ObstacleContracts.Box(2,2,2)},false,Array.Empty<Brep>());assert(replacement.Out<int>(1)==8,"Replacement failed");release.Set();Finish(old);assert(owned.All(m=>m.Disposed)&&!source.Disposed,"Replaced job leaked or disposed caller mesh");var current=Complete(c,Goo(Domain()),new[]{ObstacleContracts.Box(2,2,2)},false,Array.Empty<Brep>());assert(current.Out<int>(1)==8,"Stale geometry overwrote replacement");c.RemovedFromDocument(doc);
            using var bodyEntered=new ManualResetEventSlim();using var bodyRelease=new ManualResetEventSlim();var bodySource=ObstacleContracts.Box();bodySource.Nearest=p=>{bodyEntered.Set();bodyRelease.Wait();return p;};var body=new MovingBodyComponent{Document=doc};var motion=Goo(new(){["axis"]=new JsonArray(1d,0d,0d)});before=Mesh.Created.Count;Solve(body,Goo(Domain()),bodySource,motion,Point3d.Origin,"removed");assert(bodyEntered.Wait(2000),"Body not running");old=Worker(body);owned=Mesh.Created.Skip(before).ToArray();body.RemovedFromDocument(doc);bodyRelease.Set();Finish(old);assert(owned.All(m=>m.Disposed)&&!bodySource.Disposed,"Removed body leaked capture");
            using var checkEntered=new ManualResetEventSlim();using var checkRelease=new ManualResetEventSlim();var checkSource=ObstacleContracts.Box();checkSource.NakedProvider=()=>{checkEntered.Set();checkRelease.Wait();return null;};var check=new GeometryCheckComponent{Document=doc};before=Mesh.Created.Count;Solve(check,new[]{checkSource},1d);assert(checkEntered.Wait(2000),"Check not running");old=Worker(check);owned=Mesh.Created.Skip(before).ToArray();check.RemovedFromDocument(doc);checkRelease.Set();Finish(old);assert(owned.All(m=>m.Disposed)&&!checkSource.Disposed,"Removed checker leaked capture");global::Grasshopper.Instances.DocumentServer.Clear();foreach(var timer in Eto.Forms.UITimer.Active.ToArray())timer.Pulse();
        });
        test("Geometry Check reports the same obstacle rejection and preserves display metadata",()=>{
            var c=new GeometryCheckComponent();assert(c.ComponentGuid==new Guid("a7bb3b0a-ae4f-42ae-9301-a3c55f077134"),"Check GUID changed");
            var good=ObstacleContracts.Box();var bad=ObstacleContracts.Box();bad.Faces.RemoveAt(0);bad.NakedEdges=new[]{new[]{new Point3d(0,0,0),new Point3d(1,0,0)}};
            var duplicate=Solve(c,new[]{good},new GhMany(1d,2d));assert(c.Errors.Single().Contains("one value per item input")&&duplicate.Outputs.Count==0,"Background Geometry Check accepted multiple spacing values");
            var r=Complete(c,new[]{good,bad},1d);assert(r.List(0).Cast<bool>().SequenceEqual(new[]{true,false}),"Checker disagrees with obstacle admission");
            assert(r.List(2).Cast<string>().ElementAt(1).Contains("Obstacle 2: 4 naked")&&r.List(2).Cast<string>().ElementAt(0).Contains("Coplanar")&&r.List(1).Count==1,"Checker lost defect, edge or unsupported limit");
            r=Solve(c,new[]{good},0d);assert(c.Errors.Single().Contains("Spacing"),"Nonpositive spacing accepted");c.RemovedFromDocument(new GH_Document());
        });
    }
}
