using System.Text.Json.Nodes;
using Hawa.Shared;
using Rhino;
using Rhino.Geometry;
using Rhino.Input.Custom;
using Rhino.DocObjects;
namespace Hawa.Native;

public static partial class NativeGeometry
{
    public static void Pick(uint serial) {
        var doc = RhinoDoc.FromRuntimeSerialNumber(serial) ?? throw new InvalidOperationException("Document closed");
        if (RhinoDoc.ActiveDoc != doc) throw new InvalidOperationException("Activate this Rhino document before selecting objects");
        using var pick = new GetObject(); pick.SetCommandPrompt("Select closed meshes or solid surfaces for Hawa");
        pick.GeometryFilter = ObjectType.Mesh | ObjectType.Brep; pick.SubObjectSelect = false;
        pick.GetMultiple(1, 100);
        if (pick.CommandResult() != Rhino.Commands.Result.Success) return;
        SelectObjects(serial, Enumerable.Range(0, pick.ObjectCount).Select(i => pick.Object(i).ObjectId), true);
    }
}
