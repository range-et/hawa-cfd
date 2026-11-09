"""In-process service shared by compiled Grasshopper components and headless tests.

No Rhino imports: geometry is passed as lattice solid indices and domain metadata.
The JSON interface never launches an external Python or CFD process.
"""

import hashlib
import json
import math
from pathlib import Path
import threading
import time
import uuid

import numpy as np
import torch
import lettuce as lt

from .backends import select_backend
from .cases import make_case


def canonical(spec):
    return json.dumps(spec, sort_keys=True, separators=(",", ":"), allow_nan=False)


def case_key(spec):
    return hashlib.sha256(canonical(spec).encode()).hexdigest()


def check_case(spec):
    if "example" in spec:
        if spec.get("moving_bodies"):raise ValueError("Moving bodies require a physical 3D case")
        from .cases import CASES,example_size
        n=example_size(spec['example'],spec.get('size'))
        dimension=3 if CASES[spec['example']][0]=='tgv3d' else 2
        estimated=n**dimension*(27 if dimension==3 else 9)*4*10/1024**2
        if estimated>float(spec.get('memory_limit_mb',1024)):
            raise ValueError('Example allocation exceeds the case memory budget')
        return {"valid": True, "case_hash": case_key(spec), "example": spec["example"],"estimated_peak_mb":estimated}
    shape = spec["shape"]
    if len(shape) != 3 or any(type(n) is not int or n < 4 for n in shape):
        raise ValueError("A 3D domain requires three integer resolutions >= 4")
    if math.prod(shape) > 2_000_000:
        raise ValueError("This release limits dense grids to two million cells")
    dx, speed, viscosity, density, mach = [float(spec.get(k, d)) for k, d in (
        ("dx", 0), ("speed", 1), ("viscosity", 1.5e-5), ("density", 1.225), ("mach", .05))]
    if any(not math.isfinite(x) or x <= 0 for x in (dx, speed, viscosity, density, mach)):
        raise ValueError("Cell size, inlet speed, viscosity, density and Mach must be finite and positive")
    if mach > .15:
        raise ValueError("Use lattice Mach <= 0.15 for this low-Mach solver")
    tau = .5 + 3 * viscosity * (mach / math.sqrt(3) * dx / speed) / dx ** 2
    if tau <= .500001:
        raise ValueError("Physical viscosity/resolution puts FP32 relaxation too close to 0.5; refine the grid or revise the physical case")
    if spec.get("collision", "regularized") not in ("bgk", "trt", "regularized", "smagorinsky"):
        raise ValueError("Wind collision must be bgk, trt, regularized or smagorinsky")
    allowed = {"inlet", "outlet", "wall", "slip", "periodic"}
    boundaries = spec.get("boundaries", ["inlet", "outlet", "periodic", "periodic", "wall", "slip"])
    if len(boundaries) != 6 or any(b not in allowed for b in boundaries):
        raise ValueError("Six face boundary types are required")
    if boundaries[:2] != ["inlet", "outlet"] or any(b in ("inlet", "outlet") for b in boundaries[2:]):
        raise ValueError("This release uses inlet at X- and outlet at X+; rotate the domain for another wind direction")
    for axis in range(3):
        pair = boundaries[2 * axis:2 * axis + 2]
        if ("periodic" in pair) and pair != ["periodic", "periodic"]:
            raise ValueError("Periodic boundaries must occur in opposite-face pairs")
    solid = spec.get("solid", [])
    if any(type(i) is not int or i < 0 or i >= math.prod(shape) for i in solid):
        raise ValueError("Solid indices are outside the lattice")
    if solid:
        ix = np.asarray(solid) // (shape[1] * shape[2])
        if np.any((ix == 0) | (ix == shape[0] - 1)):
            raise ValueError("Obstacles intersect the inlet or outlet; enlarge the domain")
    if spec.get("moving_bodies"):
        from .motion import validate_bodies
        validate_bodies(spec)
    estimated = math.prod(shape) * 19 * 4 * (24 if spec.get("moving_bodies") else 10)
    limit = int(spec.get("memory_limit_mb", 1024)) * 1024 ** 2
    if estimated > limit:
        raise ValueError("Estimated peak allocation {:.0f} MiB exceeds the case budget".format(estimated / 1024 ** 2))
    return {"valid": True, "case_hash": case_key(spec), "shape": shape, "tau": tau,
            "reynolds": speed * dx * max(shape) / viscosity,
            "estimated_peak_mb": estimated / 1024 ** 2,
            "time_step_seconds": mach / math.sqrt(3) * dx / speed}


class SlipBoundary(lt.Boundary):
    def __init__(self, flow, mask, axis):
        self.mask = mask
        velocities = np.asarray(flow.stencil.e)
        reflection = velocities.copy()
        reflection[:, axis] *= -1
        self.indices = [int(np.where(np.all(velocities == v, axis=1))[0][0]) for v in reflection]

    def __call__(self, flow):
        return flow.f[self.indices]

    def make_no_collision_mask(self, shape, context):
        return self.mask

    def make_no_streaming_mask(self, shape, context):
        return None

    def native_available(self):
        return False

    def native_generator(self, index):
        raise NotImplementedError("Use the portable tensor path")


class ExtrapolationOutlet(lt.Boundary):
    """Zero normal population gradient at X+. Requires an outgoing flow.

    Copy all populations from the adjacent post-collision fluid plane before
    streaming. This is an approximate outflow, not a nonreflecting boundary.
    """
    def __init__(self, flow):
        self.mask=flow.context.zero_tensor(flow.resolution,dtype=torch.bool)
        self.mask[-1]=True

    def __call__(self, flow):
        value=flow.f.clone()
        value[:,-1]=flow.f[:,-2]
        return value

    def make_no_collision_mask(self, shape, context):return self.mask
    def make_no_streaming_mask(self, shape, context):return None
    def native_available(self):return False
    def native_generator(self,index):raise NotImplementedError("Use the portable tensor path")


class WindFlow(lt.Flow):
    def __init__(self, context, spec):
        self.spec = spec
        shape = spec["shape"]
        dx, speed, viscosity = spec["dx"], spec["speed"], spec["viscosity"]
        length = dx * (shape[0] - 1)
        units = lt.UnitConversion(speed * length / viscosity, mach_number=spec.get("mach", .05),
                                  characteristic_length_pu=length, characteristic_velocity_pu=speed,
                                  characteristic_length_lu=shape[0] - 1,
                                  characteristic_density_pu=spec.get("density", 1.225))
        self.solid = context.zero_tensor(shape, dtype=torch.bool)
        indices = spec.get("solid", [])
        if indices:
            self.solid.view(-1)[torch.tensor(indices, device=context.device, dtype=torch.long)] = True
        super().__init__(context, shape, units, lt.D3Q19(), lt.QuadraticEquilibrium())

    def initial_pu(self):
        p = self.context.zero_tensor([1, *self.resolution])
        u = self.context.zero_tensor([3, *self.resolution])
        u[0] = self.spec["speed"] * (~self.solid)
        return p, u

    @property
    def grid(self):
        return torch.meshgrid(*(torch.arange(n, device=self.context.device, dtype=self.context.dtype)
                                * self.spec["dx"] for n in self.resolution), indexing="ij")

    @property
    def post_boundaries(self):
        types = self.spec.get("boundaries", ["inlet", "outlet", "periodic", "periodic", "wall", "slip"])
        result = []
        for face, kind in enumerate(types):
            if kind == "periodic":
                continue
            axis, side = face // 2, face % 2
            mask = self.context.zero_tensor(self.resolution, dtype=torch.bool)
            index = [slice(None)] * 3
            index[axis] = -1 if side else 0
            mask[tuple(index)] = True
            if kind == "inlet":
                result.append(lt.EquilibriumBoundaryPU(self.context, self, mask, [self.spec["speed"], 0, 0]))
            elif kind == "outlet":
                result.append(ExtrapolationOutlet(self))
            elif kind == "slip":
                result.append(SlipBoundary(self, mask, axis))
            else:
                result.append(lt.BounceBackBoundary(mask))
        result.append(lt.BounceBackBoundary(self.solid))
        return result


def make_solver(spec, device):
    check_case(spec)
    backend = select_backend(device)
    context = lt.Context(backend.device, torch.float32, use_native=False)
    if "example" in spec:
        flow, solver = make_case(spec["example"], context, spec.get("size"))
    else:
        flow = WindFlow(context, spec)
        model = {"bgk": lt.BGKCollision, "trt": lt.TRTCollision,
                 "regularized": lt.RegularizedCollision, "smagorinsky": lt.SmagorinskyCollision}[spec.get("collision", "regularized")]
        solver = lt.Simulation(flow, model(flow.units.relaxation_parameter_lu), [])
    if spec.get("wall_links"):
        from .walls import install_interpolated_walls
        install_interpolated_walls(solver, spec["wall_links"])
    if spec.get("moving_bodies"):
        from .moving_boundaries import MovingBoundaries
        solver.moving=MovingBoundaries(solver,spec)
    return backend, flow, solver


class Session:
    def __init__(self, spec, device):
        self.spec = json.loads(canonical(spec))
        self.key=case_key(self.spec)
        self.backend, self.flow, self.solver = make_solver(spec, device)
        self.id = str(uuid.uuid4())
        self.lock = threading.RLock()
        self.lifecycle = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.state = "ready"
        self.error = None
        self.target = 0
        self.initial_mass = float(self.flow.rho().sum().cpu())
        self.relative_mass_change = 0.0
        self.initial_f = self.flow.f.clone()
        self.mean_u = None
        self.samples = 0
        self.updated = time.time()

    @torch.no_grad()
    def advance(self, steps):
        if type(steps) is not int or steps < 0:
            raise ValueError("Steps must be a nonnegative integer")
        with self.lock:
            remaining = steps
            while remaining:
                n = min(remaining, 5 - self.flow.i % 5)
                self.solver(n)
                remaining -= n
                self.backend.synchronize()
                if not bool(torch.isfinite(self.flow.f).all().cpu()) or not bool((self.flow.rho() > 0).all().cpu()):
                    raise RuntimeError("Simulation became unstable; revise physics, grid or boundaries")
                if self.flow.i % 5 == 0 and not hasattr(self.solver,"moving"):
                    self.samples += 1
                    for name, value in (("mean_u", self.flow.u_pu), ("mean_p", self.flow.p_pu), ("mean_rho", self.flow.rho_pu)):
                        old = getattr(self, name, None)
                        if old is None:
                            setattr(self, name, value.detach().clone())
                        else:
                            old.add_((value.detach() - old) / self.samples)
                self.relative_mass_change = (float(self.flow.rho().sum().cpu()) - self.initial_mass) / self.initial_mass
                self.updated = time.time()

    def start(self, target):
        if type(target) is not int or target < 0:
            raise ValueError("Target steps must be a nonnegative integer")
        with self.lifecycle:
            if self.state == 'resetting':
                raise ValueError('Wait for reset to finish before resuming')
            self.target = target
            self.stop.clear()
            self.error = None
            self.state = "running"
            if self.thread is not None and self.thread.is_alive():
                return

            def work():
                try:
                    while True:
                        with self.lifecycle:
                            if self.stop.is_set() or self.flow.i >= self.target:
                                if self.state != "resetting":
                                    self.state = "completed" if self.flow.i >= self.target else "paused"
                                self.thread = None
                                return
                            count = min(5, self.target - self.flow.i)
                        self.advance(count)
                except Exception as exc:
                    with self.lifecycle:
                        self.error = str(exc)
                        self.state = "failed"
                        self.thread = None
            self.thread = threading.Thread(target=work, name="Hawa " + self.id[:8], daemon=True)
            self.thread.start()

    def pause(self):
        self.stop.set()
        worker = self.thread
        if worker is not None and worker.is_alive():
            worker.join(timeout=30)
            if worker.is_alive():
                raise RuntimeError("Solver has not yet reached a cancellation boundary")

    def status(self):
        # UI polling reads Python scalars. GPU reductions happen in the worker.
        return {"session": self.id, "state": self.state, "steps": self.flow.i,
                "target": self.target, "error": self.error, "backend": self.backend.info(),
                "case_hash": self.key, "resolution": self.flow.resolution,
                "physical_time": self.flow.units.convert_time_to_pu(self.flow.i),
                "relative_mass_change": self.relative_mass_change,
                "averaging_samples": self.samples, "updated": self.updated}

    def fields(self, mean=False, with_provenance=False):
        if mean and hasattr(self.solver,"moving"):raise ValueError("Moving fields require instantaneous snapshots; average body loads over cycles")
        with self.lock, torch.no_grad():
            u = self.mean_u if mean and self.mean_u is not None else self.flow.u_pu
            result = {"velocity": u.detach().cpu().numpy().copy(),
                    "pressure": (self.mean_p if mean and self.mean_u is not None else self.flow.p_pu)[0].detach().cpu().numpy().copy(),
                    "density": (self.mean_rho if mean and self.mean_u is not None else self.flow.rho_pu)[0].detach().cpu().numpy().copy()}
            if hasattr(self.flow, "solid"):
                result["solid"] = self.flow.solid.detach().cpu().numpy().copy()
            if with_provenance:
                result["snapshot"] = {"steps": int(self.flow.i), "session": self.id,
                                      "physical_time": float(self.flow.units.convert_time_to_pu(self.flow.i))}
            return result


SESSIONS = {}
REGISTRY_LOCK = threading.Lock()


def sample_arrays(fields, points):
    """Trilinear interpolation of component-first velocity and scalar fields."""
    shape = np.array(fields["pressure"].shape)
    results = []
    for point in points:
        point = np.asarray(point, dtype=float)[:len(shape)]
        if len(point) != len(shape) or not np.isfinite(point).all() or np.any(point < 0) or np.any(point > shape - 1):
            results.append(None)
            continue
        lo = np.floor(point).astype(int)
        hi = np.minimum(lo + 1, shape - 1)
        if "solid" in fields and fields["solid"][tuple(np.rint(point).astype(int))]:
            results.append(None)
            continue
        weight = point - lo
        v, p, rho = np.zeros(len(shape)), 0.0, 0.0
        valid = True
        for corner in np.ndindex(*([2] * len(shape))):
            index = tuple(hi[a] if corner[a] else lo[a] for a in range(len(shape)))
            w = math.prod(weight[a] if corner[a] else 1 - weight[a] for a in range(len(shape)))
            if w > 1e-12 and "solid" in fields and fields["solid"][index]:
                valid = False
                break
            v += w * fields["velocity"][(slice(None), *index)]
            p += w * float(fields["pressure"][index])
            rho += w * float(fields["density"][index])
        if not valid:
            results.append(None)
            continue
        results.append({"velocity": list(v) + [0.0] * (3 - len(v)), "pressure": p, "density": rho,
                        "speed": float(np.linalg.norm(v))})
    return results


def dispatch(request):
    op = request["op"]
    if op == "recording":
        from .recording import load_frame, pathlines
        if request["action"] == "load":
            return load_frame(request["manifest"], request["index"])
        if request["action"] == "particles":
            return pathlines(request["manifest"], request["seeds"], request.get("last"))
        raise ValueError("Recording action must be load or particles")
    if op == "field":
        from .fields import dispatch_field
        return dispatch_field(request, SESSIONS[request["session"]] if request.get("session") else None)
    if op == "airfoil":
        from .airfoils import dispatch_airfoil
        return dispatch_airfoil(request)
    if op.startswith("evaluate_"):
        from .jobs import dispatch_job
        return dispatch_job(request)
    if op == "info":
        import os, sys
        return {"python": sys.version, "numpy": np.__version__, "torch": torch.__version__,
                "pid": os.getpid(), "engine": lt.__version__,
                "mps": torch.backends.mps.is_available(), "cuda": torch.cuda.is_available()}
    if op == "check":
        return check_case(request["case"])
    if op == "evaluate":
        from .optimization import evaluate
        session = Session(request["case"], request.get("device", "auto"))
        result = evaluate(session, request.get("steps", 200), request.get("window", 20),
                          float(request["reference_volume"]))
        with REGISTRY_LOCK:
            SESSIONS[session.id] = session
        result["status"] = session.status()
        return result
    if op == "create":
        session = Session(request["case"], request.get("device", "auto"))
        with REGISTRY_LOCK:
            SESSIONS[session.id] = session
        return session.status()
    if op == "close_async" and request["session"] not in SESSIONS:
        return {"closed": True}
    session = SESSIONS[request["session"]]
    if op in ("pause_async", "close_async", "reset_async"):
        session.stop.set()
        session.state = "resetting" if op == "reset_async" else ("pausing" if session.thread is not None and session.thread.is_alive() else "paused")
        if op != "pause_async":
            def finish():
                try:
                    dispatch({"op": "close" if op == "close_async" else "reset", "session": session.id})
                except Exception as exc:
                    session.error = str(exc)
                    session.state = "failed"
            threading.Thread(target=finish, name="Hawa control", daemon=True).start()
        return session.status()
    if op == "start":
        session.start(request["steps"])
        return session.status()
    if op == "pause":
        session.pause()
        return session.status()
    if op == "step":
        session.pause()
        session.advance(int(request["steps"]))
        return session.status()
    if op == "reset":
        session.pause()
        with session.lock:
            session.flow.f.copy_(session.initial_f)
            session.flow.i = 0
            if hasattr(session.solver,"moving"):session.solver.moving.reset()
            session.samples = 0
            session.relative_mass_change = 0.0
            session.mean_u = session.mean_p = session.mean_rho = None
            session.state = "ready"
            session.error = None
        return session.status()
    if op == "close":
        session.pause()
        with REGISTRY_LOCK:
            del SESSIONS[session.id]
        return {"closed": True}
    if op == "body_loads":
        with session.lock:
            if not hasattr(session.solver,"moving"):raise ValueError("This session has no moving bodies")
            moving=session.solver.moving
            return {**moving.metadata(),"history":list(moving.history),"case":session.spec,"time":session.flow.units.convert_time_to_pu(session.flow.i)}
    if op == "status":
        return session.status()
    if op == "sample":
        if len(request["points"]) > 10000:
            raise ValueError("Limit each sampling request to 10000 points")
        return {"values": sample_arrays(session.fields(request.get("mean", False)), request["points"])}
    if op == "slice":
        axis = int(request.get("axis", 2))
        fields = session.fields(request.get("mean", False), with_provenance=True)
        shape = fields["pressure"].shape
        if len(shape) == 2:
            axis = 2
            index = 0
            coordinates = list(np.ndindex(shape))
        else:
            if axis not in (0, 1, 2):
                raise ValueError("Slice axis must be 0, 1 or 2")
            index = int(request.get("index", shape[axis] // 2))
            if index < 0 or index >= shape[axis]:
                raise ValueError("Slice index outside domain")
            remaining = [a for a in range(3) if a != axis]
            coordinates = []
            for ij in np.ndindex(*(shape[a] for a in remaining)):
                p = [0, 0, 0]
                p[axis] = index
                for a, i in zip(remaining, ij):
                    p[a] = i
                coordinates.append(tuple(p))
        values = sample_arrays(fields, coordinates)
        name = request.get("field", "speed")
        if name not in ("speed", "pressure", "density"):
            raise ValueError("Slice field must be speed, pressure or density")
        dimensions = list(shape) if len(shape) == 2 else [shape[a] for a in range(3) if a != axis]
        return {"shape": dimensions, "coordinates": [list(p) + [0] * (3 - len(p)) for p in coordinates],
                "values": [p[name] if p else 0.0 for p in values],
                "valid": [p is not None for p in values], "field": name,
                "steps": fields["snapshot"]["steps"], "session": fields["snapshot"]["session"],
                "physical_time": fields["snapshot"]["physical_time"]}
    if op == "streamlines":
        fields = session.fields(request.get("mean", False))
        paths = []
        for seed in request["seeds"][:200]:
            p = np.asarray(seed, dtype=float)
            points = [p.tolist()]
            for _ in range(min(1000, max(1, int(request.get("steps", 100))))):
                value = sample_arrays(fields, [p])[0]
                if value is None or value["speed"] < 1e-12:
                    break
                delta = np.asarray(value["velocity"]) / value["speed"] * .4
                midpoint = sample_arrays(fields, [p + delta / 2])[0]
                if midpoint is None or midpoint["speed"] < 1e-12:
                    break
                p += np.asarray(midpoint["velocity"]) / midpoint["speed"] * .4
                if sample_arrays(fields, [p])[0] is None:
                    break
                points.append(p.tolist())
            paths.append(points)
        return {"paths": paths}
    if op == "save":
        session.pause()
        path = Path(request["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with session.lock, path.open("wb") as out:
            np.savez_compressed(out, populations=session.flow.f.detach().cpu().numpy(),
                                iteration=np.array(session.flow.i), spec=np.array(canonical(session.spec)),
                                motion_history=np.array(json.dumps(list(session.solver.moving.history) if hasattr(session.solver,"moving") else [])),
                                transition_mass=np.array(session.solver.moving.transition_mass if hasattr(session.solver,"moving") else 0.))
        return {"path": str(path)}
    if op == "load":
        session.pause()
        with np.load(request["path"], allow_pickle=False) as data:
            populations=data['populations']
            iteration=data['iteration']
            if str(data["spec"]) != canonical(session.spec) or populations.shape != tuple(session.flow.f.shape):
                raise ValueError("Checkpoint belongs to a different case")
            if not np.isfinite(populations).all():
                raise ValueError("Checkpoint contains nonfinite populations")
            if iteration.shape!=() or iteration.dtype.kind not in 'iu' or int(iteration)<0:
                raise ValueError('Checkpoint iteration must be a nonnegative integer')
            density=populations.sum(axis=0)
            if not np.isfinite(density).all() or np.any(density<=0):
                raise ValueError('Checkpoint density must be finite and positive')
            with session.lock:
                session.flow.f.copy_(session.flow.context.convert_to_tensor(populations))
                session.flow.i = int(iteration)
                if hasattr(session.solver,"moving"):
                    session.solver.moving.reset(int(iteration))
                    if "motion_history" in data:session.solver.moving.history.extend(json.loads(str(data["motion_history"])))
                    if "transition_mass" in data:session.solver.moving.transition_mass=float(data["transition_mass"])
                session.mean_u = session.mean_p = session.mean_rho = None
                session.samples = 0
                session.relative_mass_change=(float(density.sum())-session.initial_mass)/session.initial_mass
                session.error=None
                session.updated=time.time()
                session.state = "paused"
        return session.status()
    if op == "export":
        path = Path(request["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as out:
            np.savez_compressed(out, **session.fields())
        return {"path": str(path)}
    raise ValueError("Unknown Hawa operation: " + op)


def dispatch_json(text):
    try:
        return json.dumps({"ok": True, "result": dispatch(json.loads(text))}, allow_nan=False)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc), "type": type(exc).__name__})
