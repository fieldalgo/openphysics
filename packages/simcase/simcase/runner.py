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
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import physmat

from galerkin import Mesh
from meshine import TriMesh, generate, shapes as mshapes

from . import physics_em_modes2d
from .geometry import build_domain
from . import units
from .materials import material_table
from .schema import Document, DocumentError


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
    domain, namer, region_materials = build_domain(doc)
    mcfg = doc["mesh"]
    size_fn = None
    if mcfg.get("grading"):
        g = mcfg["grading"]
        size_fn = mshapes.size_graded(g["near"], g["far"], g["distance"], center=tuple(g["center"]))
    tri = generate(domain, namer, min_angle=mcfg.get("min_angle", 28.0), size_fn=size_fn)
    if tri.num_triangles == 0 or tri.num_nodes == 0:
        raise DocumentError(
            f"meshing produced {tri.num_nodes} nodes and {tri.num_triangles} triangles. An empty mesh is "
            f"never a usable intermediate result, so it is refused here rather than in whatever reduction "
            f"reaches it first. The usual cause is a mesh.size or a feature far from the scale of the "
            f"units this document declares.")
    mesh = Mesh(tri.nodes, tri.triangles, boundary=dict(tri.boundary_nodes),
                boundary_edges=dict(tri.boundary_edges))
    return MeshedModel(doc, tri, mesh, region_materials, material_table(doc, region_materials))


def study_points(doc: Document) -> tuple[str | None, list]:
    """(parameter path, values) for the study; (None, [None]) for a single point."""
    study = doc["study"]
    if study["type"] == "sweep":
        return study["parameter"], list(study["values"])
    return None, [None]


def solve_point(model: MeshedModel, physics: dict) -> dict:
    """One physics solve on an already meshed model."""
    wl = physics["wavelength"]
    return physics_em_modes2d.solve(model.mesh, model.eps_per_triangle(wl), wl, physics["boundary"],
                                    int(physics["num_modes"]), physics["formulation"])


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
    fields: list[np.ndarray]    # per point: (N, num_modes)
    timings: dict[str, float] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)

    # -- derived -----------------------------------------------------------

    def group_index(self) -> np.ndarray | None:
        """n_g = n_eff - lambda dn/dlambda when the study sweeps the wavelength."""
        if self.parameter is None or not self.parameter.endswith(".wavelength") or len(self.values) < 2:
            return None
        wl = np.asarray(self.values, dtype=float)
        return self.neff - wl[:, None] * np.gradient(self.neff, wl, axis=0)

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
        if ng is not None:
            out["group_index"] = ng.tolist()
        return out

    # -- output ------------------------------------------------------------

    def save(self, outdir: str | Path) -> Path:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "summary.json").write_text(json.dumps(self.summary(), indent=2), encoding="utf-8")
        (outdir / "log.txt").write_text("\n".join(self.log) + "\n", encoding="utf-8")
        self.doc.save(outdir / "model.json")
        if self.doc["results"].get("save_fields", True):
            np.savez_compressed(outdir / "fields.npz", nodes=self.mesh_nodes, triangles=self.mesh_triangles,
                                regions=self.mesh_regions, region_names=np.array(self.region_names),
                                values=np.asarray(self.values, dtype=float), neff=self.neff,
                                fields=np.stack(self.fields))
        if self.doc["results"].get("plots", True):
            self.plot(outdir / "results.png")
        return outdir

    def plot(self, path: str | Path) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        sweep = self.parameter is not None and len(self.values) > 1
        length = self.doc.length_unit
        value_unit = length if self.parameter is None or self.parameter.endswith(".wavelength") else None
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
        f = np.abs(self.fields[i][:, 0])
        ax.tricontourf(self.mesh_nodes[:, 0], self.mesh_nodes[:, 1], self.mesh_triangles, f, levels=30, cmap="inferno")
        ax.set_aspect("equal")
        pname, phys = self.doc.sole_physics()
        label = f"{self.parameter} = {self.values[i]}" if self.parameter else f"lambda = {phys['wavelength']}"
        if value_unit is not None:
            label += f" [{value_unit}]"
        ax.set_title(f"|mode 1|, {label}: n_eff = {self.neff[i, 0]:.5f}")
        ax.set_xlabel(f"x ({length})"); ax.set_ylabel(f"y ({length})")
        if sweep:
            ax = axes[2]
            for j in range(self.neff.shape[1]):
                ax.plot(self.values, self.neff[:, j], "o-", label=f"mode {j + 1}")
            xlabel = f"{self.parameter} ({value_unit})" if value_unit is not None else self.parameter
            ax.set_xlabel(xlabel); ax.set_ylabel("n_eff"); ax.legend(fontsize=8)
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


def run(doc: Document, verbose: bool = True) -> RunResult:
    """Compose the stages over every study point."""
    log: list[str] = []

    def say(msg):
        log.append(msg)
        if verbose:
            print(msg)

    doc.validate()
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
    t0 = time.time()
    for v in values:
        d = doc.copy()
        if parameter is not None:
            d.set_path(parameter, v)
        res = solve_point(model, d.sole_physics()[1])
        neffs.append(res["neff"]); fields.append(res["fields"])
        tag = f"{parameter} = {v}: " if parameter else ""
        say(f"  {tag}n_eff = " + ", ".join(f"{n:.6f}" for n in res["neff"]) +
            ("" if res["guided"].all() else "  (some modes below cladding index: not guided)"))
    t_solve = time.time() - t0
    say(f"solved {len(values)} point(s) in {t_solve:.2f} s")

    return RunResult(doc, tm.nodes, tm.triangles, tm.regions, tm.region_names, model.region_materials,
                     parameter, values if parameter else [doc.sole_physics()[1]["wavelength"]],
                     np.array(neffs), fields, {"mesh": t_mesh, "solve": t_solve}, log)
