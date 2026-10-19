# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Single rectangular cavity studies and their explicit SI output contract.

A vacuum PEC box keeps the original real-valued result layout. Box-shaped
materials, a non-vacuum background or finite-conductivity walls use the complex
material cavity solver and the complex layout ``cavity3d-edge-complex-v1``.
"""

from __future__ import annotations

import copy
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .schema import Document, DocumentError

if TYPE_CHECKING:
    from galerkin import CavityResult


def _object(value, allowed, path):
    if not isinstance(value, dict):
        raise DocumentError(f"{path}: expected an object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise DocumentError(f"{path}: unsupported cavity keys {sorted(unknown)}")


def _number(value, path, *, positive=False, integer=False):
    try:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or (positive and value <= 0) or (integer and int(value) != value):
        kind = "positive integer" if integer else "finite positive number" if positive else "finite number"
        raise DocumentError(f"{path}: expected a {kind}")


WALL_NAMES = {"xmin": "x0", "xmax": "x1", "ymin": "y0", "ymax": "y1", "zmin": "z0", "zmax": "z1"}
_GRID_TOLERANCE = 1e-9


def _complex_constant(value, path):
    """A JSON real number or [real, imag] pair; passive under exp(+j*omega*t)."""
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise DocumentError(f"{path}: expected a number or [real, imag]")
        _number(value[0], f"{path}[0]", positive=True)
        _number(value[1], f"{path}[1]")
        if value[1] > 0:
            raise DocumentError(f"{path}[1]: imaginary part must be <= 0 (passive, exp(+j*omega*t))")
        return complex(value[0], value[1])
    _number(value, path, positive=True)
    return complex(value)


def _cavity_materials(d):
    materials = d["materials"]
    if not isinstance(materials, dict):
        raise DocumentError("materials: expected an object")
    resolved = {}
    for name, spec in materials.items():
        path = f"materials.{name}"
        if not isinstance(name, str) or not name or name == "vacuum":
            raise DocumentError(f"{path}: material names must be non-empty and not 'vacuum'")
        _object(spec, {"relative_permittivity", "relative_permeability"}, path)
        if "relative_permittivity" not in spec:
            raise DocumentError(f"{path}: relative_permittivity is required")
        resolved[name] = (_complex_constant(spec["relative_permittivity"], f"{path}.relative_permittivity"),
                          _complex_constant(spec.get("relative_permeability", 1.0),
                                            f"{path}.relative_permeability"))
    return resolved


def _cavity_boundary(boundary, path):
    """'pec', or {"conductivity_s_per_m": S/m or {wall: S/m}} with walls xmin..zmax."""
    if boundary == "pec":
        return None
    _object(boundary, {"conductivity_s_per_m"}, path)
    value = boundary.get("conductivity_s_per_m")
    if isinstance(value, dict):
        if not value:
            raise DocumentError(f"{path}.conductivity_s_per_m: name at least one wall")
        unknown = set(value) - set(WALL_NAMES)
        if unknown:
            raise DocumentError(f"{path}.conductivity_s_per_m: unknown walls {sorted(unknown)}; "
                                f"use {list(WALL_NAMES)}")
        for wall, sigma in value.items():
            _number(sigma, f"{path}.conductivity_s_per_m.{wall}", positive=True)
        return {WALL_NAMES[wall]: float(sigma) for wall, sigma in value.items()}
    _number(value, f"{path}.conductivity_s_per_m", positive=True)
    return float(value)


def _cavity_shapes(doc, materials):
    """Validated box shapes as (bounds relative to the domain origin in metres, name)."""
    g = doc.data["geometry"]
    shapes = g.get("shapes")
    if not isinstance(shapes, list):
        raise DocumentError("geometry.shapes: expected a list")
    dom = g["domain"]
    cells = doc.data["mesh"]["subdivisions"]
    names, boxes = set(), []
    for i, shape in enumerate(shapes):
        path = f"geometry.shapes[{i}]"
        keys = {axis + side for axis in "xyz" for side in ("min", "max")}
        _object(shape, keys | {"type", "name", "material"}, path)
        if shape.get("type") != "box":
            raise DocumentError(f"{path}: em.cavity3d supports only type 'box'")
        missing = (keys | {"name", "material"}) - set(shape)
        if missing:
            raise DocumentError(f"{path}: missing {sorted(missing)}")
        name = shape["name"]
        if not isinstance(name, str) or not name or name in names:
            raise DocumentError(f"{path}.name: expected a unique non-empty string")
        names.add(name)
        if shape["material"] not in materials:
            raise DocumentError(f"{path}.material: {shape['material']!r} is not defined in materials")
        bounds = []
        for a, axis in enumerate("xyz"):
            low, high = shape[axis + "min"], shape[axis + "max"]
            _number(low, f"{path}.{axis}min")
            _number(high, f"{path}.{axis}max")
            if not dom[axis + "min"] <= low < high <= dom[axis + "max"]:
                raise DocumentError(f"{path}: needs {axis}min < {axis}max inside the domain")
            extent = dom[axis + "max"] - dom[axis + "min"]
            for label, value in ((axis + "min", low), (axis + "max", high)):
                position = (value - dom[axis + "min"]) / extent * cells[a]
                if abs(position - round(position)) > _GRID_TOLERANCE * max(1, cells[a]):
                    raise DocumentError(
                        f"{path}.{label}: must lie on a mesh grid plane (multiples of "
                        f"{extent / cells[a]:g} {doc.length_unit} from {axis}min); adjust mesh.subdivisions")
            bounds.append((doc.scale.to_si(low - dom[axis + "min"], {"length": 1}),
                           doc.scale.to_si(high - dom[axis + "min"], {"length": 1})))
        boxes.append((tuple(bounds), shape["material"]))
    return boxes


def uses_material_solver(doc: Document) -> bool:
    """True when the study needs the complex material/impedance cavity solver."""
    d = doc.data
    p = doc.sole_physics()[1]
    return bool(d["materials"] or d["geometry"]["shapes"] or p.get("boundary") != "pec"
                or d["geometry"]["background"] != {"material": "vacuum"})


def validate_cavity(doc: Document) -> None:
    """Reject unsupported physics instead of silently ignoring 2D settings."""
    d = doc.data
    _object(d, {"openphysics", "name", "units", "geometry", "materials", "physics", "mesh", "study", "results"}, "document")
    pname, p = doc.sole_physics()
    if not isinstance(pname, str) or not pname.isidentifier():
        raise DocumentError("physics name must be an identifier")
    _object(p, {"type", "boundary", "search", "target_frequency_hz", "num_modes"}, f"physics.{pname}")
    _cavity_boundary(p.get("boundary"), f"physics.{pname}.boundary")
    if p.get("search") != "near_target":
        raise DocumentError(f"physics.{pname}.search: cavity requires 'near_target'")
    _number(p.get("target_frequency_hz"), f"physics.{pname}.target_frequency_hz", positive=True)
    _number(p.get("num_modes"), f"physics.{pname}.num_modes", positive=True, integer=True)
    if "length" not in doc.scale.declared:
        raise DocumentError("units.length is required for em.cavity3d")
    g = d["geometry"]
    _object(g, {"domain", "background", "shapes"}, "geometry")
    dom = g.get("domain")
    keys = {axis + side for axis in "xyz" for side in ("min", "max")}
    _object(dom, keys, "geometry.domain")
    if set(dom) != keys:
        raise DocumentError("geometry.domain needs xmin, xmax, ymin, ymax, zmin, zmax")
    for key, value in dom.items():
        _number(value, f"geometry.domain.{key}")
        _number(doc.scale.to_si(value, {"length": 1}), f"geometry.domain.{key} in metres")
    for axis in "xyz":
        _number(dom[axis + "max"] - dom[axis + "min"], f"geometry.domain.{axis} extent", positive=True)
        _number(doc.scale.to_si(dom[axis + "max"] - dom[axis + "min"], {"length": 1}),
                f"geometry.domain.{axis} extent in metres", positive=True)
    materials = _cavity_materials(d)
    background = g.get("background")
    _object(background, {"material"}, "geometry.background")
    if background.get("material") != "vacuum" and background.get("material") not in materials:
        raise DocumentError("geometry.background.material: use 'vacuum' or a name defined in materials")
    m = d["mesh"]
    _object(m, {"subdivisions"}, "mesh")
    subdivisions = m.get("subdivisions")
    if not isinstance(subdivisions, (list, tuple)) or len(subdivisions) != 3:
        raise DocumentError("mesh.subdivisions: expected [nx, ny, nz]")
    for i, value in enumerate(subdivisions):
        _number(value, f"mesh.subdivisions[{i}]", positive=True, integer=True)
    _cavity_shapes(doc, materials)
    if d["study"] != {"type": "single"}:
        raise DocumentError("em.cavity3d supports only study {'type': 'single'}")
    r = d["results"]
    _object(r, {"save_fields", "plots"}, "results")
    if not isinstance(r.get("save_fields"), bool) or not isinstance(r.get("plots"), bool):
        raise DocumentError("results.save_fields and results.plots must be booleans")
    if r["plots"]:
        raise DocumentError("em.cavity3d plotting is not supported; set results.plots=false")
    doc.notes = []


def cavity_summary(doc: Document) -> str:
    pname, p = doc.sole_physics()
    dom = doc.domain
    bounds = "  ".join(f"{axis} [{dom[axis+'min']}, {dom[axis+'max']}]" for axis in "xyz")
    boundary = p["boundary"]
    if boundary == "pec":
        walls = "all faces PEC"
    else:
        sigma = boundary["conductivity_s_per_m"]
        walls = (f"all faces sigma={sigma:g} S/m (surface impedance)" if not isinstance(sigma, dict)
                 else "surface impedance on " + ", ".join(f"{w} sigma={v:g} S/m" for w, v in sigma.items())
                 + "; other faces PEC")
    fill = doc["geometry"]["background"]["material"]
    shapes = "".join(f"\n  box {s['name']}: {s['material']}" for s in doc["geometry"]["shapes"])
    return (f"{doc['name']}  (openphysics {doc['openphysics']})\n"
            f"  domain {bounds} {doc.length_unit}\n"
            f"  physics {pname}: em.cavity3d, background {fill}, {walls}{shapes}\n"
            f"  search: near_target {p['target_frequency_hz']:g} Hz, {p['num_modes']} mode(s)\n"
            f"  mesh: subdivisions {doc['mesh']['subdivisions']}\n"
            "  study: single; output coordinates m, frequencies Hz")


@dataclass
class CavityRunResult:
    """Cavity result; all numerical arrays use SI, independent of input units.

    See ``docs/cavity3d.md`` for raw coefficient units and search limitations.
    ``cavity`` is the reusable galerkin result, with the document translation
    applied to its mesh coordinates.
    """
    doc: Document
    cavity: CavityResult
    timings: dict[str, float]
    log: list[str]

    @property
    def frequencies_hz(self):
        return self.cavity.frequencies_hz

    @property
    def cluster_completeness(self):
        return self.cavity.cluster_completeness

    @property
    def mode_count_policy(self):
        return self.cavity.mode_count_policy

    @property
    def complex_layout(self) -> bool:
        """True for the material/impedance solver's complex result."""
        return hasattr(self.cavity, "quality_factors")

    def _complex_summary(self) -> dict:
        c = self.cavity
        doc_boundary = self.doc.sole_physics()[1]["boundary"]
        return {
            "name": self.doc["name"], "physics_type": "em.cavity3d",
            "units": copy.deepcopy(self.doc["units"]),
            "mesh_length_unit": "m", "frequency_unit": "Hz", "eigenvalue_unit": "m^-2",
            "field_layout": "cavity3d-edge-complex-v1",
            "time_convention": c.time_convention,
            "normalization": "vacuum_mass_hermitian_unit_si",
            "edge_coefficient_unit": "m^-1/2", "electric_field_unit": "m^-3/2",
            "amplitude": "arbitrary normalized; not V/m",
            "edge_orientation": "low_node_index_to_high_node_index",
            "electric_field_location": "tetrahedron_centroid",
            "cluster_completeness": c.cluster_completeness,
            "mode_count_policy": c.mode_count_policy,
            "mesh": {"nodes": len(c.mesh.nodes), "tetrahedra": len(c.mesh.tets),
                     "edges": len(c.space.edges), "subdivisions": self.doc["mesh"]["subdivisions"]},
            "study": {"type": "single"},
            "boundary": copy.deepcopy(doc_boundary),
            "wall_conductivity_s_per_m": {doc_name: c.wall_conductivity_s_per_m[engine_name]
                                          for doc_name, engine_name in WALL_NAMES.items()},
            "background": copy.deepcopy(self.doc["geometry"]["background"]),
            "materials": copy.deepcopy(self.doc["materials"]),
            "lossless": bool(c.lossless),
            "search": c.search, "target_frequency_hz": c.target_frequency_hz,
            "requested_modes": c.requested_modes, "returned_modes": len(c.frequencies_hz),
            "resonant_frequencies_hz": c.resonant_frequencies_hz.tolist(),
            "frequencies_hz_imag": c.frequencies_hz.imag.tolist(),
            # JSON has no infinity: a lossless mode reports null.
            "quality_factors": [None if math.isinf(q) else float(q) for q in c.quality_factors],
            "eigenvalues_m2_real": c.eigenvalues_m2.real.tolist(),
            "eigenvalues_m2_imag": c.eigenvalues_m2.imag.tolist(),
            "relative_residuals": c.relative_residuals.tolist(),
            "fixed_point_iterations": [int(v) for v in c.fixed_point_iterations],
            "timings_s": dict(self.timings),
        }

    def summary(self) -> dict:
        if self.complex_layout:
            return self._complex_summary()
        c = self.cavity
        return {
            "name": self.doc["name"], "physics_type": "em.cavity3d",
            "units": copy.deepcopy(self.doc["units"]),
            "mesh_length_unit": "m", "frequency_unit": "Hz", "eigenvalue_unit": "m^-2",
            "field_layout": "cavity3d-edge-v1",
            "normalization": "electric_mass_orthonormal_si",
            "edge_coefficient_unit": "m^-1/2", "electric_field_unit": "m^-3/2",
            "amplitude": "arbitrary normalized; not V/m",
            "edge_orientation": "low_node_index_to_high_node_index",
            "electric_field_location": "tetrahedron_centroid",
            "cluster_completeness": c.cluster_completeness,
            "mode_count_policy": c.mode_count_policy,
            "mesh": {"nodes": len(c.mesh.nodes), "tetrahedra": len(c.mesh.tets),
                     "edges": len(c.space.edges), "subdivisions": self.doc["mesh"]["subdivisions"]},
            "study": {"type": "single"}, "boundary": "pec", "material": "vacuum",
            "search": c.search, "target_frequency_hz": c.target_frequency_hz,
            "requested_modes": c.requested_modes, "returned_modes": len(c.frequencies_hz),
            "frequencies_hz": c.frequencies_hz.tolist(), "eigenvalues_m2": c.eigenvalues_m2.tolist(),
            "relative_residuals": c.relative_residuals.tolist(),
            "timings_s": dict(self.timings),
        }

    def save(self, outdir: str | Path) -> Path:
        """Write a result without overwriting or mixing earlier result files."""
        outdir = Path(outdir)
        reserved = ("summary.json", "model.json", "log.txt", "fields.npz", "results.png")
        existing = [name for name in reserved
                    if (outdir / name).exists() or (outdir / name).is_symlink()]
        if existing:
            raise FileExistsError(
                f"cavity output already contains result paths: {', '.join(existing)}; "
                "choose a fresh output directory")
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "summary.json").write_text(json.dumps(self.summary(), indent=2), encoding="utf-8")
        (outdir / "log.txt").write_text("\n".join(self.log) + "\n", encoding="utf-8")
        self.doc.save(outdir / "model.json")
        if self.doc["results"]["save_fields"] and self.complex_layout:
            c = self.cavity
            conductivity = np.array([np.nan if c.wall_conductivity_s_per_m[w] is None
                                     else c.wall_conductivity_s_per_m[w] for w in WALL_NAMES.values()])
            np.savez_compressed(
                outdir / "fields.npz", nodes=c.mesh.nodes, tetrahedra=c.mesh.tets,
                edges=c.space.edges, tet_edges=c.space.tet_edges, edge_signs=c.space.signs,
                pec_edge_ids=c.pec_edge_ids,
                frequencies_hz=c.frequencies_hz, eigenvalues_m2=c.eigenvalues_m2,
                quality_factors=c.quality_factors,
                edge_coefficients=c.edge_coefficients, electric_field=c.electric_field,
                relative_residuals=c.relative_residuals,
                tet_relative_permittivity=c.tet_relative_permittivity,
                tet_relative_permeability=c.tet_relative_permeability,
                wall_names=np.array(list(WALL_NAMES)), wall_conductivity_s_per_m=conductivity,
                fixed_point_iterations=c.fixed_point_iterations,
                field_layout="cavity3d-edge-complex-v1", time_convention=c.time_convention,
                mesh_length_unit="m", frequency_unit="Hz", eigenvalue_unit="m^-2",
                edge_coefficient_unit="m^-1/2", electric_field_unit="m^-3/2",
                conductivity_unit="S/m", normalization="vacuum_mass_hermitian_unit_si",
                search=c.search, target_frequency_hz=c.target_frequency_hz,
                requested_modes=c.requested_modes, returned_modes=len(c.frequencies_hz),
                edge_orientation="low_node_index_to_high_node_index",
                electric_field_location="tetrahedron_centroid",
                cluster_completeness=c.cluster_completeness,
                mode_count_policy=c.mode_count_policy)
        elif self.doc["results"]["save_fields"]:
            c = self.cavity
            np.savez_compressed(
                outdir / "fields.npz", nodes=c.mesh.nodes, tetrahedra=c.mesh.tets,
                edges=c.space.edges, tet_edges=c.space.tet_edges, edge_signs=c.space.signs,
                pec_edge_ids=c.pec_edge_ids,
                frequencies_hz=c.frequencies_hz, eigenvalues_m2=c.eigenvalues_m2,
                edge_coefficients=c.edge_coefficients, electric_field=c.electric_field,
                relative_residuals=c.relative_residuals,
                field_layout="cavity3d-edge-v1", mesh_length_unit="m",
                frequency_unit="Hz", eigenvalue_unit="m^-2", edge_coefficient_unit="m^-1/2",
                electric_field_unit="m^-3/2", normalization="electric_mass_orthonormal_si",
                search=c.search, target_frequency_hz=c.target_frequency_hz,
                requested_modes=c.requested_modes, returned_modes=len(c.frequencies_hz),
                edge_orientation="low_node_index_to_high_node_index",
                electric_field_location="tetrahedron_centroid",
                cluster_completeness=c.cluster_completeness,
                mode_count_policy=c.mode_count_policy)
        return outdir


def _run_material_cavity(doc: Document, verbose: bool) -> CavityRunResult:
    import galerkin

    solve = getattr(galerkin, "solve_material_cavity_box", None)
    region_type = getattr(galerkin, "CavityMaterialRegion", None)
    if solve is None or region_type is None:
        raise RuntimeError("em.cavity3d with materials or conducting walls requires a galerkin "
                           "build providing solve_material_cavity_box")
    p = doc.sole_physics()[1]
    dom = doc.domain
    lengths_m = [doc.scale.to_si(dom[a + "max"] - dom[a + "min"], {"length": 1}) for a in "xyz"]
    origin_m = np.array([doc.scale.to_si(dom[a + "min"], {"length": 1}) for a in "xyz"])
    materials = _cavity_materials(doc.data)
    regions = []
    background = doc["geometry"]["background"]["material"]
    if background != "vacuum":
        eps, mu = materials[background]
        regions.append(region_type(tuple((0.0, length) for length in lengths_m), eps, mu))
    for bounds, name in _cavity_shapes(doc, materials):
        eps, mu = materials[name]
        regions.append(region_type(bounds, eps, mu))
    start = time.perf_counter()
    cavity = solve(lengths_m, [int(n) for n in doc["mesh"]["subdivisions"]], regions=regions,
                   num_modes=int(p["num_modes"]), target_frequency_hz=p["target_frequency_hz"],
                   wall_conductivity_s_per_m=_cavity_boundary(p["boundary"], "boundary"))
    cavity.mesh.nodes += origin_m
    timings = {"mesh_and_solve": time.perf_counter() - start}
    q = ", ".join("inf" if math.isinf(v) else f"{v:.8g}" for v in cavity.quality_factors)
    log = [doc.summary(),
           "resonant_frequencies_hz: " + ", ".join(f"{v:.12g}" for v in cavity.resonant_frequencies_hz),
           "quality_factors: " + q,
           "time convention exp(+j*omega*t); Q = Re f / (2 Im f)",
           "near-target candidate search; no complete lowest-spectrum guarantee; multiplicities are retained"]
    if verbose:
        print("\n".join(log))
    return CavityRunResult(doc, cavity, timings, log)


def run_cavity(doc: Document, *, verbose: bool = True) -> CavityRunResult:
    import galerkin

    doc.validate()
    if uses_material_solver(doc):
        return _run_material_cavity(doc, verbose)
    solve_cavity_box = getattr(galerkin, "solve_cavity_box", None)
    if solve_cavity_box is None:
        raise RuntimeError("em.cavity3d requires a matching cavity-enabled galerkin build "
                           "providing solve_cavity_box")
    p = doc.sole_physics()[1]
    dom = doc.domain
    lengths_m = [doc.scale.to_si(dom[a + "max"] - dom[a + "min"], {"length": 1}) for a in "xyz"]
    origin_m = np.array([doc.scale.to_si(dom[a + "min"], {"length": 1}) for a in "xyz"])
    start = time.perf_counter()
    cavity = solve_cavity_box(lengths_m, [int(n) for n in doc["mesh"]["subdivisions"]],
                              num_modes=int(p["num_modes"]), target_frequency_hz=p["target_frequency_hz"])
    cavity.mesh.nodes += origin_m
    timings = {"mesh_and_solve": time.perf_counter() - start}
    log = [doc.summary(), "frequencies_hz: " + ", ".join(f"{v:.12g}" for v in cavity.frequencies_hz),
           "near-target candidate search; no complete lowest-spectrum guarantee; multiplicities are retained"]
    if verbose:
        print("\n".join(log))
    return CavityRunResult(doc, cavity, timings, log)
