# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""em.modes2d — guided modes of a waveguide cross-section.

Scalar formulation (P1 nodal):   (k0^2 M_eps - K) phi = beta^2 M phi,  n_eff = beta / k0
    Exact for TE modes of slab-like (1D) structures, an approximation for
    2D high-contrast cores. Boundary "pec" -> phi = 0, "pmc" -> natural (Neumann).

Vector formulation: provided by the galerkin M3a mode solver once it lands;
    this module raises a clear error until then so documents can already
    request it.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse.linalg as spla

from galerkin import Mesh, assemble_mass, assemble_stiffness


def solve(mesh: Mesh, eps_tri: np.ndarray, wavelength: float, boundary: dict[str, str],
          num_modes: int = 1, formulation: str = "scalar"):
    if formulation == "vector":
        raise NotImplementedError("physics.formulation 'vector' needs the galerkin M3a mode solver; use 'scalar'")
    if np.iscomplexobj(eps_tri) and np.abs(eps_tri.imag).max() > 0:
        raise NotImplementedError("lossy materials (Im eps != 0) need the complex eigensolver; not in the scalar path yet")
    eps_tri = np.real(eps_tri)
    k0 = 2 * np.pi / wavelength
    K = assemble_stiffness(mesh, 1.0)
    M = assemble_mass(mesh, 1.0)
    Me = assemble_mass(mesh, eps_tri)
    A = (k0 ** 2 * Me - K).tocsc()

    pec_sides = [s for s, kind in boundary.items() if kind == "pec"]
    fixed = np.unique(np.concatenate([mesh.boundary[s] for s in pec_sides])) if pec_sides else np.zeros(0, int)
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    A_f, M_f = A[free][:, free], M[free][:, free].tocsc()

    sigma = (k0 * np.sqrt(eps_tri.max())) ** 2
    k = min(num_modes, len(free) - 2)
    vals, vecs = spla.eigsh(A_f, k=k, M=M_f, sigma=sigma, which="LM",
                            v0=np.ones(len(free)), ncv=min(len(free), max(4 * k, 40)), maxiter=10000)
    order = np.argsort(-vals)
    vals, vecs = vals[order], vecs[:, order]
    neff = np.sqrt(np.maximum(vals, 0.0)) / k0
    guided = neff > np.sqrt(eps_tri.min())          # above the lowest material index = guided
    fields = np.zeros((mesh.num_nodes, k))
    fields[free] = vecs
    # normalise each field to unit maximum with positive peak
    for j in range(k):
        i = np.argmax(np.abs(fields[:, j]))
        fields[:, j] /= fields[i, j]
    return {"neff": neff, "guided": guided, "fields": fields}
