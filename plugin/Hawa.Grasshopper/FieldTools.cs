using System.Drawing;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Rhino.Geometry;

namespace Hawa.Grasshopper;

// Shared frame handling for the field views. Linked in full into the
// StateContracts host (tests/dotnet/StateContracts/ComponentContracts.cs).
internal static class FieldTools {
    private static HawaGoo? Unwrap(IGH_Goo input)=>input is HawaGoo value?value:(input as GH_ObjectWrapper)?.Value as HawaGoo;
    internal static JsonObject Frames(IGH_DataAccess da,int index){
        var inputs=new List<IGH_Goo>();da.GetDataList(index,inputs);
        var frames=new List<JsonObject>();
        foreach(var input in inputs.Where(v=>
            v!=null
        )){
            var h=Unwrap(input);
            if(h==null)throw new ArgumentException("Connect Field Snapshot or Playback frames");
            var f=h.Data;if(f["frame"]==null||f["case"]==null)throw new ArgumentException("Connect immutable field frames");frames.Add(f);
        }
        if(frames.Count<1||frames.Count>16)throw new ArgumentException("Use 1..16 field frames");
        var result=frames[0].DeepClone().AsObject();
        if(frames.Count>1)result["frames"]=new JsonArray(frames.Select(f=>
            f["frame"]!.DeepClone()
        ).ToArray());
        return result;
    }
    // A composed view names a wired child that delivered nothing (cancelled, failed
    // or still running) and frames wired twice, instead of dropping them silently (#74).
    internal static void ReportSources(GH_Component owner,IGH_Param input){
        var sources=new List<(string Name,bool Empty)>();
        foreach(var source in input.Sources)sources.Add((source.Attributes?.GetTopLevel?.DocObject?.NickName??source.NickName,!source.VolatileData.AllData(true).Any()));
        var missing=Hawa.Shared.LifecycleText.Missing(sources);
        if(missing!=null)owner.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,missing);
        var frames=new List<string>();
        foreach(var item in input.VolatileData.AllData(true))if(Unwrap(item)?.Data["frame"] is JsonNode frame)frames.Add(frame.ToJsonString());
        var duplicates=Hawa.Shared.LifecycleText.Duplicates(frames);
        if(duplicates!=null)owner.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning,duplicates);
    }
    internal static JsonObject Request(JsonObject frame,string action,string field="speed")=>new(){["op"]="field",["action"]=action,["frame"]=frame["frame"]!.DeepClone(),["frames"]=frame["frames"]?.DeepClone()??(action=="plane"&&frame["case"]?["shape"]?.AsArray().Count==3?new JsonArray(frame["frame"]!.DeepClone()):null),["field"]=field};
    internal static JsonObject World(JsonObject frame)=>new(){["case"]=frame["case"]!.DeepClone()};
    internal static Color ColorAt(double t,string palette){t=Math.Clamp(t,0,1);Color[] colors=palette.ToLowerInvariant() switch{"spectrum"=>new[]{Color.DarkBlue,Color.Cyan,Color.Lime,Color.Yellow,Color.Red},"diverging"=>new[]{Color.RoyalBlue,Color.White,Color.Firebrick},_=>new[]{Color.FromArgb(8,48,107),Color.FromArgb(0,160,180),Color.FromArgb(150,235,140)}};double u=t*(colors.Length-1);int i=Math.Min(colors.Length-2,(int)u);double f=u-i;return Color.FromArgb((int)(colors[i].R*(1-f)+colors[i+1].R*f),(int)(colors[i].G*(1-f)+colors[i+1].G*f),(int)(colors[i].B*(1-f)+colors[i+1].B*f));}
    internal static Mesh Mesh(JsonObject data,JsonObject frame){var m=new Mesh();foreach(var p in data["vertices"]!.AsArray())m.Vertices.Add(Coordinates.World(World(frame),p!));foreach(var f in data["faces"]!.AsArray())m.Faces.AddFace(f![0]!.GetValue<int>(),f[1]!.GetValue<int>(),f[2]!.GetValue<int>());m.Normals.ComputeNormals();return m;}
}
