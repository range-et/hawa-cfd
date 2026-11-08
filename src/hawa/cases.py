"""Identical, deterministic case definitions for upstream and compatibility runs."""

CASES = {
    "tgv2d-bgk": ("tgv2d", "bgk"),
    "tgv2d-trt": ("tgv2d", "trt"),
    "tgv2d-smagorinsky": ("tgv2d", "smagorinsky"),
    "tgv3d-bgk": ("tgv3d", "bgk"),
    "tgv3d-smagorinsky": ("tgv3d", "smagorinsky"),
    "cavity2d-bgk": ("cavity2d", "bgk"),
    "poiseuille2d-guo": ("poiseuille2d", "bgk"),
}


def make_case(name, context, size=None):
    import lettuce as lt

    flow_type, collision_type = CASES[name]
    n = size or (12 if flow_type == "tgv3d" else 32)
    common = dict(context=context, reynolds_number=10, mach_number=0.05)
    force = None
    if flow_type.startswith("tgv"):
        dimension = 3 if flow_type == "tgv3d" else 2
        flow = lt.TaylorGreenVortex(resolution=[n] * dimension, **common)
    elif flow_type == "cavity2d":
        flow = lt.Cavity2D(resolution=n, **common)
    elif flow_type == "poiseuille2d":
        common["reynolds_number"] = 1
        flow = lt.PoiseuilleFlow2D(resolution=n, initialize_with_zeros=True, **common)
        force = lt.Guo(flow, flow.units.relaxation_parameter_lu,
                       flow.units.convert_acceleration_to_lu(flow.acceleration))
    else:
        raise ValueError("Unknown flow: " + flow_type)
    tau = flow.units.relaxation_parameter_lu
    if collision_type == "trt":
        collision = lt.TRTCollision(tau)
    elif collision_type == "smagorinsky":
        collision = lt.SmagorinskyCollision(tau)
    else:
        collision = lt.BGKCollision(tau, force=force)
    return flow, lt.Simulation(flow=flow, collision=collision, reporter=[])
