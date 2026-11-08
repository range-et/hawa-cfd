"""Run with Rhino 8 Python 3 using runpy.run_path; see README.md."""

from pathlib import Path
import json
import platform
import sys

# Set by compile/runpy, or override HAWA_ROOT when pasting into ScriptEditor.
ROOT = Path(HAWA_ROOT) if "HAWA_ROOT" in globals() else Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / ".runtime" / "rhino-py39"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from hawa.backends import select_backend
from hawa.lbm import VortexConfig, VortexSimulation

import Rhino
import System.Drawing as Drawing

DEVICE = globals().get("HAWA_DEVICE", "mps")
SIZE = globals().get("HAWA_SIZE", 64)
STEPS = globals().get("HAWA_STEPS", 200)
sim = VortexSimulation(select_backend(DEVICE), VortexConfig(size=SIZE))
sim.advance(STEPS)
report = sim.diagnostics()
report.update({"python": sys.version, "architecture": platform.machine(),
               "host": "rhino-embedded", "rhino": str(Rhino.RhinoApp.Version)})
output = ROOT / "results" / ("rhino-" + str(sim.backend.device).replace(":", "-"))
output.mkdir(parents=True, exist_ok=True)
(output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
if not report["passed"]:
    raise RuntimeError("LBM verification failed; see report.json")

def create_preview():
    # The offset keeps this lattice-units illustration clear of existing geometry.
    origin = globals().get("HAWA_ORIGIN", (100.0, 0.0, 0.0))
    doc = globals().get("__rhino_doc__") or Rhino.RhinoDoc.ActiveDoc
    if doc is None:
        raise RuntimeError("No Rhino document available for preview")
    snapshot = sim.snapshot()
    u = snapshot["velocity"]
    mesh = Rhino.Geometry.Mesh()
    max_speed = report["max_speed_lattice"]
    for y in range(SIZE):
        for x in range(SIZE):
            magnitude = float((u[0, y, x] ** 2 + u[1, y, x] ** 2) ** 0.5)
            t = magnitude / max(max_speed, 1e-12)
            mesh.Vertices.Add(origin[0] + x, origin[1] + y, origin[2])
            mesh.VertexColors.Add(Drawing.Color.FromArgb(int(255 * t), int(100 * (1 - t)), int(255 * (1 - t))))
    for y in range(SIZE - 1):
        for x in range(SIZE - 1):
            a = y * SIZE + x
            mesh.Faces.AddFace(a, a + 1, a + SIZE + 1, a + SIZE)
    mesh.Normals.ComputeNormals()
    layer = Rhino.DocObjects.Layer()
    layer.Name = "Hawa Feasibility"
    layer_index = doc.Layers.FindByFullPath(layer.Name, -1)
    if layer_index < 0:
        layer_index = doc.Layers.Add(layer)
    attrs = Rhino.DocObjects.ObjectAttributes()
    attrs.LayerIndex = layer_index
    attrs.Name = "Hawa Taylor-Green {} steps {}".format(DEVICE, STEPS)
    attrs.SetUserString("hawa.demo", "taylor-green")
    # Replace only Hawa-owned demo objects. Never clear the document or layer.
    owned = [obj.Id for obj in doc.Objects if obj.Attributes.GetUserString("hawa.demo") == "taylor-green"]
    for object_id in owned:
        doc.Objects.Delete(object_id, True)
    object_ids = [str(doc.Objects.AddMesh(mesh, attrs))]
    stride = max(1, SIZE // 8)
    for y in range(stride // 2, SIZE, stride):
        for x in range(stride // 2, SIZE, stride):
            start = Rhino.Geometry.Point3d(origin[0] + x, origin[1] + y, origin[2] + 0.1)
            end = start + Rhino.Geometry.Vector3d(float(u[0, y, x]) * 100,
                                                  float(u[1, y, x]) * 100, 0)
            object_ids.append(str(doc.Objects.AddLine(start, end, attrs)))
    doc.Views.Redraw()
    report["preview_object_ids"] = object_ids
    report["preview_origin"] = origin
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Hawa preview created: {} objects on Hawa Feasibility".format(len(object_ids)))


if globals().get("HAWA_PREVIEW", True):
    create_preview()
