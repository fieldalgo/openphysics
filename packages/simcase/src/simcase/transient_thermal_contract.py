# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict serializable transient rectangle inputs; no solver or persistence.

Temperatures are finite Kelvin, including negative mathematical values. Initial
data are never projected. Time-dependent side data are samples at the requested
times, with no interpolation, extrapolation, or serialized callback language.
Outward flux and convection sides reuse the steady boundary contract's readers
(same keys, limits and messages) and are time-independent constants; a document
that carries either key saves the boundary result/layout pair ``V2``.
"""
import math
import sys
from collections.abc import Mapping

import numpy as np

from . import units, views
from .schema import DocumentError
from .steady_boundary_contract import (
    has_natural_conditions, natural_conditions, rectangle_exterior_edges, validate_natural_edges,
)

PHYSICS = "thermal.transient2d"
RESULT_FORMAT = "thermal.transient2d-result-v1"
FIELD_LAYOUT = "thermal2d-transient-p1-node-cell-v1"
V1 = (RESULT_FORMAT, FIELD_LAYOUT)
V2 = ("thermal.transient2d-result-v2", "thermal2d-transient-p1-node-cell-boundary-v1")
SIDES = ("left", "right", "bottom", "top")


def is_transient_thermal(data):
    return (isinstance(data, dict) and isinstance(data.get("physics"), dict)
            and any(isinstance(p, dict) and p.get("type") == PHYSICS
                    for p in data["physics"].values()))


def defaults():
    return {"openphysics": "0.2", "name": "untitled",
            "geometry": {"domain": None}, "materials": {}, "physics": {},
            "mesh": {}, "study": {"type": "transient"},
            "results": {"save_fields": True, "plots": False}}


def _object(value, allowed, path, required=()):
    if not isinstance(value, dict):
        raise DocumentError(f"{path}: expected an object")
    unknown = set(value)-set(allowed)
    if unknown:
        raise DocumentError(f"{path}: unsupported keys {sorted(map(str, unknown))}")
    missing = set(required)-set(value)
    if missing:
        raise DocumentError(f"{path}: missing keys {sorted(missing)}")


def _number(value, path, *, positive=False, integer=False):
    try:
        finite = (isinstance(value, (int, float)) and not isinstance(value, bool)
                  and math.isfinite(value))
    except OverflowError:
        finite = False
    if (not finite or (positive and value <= 0)
            or (integer and not isinstance(value, int))):
        kind = "positive integer" if integer else "positive number" if positive else "number"
        raise DocumentError(f"{path}: expected a finite {kind}")
    return float(value)


def _array(value, path, length=None):
    if not isinstance(value, list) or (length is not None and len(value) != length):
        shape = f"exactly {length} entries" if length is not None else "an array"
        raise DocumentError(f"{path}: expected {shape}")
    return [_number(v, f"{path}[{i}]") for i, v in enumerate(value)]


def _domain(doc):
    dom = doc.data["geometry"]["domain"]
    p = {key: _number(doc.scale.to_si(value, {"length": 1}),
                      f"geometry.domain.{key} in metres") for key, value in dom.items()}
    lengths = []
    for axis in "xy":
        extent = _number(dom[axis+"max"]-dom[axis+"min"],
                         f"geometry.domain.{axis} extent", positive=True)
        length = _number(doc.scale.to_si(extent, {"length": 1}),
                         f"geometry.domain.{axis} extent in metres", positive=True)
        _number(p[axis+"min"]+length, f"geometry.domain.{axis} endpoint in metres")
        if not p[axis+"min"] < p[axis+"min"]+length:
            raise DocumentError(f"geometry.domain.{axis}: SI extent is not representable")
        lengths.append(length)
    return p["xmin"], p["ymin"], lengths[0], lengths[1]


def _initial_value(spec, x, y, origin):
    if isinstance(spec, dict):
        gx, gy = spec["gradient_k_per_m"]
        return spec["origin_temperature_k"]+gx*(x-origin[0])+gy*(y-origin[1])
    return spec


def _samples(value, times, path):
    if isinstance(value, dict):
        _object(value, {"values_k"}, path, {"values_k"})
        return _array(value["values_k"], path+".values_k", len(times))
    return [_number(value, path)]*len(times)


def _agree(initial, prescribed):
    return abs(initial-prescribed) <= 32*sys.float_info.epsilon*max(
        1., abs(initial), abs(prescribed))


def validate_transient_thermal(doc):
    d = doc.data
    _object(d, {"openphysics", "name", "units", "geometry", "materials",
                "physics", "mesh", "study", "results"}, "document",
            {"openphysics", "name", "units", "geometry", "materials", "physics",
             "mesh", "study", "results"})
    if d["openphysics"] != "0.2":
        raise DocumentError('openphysics: expected format string "0.2"')
    if not isinstance(d["name"], str):
        raise DocumentError("name: expected a string")
    _object(d["units"], {"length", "temperature", "time"}, "units",
            {"length", "temperature", "time"})
    if d["units"]["temperature"] != "K" or d["units"]["time"] != "s":
        raise DocumentError('thermal.transient2d requires temperature="K" and time="s"')
    try:
        doc.scale = units.resolve(d["units"])
    except (units.UnitError, OverflowError, TypeError, ValueError) as exc:
        raise DocumentError(f"units: {exc}") from exc
    _object(d["geometry"], {"domain"}, "geometry", {"domain"})
    dom = d["geometry"]["domain"]
    _object(dom, {"xmin", "xmax", "ymin", "ymax"}, "geometry.domain",
            {"xmin", "xmax", "ymin", "ymax"})
    for key, value in dom.items():
        _number(value, f"geometry.domain.{key}")
    origin_x, origin_y, lx, ly = _domain(doc)
    if not isinstance(d["materials"], dict) or d["materials"]:
        raise DocumentError("materials: transient heat requires an empty object")
    _object(d["mesh"], {"subdivisions"}, "mesh", {"subdivisions"})
    subdivisions = d["mesh"]["subdivisions"]
    if not isinstance(subdivisions, list) or len(subdivisions) != 2:
        raise DocumentError("mesh.subdivisions: expected [nx, ny]")
    for i, value in enumerate(subdivisions):
        _number(value, f"mesh.subdivisions[{i}]", positive=True, integer=True)
    _object(d["study"], {"type", "time_s"}, "study", {"type", "time_s"})
    if d["study"]["type"] != "transient":
        raise DocumentError('study.type: expected "transient"')
    times = _array(d["study"]["time_s"], "study.time_s")
    if len(times) < 2 or times[0] < 0:
        raise DocumentError("study.time_s: need at least two nonnegative increasing seconds")
    for i, (a, b) in enumerate(zip(times, times[1:]), 1):
        _number(b-a, f"study.time_s step[{i}]", positive=True)
    if not isinstance(d["physics"], dict) or len(d["physics"]) != 1:
        raise DocumentError("physics: exactly one transient heat entry is required")
    name, p = next(iter(d["physics"].items()))
    if not isinstance(name, str) or not name.isidentifier():
        raise DocumentError("physics name must be an identifier")
    where = f"physics.{name}"
    keys = {"type", "conductivity_w_mk", "volumetric_heat_capacity_j_m3k",
            "initial_temperature_k", "dirichlet_temperature_k", "heat_source_w_m3"}
    _object(p, keys | {"outward_flux_w_m2", "convection"}, where, keys-{"heat_source_w_m3"})
    if p["type"] != PHYSICS:
        raise DocumentError(f"{where}.type: expected {PHYSICS}")
    for key in ("conductivity_w_mk", "volumetric_heat_capacity_j_m3k"):
        _number(p[key], f"{where}.{key}", positive=True)
    p.setdefault("heat_source_w_m3", 0.)
    _number(p["heat_source_w_m3"], where+".heat_source_w_m3")
    spec = p["initial_temperature_k"]
    initial_path = where+".initial_temperature_k"
    if isinstance(spec, dict):
        _object(spec, {"type", "origin_temperature_k", "gradient_k_per_m"}, initial_path,
                {"type", "origin_temperature_k", "gradient_k_per_m"})
        if spec["type"] != "affine":
            raise DocumentError(f"{initial_path}.type: expected affine")
        _number(spec["origin_temperature_k"], initial_path+".origin_temperature_k")
        _array(spec["gradient_k_per_m"], initial_path+".gradient_k_per_m", 2)
    else:
        _number(spec, initial_path)
    corners = ((origin_x, origin_y), (origin_x, origin_y+ly),
               (origin_x+lx, origin_y), (origin_x+lx, origin_y+ly))
    initial = [_number(_initial_value(spec, x, y, (origin_x, origin_y)),
                       initial_path+" at domain corner") for x, y in corners]
    side_corners = {"left": (0, 1), "right": (2, 3), "bottom": (0, 2), "top": (1, 3)}
    boundary = p["dirichlet_temperature_k"]
    _object(boundary, SIDES, where+".dirichlet_temperature_k")
    sampled = {tag: _samples(value, times, where+".dirichlet_temperature_k."+tag)
               for tag, value in boundary.items()}
    for horizontal in ("left", "right"):
        for vertical in ("bottom", "top"):
            if (horizontal in sampled and vertical in sampled
                    and sampled[horizontal] != sampled[vertical]):
                raise DocumentError(f"{where}.dirichlet_temperature_k: conflicting corner "
                                    f"temperatures on {horizontal}/{vertical}")
    for tag, values in sampled.items():
        if any(not _agree(initial[i], values[0]) for i in side_corners[tag]):
            raise DocumentError(f"{where}.dirichlet_temperature_k.{tag}: initial t0 mismatch "
                                "(32 eps bound); no projection")
    # Same reader as thermal.steady2d: constant g and (h, ambient) per side, no
    # time samples. The mass/time term keeps the system well posed, so no anchor
    # is required and h=0 is only an insulated side.
    natural_conditions(p, where, sampled)
    _object(d["results"], {"save_fields", "plots"}, "results", {"save_fields", "plots"})
    if any(not isinstance(d["results"][key], bool) for key in ("save_fields", "plots")):
        raise DocumentError("results.save_fields and results.plots must be booleans")
    if d["results"]["plots"]:
        raise DocumentError("results.plots: transient heat is headless; plots=true unsupported")
    doc.notes = []


def transient_result_versions(doc):
    """Return the (result_format, field_layout) pair a validated document saves.

    Presence of ``outward_flux_w_m2`` or ``convection`` selects ``V2``; every
    other document keeps the legacy ``V1`` identifiers and arrays.
    """
    doc.validate()
    return V2 if has_natural_conditions(doc.sole_physics()[1]) else V1


def transient_solver_inputs(doc, mesh):
    """Return copied keyword arguments for solve_transient_heat(mesh, **kwargs).

    The caller constructs its SI rectangle mesh. Initial data are evaluated by
    coordinates, never by assumed node ordering. Only requested-time lookup is
    supported for sampled side data. No engine or file operation is performed.
    With ``outward_flux_w_m2`` or ``convection`` the result also carries the
    engine's ``outward_flux`` and ``convection`` mappings over complete exterior
    sides of ``mesh.boundary_edges``, validated as in the steady contract;
    without them the six legacy keywords are returned unchanged.
    """
    doc.validate()
    name, p = doc.sole_physics()
    if p["type"] != PHYSICS:
        raise DocumentError(f"physics.{name}.type: expected {PHYSICS}")
    nodes = np.asarray(getattr(mesh, "nodes", None))
    if (nodes.ndim != 2 or nodes.shape[1] != 2 or nodes.dtype.kind not in "iuf"
            or not np.isfinite(nodes).all() or len(nodes) < 3):
        raise DocumentError("mesh.nodes: expected finite (N,2) SI coordinates")
    nodes = np.asarray(nodes, dtype=float).copy()
    # the contract's extent converts max - min (views.LENGTH_FORMULAS)
    grid, heat = views.rectangle_mesh(doc, "difference"), views.transient_rectangle_heat(doc)
    (x0, y0), (lx, ly) = grid.origin, grid.lengths
    tolerance = 64*np.finfo(float).eps*np.maximum(np.abs([x0, y0]), [lx, ly])
    if (np.any(nodes < np.array([x0, y0])-tolerance)
            or np.any(nodes > np.array([x0+lx, y0+ly])+tolerance)):
        raise DocumentError("mesh.nodes: coordinates outside the declared SI rectangle")
    times = heat.time
    spec = heat.initial_temperature
    with np.errstate(over="ignore", invalid="ignore"):
        initial = (np.full(len(nodes), spec) if not isinstance(spec, views.AffineTemperature)
                   else spec.origin_temperature + (nodes-np.array([x0, y0]))@spec.gradient)
    if not np.isfinite(initial).all():
        raise DocumentError("initial_temperature_k: nonfinite field at mesh nodes")
    sampled_nodes = {}
    boundary_nodes = getattr(mesh, "boundary", None)
    if not isinstance(boundary_nodes, Mapping):
        raise DocumentError("mesh.boundary: expected a mapping of exterior sides")
    side_axis_value = {"left": (0, x0), "right": (0, x0+lx),
                       "bottom": (1, y0), "top": (1, y0+ly)}
    for tag, values in heat.dirichlet.items():
        ids = np.asarray(boundary_nodes.get(tag, []))
        if (ids.ndim != 1 or not len(ids) or ids.dtype.kind not in "iu"
                or np.any(ids < 0) or np.any(ids >= len(nodes))
                or len(np.unique(ids)) != len(ids)):
            raise DocumentError(f"mesh.boundary.{tag}: expected unique valid integer indices")
        axis, location = side_axis_value[tag]
        if np.any(abs(nodes[ids, axis]-location) > tolerance[axis]):
            raise DocumentError(f"mesh.boundary.{tag}: nodes not on declared SI side")
        expected = np.flatnonzero(abs(nodes[:, axis]-location) <= tolerance[axis])
        if not np.array_equal(np.sort(ids), expected):
            raise DocumentError(f"mesh.boundary.{tag}: selection must cover the complete side")
        for node in ids:
            node = int(node)
            if node in sampled_nodes and sampled_nodes[node] != values:
                raise DocumentError(f"mesh.boundary.{tag}: conflicting corner node {node}")
            if not _agree(float(initial[node]), values[0]):
                raise DocumentError(f"mesh.boundary.{tag}: initial t0 mismatch; no projection")
            sampled_nodes[node] = values

    def lookup(values):
        table = dict(zip(map(float, times), values))
        def at_time(time_s):
            if not isinstance(time_s, (int, float)) or isinstance(time_s, bool):
                raise ValueError("boundary callback expects one requested scalar time")
            try:
                return table[float(time_s)]
            except KeyError as exc:
                raise ValueError("boundary time not in requested samples; no interpolation") from exc
        return at_time

    boundary = {node: (values[0] if all(v == values[0] for v in values) else lookup(values))
                for node, values in sorted(sampled_nodes.items())}
    inputs = {"conductivity": heat.conductivity,
              "volumetric_heat_capacity": heat.volumetric_heat_capacity,
              "time_s": times, "initial_temperature_k": initial.copy(),
              "dirichlet": boundary, "heat_source": heat.heat_source}
    if heat.boundary_layout:
        lower, upper = np.array([x0, y0]), np.array([x0+lx, y0+ly])
        exterior = rectangle_exterior_edges(mesh, lower, upper)
        validate_natural_edges(mesh, *exterior, sampled_nodes, heat.outward_flux, heat.convection)
        inputs.update(outward_flux=dict(heat.outward_flux), convection=dict(heat.convection))
    return inputs


def transient_thermal_summary(doc):
    from .transient_regions import is_transient_region_thermal, transient_region_summary
    if is_transient_region_thermal(doc.data):
        return transient_region_summary(doc)
    name, p = doc.sole_physics()
    times = doc["study"]["time_s"]
    natural = ''
    if has_natural_conditions(p):
        natural = (f'  outward flux {p.get("outward_flux_w_m2", {})} W/m^2; '
                   f'convection {p.get("convection", {})}\n'
                   '  q.n = g_out + h*(T-T_ambient), sampled once; unselected natural sides insulated\n')
    return (f'{doc["name"]} (openphysics 0.2)\n'
            f'  physics {name}: {PHYSICS}, {len(times)} explicit times in s\n'
            f'  domain {doc.domain} {doc.length_unit}; mesh {doc["mesh"]["subdivisions"]}\n'
            f'  k={p["conductivity_w_mk"]} W/(m K), '
            f'c={p["volumetric_heat_capacity_j_m3k"]} J/(m^3 K)\n'
            + natural +
            '  output: SI time/node/cell histories; rates at interval ends only')

