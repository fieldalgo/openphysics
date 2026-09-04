"""Cylindrical (radial) PML via complex coordinate stretching (Collino & Monk).

Idea: for r > R0, stretch the radius into the complex plane:
    r~(r) = r + (i/k) int_{R0}^{r} sigma(s) ds,     s(r) = dr~/dr = 1 + (i/k) sigma(r)

An outgoing wave e^{i k r~} = e^{i k r} e^{-int sigma} then decays
exponentially inside the PML. Mapping back to real coordinates turns the
Helmholtz equation into an "anisotropic absorbing material" problem:

    div(Lam grad u) + k^2 beta u = 0
    Lam = (r~/(s r)) rhat rhat^T + (s r/r~) that that^T,     beta = s r~ / r

In the physical region (r < R0) s = 1 and r~ = r, so Lam = I and beta = 1
automatically. sigma uses a quadratic profile sigma(r) = sigma_max ((r-R0)/d)^2
that switches on smoothly at the interface, keeping numerical reflection small.
"""

from __future__ import annotations

import numpy as np

from .mesh import Mesh


def radial_pml_coeffs(mesh: Mesh, k: float, r0: float, d: float,
                      sigma_max: float | None = None):
    """Per-element PML coefficients (Lam, beta).

    k: wavenumber, r0: PML start radius, d: PML thickness.
    sigma_max: absorption strength. The default sigma_max = 21/d gives a
               theoretical round-trip reflection e^{-2S}, S = sigma_max d/3,
               of about 1e-6.
    Returns: Lam (T, 2, 2) complex tensors, beta (T,) complex array.
    """
    if sigma_max is None:
        sigma_max = 21.0 / d

    cent = mesh.nodes[mesh.triangles].mean(axis=1)   # (T, 2) element centroids
    r = np.linalg.norm(cent, axis=1)

    depth = np.clip(r - r0, 0.0, d)                  # penetration depth into PML
    sigma = sigma_max * (depth / d) ** 2
    S = sigma_max * d / 3.0 * (depth / d) ** 3       # int sigma (analytic)

    s = 1.0 + 1j * sigma / k
    r_t = r + 1j * S / k                             # r~

    lam_r = r_t / (s * r)                            # radial eigenvalue
    lam_t = s * r / r_t                              # azimuthal eigenvalue
    beta = s * r_t / r

    # Lam = lam_r rhat rhat^T + lam_t that that^T in Cartesian components
    rhat = cent / r[:, None]
    that = np.column_stack([-rhat[:, 1], rhat[:, 0]])
    Lam = (lam_r[:, None, None] * rhat[:, :, None] * rhat[:, None, :]
           + lam_t[:, None, None] * that[:, :, None] * that[:, None, :])
    return Lam.astype(complex), beta.astype(complex)
