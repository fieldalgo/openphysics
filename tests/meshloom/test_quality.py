# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Mesh quality and size of ``meshloom.generate3d`` against the frozen baseline: V10 and V8.

Rows of docs/packages/meshine/validation3d.md, with the constants of its "Frozen
baseline constants" section (Gmsh 4.15.2 with the Netgen optimizer):

- V10 on C2 (unit cube), C3 (chip package, 3 regions), C4 (via r = 0.3 through
  [-1,1]^2 x [0,1]), C5 (sphere r = 0.5 in [-1,1]^3) and C6 (Fichera corner, [-1,1]^3
  minus [0,1]^3) at the plan's three sizes, all 15 pairs: the smallest dihedral angle
  is at least the gate, the mean q (3 inradius / circumradius) at least the floor and
  the tetrahedron count T within [0.75, 1.33] T_B. No input angle of these cases is
  below the exemption limits, so every tetrahedron counts. C4 and C5 come from
  ``meshloom.builder``.
- V9 on C1 (unit sphere) at three sizes: T within [0.85, 1.25] T_B, then the smallest
  dihedral angle at least 15°, the smallest q at least 0.30 and the mean q at least the
  floor.
- V6 on C1: the volume error e(h) = |sum V_T - 4 pi/3| / (4 pi/3) has a least-squares
  slope of at least 1.8 over the three sizes and e(0.05) <= 1.5e-3.
- V21 on C1: u = x^2 - y^2 + z with Dirichlet data; the P1 L2 error (degree-5 rule)
  has a slope of at least 1.8 against h_eff = (|Omega| / T)^(1/3) over the three sizes.
- V8 on C1 and C2 at three sizes and on C3 with the die at h/2: per region, the median of
  edge length over h within +-10% of the baseline median and the 95th percentile at
  most the baseline's + 0.10 (the die's edges over h/2).

The finest sizes run with the slow studies. Rows the mesher does not meet yet are not
here; they are listed on the meshloom page under its limits.
"""

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom import builder  # noqa: E402

try:  # the box assembly of the refinement tests; the installed-wheel check renames it
    from test_refine import C3_SEEDS, c2, c3, grid_plc  # noqa: E402
except ImportError:
    from test_meshloom_refine import C3_SEEDS, c2, c3, grid_plc  # noqa: E402


def c6():
    """Fichera corner: [-1,1]^3 minus [0,1]^3."""
    g = [-1.0, 0.0, 1.0]
    cells = {(i, j, k): "a" for i in range(2) for j in range(2) for k in range(2) if (i, j, k) != (1, 1, 1)}
    return grid_plc(g, g, g, cells)


def generate(case, h):
    if case == "C2":
        (pts, facets), _ = c2()
        return meshloom.generate3d(pts, facets, h=h)
    if case == "C3":
        (pts, facets), _ = c3()
        return meshloom.generate3d(pts, facets, h=h, region_points=C3_SEEDS)
    if case == "C4":
        return meshloom.generate3d(h=h, **builder.via_in_slab(h))
    if case == "C5":
        return meshloom.generate3d(h=h, **builder.sphere_in_box(h))
    if case == "C1":
        return meshloom.generate3d(h=h, **builder.sphere(h))
    pts, facets = c6()
    return meshloom.generate3d(pts, facets, h=h)


def dihedral_and_q(m):
    """Smallest dihedral angle (degrees) and q = 3 inradius / circumradius per tetrahedron."""
    x = m["nodes"][m["tetrahedra"]]
    a, b, c = x[:, 1] - x[:, 0], x[:, 2] - x[:, 0], x[:, 3] - x[:, 0]
    v6 = np.abs(np.einsum("ij,ij->i", a, np.cross(b, c)))
    area = sum(0.5 * np.linalg.norm(np.cross(x[:, j] - x[:, i], x[:, k] - x[:, i]), axis=1)
               for i, j, k in ((1, 2, 3), (0, 2, 3), (0, 1, 3), (0, 1, 2)))
    rin = 0.5 * v6 / area
    num = (np.einsum("ij,ij->i", a, a)[:, None] * np.cross(b, c) + np.einsum("ij,ij->i", b, b)[:, None] * np.cross(c, a)
           + np.einsum("ij,ij->i", c, c)[:, None] * np.cross(a, b))
    rc = np.linalg.norm(num, axis=1) / (2 * v6)
    angles = []
    for i, j, k, l in ((0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2), (1, 2, 0, 3), (1, 3, 0, 2), (2, 3, 0, 1)):
        e = x[:, j] - x[:, i]
        n1, n2 = np.cross(e, x[:, k] - x[:, i]), np.cross(e, x[:, l] - x[:, i])
        cos = np.einsum("ij,ij->i", n1, n2) / np.linalg.norm(n1, axis=1) / np.linalg.norm(n2, axis=1)
        angles.append(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
    return np.min(angles, axis=0), 3 * rin / rc


def edges(m):
    t = m["tetrahedra"]
    e = np.unique(np.sort(np.concatenate([t[:, [i, j]] for i in range(4) for j in range(i + 1, 4)]), axis=1), axis=0)
    return e, np.linalg.norm(m["nodes"][e[:, 0]] - m["nodes"][e[:, 1]], axis=1)


# (case, h): (min dihedral gate, mean q floor, T window), from the frozen baseline table
V10 = {
    ("C2", 0.12): (15.0, 0.7906, (2721, 4823)),
    ("C2", 0.06): (15.0, 0.8274, (15919, 28229)),
    ("C2", 0.03): (15.0, 0.8429, (118695, 210484)),
    ("C3", 0.8): (13.80, 0.7337, (3248, 5758)),
    ("C3", 0.4): (12.82, 0.7782, (16189, 28708)),
    ("C3", 0.2): (12.61, 0.8176, (105384, 186880)),
    ("C4", 0.2): (15.0, 0.7642, (2343, 4154)),
    ("C4", 0.1): (15.0, 0.8130, (14309, 25373)),
    ("C4", 0.05): (12.89, 0.8369, (99630, 176677)),
    ("C5", 0.24): (15.0, 0.7768, (2834, 5024)),
    ("C5", 0.12): (15.0, 0.8185, (17035, 30208)),
    ("C5", 0.06): (15.0, 0.8385, (120495, 213676)),
    ("C6", 0.24): (15.0, 0.7794, (2807, 4976)),
    ("C6", 0.12): (15.0, 0.8203, (14852, 26336)),
    ("C6", 0.06): (15.0, 0.8403, (103604, 183723)),
}
FINEST = {("C2", 0.03), ("C3", 0.2), ("C4", 0.05), ("C5", 0.06), ("C6", 0.06)}
V10_ROWS = [pytest.param(*k, marks=pytest.mark.slow) if k in FINEST else k for k in V10]


@pytest.mark.parametrize("case,h", V10_ROWS)
def test_v10_quality_against_the_baseline(case, h):
    theta_gate, q_floor, (lo, hi) = V10[(case, h)]
    theta, q = dihedral_and_q(generate(case, h))
    assert theta.min() >= theta_gate, (case, h, float(theta.min()))
    assert q.mean() >= q_floor, (case, h, float(q.mean()))
    assert lo <= len(q) <= hi, (case, h, len(q))


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


# V8: (median window, p95 bound) per case and size; C3 per region (substrate, die, mold)
V8_C1 = {0.2: ((1.060, 1.296), 1.771), 0.1: ((1.153, 1.409), 1.810), 0.05: ((1.191, 1.456), 1.810)}
V8_C2 = {0.12: ((0.947, 1.158), 1.684), 0.06: ((1.120, 1.369), 1.777), 0.03: ((1.166, 1.425), 1.782)}
V8_C3 = {
    0.96: (((0.687, 0.839), 1.332), ((0.827, 1.011), 1.480), ((0.688, 0.841), 1.339)),
    0.48: (((0.843, 1.031), 1.547), ((0.885, 1.081), 1.646), ((0.843, 1.030), 1.560)),
    0.24: (((0.893, 1.091), 1.604), ((1.049, 1.282), 1.766), ((0.893, 1.091), 1.623)),
}


@pytest.mark.parametrize("h", [0.12, 0.06, pytest.param(0.03, marks=pytest.mark.slow)])
def test_v8_cube_edge_lengths(h):
    (pts, facets), _ = c2()
    _, length = edges(meshloom.generate3d(pts, facets, h=h))
    (lo, hi), p95 = V8_C2[h]
    r = length / h
    assert lo <= np.median(r) <= hi, (h, float(np.median(r)))
    assert np.percentile(r, 95) <= p95, (h, float(np.percentile(r, 95)))


@pytest.mark.parametrize("h", [0.2, 0.1, pytest.param(0.05, marks=pytest.mark.slow)])
def test_v8_sphere_edge_lengths(h):
    _, length = edges(generate("C1", h))
    (lo, hi), p95 = V8_C1[h]
    r = length / h
    assert lo <= np.median(r) <= hi, (h, float(np.median(r)))
    assert np.percentile(r, 95) <= p95, (h, float(np.percentile(r, 95)))


def c3_regions(h):
    """Edge length over the region's h for C3 with the die at h/2: substrate, die, mold."""
    (pts, facets), _ = c3()
    m = meshloom.generate3d(pts, facets, h={"substrate": h, "die": h / 2, "mold": h}, region_points=C3_SEEDS)
    e, length = edges(m)
    mid = 0.5 * (m["nodes"][e[:, 0]] + m["nodes"][e[:, 1]])
    die = (mid[:, 0] >= 3) & (mid[:, 0] <= 7) & (mid[:, 1] >= 3) & (mid[:, 1] <= 7) & (mid[:, 2] >= 1) & (mid[:, 2] <= 1.5)
    r = length / np.where(die, h / 2, h)
    below = mid[:, 2] < 1
    return {"substrate": r[below & ~die], "die": r[die], "mold": r[~below & ~die]}


@pytest.mark.parametrize("h", [0.96, 0.48, pytest.param(0.24, marks=pytest.mark.slow)])
def test_v8_chip_edge_lengths_per_region(h):
    ratios = c3_regions(h)
    for (name, r), ((lo, hi), p95) in zip(ratios.items(), V8_C3[h]):
        assert lo <= np.median(r) <= hi, (h, name, float(np.median(r)))
        assert np.percentile(r, 95) <= p95, (h, name, float(np.percentile(r, 95)))
