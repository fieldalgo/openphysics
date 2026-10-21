# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Run a document end to end: geometry -> mesh -> materials -> physics -> study -> results.

The pipeline is also available one stage at a time. ``build_mesh`` stops after
geometry, meshing and material resolution and hands back a ``MeshedModel``;
``solve_point`` takes that model and one physics setting. ``run`` is their
composition over the study points. A GUI previewing a mesh, or a future caching
layer that recomputes only what changed, uses the stages rather than repeating
them.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import physmat

from galerkin import Mesh
from meshine import TriMesh, generate, shapes as mshapes

from . import physics_em_modes2d
from .geometry import build_domain
from . import units
from .materials import material_table
from .fields import VectorField
from .schema import Document, DocumentError
from .tracking import ModeTracker, ModeTrackingError, tracking_settings
from .subspace_tracking import SUBSPACE_METHOD, SubspaceTracker


if TYPE_CHECKING:
    from .cavity import CavityRunResult
    from .subspace_result import SubspaceSweepResult
    from .thermal import ThermalRunResult
    from .transient_thermal import TransientThermalRunResult


@dataclass
class MeshedModel:
    """Everything a document determines before any physics runs.

    Depends only on the ``geometry``, ``mesh`` and ``materials`` sections, so it
    survives any change to ``physics`` or ``study`` -- which is what makes it
    worth caching.
    """
    doc: Document
    tri: TriMesh                            # meshine output: regions, quality, boundary edges
    mesh: Mesh                              # the same mesh as the solver wants it
    region_materials: dict[str, str]        # region name -> material name
    materials: dict[str, physmat.Material]  # region name -> resolved material
    #: The same mesh in micrometres, as meshine produced it. ``tri`` and ``mesh`` are
    #: in the document's length unit; the solver runs on this one with the wavelength
    #: in micrometres, so a document's answer does not depend on its declared unit.
    #: None for a model assembled by hand: the solver then uses ``mesh`` directly.
    solver_mesh: Mesh | None = None

    def eps_per_triangle(self, wavelength: float) -> np.ndarray:
        """Relative permittivity of each triangle at one wavelength.

        Complex, loss included. Dropping the imaginary part here would leave the
        physics with no way to tell a lossy material from a lossless one, and
        its own guard against loss would never fire.
        """
        wl_um = units.to_micrometres(wavelength, self.doc.scale)
        lut = np.array([self.materials[n].eps(wl_um) for n in self.tri.region_names])
        return lut[self.tri.regions]


def build_mesh(doc: Document) -> MeshedModel:
    """Geometry -> mesh -> materials. The first stage of ``run``."""
    doc.validate()
    from .transient_thermal_contract import is_transient_thermal
    if is_transient_thermal(doc.data):
        raise DocumentError('build_mesh is an EM 2D stage; use run(document) for thermal.transient2d')
    from .thermal import is_thermal
    if is_thermal(doc.data):
        raise DocumentError('build_mesh is an EM 2D stage; use run(document) for thermal.steady2d')
    if any(p.get("type") == "em.cavity3d" for p in doc["physics"].values()):
        raise DocumentError("build_mesh is a 2D stage; use run(document) for em.cavity3d")
    # Geometry and meshing run in micrometres whatever the document declares: the
    # same device written in nm, um or m then gives meshine the same doubles, and
    # so the same mesh. Coordinates go back to the document unit afterwards.
    canonical = micrometre_document(doc)
    domain, namer, region_materials = build_domain(canonical)
    doc.notes.extend(note for note in canonical.notes if note.startswith("geometry."))
    mcfg = canonical["mesh"]
    size_fn = None
    if mcfg.get("grading"):
        g = mcfg["grading"]
        size_fn = mshapes.size_graded(g["near"], g["far"], g["distance"], center=tuple(g["center"]))
    tri_um = generate(domain, namer, min_angle=mcfg.get("min_angle", 28.0), size_fn=size_fn)
    if tri_um.num_triangles == 0 or tri_um.num_nodes == 0:
        raise DocumentError(
            f"meshing produced {tri_um.num_nodes} nodes and {tri_um.num_triangles} triangles. An empty mesh is "
            f"never a usable intermediate result, so it is refused here rather than in whatever reduction "
            f"reaches it first. The usual cause is a mesh.size or a feature far from the scale of the "
            f"units this document declares.")
    tri = dataclasses.replace(tri_um, nodes=units.lengths_from_micrometres(tri_um.nodes, doc.scale))
    return MeshedModel(doc, tri, _solver_mesh(tri), region_materials, material_table(doc, region_materials),
                       solver_mesh=_solver_mesh(tri_um))


def _solver_mesh(tri: TriMesh) -> Mesh:
    return Mesh(tri.nodes, tri.triangles, boundary=dict(tri.boundary_nodes),
                boundary_edges=dict(tri.boundary_edges))


def micrometre_document(doc: Document) -> Document:
    """The same EM or region heat document with every length in micrometres.

    Each number is converted once and exactly where it is representable
    (``units.length_to_micrometres``). A micrometre document comes back equal.
    This lists geometry/mesh lengths shared by EM and region heat documents,
    plus EM wavelength and dispersion lengths. SI-suffixed thermal properties
    and study times stay unchanged. Add new length fields here.
    """
    d = copy.deepcopy(doc.data)
    um = lambda v, power=1: units.length_to_micrometres(v, doc.scale, power)   # noqa: E731
    g = d["geometry"]
    g["domain"] = {k: um(v) for k, v in g["domain"].items()}
    if "mesh_size" in g["background"]:
        g["background"]["mesh_size"] = um(g["background"]["mesh_size"])
    for s in g["shapes"]:
        for k in ("x", "y", "w", "h", "cx", "cy", "r", "mesh_size"):
            if s.get(k) is not None:
                s[k] = um(s[k])
        if "points" in s:
            s["points"] = [[um(c) for c in p] for p in s["points"]]
    m = d["mesh"]
    m["size"] = um(m["size"])
    if m.get("grading"):
        gr = m["grading"]
        gr["center"] = [um(c) for c in gr["center"]]
        for k in ("near", "far", "distance"):
            gr[k] = um(gr[k])
    for p in d["physics"].values():
        if p.get("type") == "em.modes2d":
            p["wavelength"] = um(p["wavelength"])
    st = d["study"]
    if st.get("type") == "sweep" and str(st.get("parameter", "")).endswith(".wavelength"):
        st["values"] = [um(v) for v in st["values"]]
    for spec in d["materials"].values():
        sm = spec.get("sellmeier") if isinstance(spec, dict) else None
        if sm:
            sm["C"] = [um(c, 2) for c in sm["C"]]
            if "range" in sm:
                sm["range"] = [um(r) for r in sm["range"]]
    d["units"] = dict(d["units"], length="um")
    return Document.from_dict(d)


def study_points(doc: Document) -> tuple[str | None, list]:
    """(parameter path, values) for the study; (None, [None]) for a single point."""
    study = doc["study"]
    if study["type"] == "sweep":
        return study["parameter"], list(study["values"])
    return None, [None]


def solve_point(model: MeshedModel, physics: dict) -> dict:
    """One physics solve on an already meshed model."""
    if physics.get('type') == 'thermal.transient2d':
        raise DocumentError('solve_point is an EM 2D stage; use run(document) for thermal.transient2d')
    if physics.get('type') == 'thermal.steady2d':
        raise DocumentError('solve_point is an EM 2D stage; use run(document) for thermal.steady2d')
    if physics.get("type") == "em.cavity3d":
        raise DocumentError("solve_point is a 2D stage; use run(document) for em.cavity3d")
    res = _solve_in_micrometres(model, physics)
    if "vector_field" in res:
        res["vector_field"] = _field_in_document_units(res["vector_field"], model)
    return res


def _solve_in_micrometres(model: MeshedModel, physics: dict) -> dict:
    """``solve_point`` on the micrometre mesh. A vector field's line integrals are in um."""
    wl = physics["wavelength"]
    eps = model.eps_per_triangle(wl)
    mesh, wl_solve = model.mesh, wl
    if model.solver_mesh is not None:
        mesh, wl_solve = model.solver_mesh, units.to_micrometres(wl, model.doc.scale)
    return physics_em_modes2d.solve(mesh, eps, wl_solve, physics["boundary"],
                                    int(physics["num_modes"]), physics["formulation"], physics.get("n_cladding"))


def _field_in_document_units(field: VectorField, model: MeshedModel) -> VectorField:
    """Transverse line integrals carry one length; nothing else in the field does."""
    if model.solver_mesh is None:
        return field
    return dataclasses.replace(field, transverse=units.lengths_from_micrometres(field.transverse, model.doc.scale))


def _tracking_mesh(model: MeshedModel) -> Mesh:
    return model.mesh if model.solver_mesh is None else model.solver_mesh


@dataclass
class RunResult:
    doc: Document
    mesh_nodes: np.ndarray
    mesh_triangles: np.ndarray
    mesh_regions: np.ndarray
    region_names: list[str]
    region_materials: dict[str, str]
    parameter: str | None
    values: list
    neff: np.ndarray            # (n_points, num_modes)
    fields: list[np.ndarray]    # scalar per point: (N, num_modes); empty for vector
    timings: dict[str, float] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    vector_fields: list[VectorField] | None = None
    mode_tracking: dict | None = None

    # -- derived -----------------------------------------------------------

    def group_index(self) -> np.ndarray | None:
        """n_g = n_eff - lambda dn/dlambda when the study sweeps the wavelength."""
        if self.parameter is None or not self.parameter.endswith(".wavelength") or len(self.values) < 2:
            return None
        if self.vector_fields is not None and self.mode_tracking is None:
            return None
        wl = np.asarray(self.values, dtype=float)
        order = 2 if self.mode_tracking is not None else 1
        return self.neff - wl[:, None] * np.gradient(self.neff, wl, axis=0, edge_order=order)

    def summary(self) -> dict:
        out = {
            "name": self.doc["name"],
            "units": copy.deepcopy(self.doc["units"]),
            "mesh": {"nodes": int(len(self.mesh_nodes)), "triangles": int(len(self.mesh_triangles)),
                     "regions": {n: self.region_materials[n] for n in self.region_names}},
            "study": {"parameter": self.parameter, "values": [float(v) for v in self.values]},
            "neff": self.neff.tolist(),
            "timings_s": {k: round(v, 3) for k, v in self.timings.items()},
        }
        ng = self.group_index()
        if self.vector_fields is not None:
            physics = self.doc.sole_physics()[1]
            out.update(formulation="vector", field_representation="vector-edge-nodal-v1",
                       normalization="max_centroid_magnitude", amplitude_unit="relative",
                       n_cladding=physics["n_cladding"], requested_modes=physics["num_modes"],
                       returned_modes=int(self.neff.shape[1]))
        if ng is not None:
            out["group_index"] = ng.tolist()
        if self.mode_tracking is not None:
            out["mode_tracking"] = copy.deepcopy(self.mode_tracking)
        return out

    # -- output ------------------------------------------------------------

    def save(self, outdir: str | Path) -> Path:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "summary.json").write_text(json.dumps(self.summary(), indent=2), encoding="utf-8")
        (outdir / "log.txt").write_text("\n".join(self.log) + "\n", encoding="utf-8")
        self.doc.save(outdir / "model.json")
        if self.doc["results"].get("save_fields", True):
            arrays = dict(nodes=self.mesh_nodes, triangles=self.mesh_triangles, regions=self.mesh_regions,
                          region_names=np.array(self.region_names), values=np.asarray(self.values, dtype=float),
                          neff=self.neff)
            if self.vector_fields is None:
                arrays["fields"] = np.stack(self.fields)
            else:
                arrays.update(field_representation="vector-edge-nodal-v1", edges=self.vector_fields[0].edges,
                              vector_transverse=np.stack([f.transverse for f in self.vector_fields]),
                              vector_longitudinal=np.stack([f.longitudinal for f in self.vector_fields]),
                              vector_electric=np.stack([f.electric for f in self.vector_fields]))
                if self.mode_tracking is not None:
                    arrays.update(mode_tracking_json=json.dumps(self.mode_tracking), group_index=self.group_index())
            np.savez_compressed(outdir / "fields.npz", **arrays)
        if self.doc["results"].get("plots", True):
            self.plot(outdir / "results.png")
        return outdir

    def plot(self, path: str | Path) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        sweep = self.parameter is not None and len(self.values) > 1
        length = self.doc.length_unit
        value_unit = f" {length}" if self.parameter is None or self.parameter.endswith(".wavelength") else ""
        ncols = 3 if sweep else 2
        fig, axes = plt.subplots(1, ncols, figsize=(5.2 * ncols, 4.4))
        # mesh
        ax = axes[0]
        ax.tripcolor(self.mesh_nodes[:, 0], self.mesh_nodes[:, 1], self.mesh_triangles,
                     facecolors=self.mesh_regions.astype(float), cmap="Blues", edgecolors="k", linewidth=0.1, alpha=0.9)
        ax.set_aspect("equal"); ax.set_title(f"mesh: {len(self.mesh_triangles)} triangles")
        ax.set_xlabel(f"x ({length})"); ax.set_ylabel(f"y ({length})")
        # field of the first mode at the middle study point
        i = len(self.values) // 2
        ax = axes[1]
        if self.vector_fields is None:
            f = np.abs(self.fields[i][:, 0])
            ax.tricontourf(self.mesh_nodes[:, 0], self.mesh_nodes[:, 1], self.mesh_triangles, f, levels=30, cmap="inferno")
        else:
            f = np.linalg.norm(self.vector_fields[i].electric[:, 0, :], axis=1)
            ax.tripcolor(self.mesh_nodes[:, 0], self.mesh_nodes[:, 1], self.mesh_triangles,
                         facecolors=f, shading="flat", cmap="inferno")
        ax.set_aspect("equal")
        pname, phys = self.doc.sole_physics()
        label = f"{self.parameter or 'lambda'} = {self.values[i]}{value_unit}"
        ax.set_title(f"|mode 1|, {label}: n_eff = {self.neff[i, 0]:.5f}")
        ax.set_xlabel(f"x ({length})"); ax.set_ylabel(f"y ({length})")
        if sweep:
            ax = axes[2]
            for j in range(self.neff.shape[1]):
                ax.plot(self.values, self.neff[:, j], "o-", label=f"mode {j + 1}")
            ax.set_xlabel(self.parameter + (f" ({length})" if value_unit else ""))
            ax.set_ylabel("n_eff"); ax.legend(fontsize=8)
            ng = self.group_index()
            if ng is not None:
                ax2 = ax.twinx()
                ax2.plot(self.values, ng[:, 0], "s--", color="C3", ms=4, label="n_g (mode 1)")
                ax2.set_ylabel("group index", color="C3")
            ax.set_title("study")
        fig.suptitle(f"{self.doc['name']}  ({pname}: {phys['type']}, {phys['formulation']})")
        fig.tight_layout()
        fig.savefig(path, dpi=130)
        plt.close(fig)


def run(doc: Document, verbose: bool = True) -> RunResult | SubspaceSweepResult | CavityRunResult | ThermalRunResult | TransientThermalRunResult:
    """Run a document, returning RunResult for 2D or CavityRunResult for 3D."""
    log: list[str] = []

    def say(msg):
        log.append(msg)
        if verbose:
            print(msg)

    doc.validate()
    from .transient_thermal_contract import is_transient_thermal
    if is_transient_thermal(doc.data):
        from .transient_thermal import run_transient_thermal
        return run_transient_thermal(doc, verbose=verbose)
    from .thermal import is_thermal, run_thermal
    if is_thermal(doc.data):
        return run_thermal(doc, verbose=verbose)
    if any(p.get("type") == "em.cavity3d" for p in doc["physics"].values()):
        from .cavity import run_cavity
        return run_cavity(doc, verbose=verbose)
    say(doc.summary())
    for note in doc.notes:
        say(f"  warning: {note}")

    t0 = time.time()
    model = build_mesh(doc)
    t_mesh = time.time() - t0
    tm = model.tri
    say(f"mesh: {tm.num_nodes} nodes, {tm.num_triangles} triangles, min angle {tm.min_angle():.1f} deg, {t_mesh:.2f} s")
    for r, m in model.materials.items():
        say(f"  {r}: {m.name}  [{m.source.split(';')[0]}]")

    wl_um = units.to_micrometres(doc.sole_physics()[1]["wavelength"], doc.scale)
    for region, material in model.materials.items():
        try:
            n = material.index(wl_um).real
        except Exception:
            continue                    # a diagnostic must not be what fails the run
        note = units.implausible("refractive index", n)
        if note:
            say(f"  warning: material {material.name} in {region}: {note}")

    parameter, values = study_points(doc)
    neffs, fields = [], []
    vector_fields = [] if doc.sole_physics()[1]["formulation"] == "vector" else None
    tracker, tracking = None, None
    if vector_fields is not None and parameter is not None:
        requested = int(doc.sole_physics()[1]["num_modes"])
        settings = tracking_settings(requested, doc["study"].get("tracking"))
        if settings.get("method") == SUBSPACE_METHOD:
            return _run_subspace(doc, model, parameter, values, settings, say, log, t_mesh)
        tracker = ModeTracker(_tracking_mesh(model), requested, settings)
        tracking = dict(method="electric-l2-assignment-v1", settings=settings, points=[])
        say("vector sweep: tracking resolved modes by electric L2 overlap; check wavelength-step convergence")
    t0 = time.time()
    for v in values:
        d = doc.copy()
        if parameter is not None:
            d.set_path(parameter, v)
        physics = d.sole_physics()[1]
        if tracker is not None:
            physics = dict(physics, num_modes=tracker.settings["search_modes"])
            location = f"wavelength {v:g} {doc.length_unit}"
            try:
                res = _solve_in_micrometres(model, physics)
            except (ValueError, RuntimeError) as exc:
                raise ModeTrackingError(f"vector sweep at {location}: {exc}") from exc
            res["neff"], res["vector_field"], evidence = tracker.step(res["neff"], res["vector_field"], location)
            res["vector_field"] = _field_in_document_units(res["vector_field"], model)
            tracking["points"].append(evidence)
        else:
            res = solve_point(model, physics)
        neffs.append(res["neff"])
        if vector_fields is None:
            fields.append(res["fields"])
        else:
            vector_fields.append(res["vector_field"])
            requested = int(d.sole_physics()[1]["num_modes"])
            if len(res["neff"]) < requested:
                say(f"  warning: requested {requested} modes; found {len(res['neff'])} in the guided interval")
        value_unit = f" {doc.length_unit}" if parameter and parameter.endswith(".wavelength") else ""
        tag = f"{parameter} = {v}{value_unit}: " if parameter else ""
        say(f"  {tag}n_eff = " + ", ".join(f"{n:.6f}" for n in res["neff"]) +
            ("" if res["guided"].all() else "  (some modes below cladding index: not guided)"))
    t_solve = time.time() - t0
    say(f"solved {len(values)} point(s) in {t_solve:.2f} s")

    return RunResult(doc, tm.nodes, tm.triangles, tm.regions, tm.region_names, model.region_materials,
                     parameter, values if parameter else [doc.sole_physics()[1]["wavelength"]],
                     np.array(neffs), fields, {"mesh": t_mesh, "solve": t_solve}, log, vector_fields, tracking)



def _run_subspace(doc, model, parameter, values, settings, say, log, t_mesh) -> "SubspaceSweepResult":
    """Opt-in electric-l2-subspace-v1 sweep: all points succeed or nothing is returned."""
    from .subspace_result import SubspaceSweepResult

    requested = int(doc.sole_physics()[1]["num_modes"])
    tracker = SubspaceTracker(_tracking_mesh(model), requested, settings)
    tracking = dict(method=SUBSPACE_METHOD, settings=settings, points=[])
    say("vector sweep: tracking isolated clusters by electric L2 principal angles "
        "(electric-l2-subspace-v1); check wavelength-step, mesh and search_modes convergence")
    neffs, fields, transforms, offsets = [], [], [], None
    t0 = time.time()
    for v in values:
        d = doc.copy()
        d.set_path(parameter, v)
        physics = dict(d.sole_physics()[1], num_modes=settings["search_modes"])
        location = f"wavelength {v:g} {doc.length_unit}"
        try:
            res = _solve_in_micrometres(model, physics)
        except (ValueError, RuntimeError) as exc:
            raise ModeTrackingError(f"vector subspace sweep at {location}: {exc}") from exc
        neff, field, transform, point_offsets, evidence = tracker.step(res["neff"], res["vector_field"], location)
        field = _field_in_document_units(field, model)
        if offsets is None:
            offsets = point_offsets
        tracking["points"].append(evidence)
        neffs.append(neff)
        fields.append(field)
        transforms.append(transform)
        bands = "; ".join(f"cluster {c + 1}: " + ", ".join(f"{n:.6f}" for n in neff[offsets[c]:offsets[c + 1]])
                          for c in range(len(offsets) - 1))
        say(f"  {parameter} = {v} {doc.length_unit}: {bands}")
    t_solve = time.time() - t0
    say(f"solved {len(values)} point(s) in {t_solve:.2f} s")
    tm = model.tri
    return SubspaceSweepResult(doc, tm.nodes, tm.triangles, tm.regions, tm.region_names, model.region_materials,
                               parameter, list(values), np.array(neffs), [], {"mesh": t_mesh, "solve": t_solve},
                               log, fields, tracking, cluster_offsets=np.asarray(offsets),
                               frame_transforms=transforms)
