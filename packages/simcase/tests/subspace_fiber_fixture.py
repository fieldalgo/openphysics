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


def sellmeier(wavelength):
    """Core 1 + 1.1 l^2/(l^2 - 0.01), cladding 0.993 x core: (n1, n2, dn1, dn2)."""
    n1 = np.sqrt(1 + 1.1 * wavelength ** 2 / (wavelength ** 2 - 0.01))
    dn1 = -1.1 * 0.01 * wavelength / (n1 * (wavelength ** 2 - 0.01) ** 2)
    return n1, 0.993 * n1, dn1, 0.993 * dn1


def centred(step):
    return [1.55 + k * step for k in (-2, -1, 0, 1, 2)]


def he11_sweep(wavelengths, scale=2, radius=6.0, search_modes=None, rotate_seed=None, materials=None):
    """Return dict(g, mean, sigma2, guards, ranks) for the HE11 rank-2 cluster.

    ``radius`` is in units of a; the outer shell keeps 4 radial layers per a
    per scale. ``rotate_seed`` applies an independent random unitary to each
    returned degenerate pair basis (HE11 and HE21) before every step.
    ``materials(wavelength) -> (n1, n2)`` makes the indices wavelength dependent
    on the fixed mesh (default: constant N1, N2).
    """
    if materials is None:
        materials = lambda wl: (N1, N2)        # noqa: E731
    mesh = disk_mesh((A, 2 * A, radius * A), (4 * scale, 4 * scale, int(round(4 * scale * (radius - 2)))),
                     32 * scale)
    extra = {} if search_modes is None else {"search_modes": search_modes}
    settings = tracking_settings(2, dict(SETTINGS, **extra))
    tracker = SubspaceTracker(mesh, 2, settings)
    rng = np.random.default_rng(rotate_seed)
    means, sigma2, guards, ranks = [], [], [], None
    for wl in wavelengths:
        n1, n2 = materials(wl)
        eps = mesh.by_region([n1 ** 2, n2 ** 2, n2 ** 2])
        n_eff, space, et, ez = solve_modes(mesh, eps, 2 * np.pi / wl, n_target=n1,
                                           num_modes=max(10, settings["search_modes"] + 4))
        keep = np.flatnonzero((n_eff > n2) & (n_eff < n1))[:settings["search_modes"]]
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


# -- field-space comparison with the exact vector fields -----------------------

# Dunavant degree-5 rule on a triangle: barycentric points and weights (sum 1).
_QUADRATURE = [((1 / 3, 1 / 3, 1 / 3), 0.225)]
for (_a, _b), _w in (((0.059715871789770, 0.470142064105115), 0.132394152788506),
                     ((0.797426985353087, 0.101286507323456), 0.125939180544827)):
    _QUADRATURE += [((_a, _b, _b), _w), ((_b, _a, _b), _w), ((_b, _b, _a), _w)]


def _fe_at_quadrature(mesh, space, et, ez):
    """Whitney E_t and P1 E_z (= 1j ez) at quadrature points: (T, q, modes, 3)."""
    from galerkin.edge import _tri_grads
    grads, _ = _tri_grads(mesh)
    out = np.zeros((mesh.num_triangles, len(_QUADRATURE), et.shape[0], 3), dtype=complex)
    for q, (lam, _) in enumerate(_QUADRATURE):
        for e, (i, j) in enumerate(zip((1, 2, 0), (2, 0, 1))):
            whitney = lam[i] * grads[:, j, :] - lam[j] * grads[:, i, :]
            coef = space.signs[:, e][:, None] * et[:, space.tri_edges[:, e]].T
            out[:, q, :, :2] += coef[:, :, None] * whitney[:, None, :]
        out[:, q, :, 2] = 1j * sum(lam[k] * ez[:, mesh.triangles[:, k]].T for k in range(3))
    return out


def _gram(left, right, area):
    weights = np.array([w for _, w in _QUADRATURE])
    return np.einsum("t,q,tqmc,tqnc->mn", area, weights, left.conj(), right)


def field_space_sin_angles(scale, label="HE11", fe_columns=(0, 1)):
    """sin of principal angles between FEM eigenvector spans and the exact mode span.

    Electric L2 inner products by degree-5 quadrature over the FE mesh; the
    exact field uses the true core radius at every quadrature point.
    """
    from refsol import fiber
    mesh = disk_mesh((A, 2 * A, 6 * A), (4 * scale, 4 * scale, 16 * scale), 32 * scale)
    eps = mesh.by_region([N1 ** 2, N2 ** 2, N2 ** 2])
    _, space, et, ez = solve_modes(mesh, eps, 2 * np.pi / 1.55, n_target=N1, num_modes=10)
    cols = list(fe_columns)
    fe = _fe_at_quadrature(mesh, space, et[cols], ez[cols])
    corners = mesh.nodes[mesh.triangles]
    d1, d2 = corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]
    area = 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    pts = np.stack([sum(lam[k] * corners[:, k, :] for k in range(3)) for lam, _ in _QUADRATURE], axis=1)
    polarizations = (0, 1) if fiber.mode_l(label) else (0,)
    exact = np.stack([fiber.vector_mode_field(A, N1, N2, 1.55, label, pts[..., 0], pts[..., 1], p)
                      for p in polarizations], axis=2)

    def whitened(x):
        g = _gram(x, x, area)
        values, vectors = np.linalg.eigh((g + g.conj().T) / 2)
        return np.einsum("tqmc,mk->tqkc", x, vectors / np.sqrt(values))

    cosines = np.linalg.svd(_gram(whitened(fe), whitened(exact), area), compute_uv=False)
    return np.sqrt(np.clip(1 - cosines ** 2, 0, 1))
