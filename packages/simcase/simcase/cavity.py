# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Single vacuum PEC box studies and their explicit SI output contract."""

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


def validate_cavity(doc: Document) -> None:
    """Reject unsupported physics instead of silently ignoring 2D settings."""
    d = doc.data
    _object(d, {"openphysics", "name", "units", "geometry", "materials", "physics", "mesh", "study", "results"}, "document")
    pname, p = doc.sole_physics()
    if not isinstance(pname, str) or not pname.isidentifier():
        raise DocumentError("physics name must be an identifier")
    _object(p, {"type", "boundary", "search", "target_frequency_hz", "num_modes"}, f"physics.{pname}")
    if p.get("boundary") != "pec":
        raise DocumentError(f"physics.{pname}.boundary: cavity requires 'pec' on every face")
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
    if g.get("background") != {"material": "vacuum"} or g.get("shapes") != [] or d["materials"] != {}:
        raise DocumentError("em.cavity3d supports vacuum only: background material vacuum, empty shapes and materials")
    m = d["mesh"]
    _object(m, {"subdivisions"}, "mesh")
    subdivisions = m.get("subdivisions")
    if not isinstance(subdivisions, (list, tuple)) or len(subdivisions) != 3:
        raise DocumentError("mesh.subdivisions: expected [nx, ny, nz]")
    for i, value in enumerate(subdivisions):
        _number(value, f"mesh.subdivisions[{i}]", positive=True, integer=True)
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
    return (f"{doc['name']}  (openphysics {doc['openphysics']})\n"
            f"  domain {bounds} {doc.length_unit}\n"
            f"  physics {pname}: em.cavity3d, vacuum, all faces PEC\n"
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

    def summary(self) -> dict:
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
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "summary.json").write_text(json.dumps(self.summary(), indent=2), encoding="utf-8")
        (outdir / "log.txt").write_text("\n".join(self.log) + "\n", encoding="utf-8")
        self.doc.save(outdir / "model.json")
        if self.doc["results"]["save_fields"]:
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
                requested_modes=c.requested_modes,
                edge_orientation="low_node_index_to_high_node_index",
                electric_field_location="tetrahedron_centroid",
                cluster_completeness=c.cluster_completeness,
                mode_count_policy=c.mode_count_policy)
        return outdir


def run_cavity(doc: Document, *, verbose: bool = True) -> CavityRunResult:
    import galerkin

    solve_cavity_box = getattr(galerkin, "solve_cavity_box", None)
    if solve_cavity_box is None:
        raise RuntimeError("em.cavity3d requires a matching cavity-enabled galerkin build "
                           "providing solve_cavity_box")
    doc.validate()
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
