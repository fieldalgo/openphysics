# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""em.modes2d — guided modes of a waveguide cross-section.

Scalar formulation (P1 nodal):   (k0^2 M_eps - K) phi = beta^2 M phi,  n_eff = beta / k0
    Exact for TE modes of slab-like (1D) structures, an approximation for
    2D high-contrast cores. Boundary "pec" -> phi = 0, "pmc" -> natural (Neumann).

Vector formulation: mixed edge/nodal guided modes from galerkin. PEC fixes
    tangential E and E_z; PMC is natural. Only real positive permittivity is
    supported. An explicit exterior cladding index defines the guided interval.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse.linalg as spla

from galerkin import Mesh, EdgeSpace, assemble_mass, assemble_stiffness, solve_modes, eval_edge_field

from .fields import VectorField


def solve(mesh: Mesh, eps_tri: np.ndarray, wavelength: float, boundary: dict[str, str],
          num_modes: int = 1, formulation: str = "scalar", n_cladding: float | None = None):
    if formulation == "vector" and not np.isfinite(eps_tri).all():
        raise ValueError("vector modes require finite positive dielectric permittivity")
    if np.iscomplexobj(eps_tri) and np.abs(eps_tri.imag).max() > 0:
        raise NotImplementedError("lossy materials (Im eps != 0) need a complex eigensolver; not supported")
    eps_tri = np.real(eps_tri)
    if formulation == "vector":
        return _solve_vector(mesh, eps_tri, wavelength, boundary, num_modes, n_cladding)
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


def _solve_vector(mesh, eps_tri, wavelength, boundary, num_modes, n_cladding):
    if not np.isfinite(eps_tri).all() or np.any(eps_tri <= 0):
        raise ValueError("vector modes require finite positive dielectric permittivity")
    n_core = float(np.sqrt(eps_tri.max()))
    if n_cladding is None or not np.isfinite(n_cladding) or not 0 < n_cladding < n_core:
        raise ValueError("vector n_cladding must be positive and below the maximum material index")
    # A wavelength-sized coordinate system keeps mixed edge/nodal blocks equally
    # conditioned when the same physical document is expressed in nm, um or m.
    scaled = Mesh(mesh.nodes / wavelength, mesh.triangles.copy(), mesh.boundary, mesh.boundary_edges)
    pec_sides = [side for side, kind in boundary.items() if kind == "pec"]
    pec = np.unique(np.concatenate([mesh.boundary[s] for s in pec_sides])) if pec_sides else np.zeros(0, int)
    topology = EdgeSpace(scaled)
    edge_ids = {tuple(edge): i for i, edge in enumerate(topology.edges)}
    pec_edges = np.unique([edge_ids[tuple(sorted(edge))]
                           for side in pec_sides for edge in mesh.boundary_edges[side]]).astype(int)
    free_count = topology.num_edges + mesh.num_nodes - len(pec) - len(pec_edges)
    candidates = min(max(2 * num_modes, 6), free_count - 2)
    if candidates < 1:
        raise ValueError("mesh has too few unconstrained degrees of freedom for vector modes")
    neff, space, et, ez = solve_modes(scaled, eps_tri, 2 * np.pi, n_target=n_core,
                                     num_modes=candidates, pec_nodes=pec, pec_edges=pec_edges)
    keep = np.flatnonzero(np.isfinite(neff) & (neff > n_cladding) & (neff < n_core))[:num_modes]
    if not len(keep):
        raise ValueError("no guided vector modes found between n_cladding and the maximum material index; "
                         "check the cladding index, mesh and computational domain")
    neff, et, ez = neff[keep], et[keep], ez[keep]
    electric = np.empty((mesh.num_triangles, len(keep), 3), dtype=complex)
    for j in range(len(keep)):
        electric[:, j, :2] = eval_edge_field(space, et[j])
        electric[:, j, 2] = 1j * ez[j][mesh.triangles].mean(axis=1)
    norm = np.linalg.norm(electric, axis=2).max(axis=0)
    if not np.isfinite(norm).all() or np.any(norm == 0):
        raise ValueError("vector eigensolver returned a non-finite or zero field")
    field = VectorField(space.edges.copy(), et.T * wavelength / norm,
                        1j * ez.T / norm, electric / norm[None, :, None])
    return {"neff": neff, "guided": np.ones(len(keep), dtype=bool), "vector_field": field}
