# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict steady rectangle boundary inputs, independent of schema dispatch.

The public document reader is connected separately. These helpers read a
Document without mutating its data, scale or notes. They do not solve or save.
"""
import math
from collections.abc import Mapping
from itertools import combinations

import numpy as np

from . import units
from .schema import DocumentError

PHYSICS = "thermal.steady2d"
SIDES = ("left", "right", "bottom", "top")
V1 = ("thermal.steady2d-result-v1", "thermal2d-p1-node-cell-v1")
V2 = ("thermal.steady2d-result-v2", "thermal2d-p1-node-cell-boundary-v2")


def _object(value, allowed, path, required=()):
    if not isinstance(value, dict):
        raise DocumentError(f"{path}: expected an object")
    if set(value)-set(allowed):
        raise DocumentError(f"{path}: unsupported keys {sorted(map(str, set(value)-set(allowed)))}")
    if set(required)-set(value):
        raise DocumentError(f"{path}: missing keys {sorted(set(required)-set(value))}")


def _number(value, path, *, positive=False, nonnegative=False, integer=False):
    try:
        ok = (isinstance(value, (int, float)) and not isinstance(value, bool)
              and math.isfinite(value))
    except OverflowError:
        ok = False
    if (not ok or (positive and value <= 0) or (nonnegative and value < 0)
            or (integer and not isinstance(value, int))):
        raise DocumentError(f"{path}: expected a finite valid "
                            + ("positive integer" if integer else "number"))
    return float(value)


def _validated(doc):
    d = getattr(doc, "data", None)
    top = {"openphysics", "name", "units", "geometry", "materials", "physics",
           "mesh", "study", "results"}
    _object(d, top, "document", top)
    if d["openphysics"] != "0.2" or not isinstance(d["name"], str):
        raise DocumentError('document: expected format "0.2" and a string name')
    _object(d["units"], {"length", "temperature"}, "units", {"length", "temperature"})
    if d["units"]["temperature"] != "K":
        raise DocumentError('units.temperature: expected "K"')
    try:
        scale = units.resolve(d["units"])
    except (units.UnitError, TypeError, ValueError, OverflowError) as exc:
        raise DocumentError(f"units: {exc}") from exc
    _object(d["geometry"], {"domain"}, "geometry", {"domain"})
    dom = d["geometry"]["domain"]
    keys = {"xmin", "xmax", "ymin", "ymax"}
    _object(dom, keys, "geometry.domain", keys)
    bounds = {}
    for key in keys:
        value = _number(dom[key], "geometry.domain."+key)
        bounds[key] = _number(scale.to_si(value, {"length": 1}),
                              "geometry.domain."+key+" in metres")
    for axis in "xy":
        _number(dom[axis+"max"]-dom[axis+"min"], "geometry.domain."+axis+" extent", positive=True)
        _number(bounds[axis+"max"]-bounds[axis+"min"],
                "geometry.domain."+axis+" SI extent", positive=True)
    _object(d["materials"], set(), "materials")
    _object(d["mesh"], {"subdivisions"}, "mesh", {"subdivisions"})
    counts = d["mesh"]["subdivisions"]
    if not isinstance(counts, list) or len(counts) != 2:
        raise DocumentError("mesh.subdivisions: expected [nx, ny]")
    for i, value in enumerate(counts):
        _number(value, f"mesh.subdivisions[{i}]", positive=True, integer=True)
    _object(d["study"], {"type"}, "study", {"type"})
    if d["study"]["type"] != "single":
        raise DocumentError('study.type: expected "single"')
    _object(d["results"], {"save_fields", "plots"}, "results", {"save_fields", "plots"})
    if any(not isinstance(d["results"][k], bool) for k in ("save_fields", "plots")):
        raise DocumentError("results: expected boolean save_fields and plots")
    if d["results"]["plots"]:
        raise DocumentError("results.plots: steady heat is headless")
    physics = d["physics"]
    if not isinstance(physics, dict) or len(physics) != 1:
        raise DocumentError("physics: exactly one steady heat entry required")
    name, p = next(iter(physics.items()))
    if not isinstance(name, str) or not name.isidentifier():
        raise DocumentError("physics: name must be an identifier")
    path = "physics."+name
    required = {"type", "conductivity_w_mk", "dirichlet_temperature_k"}
    _object(p, required | {"heat_source_w_m3", "outward_flux_w_m2", "convection"},
            path, required)
    if p["type"] != PHYSICS:
        raise DocumentError(path+".type: expected "+PHYSICS)
    k = _number(p["conductivity_w_mk"], path+".conductivity_w_mk", positive=True)
    q = _number(p.get("heat_source_w_m3", 0.), path+".heat_source_w_m3")
    bc = p["dirichlet_temperature_k"]
    _object(bc, SIDES, path+".dirichlet_temperature_k")
    prescribed = {tag: _number(value, path+".dirichlet_temperature_k."+tag, nonnegative=True)
                  for tag, value in bc.items()}
    for a in ("left", "right"):
        for b in ("bottom", "top"):
            if a in prescribed and b in prescribed and prescribed[a] != prescribed[b]:
                raise DocumentError(path+".dirichlet_temperature_k: conflicting corner")
    flux = p.get("outward_flux_w_m2", {})
    _object(flux, SIDES, path+".outward_flux_w_m2")
    flux = {tag: _number(value, path+".outward_flux_w_m2."+tag) for tag, value in flux.items()}
    robin = p.get("convection", {})
    _object(robin, SIDES, path+".convection")
    convection = {}
    for tag, value in robin.items():
        where = path+".convection."+tag
        members = {"h_w_m2k", "ambient_temperature_k"}
        _object(value, members, where, members)
        h = _number(value["h_w_m2k"], where+".h_w_m2k", nonnegative=True)
        ambient = _number(value["ambient_temperature_k"], where+".ambient_temperature_k", nonnegative=True)
        convection[tag] = (h, ambient)
    if not prescribed and not any(h > 0 for h, _ in convection.values()):
        raise DocumentError(path+": requires Dirichlet or positive Robin anchor; pure Neumann unsupported")
    if set(prescribed) & (set(flux) | set(convection)):
        raise DocumentError(path+": natural condition overlaps a fully Dirichlet side")
    versions = V2 if "outward_flux_w_m2" in p or "convection" in p else V1
    return bounds, prescribed, k, q, flux, convection, versions


def validate_steady_boundary(doc):
    """Validate complete normalized document values without modifying the input.

    Nonnegative prescribed/ambient Kelvin is a document policy; the unchanged
    engine permits finite mathematical Kelvin and does not clamp the solution.
    Empty natural mappings select v2 by presence but do not provide an anchor.
    """
    _validated(doc)


def steady_result_versions(doc):
    """Return independent result/layout IDs; absent new keys keep legacy v1."""
    return _validated(doc)[-1]


def steady_boundary_inputs(doc, mesh):
    """Return five copied solve_steady_heat keyword arguments, never a solution.

    Dirichlet selects complete node sides; natural conditions select actual
    boundary_edges tags. Fully fixed natural edges reject; a single fixed
    endpoint retains its consistent load. Mesh geometry is validated by the
    existing engine, with no new solver or assembly.
    """
    bounds, side_bc, k, q, flux, convection, _ = _validated(doc)
    lower = np.array([bounds["xmin"], bounds["ymin"]])
    upper = np.array([bounds["xmax"], bounds["ymax"]])
    extent = upper-lower
    tol = 64*np.finfo(float).eps*np.maximum(np.maximum(abs(lower), abs(upper)), extent)
    # Finite endpoints alone do not guarantee distinguishable opposite sides.
    # Keep the existing roundoff budget, but reject before it can span both
    # sides. Never silently enlarge/shrink that budget to accept ambiguous data.
    if np.any(tol >= extent/2):
        raise DocumentError("mesh: insufficient coordinate precision to distinguish "
                            "opposite rectangle sides; use a smaller coordinate origin")
    from galerkin.core.triangles import triangle_geometry
    try:
        p, t, area, _, count, _ = triangle_geometry(mesh)
    except (ValueError, TypeError, IndexError, AttributeError, OverflowError) as exc:
        raise DocumentError(f"mesh: {exc}") from exc
    if count != 1:
        raise DocumentError("mesh: rectangle must be connected")
    if np.any(p < lower-tol) or np.any(p > upper+tol):
        raise DocumentError("mesh.nodes: outside declared SI rectangle")
    axes = {"left": (0, lower[0]), "right": (0, upper[0]),
            "bottom": (1, lower[1]), "top": (1, upper[1])}
    owners = {}
    for tri in t:
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((int(tri[a]), int(tri[b]))))
            owners[edge] = owners.get(edge, 0)+1
    exterior = {edge for edge, n in owners.items() if n == 1}
    expected_edges = {tag: {edge for edge in exterior
                            if np.all(abs(p[list(edge), axis]-value) <= tol[axis])}
                      for tag, (axis, value) in axes.items()}
    # Each actual exterior edge must belong to exactly one side, including
    # adjacent sides: a short corner edge can fit both tolerance bands.
    if any(expected_edges[a] & expected_edges[b] for a, b in combinations(SIDES, 2)):
        raise DocumentError("mesh: insufficient coordinate precision; ambiguous "
                            "rectangle side edge classification")
    if (set().union(*expected_edges.values()) != exterior
            or any(not edges for edges in expected_edges.values())
            or not np.isclose(area.sum(), np.prod(upper-lower), rtol=1e-12, atol=0)):
        raise DocumentError("mesh: must cover the complete rectangle without holes")
    node_tags, edge_tags = getattr(mesh, "boundary", None), getattr(mesh, "boundary_edges", None)
    if not isinstance(node_tags, Mapping) or not isinstance(edge_tags, Mapping):
        raise DocumentError("mesh: boundary node and edge mappings required")
    prescribed = {}
    for tag, value in side_bc.items():
        ids = np.asarray(node_tags.get(tag, []))
        # Boundary identity comes from verified exterior edges, not a broad
        # coordinate mask that could also include nearby interior nodes.
        expected = np.array(sorted({node for edge in expected_edges[tag] for node in edge}),
                            dtype=int)
        if (ids.ndim != 1 or ids.dtype.kind not in "iu" or len(ids) != len(expected)
                or len(np.unique(ids)) != len(ids) or np.any(ids < 0) or np.any(ids >= len(p))
                or not np.array_equal(np.sort(ids), expected)):
            raise DocumentError(f"mesh.boundary.{tag}: expected the complete unique SI side")
        for node in ids:
            if int(node) in prescribed and prescribed[int(node)] != value:
                raise DocumentError("mesh.boundary: conflicting Dirichlet corner")
            prescribed[int(node)] = value
    # Validate each condition kind independently: one flux plus one Robin is additive.
    for label, conditions in (("outward_flux", flux), ("convection", convection)):
        seen = set()
        for tag in conditions:
            edges = np.asarray(edge_tags.get(tag, []))
            if (edges.ndim != 2 or edges.shape[1] != 2 or not len(edges)
                    or edges.dtype.kind not in "iu" or np.any(edges < 0) or np.any(edges >= len(p))):
                raise DocumentError(f"mesh.boundary_edges.{tag}: expected valid integer (E,2)")
            found = set()
            for a, b in edges:
                edge = tuple(sorted((int(a), int(b))))
                if a == b or owners.get(edge) != 1 or edge in seen:
                    raise DocumentError(f"mesh.boundary_edges.{tag}: invalid or duplicate {label} edge")
                if int(a) in prescribed and int(b) in prescribed:
                    raise DocumentError(f"mesh.boundary_edges.{tag}: natural edge is fully Dirichlet")
                seen.add(edge)
                found.add(edge)
            if found != expected_edges[tag]:
                raise DocumentError(f"mesh.boundary_edges.{tag}: selection must cover the complete SI side")
    return {"conductivity": k, "dirichlet": dict(sorted(prescribed.items())),
            "heat_source": q, "outward_flux": dict(flux), "convection": dict(convection)}
