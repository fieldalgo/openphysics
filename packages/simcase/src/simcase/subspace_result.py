# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Result of an opt-in ``electric-l2-subspace-v1`` vector wavelength sweep.

Kept separate from the per-branch semantics of ``RunResult``: columns of
``effective_index`` here are raw local eigenpairs ordered within each cluster at every
point, not branch identities. Only cluster-level quantities are tracked. Like ``RunResult``
it is SI under exp(-i omega t): the raw fields' line integrals are in metres, the complex
fields and the frame transforms are the kernel's conjugated once (``runner._to_public``).
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import ClassVar
from pathlib import Path

import numpy as np

from . import results_common
from .fields import VectorField
from .runner import RunResult, _series
from .subspace_tracking import columns

FIELD_REPRESENTATION = "vector-subspace-edge-nodal-v2"
#: Saved layout: raw eigenpair columns per cluster, not tracked modes. Distinct from the
#: per-mode layout so a consumer of that one refuses this.
FIELD_LAYOUT = "em-modes2d-subspace-raw-v2"
FRAME_NORMALIZATION = ("electric-L2 orthonormal on the micrometre solver mesh "
                       "(transverse line integrals and nodal Ez; not V/m and not unit power)")
MEAN_GROUP_INDEX_MEANING = ("derivative of the cluster mean index: n_bar - lambda d(n_bar)/d(lambda); "
                            "not the group index of a frame column and not a power-weighted average")


def kernel_cluster_means(neff, offsets, wavelength_um):
    """The cluster mean index and its wavelength derivative n_bar - lambda d(n_bar)/d(lambda),
    in the kernel frame (micrometre wavelengths, second-order differences), shape
    (points, clusters) each."""
    o = np.asarray(offsets)
    mean = np.stack([neff[:, o[c]:o[c + 1]].mean(axis=1) for c in range(len(o) - 1)], axis=1)
    wl = np.asarray(wavelength_um, dtype=float)
    return mean, mean - wl[:, None] * np.gradient(mean, wl, axis=0, edge_order=2)


@dataclass
class SubspaceSweepResult(RunResult):
    """Vector wavelength sweep tracked by isolated fixed-rank clusters.

    ``effective_index`` holds the raw n_eff (points, vectors). ``vector_fields`` hold raw
    eigenfields with the existing max-centroid normalization. ``frame_transforms`` hold
    block-diagonal T with frame = raw @ T for every component.
    """

    #: Layout name of the saved and served vector fields (``summary.json``,
    #: ``fields.npz`` and the Studio payload).
    field_representation: ClassVar[str] = FIELD_REPRESENTATION

    cluster_offsets: np.ndarray | None = None
    frame_transforms: list[np.ndarray] | None = None
    #: the cluster mean index (points, clusters)
    mean_effective_index: np.ndarray | None = None
    #: n_bar - lambda d(n_bar)/d(lambda) of each cluster mean (points, clusters)
    mean_group_index: np.ndarray | None = None

    # -- cluster quantities ---------------------------------------------------

    @property
    def cluster_ids(self) -> list[int]:
        return list(range(1, len(self.cluster_offsets)))

    @property
    def cluster_ranks(self) -> list[int]:
        return np.diff(self.cluster_offsets).astype(int).tolist()

    def group_index(self):
        """No per-column group index: columns are not tracked branches.

        Use ``mean_group_index`` or ``singleton_group_index``.
        """
        return None

    def singleton_group_index(self) -> dict[int, np.ndarray]:
        """Individual n_g of rank-one clusters only, keyed by cluster ID."""
        return {cid: self.mean_group_index[:, cid - 1] for cid, rank in zip(self.cluster_ids, self.cluster_ranks)
                if rank == 1}

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

    def arrays(self) -> dict:
        return dict(
            node_coordinates=self.node_coordinates, triangles=self.triangles, regions=self.regions,
            region_names=np.array(self.region_names), vacuum_wavelength=self.vacuum_wavelength,
            field_layout=np.array(FIELD_LAYOUT), study_parameter=np.array(self.parameter),
            field_representation=np.array(FIELD_REPRESENTATION),
            cluster_ids=np.array(self.cluster_ids, dtype=np.int64),
            cluster_offsets=np.asarray(self.cluster_offsets, dtype=np.int64),
            effective_index=self.effective_index, edges=self.vector_fields[0].edges,
            unnormalized_electric_field_line_integral=np.stack([f.transverse for f in self.vector_fields]),
            unnormalized_electric_field_z=np.stack([f.longitudinal for f in self.vector_fields]),
            unnormalized_electric_field=np.stack([f.electric for f in self.vector_fields]),
            frame_transform=np.stack(self.frame_transforms),
            mean_effective_index=self.mean_effective_index, mean_group_index=self.mean_group_index,
            mode_tracking_json=np.array(json.dumps(self.mode_tracking, allow_nan=False)))

    def summary(self) -> dict:
        arrays = self.arrays()
        out = self._envelope(arrays)
        out["field_layout"] = FIELD_LAYOUT
        physics = self._physics()
        o = self.cluster_offsets
        out.update({
            "time_convention": results_common.TIME_CONVENTION, "propagation": "exp(+i beta z)",
            "formulation": "vector", "field_representation": FIELD_REPRESENTATION,
            "normalization": "max_centroid_magnitude", "frame_normalization": FRAME_NORMALIZATION,
            "effective_index_threshold": physics["effective_index_threshold"],
            "mode_count": int(physics["mode_count"]),
            "clusters": [{"id": cid, "rank": rank, "columns": [int(o[cid - 1]), int(o[cid])]}
                         for cid, rank in zip(self.cluster_ids, self.cluster_ranks)],
            "effective_index": _series(self.effective_index, "effective_index"),
            "raw_neff_order": "seed cluster order; members by descending n_eff locally at each point "
                                     "(member columns are not branch identities)",
            "mean_effective_index": _series(self.mean_effective_index, "mean_effective_index"),
            "mean_group_index": _series(self.mean_group_index, "mean_group_index"),
            "cluster_mean_group_index_meaning": MEAN_GROUP_INDEX_MEANING,
            "mode_tracking": copy.deepcopy(self.mode_tracking),
        })
        results_common.dumps_summary(out)
        return out

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
        summary = self.summary()
        (outdir / "summary.json").write_text(results_common.dumps_summary(summary), encoding="utf-8")
        (outdir / "log.txt").write_text("\n".join(self.log) + "\n", encoding="utf-8")
        results_common.write_model_json(self.doc, outdir / "model.json")
        if self.doc.si["results"]["save_fields"]:
            arrays = dict(self.arrays(), metadata_json=results_common.metadata_json(summary))
            np.savez_compressed(outdir / "fields.npz", **arrays)
        if self.doc.si["results"]["plots"]:
            self.plot(outdir / "results.png")

    def plot(self, path: str | Path) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        length, per_unit = self._display()
        nodes = self.node_coordinates / per_unit
        values = self.vacuum_wavelength / per_unit
        fig, axes = plt.subplots(1, 3, figsize=(15.6, 4.4))
        ax = axes[0]
        ax.tripcolor(nodes[:, 0], nodes[:, 1], self.triangles, facecolors=self.regions.astype(float), cmap="Blues",
                     edgecolors="k", linewidth=0.1, alpha=0.9)
        ax.set_aspect("equal"); ax.set_title(f"mesh: {len(self.triangles)} triangles")
        ax.set_xlabel(f"x ({length})"); ax.set_ylabel(f"y ({length})")
        i = len(values) // 2
        ax = axes[1]
        ax.tripcolor(nodes[:, 0], nodes[:, 1], self.triangles, facecolors=self.subspace_density(i, 1), shading="flat",
                     cmap="inferno")
        ax.set_aspect("equal")
        ax.set_title(f"cluster 1 (rank {self.cluster_ranks[0]}): normalized subspace field density\n"
                     f"vacuum_wavelength = {values[i]:g} {length}")
        ax.set_xlabel(f"x ({length})"); ax.set_ylabel(f"y ({length})")
        ax = axes[2]
        mean, mean_ng = self.mean_effective_index, self.mean_group_index
        o = self.cluster_offsets
        for c, cid in enumerate(self.cluster_ids):
            band = self.effective_index[:, o[c]:o[c + 1]]
            ax.fill_between(values, band.min(axis=1), band.max(axis=1), color=f"C{c}", alpha=0.3)
            ax.plot(values, mean[:, c], "o-", color=f"C{c}", label=f"cluster {cid} mean (rank {o[c + 1] - o[c]})")
        ax.set_xlabel(f"vacuum_wavelength ({length})"); ax.set_ylabel("n_eff"); ax.legend(fontsize=8)
        ax2 = ax.twinx()
        ax2.plot(values, mean_ng[:, 0], "s--", color="C3", ms=4)
        ax2.set_ylabel("cluster 1 mean-index derivative n_g", color="C3")
        ax.set_title("subspace study")
        fig.suptitle(f"{self.doc.si['name']}  (electric-l2-subspace-v1)")
        fig.tight_layout()
        fig.savefig(path, dpi=130)
        plt.close(fig)
