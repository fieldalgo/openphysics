# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""HE11 subspace sweep on the symmetric polar fiber fixture (shared by tests)."""

import numpy as np

from galerkin import disk_mesh, eval_edge_field, solve_modes
from simcase.fields import VectorField
from simcase.subspace_tracking import SubspaceTracker, columns
from simcase.tracking import tracking_settings

A, N1, N2 = 4.0, 1.45, 1.44
SETTINGS = dict(method="electric-l2-subspace-v1", cluster_span_max=1e-6, external_gap_min=1e-3)


def centred(step):
    return [1.55 + k * step for k in (-2, -1, 0, 1, 2)]


def he11_sweep(wavelengths, scale=2, radius=6.0, search_modes=None, rotate_seed=None):
    """Return dict(g, mean, sigma2, guards, ranks) for the HE11 rank-2 cluster.

    ``radius`` is in units of a; the outer shell keeps 4 radial layers per a
    per scale. ``rotate_seed`` applies an independent random unitary to each
    returned degenerate pair basis (HE11 and HE21) before every step.
    """
    mesh = disk_mesh((A, 2 * A, radius * A), (4 * scale, 4 * scale, int(round(4 * scale * (radius - 2)))),
                     32 * scale)
    eps = mesh.by_region([N1 ** 2, N2 ** 2, N2 ** 2])
    extra = {} if search_modes is None else {"search_modes": search_modes}
    settings = tracking_settings(2, dict(SETTINGS, **extra))
    tracker = SubspaceTracker(mesh, 2, settings)
    rng = np.random.default_rng(rotate_seed)
    means, sigma2, guards, ranks = [], [], [], None
    for wl in wavelengths:
        n_eff, space, et, ez = solve_modes(mesh, eps, 2 * np.pi / wl, n_target=N1,
                                           num_modes=max(10, settings["search_modes"] + 4))
        keep = np.flatnonzero((n_eff > N2) & (n_eff < N1))[:settings["search_modes"]]
        electric = np.zeros((mesh.num_triangles, len(keep), 3), dtype=complex)
        for j, i in enumerate(keep):
            electric[:, j, :2] = eval_edge_field(space, et[i])
            electric[:, j, 2] = 1j * ez[i][mesh.triangles].mean(axis=1)
        field = VectorField(space.edges.copy(), et[keep].T, 1j * ez[keep].T, electric)
        if rotate_seed is not None:
            unitary = np.eye(len(keep), dtype=complex)
            for start in (0, 4):
                if start + 2 <= len(keep):
                    q, _ = np.linalg.qr(rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2)))
                    unitary[start:start + 2, start:start + 2] = q
            field = columns(field, unitary)
        neff, _, _, offsets, evidence = tracker.step(n_eff[keep], field, f"{wl} um")
        ranks = np.diff(offsets).tolist()
        means.append(neff.mean())
        guards.append(evidence["clusters"][0]["lower_guard_rank"])
        sigma2.append(evidence["clusters"][0].get("principal_squared"))
    wl = np.asarray(wavelengths)
    means = np.asarray(means)
    g = means - wl * np.gradient(means, wl, edge_order=2)
    return dict(g=g, mean=means, sigma2=sigma2, guards=guards, ranks=ranks)
