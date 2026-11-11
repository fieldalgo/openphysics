# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict serializable transient rectangle inputs; no solver or persistence.

Format 0.3 rectangle documents are checked on their SI values (the section at the end);
every absolute temperature is above 0 K; region documents are checked in
``transient_regions``.

Initial data are never projected. Time-dependent side data are samples at the requested
times, with no interpolation, extrapolation, or serialized callback language.
Inward flux and convection sides reuse the steady boundary contract's readers
(same keys, limits and messages) and are time-independent constants; a document
that carries either key saves the boundary result/layout pair ``V2_03``.
"""
import math
import sys
from collections.abc import Mapping

import numpy as np

from . import views
from .schema import DocumentError
from .steady_boundary_contract import rectangle_exterior_edges, validate_natural_edges

PHYSICS = "thermal.transient2d"
SIDES = ("left", "right", "bottom", "top")


def is_transient_thermal(data):
    return (isinstance(data, dict) and isinstance(data.get("physics"), dict)
            and any(isinstance(p, dict) and p.get("type") == PHYSICS
                    for p in data["physics"].values()))


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


def _agree(initial, prescribed):
    return abs(initial-prescribed) <= 32*sys.float_info.epsilon*max(
        1., abs(initial), abs(prescribed))


def transient_result_versions(doc):
    """Return the (result_format, field_layout) pair a validated document saves.

    Presence of ``inward_heat_flux`` or ``convection`` selects ``V2_03``; every
    other document saves ``V1_03``.
    """
    from .steady_boundary_contract import has_natural_conditions_03
    doc.validate()
    return V2_03 if has_natural_conditions_03(doc.sole_physics()[1]) else V1_03


def transient_solver_inputs(doc, mesh):
    """Return copied keyword arguments for solve_transient_heat(mesh, **kwargs).

    The caller constructs its SI rectangle mesh. Initial data are evaluated by
    coordinates, never by assumed node ordering. Only requested-time lookup is
    supported for sampled side data. No engine or file operation is performed.
    With ``inward_heat_flux`` or ``convection`` the result also carries the
    engine's ``outward_flux`` and ``convection`` mappings over complete exterior
    sides of ``mesh.boundary_edges``, validated as in the steady contract;
    without them the six engine keywords are returned.
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
        raise DocumentError("initial_temperature: nonfinite field at mesh nodes")
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
    from .steady_boundary_contract import has_natural_conditions_03
    from .thermal import _authored, rectangle_summary_03
    from .transient_regions import is_transient_region_thermal, transient_region_summary_03
    doc.validate()                    # a document that was not read as format 0.3 is refused by name
    if is_transient_region_thermal(doc.data):
        return transient_region_summary_03(doc)
    name = next(iter(doc.si["physics"]))
    where = f"physics.{name}"
    times = doc.si["study"]["time"]
    initial = doc.si["physics"][name]["initial_temperature"]
    initial_text = ("affine from " + _authored(doc, where + ".initial_temperature.reference_temperature")
                    if isinstance(initial, dict) else _authored(doc, where + ".initial_temperature"))
    return rectangle_summary_03(doc, f"{PHYSICS}, {len(times)} explicit times", [
        f"  volumetric_heat_capacity {_authored(doc, where + '.volumetric_heat_capacity')}; "
        f"initial_temperature {initial_text}; study.time {_authored(doc, 'study.time')}",
        "  rates at interval ends only"],
        V2_03 if has_natural_conditions_03(doc.si["physics"][name]) else V1_03)


# -- format 0.3 ------------------------------------------------------------------------------------
#
# A format 0.3 rectangle document is read by ``simcase.resolve`` against
# ``steady_boundary_contract.heat_slots(PHYSICS, transient=True)``; these checks run on its SI
# values. Absolute temperatures are now above 0 K (the registry domain).

V1_03 = ("thermal.transient2d-result-v3", "thermal2d-transient-p1-node-cell-v2")
V2_03 = ("thermal.transient2d-result-v4", "thermal2d-transient-p1-node-cell-boundary-v2")


def _initial_03(spec, path):
    if isinstance(spec, dict):
        gradient = spec["temperature_gradient"]
        if len(gradient) != 2:
            raise DocumentError(f"{path}.temperature_gradient: expected exactly 2 entries (x, y)")
        return views.AffineTemperature(float(spec["reference_temperature"]), np.array(gradient, dtype=float))
    return float(spec)


def _initial_value_03(spec, x, y, origin):
    if isinstance(spec, views.AffineTemperature):
        gx, gy = map(float, spec.gradient)     # Python floats overflow to inf without a warning
        return spec.origin_temperature+gx*(x-origin[0])+gy*(y-origin[1])
    return spec


def _samples_03(value, times, path):
    if isinstance(value, list):
        if len(value) != len(times):
            raise DocumentError(f"{path}.values: expected exactly {len(times)} entries, one per study time")
        return [float(v) for v in value]
    return [float(value)]*len(times)


def study_times_03(doc):
    """The study times of a format 0.3 transient document (SI seconds): at least two, strictly
    increasing; the registry has checked that each is finite and nonnegative."""
    study = doc.si["study"]
    if study.get("type") != "transient":
        raise DocumentError('study.type: expected "transient"')
    extra = sorted(set(study) - {"type", "time"})
    if extra:
        raise DocumentError(f"study: unsupported keys {extra}; a transient study takes type and time")
    if "time" not in study:
        raise DocumentError("study.time: a transient study needs its times", path="study.time", code="E-KEY-MISSING")
    times = study["time"]
    if len(times) < 2:
        raise DocumentError("study.time: need at least two nonnegative increasing times")
    for i, (a, b) in enumerate(zip(times, times[1:]), 1):
        if not (math.isfinite(b-a) and b-a > 0):
            raise DocumentError(f"study.time step[{i}]: expected increasing times", path=f"study.time.values[{i}]")
    return times


def validate_transient_rectangle_03(doc):
    """thermal.transient2d on a rectangle, format 0.3: today's contract on SI values."""
    from .steady_boundary_contract import _temperatures_03, natural_conditions_03, rectangle_03
    name, p = rectangle_03(doc, "transient heat", ("thermal_conductivity", "volumetric_heat_capacity"))
    where = f"physics.{name}"
    times = study_times_03(doc)
    grid = views.rectangle_mesh(doc, "difference")
    (origin_x, origin_y), (lx, ly) = grid.origin, grid.lengths
    spec = _initial_03(p["initial_temperature"], where+".initial_temperature")
    corners = ((origin_x, origin_y), (origin_x, origin_y+ly),
               (origin_x+lx, origin_y), (origin_x+lx, origin_y+ly))
    initial = [_number(_initial_value_03(spec, x, y, (origin_x, origin_y)),
                       where+".initial_temperature at domain corner") for x, y in corners]
    side_corners = {"left": (0, 1), "right": (2, 3), "bottom": (0, 2), "top": (1, 3)}
    boundary = _temperatures_03(p, where)
    sampled = {tag: _samples_03(value, times, where+".prescribed_temperature."+tag)
               for tag, value in boundary.items()}
    for horizontal in ("left", "right"):
        for vertical in ("bottom", "top"):
            if (horizontal in sampled and vertical in sampled
                    and sampled[horizontal] != sampled[vertical]):
                raise DocumentError(f"{where}.prescribed_temperature: conflicting corner "
                                    f"temperatures on {horizontal}/{vertical}")
    for tag, values in sampled.items():
        if any(not _agree(initial[i], values[0]) for i in side_corners[tag]):
            raise DocumentError(f"{where}.prescribed_temperature.{tag}: initial t0 mismatch "
                                "(32 eps bound); no projection")
    # Constant g and (h, ambient) per side, as for steady heat; no anchor is required.
    natural_conditions_03(p, where, sampled)
    from .thermal_regions import default_boundaries_03
    default_boundaries_03(doc, name, p, SIDES)


def transient_heat_inputs_03(doc):
    """The heat inputs (``views.HeatInputs``) of a validated format 0.3 transient rectangle."""
    from .steady_boundary_contract import has_natural_conditions_03, natural_conditions_03
    name, p = next(iter(doc.si["physics"].items()))
    where = f"physics.{name}"
    times = np.array(doc.si["study"]["time"], dtype=float, copy=True)
    dirichlet = {tag: tuple(_samples_03(value, times, f"{where}.prescribed_temperature.{tag}"))
                 for tag, value in p["prescribed_temperature"].items()}
    natural = has_natural_conditions_03(p)
    flux, convection = natural_conditions_03(p, where, dirichlet) if natural else ({}, {})
    source = p.get("heat_source_density")
    return views.HeatInputs(conductivity=float(p["thermal_conductivity"]),
                            heat_source=0.0 if source is None else float(source),     # hazard H9
                            dirichlet=dirichlet, outward_flux=flux, convection=convection, boundary_layout=natural,
                            volumetric_heat_capacity=float(p["volumetric_heat_capacity"]), time=times,
                            initial_temperature=_initial_03(p["initial_temperature"],
                                                            where+".initial_temperature"))
