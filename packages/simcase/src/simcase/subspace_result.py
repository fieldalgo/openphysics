# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Result of an opt-in ``electric-l2-subspace-v1`` vector wavelength sweep.

Kept separate from the per-branch semantics of ``RunResult``: columns of
``neff`` here are raw local eigenpairs ordered within each cluster at every
point, not branch identities. Only cluster-level quantities are tracked.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .fields import VectorField
from .runner import RunResult
from .subspace_tracking import columns

FIELD_REPRESENTATION = "vector-subspace-edge-nodal-v1"
FRAME_NORMALIZATION = ("electric L2 orthonormal in document length coordinates "
                       "(transverse line integrals and nodal Ez; not V/m and not unit power)")
MEAN_GROUP_INDEX_MEANING = ("derivative of the cluster mean index: n_bar - lambda d(n_bar)/d(lambda); "
                            "not the group index of a frame column and not a power-weighted average")


@dataclass
class SubspaceSweepResult(RunResult):
    """Vector wavelength sweep tracked by isolated fixed-rank clusters.

    ``neff`` holds raw n_eff (points, vectors). ``vector_fields`` hold raw
    eigenfields with the existing max-centroid normalization. ``frame_transforms``
    hold block-diagonal T with frame = raw @ T for every component.
    """

    cluster_offsets: np.ndarray | None = None
    frame_transforms: list[np.ndarray] | None = None

    # -- cluster quantities ---------------------------------------------------

    @property
    def cluster_ids(self) -> list[int]:
        return list(range(1, len(self.cluster_offsets)))

    @property
    def cluster_ranks(self) -> list[int]:
        return np.diff(self.cluster_offsets).astype(int).tolist()

    def group_index(self):
        """No per-column group index: columns are not tracked branches.

        Use ``cluster_mean_group_index`` or ``singleton_group_index``.
        """
        return None

    def cluster_mean_index(self) -> np.ndarray:
        """Mean raw n_eff of each cluster, shape (points, clusters)."""
        o = self.cluster_offsets
        return np.stack([self.neff[:, o[c]:o[c + 1]].mean(axis=1) for c in range(len(o) - 1)], axis=1)

    def cluster_mean_group_index(self) -> np.ndarray:
        """n_bar - lambda d(n_bar)/d(lambda) with second-order differences.

        This is the derivative of the cluster mean index, not an individual
        member's group index.
        """
        wl = np.asarray(self.values, dtype=float)
        mean = self.cluster_mean_index()
        return mean - wl[:, None] * np.gradient(mean, wl, axis=0, edge_order=2)

    def singleton_group_index(self) -> dict[int, np.ndarray]:
        """Individual n_g of rank-one clusters only, keyed by cluster ID."""
        mean_ng = self.cluster_mean_group_index()
        return {cid: mean_ng[:, cid - 1] for cid, rank in zip(self.cluster_ids, self.cluster_ranks) if rank == 1}

    def frame_fields(self, point: int) -> VectorField:
        """Aligned transport frame at one point (not eigenmodes)."""
        return columns(self.vector_fields[point], self.frame_transforms[point])

    def subspace_density(self, point: int, cluster_id: int) -> np.ndarray:
        """Normalized subspace field density at triangle centroids.

        D = sum_j |F_j|^2 over the cluster frame, divided by its maximum. It is
        invariant under unitary changes of frame; it is not electromagnetic
        energy density and not a uniquely polarized mode.
        """
        o = self.cluster_offsets
        frame = self.frame_fields(point).electric[:, o[cluster_id - 1]:o[cluster_id], :]
        density = (np.abs(frame) ** 2).sum(axis=(1, 2))
        return density / density.max()

    # -- output ------------------------------------------------------------

    def summary(self) -> dict:
        physics = self.doc.sole_physics()[1]
        o = self.cluster_offsets
        return {
            "name": self.doc["name"],
            "units": copy.deepcopy(self.doc["units"]),
            "mesh": {"nodes": int(len(self.mesh_nodes)), "triangles": int(len(self.mesh_triangles)),
                     "regions": {n: self.region_materials[n] for n in self.region_names}},
            "study": {"parameter": self.parameter, "values": [float(v) for v in self.values]},
            "formulation": "vector", "field_representation": FIELD_REPRESENTATION,
            "normalization": "max_centroid_magnitude", "amplitude_unit": "relative",
            "frame_normalization": FRAME_NORMALIZATION,
            "n_cladding": physics["n_cladding"], "requested_modes": physics["num_modes"],
            "clusters": [{"id": cid, "rank": rank, "columns": [int(o[cid - 1]), int(o[cid])]}
                         for cid, rank in zip(self.cluster_ids, self.cluster_ranks)],
            "raw_neff": self.neff.tolist(),
            "raw_neff_order": "seed cluster order; members by descending n_eff locally at each point "
                              "(member columns are not branch identities)",
            "cluster_mean_neff": self.cluster_mean_index().tolist(),
            "cluster_mean_group_index": self.cluster_mean_group_index().tolist(),
            "cluster_mean_group_index_meaning": MEAN_GROUP_INDEX_MEANING,
            "mode_tracking": copy.deepcopy(self.mode_tracking),
            "timings_s": {k: round(v, 3) for k, v in self.timings.items()},
        }

    def save(self, outdir: str | Path) -> Path:
        """Write into a fresh directory; an existing path is refused.

        A fresh directory guarantees that new metadata is never combined with
        stale fields from an earlier run. Files are written to a hidden staging
        directory beside the target and renamed into place only when all of
        them succeeded, so a failed save leaves no partial result that would
        block a retry. The existence check and the rename are not one atomic
        step; concurrent writers to the same path are not supported.
        """
        outdir = Path(outdir)
        if os.path.lexists(outdir):
            raise FileExistsError(f"subspace sweep output already exists: {outdir}; choose a fresh output directory")
        outdir.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{outdir.name}.partial-", dir=outdir.parent))
        try:
            self._write(stage)
            if os.path.lexists(outdir):
                raise FileExistsError(f"subspace sweep output appeared during save: {outdir}")
            os.rename(stage, outdir)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        return outdir

    def _write(self, outdir: Path) -> None:
        (outdir / "summary.json").write_text(json.dumps(self.summary(), indent=2, allow_nan=False),
                                             encoding="utf-8")
        (outdir / "log.txt").write_text("\n".join(self.log) + "\n", encoding="utf-8")
        self.doc.save(outdir / "model.json")
        if self.doc["results"].get("save_fields", True):
            arrays = dict(
                nodes=self.mesh_nodes, triangles=self.mesh_triangles, regions=self.mesh_regions,
                region_names=np.array(self.region_names), values=np.asarray(self.values, dtype=float),
                field_representation=np.array(FIELD_REPRESENTATION),
                cluster_ids=np.array(self.cluster_ids, dtype=np.int64),
                cluster_offsets=np.asarray(self.cluster_offsets, dtype=np.int64),
                raw_neff=self.neff, edges=self.vector_fields[0].edges,
                raw_transverse=np.stack([f.transverse for f in self.vector_fields]),
                raw_longitudinal=np.stack([f.longitudinal for f in self.vector_fields]),
                raw_electric=np.stack([f.electric for f in self.vector_fields]),
                frame_transform=np.stack(self.frame_transforms),
                cluster_mean_neff=self.cluster_mean_index(),
                cluster_mean_group_index=self.cluster_mean_group_index(),
                mode_tracking_json=np.array(json.dumps(self.mode_tracking, allow_nan=False)))
            np.savez_compressed(outdir / "fields.npz", **arrays)
        if self.doc["results"].get("plots", True):
            self.plot(outdir / "results.png")

    def plot(self, path: str | Path) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        length = self.doc.length_unit
        fig, axes = plt.subplots(1, 3, figsize=(15.6, 4.4))
        ax = axes[0]
        ax.tripcolor(self.mesh_nodes[:, 0], self.mesh_nodes[:, 1], self.mesh_triangles,
                     facecolors=self.mesh_regions.astype(float), cmap="Blues", edgecolors="k", linewidth=0.1,
                     alpha=0.9)
        ax.set_aspect("equal"); ax.set_title(f"mesh: {len(self.mesh_triangles)} triangles")
        ax.set_xlabel(f"x ({length})"); ax.set_ylabel(f"y ({length})")
        i = len(self.values) // 2
        ax = axes[1]
        ax.tripcolor(self.mesh_nodes[:, 0], self.mesh_nodes[:, 1], self.mesh_triangles,
                     facecolors=self.subspace_density(i, 1), shading="flat", cmap="inferno")
        ax.set_aspect("equal")
        ax.set_title(f"cluster 1 (rank {self.cluster_ranks[0]}): normalized subspace field density\n"
                     f"lambda = {self.values[i]} {length}")
        ax.set_xlabel(f"x ({length})"); ax.set_ylabel(f"y ({length})")
        ax = axes[2]
        mean, mean_ng = self.cluster_mean_index(), self.cluster_mean_group_index()
        o = self.cluster_offsets
        for c, cid in enumerate(self.cluster_ids):
            band = self.neff[:, o[c]:o[c + 1]]
            ax.fill_between(self.values, band.min(axis=1), band.max(axis=1), color=f"C{c}", alpha=0.3)
            ax.plot(self.values, mean[:, c], "o-", color=f"C{c}", label=f"cluster {cid} mean (rank {o[c + 1] - o[c]})")
        ax.set_xlabel(f"{self.parameter} ({length})"); ax.set_ylabel("n_eff"); ax.legend(fontsize=8)
        ax2 = ax.twinx()
        ax2.plot(self.values, mean_ng[:, 0], "s--", color="C3", ms=4)
        ax2.set_ylabel("cluster 1 mean-index derivative n_g", color="C3")
        ax.set_title("subspace study")
        fig.suptitle(f"{self.doc['name']}  (electric-l2-subspace-v1)")
        fig.tight_layout()
        fig.savefig(path, dpi=130)
        plt.close(fig)
