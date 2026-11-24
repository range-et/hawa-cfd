"""Physical-case handoff, OpenFOAM v2606 generation, and shared-probe verification (#126, #127).

The bundle schema represents an SI physical case independently of solver grids.
OpenFOAM receives its own validated volume mesh while preserving identical physical
domain bounds, fluid properties, boundary intent, and world-space probe locations.
Agreement between Hawa and OpenFOAM is cross-solver verification, not experimental
validation.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
from typing import Annotated, Dict, List, Literal, Optional

import numpy as np
from pydantic import ConfigDict, Field, StrictFloat, StrictInt, StrictStr, model_validator

from .boundary_contracts import FACES, conditions as validate_boundary_conditions
from .motion import Payload, Positive, Vector, check

SCHEMA = "hawa-openfoam-case-1"
ADAPTER_VERSION = "0.1.0"
Identifier = Annotated[StrictStr, Field(min_length=1)]
GridCount = Annotated[StrictInt, Field(ge=1, le=2000)]
PositiveVector = Annotated[List[Positive], Field(min_length=3, max_length=3)]
CellCounts = Annotated[List[GridCount], Field(min_length=3, max_length=3)]

_UNSUPPORTED_SPEC_KEYS = (
    "moving_bodies",
    "refinement_lower",
    "neutral_precursor",
    "boundary_field",
    "wall_links",
    "solid",
    "roughness",
    "porous",
    "free_surface",
)
_FOAM_HEADER = (
    "FoamFile\n"
    "{{\n"
    "    version     2.0;\n"
    "    format      ascii;\n"
    "    class       {cls};\n"
    "    object      {obj};\n"
    "}}\n"
)
_FACE_META = {
    "x-": ("xMin", 0, 0, "(0 4 7 3)"),
    "x+": ("xMax", 0, 1, "(1 2 6 5)"),
    "y-": ("yMin", 1, 0, "(0 1 5 4)"),
    "y+": ("yMax", 1, 1, "(3 7 6 2)"),
    "z-": ("zMin", 2, 0, "(0 3 2 1)"),
    "z+": ("zMax", 2, 1, "(4 5 6 7)"),
}
_REQUIRED_TOOLS = ("blockMesh", "checkMesh", "simpleFoam", "icoFoam", "postProcess")


class OpenFoamPayload(Payload):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, revalidate_instances="always")


class OpenFoamBoundaryCondition(OpenFoamPayload):
    type: Literal["velocity", "pressure", "wall", "slip", "periodic"]
    velocity: Optional[Vector] = None
    pressure_pa: Optional[StrictFloat] = None
    profile: Literal["uniform", "parabolic"] = "uniform"
    profile_axis: Optional[Literal[0, 1, 2]] = None


class OpenFoamPatch(OpenFoamPayload):
    id: Identifier
    face: Literal["x-", "x+", "y-", "y+", "z-", "z+"]
    condition: OpenFoamBoundaryCondition


class OpenFoamProbe(OpenFoamPayload):
    id: Identifier
    location_m: Vector


class PressurePair(OpenFoamPayload):
    id: Identifier
    a_probe_id: Identifier
    b_probe_id: Identifier


class OpenFoamMeshSpec(OpenFoamPayload):
    cells: CellCounts
    solver: Literal["simpleFoam", "icoFoam"] = "simpleFoam"
    max_iterations: Annotated[StrictInt, Field(ge=1, le=20000)] = 1000
    residual_tolerance: Positive = 1e-9
    delta_t: Positive = 1.0
    p_ref_cell: Optional[Annotated[StrictInt, Field(ge=0)]] = None
    p_ref_value: StrictFloat = 0.0


class OpenFoamCaseBundle(OpenFoamPayload):
    schema_: Literal["hawa-openfoam-case-1"] = Field(alias="schema")
    case_id: Identifier
    description: Identifier
    dimensions: Literal[2, 3]
    domain_origin_m: Vector
    domain_size_m: PositiveVector
    density_kg_m3: Positive
    kinematic_viscosity_m2_s: Positive
    reference_speed_m_s: Positive
    reference_length_m: Positive
    initial_velocity_m_s: Vector
    pressure_reference_pa: StrictFloat = 0.0
    boundaries: Annotated[List[OpenFoamPatch], Field(min_length=6, max_length=6)]
    probes: Annotated[List[OpenFoamProbe], Field(min_length=1)]
    pressure_pairs: List[PressurePair] = Field(default_factory=list)
    mesh: OpenFoamMeshSpec
    provenance: Dict[StrictStr, StrictStr] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_physical_contract(self):
        patch_dicts = []
        for patch in self.boundaries:
            cond = {"type": patch.condition.type, "profile": patch.condition.profile}
            if patch.condition.velocity is not None:
                cond["velocity"] = list(patch.condition.velocity)
            if patch.condition.pressure_pa is not None:
                cond["pressure_pa"] = float(patch.condition.pressure_pa)
            if patch.condition.profile_axis is not None:
                cond["profile_axis"] = int(patch.condition.profile_axis)
            patch_dicts.append({"id": patch.id, "face": patch.face, "condition": cond})
        ordered = validate_boundary_conditions({"boundary_set": {"schema": 1, "patches": patch_dicts}})
        for axis in range(3):
            pair = (ordered[2 * axis]["type"], ordered[2 * axis + 1]["type"])
            if ("periodic" in pair) and pair != ("periodic", "periodic"):
                raise ValueError("Periodic boundaries must occur in opposite-face pairs")
        if self.dimensions == 2:
            if self.mesh.cells[2] != 1:
                raise ValueError("2D OpenFOAM extrusion requires exactly 1 cell along z")
            if ordered[4]["type"] != "periodic" or ordered[5]["type"] != "periodic":
                raise ValueError("2D OpenFOAM extrusion requires periodic z- and z+ faces")
        has_velocity = any(c["type"] == "velocity" for c in ordered)
        has_pressure = any(c["type"] == "pressure" for c in ordered)
        if has_velocity and not has_pressure:
            raise ValueError("Velocity inlets require a pressure reference patch")
        if not has_pressure and self.mesh.p_ref_cell is None:
            raise ValueError("Closed-domain cases without a pressure patch require mesh.p_ref_cell")

        origin = np.asarray(self.domain_origin_m, dtype=float)
        upper = origin + np.asarray(self.domain_size_m, dtype=float)
        probe_coords = {}
        for probe in self.probes:
            if probe.id in probe_coords:
                raise ValueError("Duplicate probe id: " + probe.id)
            loc = np.asarray(probe.location_m, dtype=float)
            if np.any(loc <= origin) or np.any(loc >= upper):
                raise ValueError("Probe must lie strictly inside domain bounds: " + probe.id)
            probe_coords[probe.id] = loc

        seen_pairs = set()
        for pair in self.pressure_pairs:
            if pair.id in seen_pairs:
                raise ValueError("Duplicate pressure pair id: " + pair.id)
            seen_pairs.add(pair.id)
            if pair.a_probe_id not in probe_coords or pair.b_probe_id not in probe_coords:
                raise ValueError("Pressure pair references unknown probe id: " + pair.id)
            if float(np.linalg.norm(probe_coords[pair.b_probe_id] - probe_coords[pair.a_probe_id])) <= 1e-12:
                raise ValueError("Pressure pair probes must be distinct locations: " + pair.id)
        return self


def validate_bundle(data):
    """Validate an OpenFOAM physical-case bundle payload in strict Python mode."""
    return check(OpenFoamCaseBundle, data, "OpenFOAM case bundle")


def bundle_from_hawa_spec(case_id, description, spec, probes, pressure_pairs, mesh,
                          dimensions=2, domain_origin_m=(0.0, 0.0, 0.0), provenance=None):
    """Build a validated OpenFOAM physical-case bundle directly from a Hawa WindFlow spec."""
    if not isinstance(spec, dict):
        raise ValueError("Hawa spec must be a dictionary")
    for key in _UNSUPPORTED_SPEC_KEYS:
        if spec.get(key):
            raise ValueError("Unsupported Hawa feature for OpenFOAM handoff: " + key)
    bset = spec.get("boundary_set")
    if not isinstance(bset, dict) or bset.get("schema") != 1:
        raise ValueError("Hawa spec must provide a schema 1 boundary_set")
    shape = spec.get("shape")
    dx = spec.get("dx")
    if not isinstance(shape, (list, tuple)) or len(shape) != 3 or not all(type(n) is int and n >= 3 for n in shape):
        raise ValueError("Hawa spec requires a 3-integer shape with at least 3 nodes per axis")
    if not isinstance(dx, (int, float)) or not math.isfinite(dx) or dx <= 0:
        raise ValueError("Hawa spec requires a finite positive dx")

    patches = []
    for patch in bset.get("patches", []):
        cond = patch.get("condition", {})
        ctype = cond.get("type")
        if ctype == "open":
            raise ValueError("Open boundary faces are deferred; use velocity, pressure, wall, slip, or periodic")
        if cond.get("profile") in ("mapped", "neutral"):
            raise ValueError("Mapped and neutral velocity profiles are unsupported in OpenFOAM handoff")
        cleaned = {"type": ctype, "profile": cond.get("profile", "uniform")}
        if "velocity" in cond:
            cleaned["velocity"] = [float(v) for v in cond["velocity"]]
        if "pressure_pa" in cond:
            cleaned["pressure_pa"] = float(cond["pressure_pa"])
        if "profile_axis" in cond:
            cleaned["profile_axis"] = int(cond["profile_axis"])
        patches.append({"id": patch["id"], "face": patch["face"], "condition": cleaned})

    size = [float((shape[0] - 1) * dx), float((shape[1] - 1) * dx), float((shape[2] - 1) * dx)]
    payload = {
        "schema": SCHEMA,
        "case_id": case_id,
        "description": description,
        "dimensions": dimensions,
        "domain_origin_m": [float(v) for v in domain_origin_m],
        "domain_size_m": size,
        "density_kg_m3": float(spec.get("density", 1.225)),
        "kinematic_viscosity_m2_s": float(spec["viscosity"]),
        "reference_speed_m_s": float(spec["speed"]),
        "reference_length_m": float(size[1]),
        "initial_velocity_m_s": [float(v) for v in spec.get("initial_velocity", [0.0, 0.0, 0.0])],
        "pressure_reference_pa": 0.0,
        "boundaries": patches,
        "probes": probes,
        "pressure_pairs": pressure_pairs,
        "mesh": mesh,
        "provenance": dict(provenance or {}),
    }
    validate_bundle(payload)
    return payload


def channel_poiseuille_case(ny_cells=20, lx=4.0, ly=1.0, u_max=0.5, nu=0.025, rho=1.225, mach=0.05):
    """Build matched Hawa WindFlow spec, OpenFOAM bundle, and analytic solution for 2D channel flow."""
    if type(ny_cells) is not int or ny_cells < 6:
        raise ValueError("ny_cells must be an integer >= 6")
    dx = ly / float(ny_cells)
    nx_cells = int(round(lx / dx))
    if abs(nx_cells * dx - lx) > 1e-9:
        raise ValueError("lx must be an exact integer multiple of ly / ny_cells")
    nz_nodes = 4
    lz = (nz_nodes - 1) * dx
    zc = 0.5 * lz

    spec = {
        "shape": [nx_cells + 1, ny_cells + 1, nz_nodes],
        "dx": dx,
        "speed": float(u_max),
        "viscosity": float(nu),
        "density": float(rho),
        "mach": float(mach),
        "collision": "bgk",
        "initial_velocity": [float(2.0 * u_max / 3.0), 0.0, 0.0],
        "boundary_method": "hawa-nee-v1",
        "boundary_set": {
            "schema": 1,
            "patches": [
                {"id": "inlet", "face": "x-", "condition": {
                    "type": "velocity", "velocity": [float(u_max), 0.0, 0.0],
                    "profile": "parabolic", "profile_axis": 1}},
                {"id": "outlet", "face": "x+", "condition": {"type": "pressure", "pressure_pa": 0.0}},
                {"id": "bottom", "face": "y-", "condition": {"type": "wall", "velocity": [0.0, 0.0, 0.0]}},
                {"id": "top", "face": "y+", "condition": {"type": "wall", "velocity": [0.0, 0.0, 0.0]}},
                {"id": "back", "face": "z-", "condition": {"type": "periodic"}},
                {"id": "front", "face": "z+", "condition": {"type": "periodic"}},
            ],
        },
    }
    probe_defs = [
        ("p_x1_mid", [0.25 * lx, 0.50 * ly, zc]),
        ("p_x2_mid", [0.50 * lx, 0.50 * ly, zc]),
        ("p_x3_mid", [0.75 * lx, 0.50 * ly, zc]),
        ("p_x2_y20", [0.50 * lx, 0.20 * ly, zc]),
        ("p_x2_y35", [0.50 * lx, 0.35 * ly, zc]),
        ("p_x2_y65", [0.50 * lx, 0.65 * ly, zc]),
        ("p_x2_y80", [0.50 * lx, 0.80 * ly, zc]),
    ]
    probes = [{"id": pid, "location_m": loc} for pid, loc in probe_defs]
    pairs = [
        {"id": "dp_x1_x3", "a_probe_id": "p_x1_mid", "b_probe_id": "p_x3_mid"},
        {"id": "dp_x1_x2", "a_probe_id": "p_x1_mid", "b_probe_id": "p_x2_mid"},
        {"id": "dp_x2_x3", "a_probe_id": "p_x2_mid", "b_probe_id": "p_x3_mid"},
    ]
    mesh = {
        "cells": [nx_cells, ny_cells, 1],
        "solver": "simpleFoam",
        "max_iterations": 2000,
        "residual_tolerance": 1e-7,
        "delta_t": 1.0,
    }
    bundle = bundle_from_hawa_spec(
        case_id=f"channel_poiseuille_ny{ny_cells}",
        description=f"Laminar 2D Poiseuille channel (Re={u_max * ly / nu:g}, ny={ny_cells})",
        spec=spec,
        probes=probes,
        pressure_pairs=pairs,
        mesh=mesh,
        dimensions=2,
        provenance={"adapter_version": ADAPTER_VERSION, "control_case": "07-channel"},
    )
    dpdx = -8.0 * rho * nu * u_max / (ly ** 2)
    analytic_probes = {}
    for pid, loc in probe_defs:
        eta = loc[1] / ly
        ux = 4.0 * u_max * eta * (1.0 - eta)
        p_pa = -dpdx * (lx - loc[0])
        analytic_probes[pid] = {"velocity_m_s": [ux, 0.0, 0.0], "pressure_pa": p_pa}
    analytic_pairs = {}
    for pair in pairs:
        pa = analytic_probes[pair["a_probe_id"]]["pressure_pa"]
        pb = analytic_probes[pair["b_probe_id"]]["pressure_pa"]
        la = np.asarray(dict(probe_defs)[pair["a_probe_id"]], dtype=float)
        lb = np.asarray(dict(probe_defs)[pair["b_probe_id"]], dtype=float)
        dist = float(np.linalg.norm(lb - la))
        analytic_pairs[pair["id"]] = {
            "delta_p_pa": pa - pb,
            "gradient_pa_m": (pb - pa) / dist,
            "distance_m": dist,
        }
    analytic = {
        "dp_dx_pa_m": dpdx,
        "probes": analytic_probes,
        "pressure_pairs": analytic_pairs,
    }
    return spec, bundle, analytic


def cavity_control_case(n=64, reynolds=10.0, mach=0.05):
    """Build matched Hawa Cavity2D configuration and OpenFOAM bundle (Example 06 control)."""
    if type(n) is not int or n < 16:
        raise ValueError("n must be an integer >= 16")
    if reynolds <= 0 or mach <= 0:
        raise ValueError("reynolds and mach must be positive")
    nu = 1.0 / float(reynolds)
    lz = 0.1
    zc = 0.05
    probe_defs = [
        ("c_50_25", [0.50, 0.25, zc]),
        ("c_50_50", [0.50, 0.50, zc]),
        ("c_50_75", [0.50, 0.75, zc]),
        ("c_25_50", [0.25, 0.50, zc]),
        ("c_75_50", [0.75, 0.50, zc]),
        ("c_25_75", [0.25, 0.75, zc]),
        ("c_75_75", [0.75, 0.75, zc]),
    ]
    bundle = {
        "schema": SCHEMA,
        "case_id": f"cavity_re{int(round(reynolds))}_n{n}",
        "description": f"Lid-driven 2D cavity (Re={reynolds:g}, n={n}, Example 06 control)",
        "dimensions": 2,
        "domain_origin_m": [0.0, 0.0, 0.0],
        "domain_size_m": [1.0, 1.0, lz],
        "density_kg_m3": 1.0,
        "kinematic_viscosity_m2_s": nu,
        "reference_speed_m_s": 1.0,
        "reference_length_m": 1.0,
        "initial_velocity_m_s": [0.0, 0.0, 0.0],
        "pressure_reference_pa": 0.0,
        "boundaries": [
            {"id": "left", "face": "x-", "condition": {"type": "wall", "velocity": [0.0, 0.0, 0.0]}},
            {"id": "right", "face": "x+", "condition": {"type": "wall", "velocity": [0.0, 0.0, 0.0]}},
            {"id": "bottom", "face": "y-", "condition": {"type": "wall", "velocity": [0.0, 0.0, 0.0]}},
            {"id": "lid", "face": "y+", "condition": {"type": "wall", "velocity": [1.0, 0.0, 0.0]}},
            {"id": "back", "face": "z-", "condition": {"type": "periodic"}},
            {"id": "front", "face": "z+", "condition": {"type": "periodic"}},
        ],
        "probes": [{"id": pid, "location_m": loc} for pid, loc in probe_defs],
        "pressure_pairs": [
            {"id": "dp_upper_lr", "a_probe_id": "c_75_75", "b_probe_id": "c_25_75"},
            {"id": "dp_mid_lr", "a_probe_id": "c_75_50", "b_probe_id": "c_25_50"},
        ],
        "mesh": {
            "cells": [n, n, 1],
            "solver": "simpleFoam",
            "max_iterations": 2000,
            "residual_tolerance": 1e-7,
            "delta_t": 1.0,
            "p_ref_cell": 0,
            "p_ref_value": 0.0,
        },
        "provenance": {"adapter_version": ADAPTER_VERSION, "control_case": "06-cavity"},
    }
    validate_bundle(bundle)
    hawa_config = {"resolution": n, "reynolds_number": float(reynolds), "mach_number": float(mach)}
    return hawa_config, bundle


def _blockmesh_patch_face_centers(origin, size, cells, face):
    """Exact face-center coordinates in blockMesh face ordering for a Cartesian hex block."""
    nx, ny, nz = cells
    x0, y0, z0 = origin
    lx, ly, lz = size
    xs = x0 + (np.arange(nx) + 0.5) * (lx / nx)
    ys = y0 + (np.arange(ny) + 0.5) * (ly / ny)
    zs = z0 + (np.arange(nz) + 0.5) * (lz / nz)
    centers = []
    if face in ("x-", "x+"):
        x_val = x0 if face == "x-" else x0 + lx
        for k in range(nz):
            for j in range(ny):
                centers.append((x_val, float(ys[j]), float(zs[k])))
    elif face in ("y-", "y+"):
        y_val = y0 if face == "y-" else y0 + ly
        for k in range(nz):
            for i in range(nx):
                centers.append((float(xs[i]), y_val, float(zs[k])))
    else:
        z_val = z0 if face == "z-" else z0 + lz
        for j in range(ny):
            for i in range(nx):
                centers.append((float(xs[i]), float(ys[j]), z_val))
    return centers


def _render_parabolic_u_field(origin, size, cells, face, velocity, profile_axis):
    centers = _blockmesh_patch_face_centers(origin, size, cells, face)
    ax = int(profile_axis)
    lo = origin[ax]
    span = size[ax]
    lines = ["        type            fixedValue;", "        value           nonuniform List<vector>",
             f"        {len(centers)}", "        ("]
    for pt in centers:
        eta = (pt[ax] - lo) / span
        w = 4.0 * eta * (1.0 - eta)
        lines.append(f"            ({velocity[0] * w:.12g} {velocity[1] * w:.12g} {velocity[2] * w:.12g})")
    lines.append("        );")
    return "\n".join(lines)


def _foam_patch_type(face, cond, dimensions):
    ctype = cond["type"]
    if dimensions == 2 and face in ("z-", "z+"):
        return "empty"
    if ctype == "wall":
        return "wall"
    if ctype == "periodic":
        return "cyclic"
    return "patch"


def _render_openfoam_files(bundle):
    origin = bundle["domain_origin_m"]
    size = bundle["domain_size_m"]
    dims = bundle["dimensions"]
    mesh = bundle["mesh"]
    cells = mesh["cells"]
    rho = bundle["density_kg_m3"]
    nu = bundle["kinematic_viscosity_m2_s"]
    x0, y0, z0 = origin
    x1, y1, z1 = x0 + size[0], y0 + size[1], z0 + size[2]

    by_face = {p["face"]: p["condition"] for p in bundle["boundaries"]}
    cyclic_partner = {"x-": "xMax", "x+": "xMin", "y-": "yMax", "y+": "yMin", "z-": "zMax", "z+": "zMin"}

    bm_bounds = []
    u_bounds = []
    p_bounds = []
    for face in FACES:
        name, _, _, verts = _FACE_META[face]
        cond = by_face[face]
        ptype = _foam_patch_type(face, cond, dims)
        if ptype == "cyclic":
            bm_bounds.append(
                f"    {name}\n    {{\n        type cyclic;\n        neighbourPatch {cyclic_partner[face]};\n"
                f"        faces ({verts});\n    }}"
            )
            u_bounds.append(f"    {name}\n    {{\n        type            cyclic;\n    }}")
            p_bounds.append(f"    {name}\n    {{\n        type            cyclic;\n    }}")
        elif ptype == "empty":
            bm_bounds.append(f"    {name}\n    {{\n        type empty;\n        faces ({verts});\n    }}")
            u_bounds.append(f"    {name}\n    {{\n        type            empty;\n    }}")
            p_bounds.append(f"    {name}\n    {{\n        type            empty;\n    }}")
        else:
            bm_bounds.append(f"    {name}\n    {{\n        type {ptype};\n        faces ({verts});\n    }}")
            ctype = cond["type"]
            if ctype == "wall":
                v = cond.get("velocity", [0.0, 0.0, 0.0])
                if all(abs(c) <= 1e-15 for c in v):
                    u_bounds.append(f"    {name}\n    {{\n        type            noSlip;\n    }}")
                else:
                    u_bounds.append(
                        f"    {name}\n    {{\n        type            fixedValue;\n"
                        f"        value           uniform ({v[0]:.12g} {v[1]:.12g} {v[2]:.12g});\n    }}"
                    )
                p_bounds.append(f"    {name}\n    {{\n        type            zeroGradient;\n    }}")
            elif ctype == "velocity":
                v = cond.get("velocity", [0.0, 0.0, 0.0])
                if cond.get("profile") == "parabolic":
                    body = _render_parabolic_u_field(origin, size, cells, face, v, cond["profile_axis"])
                    u_bounds.append(f"    {name}\n    {{\n{body}\n    }}")
                else:
                    u_bounds.append(
                        f"    {name}\n    {{\n        type            fixedValue;\n"
                        f"        value           uniform ({v[0]:.12g} {v[1]:.12g} {v[2]:.12g});\n    }}"
                    )
                p_bounds.append(f"    {name}\n    {{\n        type            zeroGradient;\n    }}")
            elif ctype == "pressure":
                p_kin = float(cond.get("pressure_pa", 0.0)) / float(rho)
                u_bounds.append(f"    {name}\n    {{\n        type            zeroGradient;\n    }}")
                p_bounds.append(
                    f"    {name}\n    {{\n        type            fixedValue;\n"
                    f"        value           uniform {p_kin:.12g};\n    }}"
                )
            else:
                u_bounds.append(f"    {name}\n    {{\n        type            slip;\n    }}")
                p_bounds.append(f"    {name}\n    {{\n        type            zeroGradient;\n    }}")

    init_u = bundle["initial_velocity_m_s"]
    init_p_kin = float(bundle.get("pressure_reference_pa", 0.0)) / float(rho)
    p_ref_lines = ""
    if mesh.get("p_ref_cell") is not None:
        p_ref_lines = (
            f"    pRefCell        {int(mesh['p_ref_cell'])};\n"
            f"    pRefValue       {float(mesh.get('p_ref_value', 0.0)) / float(rho):.12g};\n"
        )

    probe_lines = "\n".join(
        f"    ({p['location_m'][0]:.12g} {p['location_m'][1]:.12g} {p['location_m'][2]:.12g})"
        for p in bundle["probes"]
    )
    solver = mesh.get("solver", "simpleFoam")
    max_iters = int(mesh.get("max_iterations", 1000))
    delta_t = float(mesh.get("delta_t", 1.0))
    res_tol = float(mesh.get("residual_tolerance", 1e-9))
    ddt_scheme = "steadyState" if solver == "simpleFoam" else "Euler"
    div_u = "bounded Gauss linearUpwind grad(U)" if solver == "simpleFoam" else "Gauss linear"

    return {
        "system/blockMeshDict": (
            _FOAM_HEADER.format(cls="dictionary", obj="blockMeshDict")
            + "scale 1;\nvertices\n(\n"
            + f"    ({x0:.12g} {y0:.12g} {z0:.12g})\n    ({x1:.12g} {y0:.12g} {z0:.12g})\n"
            + f"    ({x1:.12g} {y1:.12g} {z0:.12g})\n    ({x0:.12g} {y1:.12g} {z0:.12g})\n"
            + f"    ({x0:.12g} {y0:.12g} {z1:.12g})\n    ({x1:.12g} {y0:.12g} {z1:.12g})\n"
            + f"    ({x1:.12g} {y1:.12g} {z1:.12g})\n    ({x0:.12g} {y1:.12g} {z1:.12g})\n"
            + ");\n"
            + f"blocks\n(\n    hex (0 1 2 3 4 5 6 7) ({cells[0]} {cells[1]} {cells[2]}) simpleGrading (1 1 1)\n);\n"
            + "edges ();\nboundary\n(\n"
            + "\n".join(bm_bounds)
            + "\n);\n"
        ),
        "constant/transportProperties": (
            _FOAM_HEADER.format(cls="dictionary", obj="transportProperties")
            + f"transportModel  Newtonian;\nnu              {nu:.12g};\n"
        ),
        "constant/turbulenceProperties": (
            _FOAM_HEADER.format(cls="dictionary", obj="turbulenceProperties")
            + "simulationType  laminar;\n"
        ),
        "0/U": (
            _FOAM_HEADER.format(cls="volVectorField", obj="U")
            + "dimensions      [0 1 -1 0 0 0 0];\n"
            + f"internalField   uniform ({init_u[0]:.12g} {init_u[1]:.12g} {init_u[2]:.12g});\n"
            + "boundaryField\n{\n"
            + "\n".join(u_bounds)
            + "\n}\n"
        ),
        "0/p": (
            _FOAM_HEADER.format(cls="volScalarField", obj="p")
            + "dimensions      [0 2 -2 0 0 0 0];\n"
            + f"internalField   uniform {init_p_kin:.12g};\n"
            + "boundaryField\n{\n"
            + "\n".join(p_bounds)
            + "\n}\n"
        ),
        "system/controlDict": (
            _FOAM_HEADER.format(cls="dictionary", obj="controlDict")
            + f"application     {solver};\n"
            + "startFrom       startTime;\nstartTime       0;\nstopAt          endTime;\n"
            + f"endTime         {max_iters * delta_t:.12g};\n"
            + f"deltaT          {delta_t:.12g};\n"
            + "writeControl    timeStep;\n"
            + f"writeInterval   {max_iters};\n"
            + "purgeWrite      0;\nwriteFormat     ascii;\nwritePrecision  10;\n"
            + "writeCompression off;\ntimeFormat      general;\ntimePrecision   6;\n"
            + "runTimeModifiable true;\n"
        ),
        "system/fvSchemes": (
            _FOAM_HEADER.format(cls="dictionary", obj="fvSchemes")
            + f"ddtSchemes\n{{\n    default         {ddt_scheme};\n}}\n"
            + "gradSchemes\n{\n    default         Gauss linear;\n}\n"
            + "divSchemes\n{\n    default         none;\n"
            + f"    div(phi,U)      {div_u};\n"
            + "    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n}\n"
            + "laplacianSchemes\n{\n    default         Gauss linear corrected;\n}\n"
            + "interpolationSchemes\n{\n    default         linear;\n}\n"
            + "snGradSchemes\n{\n    default         corrected;\n}\n"
        ),
        "system/fvSolution": (
            _FOAM_HEADER.format(cls="dictionary", obj="fvSolution")
            + "solvers\n{\n"
            + "    p\n    {\n        solver          GAMG;\n        smoother        GaussSeidel;\n"
            + "        tolerance       1e-11;\n        relTol          0.01;\n    }\n"
            + "    pFinal\n    {\n        $p;\n        relTol          0;\n    }\n"
            + "    U\n    {\n        solver          smoothSolver;\n        smoother        symGaussSeidel;\n"
            + "        tolerance       1e-11;\n        relTol          0.01;\n    }\n"
            + "}\nSIMPLE\n{\n"
            + "    nNonOrthogonalCorrectors 0;\n    consistent      yes;\n"
            + p_ref_lines
            + "    residualControl\n    {\n"
            + f"        p               {res_tol:.12g};\n"
            + f"        U               {res_tol:.12g};\n"
            + "    }\n}\n"
            + "PISO\n{\n    nCorrectors     2;\n    nNonOrthogonalCorrectors 0;\n"
            + p_ref_lines
            + "}\n"
            + "relaxationFactors\n{\n    equations\n    {\n        U               0.9;\n    }\n}\n"
        ),
        "system/probes": (
            _FOAM_HEADER.format(cls="dictionary", obj="probes")
            + "type            probes;\nlibs            (sampling);\nfields          (p U);\n"
            + "interpolationScheme cellPoint;\nprobeLocations\n(\n"
            + probe_lines
            + "\n);\n"
        ),
    }


def write_openfoam_case(bundle, destination, overwrite=False):
    """Atomically publish a validated case bundle and OpenFOAM v2606 case directory."""
    validate_bundle(bundle)
    dest = Path(destination)
    if dest.exists() and not overwrite:
        raise FileExistsError("Destination already exists: " + str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".hawa-openfoam-", dir=str(dest.parent)))
    backup = None
    try:
        bundle_dir = staging / "bundle"
        case_dir = staging / "openfoam"
        bundle_dir.mkdir(parents=True)
        case_dir.mkdir(parents=True)

        files = _render_openfoam_files(bundle)
        hashes = {}
        case_json = json.dumps(bundle, indent=2, sort_keys=True) + "\n"
        (bundle_dir / "case.json").write_text(case_json, encoding="utf-8")
        hashes["bundle/case.json"] = hashlib.sha256(case_json.encode("utf-8")).hexdigest()

        for rel, content in sorted(files.items()):
            target = case_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            hashes["openfoam/" + rel] = hashlib.sha256(content.encode("utf-8")).hexdigest()

        manifest = {
            "schema": SCHEMA,
            "adapter_version": ADAPTER_VERSION,
            "case_id": bundle["case_id"],
            "files": hashes,
        }
        (bundle_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if dest.exists():
            backup = Path(tempfile.mkdtemp(prefix=".hawa-openfoam-backup-", dir=str(dest.parent)))
            backup.rmdir()
            os.replace(str(dest), str(backup))
        os.replace(str(staging), str(dest))
        if backup is not None:
            shutil.rmtree(backup)
        return {"root": str(dest), "openfoam_dir": str(dest / "openfoam"), "manifest": manifest}
    except Exception:
        if backup is not None and backup.exists() and not dest.exists():
            os.replace(str(backup), str(dest))
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise


def _default_runner(cmd, timeout_s=300):
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout_s)
    return proc.returncode, proc.stdout, proc.stderr


def detect_openfoam(launcher=None, runner=None):
    """Discover local OpenFOAM launcher and verify required v2606 tools."""
    exe = launcher or shutil.which("openfoam2606") or shutil.which("openfoam")
    if not exe:
        return {"available": False, "launcher": None, "reason": "No openfoam2606 or openfoam launcher found on PATH"}
    exec_fn = runner or _default_runner
    probe_cmd = (
        'printf "VERSION=%s\\nOPTIONS=%s\\n" "$WM_PROJECT_VERSION" "$WM_OPTIONS"; '
        + " ".join(f'printf "TOOL:{t}=%s\\n" "$(command -v {t} || true)";' for t in _REQUIRED_TOOLS)
    )
    rc, out, err = exec_fn([exe, "-c", probe_cmd], 60)
    if rc != 0:
        return {"available": False, "launcher": exe, "reason": f"Launcher exited {rc}: {err.strip() or out.strip()}"}
    version = ""
    options = ""
    tools = {}
    for line in out.splitlines():
        if line.startswith("VERSION="):
            version = line.split("=", 1)[1].strip()
        elif line.startswith("OPTIONS="):
            options = line.split("=", 1)[1].strip()
        elif line.startswith("TOOL:"):
            name, path = line[5:].split("=", 1)
            tools[name] = path.strip()
    missing = [t for t in _REQUIRED_TOOLS if not tools.get(t)]
    return {
        "available": bool(version and not missing),
        "launcher": exe,
        "version": version,
        "options": options,
        "tools": tools,
        "missing_tools": missing,
    }


def parse_check_mesh(text, expected_origin, expected_size, tol=1e-6):
    """Parse checkMesh log and verify topology status and SI bounding box."""
    cells_match = re.search(r"^\s*cells:\s+(\d+)\s*$", text, re.MULTILINE)
    bbox_match = re.search(
        r"Overall domain bounding box\s+\(([^)]+)\)\s+\(([^)]+)\)",
        text,
    )
    mesh_ok = "Mesh OK." in text
    if not cells_match or not bbox_match:
        raise ValueError("checkMesh output missing cell count or bounding box")
    cells = int(cells_match.group(1))
    lo = [float(v) for v in bbox_match.group(1).split()]
    hi = [float(v) for v in bbox_match.group(2).split()]
    exp_lo = [float(v) for v in expected_origin]
    exp_hi = [float(expected_origin[i] + expected_size[i]) for i in range(3)]
    if len(lo) != 3 or len(hi) != 3:
        raise ValueError("Malformed checkMesh bounding box")
    if not mesh_ok:
        raise ValueError("checkMesh did not report Mesh OK")
    if not (np.allclose(lo, exp_lo, atol=tol, rtol=0.0) and np.allclose(hi, exp_hi, atol=tol, rtol=0.0)):
        raise ValueError(f"checkMesh bounding box {(lo, hi)} does not match contract {(exp_lo, exp_hi)}")
    return {"mesh_ok": True, "cells": cells, "min_m": lo, "max_m": hi}


def parse_probes_scalar(text, expected_count):
    """Parse latest-time scalar probe row from OpenFOAM postProcessing/probes output."""
    rows = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not rows:
        raise ValueError("OpenFOAM scalar probe output contains no data rows")
    tokens = rows[-1].split()
    if len(tokens) != expected_count + 1:
        raise ValueError(f"Expected {expected_count} scalar probe values, got {len(tokens) - 1}")
    time_val = float(tokens[0])
    values = [float(tok) for tok in tokens[1:]]
    if not math.isfinite(time_val) or not all(math.isfinite(v) for v in values):
        raise ValueError("Non-finite value in OpenFOAM scalar probe output")
    return time_val, values


def parse_probes_vector(text, expected_count):
    """Parse latest-time vector probe row from OpenFOAM postProcessing/probes output."""
    rows = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not rows:
        raise ValueError("OpenFOAM vector probe output contains no data rows")
    last = rows[-1]
    time_match = re.match(r"^(\S+)\s+(.*)$", last)
    if not time_match:
        raise ValueError("Malformed OpenFOAM vector probe row")
    time_val = float(time_match.group(1))
    vectors = re.findall(r"\(([^)]+)\)", time_match.group(2))
    if len(vectors) != expected_count:
        raise ValueError(f"Expected {expected_count} vector probe values, got {len(vectors)}")
    parsed = []
    for vec in vectors:
        parts = [float(v) for v in vec.split()]
        if len(parts) != 3 or not all(math.isfinite(v) for v in parts):
            raise ValueError("Malformed or non-finite vector in OpenFOAM probe output")
        parsed.append(parts)
    if not math.isfinite(time_val):
        raise ValueError("Non-finite time in OpenFOAM vector probe output")
    return time_val, parsed


def _pressure_pairs_from_probes(bundle, probe_map):
    loc_by_id = {p["id"]: np.asarray(p["location_m"], dtype=float) for p in bundle["probes"]}
    out = {}
    for pair in bundle.get("pressure_pairs", []):
        pa = float(probe_map[pair["a_probe_id"]]["pressure_pa"])
        pb = float(probe_map[pair["b_probe_id"]]["pressure_pa"])
        dist = float(np.linalg.norm(loc_by_id[pair["b_probe_id"]] - loc_by_id[pair["a_probe_id"]]))
        out[pair["id"]] = {
            "delta_p_pa": pa - pb,
            "gradient_pa_m": (pb - pa) / dist,
            "distance_m": dist,
        }
    return out


def run_openfoam_case(case_dir, bundle, launcher=None, runner=None, timeout_s=300):
    """Run blockMesh, checkMesh, solver, and postProcess probes on a prepared OpenFOAM case."""
    validate_bundle(bundle)
    info = detect_openfoam(launcher=launcher, runner=runner)
    if not info["available"]:
        raise RuntimeError("OpenFOAM unavailable: " + info.get("reason", "missing required tools"))
    exe = info["launcher"]
    exec_fn = runner or _default_runner
    cdir = Path(case_dir)
    solver = bundle["mesh"]["solver"]
    steps = [
        ("blockMesh", "blockMesh"),
        ("checkMesh", "checkMesh"),
        (solver, solver),
        ("probes", "postProcess -func probes -latestTime"),
    ]
    logs = {}
    for label, cmd_str in steps:
        shell_cmd = f"cd {shlex.quote(str(cdir))} && {cmd_str}"
        rc, out, err = exec_fn([exe, "-c", shell_cmd], timeout_s)
        logs[label] = out + ("\n" + err if err else "")
        (cdir / f"{label}.log").write_text(logs[label], encoding="utf-8")
        if rc != 0:
            raise RuntimeError(f"OpenFOAM step {label} failed with exit code {rc}")

    check_summary = parse_check_mesh(logs["checkMesh"], bundle["domain_origin_m"], bundle["domain_size_m"])
    p_files = sorted((cdir / "postProcessing" / "probes").glob("*/p"))
    u_files = sorted((cdir / "postProcessing" / "probes").glob("*/U"))
    if not p_files or not u_files:
        raise RuntimeError("OpenFOAM postProcess did not write probe files for p and U")

    count = len(bundle["probes"])
    t_p, p_kin_vals = parse_probes_scalar(p_files[-1].read_text(encoding="utf-8"), count)
    t_u, u_vals = parse_probes_vector(u_files[-1].read_text(encoding="utf-8"), count)
    rho = float(bundle["density_kg_m3"])
    probes_out = {}
    for probe, p_kin, u_vec in zip(bundle["probes"], p_kin_vals, u_vals):
        probes_out[probe["id"]] = {
            "location_m": list(probe["location_m"]),
            "velocity_m_s": u_vec,
            "pressure_kinematic_m2_s2": p_kin,
            "pressure_pa": p_kin * rho,
        }
    converged = ("SIMPLE solution converged" in logs[solver]) if solver == "simpleFoam" else True
    return {
        "solver": solver,
        "openfoam_version": info["version"],
        "openfoam_options": info["options"],
        "converged": converged,
        "sample_time": t_u,
        "pressure_sample_time": t_p,
        "check_mesh": check_summary,
        "probes": probes_out,
        "pressure_pairs": _pressure_pairs_from_probes(bundle, probes_out),
    }


def sample_regular_grid(velocity, pressure, axes, probe_locations, solid=None):
    """Bilinear (2D) or trilinear (3D) interpolation at exact SI world coordinates."""
    u = np.asarray(velocity, dtype=float)
    p = np.asarray(pressure, dtype=float)
    ndim = p.ndim
    if ndim not in (2, 3) or u.shape != (ndim, *p.shape) or len(axes) != ndim:
        raise ValueError("Velocity, pressure, and axes dimensions must match (2D or 3D)")
    axis_arrays = [np.asarray(a, dtype=float) for a in axes]
    for a, n in zip(axis_arrays, p.shape):
        if a.shape != (n,) or n < 2 or not np.all(np.diff(a) > 0):
            raise ValueError("Grid axes must be strictly increasing 1D arrays matching field shape")
    solid_mask = None if solid is None else np.asarray(solid, dtype=bool)
    if solid_mask is not None and solid_mask.shape != p.shape:
        raise ValueError("Solid mask shape must match pressure field shape")

    sampled = []
    for loc in probe_locations:
        pt = np.asarray(loc[:ndim], dtype=float)
        idx = []
        frac = []
        for d in range(ndim):
            lo, hi = float(axis_arrays[d][0]), float(axis_arrays[d][-1])
            if not math.isfinite(float(pt[d])) or pt[d] < lo - 1e-12 or pt[d] > hi + 1e-12:
                raise ValueError(f"Probe coordinate {pt.tolist()} lies outside Hawa grid bounds")
            clamped = min(max(float(pt[d]), lo), hi)
            i = int(np.searchsorted(axis_arrays[d], clamped, side="right")) - 1
            i = max(0, min(i, p.shape[d] - 2))
            x0, x1 = float(axis_arrays[d][i]), float(axis_arrays[d][i + 1])
            idx.append(i)
            frac.append((clamped - x0) / (x1 - x0))
        u_val = np.zeros(ndim, dtype=float)
        p_val = 0.0
        for corner in range(1 << ndim):
            w = 1.0
            c_idx = []
            for d in range(ndim):
                bit = (corner >> d) & 1
                w *= frac[d] if bit else (1.0 - frac[d])
                c_idx.append(idx[d] + bit)
            if solid_mask is not None and w > 1e-12 and bool(solid_mask[tuple(c_idx)]):
                raise ValueError(f"Probe coordinate {pt.tolist()} touches solid/invalid Hawa node")
            u_val += w * u[(slice(None),) + tuple(c_idx)]
            p_val += w * float(p[tuple(c_idx)])
        if not np.isfinite(u_val).all() or not math.isfinite(p_val):
            raise ValueError(f"Non-finite interpolated field at probe {pt.tolist()}")
        u3 = [float(u_val[0]), float(u_val[1]), float(u_val[2]) if ndim == 3 else 0.0]
        sampled.append((u3, float(p_val)))
    return sampled


def _sample_hawa_bundle(bundle, velocity, pressure, axes, solid=None):
    locs = [p["location_m"] for p in bundle["probes"]]
    values = sample_regular_grid(velocity, pressure, axes, locs, solid=solid)
    probes_out = {}
    for probe, (u3, p_pa) in zip(bundle["probes"], values):
        probes_out[probe["id"]] = {
            "location_m": list(probe["location_m"]),
            "velocity_m_s": u3,
            "pressure_pa": p_pa,
        }
    return probes_out, _pressure_pairs_from_probes(bundle, probes_out)


def _max_observable_drift(prev_probes, cur_probes, prev_pairs, cur_pairs, u_scale, p_scale):
    max_u = 0.0
    for pid in cur_probes:
        du = np.linalg.norm(
            np.asarray(cur_probes[pid]["velocity_m_s"]) - np.asarray(prev_probes[pid]["velocity_m_s"])
        )
        max_u = max(max_u, float(du) / u_scale)
    max_dp = 0.0
    for pair_id in cur_pairs:
        ddp = abs(cur_pairs[pair_id]["delta_p_pa"] - prev_pairs[pair_id]["delta_p_pa"])
        max_dp = max(max_dp, float(ddp) / p_scale)
    return max(max_u, max_dp)


def run_hawa_channel(spec, bundle, device="cpu", max_steps=16000, check_interval=1000, settle_tol=1e-3):
    """Run Hawa WindFlow channel case until velocity and pressure drops settle."""
    from .plugin import Session

    validate_bundle(bundle)
    session = Session(spec, device=device)
    dx = float(spec["dx"])
    axes = [np.arange(n, dtype=float) * dx for n in spec["shape"]]
    u_scale = float(bundle["reference_speed_m_s"])
    p_scale = max(0.5 * float(bundle["density_kg_m3"]) * u_scale * u_scale, 1e-12)
    prev_probes = None
    prev_pairs = None
    settled = False
    drift = float("inf")
    while session.flow.i < max_steps:
        chunk = min(check_interval, max_steps - session.flow.i)
        session.advance(chunk)
        fields = session.fields()
        cur_probes, cur_pairs = _sample_hawa_bundle(
            bundle, fields["velocity"], fields["pressure"], axes, solid=fields.get("solid")
        )
        if prev_probes is not None:
            drift = _max_observable_drift(prev_probes, cur_probes, prev_pairs, cur_pairs, u_scale, p_scale)
            if drift <= settle_tol:
                settled = True
                break
        prev_probes, prev_pairs = cur_probes, cur_pairs
    return {
        "device": session.backend.info()["selected"],
        "dtype": str(session.flow.context.dtype),
        "steps": int(session.flow.i),
        "physical_time_s": float(session.flow.units.convert_time_to_pu(session.flow.i)),
        "tau": float(session.flow.units.relaxation_parameter_lu),
        "settled": settled,
        "final_drift": drift,
        "relative_mass_change": float(session.relative_mass_change),
        "probes": cur_probes,
        "pressure_pairs": cur_pairs,
    }


def run_hawa_cavity(hawa_config, bundle, device="cpu", dtype="float64", target_time_s=3.5):
    """Run Hawa Cavity2D control case and sample exact SI probe locations."""
    import lettuce as lt
    import torch
    from .backends import select_backend

    validate_bundle(bundle)
    backend = select_backend(device)
    torch_dtype = torch.float64 if dtype == "float64" else torch.float32
    if backend.device.type == "mps":
        torch_dtype = torch.float32
    ctx = lt.Context(backend.device, torch_dtype, use_native=False)
    n = int(hawa_config["resolution"])
    flow = lt.Cavity2D(
        ctx,
        resolution=n,
        reynolds_number=float(hawa_config["reynolds_number"]),
        mach_number=float(hawa_config["mach_number"]),
    )
    sim = lt.Simulation(flow=flow, collision=lt.BGKCollision(flow.units.relaxation_parameter_lu), reporter=[])
    dt = float(flow.units.convert_time_to_pu(1))
    steps = max(1, int(round(float(target_time_s) / dt)))
    sim(steps)
    backend.synchronize()
    u = flow.u_pu.detach().cpu().numpy()
    p = flow.p_pu[0].detach().cpu().numpy()
    if not np.isfinite(u).all() or not np.isfinite(p).all():
        raise RuntimeError("Hawa Cavity2D produced non-finite fields")
    axis = np.arange(n, dtype=float) / float(n)
    probes, pairs = _sample_hawa_bundle(bundle, u, p, [axis, axis])
    return {
        "device": backend.info()["selected"],
        "dtype": str(torch_dtype),
        "steps": steps,
        "physical_time_s": float(flow.units.convert_time_to_pu(steps)),
        "tau": float(flow.units.relaxation_parameter_lu),
        "resolution": n,
        "mach_number": float(hawa_config["mach_number"]),
        "probes": probes,
        "pressure_pairs": pairs,
    }


def compare_probe_results(bundle, hawa_result, openfoam_result, analytic=None,
                          velocity_tol=None, pressure_tol=None):
    """Compare Hawa and OpenFOAM at every declared probe and pressure pair."""
    validate_bundle(bundle)
    u_ref = float(bundle["reference_speed_m_s"])
    q_ref = 0.5 * float(bundle["density_kg_m3"]) * u_ref * u_ref
    probe_rows = []
    u_errs = []
    for probe in bundle["probes"]:
        pid = probe["id"]
        if pid not in hawa_result["probes"] or pid not in openfoam_result["probes"]:
            raise ValueError("Missing required probe in solver results: " + pid)
        uh = np.asarray(hawa_result["probes"][pid]["velocity_m_s"], dtype=float)
        uo = np.asarray(openfoam_result["probes"][pid]["velocity_m_s"], dtype=float)
        diff = float(np.linalg.norm(uh - uo))
        norm_err = diff / u_ref
        u_errs.append(norm_err)
        row = {
            "id": pid,
            "location_m": list(probe["location_m"]),
            "hawa_velocity_m_s": uh.tolist(),
            "openfoam_velocity_m_s": uo.tolist(),
            "abs_velocity_err_m_s": diff,
            "norm_velocity_err": norm_err,
            "hawa_pressure_pa": float(hawa_result["probes"][pid]["pressure_pa"]),
            "openfoam_pressure_pa": float(openfoam_result["probes"][pid]["pressure_pa"]),
        }
        if analytic is not None and pid in analytic.get("probes", {}):
            ua = np.asarray(analytic["probes"][pid]["velocity_m_s"], dtype=float)
            row["analytic_velocity_m_s"] = ua.tolist()
            row["hawa_vs_analytic_norm_u"] = float(np.linalg.norm(uh - ua)) / u_ref
            row["openfoam_vs_analytic_norm_u"] = float(np.linalg.norm(uo - ua)) / u_ref
        probe_rows.append(row)

    pair_rows = []
    dp_errs = []
    for pair in bundle.get("pressure_pairs", []):
        pair_id = pair["id"]
        if pair_id not in hawa_result["pressure_pairs"] or pair_id not in openfoam_result["pressure_pairs"]:
            raise ValueError("Missing required pressure pair in solver results: " + pair_id)
        hp = hawa_result["pressure_pairs"][pair_id]
        op = openfoam_result["pressure_pairs"][pair_id]
        abs_dp = abs(float(hp["delta_p_pa"]) - float(op["delta_p_pa"]))
        scale_p = max(abs(float(op["delta_p_pa"])), q_ref)
        norm_dp = abs_dp / scale_p
        dp_errs.append(norm_dp)
        row = {
            "id": pair_id,
            "hawa_delta_p_pa": float(hp["delta_p_pa"]),
            "openfoam_delta_p_pa": float(op["delta_p_pa"]),
            "abs_delta_p_err_pa": abs_dp,
            "norm_delta_p_err": norm_dp,
            "hawa_gradient_pa_m": float(hp["gradient_pa_m"]),
            "openfoam_gradient_pa_m": float(op["gradient_pa_m"]),
            "abs_gradient_err_pa_m": abs(float(hp["gradient_pa_m"]) - float(op["gradient_pa_m"])),
        }
        if analytic is not None and pair_id in analytic.get("pressure_pairs", {}):
            ap = analytic["pressure_pairs"][pair_id]
            a_dp = float(ap["delta_p_pa"])
            a_scale = max(abs(a_dp), q_ref)
            row["analytic_delta_p_pa"] = a_dp
            row["analytic_gradient_pa_m"] = float(ap["gradient_pa_m"])
            row["hawa_vs_analytic_norm_dp"] = abs(float(hp["delta_p_pa"]) - a_dp) / a_scale
            row["openfoam_vs_analytic_norm_dp"] = abs(float(op["delta_p_pa"]) - a_dp) / a_scale
        pair_rows.append(row)

    u_l2 = float(math.sqrt(sum(e * e for e in u_errs) / len(u_errs)))
    u_linf = float(max(u_errs))
    dp_linf = float(max(dp_errs)) if dp_errs else 0.0

    failures = []
    if velocity_tol is not None:
        for row in probe_rows:
            if row["norm_velocity_err"] > velocity_tol:
                failures.append(f"probe {row['id']} norm_velocity_err {row['norm_velocity_err']:.4g} > {velocity_tol}")
    if pressure_tol is not None:
        for row in pair_rows:
            if row["norm_delta_p_err"] > pressure_tol:
                failures.append(f"pair {row['id']} norm_delta_p_err {row['norm_delta_p_err']:.4g} > {pressure_tol}")

    return {
        "case_id": bundle["case_id"],
        "velocity_l2_norm": u_l2,
        "velocity_linf_norm": u_linf,
        "pressure_pair_linf_norm": dp_linf,
        "passed": len(failures) == 0,
        "failures": failures,
        "probes": probe_rows,
        "pressure_pairs": pair_rows,
    }
