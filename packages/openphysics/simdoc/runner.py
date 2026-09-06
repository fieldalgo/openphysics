# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Run a document end to end: geometry -> mesh -> materials -> physics -> study -> results."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from galerkin import Mesh
from meshine import generate, shapes as mshapes

from . import physics_em_modes2d
from .geometry import build_domain
from .materials import material_table
from .schema import Document


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
        if self.parameter != "physics.wavelength" or len(self.values) < 2:
            return None
        wl = np.asarray(self.values, dtype=float)
        return self.neff - wl[:, None] * np.gradient(self.neff, wl, axis=0)

    def summary(self) -> dict:
        out = {
            "name": self.doc["name"],
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
        ncols = 3 if sweep else 2
        fig, axes = plt.subplots(1, ncols, figsize=(5.2 * ncols, 4.4))
        # mesh
        ax = axes[0]
        ax.tripcolor(self.mesh_nodes[:, 0], self.mesh_nodes[:, 1], self.mesh_triangles,
                     facecolors=self.mesh_regions.astype(float), cmap="Blues", edgecolors="k", linewidth=0.1, alpha=0.9)
        ax.set_aspect("equal"); ax.set_title(f"mesh: {len(self.mesh_triangles)} triangles")
        ax.set_xlabel("x (um)"); ax.set_ylabel("y (um)")
        # field of the first mode at the middle study point
        i = len(self.values) // 2
        ax = axes[1]
        f = np.abs(self.fields[i][:, 0])
        ax.tricontourf(self.mesh_nodes[:, 0], self.mesh_nodes[:, 1], self.mesh_triangles, f, levels=30, cmap="inferno")
        ax.set_aspect("equal")
        label = f"{self.parameter} = {self.values[i]}" if self.parameter else f"lambda = {self.doc['physics']['wavelength']}"
        ax.set_title(f"|mode 1|, {label}: n_eff = {self.neff[i, 0]:.5f}")
        ax.set_xlabel("x (um)"); ax.set_ylabel("y (um)")
        if sweep:
            ax = axes[2]
            for j in range(self.neff.shape[1]):
                ax.plot(self.values, self.neff[:, j], "o-", label=f"mode {j + 1}")
            ax.set_xlabel(self.parameter); ax.set_ylabel("n_eff"); ax.legend(fontsize=8)
            ng = self.group_index()
            if ng is not None:
                ax2 = ax.twinx()
                ax2.plot(self.values, ng[:, 0], "s--", color="C3", ms=4, label="n_g (mode 1)")
                ax2.set_ylabel("group index", color="C3")
            ax.set_title("study")
        fig.suptitle(f"{self.doc['name']}  ({self.doc['physics']['type']}, {self.doc['physics']['formulation']})")
        fig.tight_layout()
        fig.savefig(path, dpi=130)
        plt.close(fig)


def run(doc: Document, verbose: bool = True) -> RunResult:
    log: list[str] = []

    def say(msg):
        log.append(msg)
        if verbose:
            print(msg)

    doc.validate()
    say(doc.summary())
    t0 = time.time()
    domain, namer, region_materials = build_domain(doc)
    mcfg = doc["mesh"]
    size_fn = None
    if mcfg.get("grading"):
        g = mcfg["grading"]
        size_fn = mshapes.size_graded(g["near"], g["far"], g["distance"], center=tuple(g["center"]))
    tm = generate(domain, namer, min_angle=mcfg.get("min_angle", 28.0), size_fn=size_fn)
    t_mesh = time.time() - t0
    say(f"mesh: {tm.num_nodes} nodes, {tm.num_triangles} triangles, min angle {tm.min_angle():.1f} deg, {t_mesh:.2f} s")

    mesh = Mesh(tm.nodes, tm.triangles, boundary=dict(tm.boundary_nodes), boundary_edges=dict(tm.boundary_edges))
    materials = material_table(doc, region_materials)
    for r, m in materials.items():
        say(f"  {r}: {m.name}  [{m.source.split(';')[0]}]")

    study = doc["study"]
    if study["type"] == "sweep":
        parameter, values = study["parameter"], list(study["values"])
    else:
        parameter, values = None, [None]

    phys = doc["physics"]
    neffs, fields = [], []
    t0 = time.time()
    for v in values:
        d = doc.copy()
        if parameter is not None:
            d.set_path(parameter, v)
        p = d["physics"]
        wl = p["wavelength"]
        eps_lut = np.array([materials[n].eps(wl).real for n in tm.region_names])
        eps_tri = eps_lut[tm.regions]
        res = physics_em_modes2d.solve(mesh, eps_tri, wl, p["boundary"], int(p["num_modes"]), p["formulation"])
        neffs.append(res["neff"]); fields.append(res["fields"])
        tag = f"{parameter} = {v}: " if parameter else ""
        say(f"  {tag}n_eff = " + ", ".join(f"{n:.6f}" for n in res["neff"]) +
            ("" if res["guided"].all() else "  (some modes below cladding index: not guided)"))
    t_solve = time.time() - t0
    say(f"solved {len(values)} point(s) in {t_solve:.2f} s")

    return RunResult(doc, tm.nodes, tm.triangles, tm.regions, tm.region_names, region_materials,
                     parameter, values if parameter else [phys["wavelength"]], np.array(neffs), fields,
                     {"mesh": t_mesh, "solve": t_solve}, log)
