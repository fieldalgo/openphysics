# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Mesh quality and accuracy of ``meshloom.generate3d`` on C1 (unit sphere): V9, V6, V21.

Rows of docs/packages/meshine/validation3d.md, with the constants of its "Frozen
baseline constants" section (Gmsh 4.15.2 with the Netgen optimizer):

- V9 on C1 (unit sphere) at three sizes: T within [0.85, 1.25] T_B, then the smallest
  dihedral angle at least 15°, the smallest q at least 0.30 and the mean q at least the
  floor.
- V6 on C1: the volume error e(h) = |sum V_T - 4 pi/3| / (4 pi/3) has a least-squares
  slope of at least 1.8 over the three sizes and e(0.05) <= 1.5e-3.
- V21 on C1: u = x^2 - y^2 + z with Dirichlet data; the P1 L2 error (degree-5 rule)
  has a slope of at least 1.8 against h_eff = (|Omega| / T)^(1/3) over the three sizes.

The finest sizes run with the slow studies. Rows the mesher does not meet yet are not
here; they are listed on the meshloom page under its limits. The cases and measures are
in quality_cases.py.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from quality_cases import dihedral_and_q, generate  # noqa: E402

# V9 on C1: (T window, mean q floor); min theta >= 15 and min q >= 0.30 at every size
V9 = {0.2: ((2141, 3147), 0.8108), 0.1: ((15017, 22083), 0.8347), 0.05: ((114224, 167976), 0.8463)}


@pytest.mark.parametrize("h", [0.2, 0.1, pytest.param(0.05, marks=pytest.mark.slow)])
def test_v9_sphere_quality(h):
    (lo, hi), q_floor = V9[h]
    theta, q = dihedral_and_q(generate("C1", h))
    assert lo <= len(q) <= hi, (h, len(q))
    assert theta.min() >= 15.0, (h, float(theta.min()))
    assert q.min() >= 0.30, (h, float(q.min()))
    assert q.mean() >= q_floor, (h, float(q.mean()))


@pytest.mark.slow
def test_v6_sphere_volume_converges():
    hs, errors = [0.2, 0.1, 0.05], []
    for h in hs:
        m = generate("C1", h)
        x = m["nodes"][m["tetrahedra"]]
        volume = np.abs(np.einsum("ij,ij->i", x[:, 1] - x[:, 0], np.cross(x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]))).sum() / 6
        errors.append(abs(volume - 4 * np.pi / 3) / (4 * np.pi / 3))
    slope = np.polyfit(np.log(hs), np.log(errors), 1)[0]
    assert slope >= 1.8 and errors[-1] <= 1.5e-3, (slope, errors)


def duffy_rule(n=5):
    """Collapsed Gauss-Legendre rule on the unit tetrahedron (barycentric points, weights
    summing to 1/6), exact for degree 5 and more (the rule of tests/meshine's V21)."""
    x, w = np.polynomial.legendre.leggauss(n)
    x, w = 0.5 * (x + 1), 0.5 * w
    u, v, s = np.meshgrid(x, x, x, indexing="ij")
    wu, wv, ws = np.meshgrid(w, w, w, indexing="ij")
    a, b, c = u, v * (1 - u), s * (1 - u) * (1 - v)
    weight = (wu * wv * ws * (1 - u) ** 2 * (1 - v)).ravel()
    return np.stack([1 - a - b - c, a, b, c], axis=-1).reshape(-1, 4), weight


@pytest.mark.slow
def test_v21_sphere_poisson_converges():
    from galerkin import from_mesher
    from galerkin.kernels import assemble_stiffness_3d, solve_dirichlet
    lam, wq = duffy_rule()
    h_eff, errors = [], []
    for h in (0.2, 0.1, 0.05):
        mesh = from_mesher(generate("C1", h))
        x = mesh.nodes
        exact = x[:, 0] ** 2 - x[:, 1] ** 2 + x[:, 2]
        bnd = mesh.boundary_nodes()
        uh = solve_dirichlet(assemble_stiffness_3d(mesh), np.zeros(mesh.num_nodes), {tuple(bnd): exact[bnd]})
        p = mesh.nodes[mesh.tets]
        vol6 = np.abs(np.einsum("ij,ij->i", p[:, 1] - p[:, 0], np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0])))
        xq = np.einsum("qk,tkd->tqd", lam, p)
        u = xq[..., 0] ** 2 - xq[..., 1] ** 2 + xq[..., 2]
        uq = np.einsum("qk,tk->tq", lam, uh[mesh.tets])
        errors.append(np.sqrt(((uq - u) ** 2 * wq * vol6[:, None]).sum()))
        h_eff.append((vol6.sum() / 6 / len(mesh.tets)) ** (1 / 3))
    slope = np.polyfit(np.log(h_eff), np.log(errors), 1)[0]
    assert slope >= 1.8, (slope, errors)
